# Phase1 标签质量样例验收报告

- run_id: `6e0ac4d1d2414ce19ebae662a7053129`
- v1 official output: `/tmp/fle-run/output-v1-official.sqlite`
- v1 official funds: **142**
- sample size: **10**

## 1. 结论

当前标签足够支撑第一版 MVP：可以说明一只基金的数据状态、收益风险、持仓/行业集中、权益仓位、经理任期、费率规模和初步风格。

但当前阶段不适合继续盲目加标签。优先事项是：

1. 固定样本集，持续回归每只基金的标签、证据、未触发原因。
2. 校准触发率异常高的标签，尤其是行业集中、费率低、1Y 收益风险。
3. 下一组新增标签只做相对基准和风格稳定性，不先扩债券/货币/QDII/FOF。

## 2. 10 只真实样本

| fund_code | fund_name | fund_type | 选择原因 | triggered | not_triggered | not_computed |
|---|---|---|---|---:|---:|---:|
| `000001` | 华夏成长混合 | 混合型-灵活 | 老牌灵活配置样本，检验基础收益/回撤/费率/经理标签 | 8 | 14 | 0 |
| `000006` | 西部利得量化成长混合A | 混合型-偏股 | 偏股量化成长样本，检验行业集中未触发场景 | 8 | 14 | 0 |
| `000017` | 财通可持续混合 | 混合型-偏股 | 质量成长样本，检验高级风格和持仓集中 | 10 | 12 | 0 |
| `000251` | 工银金融地产混合A | 混合型-偏股 | 价值+红利样本，检验 deep_value / dividend_steady | 9 | 13 | 0 |
| `000273` | 华润元大安鑫灵活配置混合A | 混合型-灵活 | 高波动高回撤小规模样本，检验风险标签 | 11 | 11 | 0 |
| `000373` | 华安中证细分医药ETF联接A | 指数型-股票 | 已穿透 ETF 联接样本，检验穿透补齐后的指数基金 | 8 | 14 | 0 |
| `000411` | 景顺长城优质成长股票A | 股票型 | 股票型质量成长样本，检验股票型主动权益 | 10 | 12 | 0 |
| `000628` | 大成高鑫股票A | 股票型 | 低波动股票型样本，检验 volatility_low | 8 | 14 | 0 |
| `100038` | 富国沪深300指数增强A | 指数型-股票 | 指数增强样本，检验规范代码和 deep_value | 9 | 13 | 0 |
| `100056` | 富国低碳环保混合 | 混合型-偏股 | 高费率样本，检验 fee_high | 8 | 14 | 0 |

所有 10 只样本均 `not_computed=0`，适合做标签质量验收集。

## 3. 样本标签摘要

### 000001 华夏成长混合

- 类型：混合型-灵活
- 触发标签：`data_sufficient, fee_low, fund_size_moderate, industry_concentration_high, manager_tenure_long, drawdown_high, long_term_return_strong, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_small`(threshold_not_met, observed=26.44, threshold={'fund_size_max': 1.0})；`equity_position_high`(threshold_not_met, observed=0.7941, threshold={'equity_position_min': 0.8})；`holding_concentration_high`(threshold_not_met, observed=0.2596, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.6714, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})

### 000006 西部利得量化成长混合A

