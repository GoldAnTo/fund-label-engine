# MVP 路线图

## Phase 0: 项目启动

- 建立项目目录。
- 写清楚需求、边界、基准项目和数据契约。
- 起最小 Python 包和测试。
- 实现单只基金标签计算闭环。

## Phase 1: 本地规则引擎

- 支持结构化 `FundInput`。
- 支持覆盖率检查。
- 支持基础特征计算。
- 支持第一批标签。
- 输出标签证据。

## Phase 2: 数据接入

- 接入 `fundData` 本地 SQLite 或导出的 JSON。
- 支持批量读取基金样本。
- 记录 `label_runs`。
- 保存 `fund_label_results` 和 `fund_label_evidence`。

## Phase 3: API 服务

- FastAPI 暴露 `/health`。
- FastAPI 暴露 `/v1/funds/{fund_code}/labels`。
- FastAPI 暴露 `/v1/runs`。
- 支持按批次查询结果。

## Phase 4: 工作台

- 展示基金标签。
- 展示证据链。
- 支持人工确认、驳回、观察。
- 支持导出审核报告。

## Phase 5: 股票因子和高级风格

- 建立 `stock_factors`。
- 做持仓穿透。
- 计算价值、成长、红利、质量、行业主题暴露。
- 评估风格稳定性和风格漂移。

