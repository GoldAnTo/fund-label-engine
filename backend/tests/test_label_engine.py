import json

from app.label_engine.engine import FundInput, LabelEngine, RuleConfig


def label_codes(result):
    return {label.label_code for label in result.labels}


def evidence_for(result, label_code):
    return [item for item in result.evidence if item.label_code == label_code]


def calculations_by_code(result):
    return {item.label_code: item for item in result.calculations}


def classifications_by_dimension(result):
    return {item.dimension: item for item in result.classifications}


def group_codes(result):
    return {item.group_code for item in result.groups}


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


def test_incomplete_data_still_emits_observable_labels_when_evidence_exists():
    fund = FundInput(
        fund_code="000002",
        fund_name="样例数据不全混合",
        fund_type="混合型-偏股",
        nav_returns=[0.01, -0.01],
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=12.0,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "data_insufficient" in codes
    assert "manual_review_required" in codes
    assert "manager_tenure_long" in codes
    assert "fee_low" in codes
    assert "data_sufficient" not in codes
    assert result.review_action == "manual_review"


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
        management_fee=0.010,
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


def test_thresholds_are_loaded_from_rule_config():
    fund = FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.01, 0.02, -0.01],
        stock_holdings=[{"stock_code": "600519", "weight": 0.50}],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        manager_tenure_years=3.2,
        management_fee=0.014,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )

    result = LabelEngine(
        RuleConfig(
            holding_concentration_threshold=0.45,
            manager_tenure_long_years=3.0,
            fee_low_threshold=0.02,
        )
    ).evaluate(fund)

    codes = label_codes(result)
    assert "holding_concentration_high" in codes
    assert "manager_tenure_long" in codes
    assert "fee_low" in codes
    assert evidence_for(result, "holding_concentration_high")[0].threshold == 0.45


def test_rule_config_loads_from_json_file(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            {
                "fee_low_threshold": 0.01,
                "style_drift_delta_threshold": 0.3,
                "high_dividend_sector_ratio_min": 0.65,
                "consumer_dominant_ratio_min": 0.55,
                "sector_coverage_min": 0.8,
            }
        ),
        encoding="utf-8",
    )

    cfg = RuleConfig.from_file(path)

    assert cfg.fee_low_threshold == 0.01
    assert cfg.style_drift_delta_threshold == 0.3
    assert cfg.high_dividend_sector_ratio_min == 0.65
    assert cfg.consumer_dominant_ratio_min == 0.55
    assert cfg.sector_coverage_min == 0.8


def test_style_labels_are_not_emitted_without_stock_factors():
    fund = FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.01, 0.02, -0.01],
        stock_holdings=[{"stock_code": "600519", "weight": 0.10}],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        manager_tenure_years=6.2,
        management_fee=0.010,
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


def test_stock_factor_boundary_is_explained_when_factors_exist_but_style_rules_are_not_ready():
    fund = FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.01, 0.02, -0.01],
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.49},
            {"stock_code": "600000", "weight": 0.21},
        ],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        stock_factors=[{"stock_code": "600519", "pb": 8.1, "roe": 0.24}],
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_exposure_low_coverage" in codes
    assert "deep_value" not in codes
    assert "quality_growth" not in codes
    ev = evidence_for(result, "style_exposure_low_coverage")[0]
    assert ev.metric == "factor_coverage_weight"


def _style_fund(stock_factors: list[dict]) -> FundInput:
    return FundInput(
        fund_code="110022",
        fund_name="易方达消费行业股票",
        fund_type="股票型",
        nav_returns=[0.001] * 30,
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.40},
            {"stock_code": "601398", "weight": 0.30},
        ],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        stock_factors=stock_factors,
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )


