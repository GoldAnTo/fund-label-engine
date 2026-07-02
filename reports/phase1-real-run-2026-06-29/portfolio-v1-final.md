# Portfolio Final Accepted Report

run_id: `50f9b72de7104761869dc3e86e8a36d2`
mode: `accepted`
rule_version: `v1`
objective: `core_satellite_equity_pool`
config_version: `v1`

## Draft Weights

| fund_code | bucket | draft_weight_pct | optimized_weight_pct | max_weight_pct | score | roles | risk_tags |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `000279` | `core` | 6.79 | 6.96 | 8.00 | 66.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_deep_value | tracking_error_high |
| `000308` | `core` | 6.38 | 6.00 | 6.00 | 62.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | industry_concentration_high, tracking_error_high |
| `000577` | `core` | 6.38 | 6.00 | 6.00 | 62.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha, style_quality_growth | holding_concentration_high, industry_concentration_high, tracking_error_high |
| `000520` | `core` | 6.27 | 6.43 | 8.00 | 61.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000172` | `core` | 6.17 | 6.33 | 8.00 | 60.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, low_cost, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000136` | `core` | 5.76 | 5.90 | 6.00 | 56.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | holding_concentration_high, tracking_error_high |
| `000457` | `core` | 5.66 | 5.80 | 8.00 | 55.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000433` | `satellite` | 4.73 | 4.85 | 5.00 | 46.00 | defensive_anchor, low_cost, satellite_alpha | tracking_error_high |
| `000573` | `satellite` | 4.73 | 4.85 | 5.00 | 46.00 | defensive_anchor, low_cost, satellite_alpha | tracking_error_high |
| `000398` | `satellite` | 4.22 | 4.32 | 5.00 | 41.00 | defensive_anchor, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000073` | `satellite` | 3.81 | 3.90 | 5.00 | 37.00 | defensive_anchor, satellite_alpha, style_quality_growth | holding_concentration_high, industry_concentration_high, tracking_error_high |
| `000006` | `core` | 3.70 | 3.80 | 8.00 | 36.00 | active_equity_candidate, core_holding_candidate, defensive_anchor | tracking_error_high |
| `000219` | `satellite` | 3.70 | 3.80 | 5.00 | 36.00 | defensive_anchor, satellite_alpha | holding_concentration_high, industry_concentration_observe, tracking_error_high |
| `000017` | `satellite` | 3.19 | 3.00 | 3.00 | 49.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |
| `000311` | `index_tool` | 3.19 | 3.00 | 3.00 | 40.00 | defensive_anchor, index_tool, low_cost, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000312` | `index_tool` | 3.19 | 3.00 | 3.00 | 40.00 | defensive_anchor, index_tool, low_cost, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000313` | `index_tool` | 3.19 | 3.00 | 3.00 | 35.00 | defensive_anchor, index_tool, satellite_alpha | industry_concentration_observe, tracking_error_high |
| `000404` | `satellite` | 3.19 | 3.00 | 3.00 | 54.00 | active_equity_candidate, core_holding_candidate, defensive_anchor, satellite_alpha, style_quality_growth | industry_concentration_high, tracking_error_high, volatility_high |
| `000531` | `satellite` | 2.98 | 3.00 | 3.00 | 29.00 | defensive_anchor, satellite_alpha, style_quality_growth | holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |
| `000663` | `core` | 2.67 | 2.74 | 6.00 | 26.00 | active_equity_candidate, core_holding_candidate, defensive_anchor | holding_concentration_high, industry_concentration_high, tracking_error_high |
| `000176` | `index_tool` | 2.16 | 2.21 | 3.00 | 21.00 | defensive_anchor, index_tool, low_cost | industry_concentration_observe, tracking_error_high |
| `000368` | `index_tool` | 2.16 | 2.21 | 3.00 | 21.00 | defensive_anchor, index_tool, low_cost | industry_concentration_observe, tracking_error_high |
| `000512` | `index_tool` | 2.16 | 2.21 | 3.00 | 21.00 | defensive_anchor, index_tool, low_cost | industry_concentration_observe, tracking_error_high |
| `000656` | `index_tool` | 2.16 | 2.21 | 3.00 | 21.00 | defensive_anchor, index_tool, low_cost | industry_concentration_observe, tracking_error_high |
| `000566` | `satellite` | 1.13 | 1.16 | 5.00 | 11.00 | defensive_anchor | industry_concentration_high, tracking_error_high |
| `000059` | `index_tool` | 0.10 | 0.11 | 3.00 | 1.00 | index_tool, low_cost | drawdown_high, industry_concentration_high, tracking_error_high |
| `000083` | `satellite` | 0.10 | 0.11 | 1.00 | 1.00 | active_equity_candidate | drawdown_high, industry_concentration_high, tracking_error_high |
| `000522` | `satellite` | 0.10 | 0.11 | 1.00 | 1.00 | active_equity_candidate, satellite_alpha, style_quality_growth | drawdown_high, holding_concentration_high, industry_concentration_high, tracking_error_high, volatility_high |

