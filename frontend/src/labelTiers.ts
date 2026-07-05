import type { FundLabel } from "./api";

// 风格标签（正式展示）
const STYLE_OFFICIAL_CODES = new Set([
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
]);

// 相对基准标签（需要 relative_ready 才正式展示）
const RELATIVE_CODES = new Set([
  "alpha_positive",
  "alpha_negative",
  "beta_high",
  "beta_low",
  "excess_return_positive",
  "excess_return_negative",
  "information_ratio_high",
  "excess_return_strong",
  "tracking_error_high",
  "benchmark_data_missing",
]);

// 风格观察信号
const STYLE_OBSERVE_CODES = new Set([
  "style_stable",
  "style_drift",
  "style_recent_shift",
  "style_balanced",
  "style_exposure_observe",
  "style_exposure_low_coverage",
  "style_exposure_scope_not_applicable",
  "style_pending_rule_definition",
  "style_unlabeled_stock_factors_missing",
  "sector_mapping_insufficient",
]);

// 数据层标签（不正式展示，仅用于数据处理和门禁）
const DATA_ONLY_CODES = new Set([
  "data_sufficient",
  "data_insufficient",
  "fee_low",
  "fee_high",
  "fund_size_small",
  "fund_size_moderate",
  "manager_tenure_long",
  "volatility_high",
  "volatility_low",
  "drawdown_high",
  "sharpe_high",
  "long_term_return_strong",
  "return_window_insufficient",
  "holding_concentration_high",
  "industry_concentration_high",
  "industry_concentration_observe",
  "industry_diversified",
  "equity_position_high",
  "manual_review_required",
]);

export type LabelTier = "style" | "relative" | "observe" | "data_only" | "other";

export function labelTier(label: FundLabel, relativeReady: boolean): LabelTier {
  if (STYLE_OFFICIAL_CODES.has(label.label_code)) return "style";
  if (RELATIVE_CODES.has(label.label_code)) return relativeReady ? "relative" : "other";
  if (STYLE_OBSERVE_CODES.has(label.label_code)) return "observe";
  if (DATA_ONLY_CODES.has(label.label_code)) return "data_only";
  return "other";
}

export function tierTitle(tier: LabelTier) {
  const titles: Record<LabelTier, string> = {
    style: "风格标签",
    relative: "相对基准",
    observe: "风格观察",
    data_only: "数据层标签（不展示）",
    other: "其它标签",
  };
  return titles[tier];
}

// 是否在基金报告页正式展示该分层
export function shouldDisplayTier(tier: LabelTier): boolean {
  return tier !== "data_only" && tier !== "other";
}
