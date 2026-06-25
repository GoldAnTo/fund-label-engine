from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any


SUPPORTED_ACTIVE_EQUITY_TYPES = {
    "股票型",
    "混合型-偏股",
    "混合型-灵活",
    "指数型-股票",
}


# 收益风险窗口：交易日数量近似（252/年）。1m/3m 仅作观察特征，
# 1y/3y 满足最小样本时才允许触发正式标签。
# 每个窗口需要的最小有效样本（用于避免过短样本年化导致严重失真）。
RETURN_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("1m", 21, 15),
    ("3m", 63, 40),
    ("1y", 252, 180),
    ("3y", 756, 500),
)
ANNUALIZATION_FACTOR = 252
# 正式标签只能从下列窗口产出。
LABEL_RETURN_WINDOWS: tuple[str, ...] = ("1y", "3y")


@dataclass(frozen=True)
class RuleConfig:
    holding_concentration_threshold: float = 0.55
    manager_tenure_long_years: float = 5.0
    fee_low_threshold: float = 0.012
    fee_high_threshold: float = 0.025
    industry_concentration_threshold: float = 0.60
    industry_concentration_observe_threshold: float = 0.45
    industry_diversified_top1_max: float = 0.20
    industry_diversified_min_count: int = 5
    equity_position_high_threshold: float = 0.8
    volatility_high_threshold: float = 0.3
    volatility_low_threshold: float = 0.12
    drawdown_high_threshold: float = -0.2
    sharpe_high_threshold: float = 1.0
    long_term_return_threshold: float = 0.15
    excess_return_strong_threshold: float = 0.05
    information_ratio_high_threshold: float = 0.5
    tracking_error_high_threshold: float = 0.08
    alpha_positive_threshold: float = 0.03
    beta_high_threshold: float = 1.2
    beta_low_threshold: float = 0.8
    fund_size_small_threshold: float = 1.0
    fund_size_moderate_min: float = 5.0
    fund_size_moderate_max: float = 100.0
    # ---- Phase 5: 高级风格阈值 ----
    deep_value_pb_max: float = 1.5
    deep_value_valuation_pct_max: float = 0.3
    deep_value_weight_min: float = 0.6
    quality_growth_roe_min: float = 0.15
    quality_growth_revenue_growth_min: float = 0.15
    quality_growth_weight_min: float = 0.5
    dividend_steady_yield_min: float = 0.03
    dividend_steady_weight_min: float = 0.5
    # ---- P0: 数据充足性 gate（独立可配，便于生产逐步收紧；
    #          默认保持「只校验是否存在」的旧行为，避免破坏已有用例） ----
    gate_min_nav_samples: int = 1
    gate_min_stock_holding_count: int = 1
    gate_min_industry_count: int = 1
    # 持仓/行业报告期的最大允许「陈旧天数」。None 表示不校验。
    gate_max_holding_stale_days: int | None = None
    gate_max_industry_stale_days: int | None = None
    # data_as_of（YYYY-MM-DD）。配合上面两项使用；None 时不做日期校验。
    gate_data_as_of: str | None = None
    # 权益仓位最低阈值（用于「按类型圈范围，再用持仓和权益仓位验证」的口径）。
    # None 时只校验 equity_position 是否 not null，等同旧行为；
    # 配置为 0.0~1.0 之间的值时，equity_position 低于该值会被判定 gate 失败，
    # 触发 data_insufficient 子原因码 equity_position_below_min。
    gate_min_equity_position: float | None = None
    # 最新一期持仓总权重最小要求（用于识别 ETF 联接、FOF 等「穿透不到底层」
    # 的基金，避免在数据 gap 下打出不可信的权益/行业/集中度标签）。
    # None 时不校验（旧行为）；推荐值 0.5（即穿透后股票总权重 ≥ 50% 才算可信）。
    # 低于该值会输出 data_insufficient 子原因码 stock_holdings_total_weight_low。
    gate_min_holding_total_weight: float | None = None
    # 收益风险窗口的进入门槛。允许值：None / "1m" / "3m" / "1y" / "3y"。
    # None 表示不把 return window 纳入 gate（旧行为）；
    # 配置后，若 nav 样本不足以支撑该窗口，则 gate 失败，
    # 子原因码 return_window_insufficient。
    gate_min_return_window: str | None = None

    def thresholds_for(self, label_code: str) -> dict[str, Any]:
        """返回某个标签的阈值集合（label_code -> {指标: 阈值}）。

        用于把 RuleConfig 投影到 label_definitions.thresholds_json 上，
        前端和复核可以直接看到「这个标签判定时用的阈值」。
        """
        mapping: dict[str, dict[str, Any]] = {
            "holding_concentration_high": {
                "top_10_holding_weight_min": self.holding_concentration_threshold,
            },
            "manager_tenure_long": {
                "manager_tenure_years_min": self.manager_tenure_long_years,
            },
            "fee_low": {"total_annual_fee_max": self.fee_low_threshold},
            "fee_high": {"total_annual_fee_min": self.fee_high_threshold},
            "industry_concentration_high": {
                "industry_top1_weight_min": self.industry_concentration_threshold,
            },
            "industry_concentration_observe": {
                "industry_top1_weight_min": self.industry_concentration_observe_threshold,
                "industry_top1_weight_max_exclusive": self.industry_concentration_threshold,
            },
            "industry_diversified": {
                "industry_top1_weight_max": self.industry_diversified_top1_max,
                "industry_count_min": self.industry_diversified_min_count,
            },
            "equity_position_high": {
                "equity_position_min": self.equity_position_high_threshold,
            },
            "volatility_high": {
                "annualized_volatility_min": self.volatility_high_threshold,
                "window": "3y|1y",
            },
            "volatility_low": {
                "annualized_volatility_max": self.volatility_low_threshold,
                "window": "3y|1y",
            },
            "drawdown_high": {
                "max_drawdown_max": self.drawdown_high_threshold,
                "window": "3y|1y",
            },
            "sharpe_high": {
                "sharpe_ratio_min": self.sharpe_high_threshold,
                "window": "3y|1y",
            },
            "long_term_return_strong": {
                "annualized_return_min": self.long_term_return_threshold,
                "window": "3y|1y",
            },
            "excess_return_strong": {
                "annualized_excess_return_min": self.excess_return_strong_threshold,
                "window": "3y|1y",
            },
            "information_ratio_high": {
                "information_ratio_min": self.information_ratio_high_threshold,
                "window": "3y|1y",
            },
            "tracking_error_high": {
                "tracking_error_min": self.tracking_error_high_threshold,
                "window": "3y|1y",
            },
            "alpha_positive": {
                "alpha_min": self.alpha_positive_threshold,
                "window": "3y|1y",
            },
            "beta_high": {"beta_min": self.beta_high_threshold, "window": "3y|1y"},
            "beta_low": {"beta_max": self.beta_low_threshold, "window": "3y|1y"},
            "benchmark_data_missing": {
                "min_samples_1y": RETURN_WINDOWS[2][2],
                "min_samples_3y": RETURN_WINDOWS[3][2],
            },
            "fund_size_small": {"fund_size_max": self.fund_size_small_threshold},
            "fund_size_moderate": {
                "fund_size_min": self.fund_size_moderate_min,
                "fund_size_max": self.fund_size_moderate_max,
            },
            "return_window_insufficient": {
                "min_samples_1y": RETURN_WINDOWS[2][2],
                "min_samples_3y": RETURN_WINDOWS[3][2],
            },
            "data_sufficient": {
                "min_nav_samples": self.gate_min_nav_samples,
                "min_stock_holding_count": self.gate_min_stock_holding_count,
                "min_industry_count": self.gate_min_industry_count,
                "max_holding_stale_days": self.gate_max_holding_stale_days,
                "max_industry_stale_days": self.gate_max_industry_stale_days,
                "data_as_of": self.gate_data_as_of,
                "min_equity_position": self.gate_min_equity_position,
                "min_holding_total_weight": self.gate_min_holding_total_weight,
                "min_return_window": self.gate_min_return_window,
            },
            "data_insufficient": {
                "min_nav_samples": self.gate_min_nav_samples,
                "min_stock_holding_count": self.gate_min_stock_holding_count,
                "min_industry_count": self.gate_min_industry_count,
                "max_holding_stale_days": self.gate_max_holding_stale_days,
                "max_industry_stale_days": self.gate_max_industry_stale_days,
                "data_as_of": self.gate_data_as_of,
                "min_equity_position": self.gate_min_equity_position,
                "min_holding_total_weight": self.gate_min_holding_total_weight,
                "min_return_window": self.gate_min_return_window,
            },
            "deep_value": {
                "pb_weighted_max": self.deep_value_pb_max,
                "valuation_pct_weighted_max": self.deep_value_valuation_pct_max,
                "deep_value_weight_min": self.deep_value_weight_min,
            },
            "quality_growth": {
                "roe_weighted_min": self.quality_growth_roe_min,
                "revenue_growth_weighted_min": self.quality_growth_revenue_growth_min,
                "quality_growth_weight_min": self.quality_growth_weight_min,
            },
            "dividend_steady": {
                "dividend_yield_min": self.dividend_steady_yield_min,
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
            },
        }
        return mapping.get(label_code, {})


