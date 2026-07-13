"""GovernanceRepository 测试:事务契约、外键、JSON 序列化、原子性。

覆盖:
    1. ResearchInput 写入和读取
    2. policy 不存在时失败
    3. snapshot 不存在时失败
    4. Thesis 必须关联 ResearchInput
    5. CandidateSet 批量写入原子性
    6. JSON 字段可逆序列化
    7. 数据库外键真实生效
    8. 重试不会重复写入
    9. 同一事务失败后全部回滚
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app.persistence.governance import GovernanceRepository
from app.persistence.migrations_runner import run_migrations


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture()
def gov_db(tmp_path: Path) -> Path:
    """从空库跑 migration,预置 1 条 strategy_policy + 1 个 data_snapshot。"""
    db = tmp_path / "gov.sqlite"
    run_migrations(str(db))
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """INSERT INTO strategy_policies
            (policy_id, version, business_mode, policy_status, strategy_name, strategy_type)
           VALUES ('p1', 1, 'private_strategy', 'active', '测试策略', 'equity_long_only')"""
    )
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES ('snap1', '/tmp/x')"
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def repo(gov_db: Path) -> GovernanceRepository:
    return GovernanceRepository(gov_db)


# ============================================================
# 1. ResearchInput 写入和读取
# ============================================================
class TestResearchInput:
    def test_insert_and_read(self, repo: GovernanceRepository):
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="我看好消费白马",
                data_snapshot_id="snap1",
                structured_intent={"style": "value"},
                target_assets=[{"asset_type": "stock", "asset_code": "600519"}],
            )
        assert uid.startswith("ri_")

        # 读回
        ri = repo.get_research_input(uid)
        assert ri is not None
        assert ri["raw_text"] == "我看好消费白马"
        assert ri["input_type"] == "philosophy"
        assert ri["business_mode"] == "private_strategy"
        assert ri["strategy_policy_id"] == "p1"
        assert ri["strategy_policy_version"] == 1
        assert ri["status"] == "received"

    def test_json_fields_round_trip(self, repo: GovernanceRepository):
        """JSON 字段写入后读回应一致。"""
        intent = {"style": "value", "risk": {"drawdown": 0.15}}
        assets = [{"type": "stock", "code": "600519"}]
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
                structured_intent=intent,
                target_assets=assets,
            )
        ri = repo.get_research_input(uid)
        assert ri is not None
        assert ri["structured_intent"] == intent
        assert ri["target_assets"] == assets

    def test_none_json_fields_stay_none(self, repo: GovernanceRepository):
        """structured_intent=None 时,读回也是 None。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="target",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
        ri = repo.get_research_input(uid)
        assert ri is not None
        assert ri["structured_intent"] is None
        assert ri["target_assets"] is None


# ============================================================
# 2. policy 不存在时失败
# ============================================================
class TestForeignKeyPolicy:
    def test_policy_not_exists_fails(self, repo: GovernanceRepository):
        """引用不存在的 (policy_id, version) 应失败。"""
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with repo.transaction() as tx:
                tx.insert_research_input(
                    input_type="philosophy",
                    business_mode="private_strategy",
                    strategy_policy_id="ghost",
                    strategy_policy_version=1,
                    actor_role="researcher",
                    request_source="ad_hoc_research",
                    raw_text="test",
                    data_snapshot_id="snap1",
                )

    def test_snapshot_not_exists_fails(self, repo: GovernanceRepository):
        """引用不存在的 data_snapshot_id 应失败。"""
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with repo.transaction() as tx:
                tx.insert_research_input(
                    input_type="philosophy",
                    business_mode="private_strategy",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    actor_role="researcher",
                    request_source="ad_hoc_research",
                    raw_text="test",
                    data_snapshot_id="ghost_snap",
                )

    def test_thesis_requires_existing_research_input(self, repo: GovernanceRepository):
        """thesis 的 user_input_id 必须已存在。"""
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with repo.transaction() as tx:
                tx.insert_thesis(
                    user_input_id="ghost_ri",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    title="t",
                    belief_statement="b",
                )


