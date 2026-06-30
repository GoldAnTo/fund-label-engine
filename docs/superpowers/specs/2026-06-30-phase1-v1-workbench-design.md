# Phase1 v1 可展示池工作台设计

> 状态：已获方向确认，进入规格固化。本文件只定义产品与工程边界，不改业务代码。
> 当前依据：`/tmp/fle-run/output.sqlite` 最新批次 `ecb548da7527488ebd955f0376f06b03`，
> 142 只 Phase1 v1 正式清单基金全部进入 `label_ready_pool`，其中 108 只
> `relative_label_ready`，34 只暂不可展示相对基准标签。

## 1. 产品结论

本项目已经越过“能不能跑”的阶段。下一步不是继续扩标签数量，而是把已有的标签、证据、
分类、基准质量门禁和复核动作收敛成一个可以日常使用的 Phase1 v1 工作台。

工作台第一版要回答三个问题：

1. 哪些基金可以正式展示给业务看。
2. 哪些基金暂时不能展示，以及被什么原因挡住。
3. 对被挡住或需要观察的基金，下一步应该补数据、补映射、复核阈值，还是保持观察。

## 2. 使用者与任务

### 2.1 产品池审核人员

他们不关心底层脚本细节，打开系统后首先要看到：

- 正式清单共有多少只基金。
- 可展示多少只，暂不可展示多少只。
- 暂不可展示的主要原因是什么。
- 单只基金为什么能展示或不能展示。

### 2.2 投研人员

他们需要看单只基金报告，但不能把所有信号都当成强结论。界面必须把结果分成：

- 正式结论：数据和门禁达标，可以进入 v1 展示。
- 观察信号：有业务价值，但还需要复核口径或更多样本。
- 待校准信号：技术上已算出，但不建议作为强结论。
- 阻断原因：数据源、基准源、映射或窗口不足导致无法展示。

### 2.3 数据和系统维护人员

他们需要把 blocked 池转成明确任务：

- 缺少基准收益源，补 `benchmark_component_returns`。
- 需要确认基准映射，补精确指数映射，不能宽指数代理。
- 基准组件未解析，改解析规则或明确不支持。
- 规则阈值发生覆盖，查看本批次实际 rule snapshot。

## 3. 方案选择

### 方案 A：继续补数据源为主

优点：最快提高可展示数量，和现有 P0 一致。
缺点：用户打开工作台时仍然不知道当前结果该怎么看，产品闭环不明显。

### 方案 B：先做完整复核系统

优点：长期更像正式业务系统。
缺点：权限、任务流、多人协作会把范围拉大；当前复核队列在 v1 批次里不再是主要瓶颈。

### 方案 C：先做 Phase1 v1 可展示池工作台（推荐）

优点：直接服务当前真实状态，把 142/108/34 的边界、原因和下一步处理动作展示清楚。
缺点：它不是完整业务平台，只是 v1 产品化收口。

选择方案 C。它覆盖当前最高价值问题，并为后续补基准源、阈值校准和复核系统留下入口。

## 4. 范围

### 4.1 本次 in scope

- 将默认首页调整为可展示池视角。
- 强化可展示池总览：正式清单、可展示、暂不可展示、主要阻塞项。
- 将 blocked 原因转成可处理任务，而不是只显示状态码。
- 单基金报告增加“展示资格”区域，明确该基金是否可以展示相对基准标签。
- 单基金报告把标签分成正式结论、观察信号、待校准信号、阻断原因。
- 批次详情突出分类/分组分布，并允许跳转到带筛选的基金检索。
- 复核队列升级为“待处理队列”，覆盖人工复核、基准缺口、观察标签和待校准信号。
- 显示本批次实际 rule snapshot 和命令行覆盖阈值，避免配置文件与实际运行口径混淆。
- 保留现有导出能力，但导出字段应能表达展示分层与阻断原因。

### 4.2 本次 out of scope

- 不新增基金推荐、买卖建议或自动准入决策。
- 不扩展到纯债、货币、QDII、FOF、商品基金、REITs。
- 不新增完整权限系统、审批流或多人任务分配。
- 不引入 LLM 自动下结论。
- 不把观察标签升级成正式标签。
- 不为了提高 ready 数量使用不精确的宽指数代理。
- 不在本次重构底层标签引擎的大量规则。

## 5. 关键术语

### 5.1 正式清单

Phase1 v1 的基金范围，由 `data/phase1_fund_codes_v1_official.txt` 控制。工作台应默认服务这份清单。

### 5.2 可展示

基金通过相对基准质量门禁，允许展示 Alpha、Beta、超额收益、信息比率等相对基准标签。
当前状态码为 `relative_label_ready`。

### 5.3 暂不可展示

基金本身可能已经可算基础标签，但相对基准标签不能正式展示。原因包括：

