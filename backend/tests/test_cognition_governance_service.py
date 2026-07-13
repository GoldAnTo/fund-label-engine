"""CognitionGovernanceService 测试: CandidateSet 创建 + PriorityRun 编排。

覆盖:
    Task 7:
        1. 缺 direction/conviction/time_horizon/risk_tolerance 抛 StructuredIntentIncompleteError
        2. belief_link 可空
        3. 服务使用 snapshot 行中的 source/factor 路径
        4. snapshot 路径不存在抛 CandidateDataSourceUnavailableError
        5. 自动 CandidateSet 只包含基金
        6. 通过、估值观察、数据不足和明确点名但无持仓的基金都纳入
        7. 全市场无映射且未点名的基金只进入计数
        8. 相同 Thesis/snapshot/source method 重试返回冲突及已有 candidate_set_id
        9. 服务不更新 research_inputs.structured_intent_json

    Task 8:
        1. 策略/快照/Thesis/CandidateSet 不存在
        2. 集合属于其他 Thesis
        3. 集合快照与请求不一致
        4. candidate evidence 缺失
        5. 策略 method version 不一致
        6. 重复幂等冲突携带已有 ID
        7. 所有候选排除时 result_type=no_eligible_candidate 且业务成功
        8. 计算异常只写失败 audit，不写 run
        9. 结果写入异常整套回滚
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.cognition.engine import FundCandidateEvidenceBatch
from app.persistence.candidate_priority import CandidatePriorityRepository
from app.persistence.governance import GovernanceRepository
from app.persistence.migrations_runner import run_migrations
from app.services.candidate_priority import FundCandidateEvidence
from app.services.cognition_governance_service import (
    CandidateDataSourceUnavailableError,
    CandidateSetNotFoundError,
    CognitionGovernanceService,
    DuplicateCandidateSetError,
    DuplicatePriorityRunError,
    GovernanceError,
    SnapshotNotFoundError,
    StructuredIntentIncompleteError,
    ThesisNotFoundError,
)


# ============================================================
# 测试辅助
# ============================================================
def _make_evidence(
    fund_code: str = "001001",
    fund_name: str | None = "测试基金",
    matched_holding_weight: float = 0.10,
    disclosed_holding_weight: float = 0.30,
    normalized_match_pct: float | None = None,
    holding_report_date: str | None = "2025-12-31",
    holding_age_days: int | None = 30,
    factor_coverage_weight: float = 0.80,
    valuation: dict | None = None,
    holding_trend: dict | None = None,
    manager_identity: dict | None = None,
    evidence_types: dict | None = None,
    policy_conflicts: tuple = (),
    data_snapshot_id: str = "snap1",
    asset_type: str = "fund",
) -> FundCandidateEvidence:
    """构造一个 FundCandidateEvidence。"""
    return FundCandidateEvidence(
        fund_code=fund_code,
        fund_name=fund_name,
        matched_holding_weight=matched_holding_weight,
        disclosed_holding_weight=disclosed_holding_weight,
        normalized_match_pct=(
            normalized_match_pct
            if normalized_match_pct is not None
            else (matched_holding_weight / disclosed_holding_weight if disclosed_holding_weight > 0 else 0.0)
        ),
        holding_report_date=holding_report_date,
        holding_age_days=holding_age_days,
        factor_coverage_weight=factor_coverage_weight,
        valuation=valuation or {"weighted_pe": 30, "weighted_pb": 3},
        holding_trend=holding_trend or {"trend": "stable"},
        manager_identity=manager_identity or {"name": "张三"},
        evidence_types=evidence_types
        or {
            "business_logic": [{"source": "chain_graph", "ref": "c1"}],
            "earnings_or_cashflow": [{"source": "fund_report", "ref": "r1"}],
            "valuation": [{"source": "valuation_gate", "ref": "v1"}],
            "catalyst_or_expectation_gap": [{"source": "expectation_gap", "ref": "e1"}],
        },
        policy_conflicts=policy_conflicts,
        data_snapshot_id=data_snapshot_id,
        asset_type=asset_type,
    )


def _make_batch(
    all_candidates: list[FundCandidateEvidence] | None = None,
    scanned_fund_count: int = 10,
    mapped_candidate_count: int | None = None,
    unmapped_due_to_data_count: int = 0,
) -> FundCandidateEvidenceBatch:
    """构造一个 FundCandidateEvidenceBatch。"""
    if all_candidates is None:
        all_candidates = [_make_evidence()]
    return FundCandidateEvidenceBatch(
        all_candidates=tuple(all_candidates),
        valuation_gated_candidates=(),
        scanned_fund_count=scanned_fund_count,
        mapped_candidate_count=(
            mapped_candidate_count if mapped_candidate_count is not None else len(all_candidates)
        ),
        unmapped_due_to_data_count=unmapped_due_to_data_count,
    )


def _make_mock_engine(batch: FundCandidateEvidenceBatch) -> Mock:
    """构造一个 mock CognitionEngine。"""
    engine = Mock()
    engine.build_fund_candidate_evidence.return_value = batch
    engine.close = Mock()
    return engine


def _make_engine_factory(batch: FundCandidateEvidenceBatch):
    """构造一个 mock engine_factory。"""
    def factory(source_db: str, factor_db: str | None):
        return _make_mock_engine(batch)
    return factory


# 完整的 candidate_priority 配置 JSON（不含 valuation_policy / allowed_asset_types /
# excluded_asset_codes / approved_for_production，这些从 policy_row 顶层读取）
_CANDIDATE_PRIORITY_CONFIG = {
    "method_version": "fund_priority_v0",
    "source_method_version": "fund_candidate_evidence_v0",
    "asset_type": "fund",
    "minimum_target_holding_weight": 0.03,
    "minimum_disclosed_holding_weight": 0.10,
    "minimum_factor_coverage_weight": 0.50,
    "maximum_holding_age_days": 180,
    "valuation_breach_mode": "watch",
    "require_manager_identity": True,
    "require_holding_report_date": True,
    "required_evidence": [
        "business_logic",
        "earnings_or_cashflow",
        "valuation",
        "catalyst_or_expectation_gap",
    ],
}

# 估值策略（写入 valuation_policy_json 列，从顶层读取）
_VALUATION_POLICY_CONFIG = {
    "max_pe": 60,
    "max_pb": 10,
    "max_peg": 2.0,
    "max_valuation_percentile": 85,
}

# 允许的投资标的范围（写入 allowed_universe_json 列）
_ALLOWED_UNIVERSE_CONFIG = {
    "asset_types": ["fund"],
}

# 排除的投资标的范围（写入 excluded_universe_json 列）
_EXCLUDED_UNIVERSE_CONFIG = [
    {"reason": "test", "assets": []},
]


def _intent(
    direction: str = "AI",
    conviction: str = "medium",
    time_horizon: str = "long",
    risk_tolerance: str = "moderate",
    belief_link: str | None = "光模块",
) -> dict:
    """构造 structured_intent。"""
    d = {
        "direction": direction,
        "conviction": conviction,
        "time_horizon": time_horizon,
        "risk_tolerance": risk_tolerance,
    }
    if belief_link is not None:
        d["belief_link"] = belief_link
    return d


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    """创建一个真实文件，作为 source_db_path。"""
    f = tmp_path / "source.sqlite"
    f.write_text("")
    return f


@pytest.fixture()
def factor_file(tmp_path: Path) -> Path:
    """创建一个真实文件，作为 factor_db_path。"""
    f = tmp_path / "factor.sqlite"
    f.write_text("")
    return f


@pytest.fixture()
def gov_db(tmp_path: Path, source_file: Path, factor_file: Path) -> Path:
    """创建 migrated 治理数据库 + 基础数据。"""
    db = tmp_path / "gov.sqlite"
    run_migrations(str(db))
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")

    # 插入 strategy_policies (带 candidate_priority_json, valuation_policy_json, allowed_universe_json, excluded_universe_json)
    conn.execute(
        "INSERT INTO strategy_policies "
        "(policy_id, version, business_mode, policy_status, approved_for_production, "
        "strategy_name, strategy_type, "
        "candidate_priority_json, valuation_policy_json, "
        "allowed_universe_json, excluded_universe_json) "
        "VALUES ('p1', 1, 'private_strategy', 'active', 0, '测试策略', 'equity_long_only', ?, ?, ?, ?)",
        (
            json.dumps(_CANDIDATE_PRIORITY_CONFIG, ensure_ascii=False),
            json.dumps(_VALUATION_POLICY_CONFIG, ensure_ascii=False),
            json.dumps(_ALLOWED_UNIVERSE_CONFIG, ensure_ascii=False),
            json.dumps(_EXCLUDED_UNIVERSE_CONFIG, ensure_ascii=False),
        ),
    )

    # 插入 data_snapshots
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path, factor_db_path) "
        "VALUES ('snap1', ?, ?)",
        (str(source_file), str(factor_file)),
    )
    # snap2 指向不存在的文件
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path) "
        "VALUES ('snap2', '/tmp/nonexistent_path.sqlite')"
    )

    # 插入 research_inputs (带 structured_intent_json)
    conn.execute(
        "INSERT INTO research_inputs "
        "(user_input_id, input_type, business_mode, strategy_policy_id, "
        "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
        "structured_intent_json, as_of_date, data_snapshot_id, status) "
        "VALUES ('ri1', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
        "'researcher_001', 'ad_hoc_research', '我看好AI', ?, '2025-12-31', 'snap1', 'received')",
        (json.dumps(_intent(), ensure_ascii=False),),
    )
    # ri2 缺少 direction
    bad_intent = _intent()
    del bad_intent["direction"]
    conn.execute(
        "INSERT INTO research_inputs "
        "(user_input_id, input_type, business_mode, strategy_policy_id, "
        "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
        "structured_intent_json, as_of_date, data_snapshot_id, status) "
        "VALUES ('ri2', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
        "'researcher_001', 'ad_hoc_research', 'test', ?, '2025-12-31', 'snap1', 'received')",
        (json.dumps(bad_intent, ensure_ascii=False),),
    )
    # ri3 没有 belief_link
    conn.execute(
        "INSERT INTO research_inputs "
        "(user_input_id, input_type, business_mode, strategy_policy_id, "
        "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
        "structured_intent_json, as_of_date, data_snapshot_id, status) "
        "VALUES ('ri3', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
        "'researcher_001', 'ad_hoc_research', 'test', ?, '2025-12-31', 'snap1', 'received')",
        (json.dumps(_intent(belief_link=None), ensure_ascii=False),),
    )

    # 插入 investment_theses
    conn.execute(
        "INSERT INTO investment_theses "
        "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
        "title, belief_statement, owner, as_of_date, data_snapshot_id, status) "
        "VALUES ('th1', 'ri1', 'p1', 1, 'AI配置', 'AI是核心', 'researcher_001', "
        "'2025-12-31', 'snap1', 'draft')"
    )
    conn.execute(
        "INSERT INTO investment_theses "
        "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
        "title, belief_statement, owner, as_of_date, data_snapshot_id, status) "
        "VALUES ('th2', 'ri2', 'p1', 1, 'bad', 'bad', 'researcher_001', "
        "'2025-12-31', 'snap1', 'draft')"
    )
    conn.execute(
        "INSERT INTO investment_theses "
        "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
        "title, belief_statement, owner, as_of_date, data_snapshot_id, status) "
        "VALUES ('th3', 'ri3', 'p1', 1, 'no_belief_link', 'test', 'researcher_001', "
        "'2025-12-31', 'snap1', 'draft')"
    )

    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def governance_repo(gov_db: Path) -> GovernanceRepository:
    return GovernanceRepository(gov_db)


@pytest.fixture()
def priority_repo(gov_db: Path) -> CandidatePriorityRepository:
    return CandidatePriorityRepository(gov_db)


@pytest.fixture()
def service(
    governance_repo: GovernanceRepository,
    priority_repo: CandidatePriorityRepository,
) -> CognitionGovernanceService:
    """使用 mock engine_factory 的 service。"""
    batch = _make_batch()
    return CognitionGovernanceService(
        governance_repo,
        priority_repo,
        engine_factory=_make_engine_factory(batch),
    )


def _insert_candidate_set(
    db_path: Path,
    *,
    candidate_set_id: str = "cs_existing",
    thesis_id: str = "th1",
    user_input_id: str = "ri1",
    data_snapshot_id: str = "snap1",
    source_method_version: str = "fund_candidate_evidence_v0",
    candidates: list[dict] | None = None,
) -> None:
    """直接往数据库插入 candidate_set_header + candidate_sets。"""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO candidate_set_headers "
        "(candidate_set_id, thesis_id, user_input_id, data_snapshot_id, "
        "source_method_version, scanned_fund_count, mapped_candidate_count, "
        "unmapped_due_to_data_count, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
         source_method_version, 10, 3, 7, "system"),
    )
    if candidates is None:
        candidates = [_make_evidence()]
    for i, ev in enumerate(candidates, start=1):
        cid = f"can{i}"
        from app.services.cognition_governance_service import _evidence_to_dict
        conn.execute(
            "INSERT INTO candidate_sets "
            "(candidate_id, candidate_set_id, thesis_id, user_input_id, "
            "asset_type, asset_code, asset_name, fit_score, data_snapshot_id, "
            "candidate_evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, candidate_set_id, thesis_id, user_input_id,
             ev.asset_type, ev.fund_code, ev.fund_name,
             ev.matched_holding_weight, data_snapshot_id,
             json.dumps(_evidence_to_dict(ev), ensure_ascii=False)),
        )
    conn.commit()
    conn.close()


# ============================================================
# Task 7: CandidateSet 创建
# ============================================================
class TestCreateCandidateSet:
    """CandidateSet 创建测试。"""

    def test_missing_direction_raises(self, gov_db, governance_repo, priority_repo):
        """缺少 direction 抛 StructuredIntentIncompleteError。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(StructuredIntentIncompleteError):
            svc.create_candidate_set(
                thesis_id="th2",
                data_snapshot_id="snap1",
                actor_id="researcher_001",
            )

    def test_missing_conviction_raises(self, gov_db, governance_repo, priority_repo):
        """缺少 conviction 抛 StructuredIntentIncompleteError。"""
        conn = sqlite3.connect(str(gov_db))
        bad_intent = _intent()
        del bad_intent["conviction"]
        conn.execute(
            "INSERT INTO research_inputs "
            "(user_input_id, input_type, business_mode, strategy_policy_id, "
            "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
            "structured_intent_json, as_of_date, data_snapshot_id, status) "
            "VALUES ('ri_no_conv', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
            "'r', 'ad_hoc_research', 't', ?, '2025-12-31', 'snap1', 'received')",
            (json.dumps(bad_intent, ensure_ascii=False),),
        )
        conn.execute(
            "INSERT INTO investment_theses "
            "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
            "title, belief_statement, owner, status) "
            "VALUES ('th_no_conv', 'ri_no_conv', 'p1', 1, 't', 't', 'r', 'draft')"
        )
        conn.commit()
        conn.close()

        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(StructuredIntentIncompleteError):
            svc.create_candidate_set(
                thesis_id="th_no_conv",
                data_snapshot_id="snap1",
                actor_id="r",
            )

    def test_missing_time_horizon_raises(self, gov_db, governance_repo, priority_repo):
        """缺少 time_horizon 抛 StructuredIntentIncompleteError。"""
        conn = sqlite3.connect(str(gov_db))
        bad_intent = _intent()
        del bad_intent["time_horizon"]
        conn.execute(
            "INSERT INTO research_inputs "
            "(user_input_id, input_type, business_mode, strategy_policy_id, "
            "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
            "structured_intent_json, as_of_date, data_snapshot_id, status) "
            "VALUES ('ri_no_th', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
            "'r', 'ad_hoc_research', 't', ?, '2025-12-31', 'snap1', 'received')",
            (json.dumps(bad_intent, ensure_ascii=False),),
        )
        conn.execute(
            "INSERT INTO investment_theses "
            "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
            "title, belief_statement, owner, status) "
            "VALUES ('th_no_th', 'ri_no_th', 'p1', 1, 't', 't', 'r', 'draft')"
        )
        conn.commit()
        conn.close()

        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(StructuredIntentIncompleteError):
            svc.create_candidate_set(
                thesis_id="th_no_th",
                data_snapshot_id="snap1",
                actor_id="r",
            )

    def test_missing_risk_tolerance_raises(self, gov_db, governance_repo, priority_repo):
        """缺少 risk_tolerance 抛 StructuredIntentIncompleteError。"""
        conn = sqlite3.connect(str(gov_db))
        bad_intent = _intent()
        del bad_intent["risk_tolerance"]
        conn.execute(
            "INSERT INTO research_inputs "
            "(user_input_id, input_type, business_mode, strategy_policy_id, "
            "strategy_policy_version, actor_role, actor_id, request_source, raw_text, "
            "structured_intent_json, as_of_date, data_snapshot_id, status) "
            "VALUES ('ri_no_rt', 'philosophy', 'private_strategy', 'p1', 1, 'researcher', "
            "'r', 'ad_hoc_research', 't', ?, '2025-12-31', 'snap1', 'received')",
            (json.dumps(bad_intent, ensure_ascii=False),),
        )
        conn.execute(
            "INSERT INTO investment_theses "
            "(thesis_id, user_input_id, strategy_policy_id, strategy_policy_version, "
            "title, belief_statement, owner, status) "
            "VALUES ('th_no_rt', 'ri_no_rt', 'p1', 1, 't', 't', 'r', 'draft')"
        )
        conn.commit()
        conn.close()

        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(StructuredIntentIncompleteError):
            svc.create_candidate_set(
                thesis_id="th_no_rt",
                data_snapshot_id="snap1",
                actor_id="r",
            )

    def test_belief_link_nullable(self, governance_repo, priority_repo):
        """belief_link 可空时正常工作。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th3",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        assert result["candidate_set_id"]
        assert result["thesis_id"] == "th3"

    def test_uses_snapshot_paths_for_engine(
        self, governance_repo, priority_repo, source_file, factor_file
    ):
        """服务使用 snapshot 行中的 source/factor 路径构建 CognitionEngine。"""
        batch = _make_batch()
        captured_args: list[tuple] = []

        def factory(source_db: str, factor_db: str | None):
            captured_args.append((source_db, factor_db))
            return _make_mock_engine(batch)

        svc = CognitionGovernanceService(governance_repo, priority_repo, engine_factory=factory)
        svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        assert len(captured_args) == 1
        assert captured_args[0][0] == str(source_file)
        assert captured_args[0][1] == str(factor_file)

    def test_snapshot_path_not_exist_raises(self, governance_repo, priority_repo):
        """snapshot 路径不存在抛 CandidateDataSourceUnavailableError。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(CandidateDataSourceUnavailableError):
            svc.create_candidate_set(
                thesis_id="th1",
                data_snapshot_id="snap2",
                actor_id="researcher_001",
            )

    def test_all_candidates_are_funds(self, governance_repo, priority_repo):
        """自动 CandidateSet 只包含基金(asset_type=fund)。"""
        evs = [
            _make_evidence(fund_code="001001"),
            _make_evidence(fund_code="001002"),
            _make_evidence(fund_code="001003"),
        ]
        batch = _make_batch(all_candidates=evs)
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        cs_id = result["candidate_set_id"]
        candidates = governance_repo.get_candidates_by_set(cs_id)
        assert len(candidates) == 3
        for c in candidates:
            assert c["asset_type"] == "fund"

    def test_all_matched_candidates_included(self, governance_repo, priority_repo):
        """通过、估值观察、数据不足和明确点名但无持仓的基金都纳入 CandidateSet。"""
        evs = [
            _make_evidence(fund_code="001001", fund_name="通过基金"),
            _make_evidence(
                fund_code="001002",
                fund_name="估值观察基金",
                valuation={"weighted_pe": 100, "weighted_pb": 20},
            ),
            _make_evidence(
                fund_code="001003",
                fund_name="数据不足基金",
                holding_report_date=None,
                holding_age_days=None,
                disclosed_holding_weight=0.0,
            ),
        ]
        batch = _make_batch(all_candidates=evs)
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        cs_id = result["candidate_set_id"]
        candidates = governance_repo.get_candidates_by_set(cs_id)
        assert len(candidates) == 3
        codes = {c["asset_code"] for c in candidates}
        assert codes == {"001001", "001002", "001003"}

    def test_unmapped_count_recorded(self, governance_repo, priority_repo):
        """全市场无映射且未点名的基金只进入计数。"""
        evs = [_make_evidence(fund_code="001001")]
        batch = _make_batch(
            all_candidates=evs,
            scanned_fund_count=100,
            mapped_candidate_count=1,
            unmapped_due_to_data_count=99,
        )
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        assert result["scanned_fund_count"] == 100
        assert result["mapped_candidate_count"] == 1
        assert result["unmapped_due_to_data_count"] == 99
        cs_id = result["candidate_set_id"]
        candidates = governance_repo.get_candidates_by_set(cs_id)
        assert len(candidates) == 1

    def test_duplicate_returns_existing_id(self, governance_repo, priority_repo):
        """相同 Thesis/snapshot/source method 重试返回冲突及已有 candidate_set_id。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result1 = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        with pytest.raises(DuplicateCandidateSetError) as exc_info:
            svc.create_candidate_set(
                thesis_id="th1",
                data_snapshot_id="snap1",
                actor_id="researcher_001",
            )
        assert exc_info.value.candidate_set_id == result1["candidate_set_id"]

    def test_does_not_update_structured_intent(self, governance_repo, priority_repo):
        """服务不更新 research_inputs.structured_intent_json。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        ri = governance_repo.get_research_input("ri1")
        assert ri is not None
        assert ri["structured_intent"]["direction"] == "AI"
        assert ri["structured_intent"]["belief_link"] == "光模块"

    def test_thesis_not_found_raises(self, governance_repo, priority_repo):
        """Thesis 不存在抛 ThesisNotFoundError。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(ThesisNotFoundError):
            svc.create_candidate_set(
                thesis_id="nonexistent",
                data_snapshot_id="snap1",
                actor_id="researcher_001",
            )

    def test_snapshot_not_found_raises(self, governance_repo, priority_repo):
        """Snapshot 不存在抛 SnapshotNotFoundError。"""
        batch = _make_batch()
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        with pytest.raises(SnapshotNotFoundError):
            svc.create_candidate_set(
                thesis_id="th1",
                data_snapshot_id="nonexistent",
                actor_id="researcher_001",
            )

    def test_engine_closed_in_finally(self, governance_repo, priority_repo):
        """CognitionEngine 在 finally 中关闭。"""
        batch = _make_batch()
        engine = _make_mock_engine(batch)
        factory = Mock(return_value=engine)
        svc = CognitionGovernanceService(governance_repo, priority_repo, engine_factory=factory)
        svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        engine.close.assert_called_once()

    def test_fit_score_uses_matched_holding_weight(self, governance_repo, priority_repo):
        """CandidateSet 中的 fit_score 使用真实目标权重(matched_holding_weight)。"""
        ev = _make_evidence(fund_code="001001", matched_holding_weight=0.25)
        batch = _make_batch(all_candidates=[ev])
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        candidates = governance_repo.get_candidates_by_set(result["candidate_set_id"])
        assert candidates[0]["fit_score"] == 0.25

    def test_candidate_evidence_json_stored(self, governance_repo, priority_repo):
        """candidate_evidence_json 保存完整 FundCandidateEvidence 的 dict 形式。"""
        ev = _make_evidence(fund_code="001001", matched_holding_weight=0.15)
        batch = _make_batch(all_candidates=[ev])
        svc = CognitionGovernanceService(
            governance_repo, priority_repo, engine_factory=_make_engine_factory(batch)
        )
        result = svc.create_candidate_set(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
        )
        candidates = governance_repo.get_candidates_by_set(result["candidate_set_id"])
        evidence = candidates[0]["candidate_evidence"]
        assert evidence is not None
        assert evidence["fund_code"] == "001001"
        assert evidence["matched_holding_weight"] == 0.15
        assert evidence["asset_type"] == "fund"


# ============================================================
# Task 8: PriorityRun 编排
# ============================================================
class TestCreatePriorityRun:
    """PriorityRun 编排测试。"""

    def test_thesis_not_found_raises(self, governance_repo, priority_repo, gov_db):
        """Thesis 不存在抛 ThesisNotFoundError。"""
        _insert_candidate_set(gov_db)
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(ThesisNotFoundError):
            svc.create_priority_run(
                thesis_id="nonexistent",
                candidate_set_id="cs_existing",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

    def test_candidate_set_not_found_raises(self, governance_repo, priority_repo, gov_db):
        """CandidateSet 不存在抛 CandidateSetNotFoundError。"""
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(CandidateSetNotFoundError):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="nonexistent",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

    def test_candidate_set_belongs_to_other_thesis(self, governance_repo, priority_repo, gov_db):
        """集合属于其他 Thesis 抛 GovernanceError。"""
        _insert_candidate_set(gov_db, thesis_id="th1", candidate_set_id="cs_other")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(GovernanceError, match="不一致"):
            svc.create_priority_run(
                thesis_id="th3",
                candidate_set_id="cs_other",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

    def test_snapshot_mismatch_raises(self, governance_repo, priority_repo, gov_db):
        """集合快照与请求不一致抛 GovernanceError。"""
        _insert_candidate_set(gov_db, data_snapshot_id="snap1")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(GovernanceError, match="data_snapshot_id"):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_existing",
                data_snapshot_id="snap2",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

    def test_candidate_evidence_missing_raises(self, governance_repo, priority_repo, gov_db):
        """candidate evidence 缺失抛 GovernanceError。"""
        # 插入一个没有 candidate_evidence_json 的候选
        conn = sqlite3.connect(str(gov_db))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO candidate_set_headers "
            "(candidate_set_id, thesis_id, user_input_id, data_snapshot_id, "
            "source_method_version, scanned_fund_count, mapped_candidate_count, "
            "unmapped_due_to_data_count, created_by) "
            "VALUES ('cs_no_ev', 'th1', 'ri1', 'snap1', 'fund_candidate_evidence_v0', "
            "10, 1, 0, 'system')"
        )
        conn.execute(
            "INSERT INTO candidate_sets "
            "(candidate_id, candidate_set_id, thesis_id, user_input_id, "
            "asset_type, asset_code, asset_name, data_snapshot_id) "
            "VALUES ('can_ne', 'cs_no_ev', 'th1', 'ri1', 'fund', '001001', 'test', 'snap1')"
        )
        conn.commit()
        conn.close()

        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(GovernanceError, match="candidate_evidence"):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_no_ev",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

    def test_method_version_mismatch_raises(self, governance_repo, priority_repo, gov_db):
        """策略 method version 不一致抛 GovernanceError。"""
        _insert_candidate_set(gov_db)
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(GovernanceError, match="method_version"):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_existing",
                data_snapshot_id="snap1",
                ranking_method_version="wrong_version",
                actor_id="researcher_001",
            )

    def test_duplicate_returns_existing_run_id(
        self, governance_repo, priority_repo, gov_db
    ):
        """重复幂等冲突携带已有 priority_run_id。"""
        _insert_candidate_set(gov_db)
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        result1 = svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_existing",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        with pytest.raises(DuplicatePriorityRunError) as exc_info:
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_existing",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )
        assert exc_info.value.priority_run_id == result1["priority_run_id"]

    def test_all_excluded_returns_no_eligible_candidate(
        self, governance_repo, priority_repo, gov_db
    ):
        """所有候选排除时 result_type=no_eligible_candidate 且业务成功。"""
        # 构造一个会被排除的证据(资产类型不匹配 -> 但 asset_type 在 evidence 中是 fund)
        # 用 matched_holding_weight 低于策略最低要求来触发排除
        ev = _make_evidence(
            fund_code="001001",
            matched_holding_weight=0.001,  # 低于 minimum_target_holding_weight=0.03
        )
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_excluded")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        result = svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_excluded",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        assert result["result_type"] == "no_eligible_candidate"
        assert result["eligible_candidate_count"] == 0
        assert result["evaluated_candidate_count"] == 1
        assert result["tier_counts"]["excluded"] == 1

    def test_successful_ranked_candidates(
        self, governance_repo, priority_repo, gov_db
    ):
        """正常评价返回 ranked_candidates。"""
        ev = _make_evidence(fund_code="001001", matched_holding_weight=0.10)
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_ok")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        result = svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_ok",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        assert result["result_type"] == "ranked_candidates"
        assert result["eligible_candidate_count"] >= 1
        assert result["evaluated_candidate_count"] == 1

    def test_evaluation_exception_writes_failure_audit_only(
        self, governance_repo, priority_repo, gov_db
    ):
        """计算异常只写失败 audit，不写 run。"""
        ev = _make_evidence(fund_code="001001")
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_fail")
        svc = CognitionGovernanceService(governance_repo, priority_repo)

        # Mock evaluate_all 抛异常
        original_evaluate = svc._priority_engine.evaluate_all
        svc._priority_engine.evaluate_all = Mock(side_effect=RuntimeError("计算崩溃"))

        with pytest.raises(RuntimeError, match="计算崩溃"):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_fail",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )

        # 恢复
        svc._priority_engine.evaluate_all = original_evaluate

        # 验证没有创建 PriorityRun
        runs = priority_repo.list_runs_by_thesis("th1")
        # 过滤掉其他测试可能创建的 run
        fail_runs = [r for r in runs if r["candidate_set_id"] == "cs_fail"]
        assert len(fail_runs) == 0

        # 验证写了失败 audit
        conn = sqlite3.connect(str(gov_db))
        audit_rows = conn.execute(
            "SELECT * FROM audit_log WHERE action = 'create_priority_run_failed' "
            "AND target_id = 'cs_fail'"
        ).fetchall()
        conn.close()
        assert len(audit_rows) == 1
        payload = json.loads(audit_rows[0][6])  # payload_json
        assert payload["error_type"] == "RuntimeError"
        assert payload["error_code"] == "evaluation_failed"
        # 不含敏感数据
        assert "matched_holding_weight" not in json.dumps(payload)
        assert "source_db_path" not in json.dumps(payload)

    def test_result_write_exception_rolls_back(
        self, governance_repo, priority_repo, gov_db
    ):
        """结果写入异常整套回滚。"""
        from app.persistence.candidate_priority import CandidatePriorityTransaction

        ev = _make_evidence(fund_code="001001")
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_rollback")
        svc = CognitionGovernanceService(governance_repo, priority_repo)

        # Mock insert_results 抛异常
        original = CandidatePriorityTransaction.insert_results
        CandidatePriorityTransaction.insert_results = Mock(
            side_effect=sqlite3.IntegrityError("模拟写入失败")
        )
        try:
            with pytest.raises(sqlite3.IntegrityError, match="模拟写入失败"):
                svc.create_priority_run(
                    thesis_id="th1",
                    candidate_set_id="cs_rollback",
                    data_snapshot_id="snap1",
                    ranking_method_version="fund_priority_v0",
                    actor_id="researcher_001",
                )
        finally:
            CandidatePriorityTransaction.insert_results = original

        # 验证没有创建 PriorityRun
        conn = sqlite3.connect(str(gov_db))
        rows = conn.execute(
            "SELECT * FROM candidate_priority_runs WHERE candidate_set_id = 'cs_rollback'"
        ).fetchall()
        conn.close()
        assert len(rows) == 0

    def test_policy_not_found_raises(self, governance_repo, priority_repo, gov_db):
        """策略不存在抛 GovernanceError。"""
        # 先关闭外键检查，修改 thesis 引用不存在的策略
        _insert_candidate_set(gov_db, thesis_id="th1", candidate_set_id="cs_np")
        conn = sqlite3.connect(str(gov_db))
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "UPDATE investment_theses SET strategy_policy_id = 'nonexistent', "
            "strategy_policy_version = 99 WHERE thesis_id = 'th1'"
        )
        conn.commit()
        conn.close()

        svc = CognitionGovernanceService(governance_repo, priority_repo)
        with pytest.raises(GovernanceError):
            svc.create_priority_run(
                thesis_id="th1",
                candidate_set_id="cs_np",
                data_snapshot_id="snap1",
                ranking_method_version="fund_priority_v0",
                actor_id="researcher_001",
            )


# ============================================================
# 查询服务
# ============================================================
class TestQueryService:
    """查询服务测试。"""

    def test_get_priority_run_returns_grouped_results(
        self, governance_repo, priority_repo, gov_db
    ):
        """get_priority_run 返回按五档分组的候选列表。"""
        evs = [
            _make_evidence(fund_code="001001", matched_holding_weight=0.10),
            _make_evidence(
                fund_code="001002",
                matched_holding_weight=0.001,  # 低于最低要求 -> excluded
            ),
        ]
        _insert_candidate_set(gov_db, candidates=evs, candidate_set_id="cs_query")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        result = svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_query",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        run_id = result["priority_run_id"]

        detail = svc.get_priority_run(run_id)
        assert detail is not None
        assert detail["priority_run_id"] == run_id
        assert detail["thesis_id"] == "th1"
        assert detail["candidate_set_id"] == "cs_query"
        assert "candidates_by_tier" in detail
        tiers = detail["candidates_by_tier"]
        for tier_name in ("research_now", "research_next", "valuation_watch",
                          "data_insufficient", "excluded"):
            assert tier_name in tiers
        # 001002 应该在 excluded
        excluded_codes = [r["fund_code"] for r in tiers["excluded"]]
        assert "001002" in excluded_codes

    def test_get_priority_run_not_found(self, governance_repo, priority_repo):
        """查询不存在的 run 返回 None。"""
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        assert svc.get_priority_run("nonexistent") is None

    def test_list_priority_runs_by_thesis(
        self, governance_repo, priority_repo, gov_db
    ):
        """list_priority_runs 按 Thesis 查询历史。"""
        ev = _make_evidence(fund_code="001001")
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_list")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_list",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        runs = svc.list_priority_runs("th1")
        assert len(runs) >= 1
        assert all(r["thesis_id"] == "th1" for r in runs)

    def test_approved_for_production_flag(
        self, governance_repo, priority_repo, gov_db
    ):
        """approved_for_production 从策略中获取。"""
        ev = _make_evidence(fund_code="001001")
        _insert_candidate_set(gov_db, candidates=[ev], candidate_set_id="cs_approved")
        svc = CognitionGovernanceService(governance_repo, priority_repo)
        result = svc.create_priority_run(
            thesis_id="th1",
            candidate_set_id="cs_approved",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
        detail = svc.get_priority_run(result["priority_run_id"])
        assert detail is not None
        assert detail["approved_for_production"] is False
