# Phase1 阈值校准落地对比

- before run_id: `6e0ac4d1d2414ce19ebae662a7053129`
- after run_id: `6a19ff73456546718f365f7e849559f0`
- 调整内容：行业集中分层；fee_low 从 1.5% 收紧到 1.2%。

## 1. 核心变化

| label_code | before | after | delta |
|---|---:|---:|---:|
| `industry_concentration_high` | 137 | 86 | -51 |
| `industry_concentration_observe` | 0 | 42 | 42 |
| `fee_low` | 136 | 27 | -109 |
| `fee_high` | 2 | 2 | 0 |
| `data_sufficient` | 142 | 142 | 0 |
| `data_insufficient` | 0 | 0 | 0 |

结论：行业集中从“几乎全是高集中”变成“高集中 + 观察层”；fee_low 从 136 只降到 27 只，区分度明显提升。

## 2. 10 只样本影响

| fund_code | fund_name | removed_labels | added_labels |
|---|---|---|---|
| `000006` | 西部利得量化成长混合A | fee_low | - |
| `000017` | 财通可持续混合 | fee_low | - |
| `000251` | 工银金融地产混合A | fee_low | - |
| `000273` | 华润元大安鑫灵活配置混合A | fee_low | - |
| `000373` | 华安中证细分医药ETF联接A | - | - |
| `000411` | 景顺长城优质成长股票A | fee_low | - |
| `000628` | 大成高鑫股票A | fee_low, industry_concentration_high | industry_concentration_observe |
| `100038` | 富国沪深300指数增强A | industry_concentration_high | industry_concentration_observe |

## 3. 解释

- `industry_concentration_high` 现在只表示第一大行业 ≥60%，可以作为正式高集中。
- `industry_concentration_observe` 表示第一大行业 45%~60%，仅观察展示。
- `fee_low` 现在要求综合费率 ≤1.2%，不再把 1.3%~1.5% 的主动权益基金普遍归为低费率。
- 收益风险和风格标签本轮不动，避免一次改太多导致验收困难。