# ============================================================
# 3. Thesis 必须关联 ResearchInput
# ============================================================
class TestThesis:
    def test_thesis_with_valid_input(self, repo: GovernanceRepository):
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="消费白马",
                belief_statement="消费白马是核心",
                supporting_evidence=["ev1", "ev2"],
                catalysts=["财报超预期"],
            )
        assert tid.startswith("th_")
        th = repo.get_thesis(tid)
        assert th is not None
        assert th["belief_statement"] == "消费白马是核心"
        assert th["supporting_evidence"] == ["ev1", "ev2"]
        assert th["catalysts"] == ["财报超预期"]

    def test_thesis_json_round_trip(self, repo: GovernanceRepository):
        """thesis 的所有 JSON 字段都能可逆序列化。"""
        evidence = ["ev1", {"type": "metric", "value": 0.15}]
        metrics = {"pe": 20.5, "peg": 1.2}
        valuation = {"max_pe": 60}
        invalidation = ["drawdown > 20%"]
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="t",
                belief_statement="b",
                supporting_evidence=evidence,
                opposing_evidence=["rev1"],
                key_metrics=metrics,
                candidate_assets=["600519"],
                valuation_view=valuation,
                catalysts=["c1"],
                invalidation_conditions=invalidation,
            )
        th = repo.get_thesis(tid)
        assert th is not None
        assert th["supporting_evidence"] == evidence
        assert th["opposing_evidence"] == ["rev1"]
        assert th["key_metrics"] == metrics
        assert th["candidate_assets"] == ["600519"]
        assert th["valuation_view"] == valuation
        assert th["invalidation_conditions"] == invalidation


