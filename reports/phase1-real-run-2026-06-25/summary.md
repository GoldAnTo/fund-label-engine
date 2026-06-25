# Phase1 真实基金标签跑批结果

- run_id: `3cb9bd6a2b6d41f28f7d936de86aa065`
- run_at: `2026-06-25T01:41:43+00:00`
- status: `succeeded`
- processed_funds: 168
- output_db: `/tmp/fle-run/output.sqlite`

## 计算状态分布

| state | count |
|---|---:|
| not_triggered | 2176 |
| triggered | 1298 |
| not_computed | 222 |

## 标签触发分布

| label_code | fund_count |
|---|---:|
| data_sufficient | 154 |
| fee_low | 152 |
| style_pending_rule_definition | 141 |
| industry_concentration_high | 131 |
| manager_tenure_long | 122 |
| equity_position_high | 120 |
| sharpe_high | 119 |
| long_term_return_strong | 112 |
| fund_size_moderate | 64 |
| fund_size_small | 42 |
| drawdown_high | 30 |
| volatility_high | 23 |
| holding_concentration_high | 20 |
| volatility_low | 17 |
| data_insufficient | 14 |
| manual_review_required | 14 |
| return_window_insufficient | 12 |
| industry_diversified | 11 |
| quality_growth | 9 |
| dividend_steady | 3 |
| deep_value | 2 |

## 无法计算原因分布

| reason_code | calculation_count |
|---|---:|
| stock_holdings_missing | 84 |
| return_window_insufficient | 60 |
| industry_missing | 28 |
| fee_structure_missing | 24 |
| equity_position_missing | 14 |
| manager_missing | 12 |

## 文件说明

- `phase1_real_run.xlsx`: 汇总 Excel，含逐基金总览、标签、证据、计算状态、无法计算原因。
- `fund_overview.csv`: 每只基金一行，快速看已触发/未触发/无法计算标签。
- `label_calculations.csv`: 每只基金每个标签一行，核心字段是 state 和 reason_code。
- `not_computed_by_fund.csv`: 只看无法计算的标签和原因。
- `label_evidence.csv`: 标签证据明细。

