# 10 只真实基金完整标签结果样板

目标：先看清楚现有标签能不能解释真实基金，不急着扩标签数量。

## 1. 样本覆盖

| fund_code | fund_name | 样本池 | 结果来源 | 分组 | triggered | not_triggered | not_computed |
|---|---|---|---|---|---:|---:|---:|
| `000006` | 西部利得量化成长混合A | 主动权益候选池 | official | v1正式权益样本池；主动权益候选池 | 10 | 22 | 0 |
| `000017` | 财通可持续混合 | 质量成长/行业集中/高收益池 | official | v1正式权益样本池；主动权益候选池；风格标签触发池；质量成长风格池；高收益高风险观察池；行业集中观察池 | 14 | 18 | 0 |
| `000251` | 工银金融地产混合A | 深度价值/红利稳健风格池 | official | v1正式权益样本池；主动权益候选池；风格标签触发池；深度价值风格池；红利稳健风格池；行业集中观察池 | 10 | 22 | 0 |
| `000273` | 华润元大安鑫灵活配置混合A | 高收益高回撤观察池 | official | 数据缺口/人工复核池；主动权益候选池；高收益高风险观察池；行业集中观察池；小规模观察池 | 11 | 15 | 6 |
| `000373` | 华安中证细分医药ETF联接A | 被动指数工具池 | official | v1正式权益样本池；被动指数工具池；行业集中观察池；小规模观察池 | 10 | 22 | 0 |
| `000411` | 景顺长城优质成长股票A | 主动股票型/质量成长池 | official | 数据缺口/人工复核池；主动权益候选池；风格标签触发池；质量成长风格池；高收益高风险观察池；行业集中观察池 | 10 | 16 | 6 |
| `000628` | 大成高鑫股票A | 主动股票型/低波动池 | official | 数据缺口/人工复核池；主动权益候选池 | 8 | 18 | 6 |
| `100038` | 富国沪深300指数增强A | 被动指数增强/深度价值池 | official | v1正式权益样本池；被动指数工具池；风格标签触发池；深度价值风格池 | 11 | 21 | 0 |
| `000051` | 华夏沪深300ETF联接A | 数据缺口/穿透不足池 | canonical | 数据缺口/人工复核池；被动指数工具池 | 8 | 10 | 5 |
| `000058` | 国联安安泰灵活配置混合A | 范围边界/低权益仓位池 | canonical | 数据缺口/人工复核池 | 7 | 11 | 5 |

## 2. 单基金完整样板

### 000006 西部利得量化成长混合A