# ============================================================
# 4. CandidateSet 批量写入原子性
# ============================================================
class TestCandidateSet:
    def _setup_thesis(self, repo: GovernanceRepository) -> tuple[str, str]:
        """预置一条 ResearchInput + Thesis,返回 (uid, tid)。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="t",
                belief_statement="b",
            )
        return uid, tid

    def test_batch_insert_and_read(self, repo: GovernanceRepository):
        uid, tid = self._setup_thesis(repo)
        candidates = [
            {
                "thesis_id": tid,
                "user_input_id": uid,
                "asset_type": "fund",
                "asset_code": "000001",
                "asset_name": "基金A",
                "fit_score": 0.8,
                "evidence_score": 0.7,
                "data_snapshot_id": "snap1",
                "conflict_reasons": ["与 B 重叠"],
                "exclusion_reasons": [],
            },
            {
                "thesis_id": tid,
                "user_input_id": uid,
                "asset_type": "fund",
                "asset_code": "000002",
                "asset_name": "基金B",
                "fit_score": 0.6,
                "exclusion_reasons": ["规模过小"],
            },
        ]
        with repo.transaction() as tx:
            result = tx.insert_candidates(candidates)
        assert len(result["candidate_ids"]) == 2

        # 按 thesis 查
        result = repo.get_candidates_by_thesis(tid)
        assert len(result) == 2
        assert result[0]["asset_code"] == "000001"
        assert result[0]["fit_score"] == 0.8
        assert result[0]["conflict_reasons"] == ["与 B 重叠"]
        assert result[1]["exclusion_reasons"] == ["规模过小"]

        # 按 set 查(同一 candidate_set_id)
        cs_id = result[0]["candidate_set_id"]
        assert result[1]["candidate_set_id"] == cs_id
        by_set = repo.get_candidates_by_set(cs_id)
        assert len(by_set) == 2

    def test_batch_atomicity_all_or_nothing(self, repo: GovernanceRepository):
        """批量写入中第 3 个候选违反唯一约束 -> 前两个也回滚。"""
        uid, tid = self._setup_thesis(repo)
        candidates = [
            {
                "thesis_id": tid,
                "user_input_id": uid,
                "asset_type": "fund",
                "asset_code": "000001",
                "asset_name": "A",
            },
            {
                "thesis_id": tid,
                "user_input_id": uid,
                "asset_type": "fund",
                "asset_code": "000002",
                "asset_name": "B",
            },
            {
                "thesis_id": tid,
                "user_input_id": uid,
                "asset_type": "fund",
                "asset_code": "000001",  # 重复,违反 UNIQUE(thesis_id, asset_code)
                "asset_name": "dup",
            },
        ]
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with repo.transaction() as tx:
                tx.insert_candidates(candidates)

        # 验证前两个也没有落库
        result = repo.get_candidates_by_thesis(tid)
        assert len(result) == 0, f"expected 0, got {len(result)}"


# ============================================================
# 5. 同一事务失败后全部回滚
# ============================================================
class TestTransactionRollback:
    def test_rollback_on_exception(self, repo: GovernanceRepository):
        """事务中 ResearchInput 成功,但 Thesis 失败 -> ResearchInput 也回滚。"""
        with pytest.raises(sqlite3.IntegrityError):
            with repo.transaction() as tx:
                uid = tx.insert_research_input(
                    input_type="philosophy",
                    business_mode="private_strategy",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    actor_role="researcher",
                    request_source="ad_hoc_research",
                    raw_text="test",
                    data_snapshot_id="snap1",
                )
                # thesis 引用不存在的 user_input_id -> FK 失败
                tx.insert_thesis(
                    user_input_id="ghost",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    title="t",
                    belief_statement="b",
                )

        # 验证 ResearchInput 也没落库
        ri = repo.get_research_input(uid)
        assert ri is None, "ResearchInput should have been rolled back"

    def test_audit_log_same_transaction(self, repo: GovernanceRepository):
        """审计日志与业务数据在同一事务中,一起 commit。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tx.insert_audit_log(
                action="create_research_input",
                target_type="research_input",
                target_id=uid,
                payload={"raw_text": "test"},
            )
        # 两者都在
        ri = repo.get_research_input(uid)
        assert ri is not None
        # 审计也在(直接查表)
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT * FROM audit_log WHERE target_id = ?", (uid,)
            ).fetchone()
        assert row is not None
        assert row["action"] == "create_research_input"

    def test_audit_log_rollback_with_business(self, repo: GovernanceRepository):
        """审计日志与业务数据在同一事务中,一起 rollback。"""
        with pytest.raises(sqlite3.IntegrityError):
            with repo.transaction() as tx:
                uid = tx.insert_research_input(
                    input_type="philosophy",
                    business_mode="private_strategy",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    actor_role="researcher",
                    request_source="ad_hoc_research",
                    raw_text="test",
                    data_snapshot_id="snap1",
                )
                tx.insert_audit_log(
                    action="create_research_input",
                    target_type="research_input",
                    target_id=uid,
                )
                # 触发失败:thesis 引用不存在的 user_input_id
                tx.insert_thesis(
                    user_input_id="ghost",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    title="t",
                    belief_statement="b",
                )
        # 两者都没落库
        ri = repo.get_research_input(uid)
        assert ri is None
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT * FROM audit_log WHERE target_id = ?", (uid,)
            ).fetchone()
        assert row is None


