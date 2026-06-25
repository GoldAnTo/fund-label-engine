from app.factors.exposure_aggregator import aggregate_factor_exposures
from app.label_engine.engine import RuleConfig


def test_aggregate_factor_exposures_weighted_numeric_and_style_weights():
    exposures = aggregate_factor_exposures(
        fund_code="000001",
        report_date="2024-12-31",
        holdings=[
            {"stock_code": "600001", "weight": 0.30},
            {"stock_code": "600002", "weight": 0.20},
            {"stock_code": "600003", "weight": 0.10},
        ],
        stock_factors=[
            {
                "stock_code": "600001",
                "pb": 1.0,
                "roe": 0.20,
                "revenue_growth": 0.18,
                "dividend_yield": 0.04,
                "valuation_percentile": 0.20,
                "factor_date": "2026-06-01",
            },
            {
                "stock_code": "600002",
                "pb": 3.0,
                "roe": 0.10,
                "revenue_growth": 0.05,
                "dividend_yield": 0.01,
                "valuation_percentile": 0.60,
                "factor_date": "2026-06-01",
            },
        ],
        rule_config=RuleConfig(),
    )

    by_code = {item.factor_code: item for item in exposures}
    assert by_code["pb_weighted"].exposure_value == 1.8
    assert by_code["pb_weighted"].coverage_weight == 0.5
    assert by_code["factor_coverage_weight"].exposure_value == 0.5
    assert by_code["deep_value_weight"].exposure_value == 0.3
    assert by_code["quality_growth_weight"].exposure_value == 0.3
    assert by_code["dividend_steady_weight"].exposure_value == 0.3
    assert by_code["pb_weighted"].stock_count == 3
    assert by_code["pb_weighted"].covered_stock_count == 2
    assert by_code["pb_weighted"].as_of_date == "2026-06-01"


def test_missing_factor_values_reduce_per_factor_coverage():
    exposures = aggregate_factor_exposures(
        fund_code="000001",
        report_date="2024-12-31",
        holdings=[
            {"stock_code": "600001", "weight": 0.30},
            {"stock_code": "600002", "weight": 0.20},
        ],
        stock_factors=[
            {"stock_code": "600001", "pb": 1.0, "roe": 0.20},
            {"stock_code": "600002", "roe": 0.10},
        ],
        rule_config=RuleConfig(),
    )

    by_code = {item.factor_code: item for item in exposures}
    assert by_code["pb_weighted"].exposure_value == 1.0
    assert by_code["pb_weighted"].coverage_weight == 0.3
    assert by_code["roe_weighted"].coverage_weight == 0.5