- 分类：混合型-偏股
- 样本池：主动权益候选池
- 进入分组：v1正式权益样本池；主动权益候选池
- 最新持仓权重：83.52%（265 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fund_size_moderate`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `alpha_positive`（relative_benchmark，active，confidence=0.75）
- `beta_low`（relative_benchmark，active，confidence=0.75）
- `tracking_error_high`（relative_benchmark，active，confidence=0.75）
- `long_term_return_strong`（return_risk，active，confidence=0.8）
- `sharpe_high`（return_risk，active，confidence=0.75）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `alpha_positive` / `alpha_1y`：value=0.483003，threshold=0.03；1Y Alpha 48.30%，达到相对基准阈值 3.00%。
- `beta_low` / `beta_1y`：value=-0.021693，threshold=0.8；1Y Beta -2.17%，达到相对基准阈值 80.00%。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `equity_position_high` / `equity_position`：value=0.8352，threshold=0.8；权益仓位 83.52%，达到 80.00% 权益仓位阈值。
- `fund_size_moderate` / `fund_size`：value=13.37，threshold=5.00~100.00 亿元；基金规模 13.37 亿元，处于 5.00~100.00 亿元合理区间。
- `long_term_return_strong` / `annualized_return_1y`：value=0.443516，threshold=0.15；1Y 年化收益率 44.35%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=9.52，threshold=5.0；当前基金经理任期 9.5 年，达到 5.0 年稳定性阈值。
- `sharpe_high` / `sharpe_ratio_1y`：value=2.991613，threshold=1.0；1Y 夏普 2.99，达到 1.00。
- `style_pending_rule_definition` / `style_factor_coverage_weight`：value=0.8352，threshold=style_weights_below_threshold；已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
- `tracking_error_high` / `tracking_error_1y`：value=0.227532，threshold=0.08；1Y 年化跟踪误差 22.75%，达到相对基准阈值 8.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.013，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.013，threshold={'total_annual_fee_max': 0.012}
- `fund_size_small`：threshold_not_met，observed=13.37，threshold={'fund_size_max': 1.0}
- `holding_concentration_high`：threshold_not_met，observed=0.1034，threshold={'top_10_holding_weight_min': 0.55}
- `industry_concentration_high`：threshold_not_met，observed=0.3447，threshold={'industry_top1_weight_min': 0.6}
- `industry_concentration_observe`：threshold_not_met，observed=0.3447，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.3447，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}

**因为数据不足/范围边界不能算**
- 无

**白话解释**

西部利得量化成长混合A 属于 混合型-偏股，可以进入 v1 权益基金正式样本。

### 000017 财通可持续混合

- 分类：混合型-偏股
- 样本池：质量成长/行业集中/高收益池
- 进入分组：v1正式权益样本池；主动权益候选池；风格标签触发池；质量成长风格池；高收益高风险观察池；行业集中观察池
- 最新持仓权重：94.65%（61 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `holding_concentration_high`（holding_structure，active，confidence=0.9）
- `industry_concentration_high`（holding_structure，active，confidence=0.85）
- `quality_growth`（holding_style，active，confidence=0.75）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `alpha_positive`（relative_benchmark，active，confidence=0.75）
- `beta_low`（relative_benchmark，active，confidence=0.75）
- `excess_return_strong`（relative_benchmark，active，confidence=0.75）
- `information_ratio_high`（relative_benchmark，active，confidence=0.75）
- `tracking_error_high`（relative_benchmark，active，confidence=0.75）
- `long_term_return_strong`（return_risk，active，confidence=0.8）
- `sharpe_high`（return_risk，active，confidence=0.75）
- `volatility_high`（return_risk，active，confidence=0.75）

**为什么打出来（证据摘要）**
- `alpha_positive` / `alpha_1y`：value=2.888226，threshold=0.03；1Y Alpha 288.82%，达到相对基准阈值 3.00%。
- `beta_low` / `beta_1y`：value=-0.199942，threshold=0.8；1Y Beta -19.99%，达到相对基准阈值 80.00%。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `equity_position_high` / `equity_position`：value=0.9465，threshold=0.8；权益仓位 94.65%，达到 80.00% 权益仓位阈值。
- `excess_return_strong` / `annualized_excess_return_1y`：value=2.087308，threshold=0.05；1Y 年化超额收益 208.73%，达到相对基准阈值 5.00%。
- `holding_concentration_high` / `top_10_holding_weight`：value=0.6788，threshold=0.55；前十大持仓合计 67.88%，达到持仓集中度高阈值 55.00%。
- `industry_concentration_high` / `industry_top1_weight`：value=0.7931，threshold=0.6；第一大行业占比 79.31%，达到 60.00% 行业高度集中阈值。
- `information_ratio_high` / `information_ratio_1y`：value=4.810973，threshold=0.5；1Y 信息比率 481.10%，达到相对基准阈值 50.00%。
- `long_term_return_strong` / `annualized_return_1y`：value=2.694468，threshold=0.15；1Y 年化收益率 269.45%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=10.06，threshold=5.0；当前基金经理任期 10.1 年，达到 5.0 年稳定性阈值。
- `quality_growth` / `quality_growth_weight`：value=0.5542，threshold=0.4；预聚合质量成长持仓权重 55%，达到 40% 阈值。 因子覆盖权重 95%。
- `sharpe_high` / `sharpe_ratio_1y`：value=6.710162，threshold=1.0；1Y 夏普 6.71，达到 1.00。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_max': 0.012}
- `fund_size_moderate`：threshold_not_met，observed=1.52，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `fund_size_small`：threshold_not_met，observed=1.52，threshold={'fund_size_max': 1.0}
- `industry_concentration_observe`：threshold_not_met，observed=0.7931，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.7931，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `deep_value`：threshold_not_met，observed=0.001，threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- 无

**白话解释**

财通可持续混合 属于 混合型-偏股，可以进入 v1 权益基金正式样本。持仓因子显示质量成长特征较明显。行业暴露较集中，收益弹性和行业风险都更高。前十大持仓占比较高，个股集中风险需要关注。历史风险指标偏高，适合放在观察池而不是只看收益。

### 000251 工银金融地产混合A

- 分类：混合型-偏股
- 样本池：深度价值/红利稳健风格池
- 进入分组：v1正式权益样本池；主动权益候选池；风格标签触发池；深度价值风格池；红利稳健风格池；行业集中观察池
- 最新持仓权重：88.40%（67 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fund_size_moderate`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `holding_concentration_high`（holding_structure，active，confidence=0.9）
- `industry_concentration_high`（holding_structure，active，confidence=0.85）
- `deep_value`（holding_style，active，confidence=0.75）
- `dividend_steady`（holding_style，active，confidence=0.75）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `beta_low`（relative_benchmark，active，confidence=0.75）
- `tracking_error_high`（relative_benchmark，active，confidence=0.75）

