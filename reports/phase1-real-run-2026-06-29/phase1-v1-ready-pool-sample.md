# Phase1 v1 Ready Pool 验收报告

样本基金数: 8
run_id: cdfd1197a7df44de9d81bb63808cc9d3
数据源: /tmp/fle-run/source.sqlite + /tmp/fle-run/output.sqlite
审计口径: reports/phase1-real-run-2026-06-29/relative-label-eligibility.csv
基准映射: reports/phase1-real-run-2026-06-29/benchmark-mapping.csv

## 样本概览

| fund_code | fund_name | benchmark_code | mapping_reason | quality_status | relative_label_status | nav_n | bench_n |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| `000006` | 西部利得量化成长混合A | `000905:0.75+BANK_CURRENT:0.25` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000020` | 景顺长城品质投资混合A | `000300:0.80+H11001:0.20` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000039` | 农银高增长混合 | `000300:0.75+H11001:0.25` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000199` | 国泰量化策略收益混合A | `000300:0.75+H11009:0.25` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000354` | 长盛城镇化主题混合A | `000300:0.80+H11009:0.20` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000511` | 国泰国策驱动灵活配置混合A | `000300:0.50+H11009:0.50` | composite_benchmark_supported_components | ready | relative_label_ready | 256 | 241 |
| `000656` | 前海开源沪深300指数A | `000300` | tracking_target_exact_supported_index | ready | relative_label_ready | 256 | 241 |
| `100038` | 富国沪深300指数增强A | `000300` | tracking_target_exact_supported_index | ready | nav_window_insufficient | 20 | 241 |

## 逐只展示
### 000006 西部利得量化成长混合A

- fund_type: `混合型-偏股`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `中证500指数收益率*75%+同期银行活期存款利率(税后)*25%`
- benchmark_code: `000905:0.75+BANK_CURRENT:0.25`
- benchmark_name: `中证50075%+银行活期存款利率25%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000905` 中证500 weight=0.75 secid=`1.000905` status=resolved reason=index
  - 2. `BANK_CURRENT` 银行活期存款利率 weight=0.25 secid=`synthetic:0.003500` status=resolved reason=synthetic

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - business: active_equity_candidate_pool 主动权益候选池 reason=active_equity_basic_gate_passed
  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: low_valuation_group 低估值组 reason=style_label_triggered
  - style: small_cap_group 小盘组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 0.454287
  - annualized_return_1y: 0.443516
  - annualized_volatility_1y: 0.148253
  - beta_1y: -0.025799
  - information_ratio_1y: 0.095846
  - max_drawdown_1y: -0.09091
  - sharpe_ratio_1y: 2.890435
  - tracking_error_1y: 0.227999

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [fee_size] fund_size_moderate 基金规模适中 | confidence=0.80 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_style] low_valuation 低估值 | confidence=0.70 status=active
  - [holding_style] small_cap 小盘风格 | confidence=0.70 status=active
  - [holding_style] style_balanced 均衡风格 | confidence=1.00 status=observe
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=0.454287 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.025799 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.025799 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=not_triggered reason=threshold_not_met observed=0.021853 threshold={'annualized_excess_return_min': 0.05, 'window': '3y|1y'} source=benchmark_returns
  - information_ratio_high (信息比率较高): state=not_triggered reason=threshold_not_met observed=0.095846 threshold={'information_ratio_min': 0.5, 'window': '3y|1y'} source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.227999 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=0.454287 threshold=0.03 source=benchmark_returns message=1Y Alpha 45.43%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.025799 threshold=0.8 source=benchmark_returns message=1Y Beta -2.58%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - equity_position_high / equity_position: value=0.8352 threshold=0.8 source=fund_positions message=权益仓位 83.52%，达到 80.00% 权益仓位阈值。
  - fund_size_moderate / fund_size: value=13.37 threshold=5.00~100.00 亿元 source=fund_profiles message=基金规模 13.37 亿元，处于 5.00~100.00 亿元合理区间。
  - long_term_return_strong / annualized_return_1y: value=0.443516 threshold=0.15 source=nav_history message=1Y 年化收益率 44.35%，达到 15.00% 阈值。
  - low_valuation / pb_weighted/pe_weighted: value=PB=2.72, PE=49.80 threshold=PB≤4.530768317734193 或 PE≤33.699398864747614 source=fund_factor_exposures message=加权 PB=2.72，加权 PE=49.80，达到低估值阈值。
  - manager_tenure_long / manager_tenure_years: value=9.52 threshold=5.0 source=fund_manager_links message=当前基金经理任期 9.5 年，达到 5.0 年稳定性阈值。
  - sharpe_high / sharpe_ratio_1y: value=2.890435 threshold=1.0 source=nav_history message=1Y 夏普 2.89，达到 1.00。
  - small_cap / log10_market_cap_weighted: value=10.2625 threshold=10.816768535415806 source=fund_factor_exposures message=加权对数市值 10.26，达到小盘阈值 10.816768535415806。
  - style_balanced / style_balanced_weight_count: value=2 threshold=at_least_2_styles_ge_20% source=fund_factor_exposures message=无单一主导风格达阈值，但有 2 类风格权重 ≥ 20%，判为均衡风格。deep_value=28%, quality_growth=3%, dividend_steady=24%。
  - tracking_error_high / tracking_error_1y: value=0.227999 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 22.80%，达到相对基准阈值 8.00%。

### 000020 景顺长城品质投资混合A

- fund_type: `混合型-偏股`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `沪深300指数*80%+中证全债指数*20%`
- benchmark_code: `000300:0.80+H11001:0.20`
- benchmark_name: `沪深30080%+中证全债20%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=0.80 secid=`1.000300` status=resolved reason=index
  - 2. `H11001` 中证全债 weight=0.20 secid=`local:H11001` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - business: active_equity_candidate_pool 主动权益候选池 reason=active_equity_basic_gate_passed
  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_high
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: high_valuation_group 高估值组 reason=style_label_triggered
  - style: large_cap_group 大盘组 reason=style_label_triggered
  - style: profit_growth_group 利润高增长组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 1.007412
  - annualized_return_1y: 0.926359
  - annualized_volatility_1y: 0.217974
  - beta_1y: -0.155763
  - information_ratio_1y: 2.331849
  - max_drawdown_1y: -0.106932
  - sharpe_ratio_1y: 4.18105
  - tracking_error_1y: 0.264685

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_structure] industry_concentration_high 行业高度集中 | confidence=0.85 status=active
  - [holding_style] high_valuation 高估值 | confidence=0.70 status=active
  - [holding_style] large_cap 大盘风格 | confidence=0.70 status=active
  - [holding_style] profit_growth_strong 利润高增长 | confidence=0.70 status=active
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] excess_return_strong 超额收益较强 | confidence=0.75 status=active
  - [relative_benchmark] information_ratio_high 信息比率较高 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active
  - [style_boundary] style_pending_rule_definition 风格未达阈值 | confidence=1.00 status=observe

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=1.007412 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.155763 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.155763 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=triggered reason=threshold_met observed=0.617206 threshold=0.05 source=benchmark_returns
  - information_ratio_high (信息比率较高): state=triggered reason=threshold_met observed=2.331849 threshold=0.5 source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.264685 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=1.007412 threshold=0.03 source=benchmark_returns message=1Y Alpha 100.74%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.155763 threshold=0.8 source=benchmark_returns message=1Y Beta -15.58%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - equity_position_high / equity_position: value=0.8857 threshold=0.8 source=fund_positions message=权益仓位 88.57%，达到 80.00% 权益仓位阈值。
  - excess_return_strong / annualized_excess_return_1y: value=0.617206 threshold=0.05 source=benchmark_returns message=1Y 年化超额收益 61.72%，达到相对基准阈值 5.00%。
  - high_valuation / pb_weighted/pe_weighted: value=PB=8.77, PE=53.38 threshold=PB≥8.215995947752846 或 PE≥71.36983492111406 source=fund_factor_exposures message=加权 PB=8.77，加权 PE=53.38，达到高估值阈值。
  - industry_concentration_high / industry_top1_weight: value=0.6009 threshold=0.6 source=fund_industry_allocations message=第一大行业占比 60.09%，达到 60.00% 行业高度集中阈值。
  - information_ratio_high / information_ratio_1y: value=2.331849 threshold=0.5 source=benchmark_returns message=1Y 信息比率 233.18%，达到相对基准阈值 50.00%。
  - large_cap / log10_market_cap_weighted: value=11.2651 threshold=10.987392528384815 source=fund_factor_exposures message=加权对数市值 11.27，达到大盘阈值 10.987392528384815。
  - long_term_return_strong / annualized_return_1y: value=0.926359 threshold=0.15 source=nav_history message=1Y 年化收益率 92.64%，达到 15.00% 阈值。
  - manager_tenure_long / manager_tenure_years: value=10.42 threshold=5.0 source=fund_manager_links message=当前基金经理任期 10.4 年，达到 5.0 年稳定性阈值。
  - profit_growth_strong / profit_growth_weighted: value=0.414 threshold=0.38014767467228566 source=fund_factor_exposures message=加权利润增速=41.40%，达到阈值 38%。
  - sharpe_high / sharpe_ratio_1y: value=4.18105 threshold=1.0 source=nav_history message=1Y 夏普 4.18，达到 1.00。
  - style_pending_rule_definition / style_factor_coverage_weight: value=0.8857 threshold=style_weights_below_threshold source=fund_factor_exposures message=已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
  - tracking_error_high / tracking_error_1y: value=0.264685 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 26.47%，达到相对基准阈值 8.00%。

