"""CandidatePriorityRepository 测试:原子性、幂等、历史和查询。

覆盖:
    1. run + N results + audit 一次提交
    2. 第 N 个 result 失败则三类数据全部回滚
    3. 相同幂等键查询到已有 ID
    4. 新 snapshot 生成新 run
    5. 旧 run 不变
    6. 按 Thesis 历史倒序
    7. JSON 坏数据不静默
    8. 参数化查询可抵御包含引号的 fund code
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app.persistence.candidate_priority import CandidatePriorityRepository
from app.persistence.migrations_runner import run_migrations


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture()
def fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "priority.sqlite"
    return db


@pytest.fixture()
def migrated_db(fresh_db: Path) -> Path:
    run_migrations(str(fresh_db))
    return fresh_db


@pytest.fixture()
def repo(migrated_db: Path) -> CandidatePriorityRepository:
    return CandidatePriorityRepository(migrated_db)


@pytest.fixture()
def conn_with_data(migrated_db: Path):
    """已建好基础数据。"""
    conn = sqlite3.connect(str(migrated_db))
    conn.execute("PRAGMA foreign_keys = ON")
    # 插入 strategy_policies
    conn.execute(
        "INSERT INTO strategy_policies (policy_id, version, business_mode, "
        "policy_status, strategy_name, strategy_type) VALUES "
        "('p1', 1, 'private_strategy', 'active', '测试', 'equity_long_only')"
    )
    # 插入 data_snapshots
    conn.execute("INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES ('snap1', '/tmp/x')")
    conn.execute("INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES ('snap2', '/tmp/y')")
    # 插入 research_inputs
    conn.execute(
        "INSERT INTO research_inputs (user_input_id, input_type, business_mode, "
        "strategy_policy_id, strategy_policy_version, actor_role, request_source, "
        "raw_text, data_snapshot_id, status) VALUES "
        "('ri1', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
        "'ad_hoc_research', 'test', 'snap1', 'received')"
    )
    # 插入 investment_theses
    conn.execute(
        "INSERT INTO investment_theses (thesis_id, user_input_id, strategy_policy_id, "
        "strategy_policy_version, title, belief_statement, owner, status) VALUES "
        "('th1', 'ri1', 'p1', 1, 'title', 'belief', 'owner', 'draft')"
    )
    # 插入 candidate_set_headers
    conn.execute(
        "INSERT INTO candidate_set_headers (candidate_set_id, thesis_id, user_input_id, "
        "data_snapshot_id, source_method_version, scanned_fund_count, "
        "mapped_candidate_count, unmapped_due_to_data_count, created_by) VALUES "
        "('cs1', 'th1', 'ri1', 'snap1', 'method_v0', 10, 3, 7, 'system')"
    )
    # 插入 candidate_sets(3个候选)
    for i in range(1, 4):
        conn.execute(
            f"INSERT INTO candidate_sets (candidate_id, candidate_set_id, thesis_id, "
            f"user_input_id, asset_type, asset_code, asset_name, data_snapshot_id) VALUES "
            f"('can{i}', 'cs1', 'th1', 'ri1', 'fund', '00000{i}', '基金{i}', 'snap1')"
        )
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# 辅助函数
# ============================================================
def _make_run(**overrides) -> dict:
    defaults = {
        "priority_run_id": "cpr_001",
        "candidate_set_id": "cs1",
        "thesis_id": "th1",
        "user_input_id": "ri1",
        "strategy_policy_id": "p1",
        "strategy_policy_version": 1,
        "data_snapshot_id": "snap1",
        "ranking_method_version": "fund_priority_v0",
        "result_status": "completed",
        "result_type": "ranked_candidates",
        "scanned_fund_count": 10,
        "mapped_candidate_count": 3,
        "unmapped_due_to_data_count": 7,
        "evaluated_candidate_count": 3,
        "eligible_candidate_count": 2,
        "tier_counts": {
            "research_now": 1,
            "research_next": 1,
            "valuation_watch": 0,
            "data_insufficient": 0,
            "excluded": 1,
        },
        "created_by": "researcher_001",
    }
    defaults.update(overrides)
    return defaults


def _make_result(priority_run_id: str, candidate_id: str, **overrides) -> dict:
    defaults = {
        "priority_result_id": f"cprr_{candidate_id}",
        "priority_run_id": priority_run_id,
        "candidate_id": candidate_id,
        "fund_code": f"00000{candidate_id[-1]}",
        "fund_name": f"基金{candidate_id[-1]}",
        "eligibility_status": "eligible",
        "priority_tier": "research_now",
        "priority_rank": 1,
        "matched_holding_weight": 0.10,
        "disclosed_holding_weight": 0.30,
        "normalized_match_pct": 0.33,
        "fit_score": 0.10,
        "evidence_score": 0.75,
        "holdings_truth_status": "verified",
        "valuation_status": "fair",
        "data_quality_status": "sufficient",
        "holding_report_date": "2025-12-31",
        "dimension_results": {"data_quality_status": "sufficient", "valuation_status": "fair"},
        "priority_reasons": [{"code": "all_required_evidence_present", "message": "证据齐全"}],
        "exclusion_reasons": [],
    }
    defaults.update(overrides)
    return defaults


# ============================================================
# 1. run + N results + audit 一次提交
# ============================================================
class TestAtomicCommit:
    def test_run_results_audit_one_transaction(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """在同一个事务中插入 1 个 run + 3 个 result + 1 个 audit_log,全部成功提交。"""
        run = _make_run()
        results = [
            _make_result("cpr_001", "can1"),
            _make_result("cpr_001", "can2"),
            _make_result("cpr_001", "can3"),
        ]
        with repo.transaction() as tx:
            run_id = tx.insert_run(run)
            tx.insert_results(results)
            tx.insert_audit_log(
                action="create_priority_run",
                target_type="priority_run",
                target_id=run_id,
                payload={"result_count": 3},
                actor="researcher_001",
                run_id=run_id,
            )

        # 验证 run 落库
        stored_run = repo.get_run(run_id)
        assert stored_run is not None
        assert stored_run["priority_run_id"] == "cpr_001"
        assert stored_run["candidate_set_id"] == "cs1"
        assert stored_run["tier_counts"] == {
            "research_now": 1,
            "research_next": 1,
            "valuation_watch": 0,
            "data_insufficient": 0,
            "excluded": 1,
        }

        # 验证 3 个 result 落库
        stored_results = repo.get_results(run_id)
        assert len(stored_results) == 3
        # 验证 JSON 字段被正确解析
        r0 = stored_results[0]
        assert r0["dimension_results"] == {
            "data_quality_status": "sufficient",
            "valuation_status": "fair",
        }
        assert r0["priority_reasons"] == [
            {"code": "all_required_evidence_present", "message": "证据齐全"}
        ]
        assert r0["exclusion_reasons"] == []

        # 验证 audit_log 落库
        with repo._connect() as conn:  # noqa: SLF001
            row = conn.execute(
                "SELECT * FROM audit_log WHERE target_id = ?", (run_id,)
            ).fetchone()
        assert row is not None
        assert row["action"] == "create_priority_run"


# ============================================================
# 2. 第 N 个 result 失败则三类数据全部回滚
# ============================================================
class TestAtomicRollback:
    def test_third_result_failure_rolls_back_all(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """插入 run + 2 个 result,第 3 个 result 缺少必填字段(fund_code=None),
        事务回滚,run 和前 2 个 result 也不存在。"""
        run = _make_run()
        results = [
            _make_result("cpr_001", "can1"),
            _make_result("cpr_001", "can2"),
            _make_result("cpr_001", "can3", fund_code=None),  # NOT NULL 约束失败
        ]
        with pytest.raises(sqlite3.IntegrityError):
            with repo.transaction() as tx:
                tx.insert_run(run)
                tx.insert_results(results)

        # run 不应落库
        assert repo.get_run("cpr_001") is None
        # result 不应落库
        assert repo.get_results("cpr_001") == []


# ============================================================
# 3. 相同幂等键查询到已有 ID
# ============================================================
class TestIdempotencyKey:
    def test_same_idempotency_key_returns_existing_id(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """先插入一个 run,再用相同幂等键查询 get_existing_run_id(),
        返回已有的 priority_run_id。"""
        run = _make_run()
        with repo.transaction() as tx:
            tx.insert_run(run)

        existing_id = repo.get_existing_run_id(
            candidate_set_id="cs1",
            strategy_policy_id="p1",
            strategy_policy_version=1,
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
        )
        assert existing_id == "cpr_001"

    def test_different_idempotency_key_returns_none(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """不同幂等键查询返回 None。"""
        run = _make_run()
        with repo.transaction() as tx:
            tx.insert_run(run)

        existing_id = repo.get_existing_run_id(
            candidate_set_id="cs1",
            strategy_policy_id="p1",
            strategy_policy_version=1,
            data_snapshot_id="snap1",
            ranking_method_version="different_version",
        )
        assert existing_id is None

    def test_idempotency_key_with_none_snapshot(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """data_snapshot_id 为 None 时幂等查询也能正确匹配。"""
        run = _make_run(data_snapshot_id=None, priority_run_id="cpr_none_snap")
        with repo.transaction() as tx:
            tx.insert_run(run)

        existing_id = repo.get_existing_run_id(
            candidate_set_id="cs1",
            strategy_policy_id="p1",
            strategy_policy_version=1,
            data_snapshot_id=None,
            ranking_method_version="fund_priority_v0",
        )
        assert existing_id == "cpr_none_snap"


# ============================================================
# 4. 新 snapshot 生成新 run
# ============================================================
class TestNewSnapshotNewRun:
    def test_different_snapshot_creates_new_run(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """插入两个 run,只有 data_snapshot_id 不同,都能成功。"""
        run1 = _make_run(priority_run_id="cpr_snap1", data_snapshot_id="snap1")
        run2 = _make_run(priority_run_id="cpr_snap2", data_snapshot_id="snap2")

        with repo.transaction() as tx:
            id1 = tx.insert_run(run1)
        with repo.transaction() as tx:
            id2 = tx.insert_run(run2)

        assert id1 == "cpr_snap1"
        assert id2 == "cpr_snap2"
        assert repo.get_run("cpr_snap1") is not None
        assert repo.get_run("cpr_snap2") is not None


# ============================================================
# 5. 旧 run 不变
# ============================================================
class TestOldRunImmutable:
    def test_old_run_unchanged_after_new_run(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """插入新 run 后,查询旧 run 仍返回正确数据。"""
        run1 = _make_run(priority_run_id="cpr_old", data_snapshot_id="snap1")
        with repo.transaction() as tx:
            tx.insert_run(run1)

        # 插入新 run(不同 snapshot)
        run2 = _make_run(
            priority_run_id="cpr_new",
            data_snapshot_id="snap2",
            tier_counts={"research_now": 2, "research_next": 0, "valuation_watch": 0,
                         "data_insufficient": 0, "excluded": 1},
        )
        with repo.transaction() as tx:
            tx.insert_run(run2)

        # 旧 run 数据不变
        old = repo.get_run("cpr_old")
        assert old is not None
        assert old["data_snapshot_id"] == "snap1"
        assert old["tier_counts"] == {
            "research_now": 1,
            "research_next": 1,
            "valuation_watch": 0,
            "data_insufficient": 0,
            "excluded": 1,
        }


# ============================================================
# 6. 按 Thesis 历史倒序
# ============================================================
class TestListByThesisDesc:
    def test_list_runs_by_thesis_desc(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """插入 3 个 run(同一 thesis_id,不同 created_at),list_runs_by_thesis()
        返回按 created_at DESC 排序。"""
        # 手动设置不同的 created_at 值(绕过默认 datetime('now'))
        base_sql = (
            "INSERT INTO candidate_priority_runs "
            "(priority_run_id, candidate_set_id, thesis_id, user_input_id, "
            "strategy_policy_id, strategy_policy_version, data_snapshot_id, "
            "ranking_method_version, result_status, result_type, "
            "scanned_fund_count, mapped_candidate_count, unmapped_due_to_data_count, "
            "evaluated_candidate_count, eligible_candidate_count, tier_counts_json, "
            "created_by, created_at) VALUES "
            "(?, 'cs1', 'th1', 'ri1', 'p1', 1, ?, 'fund_priority_v0', 'completed', "
            "'ranked_candidates', 10, 3, 7, 3, 2, ?, 'researcher_001', ?)"
        )
        cur = conn_with_data.cursor()
        cur.execute(
            base_sql,
            ("cpr_a", "snap1", '{"research_now": 1}', "2026-01-01T00:00:00+00:00"),
        )
        cur.execute(
            base_sql,
            ("cpr_b", "snap2", '{"research_now": 2}', "2026-03-01T00:00:00+00:00"),
        )
        cur.execute(
            base_sql,
            ("cpr_c", None, '{"research_now": 3}', "2026-02-01T00:00:00+00:00"),
        )
        conn_with_data.commit()

        runs = repo.list_runs_by_thesis("th1")
        assert len(runs) == 3
        # 按 created_at DESC: cpr_b(03) > cpr_c(02) > cpr_a(01)
        assert runs[0]["priority_run_id"] == "cpr_b"
        assert runs[1]["priority_run_id"] == "cpr_c"
        assert runs[2]["priority_run_id"] == "cpr_a"
        # 验证 JSON 字段被解析
        assert runs[0]["tier_counts"] == {"research_now": 2}
        assert runs[1]["tier_counts"] == {"research_now": 3}
        assert runs[2]["tier_counts"] == {"research_now": 1}

    def test_list_runs_by_thesis_empty(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """没有 run 时返回空列表。"""
        runs = repo.list_runs_by_thesis("th1")
        assert runs == []


# ============================================================
# 7. JSON 坏数据不静默
# ============================================================
class TestBadJsonRaises:
    def test_bad_tier_counts_json_raises_value_error(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """直接在数据库中插入坏 JSON 到 tier_counts_json,查询 get_run() 时抛 ValueError。"""
        conn_with_data.execute(
            "INSERT INTO candidate_priority_runs "
            "(priority_run_id, candidate_set_id, thesis_id, user_input_id, "
            "strategy_policy_id, strategy_policy_version, data_snapshot_id, "
            "ranking_method_version, result_status, result_type, "
            "scanned_fund_count, mapped_candidate_count, unmapped_due_to_data_count, "
            "evaluated_candidate_count, eligible_candidate_count, tier_counts_json, "
            "created_by) VALUES "
            "('cpr_bad', 'cs1', 'th1', 'ri1', 'p1', 1, 'snap1', 'fund_priority_v0', "
            "'completed', 'ranked_candidates', 10, 3, 7, 3, 2, '{invalid json}', "
            "'researcher_001')"
        )
        conn_with_data.commit()

        with pytest.raises(ValueError, match="JSON 反序列化失败"):
            repo.get_run("cpr_bad")

    def test_bad_results_json_raises_value_error(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """直接在数据库中插入坏 JSON 到 dimension_results_json,查询 get_results() 时抛 ValueError。"""
        with repo.transaction() as tx:
            tx.insert_run(_make_run(priority_run_id="cpr_bad_results"))
        # 直接插入坏 JSON 的 result
        conn_with_data.execute(
            "INSERT INTO candidate_priority_results "
            "(priority_result_id, priority_run_id, candidate_id, fund_code, fund_name, "
            "eligibility_status, priority_tier, priority_rank, matched_holding_weight, "
            "disclosed_holding_weight, normalized_match_pct, fit_score, evidence_score, "
            "holdings_truth_status, valuation_status, data_quality_status, "
            "holding_report_date, dimension_results_json, priority_reasons_json, "
            "exclusion_reasons_json) VALUES "
            "('cprr_bad', 'cpr_bad_results', 'can1', '000001', '基金1', 'eligible', "
            "'research_now', 1, 0.1, 0.3, 0.33, 0.1, 0.75, 'verified', 'fair', "
            "'sufficient', '2025-12-31', '{bad json}', '[]', '[]')"
        )
        conn_with_data.commit()

        with pytest.raises(ValueError, match="JSON 反序列化失败"):
            repo.get_results("cpr_bad_results")


# ============================================================
# 8. 参数化查询可抵御包含引号的 fund code
# ============================================================
class TestSqlParameterized:
    def test_fund_code_with_single_quote(
        self, repo: CandidatePriorityRepository, conn_with_data
    ):
        """插入 fund_code = "000'001" 的 result,查询 get_results() 能正确返回。"""
        run = _make_run(priority_run_id="cpr_quote")
        result = _make_result(
            "cpr_quote", "can1", fund_code="000'001", fund_name="带引号的基金"
        )
        with repo.transaction() as tx:
            tx.insert_run(run)
            tx.insert_results([result])

        stored_results = repo.get_results("cpr_quote")
        assert len(stored_results) == 1
        assert stored_results[0]["fund_code"] == "000'001"
        assert stored_results[0]["fund_name"] == "带引号的基金"
