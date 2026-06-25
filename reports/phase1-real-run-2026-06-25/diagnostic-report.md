# Phase1 真实跑批诊断报告

- run_id: `586a245ffe3c4b878531771a4708419f`
- run_at: `2026-06-25T01:57:53+00:00`
- status: `succeeded`
- processed_funds: **161**
- output_db: `/tmp/fle-run/output-canonical.sqlite`
- source_db: `/tmp/fle-run/source.sqlite`

## 1. 结论先行

Phase1 已经不是“能不能跑”的阶段，而是进入“结果是否可靠、哪些能正式展示”的验收阶段。
本次 161 只基金共产生 1329 条触发标签、3542 条标签计算状态。

核心判断：

- **可进入 v1 正式展示**：数据质量、费率、规模、经理任期、已补足 NAV 的收益风险标签。
- **建议观察展示**：行业集中、持仓集中、权益仓位；原因是部分基金存在穿透/行业口径问题，需继续验收。
- **暂时观察/待校准**：深度价值、质量成长、红利稳健；原因是触发数量少且阈值经过 phase1 样本下调，不能直接作为强结论。
- **主要数据缺口**：收益窗口已收敛到 0；剩余主要是 ETF 联接/低股票仓位穿透问题，以及少量费率、持仓/行业真实缺口。

## 2. 计算状态总览

| state | calculation_count | fund_count |
|---|---:|---:|
| not_triggered | 2115 | 161 |
| triggered | 1304 | 161 |
| not_computed | 123 | 25 |

解读：`not_computed` 不是规则未命中，而是前置数据不足；后续应优先减少这一类。

## 3. 标签触发分布与可靠性判断

| label_code | category | status | fund_count | 覆盖率 | 初步判断 |
|---|---|---|---:|---:|---|
| `fee_low` | fee_size | active,observe | 152 | 94.4% | 可正式展示 |
| `style_pending_rule_definition` | style_boundary | observe | 145 | 90.1% | 待校准/观察 |
| `data_sufficient` | data_quality | active | 136 | 84.5% | 可正式展示 |
| `industry_concentration_high` | holding_structure | active,observe | 135 | 83.9% | 观察展示，需继续校准口径 |
| `manager_tenure_long` | manager | active,observe | 126 | 78.3% | 可正式展示 |
| `sharpe_high` | return_risk | active,observe | 124 | 77.0% | 可正式展示 |
| `equity_position_high` | holding_structure | active,observe | 122 | 75.8% | 观察展示，需继续校准口径 |
| `long_term_return_strong` | return_risk | active,observe | 117 | 72.7% | 可正式展示 |
| `fund_size_moderate` | fee_size | active,observe | 59 | 36.6% | 可正式展示 |
| `fund_size_small` | fee_size | active,observe | 42 | 26.1% | 可正式展示 |
| `drawdown_high` | return_risk | active,observe | 31 | 19.3% | 可正式展示 |
| `volatility_high` | return_risk | active,observe | 26 | 16.1% | 可正式展示 |
| `data_insufficient` | data_quality | observe | 25 | 15.5% | 可正式展示 |
| `manual_review_required` | review | observe | 25 | 15.5% | 流程状态 |
| `holding_concentration_high` | holding_structure | active | 20 | 12.4% | 观察展示，需继续校准口径 |
| `volatility_low` | return_risk | observe,active | 17 | 10.6% | 可正式展示 |
| `industry_diversified` | holding_structure | observe | 12 | 7.5% | 观察展示，需继续校准口径 |
| `quality_growth` | holding_style | active | 9 | 5.6% | 待校准/观察 |
| `deep_value` | holding_style | active,observe | 3 | 1.9% | 待校准/观察 |
| `dividend_steady` | holding_style | active | 3 | 1.9% | 待校准/观察 |

### 3.1 明显需要校准的标签

- `fee_low`: 152/161（94.4%）触发，区分度偏弱。建议 v1 可以展示，但下一轮要按基金类型或主动/指数费率分层设阈值。
  - 当前 total_annual_fee 分布：min=0.0020, p25=0.0125, median=0.0140, p75=0.0140, max=0.0190。
- `industry_concentration_high`: 135/161（83.9%）触发，阈值 35% 在当前行业口径下偏容易触发。建议先观察展示，复核行业分类是否过粗。
  - 当前 industry_top1_weight 分布：min=0.0000, p25=0.4747, median=0.6313, p75=0.7642, max=0.9095。
- `style_pending_rule_definition`: 145/161（90.1%）触发，说明多数基金已有因子但未达到风格阈值。风格标签应暂列观察/待校准。

## 4. 无法计算原因拆解

