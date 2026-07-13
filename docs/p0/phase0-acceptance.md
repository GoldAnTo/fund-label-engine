# 阶段 0 · 验收与立项决策 v0.5

> 文档状态:v0.5
> 变更说明:完成 P0 fix batch(6 个 P0 子任务),把"演示可跑"升级为"演示 + 治理核心表 + 政策同步 + 17 个正式测试 + 零破坏回归"。

## 1. 验收目标

阶段 0 不验证投资收益,也不证明系统已经可以自动推荐基金。阶段 0 只验证:

1. 业务模式边界是否明确。
2. 研究请求、策略政策、投资假设和候选集合是否有共同语言。
3. 研究结果是否有证据、数据快照和排除原因。
4. 无候选时是否可以诚实结束。
5. 治理核心表是否能在空库完整初始化并被应用实际使用。
6. 阶段 1 是否有明确、可控的开发入口。

## 2. 业务模式验收

- [x] 默认模式已确认:**`private_strategy`**
- [x] FOF 模式已标记为扩展样例(`foof_growth_v0.yaml: business_mode=fof, approved_for_production=false`)
- [x] 策略样例有 `business_mode`、`policy_id`、`version` 和 `policy_status`
- [x] 样例政策没有被描述成正式公司制度(两份 YAML 都标注了 `policy_status: example`)

## 3. 三个研究请求验收

### A:投资观点
- [x] 输入一条原始研究观点
- [x] 输入保存 `actor_role`、`strategy_policy_id` 和 `data_snapshot_id`
- [x] 系统生成投资假设
- [x] 系统返回有证据的候选
- [x] 候选状态为 `candidates`(不强制固定数量)

### B:行业或方向
- [x] 输入一个行业
- [x] 系统展示行业的真实暴露
- [x] 每个暴露带报告期和数据质量
- [x] 系统区分政策排除(暴露 < 10% 视为政策阈值排除)

### C:具体标的
- [x] 输入具体股票
- [x] 系统返回持仓分析
- [x] 系统输出报告期和持仓权重
- [x] 不强制返回固定数量候选

## 4. 复现验收

每个演示结果都能找到:

- [x] `research_input_id`(每个场景独立 ID)
- [x] `thesis` 标题、belief_statement、time_horizon
- [x] `candidate_status`(candidates 或 no_eligible_candidate)
- [x] `strategy_policy_id + version`(`private_equity_growth v1`)
- [x] `data_snapshot_id`(写入 `data_snapshots` 表)
- [x] `as_of_date`

第三方根据 `reports/p0/smoke-e2e-report.md` 中的任意一个 `research_input_id`:
1. 跑 `python scripts/sync_strategy_policies.py <db>` 复现策略
2. 读 `data_snapshots` 表复现数据快照
3. 重跑 `python scripts/p0/smoke_e2e_private_fund.py` 复现候选结果

**复现时间估计**: < 5 分钟(脚本不依赖外部服务,只依赖 seed + migration)。

## 5. 反模式验收

- [x] 系统无研究请求不会主动生成候选(脚本仅在收到输入后生成)
- [x] 原始输入完整保存(每个场景都包含 `raw_text`)
- [x] 候选可反查输入、策略和快照(**报告字段层面**:报告里每个候选都展示 5 个 ID;**数据库真实反查留到阶段 1 GovernanceRepository 完成后**)
- [x] 未用固定数量作为候选成功条件
- [x] 数据未过期(as_of_date=2026-03-31,报告期与数据匹配)
- [x] 样例政策阈值未当成正式投资制度(`policy_status: example`)
- [x] 未通过新增标签绕过现有标签引擎(直接用 `fund_stock_holdings` / `fund_industry_allocations`)
- [x] 演示脚本使用 `seed_sample_db.py` 真实样例数据
- [x] **🆕 smoke 脚本不偷偷建表**: `_save_data_snapshot_id` 在表不存在时明确失败;由 `_ensure_source_db` 先 seed 再 migration 补表
- [x] **🆕 raw_text 绝对不可变**: trigger 在 `received` 状态就拦住(修正 P0.1 问题)

## 6. 治理核心表验收(P0 fix batch)

### 6.1 migration bootstrap

- [x] 空库可以完整初始化(`run_migrations` 跑 0000~0015 共 17 个文件)
- [x] 重复执行幂等(再次跑返回空集)
- [x] baseline 表(从 `LabelRunWriter.SCHEMA_STATEMENTS` 迁出)全部存在
- [x] governance 表(5 张)全部存在
- [x] `_split_statements` 正确处理 trigger body(不被 `;` 切坏)

