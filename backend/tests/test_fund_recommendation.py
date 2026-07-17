"""基金推荐引擎测试。

覆盖:
    1. 主动基金和 ETF/指数基金独立排名
    2. 主题暴露低于最低阈值不推荐
    3. 主题暴露权重最大
    4. 持仓缺失或过期为 data_insufficient
    5. 产品类别未知为 excluded 且不可推荐
    6. 每类最多 3 个 recommended 和 2 个 alternative
    7. 同分按基金代码稳定排序
"""
from __future__ import annotations

import pytest
from app.services.candidate_priority import FundCandidateEvidence
from app.services.fund_recommendation import (
    FundRecommendationEngine,
    FundRecommendationPolicy,
    RecommendationReason,
    parse_fund_recommendation_policy,
)


# ============================================================
# 辅助函数
# ============================================================
def _policy(
    minimum: float = 0.03,
    active_limit: int = 3,
    etf_limit: int = 3,
    alt_limit: int = 2,
) -> FundRecommendationPolicy:
    return FundRecommendationPolicy(
        method_version="fund_recommendation_v1",
        source_method_version="fund_candidate_evidence_v0",
        minimum_target_holding_weight=minimum,
        maximum_holding_age_days=180,
        active_fund_limit=active_limit,
        etf_or_index_limit=etf_limit,
        alternative_limit=alt_limit,
        weights={
            "theme_exposure": 0.55,
            "thesis_alignment": 0.15,
            "risk_return": 0.15,
            "fund_quality": 0.15,
        },
    )


def _evidence(
    code: str,
    *,
    exposure: float = 0.10,
    category: str = "active_fund",
    disclosed: float = 0.5,
    report_date: str = "2025-06-30",
    age_days: int = 30,
    quality: float = 0.5,
    name: str | None = None,
    conflicts: tuple[str, ...] = (),
    valuation: dict | None = None,
    trend: str = "stable",
    evidence_types: dict | None = None,
) -> FundCandidateEvidence:
    """构建测试用 FundCandidateEvidence。"""
    if valuation is None:
        valuation = {"weighted_pe": 20, "weighted_val_pct": 50}
    if evidence_types is None:
        evidence_types = {
            "business_logic": [{"source": "test"}],
            "earnings_or_cashflow": [{"source": "test"}],
            "valuation": [{"source": "test"}],
            "catalyst_or_expectation_gap": [{"source": "test"}],
        }
    return FundCandidateEvidence(
        fund_code=code,
        fund_name=name or f"基金{code}",
        matched_holding_weight=exposure,
        disclosed_holding_weight=disclosed,
        normalized_match_pct=exposure / disclosed if disclosed > 0 else 0.0,
        holding_report_date=report_date,
        holding_age_days=age_days,
        factor_coverage_weight=quality,
        valuation=valuation,
        holding_trend={"trend": trend},
        manager_identity={"name": "manager"} if quality > 0.3 else None,
        evidence_types=evidence_types,
        policy_conflicts=conflicts,
        data_snapshot_id="snap_test",
        asset_type="fund",
        product_category=category,
    )


def _active(code: str, **kwargs) -> FundCandidateEvidence:
    return _evidence(code, category="active_fund", **kwargs)


def _etf(code: str, **kwargs) -> FundCandidateEvidence:
    return _evidence(code, category="etf_or_index", **kwargs)


def _evaluate(ev: FundCandidateEvidence, policy: FundRecommendationPolicy):
    return FundRecommendationEngine().evaluate_all([ev], policy)[0]


def _evaluate_all(evs, policy):
    return FundRecommendationEngine().evaluate_all(evs, policy)


def _by_code(results, code: str):
    for r in results:
        if r.fund_code == code:
            return r
    raise KeyError(f"fund_code {code} not found in results")