## Excluded

| fund_code | reasons |
| --- | --- |
| `000001` | not_signed_off |
| `000011` | not_signed_off |
| `000020` | not_signed_off |
| `000021` | not_signed_off |
| `000029` | not_signed_off |
| `000030` | not_signed_off |
| `000031` | not_signed_off |
| `000039` | not_signed_off |
| `000042` | not_signed_off |
| `000056` | not_signed_off |
| `000057` | not_signed_off |
| `000061` | not_signed_off |
| `000063` | not_signed_off |
| `000066` | not_signed_off |
| `000082` | not_signed_off |
| `000117` | not_signed_off |
| `000120` | not_signed_off |
| `000124` | not_signed_off |
| `000126` | not_signed_off |
| `000127` | not_signed_off |
| `000165` | not_signed_off |
| `000166` | not_signed_off |
| `000167` | not_signed_off |
| `000173` | not_signed_off |
| `000195` | not_signed_off |
| `000196` | not_signed_off |
| `000199` | not_signed_off |
| `000209` | not_signed_off |
| `000214` | not_signed_off |
| `000220` | not_signed_off |
| `000241` | not_signed_off |
| `000242` | not_signed_off |
| `000251` | not_signed_off |
| `000263` | not_signed_off |
| `000264` | not_signed_off |
| `000270` | not_signed_off |
| `000273` | not_signed_off |
| `000294` | not_signed_off |
| `000309` | not_signed_off |
| `000314` | not_signed_off |
| `000326` | not_signed_off |
| `000327` | not_signed_off |
| `000328` | not_signed_off |
| `000336` | not_signed_off |
| `000339` | not_signed_off |
| `000354` | not_signed_off |
| `000362` | not_signed_off |
| `000363` | not_signed_off |
| `000373` | not_signed_off |
| `000376` | not_signed_off |
| `000390` | not_signed_off |
| `000408` | not_signed_off |
| `000409` | not_signed_off |
| `000411` | not_signed_off |
| `000418` | not_signed_off |
| `000423` | not_signed_off |
| `000431` | not_signed_off |
| `000432` | not_signed_off |
| `000452` | not_signed_off |
| `000458` | not_signed_off |
| `000459` | not_signed_off |
| `000462` | not_signed_off |
| `000471` | not_signed_off |
| `000477` | not_signed_off |
| `000478` | not_signed_off |
| `000480` | not_signed_off |
| `000496` | not_signed_off |
| `000511` | not_signed_off |
| `000513` | not_signed_off |
| `000523` | not_signed_off |
| `000524` | not_signed_off |
| `000527` | not_signed_off |
| `000529` | not_signed_off |
| `000530` | not_signed_off |
| `000532` | not_signed_off |
| `000534` | not_signed_off |
| `000535` | not_signed_off |
| `000538` | not_signed_off |
| `000541` | not_signed_off |
| `000545` | not_signed_off |
| `000547` | not_signed_off |
| `000549` | not_signed_off |
| `000550` | not_signed_off |
| `000551` | not_signed_off |
| `000554` | not_signed_off |
| `000567` | not_signed_off |
| `000574` | not_signed_off |
| `000584` | not_signed_off |
| `000586` | not_signed_off |
| `000587` | not_signed_off |
| `000589` | not_signed_off |
| `000591` | not_signed_off |
| `000592` | not_signed_off |
| `000594` | not_signed_off |
| `000595` | not_signed_off |
| `000596` | not_signed_off |
| `000598` | not_signed_off |
| `000601` | not_signed_off |
| `000603` | not_signed_off |
| `000609` | not_signed_off |
| `000612` | not_signed_off |
| `000619` | not_signed_off |
| `000628` | not_signed_off |
| `000634` | not_signed_off |
| `000646` | not_signed_off |
| `000649` | not_signed_off |
| `000652` | not_signed_off |
| `000654` | not_signed_off |
| `000679` | not_signed_off |
| `000684` | not_signed_off |
| `100038` | manual_exclude |
| `100039` | manual_exclude |
| `100056` | manual_exclude |
| `100060` | manual_exclude |
