# 阶段 0 交付物索引

> 适用文档: [`../private-fund-investment-research-system-plan.md`](../private-fund-investment-research-system-plan.md)
>
> 阶段 0 目标:**不写新业务代码**,只交付"业务边界、领域语言、策略样例、快照架构、最短演示和验收标准"六件套,为阶段 1 立项提供唯一依据。
>
> 主业务:**私募内部投研与组合决策**；FOF / 母基金(外部基金筛选)作为可配置扩展模式。
>
> 阶段 0 出口: [`phase0-acceptance.md`](./phase0-acceptance.md) 中"是否进入阶段 1"的明文决策。
>
> 当前版本:**v0.3**(私募内部投研主线),基于 v0.2 重写。

---

## 1. v0.1 → v0.2 关键变更

| 文件 | 变更 | 原因 |
|---|---|---|
| `business-scope.md` | 从单一 FOF 用户入口改为"**私募内部研究请求**为主、FOF 可选"的 A/B/C 场景 | 不能在未确认业务模式前把系统锁死为外部基金筛选 |
| `domain-language-v0.md` | 保留 `UserInput` 技术实体,业务语义改称 `ResearchInput` 并增加发起人、策略和请求上下文 | 内部投研人员不是外部客户,必须能追踪谁在什么业务上下文发起研究 |
| `roles.md` | 将"用户"从外部角色改为统一的请求发起人,明确研究员、投资经理、风控和产品运营边界 | 私募系统的主要使用者是内部角色,不是大众用户 |
| `strategy_policy/private_equity_growth_v0.yaml` | 新增自有权益策略样例,保留 FOF 样例作为扩展模式 | P0 必须有符合私募主业务的策略政策样例 |
| `snapshot-architecture.md` | 明确现有 SQLite `data_snapshots`、run 和 manifest 的最小方案 | 不在 P0 过早锁定 DVC、MLflow、Feast |
| `phase0-acceptance.md` | 新增阶段 0 验收和是否进入阶段 1 的明文决策 | README 中引用的验收文件此前不存在 |
| `README.md` | 增加变更日志 | 跟踪迭代 |

---

## 2. 文件清单与责任人

| # | 文件 | 用途 | 主笔 | 评审 |
|---|---|---|---|---|
| 1 | [`business-scope.md`](./business-scope.md) | **用户视角 3 场景 A/B/C** + 系统响应链路 | 投研负责人 | 投决会 |
| 2 | [`roles.md`](./roles.md) | 6 角色(用户 + 5 内部)输入输出与权限 | PM | 各角色代表 |
| 3 | [`domain-language-v0.md`](./domain-language-v0.md) | **6 实体**字段/状态机/不可变约束(含 UserInput) | 架构师 | 全员 |
| 4 | [`snapshot-architecture.md`](./snapshot-architecture.md) | SQLite 快照、run、manifest 和未来外部工具的边界 | 架构师 | 后端 Lead |
| 5 | [`phase0-acceptance.md`](./phase0-acceptance.md) | 阶段 0 验收与立项决策 | PM | 管理层 |

> 注:`snapshot-architecture.md` 是阶段 0 第 2 周产出,本目录初版不强制在第 1 周填完。

## 3. 配套文件(非 docs/p0/ 内)

| 路径 | 用途 |
|---|---|
| [`../../config/strategy_policy/private_equity_growth_v0.yaml`](../../config/strategy_policy/private_equity_growth_v0.yaml) | 主业务 Strategy Policy 样例(自有权益策略) |
| [`../../config/strategy_policy/foof_growth_v0.yaml`](../../config/strategy_policy/foof_growth_v0.yaml) | FOF 扩展模式样例,不作为默认主业务 |
| `../../scripts/p0/smoke_e2e_private_fund.py` | 计划新增的私募内部投研最短演示脚本 |
| `../../reports/p0/smoke-e2e-report.md` | 计划由演示脚本生成的报告,阶段 0 未完成前不得伪造 |

## 4. 写作大纲(每份文档必答 3 问)

每份文档必须明确回答:

1. **它解决什么问题?**(Why)
2. **谁会读它、读完会做什么决定?**(Who / So what)
3. **它的不可变承诺是什么?**(冻结哪些字段 / 哪些决策 / 哪些状态)

未回答这 3 问的文档视为未完成。

## 5. 阶段 0 反模式(强制避坑)

- ❌ 新建第二个标签系统(扩 `label_engine`)。
- ❌ 为演示塞假数据(用现有 `seed_sample_db.py`)。
- ❌ 把 DVC 用来存整个数据库。
- ❌ 把 MLflow 当数据库。
- ❌ 在策略政策 YAML 里加表达式或脚本。
- ❌ 承诺阶段 1 一定能成功。
- ❌ **🆕 系统在没有用户输入的情况下主动生成候选**。
- ❌ **🆕 用户原话(`raw_text`)丢失或不落库**。
- ❌ **🆕 候选清单反查不到 `user_input_id`**。

## 6. 阶段 0 → 阶段 1 的衔接(已更新)

进入阶段 1 后,需要预先明确:

- **建表对象**:`user_input`、`investment_thesis`、`candidate_set`、`decision_record` 最小版(`strategy_policy` 先保留 YAML,但必须绑定 `policy_id + version`)
- **新建 1 个 migration**:`0015_governance_core.sql`
- **新建 1 个 backend 包**:`backend/app/governance/`
- **新建前端页**:`/inputs`(研究请求入口)+ `/inputs/:id`(研究响应与候选页)
- **阶段 1 建** `decision_record` 最小版,只记录 pending / approved / rejected / watching,完整投决会工作流留到阶段 3
- **不建** 多产品组合聚合(留到阶段 2)
- **关键改动**:阶段 1 第一个 PR 必须是"ResearchInput 落库 + 复现输入 + 最小决策记录",否则候选结果仍然无法进入私募投研流程。

## 7. v0.3 强制边界

1. 阶段 0 默认演示自有权益策略，不默认演示 FOF。
2. A/B/C 三个场景仍保留，但候选对象可以是股票、行业、基金、管理人、策略或产品。
3. 用户输入在业务层称为 `ResearchInput`，技术字段暂保留 `user_input_id`，以降低后续迁移成本。
4. “至少返回 3 只基金”不再是验收条件。合格候选数量可以为 0，但必须给出数据状态、排除原因和下一步动作。
5. 阶段 0 允许使用结构化样例输入，不承诺完整自然语言解析；原始文本必须完整保留。
6. 阶段 1 进入候选之后必须留下最小决策记录，不能把所有决策能力推迟到阶段 3。