### 6.2 trigger 真实性

- [x] `raw_text` 任何状态都不可改(已在 `received` 状态拦)
- [x] thesis 核心字段(`belief_statement` / `as_of_date` / `data_snapshot_id`)在 `validated` 之后不可改
- [x] `decision_records` 整行不可 UPDATE
- [x] `decision_records` 整行不可 DELETE
- [x] 同一 `policy_id` 只能有 1 个 `active` 状态

### 6.3 策略政策同步

- [x] `scripts/sync_strategy_policies.py` 从空库自动跑 migration + 同步 2 份 YAML
- [x] 嵌套对象(`position_limit` / `monitoring_policy` 等)以 JSON 字符串存到 `*_json` 列
- [x] 同步幂等(已存在的 policy 不会覆盖)
- [x] `foof_growth` 仍标记为 `policy_status: example`

### 6.4 正式测试

- [x] `backend/tests/test_governance_migrations.py` 17 个测试全部通过
- [x] `backend/tests/test_governance_repository.py` 20 个测试全部通过
- [x] `backend/tests/test_governance_service.py` 26 个测试全部通过
- [x] `backend/tests/test_api_governance.py` 13 个测试全部通过
- [x] `backend/tests/test_smoke_persist.py` 7 个测试全部通过(首次运行/重复运行/报告反查)
- [x] 全量后端测试 539 passed / 2 skipped / 0 failed(零破坏)

## 7. 进入阶段 1 的决策

### 通过条件

业务模式、领域语言、快照架构、三类研究请求、治理核心表、API 和持久化 smoke 全部通过,
且无候选状态可解释。

### 决策结果

- [x] **通过**: 进入阶段 1
- 阶段 1 已完成:
  1. ~~`GovernanceRepository`~~(纯 SQL,事务上下文,参数绑定,row->dict)
  2. ~~`GovernanceService`~~(状态机、不可变检查、policy/snapshot 存在性、audit_log 同事务)
  3. ~~`POST /v1/governance/research-inputs` API~~(含异常映射 404/409/422)
  4. ~~`GET /v1/governance/research-inputs/{input_id}` API~~
  5. ~~`GET /v1/governance/candidate-sets/{candidate_set_id}` API~~(含完整反查链路)
  6. ~~smoke 脚本 `--persist` 选项~~(通过 GovernanceService 落库,API 反查验证,重跑零重复)

### 已知遗留(不影响阶段 0 通过,但要在阶段 1 解决)

- **数据规模有限**: 当前 `seed_sample_db.py` 只有 1 只有效股票型基金
- **场景 A 关键词是硬编码**: 阶段 1 接入 cognition 主题映射
- **`CognitionEngine.run_stock_cognition` 依赖生产表**: smoke 改用直接读 `fund_stock_holdings`;阶段 1 评估
- **FOF YAML 同步时 `policy_status=example`**: 应用层在 UI 切换 `active`

### 阶段 1 完成后置

- 完整投决会(多人审批)
- 多产品组合聚合
- 客户适当性
- 自动交易
- DVC / MLflow / Feast 接入(目前在 `snapshot-architecture.md` 中描述为设计,未实施)

## 8. 阶段 0 演示产物索引

| 产物 | 路径 | 用途 |
|---|---|---|
| 演示脚本 | `scripts/p0/smoke_e2e_private_fund.py` | 跑通 3 个场景(内存版,无 --persist) |
| 演示报告 | `reports/p0/smoke-e2e-report.md` | 真实候选 + 证据 + 排除原因 |
| 样例数据 | `seed_sample_db.py` → `/tmp/fle-p0/source.sqlite` | 真实数据底座 |
| 主业务策略 | `config/strategy_policy/private_equity_growth_v0.yaml` | 阶段 0 默认策略 |
| FOF 扩展策略 | `config/strategy_policy/foof_growth_v0.yaml` | 扩展模式样例 |
| 同步脚本 | `scripts/sync_strategy_policies.py` | YAML → strategy_policies(幂等) |
| 治理核心表 migration | `backend/app/persistence/migrations/0015_governance_core.sql` | 5 表 + 2 视图 + 4 trigger |
| Baseline migration | `backend/app/persistence/migrations/0000_baseline_schema.sql` | 把 SCHEMA_STATEMENTS 提到 migration 层 |
| 正式治理测试 | `backend/tests/test_governance_migrations.py` | 17 个测试 |
| 领域语言 | `docs/p0/domain-language-v0.md` | 6 实体字段/状态机 |
| 业务场景 | `docs/p0/business-scope.md` | 3 个研究请求链路 |
| 角色说明 | `docs/p0/roles.md` | 5 内部角色边界 |
| 快照架构 | `docs/p0/snapshot-architecture.md` | DVC + MLflow + Feast 设计 |
| 实施计划 | `docs/superpowers/plans/2026-07-10-private-fund-p0-realignment.md` | 阶段 0~5 路线图 |

