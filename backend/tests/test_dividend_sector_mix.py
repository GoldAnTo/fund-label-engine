from app.factors.dividend_sector_mix import aggregate_dividend_sector_mix


def test_aggregate_dividend_sector_mix_uses_only_matched_dividend_rows() -> None:
    contributions = [
        {"stock_code": "601398", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
        {"stock_code": "600900", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.20, "report_date": "2026-06-30"},
        {"stock_code": "600519", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.10, "report_date": "2026-06-30"},
        {"stock_code": "000001", "style_code": "deep_value", "matched": 1, "contribution_weight": 0.40, "report_date": "2026-06-30"},
    ]
    industry_map = {
        "601398": {"sector_group": "financial", "as_of_date": "2026-06-30"},
        "600900": {"sector_group": "energy_utility", "as_of_date": "2026-06-30"},
        "600519": {"sector_group": "consumer", "as_of_date": "2026-06-30"},
    }

    result = aggregate_dividend_sector_mix("000001", "2026-06-30", contributions, industry_map)

    assert result is not None
    by_code = {item.factor_code: item for item in result}
    assert by_code["dividend_sector_coverage"].exposure_value == 1.0
    assert by_code["dividend_sector_financial_ratio"].exposure_value == 0.5
    assert by_code["dividend_sector_energy_utility_ratio"].exposure_value == 0.333333
    assert by_code["dividend_sector_consumer_ratio"].exposure_value == 0.166667


def test_aggregate_dividend_sector_mix_tracks_missing_industry_coverage() -> None:
    contributions = [
        {"stock_code": "601398", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
        {"stock_code": "600519", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
    ]
    industry_map = {
        "601398": {"sector_group": "financial", "as_of_date": "2026-06-30"},
    }

    result = aggregate_dividend_sector_mix("000001", "2026-06-30", contributions, industry_map)

    assert result is not None
    by_code = {item.factor_code: item for item in result}
    assert by_code["dividend_sector_coverage"].exposure_value == 0.5
    assert by_code["dividend_sector_financial_ratio"].coverage_weight == 0.5