- 类型：混合型-偏股
- 触发标签：`data_sufficient, fee_low, fund_size_moderate, equity_position_high, manager_tenure_long, long_term_return_strong, sharpe_high, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.013, threshold={'total_annual_fee_min': 0.025})；`fund_size_small`(threshold_not_met, observed=13.37, threshold={'fund_size_max': 1.0})；`holding_concentration_high`(threshold_not_met, observed=0.1034, threshold={'top_10_holding_weight_min': 0.55})；`industry_concentration_high`(threshold_not_met, observed=0.3447, threshold={'industry_top1_weight_min': 0.35})；`industry_diversified`(threshold_not_met, observed=0.3447, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})

### 000017 财通可持续混合

- 类型：混合型-偏股
- 触发标签：`data_sufficient, fee_low, equity_position_high, holding_concentration_high, industry_concentration_high, quality_growth, manager_tenure_long, long_term_return_strong, sharpe_high, volatility_high`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_moderate`(threshold_not_met, observed=1.52, threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0})；`fund_size_small`(threshold_not_met, observed=1.52, threshold={'fund_size_max': 1.0})；`industry_diversified`(threshold_not_met, observed=0.7931, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`drawdown_high`(threshold_not_met, observed=-0.14852, threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'})

### 000251 工银金融地产混合A

- 类型：混合型-偏股
- 触发标签：`data_sufficient, fee_low, fund_size_moderate, equity_position_high, holding_concentration_high, industry_concentration_high, deep_value, dividend_steady, manager_tenure_long`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_small`(threshold_not_met, observed=10.77, threshold={'fund_size_max': 1.0})；`industry_diversified`(threshold_not_met, observed=0.8498, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`quality_growth`(threshold_not_met, observed=style_weight_below_threshold, threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4})；`drawdown_high`(threshold_not_met, observed=-0.122462, threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'})；`long_term_return_strong`(threshold_not_met, observed=-0.023439, threshold={'annualized_return_min': 0.15, 'window': '3y|1y'})；`return_window_insufficient`(return_window_available, observed=1y, threshold=1y_or_3y_window_required)

### 000273 华润元大安鑫灵活配置混合A

- 类型：混合型-灵活
- 触发标签：`data_sufficient, fee_low, fund_size_small, equity_position_high, industry_concentration_high, manager_tenure_long, drawdown_high, long_term_return_strong, sharpe_high, volatility_high, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_moderate`(threshold_not_met, observed=0.06, threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0})；`holding_concentration_high`(threshold_not_met, observed=0.4468, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.8133, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`quality_growth`(threshold_not_met, observed=style_weight_below_threshold, threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4})

### 000373 华安中证细分医药ETF联接A

- 类型：指数型-股票
- 触发标签：`data_sufficient, fee_low, fund_size_small, equity_position_high, industry_concentration_high, manager_tenure_long, drawdown_high, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.006, threshold={'total_annual_fee_min': 0.025})；`fund_size_moderate`(threshold_not_met, observed=0.38, threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0})；`holding_concentration_high`(threshold_not_met, observed=0.46816, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.725325, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`quality_growth`(threshold_not_met, observed=style_weight_below_threshold, threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4})

### 000411 景顺长城优质成长股票A

- 类型：股票型
- 触发标签：`data_sufficient, fee_low, fund_size_moderate, equity_position_high, industry_concentration_high, quality_growth, manager_tenure_long, long_term_return_strong, sharpe_high, volatility_high`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_small`(threshold_not_met, observed=12.81, threshold={'fund_size_max': 1.0})；`holding_concentration_high`(threshold_not_met, observed=0.5368, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.8093, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`drawdown_high`(threshold_not_met, observed=-0.135135, threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'})

### 000628 大成高鑫股票A

- 类型：股票型
- 触发标签：`data_sufficient, fee_low, equity_position_high, holding_concentration_high, industry_concentration_high, manager_tenure_long, volatility_low, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.014, threshold={'total_annual_fee_min': 0.025})；`fund_size_moderate`(threshold_not_met, observed=109.88, threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0})；`fund_size_small`(threshold_not_met, observed=109.88, threshold={'fund_size_max': 1.0})；`industry_diversified`(threshold_not_met, observed=0.5398, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`quality_growth`(threshold_not_met, observed=style_weight_below_threshold, threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4})

### 100038 富国沪深300指数增强A

