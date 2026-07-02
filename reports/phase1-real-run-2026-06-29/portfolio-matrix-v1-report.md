# Portfolio Matrix v1 Report

run_id: `349ee38559864bdd8b7968532452ba03`
rule_version: `v1`
portfolio_objective: `core_satellite_equity_pool`
portfolio_config_version: `v1`
total_count: 142

## How To Read

- `eligible`: data-ready for role screening; still obey risk tags before sizing.
- `observe`: has useful labels, but still has watch reasons that need calibration or source completion.
- `review_required`: blocked by missing data or manual review.

## Allocation Status

| item | count |
| --- | ---: |
| `observe` | 133 |
| `eligible` | 9 |

## Portfolio Roles

| item | count |
| --- | ---: |
| `defensive_anchor` | 86 |
| `active_equity_candidate` | 79 |
| `satellite_alpha` | 68 |
| `core_holding_candidate` | 66 |
| `low_cost` | 27 |
| `index_tool` | 14 |
| `style_quality_growth` | 9 |
| `style_deep_value` | 3 |
| `style_dividend_steady` | 2 |
| `style_high_dividend_financial` | 1 |

## Role Quality Checks

| check | count | examples | note |
| --- | ---: | --- | --- |
| `eligible_with_allocation_risk_review` | 6 | `000017`, `000251`, `000354`, `000411`, `000522`, `000531` | Eligible means data-ready, but these funds still need risk sizing review. |
| `core_candidate_with_core_risk_review` | 10 | `000017`, `000328`, `000354`, `000404`, `000411`, `000524`, `000592`, `000601` | Core candidates with high beta/drawdown/volatility tags should not be treated as final core holdings. |
| `active_equity_waiting_style_rule` | 66 | `000001`, `000006`, `000011`, `000020`, `000021`, `000029`, `000031`, `000063` | Active equity candidates still blocked by pending style rules. |
| `benchmark_data_missing` | 28 | `000001`, `000011`, `000021`, `000030`, `000042`, `000056`, `000073`, `000082` | Relative labels should not be trusted for these funds until benchmark data is completed. |

## Watch Reasons

| item | count |
| --- | ---: |
| `style_pending_rule_definition` | 122 |
| `benchmark_data_missing` | 28 |
| `style_exposure_observe` | 6 |
| `sector_mapping_insufficient` | 1 |

## Risk Tags

| item | count |
| --- | ---: |
| `tracking_error_high` | 114 |
| `industry_concentration_high` | 86 |
| `industry_concentration_observe` | 42 |
| `drawdown_high` | 30 |
| `volatility_high` | 26 |
| `holding_concentration_high` | 20 |
| `beta_high` | 1 |

## Blocking Reasons

| item | count |
| --- | ---: |
| (none) | 0 |

## Eligible Funds

| fund_code | status | roles | style_tags | return_tags | risk_tags | watch/blocking |
| --- | --- | --- | --- | --- | --- | --- |
| `000017` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000127` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, style_dividend_steady | dividend_steady | alpha_positive, long_term_return_strong, sharpe_high | tracking_error_high |  |
| `000251` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, style_deep_value, style_high_dividend_financial | deep_value, high_dividend_financial | excess_return_strong | holding_concentration_high, industry_concentration_high, tracking_error_high |  |
| `000279` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_deep_value | deep_value | alpha_positive, excess_return_strong, information_ratio_high, sharpe_high | tracking_error_high |  |
| `000354` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000411` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high, volatility_high |  |
| `000522` | `eligible` | active_equity_candidate, style_quality_growth | quality_growth | alpha_positive, long_term_return_strong, sharpe_high | drawdown_high, holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000531` | `eligible` | defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `100038` | `eligible` | defensive_anchor, index_tool, low_cost, style_deep_value | deep_value | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |

## Observe / Review Work Queue

| fund_code | status | roles | style_tags | return_tags | risk_tags | watch/blocking |
| --- | --- | --- | --- | --- | --- | --- |
| `000001` | `observe` | active_equity_candidate |  | long_term_return_strong | drawdown_high, industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000006` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | tracking_error_high | style_pending_rule_definition |
| `000011` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000020` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000021` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000029` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000030` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000031` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000039` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high, volatility_high | style_pending_rule_definition |
| `000042` | `observe` | index_tool, low_cost |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000056` | `observe` |  |  |  | drawdown_high, industry_concentration_high | benchmark_data_missing, style_exposure_observe |
| `000057` | `observe` |  |  |  | drawdown_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000059` | `observe` | index_tool, low_cost |  |  | drawdown_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000061` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000063` | `observe` | active_equity_candidate |  | excess_return_strong, long_term_return_strong, sharpe_high | beta_high, drawdown_high, industry_concentration_observe, tracking_error_high, volatility_high | style_pending_rule_definition |
| `000066` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high, volatility_high | style_pending_rule_definition |
| `000073` | `observe` | style_quality_growth | quality_growth | long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high | benchmark_data_missing |
| `000082` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000083` | `observe` | active_equity_candidate |  |  | drawdown_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000117` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000120` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000124` | `observe` | active_equity_candidate |  |  | drawdown_high, holding_concentration_high, industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000126` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000136` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000165` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000166` | `observe` | satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high, volatility_high | style_pending_rule_definition |
| `000167` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000172` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000173` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000176` | `observe` | defensive_anchor, index_tool, low_cost |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
