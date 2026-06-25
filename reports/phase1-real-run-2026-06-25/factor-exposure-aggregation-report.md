# Fund Factor Exposure Aggregation v1 验证报告

- run_id: `9c01103530064984b41fe004585414e0`
- processed: **142**
- 输出库：`/tmp/fle-run/output-v1-factor-exposures.sqlite`

## 1. 聚合覆盖

- 生成基金级因子暴露基金数：**142**
- 生成暴露行数：**1420**

| factor_code | fund_count | avg_value | avg_coverage |
|---|---:|---:|---:|
| `deep_value_weight` | 142 | 0.126208 | 0.870681 |
| `dividend_steady_weight` | 142 | 0.163231 | 0.870681 |
| `dividend_yield_weighted` | 142 | 0.018801 | 0.753496 |
| `factor_coverage_weight` | 142 | 0.870681 | 0.870681 |
| `pb_weighted` | 142 | 8.756764 | 0.870681 |
| `profit_growth_weighted` | 142 | 0.931643 | 0.870681 |
| `quality_growth_weight` | 142 | 0.16102 | 0.870681 |
| `revenue_growth_weighted` | 142 | 0.495844 | 0.87063 |
| `roe_weighted` | 142 | 0.115935 | 0.870119 |
| `valuation_percentile_weighted` | 142 | 0.59427 | 0.870535 |

## 2. 风格标签已切到基金级暴露证据

| source | evidence_count |
|---|---:|
| `fund_factor_exposures` | 143 |

| label_code | fund_count |
|---|---:|
| `style_pending_rule_definition` | 128 |
| `quality_growth` | 9 |
| `dividend_steady` | 3 |
| `deep_value` | 3 |

## 3. 结论

- v1 正式 142 只基金全部生成了 `fund_factor_exposures`。
- 风格标签 evidence source 已统一变为 `fund_factor_exposures`，不再在标签阶段临时重复聚合。
- 旧样本库和无暴露库仍保留 stock factor fallback。
- 暴露表包含 coverage、holding_total_weight、stock_count、covered_stock_count、as_of_date，后续可直接用于报告和 API。
