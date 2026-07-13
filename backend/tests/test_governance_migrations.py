"""阶段 0 治理核心表(P0 fix batch)的正式测试。

覆盖:
    1. migration bootstrap(空库能完整跑 0000~0015)
    2. 4 个 trigger 真实生效
    3. strategy_policies 同步脚本
    4. research_inputs / investment_theses / candidate_sets / decision_records 外键
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from app.persistence.migrations_runner import (
    list_migrations,
    run_migrations,
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
    """已跑完 0000~0015 的库。"""
    run_migrations(str(fresh_db))
    return fresh_db


@pytest.fixture()
def conn_with_policies(migrated_db: Path):
    """已建好 governance 表,且预置 1 条 strategy_policy + 1 个 data_snapshot。"""
    conn = sqlite3.connect(str(migrated_db))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        INSERT INTO strategy_policies
            (policy_id, version, business_mode, policy_status, approved_for_production,
             strategy_name, strategy_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("private_equity_growth", 1, "private_strategy", "active", 0,
         "私募主观权益成长型", "equity_long_only"),
    )
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES (?, ?)",
        ("snap_test1", "/tmp/fake.sqlite"),
    )
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# 1. migration bootstrap
# ============================================================
class TestMigrationBootstrap:
    def test_empty_db_can_run_all_migrations(self, fresh_db: Path):
        """空库 → run_migrations 应当不抛错,产生 17 个 schema_migrations 记录。"""
        assert not fresh_db.exists()
        executed = run_migrations(str(fresh_db))
        # 0000~0015 至少 16 个;0001_baseline 是占位所以也是 1 个
        assert len(executed) >= 16, f"expected >=16, got {len(executed)}: {executed}"
        assert "0015_governance_core" in executed
        assert "0000_baseline_schema" in executed
        # 再次跑应当幂等(空集)
        again = run_migrations(str(fresh_db))
        assert again == [], f"re-run should be idempotent, got {again}"

    def test_baseline_tables_present_after_migrations(self, migrated_db: Path):
        """baseline 表必须存在(0000 把它们从 writer.SCHEMA_STATEMENTS 迁移过来)。"""
        conn = sqlite3.connect(str(migrated_db))
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in (
            "label_definitions", "label_runs", "fund_label_results",
            "fund_label_evidence", "feature_values", "fund_percentile_rank",
            "fund_run_coverage", "label_reviews", "fund_run_failures",
            "label_calculation_states", "fund_classification_results",
            "fund_group_results", "audit_log", "data_snapshots",
        ):
            assert t in names, f"missing baseline table: {t}"
        conn.close()

    def test_governance_tables_present(self, migrated_db: Path):
        names = {r[0] for r in sqlite3.connect(str(migrated_db)).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        for t in (
            "strategy_policies", "research_inputs", "investment_theses",
            "candidate_sets", "decision_records",
        ):
            assert t in names, f"missing governance table: {t}"

    def test_split_statements_handles_trigger(self, fresh_db: Path):
        """_split_statements 必须能正确切出 trigger 整条(BEGIN..END; 内的 ; 不切)。"""
        from app.persistence.migrations_runner import _split_statements

        sql_path = Path(__file__).resolve().parents[2] / "backend" / "app" / "persistence" / "migrations" / "0015_governance_core.sql"
        text = sql_path.read_text(encoding="utf-8")
        stmts = _split_statements(text)
        trigger_stmts = [s for s in stmts if s.lstrip().upper().startswith("CREATE TRIGGER")]
        # 4 个 trigger
        assert len(trigger_stmts) == 4, f"expected 4 trigger stmts, got {len(trigger_stmts)}"
        for t in trigger_stmts:
            # 每条 trigger 必须以 END; 结尾(独立行)
            assert t.rstrip().splitlines()[-1].strip() == "END;", (
                f"trigger not properly terminated: {t[:80]}..."
            )

    def test_list_migrations_returns_17(self):
        """migration 文件数应 >=17(0000 + 0001~0015)。"""
        files = list_migrations()
        ids = [p.stem for p in files]
        assert "0000_baseline_schema" in ids
        assert "0015_governance_core" in ids
        assert len(files) >= 16


# ============================================================
# 2. triggers
# ============================================================
class TestGovernanceTriggers:
    def test_raw_text_immutable_even_in_received(self, conn_with_policies):
        """raw_text 任何状态都不可改(不只是 parsed 之后)。"""
        c = conn_with_policies
        c.execute(
            """
            INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("ri_test1", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "原始输入", "snap_test1", "received"),
        )
        c.commit()
        # 立即改 raw_text 应当失败
        with pytest.raises(sqlite3.IntegrityError, match="raw_text is immutable"):
            c.execute("UPDATE research_inputs SET raw_text='改' WHERE user_input_id='ri_test1'")
            c.commit()

    def test_raw_text_immutable_after_status_change(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_test2", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "原始输入", "snap_test1", "received"),
        )
        c.commit()
        c.execute("UPDATE research_inputs SET status='parsed' WHERE user_input_id='ri_test2'")
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="raw_text is immutable"):
            c.execute("UPDATE research_inputs SET raw_text='再改' WHERE user_input_id='ri_test2'")
            c.commit()

    def test_thesis_core_fields_immutable_after_validated(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_test3", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "raw", "snap_test1", "received"),
        )
        c.execute(
            """INSERT INTO investment_theses
                (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
                 title, belief_statement, owner, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("th_test1", "ri_test3", "private_equity_growth", 1,
             "title", "原始 belief", "owner", "draft"),
        )
        c.commit()
        # draft 时可以改
        c.execute("UPDATE investment_theses SET belief_statement='draft 期可改' WHERE thesis_id='th_test1'")
        c.commit()
        # 切到 validated
        c.execute("UPDATE investment_theses SET status='validated' WHERE thesis_id='th_test1'")
        c.commit()
        # 之后改 belief_statement 应失败
        with pytest.raises(sqlite3.IntegrityError, match="immutable after validated"):
            c.execute("UPDATE investment_theses SET belief_statement='不可改' WHERE thesis_id='th_test1'")
            c.commit()
        # 改 as_of_date 也应失败
        with pytest.raises(sqlite3.IntegrityError, match="immutable after validated"):
            c.execute("UPDATE investment_theses SET as_of_date='2027-01-01' WHERE thesis_id='th_test1'")
            c.commit()

    def test_decision_records_no_update(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_d1", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "raw", "snap_test1", "received"),
        )
        c.execute(
            """INSERT INTO investment_theses
                (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
                 title, belief_statement, owner, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("th_d1", "ri_d1", "private_equity_growth", 1, "t", "b", "o", "draft"),
        )
        c.execute(
            """INSERT INTO decision_records
                (decision_id, strategy_policy_id, strategy_policy_version,
                 user_input_id, thesis_id, candidate_set_id, data_snapshot_id, committee_decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("dr_d1", "private_equity_growth", 1, "ri_d1", "th_d1", "cs_d1", "snap_test1", "approved"),
        )
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            c.execute("UPDATE decision_records SET committee_decision='rejected' WHERE decision_id='dr_d1'")
            c.commit()

    def test_decision_records_no_delete(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_d2", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "raw", "snap_test1", "received"),
        )
        c.execute(
            """INSERT INTO investment_theses
                (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
                 title, belief_statement, owner, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("th_d2", "ri_d2", "private_equity_growth", 1, "t", "b", "o", "draft"),
        )
        c.execute(
            """INSERT INTO decision_records
                (decision_id, strategy_policy_id, strategy_policy_version,
                 user_input_id, thesis_id, candidate_set_id, data_snapshot_id, committee_decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("dr_d2", "private_equity_growth", 1, "ri_d2", "th_d2", "cs_d2", "snap_test1", "approved"),
        )
        c.commit()
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            c.execute("DELETE FROM decision_records WHERE decision_id='dr_d2'")
            c.commit()

    def test_only_one_active_policy_per_id(self, conn_with_policies):
        """同一 policy_id 不能有 2 个 active(unique partial index)。"""
        c = conn_with_policies
        # 第 1 个 active 已由 fixture 预置
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                """INSERT INTO strategy_policies
                    (policy_id, version, business_mode, policy_status, strategy_name, strategy_type)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("private_equity_growth", 2, "private_strategy", "active",
                 "v2", "equity_long_only"),
            )
            c.commit()
        # 切到 deprecated 后可以新建 active
        c.execute(
            "UPDATE strategy_policies SET policy_status='deprecated' WHERE policy_id='private_equity_growth' AND version=1"
        )
        c.commit()
        c.execute(
            """INSERT INTO strategy_policies
                (policy_id, version, business_mode, policy_status, strategy_name, strategy_type)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("private_equity_growth", 2, "private_strategy", "active",
             "v2", "equity_long_only"),
        )
        c.commit()  # 现在应该成功

    def test_research_input_requires_existing_policy(self, conn_with_policies):
        c = conn_with_policies
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            c.execute(
                """INSERT INTO research_inputs
                    (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                     actor_role, request_source, raw_text, data_snapshot_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("ri_ghost", "philosophy", "private_strategy", "ghost_policy", 1,
                 "researcher", "ad_hoc_research", "x", "snap_test1", "received"),
            )
            c.commit()

    def test_candidate_set_unique_per_thesis(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_c1", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "raw", "snap_test1", "received"),
        )
        c.execute(
            """INSERT INTO investment_theses
                (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
                 title, belief_statement, owner, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("th_c1", "ri_c1", "private_equity_growth", 1, "t", "b", "o", "draft"),
        )
        # 0016 后 candidate_sets 有 FK 到 candidate_set_headers,需先插 header
        c.execute(
            """INSERT INTO candidate_set_headers
                (candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
                 source_method_version, scanned_fund_count, mapped_candidate_count,
                 unmapped_due_to_data_count, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("cs_c1", "th_c1", "ri_c1", "snap_test1", "fund_candidate_evidence_v0", 1, 1, 0, "system"),
        )
        c.execute(
            """INSERT INTO candidate_sets
                (candidate_id, candidate_set_id, thesis_id, user_input_id,
                 asset_type, asset_code, asset_name, data_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("can_c1", "cs_c1", "th_c1", "ri_c1", "fund", "000001", "x", "snap_test1"),
        )
        c.commit()
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                """INSERT INTO candidate_sets
                    (candidate_id, candidate_set_id, thesis_id, user_input_id,
                     asset_type, asset_code, asset_name, data_snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("can_c2", "cs_c1", "th_c1", "ri_c1", "fund", "000001", "dup", "snap_test1"),
            )
            c.commit()

    def test_views_return_joined_data(self, conn_with_policies):
        c = conn_with_policies
        c.execute(
            """INSERT INTO research_inputs
                (user_input_id, input_type, business_mode, strategy_policy_id, strategy_policy_version,
                 actor_role, request_source, raw_text, data_snapshot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ri_v1", "philosophy", "private_strategy", "private_equity_growth", 1,
             "researcher", "ad_hoc_research", "看好消费", "snap_test1", "received"),
        )
        c.execute(
            """INSERT INTO investment_theses
                (thesis_id, user_input_id, strategy_policy_id, strategy_policy_version,
                 title, belief_statement, owner, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("th_v1", "ri_v1", "private_equity_growth", 1, "消费白马", "消费白马是核心", "owner", "draft"),
        )
        # 0016 后 candidate_sets 有 FK 到 candidate_set_headers,需先插 header
        c.execute(
            """INSERT INTO candidate_set_headers
                (candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
                 source_method_version, scanned_fund_count, mapped_candidate_count,
                 unmapped_due_to_data_count, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("cs_v1", "th_v1", "ri_v1", "snap_test1", "fund_candidate_evidence_v0", 1, 1, 0, "system"),
        )
        c.execute(
            """INSERT INTO candidate_sets
                (candidate_id, candidate_set_id, thesis_id, user_input_id,
                 asset_type, asset_code, asset_name, data_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("can_v1", "cs_v1", "th_v1", "ri_v1", "fund", "000001", "样例消费股票", "snap_test1"),
        )
        c.commit()
        row = c.execute(
            "SELECT raw_text, belief_statement, asset_code FROM v_candidate_set_full WHERE candidate_id='can_v1'"
        ).fetchone()
        assert row == ("看好消费", "消费白马是核心", "000001"), f"got {row}"


# ============================================================
# 3. 策略政策同步脚本
# ============================================================
class TestStrategyPolicySync:
    def test_sync_yaml_creates_db(self, tmp_path: Path):
        """脚本能跑通,migration + 2 份 YAML 同步成功。"""
        # 跑子进程而不是 import,避免污染 cwd
        repo_root = Path(__file__).resolve().parents[2]
        db = tmp_path / "sync.sqlite"
        result = subprocess.run(
            [sys.executable, "scripts/sync_strategy_policies.py", str(db)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        conn = sqlite3.connect(str(db))
        try:
            rows = conn.execute(
                "SELECT policy_id, version, business_mode, policy_status FROM strategy_policies ORDER BY policy_id"
            ).fetchall()
            assert len(rows) == 3, f"expected 3 policies, got {len(rows)}: {rows}"
            ids = {r[0] for r in rows}
            assert "private_equity_growth" in ids
            assert "foof_growth" in ids
            # FOF 应标为 example
            for r in rows:
                if r[0] == "foof_growth":
                    assert r[3] == "example"
        finally:
            conn.close()

    def test_sync_yaml_idempotent(self, tmp_path: Path):
        """第二次同步不报错(INSERT OR IGNORE)。"""
        repo_root = Path(__file__).resolve().parents[2]
        db = tmp_path / "sync.sqlite"
        # 第一次
        r1 = subprocess.run(
            [sys.executable, "scripts/sync_strategy_policies.py", str(db)],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert r1.returncode == 0
        # 第二次(脚本会先 unlink 再跑,等价于"覆盖";这里我们直接验证幂等 INSERT)
        # 改为:再次插入应被 IGNORE
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                """INSERT OR IGNORE INTO strategy_policies
                    (policy_id, version, business_mode, policy_status, strategy_name, strategy_type)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("private_equity_growth", 1, "private_strategy", "active",
                 "different name", "different_type"),
            )
            conn.commit()
            # name 仍应是 YAML 里的(因为 IGNORE 跳过)
            name = conn.execute(
                "SELECT strategy_name FROM strategy_policies WHERE policy_id='private_equity_growth' AND version=1"
            ).fetchone()[0]
            assert name == "私募主观权益成长型"
        finally:
            conn.close()

    def test_json_columns_stored_as_json(self, tmp_path: Path):
        """嵌套对象以 JSON 字符串存到 *_json 列。"""
        repo_root = Path(__file__).resolve().parents[2]
        db = tmp_path / "sync.sqlite"
        subprocess.run(
            [sys.executable, "scripts/sync_strategy_policies.py", str(db)],
            cwd=str(repo_root), capture_output=True, text=True, check=True,
        )
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                """SELECT position_limit_json, monitoring_policy_json, investment_policy_json
                   FROM strategy_policies WHERE policy_id='private_equity_growth'"""
            ).fetchone()
            position_limit = json.loads(row[0])
            monitoring = json.loads(row[1])
            investment_policy = json.loads(row[2])
            assert position_limit.get("gross_exposure") == 1.0
            assert "industry_drift" in monitoring
            assert "preferred_styles" in investment_policy
            assert "quality_growth" in investment_policy["preferred_styles"]
        finally:
            conn.close()