## 9. P0 fix batch 变更日志(相对 v0.4)

| 任务 | 修复内容 | 验证 |
|---|---|---|
| P0.1 | `raw_text` trigger 改为绝对不可变(去掉 `WHEN OLD.status NOT IN ('received')`);`_save_data_snapshot_id` 不再 `CREATE TABLE IF NOT EXISTS` | `test_raw_text_immutable_even_in_received` 通过 |
| P0.2 | 新建 `0000_baseline_schema.sql`,从 `LabelRunWriter.SCHEMA_STATEMENTS` 提取 baseline;`_split_statements` 支持 trigger body | `test_empty_db_can_run_all_migrations` 通过(17 个 migration) |
| P0.3 | 写 `scripts/sync_strategy_policies.py`(用 PyYAML 解析),YAML → `strategy_policies` 表 | `test_sync_yaml_creates_db` / `test_json_columns_stored_as_json` 通过 |
| P0.4 | 写 `backend/tests/test_governance_migrations.py`(17 个测试) | 17 passed |
| P0.5 | smoke 改为 seed → migration 顺序;跑全量后端测试 | 473 passed / 2 skipped / 0 failed |
| P0.6 | 更新 `phase0-acceptance.md` 验收标准(本文件) | — |

## 10. 签发

- 投研负责人:_____________  日期:_____________
- 风险负责人:_____________  日期:_____________
- 产品/运营:_____________    日期:_____________

---

## 阶段 1：基金候选优先级 v0

### 实现内容摘要

阶段 1 在阶段 0 治理核心表的基础上，实现了基金候选优先级 v0 的完整链路：

1. **CandidatePriorityEngine**（纯规则引擎）：执行策略硬门禁、数据可信度门禁、估值软门禁和五档分组（research_now / research_next / valuation_watch / data_insufficient / excluded），生成稳定原因码和档内排序。
2. **HoldingSourceAdapter**（持仓适配器）：统一 stock_holdings 和 fund_stock_holdings 两种持仓表结构，提供报告期查询和持仓加载。
3. **CognitionEngine.build_fund_candidate_evidence()**：构建完整基金候选证据（不截断），返回 FundCandidateEvidenceBatch，供治理链路使用。
4. **0016 migration**：新增 candidate_set_headers 表、candidate_priority_runs / candidate_priority_results 表、candidate_priority_json 列，PriorityResult 整行不可变。
5. **GovernanceRepository**：CandidateSet 头表持久化、幂等键检查、候选冻结证据存储。
6. **CandidatePriorityRepository**：PriorityRun / PriorityResult 持久化、幂等键查询、按 thesis 历史查询。
7. **CognitionGovernanceService**：编排服务，从投资假设生成 CandidateSet（调用 CognitionEngine），编排 PriorityRun（调用 CandidatePriorityEngine），原子写入 run + results + audit。
8. **四个治理 API 路由**：
   - POST /v1/governance/theses/{thesis_id}/candidate-sets
   - POST /v1/governance/theses/{thesis_id}/candidate-priority-runs
   - GET /v1/governance/candidate-priority-runs/{priority_run_id}
   - GET /v1/governance/theses/{thesis_id}/candidate-priority-runs

### 端到端 smoke 测试

测试文件：`backend/tests/test_smoke_candidate_priority.py`

测试使用真实认知数据库（`_make_cognition_db`），不使用 Mock，验证完整链路：
ResearchInput -> Thesis -> Cognition evidence -> CandidateSet -> CandidatePriorityRun -> CandidatePriorityResult -> API reverse lookup

覆盖场景：
1. 完整链路首次运行（含五档分组验证）
2. 同参数重复运行不创建新记录（DuplicateCandidateSetError / DuplicatePriorityRunError）
3. 新快照生成新 PriorityRun，旧结果保留
4. API 反查全链 ID（GET 详情 + GET 历史评价）

运行命令：

```bash
.venv/bin/python -m pytest backend/tests/test_smoke_candidate_priority.py -q
```

lint 命令：

```bash
.venv/bin/python -m ruff check backend/tests/test_smoke_candidate_priority.py
```

### 实际测试结果

- smoke 端到端测试：4 passed
- ruff lint：All checks passed
