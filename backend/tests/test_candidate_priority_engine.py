"""CandidatePriorityEngine 纯规则测试。

覆盖:
    1. 策略硬门禁 -> excluded
    2. 数据可信度门禁 -> data_insufficient
    3. 估值软门禁 -> valuation_watch / 估值硬门禁 -> excluded
    4. research_now / research_next 判定
    5. 档内排序稳定性
    6. fit_score / evidence_score 公式
    7. 配置错误抛 CandidatePriorityConfigurationError
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from app.services.candidate_priority import (
    CandidatePriorityConfigurationError,
    CandidatePriorityEngine,
    CandidatePriorityPolicy,
    FundCandidateEvidence,
    parse_candidate_priority_policy,
)


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture()
def policy() -> CandidatePriorityPolicy:
    """完整策略，满足 research_now 条件的基准策略。"""
    return CandidatePriorityPolicy(
        method_version="fund_priority_v0",
        source_method_version="fund_candidate_evidence_v0",
        asset_type="fund",
        minimum_target_holding_weight=0.03,
        minimum_disclosed_holding_weight=0.10,
        minimum_factor_coverage_weight=0.50,
        maximum_holding_age_days=180,
        valuation_breach_mode="watch",
        require_manager_identity=True,
        require_holding_report_date=True,
        required_evidence=(
            "business_logic",
            "earnings_or_cashflow",
            "valuation",
            "catalyst_or_expectation_gap",
        ),
        allowed_asset_types=("fund",),
        excluded_asset_codes=(),
        valuation_policy={
            "max_pe": 60,
            "max_pb": 10,
            "max_peg": 2.0,
            "max_valuation_percentile": 85,
        },
        approved_for_production=False,
    )


@pytest.fixture()
def evidence() -> FundCandidateEvidence:
    """完整证据，满足 research_now 条件的基准证据。"""
    return FundCandidateEvidence(
        fund_code="001001",
        fund_name="华夏成长",
        matched_holding_weight=0.10,
        disclosed_holding_weight=0.30,
        normalized_match_pct=0.10 / 0.30,
        holding_report_date="2025-12-31",
        holding_age_days=30,
        factor_coverage_weight=0.80,
        valuation={"weighted_pe": 30, "weighted_pb": 3},
        holding_trend={"trend": "stable"},
        manager_identity={"name": "张三"},
        evidence_types={
            "business_logic": [{"source": "chain_graph", "ref": "c1"}],
            "earnings_or_cashflow": [{"source": "fund_report", "ref": "r1"}],
            "valuation": [{"source": "valuation_gate", "ref": "v1"}],
            "catalyst_or_expectation_gap": [{"source": "expectation_gap", "ref": "e1"}],
        },
        policy_conflicts=(),
        data_snapshot_id="snap1",
    )


# ============================================================
# 策略硬门禁
# ============================================================
def test_hard_gate_asset_type_not_allowed_excludes(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """资产类型不在 allowed 列表 -> excluded。"""
    ev = replace(evidence, asset_type="stock")
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "excluded"
    assert result.eligibility_status == "ineligible"
    assert "policy_asset_type_not_allowed" in result.reason_codes


def test_hard_gate_excluded_asset_code_excludes(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """基金代码在策略黑名单 -> excluded。"""
    ev = replace(evidence, fund_code="006666")
    pol = replace(policy, excluded_asset_codes=("006666",))
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, pol)
    assert result.priority_tier == "excluded"
    assert "policy_universe_excluded" in result.reason_codes


def test_hard_gate_target_exposure_below_minimum_excludes(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """真实目标持仓低于策略最低要求 -> excluded。"""
    ev = replace(evidence, matched_holding_weight=0.01)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "excluded"
    assert "target_exposure_below_minimum" in result.reason_codes


# ============================================================
# 数据可信度门禁
# ============================================================
def test_data_stale_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """高匹配但持仓过期 -> data_insufficient。"""
    ev = replace(evidence, matched_holding_weight=0.30, holding_age_days=181)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert result.eligibility_status == "unassessable"
    assert "holding_data_stale" in result.reason_codes


def test_holding_report_date_missing_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """持仓报告期缺失 -> data_insufficient。"""
    ev = replace(evidence, holding_report_date=None, holding_age_days=None)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert "holding_report_date_missing" in result.reason_codes


def test_disclosed_holding_weight_low_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """披露权重不足 -> data_insufficient。"""
    ev = replace(evidence, disclosed_holding_weight=0.05)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert "disclosed_holding_weight_low" in result.reason_codes


def test_factor_coverage_insufficient_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """因子覆盖不足 -> data_insufficient。"""
    ev = replace(evidence, factor_coverage_weight=0.30)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert "factor_coverage_insufficient" in result.reason_codes


def test_manager_identity_missing_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """经理缺失 -> data_insufficient。"""
    ev = replace(evidence, manager_identity=None)
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert "manager_identity_missing" in result.reason_codes


def test_valuation_data_missing_leads_to_data_insufficient(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """估值证据缺失 -> data_insufficient。"""
    ev = replace(evidence, valuation={})
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "data_insufficient"
    assert "valuation_data_missing" in result.reason_codes


# ============================================================
# 估值软门禁 / 硬门禁
# ============================================================
def test_valuation_soft_breach_leads_to_valuation_watch(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """高匹配但估值偏贵(软限制) -> valuation_watch。"""
    ev = replace(evidence, valuation={"weighted_pe": 61, "weighted_pb": 5})
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "valuation_watch"
    assert result.eligibility_status == "eligible"
    assert "valuation_soft_breach" in result.reason_codes


def test_valuation_hard_breach_with_exclude_mode_leads_to_excluded(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """估值 hard breach + valuation_breach_mode=exclude -> excluded。"""
    ev = replace(evidence, valuation={"weighted_pe": 100, "weighted_pb": 20})
    pol = replace(policy, valuation_breach_mode="exclude")
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, pol)
    assert result.priority_tier == "excluded"
    assert "valuation_hard_breach" in result.reason_codes


# ============================================================
# research_now / research_next
# ============================================================
def test_all_evidence_complete_and_valuation_fair_leads_to_research_now(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """全部证据完整且估值合理 -> research_now。"""
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(evidence, policy)
    assert result.priority_tier == "research_now"
    assert result.eligibility_status == "eligible"
    assert "all_required_evidence_present" in result.reason_codes


def test_holding_trend_decreasing_leads_to_research_next(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """下降趋势 -> research_next。"""
    ev = replace(evidence, holding_trend={"trend": "decreasing"})
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.priority_tier == "research_next"
    assert "holding_trend_decreasing" in result.reason_codes


# ============================================================
# 排序
# ============================================================
def test_real_target_holding_drives_ranking_not_disclosed_match_pct(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """真实目标持仓驱动排序，不是披露内匹配比例。

    基金A matched=0.05/purity=0.50 (纯度更高)
    基金B matched=0.10/purity=0.20 (纯度更低但真实持仓更高)
    -> B 排在 A 前面
    """
    fund_a = replace(
        evidence,
        fund_code="A",
        matched_holding_weight=0.05,
        disclosed_holding_weight=0.10,
        normalized_match_pct=0.50,
    )
    fund_b = replace(
        evidence,
        fund_code="B",
        matched_holding_weight=0.10,
        disclosed_holding_weight=0.50,
        normalized_match_pct=0.20,
    )
    engine = CandidatePriorityEngine()
    results = engine.evaluate_all([fund_a, fund_b], policy)
    ranked = [r for r in results if r.priority_tier == "research_now"]
    assert len(ranked) == 2
    assert ranked[0].fund_code == "B"
    assert ranked[1].fund_code == "A"
    assert ranked[0].priority_rank == 1
    assert ranked[1].priority_rank == 2


def test_evaluate_all_is_deterministic_for_same_input(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """同输入重复运行完全一致。"""
    engine = CandidatePriorityEngine()
    results1 = engine.evaluate_all([evidence], policy)
    results2 = engine.evaluate_all([evidence], policy)
    assert len(results1) == len(results2) == 1
    r1 = results1[0]
    r2 = results2[0]
    assert r1.priority_tier == r2.priority_tier
    assert r1.priority_rank == r2.priority_rank
    assert r1.fit_score == r2.fit_score
    assert r1.evidence_score == r2.evidence_score
    assert r1.reason_codes == r2.reason_codes


# ============================================================
# priority_rank 规则
# ============================================================
def test_excluded_and_data_insufficient_have_null_rank(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """excluded/data_insufficient 的 priority_rank 为 None。"""
    excluded_ev = replace(evidence, fund_code="EXC", asset_type="stock")
    data_insufficient_ev = replace(
        evidence, fund_code="DAT", holding_report_date=None, holding_age_days=None
    )
    research_ev = replace(evidence, fund_code="RES")
    engine = CandidatePriorityEngine()
    results = engine.evaluate_all([excluded_ev, data_insufficient_ev, research_ev], policy)
    by_code = {r.fund_code: r for r in results}
    assert by_code["EXC"].priority_rank is None
    assert by_code["DAT"].priority_rank is None
    assert by_code["RES"].priority_rank is not None


# ============================================================
# 指标公式
# ============================================================
def test_evidence_score_equals_satisfied_required_evidence_ratio(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """evidence_score 严格等于 已满足的必需证据类型数/必需证据总数。"""
    ev = replace(
        evidence,
        evidence_types={
            "business_logic": [{"source": "s"}],
            "earnings_or_cashflow": [{"source": "s"}],
            # 缺少 valuation 和 catalyst_or_expectation_gap
        },
    )
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    # 2/4 = 0.5
    assert result.evidence_score == pytest.approx(0.5)


def test_fit_score_and_normalized_match_pct(
    evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
) -> None:
    """真实目标持仓 5%、已披露持仓 10% 时，fit_score=0.05, normalized_match_pct=0.5。"""
    ev = replace(
        evidence,
        matched_holding_weight=0.05,
        disclosed_holding_weight=0.10,
        normalized_match_pct=0.5,
    )
    engine = CandidatePriorityEngine()
    result = engine.evaluate_one(ev, policy)
    assert result.fit_score == pytest.approx(0.05)
    assert result.evidence.normalized_match_pct == pytest.approx(0.5)


# ============================================================
# 配置解析
# ============================================================
def test_parse_policy_missing_field_raises_configuration_error() -> None:
    """配置缺失字段抛 CandidatePriorityConfigurationError。"""
    policy_row = {
        "candidate_priority": {
            "method_version": "fund_priority_v0",
            "source_method_version": "fund_candidate_evidence_v0",
            "asset_type": "fund",
            # minimum_target_holding_weight 缺失
            "minimum_disclosed_holding_weight": 0.10,
            "minimum_factor_coverage_weight": 0.50,
            "maximum_holding_age_days": 180,
            "valuation_breach_mode": "watch",
            "require_manager_identity": True,
            "require_holding_report_date": True,
            "required_evidence": ["business_logic"],
            "allowed_asset_types": ["fund"],
            "excluded_asset_codes": [],
            "valuation_policy": {"max_pe": 60, "max_pb": 10},
            "approved_for_production": False,
        },
        "valuation_policy": {"max_pe": 60, "max_pb": 10},
        "allowed_universe": ["fund"],
        "excluded_universe": [],
        "approved_for_production": False,
    }
    with pytest.raises(CandidatePriorityConfigurationError):
        parse_candidate_priority_policy(policy_row)


def test_parse_policy_none_field_raises_configuration_error() -> None:
    """配置字段为 None 抛 CandidatePriorityConfigurationError。"""
    policy_row = {
        "candidate_priority": {
            "method_version": "fund_priority_v0",
            "source_method_version": "fund_candidate_evidence_v0",
            "asset_type": "fund",
            "minimum_target_holding_weight": None,
            "minimum_disclosed_holding_weight": 0.10,
            "minimum_factor_coverage_weight": 0.50,
            "maximum_holding_age_days": 180,
            "valuation_breach_mode": "watch",
            "require_manager_identity": True,
            "require_holding_report_date": True,
            "required_evidence": ["business_logic"],
            "allowed_asset_types": ["fund"],
            "excluded_asset_codes": [],
            "valuation_policy": {"max_pe": 60, "max_pb": 10},
            "approved_for_production": False,
        },
        "valuation_policy": {"max_pe": 60, "max_pb": 10},
        "allowed_universe": ["fund"],
        "excluded_universe": [],
        "approved_for_production": False,
    }
    with pytest.raises(CandidatePriorityConfigurationError):
        parse_candidate_priority_policy(policy_row)


def test_parse_policy_none_candidate_priority_raises_configuration_error() -> None:
    """candidate_priority 为 None 抛 CandidatePriorityConfigurationError。"""
    policy_row = {
        "candidate_priority": None,
        "valuation_policy": {"max_pe": 60, "max_pb": 10},
        "allowed_universe": ["fund"],
        "excluded_universe": [],
        "approved_for_production": False,
    }
    with pytest.raises(CandidatePriorityConfigurationError):
        parse_candidate_priority_policy(policy_row)