DEFAULT_LABEL_DEFINITIONS = (
    {
        "label_code": "data_sufficient",
        "label_name": "数据充足",
        "category": "data_quality",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "必要数据覆盖率达标，可以输出正式基础标签。",
    },
    {
        "label_code": "data_insufficient",
        "label_name": "数据不足",
        "category": "data_quality",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "缺少必要净值、持仓、经理、费率、规模或仓位数据。",
    },
    {
        "label_code": "manual_review_required",
        "label_name": "需人工复核",
        "category": "review",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "自动计算不能形成最终结论，需要人工确认。",
    },
    {
        "label_code": "holding_concentration_high",
        "label_name": "持仓集中度高",
        "category": "holding_structure",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "最近一期前十大股票持仓合计超过规则阈值。",
    },
    {
        "label_code": "manager_tenure_long",
        "label_name": "经理任期较长",
        "category": "manager",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "当前基金经理任期超过规则阈值。",
    },
    {
        "label_code": "fee_low",
        "label_name": "费率较低",
        "category": "fee_size",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "管理费、托管费和销售服务费合计不高于规则阈值。",
    },
    {
        "label_code": "industry_concentration_high",
        "label_name": "行业高度集中",
        "category": "holding_structure",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "最近一期第一大行业配置比例达到正式高集中阈值。",
    },
    {
        "label_code": "industry_concentration_observe",
        "label_name": "行业集中观察",
        "category": "holding_structure",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "最近一期第一大行业配置比例进入观察区间，但未达到正式高集中阈值。",
    },
    {
        "label_code": "equity_position_high",
        "label_name": "权益仓位高",
        "category": "holding_structure",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "最近一期权益仓位超过规则阈值。",
    },
    {
        "label_code": "volatility_high",
        "label_name": "波动较高",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "年化波动率超过规则阈值。",
    },
    {
        "label_code": "drawdown_high",
        "label_name": "回撤较大",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "区间最大回撤超过规则阈值。",
    },
    {
        "label_code": "sharpe_high",
        "label_name": "夏普较高",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "区间年化夏普达到规则阈值。",
    },
    {
        "label_code": "style_unlabeled_stock_factors_missing",
        "label_name": "风格未标注：缺少股票因子",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "有基金持仓但缺少股票因子，不能输出正式风格标签。",
    },
    {
        "label_code": "style_pending_rule_definition",
        "label_name": "风格待计算：规则尚未启用",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "股票因子已经存在，但高级风格标签规则尚未启用。",
    },
    {
        "label_code": "deep_value",
        "label_name": "深度价值",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "PB 加权低且估值分位数低的股票，持仓权重占比超阈值。",
    },
    {
        "label_code": "quality_growth",
        "label_name": "质量成长",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "ROE 和营收增速同时达到阈值的股票，持仓权重占比超阈值。",
    },
    {
        "label_code": "dividend_steady",
        "label_name": "红利稳健",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "高股息率股票的持仓权重占比超阈值。",
    },
    {
        "label_code": "long_term_return_strong",
        "label_name": "长期收益优秀",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "区间年化收益达到规则阈值。",
    },
    {
        "label_code": "excess_return_strong",
        "label_name": "超额收益较强",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "相对基准的区间年化超额收益达到规则阈值。",
    },
    {
        "label_code": "information_ratio_high",
        "label_name": "信息比率较高",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "相对基准的信息比率达到规则阈值。",
    },
    {
        "label_code": "tracking_error_high",
        "label_name": "跟踪误差较高",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "相对基准的年化跟踪误差超过规则阈值。",
    },
    {
        "label_code": "alpha_positive",
        "label_name": "Alpha 为正",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "按零无风险利率近似计算的 Alpha 达到规则阈值。",
    },
    {
        "label_code": "beta_high",
        "label_name": "Beta 较高",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "相对基准 Beta 高于规则阈值。",
    },
    {
        "label_code": "beta_low",
        "label_name": "Beta 较低",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "相对基准 Beta 低于规则阈值。",
    },
    {
        "label_code": "benchmark_data_missing",
        "label_name": "基准数据缺失",
        "category": "relative_benchmark",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "缺少可对齐的基准收益序列，不能输出正式相对基准标签。",
    },
    {
        "label_code": "return_window_insufficient",
        "label_name": "收益风险样本不足",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "净值样本不足以支撑 1Y/3Y 收益风险窗口，仅作为观察提示。",
    },
    {
        "label_code": "volatility_low",
        "label_name": "波动较低",
        "category": "return_risk",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "区间年化波动低于规则阈值。",
    },
    {
        "label_code": "industry_diversified",
        "label_name": "行业分散",
        "category": "holding_structure",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "第一大行业占比低且行业数量充足。",
    },
    {
        "label_code": "fund_size_moderate",
        "label_name": "基金规模适中",
        "category": "fee_size",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "基金规模在规则配置的合理区间内。",
    },
    {
        "label_code": "fund_size_small",
        "label_name": "规模偏小",
        "category": "fee_size",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "基金规模低于规则阈值，需关注流动性与持有人结构。",
    },
    {
        "label_code": "fee_high",
        "label_name": "费率偏高",
        "category": "fee_size",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "管理费、托管费和销售服务费合计高于规则阈值。",
    },
)


_LABEL_DEFINITION_BY_CODE = {
    item["label_code"]: item for item in DEFAULT_LABEL_DEFINITIONS
}
CALCULATION_LABEL_CODES = tuple(
    item["label_code"]
    for item in DEFAULT_LABEL_DEFINITIONS
    if item["category"] != "review"
)
_RISK_LABEL_FEATURES = {
    "volatility_high": "annualized_volatility",
    "volatility_low": "annualized_volatility",
    "drawdown_high": "max_drawdown",
    "sharpe_high": "sharpe_ratio",
    "long_term_return_strong": "annualized_return",
}
_RELATIVE_LABEL_FEATURES = {
    "excess_return_strong": "annualized_excess_return",
    "information_ratio_high": "information_ratio",
    "tracking_error_high": "tracking_error",
    "alpha_positive": "alpha",
    "beta_high": "beta",
    "beta_low": "beta",
}
_STYLE_LABELS = {"deep_value", "quality_growth", "dividend_steady"}
_STYLE_GROUP_BY_LABEL = {
    "deep_value": ("deep_value_group", "深度价值组"),
    "quality_growth": ("quality_growth_group", "质量成长组"),
    "dividend_steady": ("dividend_steady_group", "红利稳健组"),
}


@dataclass(frozen=True)
class FundInput:
    fund_code: str
    fund_name: str
    fund_type: str
    nav_returns: list[float] = field(default_factory=list)
    stock_holdings: list[dict[str, Any]] = field(default_factory=list)
    industry_allocations: list[dict[str, Any]] = field(default_factory=list)
    stock_factors: list[dict[str, Any]] = field(default_factory=list)
    benchmark_returns: list[float] = field(default_factory=list)
    benchmark_name: str | None = None
    manager_tenure_years: float | None = None
    management_fee: float | None = None
    custody_fee: float | None = None
    sales_service_fee: float | None = None
    fund_size: float | None = None
    equity_position: float | None = None
    holding_report_date: str | None = None
    industry_report_date: str | None = None


@dataclass(frozen=True)
class LabelResult:
    label_code: str
    label_name: str
    category: str
    confidence: float
    status: str = "active"


@dataclass(frozen=True)
class EvidenceItem:
    label_code: str
    metric: str
    value: float | str
    threshold: float | str
    source: str
    message: str


@dataclass(frozen=True)
class FeatureValue:
    feature_code: str
    value: float | str
    source: str


@dataclass(frozen=True)
class LabelCalculation:
    label_code: str
    label_name: str
    category: str
    state: str
    reason_code: str
    observed: float | str
    threshold: float | str
    source: str
    message: str


@dataclass(frozen=True)
class FundClassification:
    dimension: str
    classification_code: str
    classification_name: str
    confidence: float
    reason_code: str
    evidence: str
    source: str


@dataclass(frozen=True)
class FundGroup:
    group_code: str
    group_name: str
    group_type: str
    reason_code: str
    evidence: str
    source: str


@dataclass(frozen=True)
class EngineResult:
    fund_code: str
    labels: list[LabelResult]
    evidence: list[EvidenceItem]
    review_action: str
    coverage: dict[str, bool]
    features: list[FeatureValue]
    calculations: list[LabelCalculation]
    classifications: list[FundClassification]
    groups: list[FundGroup]
    fund_type: str = ""


