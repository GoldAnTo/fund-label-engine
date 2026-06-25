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
| volatility_high | 波动较高 | 年化波动高于阈值 |
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
| style_pending_rule_definition | 风格待计算：规则尚未启用 | 股票因子已经存在，但高级风格标签规则尚未启用 |

## 后续高级标签

以下标签需要 `stock_factors` 或 `stock_labels`：

- deep_value，深度价值
- quality_growth，质量成长
- dividend_stable，红利稳健
- low_valuation_recovery，低估修复
- high_valuation_high_volatility，高估高波动
- style_drift，风格漂移
- crowded_holding_high，抱团程度高

## 当前默认阈值

| 标签代码 | 默认阈值 | 说明 |
|---|---|---|
| holding_concentration_high | 前十大股票持仓合计 >= 55% | 后续应按基金类型和市场环境校准 |
| manager_tenure_long | 当前经理任期 >= 5 年 | 仅使用当前经理任期，暂不处理多人经理贡献拆分 |
| fee_low | 管理费 + 托管费 + 销售服务费 <= 1.5% | 当前按简单合计处理 |
| fee_high | 管理费 + 托管费 + 销售服务费 > 2.5% | 当前按简单合计处理 |
| industry_concentration_high | 第一大行业占比 >= 35% | 使用最近一期行业配置 |
| industry_diversified | 第一大行业 < 20% 且行业数 >= 5 | 使用最近一期行业配置 |
| equity_position_high | 权益仓位 >= 80% | fundData 适配时暂用最近一期股票持仓合计 |
| volatility_high | 年化波动 >= 30% | 当前按可用净值窗口计算 |
| volatility_low | 年化波动 <= 12% | 当前按可用净值窗口计算 |
| drawdown_high | 最大回撤 <= -20% | 当前按可用净值窗口计算 |
| sharpe_high | 夏普 >= 1.0 | 当前无风险利率按 0 处理 |
| long_term_return_strong | 年化收益 >= 15% | 当前按可用净值窗口计算，长期校准前请视为观察 |
| fund_size_small | 规模 < 1 亿 | 触发流动性、迷你基金风险关注 |
| fund_size_moderate | 5 亿 <= 规模 <= 100 亿 | 合理区间，避免过小或过大 |

## 状态约定

- `active`：证据完整，可以作为正式基础标签使用。
- `observe`：证据不足或规则未启用，只能作为观察提示。
- `rejected`：人工或规则复核后不采纳。

## 计算状态约定

`fund_label_results.status` 只描述已经输出的标签是否可作为正式结论。为了说明“为什么某个标签没有出现”，当前版本新增独立的 `label_calculation_states`：

| 状态 | 含义 | 示例 |
|---|---|---|
| triggered | 标签条件已满足，标签已经输出 | 年化收益达到阈值，输出 `long_term_return_strong` |
| not_triggered | 前置数据齐全，但指标没到阈值 | 经理任期只有 2 年，未触发 `manager_tenure_long` |
| not_computed | 前置数据不足，不能计算该标签 | 净值不足 1Y，不能计算收益风险标签 |

每条计算状态都必须保存：

- `label_code`：标签代码。
- `state`：计算状态。
- `reason_code`：触发、未触发或无法计算的机器原因。
- `observed`：实际观测值或缺失情况。
- `threshold`：使用的阈值或数据要求。
- `source`：数据来源。
- `message`：给前端和汇报使用的白话解释。

当前阶段先处理自动计算闭环，不把人工复核作为标签计算的必要步骤。

## 分类和分组约定

标签是原子结论，分类和分组是把原子结论整理成可比较的业务池。

- 分类写入 `fund_classification_results`，按 `dimension` 表达基金身份，例如 `asset_class`、`management_style`、`calculation_eligibility`、`style_clarity`。
- 分组写入 `fund_group_results`，按 `group_code` 表达业务池或观察池，例如 `active_equity_candidate_pool`、`passive_tool_pool`、`data_gap_pool`、`style_factor_missing_pool`。
- 分类和分组都必须保存 `reason_code`、`evidence`、`source`。
- 分组不等于推荐或最终准入，只说明“应该放在哪里比较”和“为什么放进去”。

详细规则见 `docs/fund-classification-and-grouping.md`。
