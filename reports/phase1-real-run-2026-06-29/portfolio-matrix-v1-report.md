# Portfolio Matrix v1 Report

run_id: `50f9b72de7104761869dc3e86e8a36d2`
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
| `observe` | 110 |
| `eligible` | 28 |
| `review_required` | 4 |

## Portfolio Roles

| item | count |
| --- | ---: |
| `active_equity_candidate` | 77 |
| `defensive_anchor` | 71 |
| `core_holding_candidate` | 65 |
| `satellite_alpha` | 54 |
| `low_cost` | 27 |
| `index_tool` | 14 |
| `style_quality_growth` | 9 |
| `needs_review` | 4 |
| `style_deep_value` | 2 |
| `style_dividend_steady` | 2 |
| `style_high_dividend_financial` | 1 |

## Role Quality Checks

| check | count | examples | note |
| --- | ---: | --- | --- |
| `eligible_with_allocation_risk_review` | 13 | `000017`, `000059`, `000073`, `000083`, `000136`, `000219`, `000308`, `000404` | Eligible means data-ready, but these funds still need risk sizing review. |
| `core_candidate_with_core_risk_review` | 9 | `000017`, `000328`, `000354`, `000404`, `000411`, `000524`, `000592`, `000601` | Core candidates with high beta/drawdown/volatility tags should not be treated as final core holdings. |
| `active_equity_waiting_style_rule` | 53 | `000001`, `000011`, `000020`, `000021`, `000029`, `000031`, `000063`, `000082` | Active equity candidates still blocked by pending style rules. |
| `benchmark_data_missing` | 54 | `000001`, `000011`, `000020`, `000021`, `000039`, `000042`, `000063`, `000066` | Relative labels should not be trusted for these funds until benchmark data is completed. |

## Style Pending Reasons

| reason | count |
| --- | ---: |
| `style_weight_below_formal_threshold` | 95 |

## Watch Reasons

| item | count |
| --- | ---: |
| `style_pending_rule_definition` | 95 |
| `benchmark_data_missing` | 54 |
| `style_exposure_observe` | 6 |
| `return_window_insufficient` | 4 |
| `sector_mapping_insufficient` | 1 |

## Risk Tags

| item | count |
| --- | ---: |
| `tracking_error_high` | 88 |
| `industry_concentration_high` | 86 |
| `industry_concentration_observe` | 42 |
| `drawdown_high` | 29 |
| `volatility_high` | 23 |
| `holding_concentration_high` | 20 |

## Blocking Reasons

| item | count |
| --- | ---: |
| `data_insufficient` | 4 |
| `manual_review_action` | 4 |
| `manual_review_required` | 4 |

## Eligible Funds

| fund_code | status | roles | style_tags | return_tags | risk_tags | watch/blocking |
| --- | --- | --- | --- | --- | --- | --- |
| `000006` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | tracking_error_high |  |
| `000017` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000059` | `eligible` | index_tool, low_cost |  |  | drawdown_high, industry_concentration_high, tracking_error_high |  |
| `000073` | `eligible` | defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high |  |
| `000083` | `eligible` | active_equity_candidate |  |  | drawdown_high, industry_concentration_high, tracking_error_high |  |
| `000136` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, tracking_error_high |  |
| `000172` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000176` | `eligible` | defensive_anchor, index_tool, low_cost |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000219` | `eligible` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_observe, tracking_error_high |  |
| `000279` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_deep_value | deep_value | alpha_positive, excess_return_strong, information_ratio_high, sharpe_high | tracking_error_high |  |
| `000308` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high |  |
| `000311` | `eligible` | defensive_anchor, index_tool, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000312` | `eligible` | defensive_anchor, index_tool, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000313` | `eligible` | defensive_anchor, index_tool, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000368` | `eligible` | defensive_anchor, index_tool, low_cost |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000398` | `eligible` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000404` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high, volatility_high |  |
| `000433` | `eligible` | defensive_anchor, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | tracking_error_high |  |
| `000457` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000512` | `eligible` | defensive_anchor, index_tool, low_cost |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000520` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000522` | `eligible` | active_equity_candidate, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | drawdown_high, holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000531` | `eligible` | defensive_anchor, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |  |
| `000566` | `eligible` | defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high |  |
| `000573` | `eligible` | defensive_anchor, low_cost, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | tracking_error_high |  |
| `000577` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha, style_quality_growth | quality_growth | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high |  |
| `000656` | `eligible` | defensive_anchor, index_tool, low_cost |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high |  |
| `000663` | `eligible` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high |  |

## Observe / Review Work Queue

| fund_code | status | roles | style_tags | return_tags | risk_tags | watch/blocking |
| --- | --- | --- | --- | --- | --- | --- |
| `000001` | `observe` | active_equity_candidate |  | long_term_return_strong | drawdown_high, industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000011` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000020` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000021` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000029` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000030` | `observe` | defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000031` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | holding_concentration_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000039` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_observe, volatility_high | benchmark_data_missing, style_pending_rule_definition |
| `000042` | `observe` | index_tool, low_cost |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing |
| `000056` | `observe` |  |  |  | drawdown_high, industry_concentration_high, tracking_error_high | style_exposure_observe |
| `000057` | `observe` |  |  |  | drawdown_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000061` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000063` | `observe` | active_equity_candidate |  | long_term_return_strong, sharpe_high | drawdown_high, industry_concentration_observe, volatility_high | benchmark_data_missing, style_pending_rule_definition |
| `000066` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_high, volatility_high | benchmark_data_missing, style_pending_rule_definition |
| `000082` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000117` | `observe` | active_equity_candidate, core_holding_candidate |  |  | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000120` | `observe` | defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000124` | `observe` | active_equity_candidate |  |  | drawdown_high, holding_concentration_high, industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000126` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha |  | alpha_positive, excess_return_strong, information_ratio_high, long_term_return_strong, sharpe_high | industry_concentration_high, tracking_error_high | style_pending_rule_definition |
| `000127` | `observe` | active_equity_candidate, core_holding_candidate, style_dividend_steady | dividend_steady | long_term_return_strong, sharpe_high |  | benchmark_data_missing |
| `000165` | `observe` | active_equity_candidate, core_holding_candidate, defensive_anchor |  | alpha_positive, long_term_return_strong, sharpe_high | industry_concentration_observe, tracking_error_high | style_pending_rule_definition |
| `000166` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_high, volatility_high | benchmark_data_missing, style_pending_rule_definition |
| `000167` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000173` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000195` | `observe` | low_cost |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000196` | `observe` |  |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing, style_pending_rule_definition |
| `000199` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing |
| `000209` | `observe` | active_equity_candidate, core_holding_candidate |  | long_term_return_strong, sharpe_high | industry_concentration_high | benchmark_data_missing, style_pending_rule_definition |
| `000214` | `observe` | active_equity_candidate, core_holding_candidate, low_cost |  | long_term_return_strong, sharpe_high | industry_concentration_observe | benchmark_data_missing |
| `000220` | `observe` | active_equity_candidate |  |  | drawdown_high, holding_concentration_high, industry_concentration_high, tracking_error_high | style_pending_rule_definition |