class LabelEngine:
    def __init__(self, rule_config: RuleConfig | None = None) -> None:
        self._rule_config = rule_config or RuleConfig()

    def evaluate(self, fund: FundInput) -> EngineResult:
        labels: list[LabelResult] = []
        evidence: list[EvidenceItem] = []
        features = self._calculate_features(fund)
        coverage_details = self._coverage_details(fund)
        coverage = {field: detail["ok"] for field, detail in coverage_details.items()}
        coverage_ok = all(coverage.values())

        if not coverage_ok:
            missing = [name for name, ok in coverage.items() if not ok]
            labels.append(
                LabelResult(
                    label_code="data_insufficient",
                    label_name="数据不足",
                    category="data_quality",
                    confidence=1.0,
                    status="observe",
                )
            )
            labels.append(
                LabelResult(
                    label_code="manual_review_required",
                    label_name="需人工复核",
                    category="review",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="data_insufficient",
                    metric="missing_required_fields",
                    value=",".join(missing),
                    threshold="all_required_fields_present",
                    source="coverage_check",
                    message=f"缺少必要数据：{','.join(missing)}，不能生成正式标签。",
                )
            )
            # P0: 每个未通过的 gate 输出一条独立 evidence，metric 写子原因码，
            # 方便覆盖率报告聚合「拒绝原因 top」。
            for field, detail in coverage_details.items():
                if detail["ok"]:
                    continue
                evidence.append(
                    EvidenceItem(
                        label_code="data_insufficient",
                        metric=f"{field}:{detail['reason']}",
                        value=str(detail["observed"]),
                        threshold=str(detail["threshold"]),
                        source="coverage_gate",
                        message=(
                            f"字段 {field} 未通过 gate「{detail['reason']}」："
                            f"实际={detail['observed']}，阈值={detail['threshold']}。"
                        ),
                    )
                )
        else:
            labels.append(
                LabelResult(
                    label_code="data_sufficient",
                    label_name="数据充足",
                    category="data_quality",
                    confidence=0.95,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="data_sufficient",
                    metric="required_fields_present",
                    value="yes",
                    threshold="all_required_fields_present",
                    source="coverage_check",
                    message="基础净值、持仓、行业、经理、费率和规模数据均已提供。",
                )
            )

        self._add_holding_labels(fund, labels, evidence)
        self._add_industry_labels(fund, labels, evidence)
        self._add_equity_position_labels(fund, labels, evidence)
        self._add_risk_labels(features, labels, evidence)
        self._add_relative_benchmark_labels(features, labels, evidence)
        self._add_manager_labels(fund, labels, evidence)
        self._add_fee_labels(fund, labels, evidence)
        self._add_fund_size_labels(fund, labels, evidence)
        self._add_style_boundary_labels(fund, labels, evidence)

        if not coverage_ok:
            # gate 未通过时，所有非 data_quality/review 类标签强制降级为 observe，
            # 表达「在数据不足下作为观察项输出，不作为正式结论」。
            labels = [
                label
                if label.category in ("data_quality", "review")
                or label.status == "observe"
                else LabelResult(
                    label_code=label.label_code,
                    label_name=label.label_name,
                    category=label.category,
                    confidence=label.confidence,
                    status="observe",
                )
                for label in labels
            ]

        calculations = self._calculate_label_states(
            fund=fund,
            labels=labels,
            evidence=evidence,
            features=features,
            coverage_details=coverage_details,
        )
        classifications = self._classify_fund(
            fund=fund,
            labels=labels,
            calculations=calculations,
            coverage_ok=coverage_ok,
        )
        groups = self._group_fund(
            labels=labels,
            classifications=classifications,
            coverage_ok=coverage_ok,
        )

        return EngineResult(
            fund_code=fund.fund_code,
            labels=labels,
            evidence=evidence,
            review_action="observe" if coverage_ok else "manual_review",
            coverage=coverage,
            features=features,
            calculations=calculations,
            classifications=classifications,
            groups=groups,
            fund_type=fund.fund_type,
        )

    def _classify_fund(
        self,
        *,
        fund: FundInput,
        labels: list[LabelResult],
        calculations: list[LabelCalculation],
        coverage_ok: bool,
    ) -> list[FundClassification]:
        label_codes = {label.label_code for label in labels}
        calc_by_code = {item.label_code: item for item in calculations}
        classifications: list[FundClassification] = []

        def add(
            dimension: str,
            code: str,
            name: str,
            confidence: float,
            reason: str,
            evidence: str,
            source: str,
        ) -> None:
            classifications.append(
                FundClassification(
                    dimension=dimension,
                    classification_code=code,
                    classification_name=name,
                    confidence=confidence,
                    reason_code=reason,
                    evidence=evidence,
                    source=source,
                )
            )

        if fund.fund_type in SUPPORTED_ACTIVE_EQUITY_TYPES:
            add(
                "asset_class",
                "equity_related",
                "权益相关基金",
                0.95,
                "fund_type_supported",
                f"基金类型为 {fund.fund_type}，属于第一版权益相关范围。",
                "fund_profiles",
            )
        else:
            add(
                "asset_class",
                "unsupported_or_unknown",
                "暂未纳入第一版范围",
                0.9,
                "fund_type_unsupported",
                f"基金类型为 {fund.fund_type}，未纳入第一版标签范围。",
                "fund_profiles",
            )

        if self._is_passive_index_fund(fund):
            add(
                "management_style",
                "passive_index",
                "被动指数工具",
                0.9,
                "index_keyword_or_type",
                "基金类型或名称包含指数/ETF/联接等被动工具特征。",
                "fund_profiles",
            )
        else:
            add(
                "management_style",
                "active",
                "主动管理",
                0.75,
                "no_index_keyword_or_type",
                "基金类型和名称未命中指数/ETF/联接特征，按主动管理候选处理。",
                "fund_profiles",
            )

        if coverage_ok and "data_sufficient" in label_codes:
            add(
                "calculation_eligibility",
                "label_ready",
                "标签计算可用",
                0.95,
                "coverage_passed",
                "基础数据 gate 已通过，可以输出正式基础标签。",
                "coverage_check",
            )
        else:
            data_gap = calc_by_code.get("data_sufficient")
            add(
                "calculation_eligibility",
                "data_gap",
                "数据缺口",
                0.95,
                data_gap.reason_code if data_gap else "coverage_failed",
                data_gap.message if data_gap else "基础数据 gate 未通过。",
                data_gap.source if data_gap else "coverage_check",
            )

        style_codes = label_codes & _STYLE_LABELS
        if style_codes:
            add(
                "style_clarity",
                "style_clear",
                "风格已识别",
                0.8,
                "style_label_triggered",
                "已触发正式持仓风格标签：" + ",".join(sorted(style_codes)),
                "stock_factors",
            )
        elif (
            "style_pending_rule_definition" in label_codes
            or (
                calc_by_code.get("style_pending_rule_definition") is not None
                and calc_by_code["style_pending_rule_definition"].state == "triggered"
            )
        ):
            add(
                "style_clarity",
                "style_pending",
                "风格待确认",
                0.75,
                "style_threshold_not_met",
                "股票因子已接入，但尚未触发正式风格标签。",
                "stock_factors",
            )
        elif (
            "style_unlabeled_stock_factors_missing" in label_codes
            or not fund.stock_factors
        ):
            add(
                "style_clarity",
                "style_factor_missing",
                "缺少风格因子",
                0.95,
                "stock_factors_missing",
                "缺少股票因子，不能输出正式风格分组。",
                "stock_factors",
            )
        else:
            add(
                "style_clarity",
                "style_unknown",
                "风格未知",
                0.6,
                "style_not_resolved",
                "当前数据未形成明确风格结论。",
                "label_engine",
            )

        return classifications

    def _group_fund(
        self,
        *,
        labels: list[LabelResult],
        classifications: list[FundClassification],
        coverage_ok: bool,
    ) -> list[FundGroup]:
        label_codes = {label.label_code for label in labels}
        class_by_dim = {item.dimension: item for item in classifications}
        asset_class = class_by_dim.get("asset_class")
        management_style = class_by_dim.get("management_style")
        style_clarity = class_by_dim.get("style_clarity")
        groups: list[FundGroup] = []

        def add(
            code: str,
            name: str,
            group_type: str,
            reason: str,
            evidence: str,
            source: str,
        ) -> None:
            groups.append(
                FundGroup(
                    group_code=code,
                    group_name=name,
                    group_type=group_type,
                    reason_code=reason,
                    evidence=evidence,
                    source=source,
                )
            )

        if asset_class and asset_class.classification_code == "equity_related":
            add(
                "phase1_active_equity_scope",
                "第一版权益相关范围",
                "scope",
                asset_class.reason_code,
                asset_class.evidence,
                asset_class.source,
            )

        if coverage_ok:
            add(
                "label_ready_pool",
                "标签可计算池",
                "data_quality",
                "coverage_passed",
                "基础数据 gate 通过。",
                "coverage_check",
            )
        else:
            add(
                "data_gap_pool",
                "数据缺口池",
                "data_quality",
                "coverage_failed",
                "基础数据 gate 未通过，进入数据缺口池。",
                "coverage_check",
            )

        if management_style and management_style.classification_code == "passive_index":
            add(
                "passive_tool_pool",
                "被动指数工具池",
                "business",
                management_style.reason_code,
                management_style.evidence,
                management_style.source,
            )
        elif (
            management_style
            and management_style.classification_code == "active"
            and coverage_ok
            and "manager_tenure_long" in label_codes
            and "fund_size_small" not in label_codes
        ):
            add(
                "active_equity_candidate_pool",
                "主动权益候选池",
                "business",
                "active_equity_basic_gate_passed",
                "主动管理、数据充足、基金经理任期达标，且未触发规模偏小。",
                "label_engine",
            )

        if style_clarity:
            if style_clarity.classification_code in {"style_clear", "style_pending"}:
                add(
                    "style_factor_ready_pool",
                    "风格因子可用池",
                    "style",
                    style_clarity.reason_code,
                    style_clarity.evidence,
                    style_clarity.source,
                )
            elif style_clarity.classification_code == "style_factor_missing":
                add(
                    "style_factor_missing_pool",
                    "风格因子缺失池",
                    "style",
                    style_clarity.reason_code,
                    style_clarity.evidence,
                    style_clarity.source,
                )

        for label_code in sorted(label_codes & _STYLE_LABELS):
            group_code, group_name = _STYLE_GROUP_BY_LABEL[label_code]
            add(
                group_code,
                group_name,
                "style",
                "style_label_triggered",
                f"触发 {label_code} 标签，进入对应风格分组。",
                "stock_factors",
            )

        if {"long_term_return_strong", "drawdown_high"} <= label_codes:
            add(
                "high_return_high_drawdown_watch",
                "高收益高回撤观察池",
                "risk_watch",
                "return_and_drawdown_both_triggered",
                "同时触发长期收益优秀和回撤较大，需要和同类池比较风险收益。",
                "label_engine",
            )
        if "industry_concentration_high" in label_codes:
            add(
                "industry_concentration_watch",
                "行业集中观察池",
                "risk_watch",
                "industry_concentration_high",
                "触发行业高度集中，需要观察行业暴露风险。",
                "fund_industry_allocations",
            )
        elif "industry_concentration_observe" in label_codes:
            add(
                "industry_concentration_watch",
                "行业集中观察池",
                "risk_watch",
                "industry_concentration_observe",
                "第一大行业进入集中观察区间，需要持续跟踪行业暴露。",
                "fund_industry_allocations",
            )

        return groups

    @staticmethod
    def _is_passive_index_fund(fund: FundInput) -> bool:
        text = f"{fund.fund_type} {fund.fund_name}".upper()
        return any(keyword in text for keyword in ("指数", "ETF", "联接", "INDEX"))

    def _calculate_label_states(
        self,
        *,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
        features: list[FeatureValue],
        coverage_details: dict[str, dict[str, Any]],
    ) -> list[LabelCalculation]:
        emitted = {label.label_code: label for label in labels}
        first_evidence: dict[str, EvidenceItem] = {}
        for item in evidence:
            first_evidence.setdefault(item.label_code, item)
        feature_map = {item.feature_code: item for item in features}

        calculations: list[LabelCalculation] = []
        for label_code in CALCULATION_LABEL_CODES:
            definition = _LABEL_DEFINITION_BY_CODE[label_code]
            emitted_label = emitted.get(label_code)
            if emitted_label is not None:
                ev = first_evidence.get(label_code)
                calculations.append(
                    LabelCalculation(
                        label_code=label_code,
                        label_name=emitted_label.label_name,
                        category=emitted_label.category,
                        state="triggered",
                        reason_code=self._trigger_reason(label_code),
                        observed=ev.value if ev else "yes",
                        threshold=ev.threshold if ev else "emitted",
                        source=ev.source if ev else "label_engine",
                        message=ev.message if ev else f"{emitted_label.label_name} 已触发。",
                    )
                )
                continue

            state, reason, observed, threshold, source, message = (
                self._inactive_label_state(
                    label_code,
                    fund=fund,
                    feature_map=feature_map,
                    coverage_details=coverage_details,
                )
            )
            calculations.append(
                LabelCalculation(
                    label_code=label_code,
                    label_name=definition["label_name"],
                    category=definition["category"],
                    state=state,
                    reason_code=reason,
                    observed=observed,
                    threshold=threshold,
                    source=source,
                    message=message,
                )
            )
        return calculations

    @staticmethod
    def _trigger_reason(label_code: str) -> str:
        if label_code == "data_sufficient":
            return "coverage_passed"
        if label_code == "data_insufficient":
            return "coverage_failed"
        if label_code == "return_window_insufficient":
            return "return_window_insufficient"
        if label_code.startswith("style_"):
            return "boundary_triggered"
        return "threshold_met"

    def _inactive_label_state(
        self,
        label_code: str,
        *,
        fund: FundInput,
        feature_map: dict[str, FeatureValue],
        coverage_details: dict[str, dict[str, Any]],
    ) -> tuple[str, str, float | str, float | str, str, str]:
        thresholds = self._rule_config.thresholds_for(label_code)
        threshold: float | str = str(thresholds) if thresholds else "not_applicable"

        if label_code == "data_sufficient":
            failed = [
                f"{field}:{detail['reason']}"
                for field, detail in coverage_details.items()
                if not detail["ok"]
            ]
            return (
                "not_triggered",
                "coverage_failed",
                ",".join(failed),
                "all_required_fields_present",
                "coverage_check",
                "数据覆盖未通过，未触发数据充足。",
            )
        if label_code == "data_insufficient":
            return (
                "not_triggered",
                "coverage_passed",
                "all_required_fields_present",
                "any_required_field_missing",
                "coverage_check",
                "必要数据覆盖已通过，未触发数据不足。",
            )
        if label_code == "return_window_insufficient":
            chosen_window = self._chosen_return_window(feature_map)
            if chosen_window is not None:
                return (
                    "not_triggered",
                    "return_window_available",
                    chosen_window,
                    "1y_or_3y_window_required",
                    "nav_history",
                    "已有 1Y 或 3Y 收益风险窗口，未触发样本不足。",
                )

        if label_code in _RISK_LABEL_FEATURES:
            chosen_window = self._chosen_return_window(feature_map)
            if chosen_window is None:
                sample = feature_map.get("sample_count_full")
                return (
                    "not_computed",
                    "return_window_insufficient",
                    sample.value if sample else "0",
                    f"min(1y={RETURN_WINDOWS[2][2]}, 3y={RETURN_WINDOWS[3][2]})",
                    "nav_history",
                    "净值样本不足，不能计算正式收益风险标签。",
                )
            feature_code = f"{_RISK_LABEL_FEATURES[label_code]}_{chosen_window}"
            feature = feature_map.get(feature_code)
            return self._not_triggered_from_feature(
                label_code,
                feature,
                threshold,
                "收益风险指标未达到标签阈值。",
            )

        if label_code in _RELATIVE_LABEL_FEATURES:
            chosen_window = self._chosen_relative_window(feature_map)
            if chosen_window is None:
                sample = feature_map.get("benchmark_sample_count_full")
                return (
                    "not_computed",
                    "benchmark_data_missing",
                    sample.value if sample else "0",
                    f"min(1y={RETURN_WINDOWS[2][2]}, 3y={RETURN_WINDOWS[3][2]})",
                    "benchmark_returns",
                    "缺少可对齐的基准收益序列，不能计算正式相对基准标签。",
                )
            feature_code = f"{_RELATIVE_LABEL_FEATURES[label_code]}_{chosen_window}"
            feature = feature_map.get(feature_code)
            return self._not_triggered_from_feature(
                label_code,
                feature,
                threshold,
                "相对基准指标未达到标签阈值。",
            )

        if label_code == "benchmark_data_missing":
            chosen_window = self._chosen_relative_window(feature_map)
            if chosen_window is not None:
                return (
                    "not_triggered",
                    "benchmark_window_available",
                    chosen_window,
                    "1y_or_3y_relative_window_required",
                    "benchmark_returns",
                    "已有 1Y 或 3Y 相对基准窗口，未触发基准数据缺失。",
                )

        if label_code in {
            "holding_concentration_high",
            "style_unlabeled_stock_factors_missing",
            "style_pending_rule_definition",
        } | _STYLE_LABELS:
            stock_detail = coverage_details.get("stock_holdings")
            if stock_detail and not stock_detail["ok"]:
                return self._not_computed_from_gate("stock_holdings", stock_detail)
            if label_code in _STYLE_LABELS:
                if not fund.stock_factors:
                    return (
                        "not_computed",
                        "stock_factors_missing",
                        "0",
                        "stock_factors_required",
                        "stock_factors",
                        "缺少股票因子，不能计算正式风格标签。",
                    )
                return (
                    "not_triggered",
                    "threshold_not_met",
                    self._style_observed(label_code, feature_map),
                    threshold,
                    "stock_factors",
                    "股票因子存在，但风格暴露未达到标签阈值。",
                )
            if label_code == "style_unlabeled_stock_factors_missing":
                return (
                    "not_triggered",
                    "stock_factors_available",
                    len(fund.stock_factors),
                    "stock_factors_missing",
                    "stock_factors",
                    "股票因子已经存在，未触发缺少股票因子边界标签。",
                )
            if label_code == "style_pending_rule_definition":
                return (
                    "not_triggered",
                    "style_label_triggered_or_no_holdings",
                    "not_pending",
                    "no_style_label_triggered",
                    "stock_factors",
                    "已有风格标签触发，或没有进入风格待计算状态。",
                )

        gate_by_label = {
            "manager_tenure_long": "manager_tenure_years",
            "fee_low": "fee_structure",
            "fee_high": "fee_structure",
            "industry_concentration_high": "industry_allocations",
            "industry_concentration_observe": "industry_allocations",
            "industry_diversified": "industry_allocations",
            "equity_position_high": "equity_position",
            "fund_size_small": "fund_size",
            "fund_size_moderate": "fund_size",
        }
        feature_by_label = {
            "manager_tenure_long": "manager_tenure_years",
            "fee_low": "total_annual_fee",
            "fee_high": "total_annual_fee",
            "industry_concentration_high": "industry_top1_weight",
            "industry_concentration_observe": "industry_top1_weight",
            "industry_diversified": "industry_top1_weight",
            "equity_position_high": "equity_position",
            "fund_size_small": "fund_size",
            "fund_size_moderate": "fund_size",
            "holding_concentration_high": "top_10_holding_weight",
        }

        gate_field = gate_by_label.get(label_code)
        if gate_field:
            detail = coverage_details.get(gate_field)
            if detail and not detail["ok"]:
                return self._not_computed_from_gate(gate_field, detail)
        feature = feature_map.get(feature_by_label.get(label_code, ""))
        return self._not_triggered_from_feature(
            label_code,
            feature,
            threshold,
            "指标存在，但未达到标签阈值。",
        )

    @staticmethod
    def _chosen_return_window(feature_map: dict[str, FeatureValue]) -> str | None:
        for window in ("3y", "1y"):
            if f"annualized_return_{window}" in feature_map:
                return window
        return None

    @staticmethod
    def _chosen_relative_window(feature_map: dict[str, FeatureValue]) -> str | None:
        for window in ("3y", "1y"):
            if f"annualized_excess_return_{window}" in feature_map:
                return window
        return None

    @staticmethod
    def _not_computed_from_gate(
        field: str,
        detail: dict[str, Any],
    ) -> tuple[str, str, float | str, float | str, str, str]:
        return (
            "not_computed",
            str(detail["reason"]),
            str(detail["observed"]),
            str(detail["threshold"]),
            "coverage_gate",
            (
                f"字段 {field} 未通过 gate「{detail['reason']}」，"
                "不能计算依赖该字段的标签。"
            ),
        )

    @staticmethod
    def _not_triggered_from_feature(
        label_code: str,
        feature: FeatureValue | None,
        threshold: float | str,
        message: str,
    ) -> tuple[str, str, float | str, float | str, str, str]:
        return (
            "not_triggered",
            "threshold_not_met",
            feature.value if feature else "available_but_unset",
            threshold,
            feature.source if feature else "label_engine",
            f"{label_code}：{message}",
        )

    @staticmethod
    def _style_observed(
        label_code: str,
        feature_map: dict[str, FeatureValue],
    ) -> float | str:
        feature = feature_map.get(f"{label_code}_weight")
        return feature.value if feature else "style_weight_below_threshold"

    def _calculate_features(self, fund: FundInput) -> list[FeatureValue]:
        features: list[FeatureValue] = []

        returns = [float(item) for item in fund.nav_returns if item is not None]
        if returns:
            for window_name, window_size, min_samples in RETURN_WINDOWS:
                window_returns = returns[-window_size:]
                if len(window_returns) < min_samples:
                    continue
                self._append_window_features(features, window_name, window_returns)
            # 全窗口（用所有可用样本），便于排查；不参与正式标签判定
            self._append_window_features(features, "full", returns)

        benchmark_returns = [
            float(item) for item in fund.benchmark_returns if item is not None
        ]
        if returns and benchmark_returns:
            aligned_count = min(len(returns), len(benchmark_returns))
            aligned_returns = returns[-aligned_count:]
            aligned_benchmark = benchmark_returns[-aligned_count:]
            for window_name, window_size, min_samples in RETURN_WINDOWS:
                window_returns = aligned_returns[-window_size:]
                window_benchmark = aligned_benchmark[-window_size:]
                if len(window_returns) < min_samples or len(window_benchmark) < min_samples:
                    continue
                self._append_relative_benchmark_features(
                    features,
                    window_name,
                    window_returns,
                    window_benchmark,
                )
            self._append_relative_benchmark_features(
                features,
                "full",
                aligned_returns,
                aligned_benchmark,
            )

        top_10_weight = round(
            sum(float(item.get("weight", 0.0)) for item in fund.stock_holdings[:10]),
            6,
        )
        if fund.stock_holdings:
            features.append(
                FeatureValue(
                    "top_10_holding_weight",
                    top_10_weight,
                    "fund_stock_holdings",
                )
            )
            features.append(
                FeatureValue(
                    "stock_holding_count",
                    len(fund.stock_holdings),
                    "fund_stock_holdings",
                )
            )

        if fund.industry_allocations:
            industry_weights = [
                float(item.get("weight", 0.0)) for item in fund.industry_allocations
            ]
            features.append(
                FeatureValue(
                    "industry_top1_weight",
                    round(max(industry_weights), 6),
                    "fund_industry_allocations",
                )
            )
            features.append(
                FeatureValue(
                    "industry_top3_weight",
                    round(sum(sorted(industry_weights, reverse=True)[:3]), 6),
                    "fund_industry_allocations",
                )
            )
            features.append(
                FeatureValue(
                    "industry_count",
                    len(industry_weights),
                    "fund_industry_allocations",
                )
            )

        if fund.equity_position is not None:
            features.append(
                FeatureValue(
                    "equity_position",
                    round(float(fund.equity_position), 6),
                    "fund_positions",
                )
            )
        if fund.manager_tenure_years is not None:
            features.append(
                FeatureValue(
                    "manager_tenure_years",
                    round(float(fund.manager_tenure_years), 6),
                    "fund_manager_links",
                )
            )
        if fund.management_fee is not None and fund.custody_fee is not None:
            total_fee = (fund.management_fee or 0.0) + (fund.custody_fee or 0.0) + (
                fund.sales_service_fee or 0.0
            )
            features.append(
                FeatureValue(
                    "total_annual_fee",
                    round(total_fee, 6),
                    "fee_structures",
                )
            )
        if fund.fund_size is not None:
            features.append(
                FeatureValue("fund_size", round(float(fund.fund_size), 6), "fund_profiles")
            )

        return features

    @staticmethod
    def _append_relative_benchmark_features(
        features: list[FeatureValue],
        window: str,
        fund_returns: list[float],
        benchmark_returns: list[float],
    ) -> None:
        n = min(len(fund_returns), len(benchmark_returns))
        if n == 0:
            return
        fund_window = fund_returns[-n:]
        benchmark_window = benchmark_returns[-n:]
        active_returns = [f - b for f, b in zip(fund_window, benchmark_window)]
        active_cumulative = 1.0
        fund_cumulative = 1.0
        benchmark_cumulative = 1.0
        for fund_return, benchmark_return, active_return in zip(
            fund_window,
            benchmark_window,
            active_returns,
        ):
            fund_cumulative *= 1 + fund_return
            benchmark_cumulative *= 1 + benchmark_return
            active_cumulative *= 1 + active_return
        annualized_excess = (
            active_cumulative ** (ANNUALIZATION_FACTOR / n) - 1
            if active_cumulative > 0
            else -1.0
        )
        annualized_benchmark = (
            benchmark_cumulative ** (ANNUALIZATION_FACTOR / n) - 1
            if benchmark_cumulative > 0
            else -1.0
        )
        annualized_fund = (
            fund_cumulative ** (ANNUALIZATION_FACTOR / n) - 1
            if fund_cumulative > 0
            else -1.0
        )
        active_mean = sum(active_returns) / n
        tracking_variance = (
            sum((r - active_mean) ** 2 for r in active_returns) / (n - 1)
            if n > 1
            else 0.0
        )
        tracking_error = sqrt(tracking_variance) * sqrt(ANNUALIZATION_FACTOR)
        information_ratio = annualized_excess / tracking_error if tracking_error > 0 else 0.0

        fund_mean = sum(fund_window) / n
        benchmark_mean = sum(benchmark_window) / n
        benchmark_variance = (
            sum((r - benchmark_mean) ** 2 for r in benchmark_window) / (n - 1)
            if n > 1
            else 0.0
        )
        covariance = (
            sum(
                (fund_return - fund_mean) * (benchmark_return - benchmark_mean)
                for fund_return, benchmark_return in zip(fund_window, benchmark_window)
            )
            / (n - 1)
            if n > 1
            else 0.0
        )
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0
        alpha = annualized_fund - beta * annualized_benchmark

        for code, value in (
            ("benchmark_sample_count", n),
            ("annualized_benchmark_return", annualized_benchmark),
            ("annualized_excess_return", annualized_excess),
            ("tracking_error", tracking_error),
            ("information_ratio", information_ratio),
            ("beta", beta),
            ("alpha", alpha),
        ):
            features.append(
                FeatureValue(f"{code}_{window}", round(value, 6), "benchmark_returns")
            )

    @staticmethod
    def _max_drawdown(returns: list[float]) -> float:
        wealth = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for daily_return in returns:
            wealth *= 1 + daily_return
            peak = max(peak, wealth)
            if peak > 0:
                max_drawdown = min(max_drawdown, wealth / peak - 1)
        return max_drawdown

    @staticmethod
    def _append_window_features(
        features: list[FeatureValue],
        window: str,
        window_returns: list[float],
    ) -> None:
        """对单个窗口生成年化收益、年化波动、回撤、夏普等特征。"""
        n = len(window_returns)
        cumulative = 1.0
        for daily_return in window_returns:
            cumulative *= 1 + daily_return
        period_return = cumulative - 1
        annualized_return = (
            cumulative ** (ANNUALIZATION_FACTOR / n) - 1 if cumulative > 0 else -1.0
        )
        mean_return = sum(window_returns) / n
        variance = (
            sum((r - mean_return) ** 2 for r in window_returns) / (n - 1)
            if n > 1
            else 0.0
        )
        annualized_volatility = sqrt(variance) * sqrt(ANNUALIZATION_FACTOR)
        max_drawdown = LabelEngine._max_drawdown(window_returns)
        sharpe = (
            annualized_return / annualized_volatility
            if annualized_volatility > 0
            else 0.0
        )

        features.append(
            FeatureValue(f"period_return_{window}", round(period_return, 6), "nav_history")
        )
        features.append(
            FeatureValue(
                f"annualized_return_{window}", round(annualized_return, 6), "nav_history"
            )
        )
        features.append(
            FeatureValue(
                f"annualized_volatility_{window}",
                round(annualized_volatility, 6),
                "nav_history",
            )
        )
        features.append(
            FeatureValue(f"max_drawdown_{window}", round(max_drawdown, 6), "nav_history")
        )
        features.append(
            FeatureValue(f"sharpe_ratio_{window}", round(sharpe, 6), "nav_history")
        )
        features.append(
            FeatureValue(f"sample_count_{window}", n, "nav_history")
        )

    def _coverage(self, fund: FundInput) -> dict[str, bool]:
        """每个字段是否「存在且达到 gate 阈值」。

        返回的 dict 形状（field -> bool）保持稳定，前端、writer、reader、
        历史用例都依赖这个形状；细化的失败原因通过 evidence 输出。
        """
        details = self._coverage_details(fund)
        return {field: detail["ok"] for field, detail in details.items()}

    def _coverage_details(
        self, fund: FundInput
    ) -> dict[str, dict[str, Any]]:
        """逐字段返回 (ok, reason, observed, threshold)。

        reason=None 表示通过；否则是子原因码（用于 evidence/metric）。
        observed/threshold 用于 evidence 的 value/threshold 字段。
        """
        cfg = self._rule_config
        nav_len = len(fund.nav_returns or [])
        stock_len = len(fund.stock_holdings or [])
        stock_total_weight = round(
            sum(float(item.get("weight") or 0.0) for item in fund.stock_holdings),
            6,
        )
        industry_len = len(fund.industry_allocations or [])
        holding_stale = self._stale_days(fund.holding_report_date, cfg.gate_data_as_of)
        industry_stale = self._stale_days(fund.industry_report_date, cfg.gate_data_as_of)

        def detail(
            ok: bool, reason: str | None, observed: Any, threshold: Any
        ) -> dict[str, Any]:
            return {
                "ok": ok,
                "reason": reason,
                "observed": observed,
                "threshold": threshold,
            }

        out: dict[str, dict[str, Any]] = {}

        out["supported_fund_type"] = detail(
            fund.fund_type in SUPPORTED_ACTIVE_EQUITY_TYPES,
            None if fund.fund_type in SUPPORTED_ACTIVE_EQUITY_TYPES
            else "fund_type_unsupported",
            fund.fund_type,
            ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        )

        if nav_len == 0:
            out["nav_returns"] = detail(False, "nav_missing", 0, cfg.gate_min_nav_samples)
        elif nav_len < cfg.gate_min_nav_samples:
            out["nav_returns"] = detail(
                False, "nav_samples_below_min", nav_len, cfg.gate_min_nav_samples
            )
        else:
            out["nav_returns"] = detail(True, None, nav_len, cfg.gate_min_nav_samples)

        if stock_len == 0:
            out["stock_holdings"] = detail(
                False, "stock_holdings_missing", 0, cfg.gate_min_stock_holding_count
            )
        elif stock_len < cfg.gate_min_stock_holding_count:
            out["stock_holdings"] = detail(
                False,
                "stock_holdings_count_low",
                stock_len,
                cfg.gate_min_stock_holding_count,
            )
        elif (
            cfg.gate_min_holding_total_weight is not None
            and stock_total_weight < cfg.gate_min_holding_total_weight
        ):
            out["stock_holdings"] = detail(
                False,
                "stock_holdings_total_weight_low",
                stock_total_weight,
                cfg.gate_min_holding_total_weight,
            )
        elif (
            cfg.gate_max_holding_stale_days is not None
            and holding_stale is not None
            and holding_stale > cfg.gate_max_holding_stale_days
        ):
            out["stock_holdings"] = detail(
                False,
                "stock_holdings_stale",
                holding_stale,
                cfg.gate_max_holding_stale_days,
            )
        else:
            out["stock_holdings"] = detail(
                True, None, stock_len, cfg.gate_min_stock_holding_count
            )

        if industry_len == 0:
            out["industry_allocations"] = detail(
                False, "industry_missing", 0, cfg.gate_min_industry_count
            )
        elif industry_len < cfg.gate_min_industry_count:
            out["industry_allocations"] = detail(
                False,
                "industry_count_low",
                industry_len,
                cfg.gate_min_industry_count,
            )
        elif (
            cfg.gate_max_industry_stale_days is not None
            and industry_stale is not None
            and industry_stale > cfg.gate_max_industry_stale_days
        ):
            out["industry_allocations"] = detail(
                False,
                "industry_stale",
                industry_stale,
                cfg.gate_max_industry_stale_days,
            )
        else:
            out["industry_allocations"] = detail(
                True, None, industry_len, cfg.gate_min_industry_count
            )

        out["manager_tenure_years"] = detail(
            fund.manager_tenure_years is not None,
            None if fund.manager_tenure_years is not None else "manager_missing",
            fund.manager_tenure_years if fund.manager_tenure_years is not None else "null",
            "not_null",
        )

        fee_ok = fund.management_fee is not None and fund.custody_fee is not None
        out["fee_structure"] = detail(
            fee_ok,
            None if fee_ok else "fee_structure_missing",
            f"management_fee={fund.management_fee},custody_fee={fund.custody_fee}",
            "management_fee&custody_fee both not_null",
        )

        out["fund_size"] = detail(
            fund.fund_size is not None,
            None if fund.fund_size is not None else "fund_size_missing",
            fund.fund_size if fund.fund_size is not None else "null",
            "not_null",
        )

        out["equity_position"] = detail(
            fund.equity_position is not None
            and (
                cfg.gate_min_equity_position is None
                or float(fund.equity_position) >= cfg.gate_min_equity_position
            ),
            None
            if fund.equity_position is not None
            and (
                cfg.gate_min_equity_position is None
                or float(fund.equity_position) >= cfg.gate_min_equity_position
            )
            else (
                "equity_position_missing"
                if fund.equity_position is None
                else "equity_position_below_min"
            ),
            fund.equity_position if fund.equity_position is not None else "null",
            cfg.gate_min_equity_position
            if cfg.gate_min_equity_position is not None
            else "not_null",
        )

        # return_window gate：是否能产出至少一个 cfg.gate_min_return_window 窗口
        if cfg.gate_min_return_window is None:
            # 不参与 gate；out 中不写入该字段，避免影响历史 coverage 形状
            pass
        else:
            window_min = {name: min_s for name, _, min_s in RETURN_WINDOWS}
            required = cfg.gate_min_return_window
            if required not in window_min:
                # 配置非法时也输出一条失败原因，便于排查配置
                out["return_window"] = detail(
                    False,
                    "return_window_config_invalid",
                    required,
                    "/".join(window_min.keys()),
                )
            else:
                min_samples = window_min[required]
                ok = nav_len >= min_samples
                out["return_window"] = detail(
                    ok,
                    None if ok else "return_window_insufficient",
                    nav_len,
                    f"{required}>={min_samples}",
                )

        return out

    @staticmethod
    def _stale_days(report_date: str | None, as_of: str | None) -> int | None:
        """计算 report_date 距离 as_of 的天数（report_date 越旧值越大）。

        任一为空返回 None，表示无法校验，不参与 gate 判定。
        """
        if not report_date or not as_of:
            return None
        from datetime import date

        try:
            r = date.fromisoformat(str(report_date)[:10])
            a = date.fromisoformat(str(as_of)[:10])
        except ValueError:
            return None
        return (a - r).days

    def _add_holding_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        top_10_weight = round(
            sum(float(item.get("weight", 0.0)) for item in fund.stock_holdings[:10]),
            4,
        )
        threshold = self._rule_config.holding_concentration_threshold
        if top_10_weight >= threshold:
            labels.append(
                LabelResult(
                    label_code="holding_concentration_high",
                    label_name="持仓集中度高",
                    category="holding_structure",
                    confidence=0.9,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="holding_concentration_high",
                    metric="top_10_holding_weight",
                    value=top_10_weight,
                    threshold=threshold,
                    source="fund_stock_holdings",
                    message=(
                        f"前十大持仓合计 {top_10_weight:.2%}，"
                        f"达到持仓集中度高阈值 {threshold:.2%}。"
                    ),
                )
            )

    def _add_industry_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if not fund.industry_allocations:
            return
        weights = [float(item.get("weight", 0.0)) for item in fund.industry_allocations]
        top1 = round(max(weights), 4)
        high_threshold = self._rule_config.industry_concentration_threshold
        observe_threshold = self._rule_config.industry_concentration_observe_threshold
        if top1 >= high_threshold:
            labels.append(
                LabelResult(
                    label_code="industry_concentration_high",
                    label_name="行业高度集中",
                    category="holding_structure",
                    confidence=0.85,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="industry_concentration_high",
                    metric="industry_top1_weight",
                    value=top1,
                    threshold=high_threshold,
                    source="fund_industry_allocations",
                    message=f"第一大行业占比 {top1:.2%}，达到 {high_threshold:.2%} 行业高度集中阈值。",
                )
            )
        elif top1 >= observe_threshold:
            labels.append(
                LabelResult(
                    label_code="industry_concentration_observe",
                    label_name="行业集中观察",
                    category="holding_structure",
                    confidence=0.75,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="industry_concentration_observe",
                    metric="industry_top1_weight",
                    value=top1,
                    threshold=f"{observe_threshold:.2%}~{high_threshold:.2%}",
                    source="fund_industry_allocations",
                    message=(
                        f"第一大行业占比 {top1:.2%}，进入 {observe_threshold:.2%}~"
                        f"{high_threshold:.2%} 行业集中观察区间。"
                    ),
                )
            )

        top1_max = self._rule_config.industry_diversified_top1_max
        min_count = self._rule_config.industry_diversified_min_count
        if top1 < top1_max and len(weights) >= min_count:
            labels.append(
                LabelResult(
                    label_code="industry_diversified",
                    label_name="行业分散",
                    category="holding_structure",
                    confidence=0.8,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="industry_diversified",
                    metric="industry_top1_weight_and_count",
                    value=f"top1={top1:.2%}, count={len(weights)}",
                    threshold=f"top1<{top1_max:.2%}, count>={min_count}",
                    source="fund_industry_allocations",
                    message=(
                        f"第一大行业占比 {top1:.2%} 低于 {top1_max:.2%}，"
                        f"且覆盖 {len(weights)} 个行业（≥{min_count}），行业分散。"
                    ),
                )
            )

    def _add_equity_position_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if fund.equity_position is None:
            return
        equity_position = round(float(fund.equity_position), 4)
        threshold = self._rule_config.equity_position_high_threshold
        if equity_position >= threshold:
            labels.append(
                LabelResult(
                    label_code="equity_position_high",
                    label_name="权益仓位高",
                    category="holding_structure",
                    confidence=0.85,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="equity_position_high",
                    metric="equity_position",
                    value=equity_position,
                    threshold=threshold,
                    source="fund_positions",
                    message=f"权益仓位 {equity_position:.2%}，达到 {threshold:.2%} 权益仓位阈值。",
                )
            )

    def _add_risk_labels(
        self,
        features: list[FeatureValue],
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        feature_map = {item.feature_code: item for item in features}

        # 选择有效窗口：3Y 优先，其次 1Y。两者都没有 -> 出观察边界标签
        chosen_window: str | None = None
        for window in ("3y", "1y"):
            if f"annualized_return_{window}" in feature_map:
                chosen_window = window
                break

        if chosen_window is None:
            labels.append(
                LabelResult(
                    label_code="return_window_insufficient",
                    label_name="收益风险样本不足",
                    category="return_risk",
                    confidence=1.0,
                    status="observe",
                )
            )
            full_sample = feature_map.get("sample_count_full")
            evidence.append(
                EvidenceItem(
                    label_code="return_window_insufficient",
                    metric="sample_count_full",
                    value=full_sample.value if full_sample else "0",
                    threshold=f"min(1y={RETURN_WINDOWS[2][2]}, 3y={RETURN_WINDOWS[3][2]})",
                    source="nav_history",
                    message=(
                        "净值样本不足以支撑 1Y 或 3Y 收益风险窗口，"
                        "暂不输出正式收益风险标签。"
                    ),
                )
            )
            return

        vol_key = f"annualized_volatility_{chosen_window}"
        dd_key = f"max_drawdown_{chosen_window}"
        sharpe_key = f"sharpe_ratio_{chosen_window}"
        ret_key = f"annualized_return_{chosen_window}"

        volatility = feature_map.get(vol_key)
        if (
            volatility
            and float(volatility.value) >= self._rule_config.volatility_high_threshold
        ):
            labels.append(
                LabelResult(
                    label_code="volatility_high",
                    label_name="波动较高",
                    category="return_risk",
                    confidence=0.75,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="volatility_high",
                    metric=vol_key,
                    value=volatility.value,
                    threshold=self._rule_config.volatility_high_threshold,
                    source=volatility.source,
                    message=(
                        f"{chosen_window.upper()} 年化波动率 {float(volatility.value):.2%}，"
                        f"高于 {self._rule_config.volatility_high_threshold:.2%}。"
                    ),
                )
            )

        drawdown = feature_map.get(dd_key)
        if drawdown and float(drawdown.value) <= self._rule_config.drawdown_high_threshold:
            labels.append(
                LabelResult(
                    label_code="drawdown_high",
                    label_name="回撤较大",
                    category="return_risk",
                    confidence=0.75,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="drawdown_high",
                    metric=dd_key,
                    value=drawdown.value,
                    threshold=self._rule_config.drawdown_high_threshold,
                    source=drawdown.source,
                    message=(
                        f"{chosen_window.upper()} 最大回撤 {float(drawdown.value):.2%}，"
                        f"低于 {self._rule_config.drawdown_high_threshold:.2%}。"
                    ),
                )
            )

        sharpe = feature_map.get(sharpe_key)
        if sharpe and float(sharpe.value) >= self._rule_config.sharpe_high_threshold:
            labels.append(
                LabelResult(
                    label_code="sharpe_high",
                    label_name="夏普较高",
                    category="return_risk",
                    confidence=0.75,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="sharpe_high",
                    metric=sharpe_key,
                    value=sharpe.value,
                    threshold=self._rule_config.sharpe_high_threshold,
                    source=sharpe.source,
                    message=(
                        f"{chosen_window.upper()} 夏普 {float(sharpe.value):.2f}，"
                        f"达到 {self._rule_config.sharpe_high_threshold:.2f}。"
                    ),
                )
            )

        annual_return = feature_map.get(ret_key)
        if (
            annual_return
            and float(annual_return.value) >= self._rule_config.long_term_return_threshold
        ):
            labels.append(
                LabelResult(
                    label_code="long_term_return_strong",
                    label_name="长期收益优秀",
                    category="return_risk",
                    confidence=0.8,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="long_term_return_strong",
                    metric=ret_key,
                    value=annual_return.value,
                    threshold=self._rule_config.long_term_return_threshold,
                    source=annual_return.source,
                    message=(
                        f"{chosen_window.upper()} 年化收益率 {float(annual_return.value):.2%}，"
                        f"达到 {self._rule_config.long_term_return_threshold:.2%} 阈值。"
                    ),
                )
            )

        if volatility and float(volatility.value) <= self._rule_config.volatility_low_threshold:
            labels.append(
                LabelResult(
                    label_code="volatility_low",
                    label_name="波动较低",
                    category="return_risk",
                    confidence=0.7,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="volatility_low",
                    metric=vol_key,
                    value=volatility.value,
                    threshold=self._rule_config.volatility_low_threshold,
                    source=volatility.source,
                    message=(
                        f"{chosen_window.upper()} 年化波动率 {float(volatility.value):.2%}，"
                        f"不高于 {self._rule_config.volatility_low_threshold:.2%}。"
                    ),
                )
            )

    def _add_relative_benchmark_labels(
        self,
        features: list[FeatureValue],
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        feature_map = {item.feature_code: item for item in features}
        chosen_window = self._chosen_relative_window(feature_map)
        if chosen_window is None:
            sample = feature_map.get("benchmark_sample_count_full")
            labels.append(
                LabelResult(
                    label_code="benchmark_data_missing",
                    label_name="基准数据缺失",
                    category="relative_benchmark",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="benchmark_data_missing",
                    metric="benchmark_sample_count",
                    value=sample.value if sample else 0,
                    threshold=f"min(1y={RETURN_WINDOWS[2][2]}, 3y={RETURN_WINDOWS[3][2]})",
                    source="benchmark_returns",
                    message="缺少可对齐的 1Y/3Y 基准收益序列，暂不输出正式相对基准标签。",
                )
            )
            return

        checks = (
            (
                "excess_return_strong",
                "超额收益较强",
                "annualized_excess_return",
                self._rule_config.excess_return_strong_threshold,
                lambda value, threshold: value >= threshold,
                "年化超额收益",
            ),
            (
                "information_ratio_high",
                "信息比率较高",
                "information_ratio",
                self._rule_config.information_ratio_high_threshold,
                lambda value, threshold: value >= threshold,
                "信息比率",
            ),
            (
                "tracking_error_high",
                "跟踪误差较高",
                "tracking_error",
                self._rule_config.tracking_error_high_threshold,
                lambda value, threshold: value >= threshold,
                "年化跟踪误差",
            ),
            (
                "alpha_positive",
                "Alpha 为正",
                "alpha",
                self._rule_config.alpha_positive_threshold,
                lambda value, threshold: value >= threshold,
                "Alpha",
            ),
            (
                "beta_high",
                "Beta 较高",
                "beta",
                self._rule_config.beta_high_threshold,
                lambda value, threshold: value >= threshold,
                "Beta",
            ),
            (
                "beta_low",
                "Beta 较低",
                "beta",
                self._rule_config.beta_low_threshold,
                lambda value, threshold: value <= threshold,
                "Beta",
            ),
        )
        for label_code, label_name, metric_prefix, threshold, predicate, display_name in checks:
            feature = feature_map.get(f"{metric_prefix}_{chosen_window}")
            if feature is None:
                continue
            value = float(feature.value)
            if not predicate(value, threshold):
                continue
            labels.append(
                LabelResult(
                    label_code=label_code,
                    label_name=label_name,
                    category="relative_benchmark",
                    confidence=0.75,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code=label_code,
                    metric=f"{metric_prefix}_{chosen_window}",
                    value=feature.value,
                    threshold=threshold,
                    source="benchmark_returns",
                    message=(
                        f"{chosen_window.upper()} {display_name} {value:.2%}，"
                        f"达到相对基准阈值 {threshold:.2%}。"
                    ),
                )
            )

    def _add_manager_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        tenure = fund.manager_tenure_years or 0.0
        threshold = self._rule_config.manager_tenure_long_years
        if tenure >= threshold:
            labels.append(
                LabelResult(
                    label_code="manager_tenure_long",
                    label_name="经理任期较长",
                    category="manager",
                    confidence=0.9,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="manager_tenure_long",
                    metric="manager_tenure_years",
                    value=round(tenure, 2),
                    threshold=threshold,
                    source="fund_manager_links",
                    message=f"当前基金经理任期 {tenure:.1f} 年，达到 {threshold:.1f} 年稳定性阈值。",
                )
            )

    def _add_fee_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if fund.management_fee is None or fund.custody_fee is None:
            return
        total_fee = (fund.management_fee or 0.0) + (fund.custody_fee or 0.0) + (
            fund.sales_service_fee or 0.0
        )
        total_fee = round(total_fee, 4)
        low_threshold = self._rule_config.fee_low_threshold
        high_threshold = self._rule_config.fee_high_threshold
        if total_fee <= low_threshold:
            labels.append(
                LabelResult(
                    label_code="fee_low",
                    label_name="费率较低",
                    category="fee_size",
                    confidence=0.85,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="fee_low",
                    metric="total_annual_fee",
                    value=total_fee,
                    threshold=low_threshold,
                    source="fee_structures",
                    message=f"管理费、托管费和销售服务费合计 {total_fee:.2%}，不高于 {low_threshold:.2%}。",
                )
            )
        elif total_fee > high_threshold:
            labels.append(
                LabelResult(
                    label_code="fee_high",
                    label_name="费率偏高",
                    category="fee_size",
                    confidence=0.85,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="fee_high",
                    metric="total_annual_fee",
                    value=total_fee,
                    threshold=high_threshold,
                    source="fee_structures",
                    message=f"管理费、托管费和销售服务费合计 {total_fee:.2%}，高于 {high_threshold:.2%}。",
                )
            )

    def _add_fund_size_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if fund.fund_size is None:
            return
        size = round(float(fund.fund_size), 4)
        small_threshold = self._rule_config.fund_size_small_threshold
        moderate_min = self._rule_config.fund_size_moderate_min
        moderate_max = self._rule_config.fund_size_moderate_max
        if size < small_threshold:
            labels.append(
                LabelResult(
                    label_code="fund_size_small",
                    label_name="规模偏小",
                    category="fee_size",
                    confidence=0.8,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="fund_size_small",
                    metric="fund_size",
                    value=size,
                    threshold=small_threshold,
                    source="fund_profiles",
                    message=f"基金规模 {size:.2f} 亿元，低于 {small_threshold:.2f} 亿元。",
                )
            )
        elif moderate_min <= size <= moderate_max:
            labels.append(
                LabelResult(
                    label_code="fund_size_moderate",
                    label_name="基金规模适中",
                    category="fee_size",
                    confidence=0.8,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="fund_size_moderate",
                    metric="fund_size",
                    value=size,
                    threshold=f"{moderate_min:.2f}~{moderate_max:.2f} 亿元",
                    source="fund_profiles",
                    message=(
                        f"基金规模 {size:.2f} 亿元，处于 "
                        f"{moderate_min:.2f}~{moderate_max:.2f} 亿元合理区间。"
                    ),
                )
            )

    def _add_style_boundary_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if not fund.stock_holdings:
            return
        if not fund.stock_factors:
            labels.append(
                LabelResult(
                    label_code="style_unlabeled_stock_factors_missing",
                    label_name="风格未标注：缺少股票因子",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_unlabeled_stock_factors_missing",
                    metric="stock_factors_present",
                    value="no",
                    threshold="required_for_style_labels",
                    source="stock_factors",
                    message="有基金持仓，但缺少 PB、ROE、股息率、成长性等股票因子，不能输出正式风格标签。",
                )
            )
            return

        # 数据完整：把股票因子按持仓权重聚合并尝试触发深度价值/质量成长/红利稳健
        self._add_style_labels(fund, labels, evidence)

    @staticmethod
    def _factor_lookup(
        stock_factors: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        return {row["stock_code"]: row for row in stock_factors if row.get("stock_code")}

    def _add_style_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        cfg = self._rule_config
        factor_by_stock = self._factor_lookup(fund.stock_factors)

        # 计算「满足条件持仓占比」：以基金持仓为分母，仅统计存在因子且字段非空的股票。
        deep_value_weight = 0.0
        quality_weight = 0.0
        dividend_weight = 0.0
        coverage_weight = 0.0  # 至少有一项因子的股票总权重，用作 evidence
        for holding in fund.stock_holdings:
            stock_code = holding.get("stock_code")
            weight = float(holding.get("weight") or 0.0)
            if not stock_code or weight <= 0:
                continue
            factors = factor_by_stock.get(stock_code)
            if not factors:
                continue
            coverage_weight += weight
            pb = factors.get("pb")
            valuation_pct = factors.get("valuation_percentile")
            if (
                pb is not None
                and valuation_pct is not None
                and pb <= cfg.deep_value_pb_max
                and valuation_pct <= cfg.deep_value_valuation_pct_max
            ):
                deep_value_weight += weight
            roe = factors.get("roe")
            revenue_growth = factors.get("revenue_growth")
            if (
                roe is not None
                and revenue_growth is not None
                and roe >= cfg.quality_growth_roe_min
                and revenue_growth >= cfg.quality_growth_revenue_growth_min
            ):
                quality_weight += weight
            dividend_yield = factors.get("dividend_yield")
            if (
                dividend_yield is not None
                and dividend_yield >= cfg.dividend_steady_yield_min
            ):
                dividend_weight += weight

        triggered: list[str] = []

        def _emit(label_code: str, label_name: str, msg: str, ratio: float, threshold: float) -> None:
            labels.append(
                LabelResult(
                    label_code=label_code,
                    label_name=label_name,
                    category="holding_style",
                    confidence=0.7,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code=label_code,
                    metric=f"{label_code}_weight",
                    value=round(ratio, 4),
                    threshold=threshold,
                    source="stock_factors",
                    message=msg,
                )
            )
            triggered.append(label_code)

        if deep_value_weight >= cfg.deep_value_weight_min:
            _emit(
                "deep_value",
                "深度价值",
                (
                    f"PB ≤ {cfg.deep_value_pb_max} 且估值分位数 ≤ "
                    f"{cfg.deep_value_valuation_pct_max:.0%} 的持仓权重占 "
                    f"{deep_value_weight:.0%}，达到 {cfg.deep_value_weight_min:.0%} 阈值。"
                ),
                deep_value_weight,
                cfg.deep_value_weight_min,
            )
        if quality_weight >= cfg.quality_growth_weight_min:
            _emit(
                "quality_growth",
                "质量成长",
                (
                    f"ROE ≥ {cfg.quality_growth_roe_min:.0%} 且营收增速 ≥ "
                    f"{cfg.quality_growth_revenue_growth_min:.0%} 的持仓权重占 "
                    f"{quality_weight:.0%}，达到 {cfg.quality_growth_weight_min:.0%} 阈值。"
                ),
                quality_weight,
                cfg.quality_growth_weight_min,
            )
        if dividend_weight >= cfg.dividend_steady_weight_min:
            _emit(
                "dividend_steady",
                "红利稳健",
                (
                    f"股息率 ≥ {cfg.dividend_steady_yield_min:.0%} 的持仓权重占 "
                    f"{dividend_weight:.0%}，达到 {cfg.dividend_steady_weight_min:.0%} 阈值。"
                ),
                dividend_weight,
                cfg.dividend_steady_weight_min,
            )

        # 一个风格也没出 → 给观察标签解释为什么；否则三标签自身已说明
        if not triggered:
            labels.append(
                LabelResult(
                    label_code="style_pending_rule_definition",
                    label_name="风格未达阈值",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_pending_rule_definition",
                    metric="style_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold=(
                        f"deep_value≥{cfg.deep_value_weight_min:.0%}, "
                        f"quality_growth≥{cfg.quality_growth_weight_min:.0%}, "
                        f"dividend_steady≥{cfg.dividend_steady_weight_min:.0%}"
                    ),
                    source="stock_factors",
                    message=(
                        "股票因子已经存在，但没有任何风格指标达到阈值。"
                        f"deep_value={deep_value_weight:.0%}, "
                        f"quality_growth={quality_weight:.0%}, "
                        f"dividend_steady={dividend_weight:.0%}."
                    ),
                )
            )