# ============================================================
# 6. 重试不会重复写入
# ============================================================
class TestIdempotency:
    def test_same_id_reinsert_fails(self, repo: GovernanceRepository):
        """显式指定 user_input_id 后,第二次插入相同 ID 应失败。"""
        with repo.transaction() as tx:
            tx.insert_research_input(
                user_input_id="ri_fixed",
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="first",
                data_snapshot_id="snap1",
            )
        # 第二次用相同 ID -> UNIQUE constraint 冲突
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            with repo.transaction() as tx:
                tx.insert_research_input(
                    user_input_id="ri_fixed",
                    input_type="philosophy",
                    business_mode="private_strategy",
                    strategy_policy_id="p1",
                    strategy_policy_version=1,
                    actor_role="researcher",
                    request_source="ad_hoc_research",
                    raw_text="second",
                    data_snapshot_id="snap1",
                )

    def test_candidate_unique_per_set(self, repo: GovernanceRepository):
        """同一 candidate_set_id 下重复 asset_code 应失败。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="t",
                belief_statement="b",
            )
            result = tx.insert_candidates([
                {
                    "thesis_id": tid,
                    "user_input_id": uid,
                    "asset_type": "fund",
                    "asset_code": "000001",
                    "asset_name": "A",
                },
            ])
        cs_id = result["candidate_set_id"]
        # 同一 candidate_set_id + 同 asset_code -> UNIQUE 冲突
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with repo.transaction() as tx:
                tx.insert_candidates([
                    {
                        "thesis_id": tid,
                        "user_input_id": uid,
                        "candidate_set_id": cs_id,
                        "asset_type": "fund",
                        "asset_code": "000001",
                        "asset_name": "dup",
                    },
                ])


# ============================================================
# 7. 存在性检查
# ============================================================
class TestExistenceChecks:
    def test_policy_exists(self, repo: GovernanceRepository):
        assert repo.policy_exists("p1", 1) is True
        assert repo.policy_exists("p1", 2) is False
        assert repo.policy_exists("ghost", 1) is False

    def test_snapshot_exists(self, repo: GovernanceRepository):
        assert repo.snapshot_exists("snap1") is True
        assert repo.snapshot_exists("ghost") is False

    def test_policy_exists_in_transaction(self, repo: GovernanceRepository):
        with repo.transaction() as tx:
            assert tx.policy_exists("p1", 1) is True
            assert tx.policy_exists("ghost", 1) is False

    def test_snapshot_exists_in_transaction(self, repo: GovernanceRepository):
        with repo.transaction() as tx:
            assert tx.snapshot_exists("snap1") is True
            assert tx.snapshot_exists("ghost") is False


# ============================================================
# 8. 完整链路:ResearchInput -> Thesis -> Candidates -> Audit
# ============================================================
class TestFullChain:
    def test_full_chain_in_one_transaction(self, repo: GovernanceRepository):
        """在一个事务中写入完整链路,全部成功。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="我看好消费白马",
                data_snapshot_id="snap1",
                structured_intent={"style": "value"},
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="消费白马配置",
                belief_statement="消费白马是核心",
                as_of_date="2026-03-31",
                data_snapshot_id="snap1",
            )
            ids = tx.insert_candidates([
                {
                    "thesis_id": tid,
                    "user_input_id": uid,
                    "asset_type": "fund",
                    "asset_code": "000001",
                    "asset_name": "样例消费股票",
                    "fit_score": 0.85,
                    "data_snapshot_id": "snap1",
                    "exclusion_reasons": [],
                },
                {
                    "thesis_id": tid,
                    "user_input_id": uid,
                    "asset_type": "fund",
                    "asset_code": "000002",
                    "asset_name": "数据不足基金",
                    "fit_score": 0.3,
                    "data_quality_status": "insufficient",
                    "exclusion_reasons": ["数据不足"],
                },
            ])
            tx.insert_audit_log(
                action="create_research_chain",
                target_type="thesis",
                target_id=tid,
                payload={"candidate_count": len(ids)},
            )

        # 验证全部落库
        ri = repo.get_research_input(uid)
        assert ri is not None
        assert ri["structured_intent"] == {"style": "value"}

        th = repo.get_thesis(tid)
        assert th is not None
        assert th["belief_statement"] == "消费白马是核心"

        candidates = repo.get_candidates_by_thesis(tid)
        assert len(candidates) == 2
        assert candidates[0]["fit_score"] == 0.85
        assert candidates[1]["exclusion_reasons"] == ["数据不足"]

        # 候选可反查 input / policy / snapshot(数据库真实反查)
        for c in candidates:
            assert c["thesis_id"] == tid
            assert c["user_input_id"] == uid
            # 通过 thesis -> research_input -> policy 反查
            assert th["user_input_id"] == uid
            assert ri["strategy_policy_id"] == "p1"
            assert ri["data_snapshot_id"] == "snap1"


