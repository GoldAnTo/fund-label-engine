from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from math import sqrt
from pathlib import Path
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
    high_dividend_sector_ratio_min: float = 0.6
    consumer_dominant_ratio_min: float = 0.6
    sector_coverage_min: float = 0.7
    style_exposure_low_coverage_threshold: float = 0.5
    style_exposure_formal_coverage_threshold: float = 0.7
    style_balanced_weight_min: float = 0.20
    style_balanced_min_count: int = 2
    style_stability_min_periods: int = 2
    style_drift_delta_threshold: float = 0.25
    style_recent_shift_threshold: float = 0.20
    # ---- 扩展风格标签阈值（估值/规模/盈利质量） ----
    low_valuation_pb_max: float = 3.0
    low_valuation_pe_max: float = 20.0
    high_valuation_pb_min: float = 8.0
    high_valuation_pe_min: float = 40.0
    large_cap_log10_mcap_min: float = 10.5
    mid_cap_log10_mcap_min: float = 9.5
    mid_cap_log10_mcap_max: float = 10.5
    small_cap_log10_mcap_max: float = 9.5
    high_roe_threshold: float = 0.15
    profit_growth_strong_threshold: float = 0.30
    # 行业主题标签阈值
    industry_theme_weight_min: float = 0.50
    # ---- 风格组合标签阈值 ----
    # 组合标签需要两个以上基础风格标签同时命中
    mixed_style_min_styles: int = 3
    mixed_style_min_ratio: float = 0.15
    mixed_style_max_ratio: float = 0.35
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
    # 停用的规则（label_code 集合）。evaluate 会在 coverage 降级后、
    # 分类/分组前过滤掉这些标签，使它们不出现在最终输出里，
    # 也不影响 classification / group 判定。
    # data_quality / review 类标签（data_insufficient 等）不可停用。
    disabled_rules: frozenset[str] = frozenset()

    @classmethod
    def from_file(cls, path: str | Path) -> "RuleConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Rule config file must contain a JSON object.")
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"Unknown rule config field(s): {', '.join(unknown)}")
        # disabled_rules 支持 JSON 数组，转成 frozenset
        if "disabled_rules" in payload:
            dr = payload["disabled_rules"]
            if isinstance(dr, list):
                payload["disabled_rules"] = frozenset(str(x) for x in dr)
            elif not isinstance(dr, frozenset):
                raise ValueError("disabled_rules must be a JSON array of label codes.")
        return cls(**payload)

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
                "style_exposure_formal_coverage_min": self.style_exposure_formal_coverage_threshold,
            },
            "quality_growth": {
                "roe_weighted_min": self.quality_growth_roe_min,
                "revenue_growth_weighted_min": self.quality_growth_revenue_growth_min,
                "quality_growth_weight_min": self.quality_growth_weight_min,
                "style_exposure_formal_coverage_min": self.style_exposure_formal_coverage_threshold,
            },
            "dividend_steady": {
                "dividend_yield_min": self.dividend_steady_yield_min,
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
                "style_exposure_formal_coverage_min": self.style_exposure_formal_coverage_threshold,
            },
            "high_dividend_financial": {
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
                "high_dividend_sector_ratio_min": self.high_dividend_sector_ratio_min,
                "sector_coverage_min": self.sector_coverage_min,
            },
            "consumer_quality": {
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
                "consumer_dominant_ratio_min": self.consumer_dominant_ratio_min,
                "sector_coverage_min": self.sector_coverage_min,
            },
            "sector_mapping_insufficient": {
                "sector_coverage_min": self.sector_coverage_min,
            },
            "style_balanced": {
                "style_balanced_weight_min": self.style_balanced_weight_min,
                "style_balanced_min_count": self.style_balanced_min_count,
            },
            "style_exposure_low_coverage": {
                "coverage_weight_max_exclusive": self.style_exposure_low_coverage_threshold,
            },
            "style_exposure_observe": {
                "coverage_weight_min": self.style_exposure_low_coverage_threshold,
                "coverage_weight_max_exclusive": self.style_exposure_formal_coverage_threshold,
            },
            "style_stable": {
                "min_periods": self.style_stability_min_periods,
                "dominant_style_delta_max": self.style_drift_delta_threshold,
            },
            "style_drift": {
                "min_periods": self.style_stability_min_periods,
                "dominant_style_delta_min": self.style_drift_delta_threshold,
            },
            "style_recent_shift": {
                "latest_period_delta_min": self.style_recent_shift_threshold,
            },
            "low_valuation": {
                "pb_weighted_max": self.low_valuation_pb_max,
                "pe_weighted_max": self.low_valuation_pe_max,
            },
            "high_valuation": {
                "pb_weighted_min": self.high_valuation_pb_min,
                "pe_weighted_min": self.high_valuation_pe_min,
            },
            "large_cap": {
                "log10_market_cap_weighted_min": self.large_cap_log10_mcap_min,
            },
            "mid_cap": {
                "log10_market_cap_weighted_min": self.mid_cap_log10_mcap_min,
                "log10_market_cap_weighted_max": self.mid_cap_log10_mcap_max,
            },
            "small_cap": {
                "log10_market_cap_weighted_max": self.small_cap_log10_mcap_max,
            },
            "high_roe": {
                "roe_weighted_min": self.high_roe_threshold,
            },
            "profit_growth_strong": {
                "profit_growth_weighted_min": self.profit_growth_strong_threshold,
            },
            "tech_focused": {
                "industry_theme_weight_min": self.industry_theme_weight_min,
            },
            "finance_focused": {
                "industry_theme_weight_min": self.industry_theme_weight_min,
            },
            "consumer_focused": {
                "industry_theme_weight_min": self.industry_theme_weight_min,
            },
            "healthcare_focused": {
                "industry_theme_weight_min": self.industry_theme_weight_min,
            },
            "cyclical_focused": {
                "industry_theme_weight_min": self.industry_theme_weight_min,
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
        "label_name": "风格未达阈值",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "股票因子或基金级暴露存在，但高级风格标签未达阈值。",
    },
    {
        "label_code": "style_balanced",
        "label_name": "均衡风格",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "已测量风格暴露，但无单一主导风格达阈值，且至少两类风格权重均衡分布。",
    },
    {
        "label_code": "style_exposure_low_coverage",
        "label_name": "风格暴露覆盖不足",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "基金级因子覆盖权重低于最低阈值，不能正式判断风格。",
    },
    {
        "label_code": "style_exposure_scope_not_applicable",
        "label_name": "风格暴露适用范围不足",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "股票持仓总权重不足，A 股风格暴露不适合正式判断。",
    },
    {
        "label_code": "style_exposure_observe",
        "label_name": "风格暴露仅观察",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "基金级因子覆盖权重一般，只输出观察结论，不触发正式风格标签。",
    },
    {
        "label_code": "style_stable",
        "label_name": "风格稳定",
        "category": "style_stability",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "多期基金级风格暴露的主导风格保持一致，仅作为观察结论。",
    },
    {
        "label_code": "style_drift",
        "label_name": "风格漂移",
        "category": "style_stability",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "多期基金级风格暴露的主导风格发生变化，仅作为观察结论。",
    },
    {
        "label_code": "style_recent_shift",
        "label_name": "近期风格切换",
        "category": "style_stability",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "最近一期基金级风格暴露相对上一期变化较大，仅作为观察结论。",
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
        "label_code": "high_dividend_financial",
        "label_name": "金融高股息",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利贡献主要来自金融、能源、公用事业、交通运输等传统高股息行业。",
    },
    {
        "label_code": "consumer_quality",
        "label_name": "消费质量",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利底层命中但消费行业贡献主导，归为消费质量而非红利稳健。",
    },
    {
        "label_code": "sector_mapping_insufficient",
        "label_name": "行业映射覆盖不足",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利贡献股票行业映射覆盖率不足，暂不做金融/消费/红利分流。",
    },
    {
        "label_code": "low_valuation",
        "label_name": "低估值",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权 PB 或 PE 低于规则阈值，估值整体偏低。",
    },
    {
        "label_code": "high_valuation",
        "label_name": "高估值",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权 PB 或 PE 高于规则阈值，估值整体偏高。",
    },
    {
        "label_code": "large_cap",
        "label_name": "大盘风格",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权对数市值高于规则阈值，以大盘股为主。",
    },
    {
        "label_code": "mid_cap",
        "label_name": "中盘风格",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权对数市值处于中盘区间。",
    },
    {
        "label_code": "small_cap",
        "label_name": "小盘风格",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权对数市值低于规则阈值，以小盘股为主。",
    },
    {
        "label_code": "high_roe",
        "label_name": "高盈利质量",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权 ROE 达到规则阈值，持仓公司盈利能力较强。",
    },
    {
        "label_code": "profit_growth_strong",
        "label_name": "利润高增长",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "持仓加权利润增速达到规则阈值，持仓公司利润增长较快。",
    },
    {
        "label_code": "tech_focused",
        "label_name": "科技主题",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "科技行业持仓权重超过规则阈值，重仓科技板块。",
    },
    {
        "label_code": "finance_focused",
        "label_name": "金融主题",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "金融行业持仓权重超过规则阈值，重仓金融板块。",
    },
    {
        "label_code": "consumer_focused",
        "label_name": "消费主题",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "消费行业持仓权重超过规则阈值，重仓消费板块。",
    },
    {
        "label_code": "healthcare_focused",
        "label_name": "医药主题",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "医药行业持仓权重超过规则阈值，重仓医药板块。",
    },
    {
        "label_code": "cyclical_focused",
        "label_name": "周期主题",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "周期性行业持仓权重超过规则阈值，重仓周期板块。",
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
_STYLE_LABELS = {
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
    "low_valuation",
    "high_valuation",
    "large_cap",
    "mid_cap",
    "small_cap",
    "high_roe",
    "profit_growth_strong",
    "tech_focused",
    "finance_focused",
    "consumer_focused",
    "healthcare_focused",
    "cyclical_focused",
    "value_dividend",
    "growth_large_cap",
    "growth_small_cap",
    "quality_dividend",
    "value_quality",
    "growth_profit",
}
_STYLE_GROUP_BY_LABEL = {
    "deep_value": ("deep_value_group", "深度价值组"),
    "quality_growth": ("quality_growth_group", "质量成长组"),
    "dividend_steady": ("dividend_steady_group", "红利稳健组"),
    "high_dividend_financial": ("high_dividend_financial_group", "金融高股息组"),
    "consumer_quality": ("consumer_quality_group", "消费质量组"),
    "low_valuation": ("low_valuation_group", "低估值组"),
    "high_valuation": ("high_valuation_group", "高估值组"),
    "large_cap": ("large_cap_group", "大盘组"),
    "mid_cap": ("mid_cap_group", "中盘组"),
    "small_cap": ("small_cap_group", "小盘组"),
    "high_roe": ("high_roe_group", "高盈利组"),
    "profit_growth_strong": ("profit_growth_group", "利润高增长组"),
    "tech_focused": ("tech_group", "科技主题组"),
    "finance_focused": ("finance_group", "金融主题组"),
    "consumer_focused": ("consumer_theme_group", "消费主题组"),
    "healthcare_focused": ("healthcare_group", "医药主题组"),
    "cyclical_focused": ("cyclical_group", "周期主题组"),
    "value_dividend": ("composite_group", "组合风格组"),
    "growth_large_cap": ("composite_group", "组合风格组"),
    "growth_small_cap": ("composite_group", "组合风格组"),
    "quality_dividend": ("composite_group", "组合风格组"),
    "value_quality": ("composite_group", "组合风格组"),
    "growth_profit": ("composite_group", "组合风格组"),
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
    factor_exposures: list[dict[str, Any]] = field(default_factory=list)
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
        self._add_extended_style_labels(fund, labels, evidence)

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

        # 规则启停：过滤掉 disabled_rules 里的标签。
        # data_quality / review 类标签不可停用（gate 语义必须保留）。
        if self._rule_config.disabled_rules:
            labels = [
                label
                for label in labels
                if label.category in ("data_quality", "review")
                or label.label_code not in self._rule_config.disabled_rules
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
            or "style_exposure_low_coverage" in label_codes
            or "style_exposure_observe" in label_codes
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
                "style_threshold_or_coverage_not_met",
                "股票因子已接入，但风格权重或因子覆盖尚不足以输出正式风格标签。",
                "fund_factor_exposures" if fund.factor_exposures else "stock_factors",
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
            "style_exposure_low_coverage",
            "style_exposure_observe",
        } | _STYLE_LABELS:
            stock_detail = coverage_details.get("stock_holdings")
            if stock_detail and not stock_detail["ok"]:
                return self._not_computed_from_gate("stock_holdings", stock_detail)
            if label_code in _STYLE_LABELS:
                if not fund.factor_exposures and not fund.stock_factors:
                    return (
                        "not_computed",
                        "stock_factors_missing",
                        "0",
                        "stock_factors_required",
                        "stock_factors",
                        "缺少股票因子，不能计算正式风格标签。",
                    )
                source = "fund_factor_exposures" if fund.factor_exposures else "stock_factors"
                return (
                    "not_triggered",
                    "threshold_not_met",
                    self._style_observed(label_code, feature_map),
                    threshold,
                    source,
                    "风格暴露未达到标签阈值。",
                )
            if label_code == "style_unlabeled_stock_factors_missing":
                source = "fund_factor_exposures" if fund.factor_exposures else "stock_factors"
                observed = len(fund.factor_exposures) if fund.factor_exposures else len(fund.stock_factors)
                return (
                    "not_triggered",
                    "stock_factors_available",
                    observed,
                    "stock_factors_missing",
                    source,
                    "股票因子或基金级因子暴露已经存在，未触发缺少股票因子边界标签。",
                )
            if label_code in {"style_exposure_low_coverage", "style_exposure_observe"}:
                coverage = self._style_observed("factor_coverage", feature_map)
                return (
                    "not_triggered",
                    "coverage_not_in_bucket",
                    coverage,
                    threshold,
                    "fund_factor_exposures",
                    "基金级因子覆盖权重不在该观察标签区间内。",
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
        for exposure in fund.factor_exposures:
            factor_code = exposure.get("factor_code")
            if not factor_code:
                continue
            features.append(
                FeatureValue(
                    str(factor_code),
                    round(float(exposure.get("exposure_value") or 0.0), 6),
                    "fund_factor_exposures",
                )
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

    def _maybe_emit_style_balanced(
        self,
        *,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
        style_weights: dict[str, float],
        source: str,
    ) -> bool:
        cfg = self._rule_config
        balanced_count = sum(
            1 for value in style_weights.values() if value >= cfg.style_balanced_weight_min
        )
        if balanced_count < cfg.style_balanced_min_count:
            return False
        labels.append(
            LabelResult(
                label_code="style_balanced",
                label_name="均衡风格",
                category="holding_style",
                confidence=1.0,
                status="observe",
            )
        )
        detail = ", ".join(
            f"{code}={value:.0%}" for code, value in style_weights.items()
        )
        evidence.append(
            EvidenceItem(
                label_code="style_balanced",
                metric="style_balanced_weight_count",
                value=balanced_count,
                threshold=(
                    f"at_least_{cfg.style_balanced_min_count}"
                    f"_styles_ge_{cfg.style_balanced_weight_min:.0%}"
                ),
                source=source,
                message=(
                    f"无单一主导风格达阈值，但有 {balanced_count} 类风格权重 ≥ "
                    f"{cfg.style_balanced_weight_min:.0%}，判为均衡风格。{detail}。"
                ),
            )
        )
        return True

    def _add_style_boundary_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if not fund.stock_holdings:
            return
        if not fund.factor_exposures and not fund.stock_factors:
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
        self._add_style_stability_labels(fund, labels, evidence)

    def _add_extended_style_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        """扩展风格标签：估值/规模/盈利质量/行业主题。

        这些标签在原有深度价值/质量成长/红利稳健之外，利用已有但未使用的
        因子（PE、市值、利润增速）和行业映射，补充更细粒度的风格判断。
        """
        if not fund.factor_exposures and not fund.stock_factors:
            return

        cfg = self._rule_config
        exposure_by_code = self._factor_exposure_lookup(fund.factor_exposures)

        def _exp_value(code: str) -> float | None:
            row = exposure_by_code.get(code) or {}
            val = row.get("exposure_value")
            if val is None:
                return None
            return float(val)

        def _exp_coverage() -> float:
            row = exposure_by_code.get("factor_coverage_weight") or {}
            return float(row.get("exposure_value") or 0.0)

        # 如果没有预聚合暴露，从持仓股票因子现算
        if not exposure_by_code and fund.stock_factors:
            factor_by_stock = self._factor_lookup(fund.stock_factors)
            coverage_weight = 0.0
            pb_sum = pe_sum = mcap_sum = roe_sum = pg_sum = 0.0
            pb_w = pe_w = mcap_w = roe_w = pg_w = 0.0
            for holding in fund.stock_holdings:
                stock_code = holding.get("stock_code")
                weight = float(holding.get("weight") or 0.0)
                if not stock_code or weight <= 0:
                    continue
                factors = factor_by_stock.get(stock_code)
                if not factors:
                    continue
                coverage_weight += weight
                pb = self._safe_float(factors.get("pb"))
                pe = self._safe_float(factors.get("pe"))
                mcap = self._safe_float(factors.get("log10_market_cap"))
                roe = self._safe_float(factors.get("roe"))
                pg = self._safe_float(factors.get("profit_growth"))
                if pb is not None and pb > 0:
                    pb_sum += weight * min(pb, 100.0)
                    pb_w += weight
                if pe is not None and pe > 0:
                    pe_sum += weight * min(pe, 500.0)
                    pe_w += weight
                if mcap is not None:
                    mcap_sum += weight * mcap
                    mcap_w += weight
                if roe is not None:
                    roe_sum += weight * max(min(roe, 1.0), -1.0)
                    roe_w += weight
                if pg is not None:
                    pg_sum += weight * max(min(pg, 10.0), -3.0)
                    pg_w += weight

            pb_weighted = pb_sum / pb_w if pb_w > 0 else None
            pe_weighted = pe_sum / pe_w if pe_w > 0 else None
            mcap_weighted = mcap_sum / mcap_w if mcap_w > 0 else None
            roe_weighted = roe_sum / roe_w if roe_w > 0 else None
            pg_weighted = pg_sum / pg_w if pg_w > 0 else None
            coverage = coverage_weight
        else:
            pb_weighted = _exp_value("pb_weighted")
            pe_weighted = _exp_value("pe_weighted")
            mcap_weighted = _exp_value("log10_market_cap_weighted")
            roe_weighted = _exp_value("roe_weighted")
            pg_weighted = _exp_value("profit_growth_weighted")
            coverage = _exp_coverage()

        # 覆盖率不足时不输出扩展风格标签
        if coverage < cfg.style_exposure_low_coverage_threshold:
            return

        source = "fund_factor_exposures" if exposure_by_code else "stock_factors"

        # --- 估值标签 ---
        if pb_weighted is not None and pe_weighted is not None:
            if pb_weighted <= cfg.low_valuation_pb_max or pe_weighted <= cfg.low_valuation_pe_max:
                labels.append(LabelResult(
                    label_code="low_valuation",
                    label_name="低估值",
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code="low_valuation",
                    metric="pb_weighted/pe_weighted",
                    value=f"PB={pb_weighted:.2f}, PE={pe_weighted:.2f}",
                    threshold=f"PB≤{cfg.low_valuation_pb_max} 或 PE≤{cfg.low_valuation_pe_max}",
                    source=source,
                    message=f"加权 PB={pb_weighted:.2f}，加权 PE={pe_weighted:.2f}，达到低估值阈值。",
                ))
            elif pb_weighted >= cfg.high_valuation_pb_min or pe_weighted >= cfg.high_valuation_pe_min:
                labels.append(LabelResult(
                    label_code="high_valuation",
                    label_name="高估值",
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code="high_valuation",
                    metric="pb_weighted/pe_weighted",
                    value=f"PB={pb_weighted:.2f}, PE={pe_weighted:.2f}",
                    threshold=f"PB≥{cfg.high_valuation_pb_min} 或 PE≥{cfg.high_valuation_pe_min}",
                    source=source,
                    message=f"加权 PB={pb_weighted:.2f}，加权 PE={pe_weighted:.2f}，达到高估值阈值。",
                ))

        # --- 规模标签 ---
        if mcap_weighted is not None:
            if mcap_weighted >= cfg.large_cap_log10_mcap_min:
                labels.append(LabelResult(
                    label_code="large_cap",
                    label_name="大盘风格",
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code="large_cap",
                    metric="log10_market_cap_weighted",
                    value=round(mcap_weighted, 4),
                    threshold=cfg.large_cap_log10_mcap_min,
                    source=source,
                    message=f"加权对数市值 {mcap_weighted:.2f}，达到大盘阈值 {cfg.large_cap_log10_mcap_min}。",
                ))
            elif cfg.mid_cap_log10_mcap_min <= mcap_weighted < cfg.mid_cap_log10_mcap_max:
                labels.append(LabelResult(
                    label_code="mid_cap",
                    label_name="中盘风格",
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code="mid_cap",
                    metric="log10_market_cap_weighted",
                    value=round(mcap_weighted, 4),
                    threshold=f"{cfg.mid_cap_log10_mcap_min}~{cfg.mid_cap_log10_mcap_max}",
                    source=source,
                    message=f"加权对数市值 {mcap_weighted:.2f}，处于中盘区间。",
                ))
            elif mcap_weighted < cfg.small_cap_log10_mcap_max:
                labels.append(LabelResult(
                    label_code="small_cap",
                    label_name="小盘风格",
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code="small_cap",
                    metric="log10_market_cap_weighted",
                    value=round(mcap_weighted, 4),
                    threshold=cfg.small_cap_log10_mcap_max,
                    source=source,
                    message=f"加权对数市值 {mcap_weighted:.2f}，达到小盘阈值 {cfg.small_cap_log10_mcap_max}。",
                ))

        # --- 盈利质量标签 ---
        if roe_weighted is not None and roe_weighted >= cfg.high_roe_threshold:
            labels.append(LabelResult(
                label_code="high_roe",
                label_name="高盈利质量",
                category="holding_style",
                confidence=0.7,
            ))
            evidence.append(EvidenceItem(
                label_code="high_roe",
                metric="roe_weighted",
                value=round(roe_weighted, 4),
                threshold=cfg.high_roe_threshold,
                source=source,
                message=f"加权 ROE={roe_weighted:.2%}，达到阈值 {cfg.high_roe_threshold:.0%}。",
            ))

        if pg_weighted is not None and pg_weighted >= cfg.profit_growth_strong_threshold:
            labels.append(LabelResult(
                label_code="profit_growth_strong",
                label_name="利润高增长",
                category="holding_style",
                confidence=0.7,
            ))
            evidence.append(EvidenceItem(
                label_code="profit_growth_strong",
                metric="profit_growth_weighted",
                value=round(pg_weighted, 4),
                threshold=cfg.profit_growth_strong_threshold,
                source=source,
                message=f"加权利润增速={pg_weighted:.2%}，达到阈值 {cfg.profit_growth_strong_threshold:.0%}。",
            ))

        # --- 行业主题标签 ---
        self._add_industry_theme_labels(fund, labels, evidence, source)

        # --- 风格组合标签 ---
        self._add_composite_style_labels(labels, evidence, source)

    def _add_industry_theme_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
        source: str,
    ) -> None:
        """行业主题标签：统计持仓股票的行业分组权重，触发主题标签。"""
        if not fund.stock_factors:
            return

        cfg = self._rule_config
        # 从 fund.stock_factors 里的行业映射信息计算行业权重
        # stock_factors 中每只股票可能携带 sector_group 信息
        sector_weights: dict[str, float] = {}
        total_weight = 0.0

        for holding in fund.stock_holdings:
            stock_code = holding.get("stock_code")
            weight = float(holding.get("weight") or 0.0)
            if not stock_code or weight <= 0:
                continue
            total_weight += weight
            # 从 stock_factors 行里取 sector_group
            sector = None
            for sf in fund.stock_factors:
                if str(sf.get("stock_code")) == str(stock_code):
                    sector = sf.get("sector_group")
                    break
            if sector:
                sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        if total_weight <= 0:
            return

        theme_mapping = {
            "tech": ("tech_focused", "科技主题"),
            "financial": ("finance_focused", "金融主题"),
            "consumer": ("consumer_focused", "消费主题"),
            "healthcare": ("healthcare_focused", "医药主题"),
            "cyclical": ("cyclical_focused", "周期主题"),
        }

        for sector, (label_code, label_name) in theme_mapping.items():
            weight = sector_weights.get(sector, 0.0)
            ratio = weight / total_weight if total_weight > 0 else 0.0
            if ratio >= cfg.industry_theme_weight_min:
                labels.append(LabelResult(
                    label_code=label_code,
                    label_name=label_name,
                    category="holding_style",
                    confidence=0.7,
                ))
                evidence.append(EvidenceItem(
                    label_code=label_code,
                    metric=f"{sector}_industry_weight",
                    value=round(ratio, 4),
                    threshold=cfg.industry_theme_weight_min,
                    source=source,
                    message=f"{sector} 行业持仓权重 {ratio:.0%}，达到阈值 {cfg.industry_theme_weight_min:.0%}。",
                ))

    def _add_composite_style_labels(
        self,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
        source: str,
    ) -> None:
        """风格组合标签：当两个以上基础风格标签同时命中时，生成组合标签。

        组合标签让标签更接近投研语言，比如「价值红利」「大盘成长」。
        """
        # LabelResult 默认 status="active"（不传时）；基础风格标签的 active 状态
        # 即为命中。同时排除已被本组合方法本身标记的 composite_group 标签，
        # 避免重复触发与连锁。
        triggered_codes = {
            lbl.label_code
            for lbl in labels
            if lbl.status in ("active", "triggered")
        }

        # 定义组合标签规则
        composite_rules: list[tuple[str, str, frozenset[str]]] = [
            # (label_code, label_name, required_codes)
            ("value_dividend", "价值红利", frozenset({"low_valuation", "dividend_steady"})),
            ("growth_large_cap", "大盘成长", frozenset({"quality_growth", "large_cap"})),
            ("growth_small_cap", "小盘成长", frozenset({"quality_growth", "small_cap"})),
            ("quality_dividend", "高质量红利", frozenset({"high_roe", "dividend_steady"})),
            ("value_quality", "价值质量", frozenset({"low_valuation", "high_roe"})),
            ("growth_profit", "成长盈利", frozenset({"quality_growth", "profit_growth_strong"})),
        ]

        for label_code, label_name, required in composite_rules:
            if required.issubset(triggered_codes):
                labels.append(LabelResult(
                    label_code=label_code,
                    label_name=label_name,
                    category="holding_style",
                    confidence=0.65,
                ))
                evidence.append(EvidenceItem(
                    label_code=label_code,
                    metric="composite_styles",
                    value="+".join(sorted(required)),
                    threshold="同时命中",
                    source=source,
                    message=f"同时命中 {' + '.join(sorted(required))}，组合为{label_name}。",
                ))

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _factor_lookup(
        stock_factors: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        return {row["stock_code"]: row for row in stock_factors if row.get("stock_code")}

    @staticmethod
    def _factor_exposure_lookup(
        factor_exposures: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        latest_by_code: dict[str, dict[str, Any]] = {}
        for row in factor_exposures:
            factor_code = row.get("factor_code")
            if not factor_code:
                continue
            current = latest_by_code.get(str(factor_code))
            # 多期暴露会复用同一份因子快照，因此 as_of_date 通常完全相同；
            # 当前期风格标签必须按 report_date 选最新报告期，否则批处理按降序
            # 计算时，后写入的历史期会覆盖当前期，导致低覆盖误判。
            if (
                current is None
                or LabelEngine._factor_exposure_key(row)
                >= LabelEngine._factor_exposure_key(current)
            ):
                latest_by_code[str(factor_code)] = row
        return latest_by_code

    @staticmethod
    def _factor_exposure_key(row: dict[str, Any]) -> tuple[str, str]:
        return (
            str(row.get("report_date") or row.get("as_of_date") or ""),
            str(row.get("as_of_date") or ""),
        )

    def _dividend_sector_values(
        self,
        exposure_by_code: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        def value(code: str) -> float:
            row = exposure_by_code.get(code) or {}
            return float(row.get("exposure_value") or 0.0)

        return {
            "financial": value("dividend_sector_financial_ratio"),
            "energy_utility": value("dividend_sector_energy_utility_ratio"),
            "consumer": value("dividend_sector_consumer_ratio"),
            "coverage": value("dividend_sector_coverage"),
        }

    def _dividend_split_label(
        self,
        sector_values: dict[str, float],
    ) -> tuple[str, str, str]:
        cfg = self._rule_config
        high_dividend_ratio = (
            sector_values["financial"] + sector_values["energy_utility"]
        )
        if sector_values["coverage"] < cfg.sector_coverage_min:
            return (
                "dividend_steady",
                "红利稳健",
                "行业映射覆盖不足，保留红利稳健并追加观察标签。",
            )
        if high_dividend_ratio >= cfg.high_dividend_sector_ratio_min:
            return (
                "high_dividend_financial",
                "金融高股息",
                f"金融/能源/公用事业红利贡献占比 {high_dividend_ratio:.0%}。",
            )
        if sector_values["consumer"] >= cfg.consumer_dominant_ratio_min:
            return (
                "consumer_quality",
                "消费质量",
                f"消费红利贡献占比 {sector_values['consumer']:.0%}。",
            )
        return (
            "dividend_steady",
            "红利稳健",
            "红利贡献未被单一金融/能源或消费行业主导。",
        )

    def _add_style_labels_from_exposures(
        self,
        exposure_by_code: dict[str, dict[str, Any]],
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        cfg = self._rule_config
        triggered: list[str] = []

        def _value(code: str) -> float:
            row = exposure_by_code.get(code) or {}
            return float(row.get("exposure_value") or 0.0)

        def _coverage(code: str) -> float:
            row = exposure_by_code.get(code) or {}
            return float(row.get("coverage_weight") or 0.0)

        def _holding_total_weight() -> float:
            row = exposure_by_code.get("factor_coverage_weight") or {}
            return float(row.get("holding_total_weight") or 0.0)

        def _emit_scope_not_applicable(holding_total_weight: float) -> None:
            labels.append(
                LabelResult(
                    label_code="style_exposure_scope_not_applicable",
                    label_name="风格暴露适用范围不足",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_exposure_scope_not_applicable",
                    metric="stock_holding_total_weight",
                    value=round(holding_total_weight, 4),
                    threshold=cfg.style_exposure_low_coverage_threshold,
                    source="fund_factor_exposures",
                    message=(
                        f"股票持仓总权重 {holding_total_weight:.0%}，低于 "
                        f"{cfg.style_exposure_low_coverage_threshold:.0%} 最低阈值，"
                        "A股风格暴露适用范围不足，不输出正式风格标签。"
                    ),
                )
            )

        def _emit(
            label_code: str,
            label_name: str,
            metric: str,
            threshold: float,
            message: str,
        ) -> None:
            value = _value(metric)
            coverage = _coverage(metric)
            labels.append(
                LabelResult(
                    label_code=label_code,
                    label_name=label_name,
                    category="holding_style",
                    confidence=0.75,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code=label_code,
                    metric=metric,
                    value=round(value, 4),
                    threshold=threshold,
                    source="fund_factor_exposures",
                    message=f"{message} 因子覆盖权重 {coverage:.0%}。",
                )
            )
            triggered.append(label_code)

        deep_value_weight = _value("deep_value_weight")
        quality_weight = _value("quality_growth_weight")
        dividend_weight = _value("dividend_steady_weight")
        coverage_weight = _value("factor_coverage_weight")

        if coverage_weight < cfg.style_exposure_low_coverage_threshold:
            holding_total_weight = _holding_total_weight()
            if holding_total_weight < cfg.style_exposure_low_coverage_threshold:
                _emit_scope_not_applicable(holding_total_weight)
                return
            labels.append(
                LabelResult(
                    label_code="style_exposure_low_coverage",
                    label_name="风格暴露覆盖不足",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_exposure_low_coverage",
                    metric="factor_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold=cfg.style_exposure_low_coverage_threshold,
                    source="fund_factor_exposures",
                    message=(
                        f"基金级因子覆盖权重 {coverage_weight:.0%}，低于 "
                        f"{cfg.style_exposure_low_coverage_threshold:.0%} 最低阈值，"
                        "即使风格权重达标也不输出正式风格标签。"
                    ),
                )
            )
            return

        if coverage_weight < cfg.style_exposure_formal_coverage_threshold:
            labels.append(
                LabelResult(
                    label_code="style_exposure_observe",
                    label_name="风格暴露仅观察",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_exposure_observe",
                    metric="factor_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold=(
                        f"{cfg.style_exposure_low_coverage_threshold:.0%}~"
                        f"{cfg.style_exposure_formal_coverage_threshold:.0%}"
                    ),
                    source="fund_factor_exposures",
                    message=(
                        f"基金级因子覆盖权重 {coverage_weight:.0%}，处于观察区间 "
                        f"{cfg.style_exposure_low_coverage_threshold:.0%}~"
                        f"{cfg.style_exposure_formal_coverage_threshold:.0%}，"
                        "不输出正式风格标签。"
                    ),
                )
            )
            return

        if deep_value_weight >= cfg.deep_value_weight_min:
            _emit(
                "deep_value",
                "深度价值",
                "deep_value_weight",
                cfg.deep_value_weight_min,
                (
                    f"预聚合深度价值持仓权重 {deep_value_weight:.0%}，"
                    f"达到 {cfg.deep_value_weight_min:.0%} 阈值。"
                ),
            )
        if quality_weight >= cfg.quality_growth_weight_min:
            _emit(
                "quality_growth",
                "质量成长",
                "quality_growth_weight",
                cfg.quality_growth_weight_min,
                (
                    f"预聚合质量成长持仓权重 {quality_weight:.0%}，"
                    f"达到 {cfg.quality_growth_weight_min:.0%} 阈值。"
                ),
            )
        if dividend_weight >= cfg.dividend_steady_weight_min:
            sector_values = self._dividend_sector_values(exposure_by_code)
            split_code, split_name, split_message = self._dividend_split_label(
                sector_values
            )
            _emit(
                split_code,
                split_name,
                "dividend_steady_weight",
                cfg.dividend_steady_weight_min,
                (
                    f"预聚合红利持仓权重 {dividend_weight:.0%}，"
                    f"达到 {cfg.dividend_steady_weight_min:.0%} 阈值；"
                    f"行业映射覆盖率 {sector_values['coverage']:.0%}；"
                    f"financial={sector_values['financial']:.0%}, "
                    f"energy_utility={sector_values['energy_utility']:.0%}, "
                    f"consumer={sector_values['consumer']:.0%}。{split_message}"
                ),
            )
            if sector_values["coverage"] < cfg.sector_coverage_min:
                labels.append(
                    LabelResult(
                        label_code="sector_mapping_insufficient",
                        label_name="行业映射覆盖不足",
                        category="style_boundary",
                        confidence=1.0,
                        status="observe",
                    )
                )
                evidence.append(
                    EvidenceItem(
                        label_code="sector_mapping_insufficient",
                        metric="dividend_sector_coverage",
                        value=round(sector_values["coverage"], 4),
                        threshold=cfg.sector_coverage_min,
                        source="fund_factor_exposures",
                        message="红利贡献股票行业映射覆盖不足，暂不进行金融/消费/红利分流。",
                    )
                )

        if not triggered:
            if self._maybe_emit_style_balanced(
                labels=labels,
                evidence=evidence,
                style_weights={
                    "deep_value": deep_value_weight,
                    "quality_growth": quality_weight,
                    "dividend_steady": dividend_weight,
                },
                source="fund_factor_exposures",
            ):
                return
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
                    metric="style_factor_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold="style_weights_below_threshold",
                    source="fund_factor_exposures",
                    message="已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。",
                )
            )

    def _add_style_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        cfg = self._rule_config
        exposure_by_code = self._factor_exposure_lookup(fund.factor_exposures)
        if exposure_by_code:
            self._add_style_labels_from_exposures(
                exposure_by_code,
                labels,
                evidence,
            )
            return

        factor_by_stock = self._factor_lookup(fund.stock_factors)

        deep_value_weight = 0.0
        quality_weight = 0.0
        dividend_weight = 0.0
        coverage_weight = 0.0
        holding_total_weight = 0.0
        for holding in fund.stock_holdings:
            stock_code = holding.get("stock_code")
            weight = float(holding.get("weight") or 0.0)
            if not stock_code or weight <= 0:
                continue
            holding_total_weight += weight
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

        if coverage_weight < cfg.style_exposure_low_coverage_threshold:
            if holding_total_weight < cfg.style_exposure_low_coverage_threshold:
                labels.append(
                    LabelResult(
                        label_code="style_exposure_scope_not_applicable",
                        label_name="风格暴露适用范围不足",
                        category="style_boundary",
                        confidence=1.0,
                        status="observe",
                    )
                )
                evidence.append(
                    EvidenceItem(
                        label_code="style_exposure_scope_not_applicable",
                        metric="stock_holding_total_weight",
                        value=round(holding_total_weight, 4),
                        threshold=cfg.style_exposure_low_coverage_threshold,
                        source="stock_factors",
                        message=(
                            f"股票持仓总权重 {holding_total_weight:.0%}，低于 "
                            f"{cfg.style_exposure_low_coverage_threshold:.0%} 最低阈值，"
                            "A股风格暴露适用范围不足，不输出正式风格标签。"
                        ),
                    )
                )
                return
            labels.append(
                LabelResult(
                    label_code="style_exposure_low_coverage",
                    label_name="风格暴露覆盖不足",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_exposure_low_coverage",
                    metric="factor_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold=cfg.style_exposure_low_coverage_threshold,
                    source="stock_factors",
                    message=(
                        f"股票因子覆盖持仓权重 {coverage_weight:.0%}，低于 "
                        f"{cfg.style_exposure_low_coverage_threshold:.0%} 最低阈值，"
                        "不输出正式风格标签。"
                    ),
                )
            )
            return

        if coverage_weight < cfg.style_exposure_formal_coverage_threshold:
            labels.append(
                LabelResult(
                    label_code="style_exposure_observe",
                    label_name="风格暴露仅观察",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_exposure_observe",
                    metric="factor_coverage_weight",
                    value=round(coverage_weight, 4),
                    threshold=(
                        f"{cfg.style_exposure_low_coverage_threshold:.0%}~"
                        f"{cfg.style_exposure_formal_coverage_threshold:.0%}"
                    ),
                    source="stock_factors",
                    message=(
                        f"股票因子覆盖持仓权重 {coverage_weight:.0%}，处于观察区间 "
                        f"{cfg.style_exposure_low_coverage_threshold:.0%}~"
                        f"{cfg.style_exposure_formal_coverage_threshold:.0%}，"
                        "不输出正式风格标签。"
                    ),
                )
            )
            return

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

        if not triggered:
            if self._maybe_emit_style_balanced(
                labels=labels,
                evidence=evidence,
                style_weights={
                    "deep_value": deep_value_weight,
                    "quality_growth": quality_weight,
                    "dividend_steady": dividend_weight,
                },
                source="stock_factors",
            ):
                return
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

    def _style_history_periods(self, fund: FundInput) -> list[dict[str, Any]]:
        by_period: dict[str, dict[str, float]] = {}
        for row in fund.factor_exposures:
            period = str(row.get("report_date") or row.get("as_of_date") or "")
            factor_code = str(row.get("factor_code") or "")
            if not period or factor_code not in {
                "deep_value_weight",
                "quality_growth_weight",
                "dividend_steady_weight",
                "factor_coverage_weight",
            }:
                continue
            by_period.setdefault(period, {})[factor_code] = float(
                row.get("exposure_value") or 0.0
            )

        periods: list[dict[str, Any]] = []
        for period, values in by_period.items():
            coverage = values.get("factor_coverage_weight", 0.0)
            if coverage < self._rule_config.style_exposure_formal_coverage_threshold:
                continue
            style_values = {
                "deep_value": values.get("deep_value_weight", 0.0),
                "quality_growth": values.get("quality_growth_weight", 0.0),
                "dividend_steady": values.get("dividend_steady_weight", 0.0),
            }
            dominant_style, dominant_value = max(
                style_values.items(),
                key=lambda item: item[1],
            )
            periods.append(
                {
                    "period": period,
                    "coverage": coverage,
                    "dominant_style": dominant_style,
                    "dominant_value": dominant_value,
                    "style_values": style_values,
                }
            )
        return sorted(periods, key=lambda item: item["period"])

    def _add_style_stability_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        cfg = self._rule_config
        periods = self._style_history_periods(fund)
        if len(periods) < cfg.style_stability_min_periods:
            return

        latest = periods[-1]
        previous = periods[-2]
        latest_style = str(latest["dominant_style"])
        previous_style = str(previous["dominant_style"])
        latest_value = float(latest["dominant_value"])
        previous_latest_style_value = float(previous["style_values"].get(latest_style, 0.0))
        latest_delta = latest_value - previous_latest_style_value

        if latest_style != previous_style:
            labels.append(
                LabelResult(
                    label_code="style_drift",
                    label_name="风格漂移",
                    category="style_stability",
                    confidence=0.7,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_drift",
                    metric="dominant_style_change",
                    value=f"{previous_style}->{latest_style}",
                    threshold=cfg.style_drift_delta_threshold,
                    source="fund_factor_exposures",
                    message=(
                        f"主导风格从 {previous_style} 切换为 {latest_style}；"
                        f"最新权重 {latest_value:.0%}，上一期同风格权重 "
                        f"{previous_latest_style_value:.0%}。"
                    ),
                )
            )
            if abs(latest_delta) >= cfg.style_recent_shift_threshold:
                labels.append(
                    LabelResult(
                        label_code="style_recent_shift",
                        label_name="近期风格切换",
                        category="style_stability",
                        confidence=0.7,
                        status="observe",
                    )
                )
                evidence.append(
                    EvidenceItem(
                        label_code="style_recent_shift",
                        metric="latest_dominant_style_delta",
                        value=round(latest_delta, 4),
                        threshold=cfg.style_recent_shift_threshold,
                        source="fund_factor_exposures",
                        message=(
                            f"最新一期 {latest_style} 暴露较上一期变化 "
                            f"{latest_delta:.0%}，达到近期切换观察阈值。"
                        ),
                    )
                )
            return

        dominant_values = [
            float(period["style_values"].get(latest_style, 0.0))
            for period in periods
        ]
        value_range = max(dominant_values) - min(dominant_values)
        if value_range <= cfg.style_drift_delta_threshold:
            labels.append(
                LabelResult(
                    label_code="style_stable",
                    label_name="风格稳定",
                    category="style_stability",
                    confidence=0.7,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_stable",
                    metric="dominant_style",
                    value=latest_style,
                    threshold=cfg.style_drift_delta_threshold,
                    source="fund_factor_exposures",
                    message=(
                        f"近 {len(periods)} 期主导风格均为 {latest_style}，"
                        f"主导风格权重波动 {value_range:.0%}，未超过漂移阈值。"
                    ),
                )
            )
        elif abs(latest_delta) >= cfg.style_recent_shift_threshold:
            labels.append(
                LabelResult(
                    label_code="style_recent_shift",
                    label_name="近期风格切换",
                    category="style_stability",
                    confidence=0.7,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_recent_shift",
                    metric="latest_dominant_style_delta",
                    value=round(latest_delta, 4),
                    threshold=cfg.style_recent_shift_threshold,
                    source="fund_factor_exposures",
                    message=(
                        f"主导风格仍为 {latest_style}，但最新一期暴露变化 "
                        f"{latest_delta:.0%}，进入近期变化观察。"
                    ),
                )
            )