**为什么打出来（证据摘要）**
- `beta_low` / `beta_1y`：value=0.022405，threshold=0.8；1Y Beta 2.24%，达到相对基准阈值 80.00%。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `deep_value` / `deep_value_weight`：value=0.8067，threshold=0.4；预聚合深度价值持仓权重 81%，达到 40% 阈值。 因子覆盖权重 88%。
- `dividend_steady` / `dividend_steady_weight`：value=0.7401，threshold=0.5；预聚合红利稳健持仓权重 74%，达到 50% 阈值。 因子覆盖权重 88%。
- `equity_position_high` / `equity_position`：value=0.884，threshold=0.8；权益仓位 88.40%，达到 80.00% 权益仓位阈值。
- `fund_size_moderate` / `fund_size`：value=10.77，threshold=5.00~100.00 亿元；基金规模 10.77 亿元，处于 5.00~100.00 亿元合理区间。
- `holding_concentration_high` / `top_10_holding_weight`：value=0.677，threshold=0.55；前十大持仓合计 67.70%，达到持仓集中度高阈值 55.00%。
- `industry_concentration_high` / `industry_top1_weight`：value=0.8498，threshold=0.6；第一大行业占比 84.98%，达到 60.00% 行业高度集中阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=12.76，threshold=5.0；当前基金经理任期 12.8 年，达到 5.0 年稳定性阈值。
- `tracking_error_high` / `tracking_error_1y`：value=0.189295，threshold=0.08；1Y 年化跟踪误差 18.93%，达到相对基准阈值 8.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_max': 0.012}
- `fund_size_small`：threshold_not_met，observed=10.77，threshold={'fund_size_max': 1.0}
- `industry_concentration_observe`：threshold_not_met，observed=0.8498，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.8498，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `quality_growth`：threshold_not_met，observed=0.0485，threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}
- `alpha_positive`：threshold_not_met，observed=-0.055589，threshold={'alpha_min': 0.03, 'window': '3y|1y'}

**因为数据不足/范围边界不能算**
- 无

**白话解释**

工银金融地产混合A 属于 混合型-偏股，可以进入 v1 权益基金正式样本。同时具备深度价值和红利稳健特征，偏价值/红利风格。行业暴露较集中，收益弹性和行业风险都更高。前十大持仓占比较高，个股集中风险需要关注。

### 000273 华润元大安鑫灵活配置混合A

- 分类：混合型-灵活
- 样本池：高收益高回撤观察池
- 进入分组：数据缺口/人工复核池；主动权益候选池；高收益高风险观察池；行业集中观察池；小规模观察池
- 最新持仓权重：89.15%（22 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fund_size_small`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `industry_concentration_high`（holding_structure，active，confidence=0.85）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `benchmark_data_missing`（relative_benchmark，observe，confidence=1.0）
- `drawdown_high`（return_risk，active，confidence=0.75）
- `long_term_return_strong`（return_risk，active，confidence=0.8）
- `sharpe_high`（return_risk，active，confidence=0.75）
- `volatility_high`（return_risk，active，confidence=0.75）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `benchmark_data_missing` / `benchmark_sample_count`：value=0，threshold=min(1y=180, 3y=500)；缺少可对齐的 1Y/3Y 基准收益序列，暂不输出正式相对基准标签。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `drawdown_high` / `max_drawdown_1y`：value=-0.280799，threshold=-0.2；1Y 最大回撤 -28.08%，低于 -20.00%。
- `equity_position_high` / `equity_position`：value=0.8915，threshold=0.8；权益仓位 89.15%，达到 80.00% 权益仓位阈值。
- `fund_size_small` / `fund_size`：value=0.06，threshold=1.0；基金规模 0.06 亿元，低于 1.00 亿元。
- `industry_concentration_high` / `industry_top1_weight`：value=0.8133，threshold=0.6；第一大行业占比 81.33%，达到 60.00% 行业高度集中阈值。
- `long_term_return_strong` / `annualized_return_1y`：value=0.339692，threshold=0.15；1Y 年化收益率 33.97%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=10.11，threshold=5.0；当前基金经理任期 10.1 年，达到 5.0 年稳定性阈值。
- `sharpe_high` / `sharpe_ratio_1y`：value=1.129617，threshold=1.0；1Y 夏普 1.13，达到 1.00。
- `style_pending_rule_definition` / `style_factor_coverage_weight`：value=0.8915，threshold=style_weights_below_threshold；已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
- `volatility_high` / `annualized_volatility_1y`：value=0.300714，threshold=0.3；1Y 年化波动率 30.07%，高于 30.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_max': 0.012}
- `fund_size_moderate`：threshold_not_met，observed=0.06，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `holding_concentration_high`：threshold_not_met，observed=0.4468，threshold={'top_10_holding_weight_min': 0.55}
- `industry_concentration_observe`：threshold_not_met，observed=0.8133，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.8133，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `deep_value`：threshold_not_met，observed=0.0，threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- `alpha_positive`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_low`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `excess_return_strong`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `information_ratio_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `tracking_error_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)

