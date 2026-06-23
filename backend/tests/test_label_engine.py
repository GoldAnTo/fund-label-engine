from app.label_engine.engine import FundInput, LabelEngine


def label_codes(result):
    return {label.label_code for label in result.labels}


def evidence_for(result, label_code):
    return [item for item in result.evidence if item.label_code == label_code]


def test_missing_required_data_emits_insufficient_and_manual_review_labels():
    fund = FundInput(
        fund_code="000001",
        fund_name="样例偏股基金",
        fund_type="混合型-偏股",
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "data_insufficient" in codes
    assert "manual_review_required" in codes
    assert result.review_action == "manual_review"
    assert evidence_for(result, "data_insufficient")


def test_concentrated_fund_emits_explainable_holding_manager_and_fee_labels():
    fund = FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.01, -0.02, 0.03, 0.015, -0.01],
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.11},
            {"stock_code": "000858", "weight": 0.09},
            {"stock_code": "000568", "weight": 0.08},
            {"stock_code": "600887", "weight": 0.07},
            {"stock_code": "300750", "weight": 0.06},
            {"stock_code": "002594", "weight": 0.05},
            {"stock_code": "601318", "weight": 0.04},
            {"stock_code": "600036", "weight": 0.04},
            {"stock_code": "000333", "weight": 0.035},
            {"stock_code": "600276", "weight": 0.035},
        ],
        industry_allocations=[
            {"industry": "食品饮料", "weight": 0.46},
            {"industry": "电力设备", "weight": 0.11},
            {"industry": "银行", "weight": 0.08},
        ],
        manager_tenure_years=6.2,
        management_fee=0.012,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "data_sufficient" in codes
    assert "holding_concentration_high" in codes
    assert "manager_tenure_long" in codes
    assert "fee_low" in codes
    assert result.review_action == "observe"

    concentration_evidence = evidence_for(result, "holding_concentration_high")
    assert concentration_evidence[0].metric == "top_10_holding_weight"
    assert concentration_evidence[0].value == 0.61
    assert "前十大持仓合计" in concentration_evidence[0].message


def test_style_labels_are_not_emitted_without_stock_factors():
    fund = FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.01, 0.02, -0.01],
        stock_holdings=[{"stock_code": "600519", "weight": 0.10}],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        manager_tenure_years=6.2,
        management_fee=0.012,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_unlabeled_stock_factors_missing" in codes
    assert "deep_value" not in codes
    assert "quality_growth" not in codes
    assert evidence_for(result, "style_unlabeled_stock_factors_missing")
