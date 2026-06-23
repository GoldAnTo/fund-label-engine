# 标签体系设计

## 标签设计原则

每个标签必须具备：

- 标签代码
- 标签名称
- 标签类别
- 适用基金类型
- 计算口径
- 数据来源
- 证据明细
- 置信度

## 第一版标签

### 数据质量

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| data_sufficient | 数据充足 | 必要数据覆盖率达标 |
| data_insufficient | 数据不足 | 缺少必要净值、持仓、经理或费率数据 |
| manual_review_required | 需人工复核 | 数据缺失或规则无法自动确认 |

### 收益风险

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| long_term_return_strong | 长期收益优秀 | 近三年年化收益达到阈值 |
| drawdown_high | 近三年回撤较大 | 最大回撤低于阈值 |
| volatility_low | 波动较低 | 年化波动低于阈值 |
| sharpe_high | 夏普较高 | 夏普达到阈值 |

### 持仓结构

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| equity_position_high | 权益仓位高 | 股票持仓比例达到阈值 |
| holding_concentration_high | 持仓集中度高 | 前十大持仓合计达到阈值 |
| industry_concentration_high | 行业集中度高 | 第一大行业占比达到阈值 |
| industry_diversified | 行业分散 | 行业分布低集中 |

### 基金经理

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| manager_tenure_long | 经理任期较长 | 当前经理任期达到阈值 |
| manager_change_frequent | 经理变更频繁 | 指定期间内经理变更多 |

### 费用规模

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| fund_size_moderate | 基金规模适中 | 规模在合理区间 |
| fund_size_small | 规模偏小 | 规模低于阈值 |
| fee_low | 费率较低 | 综合费率低于阈值 |
| fee_high | 费率偏高 | 综合费率高于阈值 |

### 风格边界

| 标签代码 | 标签名称 | 口径 |
|---|---|---|
| style_unlabeled_stock_factors_missing | 风格未标注：缺少股票因子 | 有持仓但缺少股票因子，不能输出正式风格标签 |

## 后续高级标签

以下标签需要 `stock_factors` 或 `stock_labels`：

- deep_value，深度价值
- quality_growth，质量成长
- dividend_stable，红利稳健
- low_valuation_recovery，低估修复
- high_valuation_high_volatility，高估高波动
- style_drift，风格漂移
- crowded_holding_high，抱团程度高