| reason_code | calculation_count | fund_count | 处理判断 |
|---|---:|---:|---|
| `stock_holdings_total_weight_low` | 95 | 19 | 待进一步排查 |
| `stock_holdings_missing` | 12 | 2 | 优先回查 fundData 持仓同步；其中 ETF 联接/FOF 需要穿透或单独规则，普通权益基金缺失则是源数据未补齐。 |
| `fee_structure_missing` | 10 | 5 | 优先补 fee_structures；ETF 占位费率需单独兜底，普通基金缺失不宜强行打 fee_low。 |
| `industry_missing` | 4 | 2 | 优先回查 fundData 行业配置同步；若持仓存在，可后续由持仓股票行业映射反推。 |
| `equity_position_missing` | 2 | 2 | 优先补 fund_positions 或从最近一期股票持仓总权重兜底；ETF 联接需要穿透。 |

## 5. 典型基金抽样

### 5.1 数据完整、标签较多的基金

| fund_code | fund_name | fund_type | triggered | labels |
|---|---|---|---:|---|
| `000273` | 华润元大安鑫灵活配置混合A | 混合型-灵活 | 11 | data_sufficient, drawdown_high, equity_position_high, fee_low, fund_size_small, industry_concentration_high, long_term_return_strong, manager_tenure_long, sharpe_high, style_pending_rule_definition, volatility_high |
| `000522` | 华润元大信息传媒科技混合A | 混合型-偏股 | 11 | data_sufficient, drawdown_high, equity_position_high, fee_low, holding_concentration_high, industry_concentration_high, long_term_return_strong, manager_tenure_long, quality_growth, sharpe_high, volatility_high |
| `000017` | 财通可持续混合 | 混合型-偏股 | 10 | data_sufficient, equity_position_high, fee_low, holding_concentration_high, industry_concentration_high, long_term_return_strong, manager_tenure_long, quality_growth, sharpe_high, volatility_high |
| `000031` | 华夏复兴混合A | 混合型-偏股 | 10 | data_sufficient, equity_position_high, fee_low, fund_size_moderate, holding_concentration_high, industry_concentration_high, long_term_return_strong, manager_tenure_long, sharpe_high, style_pending_rule_definition |
| `000063` | 长盛电子信息主题混合A | 混合型-灵活 | 10 | data_sufficient, drawdown_high, equity_position_high, fee_low, industry_concentration_high, long_term_return_strong, manager_tenure_long, sharpe_high, style_pending_rule_definition, volatility_high |
| `000066` | 诺安鸿鑫混合A | 混合型-偏股 | 10 | data_sufficient, equity_position_high, fee_low, fund_size_small, industry_concentration_high, long_term_return_strong, manager_tenure_long, sharpe_high, style_pending_rule_definition, volatility_high |
| `000166` | 中海信息产业混合A | 混合型-偏股 | 10 | data_sufficient, equity_position_high, fee_low, fund_size_small, industry_concentration_high, long_term_return_strong, manager_tenure_long, sharpe_high, style_pending_rule_definition, volatility_high |
| `000354` | 长盛城镇化主题混合A | 混合型-偏股 | 10 | data_sufficient, equity_position_high, fee_low, holding_concentration_high, industry_concentration_high, long_term_return_strong, manager_tenure_long, quality_growth, sharpe_high, volatility_high |

### 5.2 not_computed 较多的基金

| fund_code | fund_name | fund_type | not_computed | reasons |
|---|---|---|---:|---|
| `000373` | 华安中证细分医药ETF联接A | 指数型-股票 | 9 | deep_value:stock_holdings_missing; dividend_steady:stock_holdings_missing; equity_position_high:equity_position_missing; holding_concentration_high:stock_holdings_missing; industry_concentration_high:industry_missing; industry_diversified:industry_missing; quality_growth:stock_holdings_missing; style_pending_rule_definition:stock_holdings_missing; style_unlabeled_stock_factors_missing:stock_holdings_missing |
| `000376` | 华安中证细分医药ETF联接C | 指数型-股票 | 9 | deep_value:stock_holdings_missing; dividend_steady:stock_holdings_missing; equity_position_high:equity_position_missing; holding_concentration_high:stock_holdings_missing; industry_concentration_high:industry_missing; industry_diversified:industry_missing; quality_growth:stock_holdings_missing; style_pending_rule_definition:stock_holdings_missing; style_unlabeled_stock_factors_missing:stock_holdings_missing |
| `100053` | 富国上证指数ETF联接A | 指数型-股票 | 7 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; fee_high:fee_structure_missing; fee_low:fee_structure_missing; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000008` | 嘉实中证500ETF联接A | 指数型-股票 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000065` | 国富焦点驱动混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000072` | 华安稳健回报混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000190` | 中银新回报灵活配置混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000215` | 广发趋势优选灵活配置混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000590` | 华安新活力灵活配置混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000597` | 中海积极收益混合 | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000051` | 华夏沪深300ETF联接A | 指数型-股票 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |
| `000417` | 国联安新精选混合A | 混合型-灵活 | 5 | deep_value:stock_holdings_total_weight_low; dividend_steady:stock_holdings_total_weight_low; holding_concentration_high:stock_holdings_total_weight_low; quality_growth:stock_holdings_total_weight_low; style_unlabeled_stock_factors_missing:stock_holdings_total_weight_low |

