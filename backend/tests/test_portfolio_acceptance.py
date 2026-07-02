"""portfolio_v1_acceptance_report 单元测试。"""
from app.portfolio.acceptance import (
    bucket_by_status,
    classify_eligible,
    exclude_reasons,
    is_risk_review_fund,
    summarize_eligible,
    top_optimized,
)


def _eligible(fund_code, **kwargs):
    base = {
        "fund_code": fund_code,
        "allocation_status": "eligible",
        "portfolio_roles": ["core_holding_candidate"],
        "risk_tags": [],
        "watch_reasons": [],
        "blocking_reasons": [],
        "bucket": "core",
        "alpha_1y": 0.05,
        "annualized_volatility_1y": 0.15,
        "max_drawdown_1y": -0.1,
    }
    base.update(kwargs)
    return base


def test_is_risk_review_for_risk_tag():
    row = _eligible("A", risk_tags=["high_volatility"])
    assert is_risk_review_fund(row) is True


def test_is_risk_review_for_watch_reason():
    row = _eligible("A", watch_reasons=["allocation_risk_review"])
    assert is_risk_review_fund(row) is True


def test_is_risk_review_for_extreme_drawdown():
    row = _eligible("A", max_drawdown_1y=-0.45)
    assert is_risk_review_fund(row) is True


def test_is_risk_review_for_high_volatility():
    row = _eligible("A", annualized_volatility_1y=0.4)
    assert is_risk_review_fund(row) is True


def test_not_risk_review_for_clean_fund():
    row = _eligible("A", alpha_1y=0.04)
    assert is_risk_review_fund(row) is False


def test_classify_core_when_alpha_positive_no_risk():
    row = _eligible("A", bucket="core", alpha_1y=0.05)
    assert classify_eligible(row) == "core"


def test_classify_core_pending_risk_when_bucket_core_but_risk_flag():
    row = _eligible("A", bucket="core", risk_tags=["high_volatility"], alpha_1y=0.05)
    assert classify_eligible(row) == "core_pending_risk_review"


def test_classify_index_tool_when_role_present():
    row = _eligible("A", bucket="satellite", portfolio_roles=["index_tool", "core_holding_candidate"])
    assert classify_eligible(row) == "index_tool"


def test_classify_satellite_default():
    row = _eligible("A", bucket="satellite", alpha_1y=0.02)
    assert classify_eligible(row) == "satellite"


def test_classify_needs_more_data_when_alpha_missing():
    row = _eligible("A", bucket="core", alpha_1y=None)
    assert classify_eligible(row) == "needs_more_data"


def test_summarize_eligible_counts():
    rows = [
        _eligible("A", bucket="core", alpha_1y=0.05),
        _eligible("B", bucket="core", risk_tags=["high_volatility"], alpha_1y=0.02),
        _eligible("C", bucket="satellite", alpha_1y=0.01),
    ]
    s = summarize_eligible(rows)
    assert s.get("core") == 1
    assert s.get("core_pending_risk_review") == 1
    assert s.get("satellite") == 1


def test_bucket_by_status():
    rows = [
        {"allocation_status": "eligible"},
        {"allocation_status": "review_required"},
        {"allocation_status": "observe"},
    ]
    b = bucket_by_status(rows)
    assert len(b["eligible"]) == 1
    assert len(b["review_required"]) == 1
    assert len(b["observe"]) == 1


def test_top_optimized_sorts_by_weight_desc():
    rows = [
        {"fund_code": "A", "optimized_weight_pct": 1.0},
        {"fund_code": "B", "optimized_weight_pct": 5.0},
        {"fund_code": "C", "optimized_weight_pct": 3.0},
    ]
    top = top_optimized(rows, n=2)
    assert [r["fund_code"] for r in top] == ["B", "C"]


def test_exclude_reasons_aggregates():
    rows = [
        {"reasons": ["benchmark_data_missing"]},
        {"reasons": ["benchmark_data_missing", "not_candidate_status"]},
        {"reasons": []},
    ]
    counts = exclude_reasons(rows)
    assert counts["benchmark_data_missing"] == 2
    assert counts["not_candidate_status"] == 1
