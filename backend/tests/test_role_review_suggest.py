"""role_review_suggest 单元测试：覆盖四个分支 + 边界。"""
import pytest

from app.portfolio.role_review_suggest import suggest_role_reviews


def _row(fund_code, status, blocking=None, watch=None, roles=None):
    return {
        "fund_code": fund_code,
        "allocation_status": status,
        "blocking_reasons": blocking or [],
        "watch_reasons": watch or [],
        "portfolio_roles": roles or [],
    }


def test_suggests_only_review_required_rows():
    matrix = [
        _row("A", "eligible"),
        _row("B", "review_required", blocking=["data_insufficient"]),
        _row("C", "excluded"),
    ]
    out = suggest_role_reviews(matrix)
    assert [s["fund_code"] for s in out] == ["B"]


def test_suggest_excludes_data_insufficient():
    matrix = [_row("A", "review_required", blocking=["data_insufficient"])]
    [s] = suggest_role_reviews(matrix)
    assert s["target_bucket"] == "exclude"
    assert s["role_code"] == "excluded"
    assert s["recommended_max_weight_pct"] == 0.0
    assert "数据不足" in s["rationale"]


def test_suggest_observe_for_manual_review_or_risk_cap():
    matrix = [
        _row("A", "review_required", blocking=["manual_review_required"]),
        _row("B", "review_required", blocking=["risk_cap"]),
    ]
    out = suggest_role_reviews(matrix)
    assert all(s["target_bucket"] == "observe" for s in out)
    assert all(s["recommended_max_weight_pct"] == 8.0 for s in out)


def test_suggest_core_when_style_unclassified_but_portfolio_ok():
    matrix = [
        _row(
            "A",
            "review_required",
            watch=["style_pending_rule_definition"],
            roles=["core_candidate"],
        )
    ]
    [s] = suggest_role_reviews(matrix)
    assert s["target_bucket"] == "core"
    assert s["role_code"] == "core"
    assert s["recommended_max_weight_pct"] == 10.0


def test_suggest_satellite_default_for_other_review_required():
    matrix = [_row("A", "review_required", blocking=["unknown_blocker"])]
    [s] = suggest_role_reviews(matrix)
    assert s["target_bucket"] == "satellite"
    assert s["role_code"] == "satellite"
    assert s["recommended_max_weight_pct"] == 5.0


def test_suggest_rationale_joins_blocking_reasons_dedup():
    matrix = [
        _row(
            "A",
            "review_required",
            blocking=["data_insufficient", "data_insufficient", "missing_data_window"],
        )
    ]
    [s] = suggest_role_reviews(matrix)
    # 重复 reason 应当去重
    assert s["rationale"].count("data_insufficient") == 1
    assert "missing_data_window" in s["rationale"]


def test_suggest_handles_empty_matrix():
    assert suggest_role_reviews([]) == []