# ============================================================
# 9. CandidateSet 集合头(CandidateSetHeader)
# ============================================================
class TestCandidateSetHeader:
    def _setup_thesis(self, repo: GovernanceRepository) -> tuple[str, str]:
        """预置一条 ResearchInput + Thesis,返回 (uid, tid)。"""
        with repo.transaction() as tx:
            uid = tx.insert_research_input(
                input_type="philosophy",
                business_mode="private_strategy",
                strategy_policy_id="p1",
                strategy_policy_version=1,
                actor_role="researcher",
                request_source="ad_hoc_research",
                raw_text="test",
                data_snapshot_id="snap1",
            )
            tid = tx.insert_thesis(
                user_input_id=uid,
                strategy_policy_id="p1",
                strategy_policy_version=1,
                title="t",
                belief_statement="b",
            )
        return uid, tid

    def test_header_and_candidates_same_transaction(self, repo: GovernanceRepository):
        """在同一个 transaction 中先写 header 再写 candidates,成功提交。"""
        uid, tid = self._setup_thesis(repo)
        cs_id = "cs_explicit_001"
        with repo.transaction() as tx:
            tx.insert_candidate_set_header(
                candidate_set_id=cs_id,
                thesis_id=tid,
                user_input_id=uid,
                data_snapshot_id="snap1",
                source_method_version="test_v1",
                scanned_fund_count=2,
                mapped_candidate_count=2,
                unmapped_due_to_data_count=0,
                created_by="test_user",
            )
            tx.insert_candidates([
                {
                    "candidate_set_id": cs_id,
                    "thesis_id": tid,
                    "user_input_id": uid,
                    "asset_type": "fund",
                    "asset_code": "000001",
                    "asset_name": "A",
                    "data_snapshot_id": "snap1",
                    "candidate_evidence": {"holdings_match": 0.85},
                },
                {
                    "candidate_set_id": cs_id,
                    "thesis_id": tid,
                    "user_input_id": uid,
                    "asset_type": "fund",
                    "asset_code": "000002",
                    "asset_name": "B",
                    "data_snapshot_id": "snap1",
                },
            ])

        # 验证 header 存在
        header = repo.get_candidate_set_header(cs_id)
        assert header is not None
        assert header["thesis_id"] == tid
        assert header["source_method_version"] == "test_v1"
        assert header["scanned_fund_count"] == 2
        assert header["created_by"] == "test_user"

        # 验证 candidates 存在,且 candidate_evidence 被正确写入
        candidates = repo.get_candidates_by_set(cs_id)
        assert len(candidates) == 2
        assert candidates[0]["candidate_evidence"] == {"holdings_match": 0.85}
        assert candidates[1]["candidate_evidence"] is None

    def test_rollback_header_candidates_audit_on_failure(
        self, repo: GovernanceRepository
    ):
        """任一候选失败时 header、候选、audit 全回滚。"""
        uid, tid = self._setup_thesis(repo)
        cs_id = "cs_rollback_001"
        with pytest.raises(KeyError):
            with repo.transaction() as tx:
                tx.insert_candidate_set_header(
                    candidate_set_id=cs_id,
                    thesis_id=tid,
                    user_input_id=uid,
                    data_snapshot_id="snap1",
                    source_method_version="test_v1",
                    scanned_fund_count=1,
                    mapped_candidate_count=1,
                    unmapped_due_to_data_count=0,
                    created_by="test_user",
                )
                tx.insert_audit_log(
                    action="create_candidates",
                    target_type="candidate_set",
                    target_id=cs_id,
                )
                tx.insert_candidates([
                    {
                        "candidate_set_id": cs_id,
                        "thesis_id": tid,
                        "user_input_id": uid,
                        "asset_type": "fund",
                        # 缺少 asset_code -> KeyError,整个事务回滚
                    },
                ])

        # 验证 header 不存在
        header = repo.get_candidate_set_header(cs_id)
        assert header is None

        # 验证 audit 不存在
        with repo._connect() as conn:  # noqa: SLF001
            row = conn.execute(
                "SELECT * FROM audit_log WHERE target_id = ?", (cs_id,)
            ).fetchone()
        assert row is None

        # 验证 candidates 不存在
        candidates = repo.get_candidates_by_set(cs_id)
        assert len(candidates) == 0

    def test_get_candidate_set_header_returns_dict(self, repo: GovernanceRepository):
        """插入 header 后能查回。"""
        uid, tid = self._setup_thesis(repo)
        cs_id = "cs_get_001"
        with repo.transaction() as tx:
            tx.insert_candidate_set_header(
                candidate_set_id=cs_id,
                thesis_id=tid,
                user_input_id=uid,
                data_snapshot_id="snap1",
                source_method_version="test_v1",
                scanned_fund_count=10,
                mapped_candidate_count=8,
                unmapped_due_to_data_count=2,
                created_by="researcher_001",
            )

        # 无事务查询
        header = repo.get_candidate_set_header(cs_id)
        assert header is not None
        assert header["candidate_set_id"] == cs_id
        assert header["thesis_id"] == tid
        assert header["user_input_id"] == uid
        assert header["data_snapshot_id"] == "snap1"
        assert header["source_method_version"] == "test_v1"
        assert header["scanned_fund_count"] == 10
        assert header["mapped_candidate_count"] == 8
        assert header["unmapped_due_to_data_count"] == 2
        assert header["created_by"] == "researcher_001"

        # 事务内查询
        with repo.transaction() as tx:
            header_tx = tx.get_candidate_set_header(cs_id)
            assert header_tx is not None
            assert header_tx["candidate_set_id"] == cs_id

        # 不存在的 header
        assert repo.get_candidate_set_header("ghost") is None