### 000039 农银高增长混合

- fund_type: `混合型-偏股`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `75%×沪深300指数+25%×中证全债指数`
- benchmark_code: `000300:0.75+H11001:0.25`
- benchmark_name: `沪深30075%+中证全债25%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=0.75 secid=`1.000300` status=resolved reason=index
  - 2. `H11001` 中证全债 weight=0.25 secid=`local:H11001` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_observe
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: high_roe_group 高盈利组 reason=style_label_triggered
  - style: high_valuation_group 高估值组 reason=style_label_triggered
  - style: large_cap_group 大盘组 reason=style_label_triggered
  - style: profit_growth_group 利润高增长组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered
  - style: tech_group 科技主题组 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 1.287504
  - annualized_return_1y: 1.152775
  - annualized_volatility_1y: 0.305116
  - beta_1y: -0.246755
  - information_ratio_1y: 2.501457
  - max_drawdown_1y: -0.146907
  - sharpe_ratio_1y: 3.728995
  - tracking_error_1y: 0.341394

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_structure] industry_concentration_observe 行业集中观察 | confidence=0.75 status=observe
  - [holding_style] high_roe 高盈利质量 | confidence=0.70 status=active
  - [holding_style] high_valuation 高估值 | confidence=0.70 status=active
  - [holding_style] large_cap 大盘风格 | confidence=0.70 status=active
  - [holding_style] profit_growth_strong 利润高增长 | confidence=0.70 status=active
  - [holding_style] tech_focused 科技主题 | confidence=0.70 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] excess_return_strong 超额收益较强 | confidence=0.75 status=active
  - [relative_benchmark] information_ratio_high 信息比率较高 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active
  - [return_risk] volatility_high 波动较高 | confidence=0.75 status=active
  - [style_boundary] style_pending_rule_definition 风格未达阈值 | confidence=1.00 status=observe

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=1.287504 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.246755 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.246755 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=triggered reason=threshold_met observed=0.853982 threshold=0.05 source=benchmark_returns
  - information_ratio_high (信息比率较高): state=triggered reason=threshold_met observed=2.501457 threshold=0.5 source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.341394 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=1.287504 threshold=0.03 source=benchmark_returns message=1Y Alpha 128.75%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.246755 threshold=0.8 source=benchmark_returns message=1Y Beta -24.68%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - equity_position_high / equity_position: value=0.8452 threshold=0.8 source=fund_positions message=权益仓位 84.52%，达到 80.00% 权益仓位阈值。
  - excess_return_strong / annualized_excess_return_1y: value=0.853982 threshold=0.05 source=benchmark_returns message=1Y 年化超额收益 85.40%，达到相对基准阈值 5.00%。
  - high_roe / roe_weighted: value=0.1723 threshold=0.13263276773825378 source=fund_factor_exposures message=加权 ROE=17.23%，达到阈值 13%。
  - high_valuation / pb_weighted/pe_weighted: value=PB=19.19, PE=125.08 threshold=PB≥8.215995947752846 或 PE≥71.36983492111406 source=fund_factor_exposures message=加权 PB=19.19，加权 PE=125.08，达到高估值阈值。
  - industry_concentration_observe / industry_top1_weight: value=0.4625 threshold=45.00%~60.00% source=fund_industry_allocations message=第一大行业占比 46.25%，进入 45.00%~60.00% 行业集中观察区间。
  - information_ratio_high / information_ratio_1y: value=2.501457 threshold=0.5 source=benchmark_returns message=1Y 信息比率 250.15%，达到相对基准阈值 50.00%。
  - large_cap / log10_market_cap_weighted: value=11.2274 threshold=10.987392528384815 source=fund_factor_exposures message=加权对数市值 11.23，达到大盘阈值 10.987392528384815。
  - long_term_return_strong / annualized_return_1y: value=1.152775 threshold=0.15 source=nav_history message=1Y 年化收益率 115.28%，达到 15.00% 阈值。
  - profit_growth_strong / profit_growth_weighted: value=1.0428 threshold=0.38014767467228566 source=fund_factor_exposures message=加权利润增速=104.28%，达到阈值 38%。
  - sharpe_high / sharpe_ratio_1y: value=3.728995 threshold=1.0 source=nav_history message=1Y 夏普 3.73，达到 1.00。
  - style_pending_rule_definition / style_factor_coverage_weight: value=0.8452 threshold=style_weights_below_threshold source=fund_factor_exposures message=已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
  - tech_focused / tech_industry_weight: value=0.8864 threshold=0.4 source=fund_factor_exposures message=tech 行业持仓权重 89%，达到阈值 40%。
  - tracking_error_high / tracking_error_1y: value=0.341394 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 34.14%，达到相对基准阈值 8.00%。
  - volatility_high / annualized_volatility_1y: value=0.305116 threshold=0.3 source=nav_history message=1Y 年化波动率 30.51%，高于 30.00%。

### 000199 国泰量化策略收益混合A

- fund_type: `混合型-偏股`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `沪深300指数收益率*75%+中证综合债指数收益率*25%`
- benchmark_code: `000300:0.75+H11009:0.25`
- benchmark_name: `沪深30075%+中证综合债25%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=0.75 secid=`1.000300` status=resolved reason=index
  - 2. `H11009` 中证综合债 weight=0.25 secid=`local:H11009` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - business: active_equity_candidate_pool 主动权益候选池 reason=active_equity_basic_gate_passed
  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_observe
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: composite_group 组合风格组 reason=style_label_triggered
  - style: dividend_steady_group 红利稳健组 reason=style_label_triggered
  - style: low_valuation_group 低估值组 reason=style_label_triggered
  - style: profit_growth_group 利润高增长组 reason=style_label_triggered
  - style: small_cap_group 小盘组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 0.545526
  - annualized_return_1y: 0.509723
  - annualized_volatility_1y: 0.162318
  - beta_1y: -0.145878
  - information_ratio_1y: 1.226836
  - max_drawdown_1y: -0.097283
  - sharpe_ratio_1y: 3.047868
  - tracking_error_1y: 0.21274

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_structure] industry_concentration_observe 行业集中观察 | confidence=0.75 status=observe
  - [holding_style] dividend_steady 红利稳健 | confidence=0.75 status=active
  - [holding_style] low_valuation 低估值 | confidence=0.70 status=active
  - [holding_style] profit_growth_strong 利润高增长 | confidence=0.70 status=active
  - [holding_style] small_cap 小盘风格 | confidence=0.70 status=active
  - [holding_style] small_cap_growth 小盘高成长 | confidence=0.65 status=active
  - [holding_style] value_dividend 价值红利 | confidence=0.65 status=active
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] excess_return_strong 超额收益较强 | confidence=0.75 status=active
  - [relative_benchmark] information_ratio_high 信息比率较高 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=0.545526 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.145878 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.145878 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=triggered reason=threshold_met observed=0.260996 threshold=0.05 source=benchmark_returns
  - information_ratio_high (信息比率较高): state=triggered reason=threshold_met observed=1.226836 threshold=0.5 source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.21274 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=0.545526 threshold=0.03 source=benchmark_returns message=1Y Alpha 54.55%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.145878 threshold=0.8 source=benchmark_returns message=1Y Beta -14.59%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - dividend_steady / dividend_steady_weight: value=0.4124 threshold=0.3 source=fund_factor_exposures message=预聚合红利持仓权重 41%，达到 30% 阈值；行业映射覆盖率 100%；financial=13%, energy_utility=18%, consumer=21%。红利贡献未被单一金融/能源或消费行业主导。 因子覆盖权重 91%。
  - equity_position_high / equity_position: value=0.9148 threshold=0.8 source=fund_positions message=权益仓位 91.48%，达到 80.00% 权益仓位阈值。
  - excess_return_strong / annualized_excess_return_1y: value=0.260996 threshold=0.05 source=benchmark_returns message=1Y 年化超额收益 26.10%，达到相对基准阈值 5.00%。
  - industry_concentration_observe / industry_top1_weight: value=0.5796 threshold=45.00%~60.00% source=fund_industry_allocations message=第一大行业占比 57.96%，进入 45.00%~60.00% 行业集中观察区间。
  - information_ratio_high / information_ratio_1y: value=1.226836 threshold=0.5 source=benchmark_returns message=1Y 信息比率 122.68%，达到相对基准阈值 50.00%。
  - long_term_return_strong / annualized_return_1y: value=0.509723 threshold=0.15 source=nav_history message=1Y 年化收益率 50.97%，达到 15.00% 阈值。
  - low_valuation / pb_weighted/pe_weighted: value=PB=3.58, PE=34.13 threshold=PB≤4.530768317734193 或 PE≤33.699398864747614 source=fund_factor_exposures message=加权 PB=3.58，加权 PE=34.13，达到低估值阈值。
  - manager_tenure_long / manager_tenure_years: value=7.74 threshold=5.0 source=fund_manager_links message=当前基金经理任期 7.7 年，达到 5.0 年稳定性阈值。
  - profit_growth_strong / profit_growth_weighted: value=0.4704 threshold=0.38014767467228566 source=fund_factor_exposures message=加权利润增速=47.04%，达到阈值 38%。
  - sharpe_high / sharpe_ratio_1y: value=3.047868 threshold=1.0 source=nav_history message=1Y 夏普 3.05，达到 1.00。
  - small_cap / log10_market_cap_weighted: value=10.3835 threshold=10.816768535415806 source=fund_factor_exposures message=加权对数市值 10.38，达到小盘阈值 10.816768535415806。
  - small_cap_growth / composite_styles: value=profit_growth_strong+small_cap threshold=同时命中 source=fund_factor_exposures message=同时命中 profit_growth_strong + small_cap，组合为小盘高成长。
  - tracking_error_high / tracking_error_1y: value=0.21274 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 21.27%，达到相对基准阈值 8.00%。
  - value_dividend / composite_styles: value=dividend_steady+low_valuation threshold=同时命中 source=fund_factor_exposures message=同时命中 dividend_steady + low_valuation，组合为价值红利。