def test_style_exposure_low_coverage_blocks_formal_style_label():
    fund = _style_fund(stock_factors=[])
    fund = FundInput(
        **{
            **fund.__dict__,
            "factor_exposures": [
                {
                    "factor_code": "deep_value_weight",
                    "exposure_value": 0.80,
                    "coverage_weight": 0.40,
                    "as_of_date": "2026-06-01",
                },
                {
                    "factor_code": "factor_coverage_weight",
                    "exposure_value": 0.40,
                    "coverage_weight": 0.40,
                    "holding_total_weight": 0.70,
                    "as_of_date": "2026-06-01",
                },
            ],
        }
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_exposure_low_coverage" in codes
    assert "deep_value" not in codes
    ev = evidence_for(result, "style_exposure_low_coverage")[0]
    assert ev.metric == "factor_coverage_weight"
    assert ev.source == "fund_factor_exposures"


def test_style_exposure_observe_blocks_formal_style_label():
    fund = _style_fund(stock_factors=[])
    fund = FundInput(
        **{
            **fund.__dict__,
            "factor_exposures": [
                {
                    "factor_code": "quality_growth_weight",
                    "exposure_value": 0.60,
                    "coverage_weight": 0.60,
                    "as_of_date": "2026-06-01",
                },
                {
                    "factor_code": "factor_coverage_weight",
                    "exposure_value": 0.60,
                    "coverage_weight": 0.60,
                    "as_of_date": "2026-06-01",
                },
            ],
        }
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_exposure_observe" in codes
    assert "quality_growth" not in codes


def test_factor_exposure_lookup_uses_latest_report_date_when_as_of_ties():
    fund = _style_fund(stock_factors=[])
    fund = FundInput(
        **{
            **fund.__dict__,
            "factor_exposures": [
                {
                    "factor_code": "deep_value_weight",
                    "report_date": "2025-12-31",
                    "exposure_value": 0.80,
                    "coverage_weight": 0.80,
                    "as_of_date": "2026-06-23",
                },
                {
                    "factor_code": "factor_coverage_weight",
                    "report_date": "2025-12-31",
                    "exposure_value": 0.80,
                    "coverage_weight": 0.80,
                    "as_of_date": "2026-06-23",
                },
                {
                    "factor_code": "deep_value_weight",
                    "report_date": "2025-09-30",
                    "exposure_value": 0.20,
                    "coverage_weight": 0.20,
                    "as_of_date": "2026-06-23",
                },
                {
                    "factor_code": "factor_coverage_weight",
                    "report_date": "2025-09-30",
                    "exposure_value": 0.20,
                    "coverage_weight": 0.20,
                    "as_of_date": "2026-06-23",
                },
            ],
        }
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "deep_value" in codes
    assert "style_exposure_low_coverage" not in codes


def test_low_stock_position_emits_scope_not_applicable_not_low_coverage():
    fund = _style_fund(stock_factors=[])
    fund = FundInput(
        **{
            **fund.__dict__,
            "factor_exposures": [
                {
                    "factor_code": "factor_coverage_weight",
                    "exposure_value": 0.30,
                    "coverage_weight": 0.30,
                    "holding_total_weight": 0.30,
                    "as_of_date": "2026-06-23",
                },
            ],
        }
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_exposure_scope_not_applicable" in codes
    assert "style_exposure_low_coverage" not in codes
    ev = evidence_for(result, "style_exposure_scope_not_applicable")[0]
    assert ev.metric == "stock_holding_total_weight"


def test_raw_low_stock_position_emits_scope_not_applicable():
    fund = FundInput(
        fund_code="110022",
        fund_name="低仓位混合",
        fund_type="混合型-灵活",
        nav_returns=[0.001] * 30,
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.30},
        ],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        stock_factors=[{"stock_code": "600519", "pb": 8.1, "roe": 0.24}],
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.30,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_exposure_scope_not_applicable" in codes
    assert "style_exposure_low_coverage" not in codes


def test_deep_value_label_emits_from_precomputed_factor_exposures():
    fund = _style_fund(stock_factors=[])
    fund = FundInput(
        **{
            **fund.__dict__,
            "factor_exposures": [
                {
                    "factor_code": "deep_value_weight",
                    "exposure_value": 0.70,
                    "coverage_weight": 0.80,
                    "as_of_date": "2026-06-01",
                },
                {
                    "factor_code": "factor_coverage_weight",
                    "exposure_value": 0.80,
                    "coverage_weight": 0.80,
                    "as_of_date": "2026-06-01",
                },
            ],
        }
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "deep_value" in codes
    assert "style_unlabeled_stock_factors_missing" not in codes
    ev = evidence_for(result, "deep_value")[0]
    assert ev.source == "fund_factor_exposures"


def _style_history_fund(periods: list[tuple[str, float, float, float, float]]) -> FundInput:
    exposures = []
    for report_date, deep, quality, dividend, coverage in periods:
        for factor_code, value in (
            ("deep_value_weight", deep),
            ("quality_growth_weight", quality),
            ("dividend_steady_weight", dividend),
            ("factor_coverage_weight", coverage),
        ):
            exposures.append(
                {
                    "report_date": report_date,
                    "as_of_date": report_date,
                    "factor_code": factor_code,
                    "exposure_value": value,
                    "coverage_weight": coverage,
                }
            )
    fund = _style_fund(stock_factors=[])
    return FundInput(**{**fund.__dict__, "factor_exposures": exposures})


def test_style_drift_emits_observe_label_when_dominant_style_changes():
    fund = _style_history_fund(
        [
            ("2025-03-31", 0.62, 0.10, 0.08, 0.85),
            ("2025-06-30", 0.20, 0.58, 0.08, 0.86),
        ]
    )

    result = LabelEngine().evaluate(fund)

    by_code = {label.label_code: label for label in result.labels}
    assert by_code["style_drift"].status == "observe"
    assert by_code["style_recent_shift"].status == "observe"
    assert "style_stable" not in by_code
    assert evidence_for(result, "style_drift")[0].metric == "dominant_style_change"


def test_default_label_definitions_include_style_scope_boundary_label():
    from app.label_engine.engine import DEFAULT_LABEL_DEFINITIONS

    assert "style_exposure_scope_not_applicable" in {
        item["label_code"] for item in DEFAULT_LABEL_DEFINITIONS
    }


def test_recent_shift_requires_delta_threshold_when_dominant_style_changes():
    fund = _style_history_fund(
        [
            ("2025-03-31", 0.26, 0.10, 0.08, 0.85),
            ("2025-06-30", 0.24, 0.25, 0.08, 0.86),
        ]
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "style_drift" in codes
    assert "style_recent_shift" not in codes


def test_style_stable_emits_observe_label_when_dominant_style_persists():
    fund = _style_history_fund(
        [
            ("2025-03-31", 0.62, 0.10, 0.08, 0.85),
            ("2025-06-30", 0.66, 0.12, 0.08, 0.86),
        ]
    )

    result = LabelEngine().evaluate(fund)

    by_code = {label.label_code: label for label in result.labels}
    assert by_code["style_stable"].status == "observe"
    assert "style_drift" not in by_code
    assert evidence_for(result, "style_stable")[0].metric == "dominant_style"


def test_deep_value_label_emits_when_pb_and_valuation_percentile_meet_threshold():
    fund = _style_fund(
        stock_factors=[
            {"stock_code": "600519", "pb": 1.0, "valuation_percentile": 0.10},
            {"stock_code": "601398", "pb": 0.8, "valuation_percentile": 0.20},
        ]
    )
    result = LabelEngine().evaluate(fund)
    codes = label_codes(result)
    assert "deep_value" in codes
    ev = evidence_for(result, "deep_value")[0]
    assert ev.metric == "deep_value_weight"
    # 0.40 + 0.30 = 0.70 >= 0.6
    assert float(ev.value) >= 0.6


def test_quality_growth_label_emits_with_roe_and_revenue_growth():
    fund = _style_fund(
        stock_factors=[
            {"stock_code": "600519", "roe": 0.22, "revenue_growth": 0.18},
            {"stock_code": "601398", "roe": 0.20, "revenue_growth": 0.16},
        ]
    )
    result = LabelEngine().evaluate(fund)
    codes = label_codes(result)
    assert "quality_growth" in codes
    ev = evidence_for(result, "quality_growth")[0]
    assert float(ev.value) >= 0.5


def test_dividend_steady_label_emits_when_yield_high_enough():
    fund = _style_fund(
        stock_factors=[
            {"stock_code": "600519", "dividend_yield": 0.04},
            {"stock_code": "601398", "dividend_yield": 0.05},
        ]
    )
    result = LabelEngine().evaluate(fund)
    codes = label_codes(result)
    assert "dividend_steady" in codes


def test_no_style_label_when_thresholds_missed_falls_back_to_pending():
    fund = _style_fund(
        stock_factors=[
            # PB 不够低、ROE 也不达标、股息率也低
            {"stock_code": "600519", "pb": 4.0, "roe": 0.05, "dividend_yield": 0.01},
            {"stock_code": "601398", "pb": 3.0, "roe": 0.08, "dividend_yield": 0.015},
        ]
    )
    result = LabelEngine().evaluate(fund)
    codes = label_codes(result)
    assert "deep_value" not in codes
    assert "quality_growth" not in codes
    assert "dividend_steady" not in codes
    assert "style_pending_rule_definition" in codes


def _base_fund(**overrides) -> FundInput:
    """构造一个数据齐全的基线 fund，便于按需覆盖测某个标签。"""
    defaults = dict(
        fund_code="000999",
        fund_name="测试基金",
        fund_type="股票型",
        nav_returns=[0.001] * 60,
        stock_holdings=[{"stock_code": "600000", "weight": 0.08}] * 10,
        industry_allocations=[
            {"industry": "电子", "weight": 0.15},
            {"industry": "医药", "weight": 0.12},
            {"industry": "食品饮料", "weight": 0.10},
            {"industry": "银行", "weight": 0.08},
            {"industry": "汽车", "weight": 0.07},
        ],
        manager_tenure_years=2.0,
        management_fee=0.010,
        custody_fee=0.002,
        sales_service_fee=0.0,
        fund_size=20.0,
        equity_position=0.6,
    )
    defaults.update(overrides)
    return FundInput(**defaults)


def test_long_term_return_strong_and_volatility_low_for_steady_returns():
    # 252 个 +0.07% 日收益 → 年化≈19%、波动极低
    fund = _base_fund(nav_returns=[0.0007] * 252)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "long_term_return_strong" in codes
    assert "volatility_low" in codes
    ev = evidence_for(result, "long_term_return_strong")[0]
    assert ev.metric == "annualized_return_1y"


def test_return_window_insufficient_for_short_nav_history():
    # 仅 30 天净值，不足以支撑 1Y/3Y 窗口
    fund = _base_fund(nav_returns=[0.001] * 30)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "return_window_insufficient" in codes
    assert "long_term_return_strong" not in codes
    assert "volatility_low" not in codes
    ev = evidence_for(result, "return_window_insufficient")[0]
    assert ev.source == "nav_history"


def test_benchmark_data_missing_when_no_benchmark_returns():
    fund = _base_fund(nav_returns=[0.001] * 252)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "benchmark_data_missing" in codes
    assert "excess_return_strong" not in codes
    calculations = calculations_by_code(result)
    assert calculations["excess_return_strong"].state == "not_computed"
    assert calculations["excess_return_strong"].reason_code == "benchmark_data_missing"


def test_relative_benchmark_labels_emit_when_metrics_meet_thresholds():
    fund = _base_fund(
        nav_returns=[0.0020, -0.0005, 0.0015, 0.0001] * 63,
        benchmark_returns=[0.0005, -0.0015, 0.0008, -0.0012] * 63,
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "benchmark_data_missing" not in codes
    assert "excess_return_strong" in codes
    assert "information_ratio_high" in codes
    assert "alpha_positive" in codes
    feature_codes = {item.feature_code for item in result.features}
    assert "annualized_excess_return_1y" in feature_codes
    assert "tracking_error_1y" in feature_codes
    assert "beta_1y" in feature_codes


def test_industry_diversified_emitted_when_top1_low_and_count_enough():
    fund = _base_fund()

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "industry_diversified" in codes
    assert "industry_concentration_high" not in codes
    assert "industry_concentration_observe" not in codes


def test_industry_concentration_observe_for_mid_top1_weight():
    fund = _base_fund(
        industry_allocations=[
            {"industry": "电子", "weight": 0.50},
            {"industry": "医药", "weight": 0.20},
            {"industry": "银行", "weight": 0.10},
        ]
    )

    result = LabelEngine().evaluate(fund)

    by_code = {label.label_code: label for label in result.labels}
    assert "industry_concentration_observe" in by_code
    assert by_code["industry_concentration_observe"].status == "observe"
    assert "industry_concentration_high" not in by_code


def test_industry_concentration_high_requires_high_top1_weight():
    fund = _base_fund(
        industry_allocations=[
            {"industry": "电子", "weight": 0.65},
            {"industry": "医药", "weight": 0.20},
            {"industry": "银行", "weight": 0.10},
        ]
    )

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "industry_concentration_high" in codes
    assert "industry_concentration_observe" not in codes


def test_default_fee_low_threshold_is_tighter_after_calibration():
    borderline = _base_fund(management_fee=0.012, custody_fee=0.002)
    low_fee = _base_fund(management_fee=0.010, custody_fee=0.002)

    borderline_result = LabelEngine().evaluate(borderline)
    low_fee_result = LabelEngine().evaluate(low_fee)

    assert "fee_low" not in label_codes(borderline_result)
    assert "fee_low" in label_codes(low_fee_result)


def test_fund_size_small_label_for_tiny_fund():
    fund = _base_fund(fund_size=0.5)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "fund_size_small" in codes
    assert "fund_size_moderate" not in codes


def test_fund_size_moderate_label_for_mid_size_fund():
    fund = _base_fund(fund_size=20.0)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "fund_size_moderate" in codes
    assert "fund_size_small" not in codes


def test_fund_size_neither_label_for_large_fund():
    fund = _base_fund(fund_size=300.0)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "fund_size_small" not in codes
    assert "fund_size_moderate" not in codes


def test_fee_high_label_for_costly_fund():
    fund = _base_fund(management_fee=0.02, custody_fee=0.005, sales_service_fee=0.005)

    result = LabelEngine().evaluate(fund)

    codes = label_codes(result)
    assert "fee_high" in codes
    assert "fee_low" not in codes


# ---------- 进入检测 gate 行为 ----------

def test_equity_position_gate_rejects_low_equity_fund():
    """权益仓位低于 gate_min_equity_position 应直接判定 data_insufficient，
    与口播稿中「按类型圈范围，再用持仓和权益仓位验证」的口径一致。"""
    fund = _base_fund(equity_position=0.3)
    cfg = RuleConfig(gate_min_equity_position=0.6)

    result = LabelEngine(cfg).evaluate(fund)

    codes = label_codes(result)
    assert "data_insufficient" in codes
    assert "manual_review_required" in codes
    assert result.review_action == "manual_review"
    reasons = {item.metric for item in evidence_for(result, "data_insufficient")}
    assert any(":equity_position_below_min" in m for m in reasons)


def test_equity_position_gate_passes_when_position_meets_threshold():
    fund = _base_fund(equity_position=0.85)
    cfg = RuleConfig(gate_min_equity_position=0.6)

    result = LabelEngine(cfg).evaluate(fund)

    codes = label_codes(result)
    assert "data_sufficient" in codes
    assert "data_insufficient" not in codes


def test_return_window_gate_rejects_short_nav_history():
    """配置 gate_min_return_window=1y 时，样本不够支撑 1y 窗口应进入数据不足。"""
    fund = _base_fund(nav_returns=[0.001] * 30)
    cfg = RuleConfig(gate_min_return_window="1y")

    result = LabelEngine(cfg).evaluate(fund)

    codes = label_codes(result)
    assert "data_insufficient" in codes
    reasons = {item.metric for item in evidence_for(result, "data_insufficient")}
    assert any(m.startswith("return_window:") for m in reasons)


def test_holding_total_weight_gate_rejects_pass_through_gap():
    """最新一期股票持仓总权重过低时，说明底层穿透不足，不应强行输出正式标签。"""
    fund = _base_fund(
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.006},
            {"stock_code": "601318", "weight": 0.006},
        ],
        equity_position=0.012,
    )
    cfg = RuleConfig(gate_min_holding_total_weight=0.5)

    result = LabelEngine(cfg).evaluate(fund)

    codes = label_codes(result)
    assert "data_insufficient" in codes
    assert result.review_action == "manual_review"
    reasons = {item.metric for item in evidence_for(result, "data_insufficient")}
    assert "stock_holdings:stock_holdings_total_weight_low" in reasons


def test_gate_failure_downgrades_non_quality_labels_to_observe():
    """gate 失败时，原本会作为正式结论的标签必须降级为 status=observe。"""
    fund = _base_fund(equity_position=None)  # 触发 equity_position_missing
    cfg = RuleConfig()

    result = LabelEngine(cfg).evaluate(fund)

    by_code = {label.label_code: label for label in result.labels}
    assert by_code["data_insufficient"].status == "observe"
    # 非 data_quality/review 类标签必须降级
    if "industry_diversified" in by_code:
        assert by_code["industry_diversified"].status == "observe"
    if "manager_tenure_long" in by_code:
        # 默认 tenure 2.0 不会触发；这里仅在出现时校验
        assert by_code["manager_tenure_long"].status == "observe"


# ---------- 标签计算状态 ----------


def test_label_calculations_mark_triggered_labels():
    fund = _base_fund(
        nav_returns=[0.0007] * 252,
        manager_tenure_years=6.0,
    )

    result = LabelEngine().evaluate(fund)

    calculations = calculations_by_code(result)
    assert calculations["long_term_return_strong"].state == "triggered"
    assert calculations["long_term_return_strong"].reason_code == "threshold_met"
    assert calculations["manager_tenure_long"].state == "triggered"
    assert calculations["manager_tenure_long"].observed != ""


def test_label_calculations_mark_not_triggered_when_data_is_available():
    fund = _base_fund(
        nav_returns=[0.0001] * 252,
        manager_tenure_years=2.0,
        fund_size=300.0,
    )

    result = LabelEngine().evaluate(fund)

    calculations = calculations_by_code(result)
    assert calculations["manager_tenure_long"].state == "not_triggered"
    assert calculations["manager_tenure_long"].reason_code == "threshold_not_met"
    assert calculations["fund_size_moderate"].state == "not_triggered"
    assert calculations["fund_size_moderate"].threshold != ""


def test_label_calculations_mark_not_computed_when_prerequisite_data_is_missing():
    fund = _base_fund(
        nav_returns=[],
        manager_tenure_years=None,
        management_fee=None,
        custody_fee=None,
    )

    result = LabelEngine().evaluate(fund)

    calculations = calculations_by_code(result)
    assert calculations["long_term_return_strong"].state == "not_computed"
    assert calculations["long_term_return_strong"].reason_code == "return_window_insufficient"
    assert calculations["manager_tenure_long"].state == "not_computed"
    assert calculations["manager_tenure_long"].reason_code == "manager_missing"
    assert calculations["fee_low"].state == "not_computed"
    assert calculations["fee_low"].reason_code == "fee_structure_missing"


# ---------- 基金分类/分组 ----------


def test_classifies_active_equity_fund_into_candidate_pool():
    fund = _base_fund(
        nav_returns=[0.0007] * 252,
        manager_tenure_years=6.0,
        fund_size=20.0,
        stock_factors=[
            {"stock_code": "600000", "pb": 4.0, "roe": 0.05, "dividend_yield": 0.01},
        ],
    )

    result = LabelEngine().evaluate(fund)

    classifications = classifications_by_dimension(result)
    assert classifications["asset_class"].classification_code == "equity_related"
    assert classifications["management_style"].classification_code == "active"
    assert classifications["calculation_eligibility"].classification_code == "label_ready"
    assert classifications["style_clarity"].classification_code == "style_pending"

    groups = group_codes(result)
    assert "phase1_active_equity_scope" in groups
    assert "label_ready_pool" in groups
    assert "active_equity_candidate_pool" in groups


def test_classifies_index_fund_as_passive_tool_pool():
    fund = _base_fund(
        fund_name="沪深300ETF联接",
        fund_type="指数型-股票",
        manager_tenure_years=1.0,
    )

    result = LabelEngine().evaluate(fund)

    classifications = classifications_by_dimension(result)
    assert classifications["asset_class"].classification_code == "equity_related"
    assert classifications["management_style"].classification_code == "passive_index"
    groups = group_codes(result)
    assert "passive_tool_pool" in groups
    assert "active_equity_candidate_pool" not in groups


def test_groups_data_gap_and_style_factor_missing():
    fund = _base_fund(
        stock_holdings=[],
        stock_factors=[],
        equity_position=None,
    )

    result = LabelEngine().evaluate(fund)

    classifications = classifications_by_dimension(result)
    assert classifications["calculation_eligibility"].classification_code == "data_gap"
    assert classifications["style_clarity"].classification_code == "style_factor_missing"
    groups = group_codes(result)
    assert "data_gap_pool" in groups
    assert "style_factor_missing_pool" in groups


def test_style_labels_emit_style_groups():
    fund = _style_fund(
        stock_factors=[
            {"stock_code": "600519", "pb": 1.0, "valuation_percentile": 0.10},
            {"stock_code": "601398", "pb": 0.8, "valuation_percentile": 0.20},
        ]
    )

    result = LabelEngine().evaluate(fund)

    classifications = classifications_by_dimension(result)
    assert classifications["style_clarity"].classification_code == "style_clear"
    groups = group_codes(result)
    assert "style_factor_ready_pool" in groups
    assert "deep_value_group" in groups


def test_disabled_rules_filter_out_labels():
    """停用的规则不出现在 labels 里，也不影响 classification/group。"""
    fund = _style_fund(
        stock_factors=[
            {"stock_code": "600519", "pb": 1.0, "valuation_percentile": 0.10},
            {"stock_code": "601398", "pb": 0.8, "valuation_percentile": 0.20},
        ]
    )
    cfg = RuleConfig(disabled_rules=frozenset({"deep_value", "style_stable"}))
    result = LabelEngine(cfg).evaluate(fund)

    codes = label_codes(result)
    assert "deep_value" not in codes
    assert "style_stable" not in codes
    # data_quality 类标签不可停用
    assert "data_sufficient" in codes


def test_disabled_rules_persist_in_rule_config_json(tmp_path):
    """RuleConfig.from_file 能正确读取 disabled_rules JSON 数组。"""
    import json

    cfg_path = tmp_path / "rules.json"
    cfg_path.write_text(
        json.dumps({"disabled_rules": ["fee_low", "volatility_high"]}),
        encoding="utf-8",
    )
    cfg = RuleConfig.from_file(str(cfg_path))
    assert cfg.disabled_rules == frozenset({"fee_low", "volatility_high"})


def _fund_with_dividend_sector_exposures(
    financial: float,
    energy: float,
    consumer: float,
    coverage: float = 1.0,
) -> FundInput:
    return FundInput(
        fund_code="110022",
        fund_name="红利分流测试基金",
        fund_type="股票型",
        nav_returns=[0.001] * 30,
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.40},
            {"stock_code": "601398", "weight": 0.30},
        ],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        stock_factors=[],
        factor_exposures=[
            {"report_date": "2026-06-30", "factor_code": "factor_coverage_weight", "exposure_value": 0.90, "coverage_weight": 0.90, "holding_total_weight": 0.90},
            {"report_date": "2026-06-30", "factor_code": "dividend_steady_weight", "exposure_value": 0.70, "coverage_weight": 0.90, "holding_total_weight": 0.90},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_financial_ratio", "exposure_value": financial, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_energy_utility_ratio", "exposure_value": energy, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_consumer_ratio", "exposure_value": consumer, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_coverage", "exposure_value": coverage, "coverage_weight": coverage, "holding_total_weight": 0.70},
        ],
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )


def test_dividend_sector_split_emits_high_dividend_financial() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.50, energy=0.15, consumer=0.10)
    )

    codes = label_codes(result)
    assert "high_dividend_financial" in codes
    assert "dividend_steady" not in codes


def test_dividend_sector_split_emits_consumer_quality() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.05, energy=0.05, consumer=0.72)
    )

    codes = label_codes(result)
    assert "consumer_quality" in codes
    assert "dividend_steady" not in codes


def test_dividend_sector_split_keeps_broad_dividend_steady() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.25, energy=0.15, consumer=0.20)
    )

    codes = label_codes(result)
    assert "dividend_steady" in codes
    assert "high_dividend_financial" not in codes
    assert "consumer_quality" not in codes


def test_dividend_sector_split_observes_low_sector_coverage() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.80, energy=0.00, consumer=0.00, coverage=0.50)
    )

    codes = label_codes(result)
    assert "sector_mapping_insufficient" in codes
    assert "dividend_steady" in codes
    assert "high_dividend_financial" not in codes
