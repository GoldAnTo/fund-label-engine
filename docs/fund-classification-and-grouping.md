# 基金分类和分组设计

## 为什么需要这一层

基金标签回答的是“这只基金有什么特征”，比如波动高、行业集中、经理任期长。分类和分组回答的是“这只基金应该放到哪个比较池里看”，比如主动权益候选池、被动指数工具池、数据缺口池、风格因子缺失池。

这层不是基金推荐，也不是最终准入结论。它的作用是把标签结果整理成更适合投研、产品池和前端展示的结构。

## 和 114/116 材料的关系

114 更偏产品池和准入思路：先区分基金是不是在本阶段范围内，再判断是不是有足够数据进入可计算池，主动权益基金还要关注经理稳定性、规模、回撤、行业集中等排除项。

116 更偏同类比较和风格划分：基金不能混在一起比，要先拆出主动/被动、权益/非权益、风格清晰/风格缺失，再在同类池里做标签和排序。

所以当前项目先落四个稳定维度：

- `asset_class`：是不是权益相关基金。
- `management_style`：主动管理，还是被动指数工具。
- `calculation_eligibility`：数据是否足够进入标签可计算池。
- `style_clarity`：风格已识别、待确认、还是缺少股票因子。

## 当前分类

| 维度 | 分类代码 | 含义 | 主要依据 |
|---|---|---|---|
| asset_class | equity_related | 第一版支持的权益相关基金 | fund_type 属于股票型、偏股混合、灵活混合、股票指数 |
| asset_class | unsupported_or_unknown | 暂未纳入第一版范围 | fund_type 不在第一版范围内 |
| management_style | active | 主动管理候选 | 名称和类型未命中指数/ETF/联接 |
| management_style | passive_index | 被动指数工具 | 类型或名称包含指数、ETF、联接、INDEX |
| calculation_eligibility | label_ready | 标签计算可用 | 数据覆盖 gate 通过 |
| calculation_eligibility | data_gap | 数据缺口 | 数据覆盖 gate 未通过 |
| style_clarity | style_clear | 风格已识别 | 已触发正式持仓风格标签 |
| style_clarity | style_pending | 风格待确认 | 股票因子存在，但未触发正式风格标签 |
| style_clarity | style_factor_missing | 缺少风格因子 | 没有股票因子，不能输出正式风格分组 |
| style_clarity | style_unknown | 风格未知 | 兜底状态 |

## 当前分组

| 分组代码 | 分组名 | 用途 |
|---|---|---|
| phase1_active_equity_scope | 第一版权益相关范围 | 说明基金进入当前项目第一阶段范围 |
| label_ready_pool | 标签可计算池 | 数据 gate 通过，可以输出正式基础标签 |
| data_gap_pool | 数据缺口池 | 数据不足，需要先补数据再比较 |
| active_equity_candidate_pool | 主动权益候选池 | 主动管理、数据充足、经理任期达标，且未触发规模偏小 |
| passive_tool_pool | 被动指数工具池 | 被动指数或 ETF 联接类工具，不和主动基金直接比 alpha |
| style_factor_ready_pool | 风格因子可用池 | 可以做风格相关分析 |
| style_factor_missing_pool | 风格因子缺失池 | 风格层不能正式计算 |
| deep_value_group | 深度价值组 | 触发深度价值标签 |
| quality_growth_group | 质量成长组 | 触发质量成长标签 |
| dividend_steady_group | 红利稳健组 | 触发红利稳健标签 |
| high_return_high_drawdown_watch | 高收益高回撤观察池 | 收益强但回撤也大，需要风险收益一起看 |
| industry_concentration_watch | 行业集中观察池 | 行业集中度高，需要看行业暴露风险 |

## 数据结构

分类结果落库到 `fund_classification_results`：

- `run_id`
- `fund_code`
- `dimension`
- `classification_code`
- `classification_name`
- `confidence`
- `reason_code`
- `evidence`
- `source`

分组结果落库到 `fund_group_results`：

- `run_id`
- `fund_code`
- `group_code`
- `group_name`
- `group_type`
- `reason_code`
- `evidence`
- `source`

每条分类和分组都必须带 `reason_code`、`evidence`、`source`，避免出现“分到了某个池子但不知道为什么”的情况。

## 当前边界

- 不覆盖债券、货币、QDII、FOF、REITs 的正式分类逻辑。
- `active_equity_candidate_pool` 只是候选池，不等于最终准入或推荐。
- 被动指数工具先单独成池，不和主动基金直接比较超额收益。
- 风格分组依赖股票因子；缺因子时只能进入 `style_factor_missing_pool`。
- 暂不引入人工复核流程作为前置条件，当前先把自动计算闭环做完整。
