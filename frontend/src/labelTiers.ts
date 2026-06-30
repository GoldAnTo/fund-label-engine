import type { FundLabel } from "./api";

const OFFICIAL_CODES = new Set([
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
]);

const RELATIVE_CODES = new Set([
  "alpha_positive",
  "alpha_negative",
  "beta_high",
  "beta_low",
  "excess_return_positive",
  "excess_return_negative",
  "information_ratio_high",
]);

const OBSERVE_CODES = new Set([
  "industry_concentration_high",
  "industry_concentration_observe",
  "industry_diversified",
  "holding_concentration_high",
  "equity_position_high",
  "style_stable",
  "style_drift",
  "style_recent_shift",
  "style_exposure_observe",
  "style_exposure_low_coverage",
]);

const CALIBRATION_CODES = new Set([
  "deep_value",
  "quality_growth",
  "dividend_steady",
  "high_dividend_financial",
  "consumer_quality",
  "style_pending_rule_definition",
  "style_unlabeled_stock_factors_missing",
  "sector_mapping_insufficient",
]);

export type LabelTier = "official" | "observe" | "calibration" | "other";

export function labelTier(label: FundLabel, relativeReady: boolean): LabelTier {
  if (OFFICIAL_CODES.has(label.label_code)) return "official";
  if (RELATIVE_CODES.has(label.label_code)) return relativeReady ? "official" : "other";
  if (OBSERVE_CODES.has(label.label_code)) return "observe";
  if (CALIBRATION_CODES.has(label.label_code)) return "calibration";
  return "other";
}

export function tierTitle(tier: LabelTier) {
  const titles: Record<LabelTier, string> = {
    official: "正式结论",
    observe: "观察信号",
    calibration: "待校准信号",
    other: "其它标签",
  };
  return titles[tier];
}