**白话解释**

华润元大安鑫灵活配置混合A 当前不适合直接下正式权益标签结论：基础类型是 混合型-灵活，但持仓穿透或股票仓位不足，系统将它放入人工复核/范围边界池，避免把数据缺口误解释成基金特征。

### 000373 华安中证细分医药ETF联接A

- 分类：指数型-股票
- 样本池：被动指数工具池
- 进入分组：v1正式权益样本池；被动指数工具池；行业集中观察池；小规模观察池
- 最新持仓权重：93.79%（50 条，2024-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fee_low`（fee_size，active，confidence=0.85）
- `fund_size_small`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `industry_concentration_high`（holding_structure，active，confidence=0.85）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `beta_low`（relative_benchmark，active，confidence=0.75）
- `tracking_error_high`（relative_benchmark，active，confidence=0.75）
- `drawdown_high`（return_risk，active，confidence=0.75）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `beta_low` / `beta_1y`：value=-0.081356，threshold=0.8；1Y Beta -8.14%，达到相对基准阈值 80.00%。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `drawdown_high` / `max_drawdown_3y`：value=-0.301225，threshold=-0.2；3Y 最大回撤 -30.12%，低于 -20.00%。
- `equity_position_high` / `equity_position`：value=0.9379，threshold=0.8；权益仓位 93.79%，达到 80.00% 权益仓位阈值。
- `fee_low` / `total_annual_fee`：value=0.006，threshold=0.012；管理费、托管费和销售服务费合计 0.60%，不高于 1.20%。
- `fund_size_small` / `fund_size`：value=0.38，threshold=1.0；基金规模 0.38 亿元，低于 1.00 亿元。
- `industry_concentration_high` / `industry_top1_weight`：value=0.7253，threshold=0.6；第一大行业占比 72.53%，达到 60.00% 行业高度集中阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=9.45，threshold=5.0；当前基金经理任期 9.4 年，达到 5.0 年稳定性阈值。
- `style_pending_rule_definition` / `style_factor_coverage_weight`：value=0.9379，threshold=style_weights_below_threshold；已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
- `tracking_error_high` / `tracking_error_1y`：value=0.300477，threshold=0.08；1Y 年化跟踪误差 30.05%，达到相对基准阈值 8.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.006，threshold={'total_annual_fee_min': 0.025}
- `fund_size_moderate`：threshold_not_met，observed=0.38，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `holding_concentration_high`：threshold_not_met，observed=0.46816，threshold={'top_10_holding_weight_min': 0.55}
- `industry_concentration_observe`：threshold_not_met，observed=0.725325，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.725325，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `deep_value`：threshold_not_met，observed=0.1691，threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}
- `dividend_steady`：threshold_not_met，observed=0.21698，threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- 无

**白话解释**

华安中证细分医药ETF联接A 更像指数/指数增强工具，重点应看跟踪标的、穿透持仓、费率和相对基准，而不是只按主动权益基金解释。行业暴露较集中，收益弹性和行业风险都更高。历史风险指标偏高，适合放在观察池而不是只看收益。费率不高，但 fee_low 标签本身仍需进一步校准。

### 000411 景顺长城优质成长股票A

- 分类：股票型
- 样本池：主动股票型/质量成长池
- 进入分组：数据缺口/人工复核池；主动权益候选池；风格标签触发池；质量成长风格池；高收益高风险观察池；行业集中观察池
- 最新持仓权重：80.93%（51 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fund_size_moderate`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `industry_concentration_high`（holding_structure，active，confidence=0.85）
- `quality_growth`（holding_style，active，confidence=0.75）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `benchmark_data_missing`（relative_benchmark，observe，confidence=1.0）
- `long_term_return_strong`（return_risk，active，confidence=0.8）
- `sharpe_high`（return_risk，active，confidence=0.75）
- `volatility_high`（return_risk，active，confidence=0.75）

