"""0016 candidate_priority v0 migration 测试。

覆盖:
    1. 空库依次运行全部 migration 成功(新表/新列存在)
    2. 0015 已有 CandidateSet 行在 0016 后仍可查询
    3. 同一 Thesis/基金可在两个不同 candidate_set_id 中存在
    4. 同一集合内重复基金失败
    5. PriorityResult UPDATE 被 trigger 拒绝
    6. PriorityResult DELETE 被 trigger 拒绝
    7. CandidateSet 冻结字段不能 UPDATE
    8. 同一 PriorityRun 幂等组合只能成功一次
    9. candidate_priority_json 能完整 round-trip
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.persistence.migrations_runner import (
    _split_statements,
    list_migrations,
    run_migrations,
)


# ============================================================
# 辅助函数
# ============================================================
def _run_migrations_up_to(db_path: str, last_mig_id: str) -> None:
    """运行 migration 直到(含)指定 ID,用于测试旧库升级路径。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        for path in list_migrations():
            mig_id = path.stem
            if mig_id > last_mig_id:
                break
            already = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE id=?", (mig_id,)
            ).fetchone()
            if already:
                continue
            sql = path.read_text(encoding="utf-8")
            for stmt in _split_statements(sql):
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" in str(exc).lower():
                        continue
                    raise
            conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
                (mig_id, datetime.now(UTC).isoformat(timespec="seconds")),
            )
            conn.commit()
    finally:
        conn.close()


