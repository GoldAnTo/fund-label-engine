# 数据契约

## 核心输入表

### fund_profiles

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| fund_name | 基金名称 |
| fund_type | 基金类型 |
| inception_date | 成立日期 |
| fund_company | 基金公司 |
| fund_size | 基金规模，亿元 |

### nav_history

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| nav_date | 净值日期 |
| nav | 单位净值 |
| adjusted_nav | 复权净值 |
| daily_return | 日收益率 |

### fund_stock_holdings

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| report_date | 报告期 |
| stock_code | 股票代码 |
| stock_name | 股票名称 |
| weight | 占基金净值比例 |
| market | 市场，例如 A/HK/US |

### fund_industry_allocations

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| report_date | 报告期 |
| industry | 行业 |
| weight | 行业占比 |

### fund_manager_links

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| manager_name | 基金经理 |
| start_date | 任职开始 |
| end_date | 任职结束 |
| tenure_years | 当前任期年限 |

### fee_structures

| 字段 | 说明 |
|---|---|
| fund_code | 基金代码 |
| management_fee | 管理费率 |
| custody_fee | 托管费率 |
| sales_service_fee | 销售服务费率 |

### stock_factors

| 字段 | 说明 |
|---|---|
| stock_code | 股票代码 |
| factor_date | 因子日期 |
| pb | 市净率 |
| roe | 净资产收益率 |
| dividend_yield | 股息率 |
| revenue_growth | 营收增长 |
| profit_growth | 利润增长 |
| market_cap_bucket | 市值分组 |
| valuation_percentile | 估值分位 |
| style | 股票风格标签 |

## 标签结果表

### label_definitions

| 字段 | 说明 |
|---|---|
| label_code | 标签代码 |
| label_name | 标签名称 |
| category | 标签类别 |
| fund_types | 适用基金类型 |
| rule_version | 规则版本 |
| enabled | 是否启用 |

### label_runs

| 字段 | 说明 |
|---|---|
| run_id | 计算批次 |
| run_at | 计算时间 |
| data_as_of | 数据日期 |
| rule_version | 规则版本 |
| status | 批次状态 |

### feature_values

| 字段 | 说明 |
|---|---|
| run_id | 计算批次 |
| fund_code | 基金代码 |
| feature_code | 特征代码 |
| value | 特征值 |
| source | 来源 |

### fund_label_results

| 字段 | 说明 |
|---|---|
| run_id | 计算批次 |
| fund_code | 基金代码 |
| label_code | 标签代码 |
| confidence | 置信度 |
| status | active/observe/rejected |

### fund_label_evidence

| 字段 | 说明 |
|---|---|
| run_id | 计算批次 |
| fund_code | 基金代码 |
| label_code | 标签代码 |
| metric | 指标 |
| value | 指标值 |
| threshold | 阈值 |
| source | 数据来源 |
| message | 解释文本 |

### label_reviews

| 字段 | 说明 |
|---|---|
| review_id | 复核记录 |
| run_id | 计算批次 |
| fund_code | 基金代码 |
| label_code | 标签代码 |
| decision | confirm/reject/observe |
| reviewer | 复核人 |
| comment | 复核备注 |