**为什么打出来（证据摘要）**
- `benchmark_data_missing` / `benchmark_sample_count`：value=0，threshold=min(1y=180, 3y=500)；缺少可对齐的 1Y/3Y 基准收益序列，暂不输出正式相对基准标签。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `equity_position_high` / `equity_position`：value=0.8093，threshold=0.8；权益仓位 80.93%，达到 80.00% 权益仓位阈值。
- `fund_size_moderate` / `fund_size`：value=12.81，threshold=5.00~100.00 亿元；基金规模 12.81 亿元，处于 5.00~100.00 亿元合理区间。
- `industry_concentration_high` / `industry_top1_weight`：value=0.8093，threshold=0.6；第一大行业占比 80.93%，达到 60.00% 行业高度集中阈值。
- `long_term_return_strong` / `annualized_return_1y`：value=2.753217，threshold=0.15；1Y 年化收益率 275.32%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=10.23，threshold=5.0；当前基金经理任期 10.2 年，达到 5.0 年稳定性阈值。
- `quality_growth` / `quality_growth_weight`：value=0.4021，threshold=0.4；预聚合质量成长持仓权重 40%，达到 40% 阈值。 因子覆盖权重 81%。
- `sharpe_high` / `sharpe_ratio_1y`：value=7.362519，threshold=1.0；1Y 夏普 7.36，达到 1.00。
- `volatility_high` / `annualized_volatility_1y`：value=0.37395，threshold=0.3；1Y 年化波动率 37.40%，高于 30.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_max': 0.012}
- `fund_size_small`：threshold_not_met，observed=12.81，threshold={'fund_size_max': 1.0}
- `holding_concentration_high`：threshold_not_met，observed=0.5368，threshold={'top_10_holding_weight_min': 0.55}
- `industry_concentration_observe`：threshold_not_met，observed=0.8093，threshold={'industry_top1_weight_min': 0.45, 'industry_top1_weight_max_exclusive': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.8093，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `deep_value`：threshold_not_met，observed=0.0，threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- `alpha_positive`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_low`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `excess_return_strong`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `information_ratio_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `tracking_error_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)

**白话解释**

景顺长城优质成长股票A 当前不适合直接下正式权益标签结论：基础类型是 股票型，但持仓穿透或股票仓位不足，系统将它放入人工复核/范围边界池，避免把数据缺口误解释成基金特征。

### 000628 大成高鑫股票A

- 分类：股票型
- 样本池：主动股票型/低波动池
- 进入分组：数据缺口/人工复核池；主动权益候选池
- 最新持仓权重：81.44%（60 条，2025-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `holding_concentration_high`（holding_structure，active，confidence=0.9）
- `industry_concentration_observe`（holding_structure，observe，confidence=0.75）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `benchmark_data_missing`（relative_benchmark，observe，confidence=1.0）
- `volatility_low`（return_risk，active，confidence=0.7）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `benchmark_data_missing` / `benchmark_sample_count`：value=0，threshold=min(1y=180, 3y=500)；缺少可对齐的 1Y/3Y 基准收益序列，暂不输出正式相对基准标签。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `equity_position_high` / `equity_position`：value=0.8144，threshold=0.8；权益仓位 81.44%，达到 80.00% 权益仓位阈值。
- `holding_concentration_high` / `top_10_holding_weight`：value=0.5767，threshold=0.55；前十大持仓合计 57.67%，达到持仓集中度高阈值 55.00%。
- `industry_concentration_observe` / `industry_top1_weight`：value=0.5398，threshold=45.00%~60.00%；第一大行业占比 53.98%，进入 45.00%~60.00% 行业集中观察区间。
- `manager_tenure_long` / `manager_tenure_years`：value=10.84，threshold=5.0；当前基金经理任期 10.8 年，达到 5.0 年稳定性阈值。
- `style_pending_rule_definition` / `style_factor_coverage_weight`：value=0.7029，threshold=style_weights_below_threshold；已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
- `volatility_low` / `annualized_volatility_1y`：value=0.104707，threshold=0.12；1Y 年化波动率 10.47%，不高于 12.00%。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_min': 0.025}
- `fee_low`：threshold_not_met，observed=0.014，threshold={'total_annual_fee_max': 0.012}
- `fund_size_moderate`：threshold_not_met，observed=109.88，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `fund_size_small`：threshold_not_met，observed=109.88，threshold={'fund_size_max': 1.0}
- `industry_concentration_high`：threshold_not_met，observed=0.5398，threshold={'industry_top1_weight_min': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.5398，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `deep_value`：threshold_not_met，observed=0.2452，threshold={'pb_weighted_max': 1.5, 'valuation_pct_weighted_max': 0.3, 'deep_value_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- `alpha_positive`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `beta_low`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `excess_return_strong`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `information_ratio_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)
- `tracking_error_high`：benchmark_data_missing，observed=0，threshold=min(1y=180, 3y=500)

