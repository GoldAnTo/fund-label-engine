# 阶段 0 · 数据快照与复现架构 v0.3

## 1. 目标

阶段 0 要证明：同一个研究请求，在相同的研究输入、策略政策和数据快照下，可以复现同一份候选结果和排除原因。

快照不等于把整个数据库复制一份，也不等于把所有文件交给 DVC、MLflow 或 Feast 管理。当前项目优先使用已经存在的 SQLite data_snapshots、run 记录和报告产物建立最小复现链。

## 2. 最小复现键

每份研究结果必须绑定：

- research_input_id
- strategy_policy_id + strategy_policy_version
- data_snapshot_id
- run_id
- engine_version
- rule_version

缺少任一关键键时，结果只能作为临时研究输出，不得标记为可复核的正式候选。

## 3. DataSnapshot 最小内容

字段要求：

- data_snapshot_id：全局唯一。
- created_at：快照创建时间。
- as_of_date：数据截至日期。
- source_db_path：主数据源位置。
- factor_db_path：因子数据源位置。
- source_manifest：数据源名称、版本、抓取时间、记录数和校验信息。
- coverage：基金、净值、持仓和因子覆盖率。
- quality_status：sufficient / partial / insufficient。

## 4. 快照边界

### 阶段 0 必须做

- 复用现有 data_snapshots 表。
- 记录数据截至日期和抓取日期。
- 记录使用的 source DB、factor DB 和 run。
- 记录策略政策版本。
- 生成报告时输出快照摘要。
- 任何候选都可以反查到快照。

### 阶段 0 不做

- 不把整个 SQLite 数据库提交到 Git。
- 不把 DVC 当作数据库。
- 不把 MLflow 当作业务数据库。
- 不在没有实际需求时引入 Feast。
- 不在 P0 锁定供应商或云平台。

## 5. 工具边界

| 工具 | 当前阶段判断 | 未来可能用途 |
|---|---|---|
| SQLite | 直接使用 | 本地研究、测试和小规模工作台 |
| Git | 版本化代码、规则文档和策略样例 | 保持 |
| DVC | P0 不引入 | 大型原始数据集版本管理 |
| MLflow | P0 不引入 | 量化实验和模型注册 |
| Feast | P0 不引入 | 大规模在线特征服务 |
| 对象存储 | P0 不引入 | 生产快照和报告归档 |

## 6. 复现流程

研究请求先锁定 StrategyPolicy 版本，再锁定 DataSnapshot，运行指定 engine 和 rule 版本，生成 CandidateSet，保存证据、排除原因和报告，最后输出复现元数据。

复现失败时必须明确失败层级：

- 输入不存在。
- 策略政策版本不存在。
- 数据快照不存在。
- 数据源文件发生变化。
- 引擎版本不匹配。
- 规则版本不匹配。
- 上游数据不足。

## 7. 阶段 1 迁移要求

阶段 1 的 0015_governance_core.sql 必须让 user_input、investment_thesis、candidate_set 和最小 decision_record 引用 data_snapshot_id 与策略政策版本。

完整的原始数据库归档、数据供应商 SLA、跨环境对象存储和数据权限属于企业化阶段。
