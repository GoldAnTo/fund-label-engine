from app.portfolio.constraints import build_portfolio_draft


def test_build_portfolio_draft_applies_manual_role_reviews() -> None:
    rows = [
        {
            "fund_code": "000001",
            "allocation_status": "eligible",
            "portfolio_roles": ["satellite_alpha"],
            "return_tags": ["alpha_positive"],
            "risk_tags": [],
            "watch_reasons": [],
        },
        {
            "fund_code": "000002",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate"],
            "return_tags": ["alpha_positive"],
            "risk_tags": [],
            "watch_reasons": [],
        },
    ]

    draft = build_portfolio_draft(
        rows,
        role_reviews={"000001": "core", "000002": "exclude"},
    )

    by_fund = {row["fund_code"]: row for row in draft["rows"]}
    assert by_fund["000001"]["bucket"] == "core"
    assert by_fund["000001"]["manual_role_review"] == "core"
    assert "000002" not in by_fund
    assert draft["excluded"] == [
        {"fund_code": "000002", "reasons": ["manual_exclude"], "manual_role_review": "exclude"}
    ]


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


def test_build_portfolio_draft_uses_manual_max_weight_pct() -> None:
    rows = [
        {
            "fund_code": "000001",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate", "index_tool"],
            "return_tags": ["alpha_positive"],
            "risk_tags": [],
            "watch_reasons": [],
        }
    ]

    draft = build_portfolio_draft(
        rows,
        role_reviews={
            "000001": {
                "decision": "accept",
                "target_bucket": "index_tool",
                "max_weight_pct": 3.0,
            }
        },
    )

    [row] = draft["rows"]
    assert row["bucket"] == "index_tool"
    assert row["manual_role_review"] == "index_tool"
    assert row["max_weight_pct"] == 3.0