# ============================================================
# 测试
# ============================================================
class TestDualTrackRanking:
    def test_active_and_etf_rankings_are_independent(self):
        """主动基金和 ETF 各自独立排名。"""
        results = _evaluate_all(
            [
                _active("A", exposure=0.40),
                _etf("E", exposure=0.35),
                _active("B", exposure=0.30),
            ],
            _policy(),
        )
        assert _by_code(results, "A").category_rank == 1
        assert _by_code(results, "E").category_rank == 1
        assert _by_code(results, "B").category_rank == 2

    def test_theme_exposure_has_largest_weight(self):
        """主题暴露权重最大，高暴露基金排名靠前。"""
        results = _evaluate_all(
            [
                _active("A", exposure=0.50),
                _active("B", exposure=0.35, quality=1.0),
            ],
            _policy(),
        )
        assert _by_code(results, "A").category_rank == 1
        assert _by_code(results, "B").category_rank == 2

    def test_same_score_sorted_by_fund_code(self):
        """同分按基金代码稳定排序。"""
        results = _evaluate_all(
            [
                _active("C", exposure=0.10, quality=0.5),
                _active("A", exposure=0.10, quality=0.5),
                _active("B", exposure=0.10, quality=0.5),
            ],
            _policy(),
        )
        # 三个基金同分，按代码排序：A=1, B=2, C=3
        assert _by_code(results, "A").category_rank == 1
        assert _by_code(results, "B").category_rank == 2
        assert _by_code(results, "C").category_rank == 3


class TestExclusionRules:
    def test_low_exposure_never_becomes_recommended(self):
        """主题暴露低于最低阈值 -> excluded。"""
        result = _evaluate(_active("A", exposure=0.02, quality=1), _policy(minimum=0.03))
        assert result.recommendation_tier == "excluded"
        assert "target_exposure_below_minimum" in result.exclusion_codes

    def test_holding_missing_is_data_insufficient(self):
        """持仓缺失 -> data_insufficient。"""
        result = _evaluate(
            _active("A", disclosed=0.0, report_date=None),
            _policy(),
        )
        assert result.recommendation_tier == "data_insufficient"
        assert "holding_data_missing" in result.reason_codes

    def test_holding_stale_is_data_insufficient(self):
        """持仓过期 -> data_insufficient。"""
        result = _evaluate(
            _active("A", age_days=200),
            _policy(maximum_holding_age_days=180) if False else _policy(),
        )
        # maximum_holding_age_days=180, age_days=200 > 180
        assert result.recommendation_tier == "data_insufficient"
        assert "holding_data_stale" in result.reason_codes

    def test_unknown_category_is_excluded(self):
        """产品类别未知 -> excluded，不可推荐。"""
        result = _evaluate(
            _evidence("A", category=None, exposure=0.5),
            _policy(),
        )
        assert result.recommendation_tier == "excluded"
        assert "product_category_unknown" in result.exclusion_codes

    def test_policy_conflict_is_excluded(self):
        """硬冲突 -> excluded。"""
        result = _evaluate(
            _active("A", exposure=0.5, conflicts=("some_conflict",)),
            _policy(),
        )
        assert result.recommendation_tier == "excluded"
        assert "policy_conflict_detected" in result.exclusion_codes