**白话解释**

大成高鑫股票A 当前不适合直接下正式权益标签结论：基础类型是 股票型，但持仓穿透或股票仓位不足，系统将它放入人工复核/范围边界池，避免把数据缺口误解释成基金特征。

### 100038 富国沪深300指数增强A

- 分类：指数型-股票
- 样本池：被动指数增强/深度价值池
- 进入分组：v1正式权益样本池；被动指数工具池；风格标签触发池；深度价值风格池
- 最新持仓权重：93.71%（438 条，2024-12-31）

**打出的标签**
- `data_sufficient`（data_quality，active，confidence=0.95）
- `fee_low`（fee_size，active，confidence=0.85）
- `fund_size_moderate`（fee_size，active，confidence=0.8）
- `equity_position_high`（holding_structure，active，confidence=0.85）
- `industry_concentration_observe`（holding_structure，observe，confidence=0.75）
- `deep_value`（holding_style，active，confidence=0.75）
- `manager_tenure_long`（manager，active，confidence=0.9）
- `alpha_positive`（relative_benchmark，active，confidence=0.75）
- `information_ratio_high`（relative_benchmark，active，confidence=0.75）
- `long_term_return_strong`（return_risk，active，confidence=0.8）
- `sharpe_high`（return_risk，active，confidence=0.75）

**为什么打出来（证据摘要）**
- `alpha_positive` / `alpha_1y`：value=0.052443，threshold=0.03；1Y Alpha 5.24%，达到相对基准阈值 3.00%。
- `data_sufficient` / `required_fields_present`：value=yes，threshold=all_required_fields_present；基础净值、持仓、行业、经理、费率和规模数据均已提供。
- `deep_value` / `deep_value_weight`：value=0.4106，threshold=0.4；预聚合深度价值持仓权重 41%，达到 40% 阈值。 因子覆盖权重 93%。
- `equity_position_high` / `equity_position`：value=0.9371，threshold=0.8；权益仓位 93.71%，达到 80.00% 权益仓位阈值。
- `fee_low` / `total_annual_fee`：value=0.0118，threshold=0.012；管理费、托管费和销售服务费合计 1.18%，不高于 1.20%。
- `fund_size_moderate` / `fund_size`：value=46.17，threshold=5.00~100.00 亿元；基金规模 46.17 亿元，处于 5.00~100.00 亿元合理区间。
- `industry_concentration_observe` / `industry_top1_weight`：value=0.4721，threshold=45.00%~60.00%；第一大行业占比 47.21%，进入 45.00%~60.00% 行业集中观察区间。
- `information_ratio_high` / `information_ratio_1y`：value=1.004656，threshold=0.5；1Y 信息比率 100.47%，达到相对基准阈值 50.00%。
- `long_term_return_strong` / `annualized_return_1y`：value=0.33274，threshold=0.15；1Y 年化收益率 33.27%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=16.44，threshold=5.0；当前基金经理任期 16.4 年，达到 5.0 年稳定性阈值。
- `sharpe_high` / `sharpe_ratio_1y`：value=2.163291，threshold=1.0；1Y 夏普 2.16，达到 1.00。

**没打出来的标签（前 8 项）**
- `data_insufficient`：coverage_passed，observed=all_required_fields_present，threshold=any_required_field_missing
- `fee_high`：threshold_not_met，observed=0.0118，threshold={'total_annual_fee_min': 0.025}
- `fund_size_small`：threshold_not_met，observed=46.17，threshold={'fund_size_max': 1.0}
- `holding_concentration_high`：threshold_not_met，observed=0.1706，threshold={'top_10_holding_weight_min': 0.55}
- `industry_concentration_high`：threshold_not_met，observed=0.4721，threshold={'industry_top1_weight_min': 0.6}
- `industry_diversified`：threshold_not_met，observed=0.4721，threshold={'industry_top1_weight_max': 0.2, 'industry_count_min': 5}
- `dividend_steady`：threshold_not_met，observed=0.4488，threshold={'dividend_yield_min': 0.03, 'dividend_steady_weight_min': 0.5, 'style_exposure_formal_coverage_min': 0.7}
- `quality_growth`：threshold_not_met，observed=0.0721，threshold={'roe_weighted_min': 0.15, 'revenue_growth_weighted_min': 0.15, 'quality_growth_weight_min': 0.4, 'style_exposure_formal_coverage_min': 0.7}

