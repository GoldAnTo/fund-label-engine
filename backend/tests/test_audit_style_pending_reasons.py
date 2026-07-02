"""style_pending_reason 二级拆分测试。"""
from scripts.audit_style_pending_reasons import style_pending_reason


def _row(features, style_tags=None):
    return {"features": features, "style_tags": style_tags or []}


def test_data_missing_when_no_style_weights():
    row = _row({"factor_coverage_weight": 0.8})
    assert style_pending_reason(row) == "style_data_missing"


def test_factor_coverage_low_when_below_50_percent():
    row = _row(
        {
            "factor_coverage_weight": 0.4,
            "quality_growth_weight": 0.2,
            "deep_value_weight": 0.1,
        }
    )
    assert style_pending_reason(row) == "style_factor_coverage_low"


def test_factor_coverage_low_when_field_absent():
    row = _row(
        {
            "quality_growth_weight": 0.5,
            "deep_value_weight": 0.1,
            "dividend_steady_weight": 0.1,
        }
    )
    # factor_coverage_weight 缺 → 视为 0 → low
    assert style_pending_reason(row) == "style_factor_coverage_low"


def test_factor_coverage_observe_band():
    row = _row(
        {
            "factor_coverage_weight": 0.6,
            "quality_growth_weight": 0.3,
            "deep_value_weight": 0.1,
            "dividend_steady_weight": 0.1,
        }
    )
    assert style_pending_reason(row) == "style_factor_coverage_observe"


def test_exposure_imbalanced_when_only_one_significant_style():
    row = _row(
        {
            "factor_coverage_weight": 0.8,
            "quality_growth_weight": 0.6,
            "deep_value_weight": 0.05,
            "dividend_steady_weight": 0.05,
        }
    )
    assert style_pending_reason(row) == "style_exposure_imbalanced"


def test_label_emitted_but_pending_when_significant_count_meets_balanced():
    row = _row(
        {
            "factor_coverage_weight": 0.8,
            "quality_growth_weight": 0.3,
            "deep_value_weight": 0.4,
            "dividend_steady_weight": 0.1,
        },
        style_tags=["value_oriented_observed"],
    )
    assert style_pending_reason(row) == "style_label_emitted_but_pending"


def test_below_formal_threshold_when_balanced_but_no_label():
    row = _row(
        {
            "factor_coverage_weight": 0.8,
            "quality_growth_weight": 0.3,
            "deep_value_weight": 0.4,
            "dividend_steady_weight": 0.1,
        },
        style_tags=[],
    )
    assert style_pending_reason(row) == "style_exposure_below_formal_threshold"


def test_priority_data_missing_wins_over_coverage():
    # 没有 weights，但 coverage 字段有 → 仍判 data_missing
    row = _row({"factor_coverage_weight": 0.9})
    assert style_pending_reason(row) == "style_data_missing"
