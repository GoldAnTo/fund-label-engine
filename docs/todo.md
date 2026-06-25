# 后续 Todo

## 已完成主线

- 已完成：接入真实基金数据源，支持本地 `fundData` SQLite schema。
- 已完成：批量生成 `label_runs`、标签、证据、覆盖率、计算状态、分类、分组和基金级因子暴露。
- 已完成：`label_calculation_states` 能解释 `triggered` / `not_triggered` / `not_computed`。
- 已完成：分类和业务分组层，覆盖主动权益候选池、被动指数工具池、数据缺口池、风格相关分组。
- 已完成：基金级因子暴露聚合，label engine 优先消费 `fund_factor_exposures`，旧股票因子路径保留 fallback。
- 已完成：风格暴露 coverage gate：`<50%` 低覆盖、`50%-70%` 观察、`>=70%` 才允许正式风格标签。
- 已完成：相对基准 v2 解析和 `benchmark_components` 审计表。
- 已完成：API、导出、复核队列、run diff、搜索页、单基金报告页和前端构建。
- 已完成：CI 覆盖 pytest、前端 build、样例 DB smoke 和关键 API smoke。
- 已完成：规则配置可从 `config/rules.v1.json` 加载，并随 run snapshot 落库。

## P0：当前最优先

- 继续补：把稳定债券指数、行业/主题指数、港股指数日收益先写入 `benchmark_component_returns`，再运行 `scripts/fetch_benchmark_returns.py`，提高 `benchmark_returns` 覆盖。
- 继续补：基于 `benchmark_components` 输出 unresolved component 榜单，优先处理 `中债综合`、`中债总`、`中国债券总` 等高频缺口。
- 继续补：固定 5-10 只真实基金，输出“标签、证据、计算状态、分类、分组、基准组件、风格稳定性”的验收报告。
- 继续补：对 `data_gap_pool` 基金做缺口归因，决定补 NAV、补持仓穿透，还是从第一版正式清单剔除。

## P1：工作台增强

- 已完成：按标签、复核动作、业务池、分组类型、分类筛选基金。
- 继续补：把 run summary 的分类/分组分布做成可点击入口，点击后自动带入搜索筛选。
- 继续补：在单基金报告页突出展示基准组件解析结果和 unresolved reason。
- 继续补：在风格区域展示多期 `style_stable` / `style_drift` / `style_recent_shift` 证据。

## P2：标签质量校准

- 已完成：`industry_concentration_high` 调整为 60% 正式、45%-60% 观察。
- 已完成：`fee_low` 收紧到 1.2%。
- 继续补：收益风险标签优先用相对基准替代纯绝对收益口径。
- 继续补：按主动/指数、A/C 份额、基金类型分层校准费率标签。
- 继续补：风格稳定性先作为观察标签使用，等待更多报告期样本后再进入正式展示口径。

## P3：工程化和审计

- 继续补：规则启停机制，禁用标签不参与计算但历史结果可查。
- 继续补：规则回放，指定历史 run、规则版本和数据日期重算。
- 继续补：数据质量报告，覆盖缺失字段、异常值、过期数据、报告期错配。
- 继续补：迁移机制继续轻量化；只有 schema 演进明显增多时再引入 Alembic。

## 暂缓事项

- 暂缓 LLM 自动分析结论。
- 暂缓完整组合优化、FOF 配置和交易回测。
- 暂缓复杂权限系统。
- 暂缓直接复用外部仓库业务代码。
