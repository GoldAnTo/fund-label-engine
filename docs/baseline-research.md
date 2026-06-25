# GitHub 基准项目借鉴说明

## 主基准：fund-analysis-agent

仓库：[nai-he/fund-analysis-agent](https://github.com/nai-he/fund-analysis-agent)

检查快照：2026-06-23，本地只做借鉴评估，不做整仓迁入。

借鉴点：

- FastAPI + React 的全栈结构。
- 风险评分、回测、AI 分析分层。
- 将“数据采集、风险评分、分析输出、前端展示”拆成独立模块。
- 数据源 fallback、风险指标和前端分析页面的组织方式。

本项目不复制其代码，原因：

- 本项目的重点是标签规则、证据链、复核边界，而不是通用基金分析展示。
- 外部项目的实现可能包含与本项目无关的数据抓取、LLM 分析和 UI 逻辑。
- 它更像个人基金分析/决策助手，核心输出偏实时分析、预测和买卖参考；本项目需要的是批量标签、规则版本、审计落库和人工复核。
- 直接复用会把推荐/预测口径带进资管标签系统，容易冲淡“证据可追溯”和“缺数据不下结论”的边界。
- 只保留工程分层思想，避免一开始引入过多不稳定依赖。

适合后续拆借的模块方向：

- 基金指标计算：收益、波动、回撤、风险评分。
- 数据源 fallback：多数据源失败降级思路。
- 前端页面：基金详情、指标卡片、图表布局。

不建议复用的方向：

- 买卖建议和预测类输出。
- LLM 自动总结作为最终标签结论。
- 与本项目数据契约不一致的临时抓取逻辑。

## 辅助参考：xalpha

仓库：[refraction-ray/xalpha](https://github.com/refraction-ray/xalpha)

借鉴点：

- 基金投资管理。
- 基金组合模拟。
- 底层股票持仓和行业分布透视。

适合用于后续持仓穿透和 FOF 组合分析，不作为第一版代码基底。

## 辅助参考：FactorHub

仓库：[cn-vhql/FactorHub](https://github.com/cn-vhql/FactorHub)

借鉴点：

- 因子管理。
- 因子分析和回测。
- 因子生命周期治理。

适合后续建设 `stock_factors` 和股票标签层。

## 辅助参考：OpenBB

仓库：[OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)

借鉴点：

- 一次接入数据，多端消费。
- 面向分析师、量化和 AI agent 的数据平台思路。

适合后续把本项目接到 API、MCP、Notebook、前端工作台。