def _insert_base_data(conn: sqlite3.Connection) -> None:
    """插入基础数据: strategy_policy, data_snapshot, research_input, thesis。"""
    conn.execute(
        """INSERT INTO strategy_policies
            (policy_id, version, business_mode, policy_status, approved_for_production,
             strategy_name, strategy_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("private_equity_growth", 1, "private_strategy", "active", 0,
         "私募主观权益成长型", "equity_long_only"),
    )
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES (?, ?)",
        ("snap_test1", "/tmp/fake.sqlite"),
    )
    conn.execute(
        """INSERT INTO research_inputs
            (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
             actor_role, request_source, raw_text, data_snapshot_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("ri_test1", "philosophy", "private_strategy", "private_equity_growth", 1,
         "researcher", "ad_hoc_research", "原始输入", "snap_test1", "received"),
    )
    conn.execute(
        """INSERT INTO investment_theses
            (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
             title, belief_statement, owner, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("th_test1", "ri_test1", "private_equity_growth", 1,
         "title", "belief", "owner", "draft"),
    )
    conn.commit()


def _insert_header(
    conn: sqlite3.Connection,
    candidate_set_id: str = "cs_test1",
    thesis_id: str = "th_test1",
    user_input_id: str = "ri_test1",
    data_snapshot_id: str = "snap_test1",
    source_method_version: str = "fund_candidate_evidence_v0",
) -> None:
    """插入一条 candidate_set_headers 记录。"""
    conn.execute(
        """INSERT INTO candidate_set_headers
            (candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
             source_method_version, scanned_fund_count, mapped_candidate_count,
             unmapped_due_to_data_count, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
         source_method_version, 10, 8, 2, "system"),
    )


def _insert_candidate(
    conn: sqlite3.Connection,
    candidate_id: str = "can_test1",
    candidate_set_id: str = "cs_test1",
    thesis_id: str = "th_test1",
    user_input_id: str = "ri_test1",
    asset_code: str = "000001",
    asset_name: str = "基金1",
) -> None:
    """插入一条 candidate_sets 记录。"""
    conn.execute(
        """INSERT INTO candidate_sets
            (candidate_id, candidate_set_id, thesis_id, user_input_id,
             asset_type, asset_code, asset_name, data_snapshot_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (candidate_id, candidate_set_id, thesis_id, user_input_id,
         "fund", asset_code, asset_name, "snap_test1"),
    )


def _insert_priority_run(
    conn: sqlite3.Connection,
    priority_run_id: str = "pr_test1",
    candidate_set_id: str = "cs_test1",
    thesis_id: str = "th_test1",
    user_input_id: str = "ri_test1",
    strategy_policy_id: str = "private_equity_growth",
    strategy_policy_version: int = 1,
    data_snapshot_id: str = "snap_test1",
    ranking_method_version: str = "fund_priority_v0",
) -> None:
    """插入一条 candidate_priority_runs 记录。"""
    conn.execute(
        """INSERT INTO candidate_priority_runs
            (priority_run_id, candidate_set_id, thesis_id, user_input_id,
             strategy_policy_id, strategy_policy_version, data_snapshot_id,
             ranking_method_version, result_type,
             evaluated_candidate_count, eligible_candidate_count, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (priority_run_id, candidate_set_id, thesis_id, user_input_id,
         strategy_policy_id, strategy_policy_version, data_snapshot_id,
         ranking_method_version, "full",
         8, 5, "system"),
    )


def _insert_priority_result(
    conn: sqlite3.Connection,
    priority_result_id: str = "pres_test1",
    priority_run_id: str = "pr_test1",
    candidate_id: str = "can_test1",
    fund_code: str = "000001",
) -> None:
    """插入一条 candidate_priority_results 记录。"""
    conn.execute(
        """INSERT INTO candidate_priority_results
            (priority_result_id, priority_run_id, candidate_id, fund_code,
             eligibility_status, priority_tier, priority_rank)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (priority_result_id, priority_run_id, candidate_id, fund_code,
         "eligible", "tier1", 1),
    )


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    """一个干净空库,从未跑过 migration。"""
    db = tmp_path / "gov.sqlite"
    return db


@pytest.fixture()
def migrated_db(fresh_db: Path) -> Path:
    """已跑完全部 migration(含 0016)的库。"""
    run_migrations(str(fresh_db))
    return fresh_db


@pytest.fixture()
def conn_with_data(migrated_db: Path):
    """已建好全部表,且预置基础数据(strategy_policy/data_snapshot/research_input/thesis)。"""
    conn = sqlite3.connect(str(migrated_db))
    conn.execute("PRAGMA foreign_keys = ON")
    _insert_base_data(conn)
    yield conn
    conn.close()


# ============================================================
# 测试
# ============================================================
class TestCandidatePriorityMigration:
    def test_empty_db_all_migrations_success(self, fresh_db: Path):
        """空库 -> run_migrations 应当成功,新表和新列都存在。"""
        run_migrations(str(fresh_db))
        conn = sqlite3.connect(str(fresh_db))
        try:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "candidate_set_headers" in names
            assert "candidate_priority_runs" in names
            assert "candidate_priority_results" in names
            # strategy_policies 有 candidate_priority_json 列
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(strategy_policies)").fetchall()
            }
            assert "candidate_priority_json" in cols
        finally:
            conn.close()

    def test_legacy_candidate_sets_preserved_after_0016(self, fresh_db: Path):
        """0015 已有 candidate_sets 行在 0016 后仍可查询。"""
        # 先只跑到 0015
        _run_migrations_up_to(str(fresh_db), "0015_governance_core")
        conn = sqlite3.connect(str(fresh_db))
        _insert_base_data(conn)
        # 旧表(0015)没有 FK 到 candidate_set_headers,可以直接插入
        conn.execute(
            """INSERT INTO candidate_sets
                (candidate_id, candidate_set_id, thesis_id, user_input_id,
                 asset_type, asset_code, asset_name, data_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("can_legacy1", "cs_legacy1", "th_test1", "ri_test1",
             "fund", "000001", "基金1", "snap_test1"),
        )
        conn.commit()
        conn.close()

        # 跑 0016
        run_migrations(str(fresh_db))

        # 验证数据仍在
        conn = sqlite3.connect(str(fresh_db))
        try:
            row = conn.execute(
                "SELECT candidate_id, candidate_set_id, asset_code FROM candidate_sets "
                "WHERE candidate_id='can_legacy1'"
            ).fetchone()
            assert row is not None, "legacy candidate_sets 行丢失"
            assert row == ("can_legacy1", "cs_legacy1", "000001")
            # header 也应该被自动创建
            header = conn.execute(
                "SELECT candidate_set_id, source_method_version FROM candidate_set_headers "
                "WHERE candidate_set_id='cs_legacy1'"
            ).fetchone()
            assert header is not None, "legacy header 未创建"
            assert header[1] == "legacy_governance_v0"
        finally:
            conn.close()

    def test_same_thesis_fund_in_different_sets(self, conn_with_data):
        """同一 Thesis/基金可在两个不同 candidate_set_id 中存在。"""
        c = conn_with_data
        # 使用不同 source_method_version 以满足 header 的 UNIQUE 约束
        _insert_header(c, candidate_set_id="cs_a", source_method_version="method_v0")
        _insert_header(c, candidate_set_id="cs_b", source_method_version="method_v1")
        _insert_candidate(c, candidate_id="can_a", candidate_set_id="cs_a", asset_code="000001")
        # 同 thesis_id, 不同 candidate_set_id, 同 asset_code -> 应当成功
        _insert_candidate(c, candidate_id="can_b", candidate_set_id="cs_b", asset_code="000001")
        c.commit()
        rows = c.execute(
            "SELECT candidate_id FROM candidate_sets WHERE asset_code='000001' ORDER BY candidate_id"
        ).fetchall()
        assert len(rows) == 2

    def test_same_set_duplicate_fund_fails(self, conn_with_data):
        """同一 candidate_set_id + asset_code 插入两次抛 IntegrityError。"""
        c = conn_with_data
        _insert_header(c, candidate_set_id="cs_dup")
        _insert_candidate(c, candidate_id="can_d1", candidate_set_id="cs_dup", asset_code="000001")
        c.commit()
        with pytest.raises(sqlite3.IntegrityError):
            _insert_candidate(
                c, candidate_id="can_d2", candidate_set_id="cs_dup", asset_code="000001"
            )
            c.commit()

    def test_priority_result_update_rejected(self, conn_with_data):
        """PriorityResult UPDATE 被 trigger 拒绝。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_priority_run(c)
        _insert_priority_result(c)
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_priority_results SET priority_tier='tier2' "
                "WHERE priority_result_id='pres_test1'"
            )
            c.commit()

    def test_priority_result_delete_rejected(self, conn_with_data):
        """PriorityResult DELETE 被 trigger 拒绝。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_priority_run(c)
        _insert_priority_result(c)
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            c.execute("DELETE FROM candidate_priority_results WHERE priority_result_id='pres_test1'")
            c.commit()

    def test_candidate_evidence_immutable(self, conn_with_data):
        """candidate_evidence_json 列 UPDATE 抛 IntegrityError。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_sets SET candidate_evidence_json='{\"k\":1}' "
                "WHERE candidate_id='can_test1'"
            )
            c.commit()

    def test_priority_run_idempotent_unique(self, conn_with_data):
        """相同的 (candidate_set_id, strategy_policy_id, strategy_policy_version,
        data_snapshot_id, ranking_method_version) 插入两次抛 IntegrityError。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_priority_run(c, priority_run_id="pr_idem1")
        c.commit()
        with pytest.raises(sqlite3.IntegrityError):
            _insert_priority_run(c, priority_run_id="pr_idem2")
            c.commit()

    def test_candidate_priority_json_roundtrip(self, conn_with_data):
        """插入包含嵌套数组的 candidate_priority_json,读回后 json.loads 结构完整。"""
        c = conn_with_data
        nested = {
            "method_version": "fund_priority_v0",
            "tiers": [
                {"name": "tier1", "min_score": 0.8},
                {"name": "tier2", "min_score": 0.6},
            ],
            "required_evidence": [
                "business_logic",
                "earnings_or_cashflow",
            ],
            "thresholds": {
                "minimum_target_holding_weight": 0.03,
                "minimum_disclosed_holding_weight": 0.10,
            },
        }
        c.execute(
            "UPDATE strategy_policies SET candidate_priority_json=? "
            "WHERE policy_id='private_equity_growth' AND version=1",
            (json.dumps(nested, ensure_ascii=False),),
        )
        c.commit()
        row = c.execute(
            "SELECT candidate_priority_json FROM strategy_policies "
            "WHERE policy_id='private_equity_growth' AND version=1"
        ).fetchone()
        assert row is not None
        result = json.loads(row[0])
        assert result["method_version"] == "fund_priority_v0"
        assert len(result["tiers"]) == 2
        assert result["tiers"][0]["name"] == "tier1"
        assert result["thresholds"]["minimum_target_holding_weight"] == 0.03
        assert "earnings_or_cashflow" in result["required_evidence"]

    def test_candidate_set_headers_immutable(self, conn_with_data):
        """candidate_set_headers 整行不可变，UPDATE 抛 IntegrityError。"""
        c = conn_with_data
        _insert_header(c)
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_set_headers SET scanned_fund_count = 999 "
                "WHERE candidate_set_id = 'cs_test1'"
            )
            c.commit()

    def test_candidate_sets_frozen_fields_immutable(self, conn_with_data):
        """candidate_sets 冻结字段（fit_score, asset_code 等）不可变。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        c.commit()

        # fit_score 不可变
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_sets SET fit_score = 0.99 "
                "WHERE candidate_id = 'can_test1'"
            )
            c.commit()

        # asset_code 不可变
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_sets SET asset_code = '999999' "
                "WHERE candidate_id = 'can_test1'"
            )
            c.commit()

        # asset_type 不可变
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE candidate_sets SET asset_type = 'stock' "
                "WHERE candidate_id = 'can_test1'"
            )
            c.commit()

    def test_candidate_sets_non_frozen_fields_can_update(self, conn_with_data):
        """candidate_sets 非冻结字段（candidate_status, reviewed_at）可以更新。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        c.commit()
        # candidate_status 可以更新
        c.execute(
            "UPDATE candidate_sets SET candidate_status = 'reviewed' "
            "WHERE candidate_id = 'can_test1'"
        )
        c.commit()
        row = c.execute(
            "SELECT candidate_status FROM candidate_sets WHERE candidate_id = 'can_test1'"
        ).fetchone()
        assert row[0] == "reviewed"


# ============================================================
# 0017 旧库升级测试
# ============================================================
class Test0017Upgrade:
    """验证已执行 0016 的旧库通过 0017 获得新列。"""

    def test_old_db_upgrade_gets_unrelated_fund_count(self, fresh_db: Path):
        """旧库（只跑到 0016）升级到 0017 后，candidate_set_headers 有 unrelated_fund_count。"""
        # 1. 模拟旧库：只跑到 0016
        _run_migrations_up_to(str(fresh_db), "0016_candidate_priority_v0")

        # 2. 确认 0016 没有 unrelated_fund_count
        conn = sqlite3.connect(str(fresh_db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(candidate_set_headers)").fetchall()]
        assert "unrelated_fund_count" not in cols
        conn.close()

        # 3. 插入一条旧格式的 header（没有 unrelated_fund_count）
        conn = sqlite3.connect(str(fresh_db))
        _insert_base_data(conn)
        _insert_header(conn)
        conn.commit()
        conn.close()

        # 4. 运行全部 migration（包括 0017）
        run_migrations(str(fresh_db))

        # 5. 验证列存在
        conn = sqlite3.connect(str(fresh_db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(candidate_set_headers)").fetchall()]
        assert "unrelated_fund_count" in cols

        # 6. 验证旧数据默认值为 0
        row = conn.execute(
            "SELECT unrelated_fund_count FROM candidate_set_headers WHERE candidate_set_id = 'cs_test1'"
        ).fetchone()
        assert row[0] == 0
        conn.close()

    def test_new_db_has_unrelated_fund_count(self, fresh_db: Path):
        """新库从头运行全部 migration，unrelated_fund_count 存在。"""
        run_migrations(str(fresh_db))
        conn = sqlite3.connect(str(fresh_db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(candidate_set_headers)").fetchall()]
        assert "unrelated_fund_count" in cols
        conn.close()

    def test_0017_idempotent_rerun(self, fresh_db: Path):
        """0017 已执行后，重复运行 migration 不会报错。"""
        run_migrations(str(fresh_db))
        # 再次运行不应该报错
        run_migrations(str(fresh_db))
        conn = sqlite3.connect(str(fresh_db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(candidate_set_headers)").fetchall()]
        assert "unrelated_fund_count" in cols
        conn.close()


# ============================================================
# 0018 fund_recommendation 测试
# ============================================================
def _insert_recommendation_run_and_result(conn: sqlite3.Connection) -> None:
    """插入一条 fund_recommendation_runs 和 fund_recommendation_results 记录。"""
    conn.execute(
        """INSERT INTO fund_recommendation_runs
            (recommendation_run_id, candidate_set_id, thesis_id, user_input_id,
             strategy_policy_id, strategy_policy_version, data_snapshot_id,
             recommendation_method_version, result_type,
             evaluated_candidate_count, recommended_count, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("frr_test1", "cs_test1", "th_test1", "ri_test1",
         "private_equity_growth", 1, "snap_test1",
         "fund_recommendation_v1", "ranked_recommendations",
         3, 2, "system"),
    )
    conn.execute(
        """INSERT INTO fund_recommendation_results
            (recommendation_result_id, recommendation_run_id, candidate_id,
             fund_code, fund_name, product_category, recommendation_tier,
             category_rank, theme_exposure_score, thesis_alignment_score,
             risk_return_score, fund_quality_score, total_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("frrr_test1", "frr_test1", "can_test1",
         "000001", "基金1", "active_fund", "candidate_pool",
         1, 0.85, 0.70, 0.60, 0.75, 0.78),
    )
    conn.commit()


class Test0018FundRecommendation:
    """0018 fund_recommendation migration 测试。"""

    def test_recommendation_tables_exist(self, migrated_db: Path):
        """新库跑完全部 migration 后，推荐表存在。"""
        conn = sqlite3.connect(str(migrated_db))
        try:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {"fund_recommendation_runs", "fund_recommendation_results"} <= tables
            # strategy_policies 有 fund_recommendation_json 列
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(strategy_policies)").fetchall()
            }
            assert "fund_recommendation_json" in cols
        finally:
            conn.close()

    def test_recommendation_results_are_immutable(self, conn_with_data):
        """RecommendationResult UPDATE 被 trigger 拒绝，错误含 'immutable'。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_recommendation_run_and_result(c)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "UPDATE fund_recommendation_results SET total_score = 0"
            )
            c.commit()

    def test_recommendation_results_cannot_be_deleted(self, conn_with_data):
        """RecommendationResult DELETE 被 trigger 拒绝。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_recommendation_run_and_result(c)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            c.execute(
                "DELETE FROM fund_recommendation_results "
                "WHERE recommendation_result_id='frrr_test1'"
            )
            c.commit()

    def test_recommendation_run_idempotent_unique(self, conn_with_data):
        """相同的幂等键组合插入两次抛 IntegrityError。"""
        c = conn_with_data
        _insert_header(c)
        _insert_candidate(c)
        _insert_recommendation_run_and_result(c)
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                """INSERT INTO fund_recommendation_runs
                    (recommendation_run_id, candidate_set_id, thesis_id, user_input_id,
                     strategy_policy_id, strategy_policy_version, data_snapshot_id,
                     recommendation_method_version, result_type,
                     evaluated_candidate_count, recommended_count, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("frr_test2", "cs_test1", "th_test1", "ri_test1",
                 "private_equity_growth", 1, "snap_test1",
                 "fund_recommendation_v1", "ranked_recommendations",
                 3, 2, "system"),
            )
            c.commit()

    def test_fund_recommendation_json_roundtrip(self, conn_with_data):
        """fund_recommendation_json 能完整 round-trip。"""
        c = conn_with_data
        nested = {
            "method_version": "fund_recommendation_v1",
            "source_method_version": "fund_candidate_evidence_v0",
            "minimum_target_holding_weight": 0.03,
            "maximum_holding_age_days": 180,
            "active_fund_limit": 3,
            "etf_or_index_limit": 3,
            "alternative_limit": 2,
            "weights": {
                "theme_exposure": 0.55,
                "thesis_alignment": 0.15,
                "risk_return": 0.15,
                "fund_quality": 0.15,
            },
        }
        c.execute(
            "UPDATE strategy_policies SET fund_recommendation_json=? "
            "WHERE policy_id='private_equity_growth' AND version=1",
            (json.dumps(nested, ensure_ascii=False),),
        )
        c.commit()
        row = c.execute(
            "SELECT fund_recommendation_json FROM strategy_policies "
            "WHERE policy_id='private_equity_growth' AND version=1"
        ).fetchone()
        assert row is not None
        result = json.loads(row[0])
        assert result["method_version"] == "fund_recommendation_v1"
        assert result["weights"]["theme_exposure"] == 0.55
        assert result["active_fund_limit"] == 3
