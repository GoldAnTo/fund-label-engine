from app.portfolio.constraints import build_portfolio_draft


def test_build_portfolio_draft_caps_high_risk_satellite() -> None:
    rows = [
        {
            "fund_code": "000001",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate", "satellite_alpha"],
            "return_tags": ["alpha_positive", "information_ratio_high"],
            "risk_tags": ["volatility_high"],
            "watch_reasons": [],
        },
        {
            "fund_code": "000002",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate", "defensive_anchor"],
            "return_tags": ["alpha_positive"],
            "risk_tags": [],
            "watch_reasons": [],
        },
        {
            "fund_code": "000003",
            "allocation_status": "observe",
            "portfolio_roles": ["satellite_alpha"],
            "return_tags": ["alpha_positive", "information_ratio_high"],
            "risk_tags": [],
            "watch_reasons": ["benchmark_data_missing"],
        },
    ]

    draft = build_portfolio_draft(rows)

    weights = {row["fund_code"]: row for row in draft["rows"]}
    assert "000003" not in weights
    assert weights["000001"]["max_weight_pct"] == 5
    assert weights["000001"]["bucket"] == "satellite"
    assert weights["000002"]["bucket"] == "core"
    assert round(sum(row["draft_weight_pct"] for row in draft["rows"]), 6) == 100
    assert draft["excluded"][0]["fund_code"] == "000003"
    assert "benchmark_data_missing" in draft["excluded"][0]["reasons"]