### 5.3 风格标签触发基金

| fund_code | fund_name | fund_type | style_labels |
|---|---|---|---|
| `000279` | 华商红利优选混合 | 混合型-灵活 | deep_value |
| `100038` | 富国沪深300指数增强A | 指数型-股票 | deep_value |
| `000251` | 工银金融地产混合A | 混合型-偏股 | deep_value, dividend_steady |
| `000127` | 农银行业领先混合 | 混合型-偏股 | dividend_steady |
| `000326` | 南方中小盘成长股票A | 股票型 | dividend_steady |
| `000017` | 财通可持续混合 | 混合型-偏股 | quality_growth |
| `000073` | 摩根成长动力混合A | 混合型-灵活 | quality_growth |
| `000308` | 建信创新中国混合 | 混合型-偏股 | quality_growth |
| `000354` | 长盛城镇化主题混合A | 混合型-偏股 | quality_growth |
| `000404` | 易方达新兴成长灵活配置 | 混合型-灵活 | quality_growth |
| `000411` | 景顺长城优质成长股票A | 股票型 | quality_growth |
| `000522` | 华润元大信息传媒科技混合A | 混合型-偏股 | quality_growth |
| `000531` | 东吴阿尔法灵活配置混合A | 混合型-灵活 | quality_growth |
| `000577` | 安信价值精选股票A | 股票型 | quality_growth |

### 5.4 return_window_insufficient 基金

共 0 只，主要是 NAV 历史未补齐或基金成立时间/源数据不足。

| fund_code | fund_name | fund_type |
|---|---|---|

### 5.5 stock_holdings_missing 基金

共 2 只。需要区分普通权益基金缺持仓，还是 ETF 联接/FOF 这类穿透结构。

| fund_code | fund_name | fund_type |
|---|---|---|
| `000373` | 华安中证细分医药ETF联接A | 指数型-股票 |
| `000376` | 华安中证细分医药ETF联接C | 指数型-股票 |

## 6. v1 正式可用标签范围建议

| 分档 | 标签 | 说明 |
|---|---|---|
| 可正式展示 | `data_sufficient`, `data_insufficient`, `fee_low`, `fee_high`, `fund_size_small`, `fund_size_moderate`, `manager_tenure_long`, `volatility_high`, `volatility_low`, `drawdown_high`, `sharpe_high`, `long_term_return_strong`, `return_window_insufficient` | 数据依赖清晰，证据链完整。收益风险只对样本充足基金正式展示。 |
| 可观察展示 | `industry_concentration_high`, `industry_diversified`, `holding_concentration_high`, `equity_position_high` | 对真实业务有价值，但行业口径、ETF 联接穿透、持仓覆盖率仍需继续校准。 |
| 暂时观察/待校准 | `deep_value`, `quality_growth`, `dividend_steady`, `style_pending_rule_definition`, `style_unlabeled_stock_factors_missing` | 股票因子可用，但风格阈值和样本解释仍需校准，不建议作为正式强结论。 |

## 7. 下一步收敛清单

1. **数据缺口收敛**：按 `reason_code` 建任务，优先补 `stock_holdings_missing`、`industry_missing`、`fee_structure_missing`。
2. **NAV 补齐常态化**：对 `return_window_insufficient` 基金跑分页 NAV，补齐后重跑收益风险标签。
3. **规则阈值复核**：重点复核 `fee_low`、`industry_concentration_high`、高级风格阈值。
4. **ETF 联接/穿透基金单列**：不要把缺穿透的 ETF 联接基金当普通股票基金下结论；启用 `--min-holding-total-weight 0.5` gate。
5. **v1 验收冻结**：先冻结可正式展示标签范围，再进入复核工作台或前端复杂化。

## 8. 附：本次跑批关键阈值

- `gate_min_nav_samples`: `180`
- `deep_value_weight_min`: `0.4`
- `quality_growth_weight_min`: `0.4`
- `dividend_steady_weight_min`: `0.5`
- `fee_low_threshold`: `0.015`
- `industry_concentration_threshold`: `0.35`
- `equity_position_high_threshold`: `0.8`
- `holding_concentration_threshold`: `0.55`
