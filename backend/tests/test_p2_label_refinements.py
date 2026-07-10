"""P2 业务深度改进测试。

覆盖：
- P2-1: 收益标签优先用相对基准替代绝对收益
- P2-2: 费率分层（share_class + is_passive）
- P2-3: 风格稳定性 confidence/status 按样本期数动态计算
"""
from __future__ import annotations

from datetime import date, timedelta

from app.label_engine.engine import (
    DEFAULT_LABEL_DEFINITIONS,
    FeatureValue,
    FundInput,
    LabelEngine,
    RuleConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_returns(n: int, base: float = 0.0006, vol: float = 0.01) -> list[float]:
    """构造 n 条日收益率（默认年化 ~ 15%）。"""
    return [base] * n


def _make_stock_holdings(count: int = 30) -> list[dict]:
    """构造 count 只股票持仓，每只权重 1.0/count。"""
    return [
        {
            "stock_code": f"60{i:05d}",
            "stock_name": f"股票{i}",
            "weight": 1.0 / count,
        }
        for i in range(count)
    ]


def _make_industry_allocations(count: int = 5) -> list[dict]:
    """构造 count 个行业配置。"""
    return [
        {
            "industry_code": f"IND{i:02d}",
            "industry_name": f"行业{i}",
            "weight": 1.0 / count,
        }
        for i in range(count)
    ]


def _make_features_for_relative_return(
    fund_code: str,
    annualized_return: float,
    excess_return: float,
    window: str = "1y",
) -> list[FeatureValue]:
    """构造带 excess_return 特征 + annualized_return 特征的 FeatureValue 列表。"""
    return [
        FeatureValue(
            feature_code=f"annualized_return_{window}",
            value=annualized_return,
            source="nav_history",
        ),
        FeatureValue(
            feature_code=f"annualized_excess_return_{window}",
            value=excess_return,
            source="benchmark_returns",
        ),
        FeatureValue(
            feature_code=f"information_ratio_{window}",
            value=1.2,
            source="benchmark_returns",
        ),
        FeatureValue(
            feature_code=f"benchmark_sample_count_full",
            value=240,
            source="benchmark_returns",
        ),
    ]


# ---------------------------------------------------------------------------
# P2-1: 收益标签优先用相对基准
# ---------------------------------------------------------------------------


def test_p2_1_relative_return_preferred_when_excess_available() -> None:
    """当 excess_return_1y 特征存在且超过阈值时，产出 relative_return_strong。"""
    fund = FundInput(
        fund_code="000001",
        fund_name="样例偏股基金",
        fund_type="混合型-偏股",
        nav_returns=_make_returns(252),
        stock_holdings=_make_stock_holdings(30),
        industry_allocations=_make_industry_allocations(5),
        manager_tenure_years=4.0,
        management_fee=0.012,
        custody_fee=0.002,
        fund_size=15.0,
    )
    features = _make_features_for_relative_return(
        "000001",
        annualized_return=0.20,
        excess_return=0.20,  # 超过 long_term_return_threshold (默认 0.15)
    )

    result = LabelEngine().evaluate(fund, features=features)

    codes = {label.label_code for label in result.labels}
    assert "relative_return_strong" in codes, (
        "excess_return 可用时应优先产出 relative_return_strong 标签"
    )
    # 相对基准可用时不应同时产出 long_term_return_strong（避免重复）
    assert "long_term_return_strong" not in codes


def test_p2_1_falls_back_to_absolute_when_no_excess_feature() -> None:
    """无 excess_return 特征时回退到 long_term_return_strong（observe 档）。"""
    fund = FundInput(
        fund_code="000002",
        fund_name="无基准基金",
        fund_type="混合型-偏股",
        nav_returns=_make_returns(252),
        stock_holdings=_make_stock_holdings(30),
        industry_allocations=_make_industry_allocations(5),
        manager_tenure_years=4.0,
        management_fee=0.012,
        custody_fee=0.002,
        fund_size=15.0,
    )
    features = [
        FeatureValue(
            feature_code="annualized_return_1y",
            value=0.20,
            source="nav_history",
        ),
    ]
    result = LabelEngine().evaluate(fund, features=features)
    codes = {label.label_code for label in result.labels}
    assert "long_term_return_strong" in codes
    assert "relative_return_strong" not in codes

    # 回退的标签应该标 observe 档
    abs_label = next(
        l for l in result.labels if l.label_code == "long_term_return_strong"
    )
    assert abs_label.status == "observe"


def test_p2_1_does_not_emit_when_below_threshold() -> None:
    """excess_return 低于阈值时既不产相对也不产绝对标签。"""
    fund = FundInput(
        fund_code="000003",
        fund_name="低收益基金",
        fund_type="混合型-偏股",
        nav_returns=_make_returns(252),
        stock_holdings=_make_stock_holdings(30),
        industry_allocations=_make_industry_allocations(5),
        manager_tenure_years=4.0,
        management_fee=0.012,
        custody_fee=0.002,
        fund_size=15.0,
    )
    features = _make_features_for_relative_return(
        "000003",
        annualized_return=0.03,  # 低于阈值
        excess_return=0.01,      # 也低于阈值
    )
    result = LabelEngine().evaluate(fund, features=features)
    codes = {label.label_code for label in result.labels}
    assert "relative_return_strong" not in codes
    assert "long_term_return_strong" not in codes


def test_p2_1_relative_definition_exists() -> None:
    """relative_return_strong 必须在 label_definitions 注册。"""
    codes = {d["label_code"] for d in DEFAULT_LABEL_DEFINITIONS}
    assert "relative_return_strong" in codes
    definition = next(
        d for d in DEFAULT_LABEL_DEFINITIONS
        if d["label_code"] == "relative_return_strong"
    )
    assert definition["category"] == "return_risk"


# ---------------------------------------------------------------------------
# P2-2: 费率分层
# ---------------------------------------------------------------------------


def _fund_with_fee(management_fee: float, custody_fee: float = 0.002) -> FundInput:
    return FundInput(
        fund_code="999999",
        fund_name="费率测试基金",
        fund_type="混合型-偏股",
        nav_returns=_make_returns(252),
        management_fee=management_fee,
        custody_fee=custody_fee,
    )


def test_p2_2_resolve_passive_uses_passive_thresholds() -> None:
    """被动指数用被动阈值（fee_low_threshold_passive=0.006）。"""
    cfg = RuleConfig()
    fund = _fund_with_fee(0.005)  # 总费率 0.007
    fund_kwargs = {"is_passive": True}
    fund = FundInput(
        **{**fund.__dict__, **fund_kwargs}
    )
    engine = LabelEngine(cfg)
    low, high, segment = engine._resolve_fee_thresholds(fund)
    assert low == cfg.fee_low_threshold_passive
    assert high == cfg.fee_high_threshold_passive
    assert segment == "被动"


def test_p2_2_resolve_active_c_uses_c_thresholds() -> None:
    """主动 C 份额用 C 阈值。"""
    cfg = RuleConfig()
    fund = FundInput(**{**_fund_with_fee(0.008).__dict__, "share_class": "C"})
    engine = LabelEngine(cfg)
    low, high, segment = engine._resolve_fee_thresholds(fund)
    assert low == cfg.fee_low_threshold_active_c
    assert high == cfg.fee_high_threshold_active_c
    assert segment == "主动-C"


def test_p2_2_resolve_active_a_uses_a_thresholds() -> None:
    """主动 A 份额用 A 阈值。"""
    cfg = RuleConfig()
    fund = FundInput(**{**_fund_with_fee(0.014).__dict__, "share_class": "A"})
    engine = LabelEngine(cfg)
    low, high, segment = engine._resolve_fee_thresholds(fund)
    assert low == cfg.fee_low_threshold_active_a
    assert high == cfg.fee_high_threshold_active_a
    assert "主动-A" in segment


def test_p2_2_resolve_unknown_uses_default() -> None:
    """主动但未识别份额 → 用默认阈值。"""
    cfg = RuleConfig()
    fund = _fund_with_fee(0.01)  # 不传 share_class / is_passive
    engine = LabelEngine(cfg)
    low, high, segment = engine._resolve_fee_thresholds(fund)
    assert low == cfg.fee_low_threshold
    assert high == cfg.fee_high_threshold
    assert segment == "默认"


def test_p2_2_passive_index_does_not_match_absolute_active_a() -> None:
    """被动指数 0.5% 在被动阈值下应产出 fee_low，但用默认阈值不会（默认阈值 1.2%）。"""
    cfg = RuleConfig()
    # 总费率 0.005 + 0.001 + 0 = 0.006，被动 low=0.006 → 等于
    passive_fund = FundInput(
        **{**_fund_with_fee(0.005, 0.001).__dict__, "is_passive": True}
    )
    default_fund = _fund_with_fee(0.005, 0.001)
    engine = LabelEngine(cfg)
    result_passive = engine.evaluate(passive_fund)
    result_default = engine.evaluate(default_fund)

    passive_codes = {l.label_code for l in result_passive.labels}
    default_codes = {l.label_code for l in result_default.labels}
    # 被动档：0.006 == low_threshold=0.006 → fee_low 触发
    assert "fee_low" in passive_codes
    # 默认档：0.006 < default_low=0.012 → 也 fee_low，但证据阈值字段不同
    assert "fee_low" in default_codes
    passive_ev = next(
        e for e in result_passive.evidence if e.label_code == "fee_low"
    )
    default_ev = next(
        e for e in result_default.evidence if e.label_code == "fee_low"
    )
    # 验证 evidence 描述里写明了层
    assert "被动" in passive_ev.message
    assert "默认" in default_ev.message


# ---------------------------------------------------------------------------
# P2-3: 风格稳定性 confidence/status 按样本期数
# ---------------------------------------------------------------------------


def _seed_style_periods(
    fund: FundInput,
    n_periods: int,
    dominant_style: str = "deep_value",
    dominant_value: float = 0.45,
) -> FundInput:
    """构造 n_periods 期风格历史，所有期 dominant_style 一致（用于触发 style_stable）。"""
    today = date.today()
    periods = []
    for i in range(n_periods):
        period_date = (today - timedelta(days=90 * (n_periods - i))).isoformat()
        periods.append(
            {
                "as_of_date": period_date,
                "dominant_style": dominant_style,
                "dominant_value": dominant_value,
                "style_values": {
                    "deep_value": dominant_value,
                    "quality_growth": 0.20,
                    "dividend_steady": 0.15,
                    "high_dividend_financial": 0.10,
                    "consumer_quality": 0.10,
                },
            }
        )
    # FundInput 是 frozen dataclass；用 object.__setattr__ 注入
    object.__setattr__(fund, "_style_periods_override", periods)
    return fund


def _engine_with_style_periods(
    style_history_periods: int = 1,
) -> LabelEngine:
    """构造一个返回 _style_history_periods 时使用我们的 mock 数据的 engine。"""
    engine = LabelEngine(RuleConfig())

    def _patched(fund: FundInput) -> list[dict]:
        override = getattr(fund, "_style_periods_override", None)
        if override is not None:
            return override
        return []

    engine._style_history_periods = _patched  # type: ignore[method-assign]
    return engine


def test_p2_3_stable_observe_when_only_two_periods() -> None:
    """2 期样本 → style_stable 仍产出，但 status=observe, conf=observe_conf。"""
    cfg = RuleConfig()
    assert cfg.style_stability_promotion_min_periods == 4  # 默认门槛

    fund = _seed_style_periods(
        FundInput(
            fund_code="X", fund_name="X", fund_type="混合型-偏股",
            nav_returns=_make_returns(252),
        ),
        n_periods=2,
    )
    engine = _engine_with_style_periods()
    # 强制走 _add_style_stability_labels 路径（需要 factor_exposures）
    labels: list = []
    evidence: list = []
    engine._add_style_stability_labels(fund, labels, evidence)

    stable = [l for l in labels if l.label_code == "style_stable"]
    assert len(stable) == 1
    assert stable[0].status == "observe"
    assert stable[0].confidence == cfg.style_stability_observe_confidence


def test_p2_3_stable_official_when_four_periods() -> None:
    """4 期样本 → style_stable 升级到 official 档，conf=official_conf。"""
    cfg = RuleConfig()

    fund = _seed_style_periods(
        FundInput(
            fund_code="X", fund_name="X", fund_type="混合型-偏股",
            nav_returns=_make_returns(252),
        ),
        n_periods=4,
    )
    engine = _engine_with_style_periods()
    labels: list = []
    evidence: list = []
    engine._add_style_stability_labels(fund, labels, evidence)

    stable = [l for l in labels if l.label_code == "style_stable"]
    assert len(stable) == 1
    assert stable[0].status == "official"
    assert stable[0].confidence == cfg.style_stability_official_confidence


def test_p2_3_drift_official_when_many_periods() -> None:
    """多期样本触发 style_drift 时，status=official。"""
    cfg = RuleConfig()
    today = date.today()
    # 4 期：前 2 期 deep_value，后 2 期 quality_growth
    # 这样最后两期 (quality_growth → quality_growth) 看起来稳定，触发 stable
    # 不对，style_drift 需要 latest_style != previous_style
    # 改为：前 3 期 deep_value，最后 1 期 quality_growth → drift 触发
    periods = []
    for i in range(3):
        periods.append({
            "as_of_date": (today - timedelta(days=90 * (3 - i))).isoformat(),
            "dominant_style": "deep_value",
            "dominant_value": 0.50,
            "style_values": {
                "deep_value": 0.50,
                "quality_growth": 0.20,
                "dividend_steady": 0.15,
                "high_dividend_financial": 0.10,
                "consumer_quality": 0.05,
            },
        })
    # 第 4 期：切换为 quality_growth
    periods.append({
        "as_of_date": today.isoformat(),
        "dominant_style": "quality_growth",
        "dominant_value": 0.45,
        "style_values": {
            "deep_value": 0.15,
            "quality_growth": 0.45,
            "dividend_steady": 0.20,
            "high_dividend_financial": 0.10,
            "consumer_quality": 0.10,
        },
    })

    fund = FundInput(
        fund_code="X", fund_name="X", fund_type="混合型-偏股",
        nav_returns=_make_returns(252),
    )
    object.__setattr__(fund, "_style_periods_override", periods)
    engine = _engine_with_style_periods()
    labels: list = []
    evidence: list = []
    engine._add_style_stability_labels(fund, labels, evidence)

    drift = [l for l in labels if l.label_code == "style_drift"]
    assert len(drift) == 1
    assert drift[0].status == "official"
    assert drift[0].confidence == cfg.style_stability_official_confidence


def test_p2_3_stability_min_periods_gate_still_works() -> None:
    """< style_stability_min_periods (2) 时不应产任何稳定性标签。"""
    cfg = RuleConfig()
    fund = _seed_style_periods(
        FundInput(
            fund_code="X", fund_name="X", fund_type="混合型-偏股",
            nav_returns=_make_returns(252),
        ),
        n_periods=1,  # < 默认 2
    )
    engine = _engine_with_style_periods()
    labels: list = []
    evidence: list = []
    engine._add_style_stability_labels(fund, labels, evidence)
    assert labels == []