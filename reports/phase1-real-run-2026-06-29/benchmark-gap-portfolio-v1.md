# Benchmark Gap Portfolio Report

run_id: `eecc91372bc249389e43c12674eead93`
benchmark_data_missing_count: 7

## Required Fix Counts

| required_fix | count |
| --- | ---: |
| `complete_benchmark_mapping` | 7 |

## Benchmark Gap Funds

| fund_code | status | roles | return_tags | risk_tags | bench_n | calc_state | required_fix | benchmark |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `000001` | `observe` | active_equity_candidate | long_term_return_strong | drawdown_high, industry_concentration_high | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000011` | `observe` | active_equity_candidate, core_holding_candidate | long_term_return_strong, sharpe_high | industry_concentration_observe | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000021` | `observe` | active_equity_candidate, core_holding_candidate | long_term_return_strong, sharpe_high | industry_concentration_high | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000042` | `observe` | index_tool, low_cost | long_term_return_strong, sharpe_high | industry_concentration_observe | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000082` | `observe` | active_equity_candidate, core_holding_candidate | long_term_return_strong, sharpe_high | industry_concentration_observe | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000124` | `observe` | active_equity_candidate |  | drawdown_high, holding_concentration_high, industry_concentration_observe | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |
| `000368` | `observe` | index_tool, low_cost | long_term_return_strong, sharpe_high | industry_concentration_observe | 0 | `triggered:threshold_met` | `complete_benchmark_mapping` |  |

## Approximate Benchmark Funds

这些基金已合成出 benchmark_returns，但债券组件用的是显式近似源（中债综合财富指数近似中债总/中国债券总/标普中国债券，source 前缀 `approx:`）。其 Alpha/超额收益/信息比率应按“近似基准”解读，不能与精确基准同等看待。

approx_benchmark_count: 21

| fund_code |
| --- |
| `000030` |
| `000056` |
| `000073` |
| `000165` |
| `000294` |
| `000308` |
| `000309` |
| `000328` |
| `000404` |
| `000457` |
| `000480` |
| `000524` |
| `000549` |
| `000566` |
| `000577` |
| `000584` |
| `000592` |
| `000594` |
| `000603` |
| `000619` |
| `000649` |