- `benchmark_source_missing`
- `benchmark_mapping_required`
- `benchmark_unresolved`
- `benchmark_missing`
- `nav_window_insufficient`

### 5.4 正式结论、观察信号、待校准信号

- 正式结论：数据依赖清楚，门禁达标，可进入 v1 展示。
- 观察信号：可展示给内部用户，但界面必须标明“观察”语义。
- 待校准信号：已有技术结果，但样本少或阈值仍需校准，不作为强结论。

## 6. 页面设计

### 6.1 默认首页：可展示池

现状默认进入批次列表。v1 应默认进入可展示池，因为这是业务用户最自然的入口。

首页信息结构：

1. 顶部指标：正式清单数、可展示数、暂不可展示数、最新批次时间。
2. 状态分布：可展示、缺收益源、需映射、未解析、未配置基准、收益窗口不足。
3. 主要阻塞项：按阻塞组件和影响基金数排序。
4. 基金列表：基金代码、名称、展示状态、基准源状态、净值/基准样本数、阻塞组件、查看报告。
5. 操作入口：仅看可展示、仅看暂不可展示、导出 blocked 清单。

验收口径：

- 最新批次下应能看到 142/108/34 的三项指标。
- blocked 列表应显示影响最多的组件，例如中债总、中国债券总、标普中国债券等。
- ready 基金点击后进入单基金报告，并能看到相对基准标签证据。

### 6.2 单基金报告

单基金报告需要从“全量技术明细”变成“先判断，再展开证据”。

顶部区域：

- 基金代码和名称。
- 展示资格：可展示 / 暂不可展示。
- 阻断原因摘要。
- 标签分层数量：正式结论、观察信号、待校准、阻断原因。
- 导出按钮。

中部区域：

- 展示资格证据：基准组件、组件状态、收益源状态、benchmark rows、NAV rows。
- 正式结论：基础数据、费用规模、经理、收益风险、相对基准等可正式展示标签。
- 观察信号：行业集中、持仓集中、权益仓位、风格稳定性观察。
- 待校准信号：深度价值、质量成长、红利稳健等当前样本仍少的高级风格标签。
- 未触发和未计算原因：保留现有 calculation states，但默认放在正式/观察/待校准之后。

底部区域：

- 因子暴露和特征值继续保留，作为调试和投研展开信息。
- 复核提交仍保留，但不作为第一屏主动作。

验收口径：

- ready 基金能解释为什么可展示。
- blocked 基金能解释为什么暂不可展示。
- 观察和待校准标签不会和正式结论混在同一张表里。

### 6.3 批次详情

批次详情仍服务工程和运营人员，重点不是替代首页，而是解释一次 run 的整体质量。

新增或强化：

- 分类分布：`asset_class`、`management_style`、`calculation_eligibility`、`style_clarity`。
- 分组分布：`label_ready_pool`、`active_equity_candidate_pool`、`passive_tool_pool`、风险观察池、风格池。
- 点击分布项跳转基金检索，并自动带入 filter。
- 规则快照区域增加“本批次实际规则”提示，突出命令行覆盖阈值。

### 6.4 待处理队列

复核队列升级为待处理队列。第一版不做权限和分派，只做清单化。

队列类型：

- 人工复核：`review_action = manual_review`。
- 基准缺口：relative label blocked 的基金。
- 映射确认：`benchmark_mapping_required`。
- 数据源缺口：`benchmark_source_missing`。
- 观察标签：行业集中、持仓集中、风格稳定性观察。
- 待校准标签：高级风格标签和风格待确认。

每条任务显示：

- 基金代码和名称。
- 任务类型。
- 原因或组件。
- 影响标签。
- 建议动作。
- 跳转单基金报告。

第一版只读即可；提交复核仍在单基金报告里完成。

### 6.5 基金检索

现有搜索能力保留，但要支持从首页、批次详情、待处理队列带参数跳入。

需要支持的筛选：

- label_code
- review_action
- group_code
- group_type
- classification_code
- relative_label_status
- benchmark_source_status

其中 `relative_label_status` 和 `benchmark_source_status` 可以先由前端调用相对基准 eligibility 接口实现，
不一定第一步就并入通用 search SQL。

## 7. 数据与 API

### 7.1 复用现有接口

- `/v1/runs`
- `/v1/runs/{run_id}`
- `/v1/runs/{run_id}/summary`
- `/v1/runs/{run_id}/style`
- `/v1/runs/{run_id}/search`
- `/v1/runs/{run_id}/review-queue`
- `/v1/runs/{run_id}/funds/{fund_code}/report`
- `/v1/runs/{run_id}/funds/{fund_code}/benchmark-components`
- `/v1/runs/{run_id}/relative-label-eligibility`

### 7.2 建议新增或扩展

第一步优先少改后端。若前端拼装过复杂，再新增聚合接口。

建议新增：