**因为数据不足/范围边界不能算**
- 无

**白话解释**

富国沪深300指数增强A 更像指数/指数增强工具，重点应看跟踪标的、穿透持仓、费率和相对基准，而不是只按主动权益基金解释。估值因子偏低，呈现深度价值特征。费率不高，但 fee_low 标签本身仍需进一步校准。

### 000051 华夏沪深300ETF联接A

- 分类：指数型-股票
- 样本池：数据缺口/穿透不足池
- 进入分组：数据缺口/人工复核池；被动指数工具池
- 最新持仓权重：1.25%（323 条，2025-12-31）

**打出的标签**
- `data_insufficient`（data_quality，observe，confidence=1.0）
- `fee_low`（fee_size，observe，confidence=0.85）
- `industry_diversified`（holding_structure，observe，confidence=0.8）
- `manager_tenure_long`（manager，observe，confidence=0.9）
- `long_term_return_strong`（return_risk，observe，confidence=0.8）
- `sharpe_high`（return_risk，observe，confidence=0.75）
- `manual_review_required`（review，observe，confidence=1.0）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `data_insufficient` / `missing_required_fields`：value=stock_holdings，threshold=all_required_fields_present；缺少必要数据：stock_holdings，不能生成正式标签。
- `data_insufficient` / `stock_holdings:stock_holdings_total_weight_low`：value=0.0125，threshold=0.5；字段 stock_holdings 未通过 gate「stock_holdings_total_weight_low」：实际=0.0125，阈值=0.5。
- `fee_low` / `total_annual_fee`：value=0.002，threshold=0.015；管理费、托管费和销售服务费合计 0.20%，不高于 1.50%。
- `industry_diversified` / `industry_top1_weight_and_count`：value=top1=0.84%, count=14，threshold=top1<20.00%, count>=5；第一大行业占比 0.84% 低于 20.00%，且覆盖 14 个行业（≥5），行业分散。
- `long_term_return_strong` / `annualized_return_1y`：value=0.323371，threshold=0.15；1Y 年化收益率 32.34%，达到 15.00% 阈值。
- `manager_tenure_long` / `manager_tenure_years`：value=9.12，threshold=5.0；当前基金经理任期 9.1 年，达到 5.0 年稳定性阈值。
- `sharpe_high` / `sharpe_ratio_1y`：value=2.219794，threshold=1.0；1Y 夏普 2.22，达到 1.00。
- `style_pending_rule_definition` / `style_coverage_weight`：value=0.0125，threshold=deep_value≥40%, quality_growth≥40%, dividend_steady≥50%；股票因子已经存在，但没有任何风格指标达到阈值。deep_value=0%, quality_growth=0%, dividend_steady=1%.

**没打出来的标签（前 8 项）**
- `data_sufficient`：coverage_failed，observed=stock_holdings:stock_holdings_total_weight_low，threshold=all_required_fields_present
- `fee_high`：threshold_not_met，observed=0.002，threshold={'total_annual_fee_min': 0.025}
- `fund_size_moderate`：threshold_not_met，observed=115.57，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `fund_size_small`：threshold_not_met，observed=115.57，threshold={'fund_size_max': 1.0}
- `equity_position_high`：threshold_not_met，observed=0.0125，threshold={'equity_position_min': 0.8}
- `industry_concentration_high`：threshold_not_met，observed=0.0084，threshold={'industry_top1_weight_min': 0.35}
- `drawdown_high`：threshold_not_met，observed=-0.072748，threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'}
- `return_window_insufficient`：return_window_available，observed=1y，threshold=1y_or_3y_window_required

**因为数据不足/范围边界不能算**
- `holding_concentration_high`：stock_holdings_total_weight_low，observed=0.0125，threshold=0.5
- `deep_value`：stock_holdings_total_weight_low，observed=0.0125，threshold=0.5
- `dividend_steady`：stock_holdings_total_weight_low，observed=0.0125，threshold=0.5
- `quality_growth`：stock_holdings_total_weight_low，observed=0.0125，threshold=0.5
- `style_unlabeled_stock_factors_missing`：stock_holdings_total_weight_low，observed=0.0125，threshold=0.5