- 类型：指数型-股票
- 触发标签：`data_sufficient, fee_low, fund_size_moderate, equity_position_high, industry_concentration_high, deep_value, manager_tenure_long, long_term_return_strong, sharpe_high`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_high`(threshold_not_met, observed=0.0118, threshold={'total_annual_fee_min': 0.025})；`fund_size_small`(threshold_not_met, observed=46.17, threshold={'fund_size_max': 1.0})；`holding_concentration_high`(threshold_not_met, observed=0.1706, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.4721, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})；`quality_growth`(threshold_not_met, observed=style_weight_below_threshold, threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4})；`drawdown_high`(threshold_not_met, observed=-0.067069, threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'})

### 100056 富国低碳环保混合

- 类型：混合型-偏股
- 触发标签：`data_sufficient, fee_high, fund_size_moderate, industry_concentration_high, long_term_return_strong, sharpe_high, volatility_high, style_pending_rule_definition`
- 未触发样例：`data_insufficient`(coverage_passed, observed=all_required_fields_present, threshold=any_required_field_missing)；`fee_low`(threshold_not_met, observed=0.026, threshold={'total_annual_fee_max': 0.015})；`fund_size_small`(threshold_not_met, observed=9.16, threshold={'fund_size_max': 1.0})；`equity_position_high`(threshold_not_met, observed=0.7825, threshold={'equity_position_min': 0.8})；`holding_concentration_high`(threshold_not_met, observed=0.3995, threshold={'top_10_holding_weight_min': 0.55})；`industry_diversified`(threshold_not_met, observed=0.7429, threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5})；`deep_value`(threshold_not_met, observed=style_weight_below_threshold, threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4})；`dividend_steady`(threshold_not_met, observed=style_weight_below_threshold, threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5})

## 4. 全量 v1 标签分布

| label_code | category | fund_count | coverage | 判断 |
|---|---|---:|---:|---|
| `data_sufficient` | data_quality | 142 | 100.0% | 正常 |
| `industry_concentration_high` | holding_structure | 137 | 96.5% | 需要校准/持续观察 |
| `fee_low` | fee_size | 136 | 95.8% | 需要校准/持续观察 |
| `style_pending_rule_definition` | style_boundary | 128 | 90.1% | 需要校准/持续观察 |
| `equity_position_high` | holding_structure | 124 | 87.3% | 正常 |
| `long_term_return_strong` | return_risk | 111 | 78.2% | 需要校准/持续观察 |
| `manager_tenure_long` | manager | 109 | 76.8% | 正常 |
| `sharpe_high` | return_risk | 109 | 76.8% | 需要校准/持续观察 |
| `fund_size_moderate` | fee_size | 54 | 38.0% | 正常 |
| `fund_size_small` | fee_size | 33 | 23.2% | 正常 |
| `drawdown_high` | return_risk | 30 | 21.1% | 正常 |
| `volatility_high` | return_risk | 26 | 18.3% | 正常 |
| `holding_concentration_high` | holding_structure | 20 | 14.1% | 正常 |
| `quality_growth` | holding_style | 9 | 6.3% | 正常 |
| `volatility_low` | return_risk | 5 | 3.5% | 正常 |
| `deep_value` | holding_style | 3 | 2.1% | 正常 |
| `dividend_steady` | holding_style | 3 | 2.1% | 正常 |
| `fee_high` | fee_size | 2 | 1.4% | 正常 |

## 5. 阈值校准清单

| label_code | coverage | 问题 | 建议 |
|---|---:|---|---|
| `industry_concentration_high` | 96.5% | 触发率过高，当前 v1 为 137/142，说明 35% 阈值或行业口径偏宽。 | 优先抽样看行业口径；建议把正式展示改成观察标签，或把阈值分层到 45%/60%。 |
| `fee_low` | 95.8% | 触发率过高，当前 v1 为大多数基金，低费率区分度弱。 | 按指数/主动、A/C 份额分层设阈值；否则 v1 只作为费率状态展示。 |
| `style_pending_rule_definition` | 90.1% | 大量基金已有因子但未达风格阈值，说明风格标签还不稳定。 | 风格先观察；下一步做风格稳定性/漂移，不急着扩大风格标签数量。 |
| `sharpe_high` | 76.8% | 收益风险标签大量触发，可能受 1Y 窗口行情影响。 | 保留 evidence，但展示时明确窗口；后续补 3Y/相对基准。 |
| `long_term_return_strong` | 78.2% | 1Y 年化收益触发较多，绝对收益标签容易被市场阶段影响。 | 下一组优先补相对基准：超额收益、信息比率、Alpha/Beta。 |

## 6. 下一步

1. 把这 10 只作为固定回归样本；每次改规则后先看这 10 只标签是否符合业务直觉。
2. 优先校准 `industry_concentration_high` 和 `fee_low`，不要先新增大量标签。
3. 下一组新增标签限定为：相对基准（超额收益、信息比率、跟踪误差、Alpha/Beta）和风格稳定性（风格漂移、成长/价值稳定性）。
4. 被动指数基金标签单独设计，不和主动权益基金混在一起。