### 000354 长盛城镇化主题混合A

- fund_type: `混合型-偏股`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `沪深300指数收益率*80%+中证综合债指数收益率*20%`
- benchmark_code: `000300:0.80+H11009:0.20`
- benchmark_name: `沪深30080%+中证综合债20%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=0.80 secid=`1.000300` status=resolved reason=index
  - 2. `H11009` 中证综合债 weight=0.20 secid=`local:H11009` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - business: active_equity_candidate_pool 主动权益候选池 reason=active_equity_basic_gate_passed
  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_high
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: composite_group 组合风格组 reason=style_label_triggered
  - style: high_roe_group 高盈利组 reason=style_label_triggered
  - style: high_valuation_group 高估值组 reason=style_label_triggered
  - style: large_cap_group 大盘组 reason=style_label_triggered
  - style: profit_growth_group 利润高增长组 reason=style_label_triggered
  - style: quality_growth_group 质量成长组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered
  - style: tech_group 科技主题组 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 3.203054
  - annualized_return_1y: 2.718319
  - annualized_volatility_1y: 0.493694
  - beta_1y: -0.240845
  - information_ratio_1y: 4.56527
  - max_drawdown_1y: -0.161043
  - sharpe_ratio_1y: 5.475694
  - tracking_error_1y: 0.52195

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_structure] holding_concentration_high 持仓集中度高 | confidence=0.90 status=active
  - [holding_structure] industry_concentration_high 行业高度集中 | confidence=0.85 status=active
  - [holding_style] growth_large_cap 大盘成长 | confidence=0.65 status=active
  - [holding_style] growth_profit 成长盈利 | confidence=0.65 status=active
  - [holding_style] high_roe 高盈利质量 | confidence=0.70 status=active
  - [holding_style] high_valuation 高估值 | confidence=0.70 status=active
  - [holding_style] large_cap 大盘风格 | confidence=0.70 status=active
  - [holding_style] profit_growth_strong 利润高增长 | confidence=0.70 status=active
  - [holding_style] quality_growth 质量成长 | confidence=0.75 status=active
  - [holding_style] tech_focused 科技主题 | confidence=0.70 status=active
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] excess_return_strong 超额收益较强 | confidence=0.75 status=active
  - [relative_benchmark] information_ratio_high 信息比率较高 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active
  - [return_risk] volatility_high 波动较高 | confidence=0.75 status=active

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=3.203054 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.240845 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.240845 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=triggered reason=threshold_met observed=2.382841 threshold=0.05 source=benchmark_returns
  - information_ratio_high (信息比率较高): state=triggered reason=threshold_met observed=4.56527 threshold=0.5 source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.52195 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=3.203054 threshold=0.03 source=benchmark_returns message=1Y Alpha 320.31%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.240845 threshold=0.8 source=benchmark_returns message=1Y Beta -24.08%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - equity_position_high / equity_position: value=0.9262 threshold=0.8 source=fund_positions message=权益仓位 92.62%，达到 80.00% 权益仓位阈值。
  - excess_return_strong / annualized_excess_return_1y: value=2.382841 threshold=0.05 source=benchmark_returns message=1Y 年化超额收益 238.28%，达到相对基准阈值 5.00%。
  - growth_large_cap / composite_styles: value=large_cap+quality_growth threshold=同时命中 source=fund_factor_exposures message=同时命中 large_cap + quality_growth，组合为大盘成长。
  - growth_profit / composite_styles: value=profit_growth_strong+quality_growth threshold=同时命中 source=fund_factor_exposures message=同时命中 profit_growth_strong + quality_growth，组合为成长盈利。
  - high_roe / roe_weighted: value=0.1998 threshold=0.13263276773825378 source=fund_factor_exposures message=加权 ROE=19.98%，达到阈值 13%。
  - high_valuation / pb_weighted/pe_weighted: value=PB=35.85, PE=190.81 threshold=PB≥8.215995947752846 或 PE≥71.36983492111406 source=fund_factor_exposures message=加权 PB=35.85，加权 PE=190.81，达到高估值阈值。
  - holding_concentration_high / top_10_holding_weight: value=0.6604 threshold=0.55 source=fund_stock_holdings message=前十大持仓合计 66.04%，达到持仓集中度高阈值 55.00%。
  - industry_concentration_high / industry_top1_weight: value=0.7422 threshold=0.6 source=fund_industry_allocations message=第一大行业占比 74.22%，达到 60.00% 行业高度集中阈值。
  - information_ratio_high / information_ratio_1y: value=4.56527 threshold=0.5 source=benchmark_returns message=1Y 信息比率 456.53%，达到相对基准阈值 50.00%。
  - large_cap / log10_market_cap_weighted: value=11.2924 threshold=10.987392528384815 source=fund_factor_exposures message=加权对数市值 11.29，达到大盘阈值 10.987392528384815。
  - long_term_return_strong / annualized_return_1y: value=2.718319 threshold=0.15 source=nav_history message=1Y 年化收益率 271.83%，达到 15.00% 阈值。
  - manager_tenure_long / manager_tenure_years: value=7.99 threshold=5.0 source=fund_manager_links message=当前基金经理任期 8.0 年，达到 5.0 年稳定性阈值。
  - profit_growth_strong / profit_growth_weighted: value=1.5171 threshold=0.38014767467228566 source=fund_factor_exposures message=加权利润增速=151.71%，达到阈值 38%。
  - quality_growth / quality_growth_weight: value=0.4569 threshold=0.4 source=fund_factor_exposures message=预聚合质量成长持仓权重 46%，达到 40% 阈值。 因子覆盖权重 93%。
  - sharpe_high / sharpe_ratio_1y: value=5.475694 threshold=1.0 source=nav_history message=1Y 夏普 5.48，达到 1.00。
  - tech_focused / tech_industry_weight: value=0.8132 threshold=0.4 source=fund_factor_exposures message=tech 行业持仓权重 81%，达到阈值 40%。
  - tracking_error_high / tracking_error_1y: value=0.52195 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 52.20%，达到相对基准阈值 8.00%。
  - volatility_high / annualized_volatility_1y: value=0.493694 threshold=0.3 source=nav_history message=1Y 年化波动率 49.37%，高于 30.00%。

### 000511 国泰国策驱动灵活配置混合A

- fund_type: `混合型-灵活`
- tracking_target: `该基金无跟踪标的`
- benchmark (raw): `沪深300指数收益率×50%+中证综合债券指数收益率×50%`
- benchmark_code: `000300:0.50+H11009:0.50`
- benchmark_name: `沪深30050%+中证综合债50%`
- mapping_reason: `composite_benchmark_supported_components`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=0.50 secid=`1.000300` status=resolved reason=index
  - 2. `H11009` 中证综合债 weight=0.50 secid=`local:H11009` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: cyclical_group 周期主题组 reason=style_label_triggered
  - style: mid_cap_group 中盘组 reason=style_label_triggered
  - style: profit_growth_group 利润高增长组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 0.056402
  - annualized_return_1y: 0.008915
  - annualized_volatility_1y: 0.208118
  - beta_1y: -0.54235
  - information_ratio_1y: -0.506761
  - max_drawdown_1y: -0.306135
  - sharpe_ratio_1y: -0.029239
  - tracking_error_1y: 0.241054

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [fee_size] fee_low 费率较低 | confidence=0.85 status=active
  - [fee_size] fund_size_small 规模偏小 | confidence=0.80 status=active
  - [holding_style] cyclical_focused 周期主题 | confidence=0.70 status=active
  - [holding_style] mid_cap 中盘风格 | confidence=0.70 status=active
  - [holding_style] profit_growth_strong 利润高增长 | confidence=0.70 status=active
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] drawdown_high 回撤较大 | confidence=0.75 status=active
  - [style_boundary] style_pending_rule_definition 风格未达阈值 | confidence=1.00 status=observe

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=0.056402 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.54235 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.54235 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=not_triggered reason=threshold_not_met observed=-0.122157 threshold={'annualized_excess_return_min': 0.05, 'window': '3y|1y'} source=benchmark_returns
  - information_ratio_high (信息比率较高): state=not_triggered reason=threshold_not_met observed=-0.506761 threshold={'information_ratio_min': 0.5, 'window': '3y|1y'} source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.241054 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=0.056402 threshold=0.03 source=benchmark_returns message=1Y Alpha 5.64%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.54235 threshold=0.8 source=benchmark_returns message=1Y Beta -54.23%，达到相对基准阈值 80.00%。
  - cyclical_focused / cyclical_industry_weight: value=0.7277 threshold=0.4 source=fund_factor_exposures message=cyclical 行业持仓权重 73%，达到阈值 40%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - drawdown_high / max_drawdown_1y: value=-0.306135 threshold=-0.2 source=nav_history message=1Y 最大回撤 -30.61%，低于 -20.00%。
  - fee_low / total_annual_fee: value=0.0086 threshold=0.012 source=fee_structures message=管理费、托管费和销售服务费合计 0.86%，不高于 1.20%。
  - fund_size_small / fund_size: value=0.66 threshold=1.0 source=fund_profiles message=基金规模 0.66 亿元，低于 1.00 亿元。
  - manager_tenure_long / manager_tenure_years: value=15.69 threshold=5.0 source=fund_manager_links message=当前基金经理任期 15.7 年，达到 5.0 年稳定性阈值。
  - mid_cap / log10_market_cap_weighted: value=10.8453 threshold=10.816768535415806~11.145162057169223 source=fund_factor_exposures message=加权对数市值 10.85，处于中盘区间。
  - profit_growth_strong / profit_growth_weighted: value=0.7557 threshold=0.38014767467228566 source=fund_factor_exposures message=加权利润增速=75.57%，达到阈值 38%。
  - style_pending_rule_definition / style_factor_coverage_weight: value=0.7636 threshold=style_weights_below_threshold source=fund_factor_exposures message=已有基金级因子暴露，但深度价值、质量成长、红利稳健权重均未达阈值。
  - tracking_error_high / tracking_error_1y: value=0.241054 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 24.11%，达到相对基准阈值 8.00%。

### 000656 前海开源沪深300指数A

- fund_type: `指数型-股票`
- tracking_target: `沪深300指数`
- benchmark (raw): `沪深300指数收益率*95%+银行活期存款利率(税后)*5%`
- benchmark_code: `000300`
- benchmark_name: `沪深300`
- mapping_reason: `tracking_target_exact_supported_index`
- eligibility: `quality_status=ready`, `relative_label_status=relative_label_ready`
- nav_sample_count: `256`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=1.00 secid=`1.000300` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: label_ready 标签计算可用 | conf=0.95 reason=coverage_passed
  - management_style: passive_index 被动指数工具 | conf=0.90 reason=index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - business: passive_tool_pool 被动指数工具池 reason=index_keyword_or_type
  - data_quality: label_ready_pool 标签可计算池 reason=coverage_passed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_observe
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: dividend_steady_group 红利稳健组 reason=style_label_triggered
  - style: large_cap_group 大盘组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

  - alpha_1y: 0.361278
  - annualized_return_1y: 0.330817
  - annualized_volatility_1y: 0.145544
  - beta_1y: -0.115999
  - information_ratio_1y: 0.173423
  - max_drawdown_1y: -0.071594
  - sharpe_ratio_1y: 2.169914
  - tracking_error_1y: 0.229168

#### Label results (active)

  - [data_quality] data_sufficient 数据充足 | confidence=0.95 status=active
  - [fee_size] fee_low 费率较低 | confidence=0.85 status=active
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=active
  - [holding_structure] industry_concentration_observe 行业集中观察 | confidence=0.75 status=observe
  - [holding_style] dividend_steady 红利稳健 | confidence=0.75 status=active
  - [holding_style] large_cap 大盘风格 | confidence=0.70 status=active
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=active
  - [relative_benchmark] alpha_positive Alpha 为正 | confidence=0.75 status=active
  - [relative_benchmark] beta_low Beta 较低 | confidence=0.75 status=active
  - [relative_benchmark] tracking_error_high 跟踪误差较高 | confidence=0.75 status=active
  - [return_risk] long_term_return_strong 长期收益优秀 | confidence=0.80 status=active
  - [return_risk] sharpe_high 夏普较高 | confidence=0.75 status=active

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=triggered reason=threshold_met observed=0.361278 threshold=0.03 source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=not_triggered reason=benchmark_window_available observed=1y threshold=1y_or_3y_relative_window_required source=benchmark_returns
  - beta_high (Beta 较高): state=not_triggered reason=threshold_not_met observed=-0.115999 threshold={'beta_min': 1.2, 'window': '3y|1y'} source=benchmark_returns
  - beta_low (Beta 较低): state=triggered reason=threshold_met observed=-0.115999 threshold=0.8 source=benchmark_returns
  - excess_return_strong (超额收益较强): state=not_triggered reason=threshold_not_met observed=0.039743 threshold={'annualized_excess_return_min': 0.05, 'window': '3y|1y'} source=benchmark_returns
  - information_ratio_high (信息比率较高): state=not_triggered reason=threshold_not_met observed=0.173423 threshold={'information_ratio_min': 0.5, 'window': '3y|1y'} source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=triggered reason=threshold_met observed=0.229168 threshold=0.08 source=benchmark_returns

#### Label evidence

  - alpha_positive / alpha_1y: value=0.361278 threshold=0.03 source=benchmark_returns message=1Y Alpha 36.13%，达到相对基准阈值 3.00%。
  - beta_low / beta_1y: value=-0.115999 threshold=0.8 source=benchmark_returns message=1Y Beta -11.60%，达到相对基准阈值 80.00%。
  - data_sufficient / required_fields_present: value=yes threshold=all_required_fields_present source=coverage_check message=基础净值、持仓、行业、经理、费率和规模数据均已提供。
  - dividend_steady / dividend_steady_weight: value=0.3783 threshold=0.3 source=fund_factor_exposures message=预聚合红利持仓权重 38%，达到 30% 阈值；行业映射覆盖率 99%；financial=36%, energy_utility=15%, consumer=22%。红利贡献未被单一金融/能源或消费行业主导。 因子覆盖权重 93%。
  - equity_position_high / equity_position: value=0.931 threshold=0.8 source=fund_positions message=权益仓位 93.10%，达到 80.00% 权益仓位阈值。
  - fee_low / total_annual_fee: value=0.006 threshold=0.012 source=fee_structures message=管理费、托管费和销售服务费合计 0.60%，不高于 1.20%。
  - industry_concentration_observe / industry_top1_weight: value=0.5218 threshold=45.00%~60.00% source=fund_industry_allocations message=第一大行业占比 52.18%，进入 45.00%~60.00% 行业集中观察区间。
  - large_cap / log10_market_cap_weighted: value=11.4482 threshold=10.987392528384815 source=fund_factor_exposures message=加权对数市值 11.45，达到大盘阈值 10.987392528384815。
  - long_term_return_strong / annualized_return_1y: value=0.330817 threshold=0.15 source=nav_history message=1Y 年化收益率 33.08%，达到 15.00% 阈值。
  - manager_tenure_long / manager_tenure_years: value=6.07 threshold=5.0 source=fund_manager_links message=当前基金经理任期 6.1 年，达到 5.0 年稳定性阈值。
  - sharpe_high / sharpe_ratio_1y: value=2.169914 threshold=1.0 source=nav_history message=1Y 夏普 2.17，达到 1.00。
  - tracking_error_high / tracking_error_1y: value=0.229168 threshold=0.08 source=benchmark_returns message=1Y 年化跟踪误差 22.92%，达到相对基准阈值 8.00%。

### 100038 富国沪深300指数增强A

- fund_type: `指数型-股票`
- tracking_target: `沪深300指数`
- benchmark (raw): `沪深300指数收益率*95%+1.5%(指年收益率,评价时按期间折算)`
- benchmark_code: `000300`
- benchmark_name: `沪深300`
- mapping_reason: `tracking_target_exact_supported_index`
- eligibility: `quality_status=ready`, `relative_label_status=nav_window_insufficient`
- nav_sample_count: `20`
- benchmark_sample_count: `241`

#### Benchmark components

  - 1. `000300` 沪深300 weight=1.00 secid=`1.000300` status=resolved reason=index

#### Classification

  - asset_class: equity_related 权益相关基金 | conf=0.95 reason=fund_type_supported
  - calculation_eligibility: data_gap 数据缺口 | conf=0.95 reason=coverage_failed
  - management_style: active 主动管理 | conf=0.75 reason=no_index_keyword_or_type
  - style_clarity: style_clear 风格已识别 | conf=0.80 reason=style_label_triggered

#### Group

  - data_quality: data_gap_pool 数据缺口池 reason=coverage_failed
  - risk_watch: industry_concentration_watch 行业集中观察池 reason=industry_concentration_observe
  - scope: phase1_active_equity_scope 第一版权益相关范围 reason=fund_type_supported
  - style: composite_group 组合风格组 reason=style_label_triggered
  - style: deep_value_group 深度价值组 reason=style_label_triggered
  - style: dividend_steady_group 红利稳健组 reason=style_label_triggered
  - style: large_cap_group 大盘组 reason=style_label_triggered
  - style: low_valuation_group 低估值组 reason=style_label_triggered
  - style: style_factor_ready_pool 风格因子可用池 reason=style_label_triggered

#### 1Y features

- (无)

#### Label results (active)

  - [data_quality] data_insufficient 数据不足 | confidence=1.00 status=observe
  - [fee_size] fee_low 费率较低 | confidence=0.85 status=observe
  - [fee_size] fund_size_moderate 基金规模适中 | confidence=0.80 status=observe
  - [holding_structure] equity_position_high 权益仓位高 | confidence=0.85 status=observe
  - [holding_structure] industry_concentration_observe 行业集中观察 | confidence=0.75 status=observe
  - [holding_style] deep_value 深度价值 | confidence=0.75 status=observe
  - [holding_style] dividend_steady 红利稳健 | confidence=0.75 status=observe
  - [holding_style] large_cap 大盘风格 | confidence=0.70 status=observe
  - [holding_style] low_valuation 低估值 | confidence=0.70 status=observe
  - [holding_style] value_dividend 价值红利 | confidence=0.65 status=observe
  - [manager] manager_tenure_long 经理任期较长 | confidence=0.90 status=observe
  - [relative_benchmark] benchmark_data_missing 基准数据缺失 | confidence=1.00 status=observe
  - [return_risk] return_window_insufficient 收益风险样本不足 | confidence=1.00 status=observe
  - [review] manual_review_required 需人工复核 | confidence=1.00 status=observe

#### Relative label calculation states

  - alpha_positive (Alpha 为正): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - benchmark_data_missing (基准数据缺失): state=triggered reason=threshold_met observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - beta_high (Beta 较高): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - beta_low (Beta 较低): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - excess_return_strong (超额收益较强): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - information_ratio_high (信息比率较高): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns
  - tracking_error_high (跟踪误差较高): state=not_computed reason=benchmark_data_missing observed=20 threshold=min(1y=180, 3y=500) source=benchmark_returns

#### Label evidence

  - benchmark_data_missing / benchmark_sample_count: value=20 threshold=min(1y=180, 3y=500) source=benchmark_returns message=缺少可对齐的 1Y/3Y 基准收益序列，暂不输出正式相对基准标签。
  - data_insufficient / missing_required_fields: value=nav_returns threshold=all_required_fields_present source=coverage_check message=缺少必要数据：nav_returns，不能生成正式标签。
  - data_insufficient / nav_returns:nav_samples_below_min: value=20 threshold=180 source=coverage_gate message=字段 nav_returns 未通过 gate「nav_samples_below_min」：实际=20，阈值=180。
  - deep_value / deep_value_weight: value=0.4106 threshold=0.4 source=fund_factor_exposures message=预聚合深度价值持仓权重 41%，达到 40% 阈值。 因子覆盖权重 93%。
  - dividend_steady / dividend_steady_weight: value=0.5045 threshold=0.3 source=fund_factor_exposures message=预聚合红利持仓权重 50%，达到 30% 阈值；行业映射覆盖率 100%；financial=28%, energy_utility=22%, consumer=21%。红利贡献未被单一金融/能源或消费行业主导。 因子覆盖权重 93%。
  - equity_position_high / equity_position: value=0.9371 threshold=0.8 source=fund_positions message=权益仓位 93.71%，达到 80.00% 权益仓位阈值。
  - fee_low / total_annual_fee: value=0.0118 threshold=0.012 source=fee_structures message=管理费、托管费和销售服务费合计 1.18%，不高于 1.20%。
  - fund_size_moderate / fund_size: value=46.17 threshold=5.00~100.00 亿元 source=fund_profiles message=基金规模 46.17 亿元，处于 5.00~100.00 亿元合理区间。
  - industry_concentration_observe / industry_top1_weight: value=0.4721 threshold=45.00%~60.00% source=fund_industry_allocations message=第一大行业占比 47.21%，进入 45.00%~60.00% 行业集中观察区间。
  - large_cap / log10_market_cap_weighted: value=11.265 threshold=10.987392528384815 source=fund_factor_exposures message=加权对数市值 11.26，达到大盘阈值 10.987392528384815。
  - low_valuation / pb_weighted/pe_weighted: value=PB=3.20, PE=25.99 threshold=PB≤4.530768317734193 或 PE≤33.699398864747614 source=fund_factor_exposures message=加权 PB=3.20，加权 PE=25.99，达到低估值阈值。
  - manager_tenure_long / manager_tenure_years: value=16.44 threshold=5.0 source=fund_manager_links message=当前基金经理任期 16.4 年，达到 5.0 年稳定性阈值。
  - return_window_insufficient / sample_count_full: value=20 threshold=min(1y=180, 3y=500) source=nav_history message=净值样本不足以支撑 1Y 或 3Y 收益风险窗口，暂不输出正式收益风险标签。
  - value_dividend / composite_styles: value=dividend_steady+low_valuation threshold=同时命中 source=fund_factor_exposures message=同时命中 dividend_steady + low_valuation，组合为价值红利。


## 一致性结论

- audit 与 output `relative_label_ready` 集合双向差集为空（已通过 verify 脚本验证）
- mapping_reason 与 component_status 全部是 `composite_benchmark_supported_components` 或 `tracking_target_exact_supported_index`
- 相对标签计算状态均 `not_computed:benchmark_data_missing`=triggered `not_triggered:benchmark_window_available` 的双向语义
- 000172 文本包含 `2.5%(指年收益率,评价时按期间折算)` 属于合成 fixed annual return 分支；若未来单独解析为 `synthetic_fixed_return`，最多释放 1 只基金，但**当前为不阻塞 v1 验收**。