# ============================================================
# 10. 策略政策 / 数据快照查询(JSON 解析)
# ============================================================
class TestStrategyPolicyAndSnapshot:
    def test_get_strategy_policy_parses_json(
        self, repo: GovernanceRepository, gov_db: Path
    ):
        """插入策略(含 candidate_priority_json)后能查回,JSON 字段被正确解析。"""
        conn = sqlite3.connect(str(gov_db))
        conn.execute(
            """INSERT INTO strategy_policies
               (policy_id, version, business_mode, policy_status, strategy_name, strategy_type,
                market_scope_json, position_limit_json, allowed_universe_json,
                excluded_universe_json, valuation_policy_json, monitoring_policy_json,
                investment_policy_json, candidate_priority_json)
               VALUES ('p2', 1, 'private_strategy', 'active', 'JSON测试策略', 'equity_long_only',
                '["A股"]', '{"max_single": 0.1}', '["stock"]', '["ST"]',
                '{"max_pe": 60}', '{"drawdown_alert": 0.15}', '{"preferred_styles": ["value"]}',
                '{"ranking_method": "weighted_sum"}')"""
        )
        conn.commit()
        conn.close()

        # 无事务查询
        policy = repo.get_strategy_policy("p2", 1)
        assert policy is not None
        assert policy["policy_id"] == "p2"
        assert policy["market_scope"] == ["A股"]
        assert policy["position_limit"] == {"max_single": 0.1}
        assert policy["allowed_universe"] == ["stock"]
        assert policy["excluded_universe"] == ["ST"]
        assert policy["valuation_policy"] == {"max_pe": 60}
        assert policy["monitoring_policy"] == {"drawdown_alert": 0.15}
        assert policy["investment_policy"] == {"preferred_styles": ["value"]}
        assert policy["candidate_priority"] == {"ranking_method": "weighted_sum"}

        # 事务内查询
        with repo.transaction() as tx:
            policy_tx = tx.get_strategy_policy("p2", 1)
            assert policy_tx is not None
            assert policy_tx["candidate_priority"] == {"ranking_method": "weighted_sum"}

        # 不存在的策略
        assert repo.get_strategy_policy("ghost", 1) is None

    def test_get_data_snapshot_returns_dict(self, repo: GovernanceRepository):
        """插入快照后能查回。"""
        # snap1 由 fixture 预置
        snapshot = repo.get_data_snapshot("snap1")
        assert snapshot is not None
        assert snapshot["snapshot_id"] == "snap1"
        assert snapshot["source_db_path"] == "/tmp/x"

        # 事务内查询
        with repo.transaction() as tx:
            snapshot_tx = tx.get_data_snapshot("snap1")
            assert snapshot_tx is not None
            assert snapshot_tx["snapshot_id"] == "snap1"

        # 不存在的快照
        assert repo.get_data_snapshot("ghost") is None

    def test_bad_json_raises_value_error(
        self, repo: GovernanceRepository, gov_db: Path
    ):
        """坏 JSON 抛 ValueError,不静默返回 None。"""
        conn = sqlite3.connect(str(gov_db))
        conn.execute(
            """INSERT INTO strategy_policies
               (policy_id, version, business_mode, policy_status, strategy_name, strategy_type,
                candidate_priority_json)
               VALUES ('p3', 1, 'private_strategy', 'active', '坏JSON策略', 'equity_long_only',
                '{invalid json}')"""
        )
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="JSON 反序列化失败"):
            repo.get_strategy_policy("p3", 1)