class TestTierLimits:
    def test_max_recommended_per_category(self):
        """每类最多 3 个 recommended。"""
        evs = [_active(f"A{i}", exposure=0.40 - i * 0.01) for i in range(5)]
        results = _evaluate_all(evs, _policy(active_limit=3, alt_limit=2))
        active_results = [r for r in results if r.product_category == "active_fund"]
        recommended = [r for r in active_results if r.recommendation_tier == "candidate_pool"]
        alternative = [r for r in active_results if r.recommendation_tier == "alternative"]
        assert len(recommended) == 3
        assert len(alternative) == 2

    def test_max_alternative_per_category(self):
        """每类最多 2 个 alternative。"""
        evs = [_active(f"A{i}", exposure=0.40 - i * 0.01) for i in range(7)]
        results = _evaluate_all(evs, _policy(active_limit=3, alt_limit=2))
        active_results = [r for r in results if r.product_category == "active_fund"]
        recommended = [r for r in active_results if r.recommendation_tier == "candidate_pool"]
        alternative = [r for r in active_results if r.recommendation_tier == "alternative"]
        watch = [r for r in active_results if r.recommendation_tier == "watch"]
        assert len(recommended) == 3
        assert len(alternative) == 2
        assert len(watch) == 2  # 剩余进入 watch

    def test_etf_and_active_limits_independent(self):
        """主动基金和 ETF 各自独立的限制。"""
        evs = [
            *[_active(f"A{i}", exposure=0.40 - i * 0.01) for i in range(5)],
            *[_etf(f"E{i}", exposure=0.40 - i * 0.01) for i in range(5)],
        ]
        results = _evaluate_all(evs, _policy(active_limit=3, etf_limit=3, alt_limit=2))
        active_recs = [r for r in results if r.product_category == "active_fund" and r.recommendation_tier == "candidate_pool"]
        etf_recs = [r for r in results if r.product_category == "etf_or_index" and r.recommendation_tier == "candidate_pool"]
        assert len(active_recs) == 3
        assert len(etf_recs) == 3


class TestScoring:
    def test_total_score_is_weighted_sum(self):
        """总分 = 各分项加权求和。"""
        result = _evaluate(_active("A", exposure=0.40), _policy())
        w = _policy().weights
        expected = (
            result.theme_exposure_score * w["theme_exposure"]
            + result.thesis_alignment_score * w["thesis_alignment"]
            + result.risk_return_score * w["risk_return"]
            + result.fund_quality_score * w["fund_quality"]
        )
        assert abs(result.total_score - expected) < 0.001

    def test_missing_data_does_not_get_full_score(self):
        """缺失数据的评分不得满分。"""
        ev = FundCandidateEvidence(
            fund_code="A",
            fund_name="基金A",
            matched_holding_weight=0.10,
            disclosed_holding_weight=0.5,
            normalized_match_pct=0.2,
            holding_report_date="2025-06-30",
            holding_age_days=30,
            factor_coverage_weight=0.0,
            valuation={},
            holding_trend={},
            manager_identity=None,
            evidence_types={},
            policy_conflicts=(),
            data_snapshot_id="snap_test",
            product_category="active_fund",
        )
        result = _evaluate(ev, _policy())
        assert result.fund_quality_score < 0.5
        assert result.thesis_alignment_score < 0.25
        assert result.risk_return_score < 0.5

    def test_reasons_use_stable_codes(self):
        """理由使用稳定 code。"""
        result = _evaluate(_active("A", exposure=0.40), _policy())
        all_codes = set()
        for r in result.reasons:
            assert isinstance(r.code, str)
            assert isinstance(r.message, str)
            all_codes.add(r.code)
        # 高暴露应该有 high_theme_exposure
        assert "high_theme_exposure" in all_codes


class TestPolicyParsing:
    def test_parse_valid_policy(self):
        """解析合法的 policy_row。"""
        policy_row = {
            "fund_recommendation": {
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
        }
        policy = parse_fund_recommendation_policy(policy_row)
        assert policy.method_version == "fund_recommendation_v1"
        assert policy.active_fund_limit == 3
        assert policy.weights["theme_exposure"] == 0.55

    def test_parse_missing_config_raises(self):
        """配置缺失抛异常。"""
        with pytest.raises(Exception, match="fund_recommendation"):
            parse_fund_recommendation_policy({})

    def test_parse_json_string(self):
        """支持 JSON 字符串。"""
        import json

        policy_row = {
            "fund_recommendation": json.dumps({
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
            })
        }
        policy = parse_fund_recommendation_policy(policy_row)
        assert policy.method_version == "fund_recommendation_v1"