```text
GET /v1/runs/{run_id}/workbench-summary
```

返回：

- `run`
- `official_pool_count`
- `ready_count`
- `blocked_count`
- `status_counts`
- `blocker_groups`
- `classification_distribution`
- `group_distribution`
- `label_tiers`
- `rule_snapshot_highlights`

建议扩展单基金 report：

- `display_eligibility`
- `relative_label_status`
- `benchmark_source_status`
- `label_tiers`
- `blocking_reasons`

若为了控制范围，也可以先在前端通过现有接口拼装，等重复逻辑明显后再沉到后端。

## 8. 标签分层规则

第一版采用静态映射，后续再配置化。

### 8.1 正式结论

- `data_sufficient`
- `data_insufficient`
- `fee_low`
- `fee_high`
- `fund_size_small`
- `fund_size_moderate`
- `manager_tenure_long`
- `volatility_high`
- `volatility_low`
- `drawdown_high`
- `sharpe_high`
- `long_term_return_strong`
- `return_window_insufficient`
- 相对基准标签仅在 `relative_label_ready` 时进入正式结论。

### 8.2 观察信号

- `industry_concentration_high`
- `industry_concentration_observe`
- `industry_diversified`
- `holding_concentration_high`
- `equity_position_high`
- `style_stable`
- `style_drift`
- `style_recent_shift`
- `style_exposure_observe`
- `style_exposure_low_coverage`

### 8.3 待校准信号

- `deep_value`
- `quality_growth`
- `dividend_steady`
- `high_dividend_financial`
- `consumer_quality`
- `style_pending_rule_definition`
- `style_unlabeled_stock_factors_missing`
- `sector_mapping_insufficient`

### 8.4 阻断原因

来自 calculation states、benchmark components 和 relative eligibility：

- `benchmark_data_missing`
- `benchmark_source_missing`
- `benchmark_mapping_required`
- `benchmark_unresolved`
- `benchmark_missing`
- `nav_window_insufficient`
- `not_computed` 状态及其 `reason_code`

## 9. 工程边界

### 9.1 前端

可以先在现有 React/Vite 结构内迭代，不引入 UI 框架。

改动集中在：

- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/components.tsx`
- `frontend/src/pages/ReadyPoolPage.tsx`
- `frontend/src/pages/FundReportPage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`
- `frontend/src/pages/ReviewQueuePage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/styles.css`

注意事项：

- 当前前端已有未提交中文化改动，实施时必须在这些改动之上继续，不回滚。
- 页面文案面向业务用户，少显示英文状态码，状态码保留在次级信息中。
- 不做营销化页面，保持工作台式信息密度。

### 9.2 后端

第一步尽量复用现有 reader 和接口。只有在前端重复拼装明显时才新增聚合接口。

若新增接口，改动集中在：

- `backend/app/main.py`
- `backend/app/persistence/reader.py`
- `backend/tests/test_api.py`
- `backend/tests/test_api_v1.py`

### 9.3 数据

不新增核心 schema。工作台应消费已有结果表：

- `label_runs`
- `fund_label_results`
- `fund_label_evidence`
- `label_calculation_states`
- `fund_classification_results`
- `fund_group_results`
- `fund_run_coverage`
- `fund_factor_exposures`
- `benchmark_components`
- `benchmark_returns`

## 10. 验收标准

### 10.1 数据验收

- 最新 v1 批次能显示 142 只正式清单基金。
- ready 数显示 108。
- blocked 数显示 34。
- blocked 状态分布与 `relative-label-eligibility` 审计一致。
- 单基金报告中，ready 基金和 blocked 基金的展示资格判断一致。

### 10.2 产品验收

- 用户打开首页，不需要懂脚本，也能知道当前 v1 能展示多少、不能展示多少、先处理什么。
- 用户打开单基金报告，能先看到结论分层，再看证据明细。
- 观察信号和待校准信号不会被误读为正式结论。
- 待处理队列能把 blocked 原因转成行动建议。

### 10.3 工程验收

- 后端测试通过。
- 前端 `npm run build` 通过。
- 若新增接口，必须有 API 测试覆盖。
- 不破坏现有导出、批次对比、基金检索、复核提交能力。

## 11. 实施顺序

1. 固化标签分层和展示资格模型。
2. 调整首页为可展示池，并补齐 blocked 任务视角。
3. 改造单基金报告，让结论分层先于技术明细。
4. 强化批次详情的分类/分组分布和跳转筛选。
5. 将复核队列升级为待处理队列。
6. 视前端拼装复杂度决定是否新增 `workbench-summary` 接口。
7. 跑后端测试和前端构建，输出验收说明。

## 12. 非目标提醒

这次不是做“基金好不好”的最终判断系统。它只负责把机器已经算出的标签分层展示，
把能展示和不能展示的边界讲清楚，把下一步数据和规则工作排清楚。

