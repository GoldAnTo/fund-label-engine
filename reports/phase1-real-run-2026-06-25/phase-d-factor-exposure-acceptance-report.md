# Phase D 验收报告：基金级因子暴露聚合 A/B/C 固化

## 1. 验收对象

- commit: `4de63a4 feat: add fund factor exposure aggregation`
- run_id: `9c01103530064984b41fe004585414e0`
- run_at: `2026-06-25T06:58:48+00:00`
- rule_version: `v1`
- run_status: `succeeded`
- 输入库: `/tmp/fle-run/source.sqlite`
- 输出库: `/tmp/fle-run/output-v1-factor-exposures.sqlite`
- processed: **142**

## 2. 暴露生成验收

- 142 只是否全部生成暴露：**是**
- 生成暴露基金数：**142**
- 生成暴露行数：**1420**

| factor_code | fund_count | avg | min | max | avg_coverage | min_coverage | max_coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deep_value_weight` | 142 | 0.126208 | 0.0 | 0.8067 | 0.870681 | 0.5402 | 0.9521 |
| `dividend_steady_weight` | 142 | 0.163231 | 0.0 | 0.7401 | 0.870681 | 0.5402 | 0.9521 |
| `dividend_yield_weighted` | 142 | 0.018801 | 0.00246 | 0.049311 | 0.753496 | 0.3624 | 0.9298 |
| `factor_coverage_weight` | 142 | 0.870681 | 0.5402 | 0.9521 | 0.870681 | 0.5402 | 0.9521 |
| `pb_weighted` | 142 | 8.756764 | 0.138744 | 35.847306 | 0.870681 | 0.5402 | 0.9521 |
| `profit_growth_weighted` | 142 | 0.931643 | -0.739366 | 13.429338 | 0.870681 | 0.5402 | 0.9521 |
| `quality_growth_weight` | 142 | 0.16102 | 0.0 | 0.597 | 0.870681 | 0.5402 | 0.9521 |
| `revenue_growth_weighted` | 142 | 0.495844 | 0.020311 | 2.816529 | 0.87063 | 0.5402 | 0.9521 |
| `roe_weighted` | 142 | 0.115935 | -0.011247 | 0.213767 | 0.870119 | 0.5402 | 0.9521 |
| `valuation_percentile_weighted` | 142 | 0.59427 | 0.090336 | 0.966666 | 0.870535 | 0.5402 | 0.9521 |

### coverage 分桶

| bucket | fund_count |
|---|---:|
| `50%-70%` | 6 |
| `>=70%` | 136 |

## 3. 风格标签变化

| label_code | status | before | after | delta |
|---|---|---:|---:|---:|
| `deep_value` | active | 3 | 3 | 0 |
| `dividend_steady` | active | 3 | 3 | 0 |
| `quality_growth` | active | 9 | 9 | 0 |
| `style_pending_rule_definition` | observe | 128 | 128 | 0 |

### 风格证据来源

| source | evidence_count |
|---|---:|
| `fund_factor_exposures` | 143 |

## 4. 抽样核对

| fund_code | fund_name | coverage | qg | deep_value | dividend | labels | 核对结论 |
|---|---|---:|---:|---:|---:|---|---|
| `000006` | 西部利得量化成长混合A | 83.52% | 3.18% | 28.40% | 20.76% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `000017` | 财通可持续混合 | 94.65% | 55.42% | 0.10% | 0.67% | `quality_growth` | 合理：证据来自 fund_factor_exposures，标签与风格权重阈值一致。 |
| `000251` | 工银金融地产混合A | 88.40% | 4.85% | 80.67% | 74.01% | `deep_value, dividend_steady` | 合理：证据来自 fund_factor_exposures，标签与风格权重阈值一致。 |
| `000390` | 华商优势行业混合A | 87.92% | 36.39% | 0.00% | 0.00% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `000433` | 安信鑫发优选混合A | 81.59% | 7.58% | 22.19% | 25.94% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `000520` | 上银新兴价值成长混合A | 93.17% | 12.46% | 22.87% | 39.55% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `000601` | 华宝创新优选混合 | 92.92% | 32.02% | 2.21% | 3.20% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `000656` | 前海开源沪深300指数A | 93.10% | 14.02% | 28.31% | 34.62% | `style_pending_rule_definition` | 合理：覆盖充足但三类风格权重未达阈值，只作观察。 |
| `100038` | 富国沪深300指数增强A | 93.18% | 7.21% | 41.06% | 44.88% | `deep_value` | 合理：证据来自 fund_factor_exposures，标签与风格权重阈值一致。 |

## 5. 正式结论边界

| 范围 | 标签 | 条件/说明 |
|---|---|---|
| 可作为正式结论 | `quality_growth, deep_value, dividend_steady` | 当前实现只要数据 gate 通过且风格权重达阈值即 active；Phase D 建议下一步加入 coverage>=70% 可信度门槛。 |
| 观察/边界结论 | `style_pending_rule_definition` | 表示已计算基金级暴露但三类风格权重均未达阈值；不应解读为没有风格，只能说明当前规则未命中。 |
| 暂不输出正式结论 | `低覆盖风格标签` | 当前尚未实现 coverage 门槛；验收建议低于 50% 不出正式风格标签，50%-70% 只观察。 |

## 6. 验收结论

- A/B/C 实现已提交并固化。
- 后端测试 `104 passed`，前端 `npm run build` 通过。
- 142 只 v1 正式样本全部生成基金级因子暴露。
- 风格标签证据来源已切到 `fund_factor_exposures`。
- 下一步不继续扩功能，优先做暴露质量门槛：`<50%` 不出正式标签，`50%-70%` 观察，`>=70%` 允许正式标签。