**白话解释**

华夏沪深300ETF联接A 当前不适合直接下正式权益标签结论：基础类型是 指数型-股票，但持仓穿透或股票仓位不足，系统将它放入人工复核/范围边界池，避免把数据缺口误解释成基金特征。

### 000058 国联安安泰灵活配置混合A

- 分类：混合型-灵活
- 样本池：范围边界/低权益仓位池
- 进入分组：数据缺口/人工复核池
- 最新持仓权重：31.99%（51 条，2025-12-31）

**打出的标签**
- `data_insufficient`（data_quality，observe，confidence=1.0）
- `fee_low`（fee_size，observe，confidence=0.85）
- `industry_diversified`（holding_structure，observe，confidence=0.8）
- `manager_tenure_long`（manager，observe，confidence=0.9）
- `volatility_low`（return_risk，observe，confidence=0.7）
- `manual_review_required`（review，observe，confidence=1.0）
- `style_pending_rule_definition`（style_boundary，observe，confidence=1.0）

**为什么打出来（证据摘要）**
- `data_insufficient` / `missing_required_fields`：value=stock_holdings，threshold=all_required_fields_present；缺少必要数据：stock_holdings，不能生成正式标签。
- `data_insufficient` / `stock_holdings:stock_holdings_total_weight_low`：value=0.3199，threshold=0.5；字段 stock_holdings 未通过 gate「stock_holdings_total_weight_low」：实际=0.3199，阈值=0.5。
- `fee_low` / `total_annual_fee`：value=0.011，threshold=0.015；管理费、托管费和销售服务费合计 1.10%，不高于 1.50%。
- `industry_diversified` / `industry_top1_weight_and_count`：value=top1=19.84%, count=6，threshold=top1<20.00%, count>=5；第一大行业占比 19.84% 低于 20.00%，且覆盖 6 个行业（≥5），行业分散。
- `manager_tenure_long` / `manager_tenure_years`：value=13.89，threshold=5.0；当前基金经理任期 13.9 年，达到 5.0 年稳定性阈值。
- `style_pending_rule_definition` / `style_coverage_weight`：value=0.3199，threshold=deep_value≥40%, quality_growth≥40%, dividend_steady≥50%；股票因子已经存在，但没有任何风格指标达到阈值。deep_value=10%, quality_growth=3%, dividend_steady=12%.
- `volatility_low` / `annualized_volatility_1y`：value=0.040554，threshold=0.12；1Y 年化波动率 4.06%，不高于 12.00%。

**没打出来的标签（前 8 项）**
- `data_sufficient`：coverage_failed，observed=stock_holdings:stock_holdings_total_weight_low，threshold=all_required_fields_present
- `fee_high`：threshold_not_met，observed=0.011，threshold={'total_annual_fee_min': 0.025}
- `fund_size_moderate`：threshold_not_met，observed=1.55，threshold={'fund_size_min': 5.0, 'fund_size_max': 100.0}
- `fund_size_small`：threshold_not_met，observed=1.55，threshold={'fund_size_max': 1.0}
- `equity_position_high`：threshold_not_met，observed=0.3199，threshold={'equity_position_min': 0.8}
- `industry_concentration_high`：threshold_not_met，observed=0.1984，threshold={'industry_top1_weight_min': 0.35}
- `drawdown_high`：threshold_not_met，observed=-0.036915，threshold={'max_drawdown_max': -0.2, 'window': '3y|1y'}
- `long_term_return_strong`：threshold_not_met，observed=0.040371，threshold={'annualized_return_min': 0.15, 'window': '3y|1y'}

**因为数据不足/范围边界不能算**
- `holding_concentration_high`：stock_holdings_total_weight_low，observed=0.3199，threshold=0.5
- `deep_value`：stock_holdings_total_weight_low，observed=0.3199，threshold=0.5
- `dividend_steady`：stock_holdings_total_weight_low，observed=0.3199，threshold=0.5
- `quality_growth`：stock_holdings_total_weight_low，observed=0.3199，threshold=0.5
- `style_unlabeled_stock_factors_missing`：stock_holdings_total_weight_low，observed=0.3199，threshold=0.5

**白话解释**

国联安安泰灵活配置混合A 当前不适合直接下正式权益标签结论：基础类型是 混合型-灵活，但持仓穿透或股票仓位不足，系统将它放入人工复核/范围边界池，避免把数据缺口误解释成基金特征。
