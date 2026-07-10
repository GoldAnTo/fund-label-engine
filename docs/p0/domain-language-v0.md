# 阶段 0 · 核心领域语言 v0(初稿 v0.3)

> 文档状态:阶段 0 初稿 v0.3
> 变更说明:v0.2 把内部研究人员写成了外部用户。v0.3 保留 `UserInput` 技术实体,业务语义统一为 `ResearchInput`,并增加业务模式、策略政策和请求上下文。
> 必答 3 问:
> 1. 解决什么问题 → 团队没有共同的"研究请求 / 研究 / 策略 / 候选 / 决策"语言,导致沟通歧义。
> 2. 谁会读、做什么决定 → 架构师据此建表,后端据此写代码,投研据此提研究请求和决策。
> 3. 不可变承诺 → **冻结 6 个核心实体的字段命名、状态机、不可变约束**;阶段 1 建表必须 1:1 对齐。
>
> 对照参考: [`../private-fund-investment-research-system-plan.md`](../private-fund-investment-research-system-plan.md) 第 5 章 + [`./business-scope.md`](./business-scope.md) 第 2 章。

---

## 1. 6 个核心实体总览(新增 UserInput)

| # | 实体 | 阶段 0 状态 | 阶段 1 落点 |
|---|---|---|---|
| 0 | **UserInput**(业务名 ResearchInput) | 字段冻结,演示用 | `0015_governance_core.sql` |
| 1 | StrategyPolicy | 字段冻结,1 份 YAML 样例 | 同上 |
| 2 | InvestmentThesis | 字段冻结,脚本演示 | 同上 |
| 3 | CandidateSet | 字段冻结,脚本演示 | 同上 |
| 4 | DecisionRecord | 字段冻结 | 阶段 1 建最小版,阶段 3 扩展完整投决 |
| 5 | MonitoringEvent | 字段冻结 | **阶段 1 起建表** |

> **关键关系链**:`UserInput → InvestmentThesis → CandidateSet → DecisionRecord`,数据快照 `DataSnapshot` 横切所有实体。

> 阶段 0 **不建任何新表**。本文件只是"语言契约"。

---

## 2. 实体 0:UserInput(业务名 ResearchInput)🆕

> 这是研究请求的技术入口。它不是外部客户账户,而是研究员、投资经理、风控或产品运营发起的一次可追溯研究请求。

### 2.1 必填字段(冻结)

```yaml
user_input_id: string             # 全局唯一
input_type: enum                  # philosophy | industry | target | manager | strategy
raw_text: string                  # 用户的原始输入
business_mode: enum               # private_strategy | fof
strategy_policy_id: string        # 引用 StrategyPolicy.policy_id
strategy_policy_version: int      # 冻结本次请求使用的政策版本
actor_role: enum                  # researcher | portfolio_manager | risk | product
request_source: enum              # research_meeting | ad_hoc_research | portfolio_review | risk_review
structured_intent: object         # 解析后的结构化意图,见 2.3
target_assets: object[]           # 场景 C/D 时的具体标的
  - asset_type: stock | fund | manager | strategy | product
    asset_code: string
    asset_name: string
implicit_intent: enum             # 场景 C 时的隐含意图
  # copy      复制持仓
  # alternative 找替代
  # hedge     找对冲
  # correlate 找相关
session_id: string                # 跨场景追问的会话
as_of_date: date
data_snapshot_id: string
created_at: timestamp
```

### 2.2 与场景的对应

| `input_type` | 对应业务场景 | 必填 |
|---|---|---|
| `philosophy` | 场景 A 投资理念 | ✅ 阶段 0 必做 |
| `industry` | 场景 B 看好的行业 | ✅ 阶段 0 必做 |
| `target` | 场景 C 知道要投什么 | ✅ 阶段 0 必做 |
| `manager` | 场景 D 看好的管理人(FOF 特有) | ⚠️ 阶段 0 候选 |

### 2.3 `structured_intent` 子结构(场景 A 用)

```yaml
style_preference: string[]        # value / growth / quality / dividend / momentum
industry_preference:
  positive: string[]              # 偏好行业
  negative: string[]              # 反向行业
risk_preference:
  drawdown_tolerance: decimal     # 0~1
  volatility_tolerance: decimal   # 0~1
holding_preference:
  concentration: enum             # concentrated | balanced | diversified
  turnover: enum                  # low | medium | high
esg_floor: enum                   # 最低 ESG 评级要求
```

### 2.4 状态机

```text
received → parsed → expanded → closed
                ↘ failed(解析失败)
```

- `received`:用户输入已落库。
- `parsed`:已解析为结构化意图。
- `expanded`:已生成 InvestmentThesis(可能 1 个输入 → 多个 Thesis)。
- `closed`:用户已结束追问。
- `failed`:解析失败,记录原因。

### 2.5 不可变约束

- `raw_text` 不可修改(用于复盘"用户当时是怎么说的")。
- `structured_intent` 一旦进入 `parsed`,不原地覆盖;修正通过新增 `user_input_id` 并引用 `previous_user_input_id`。
- 每个 `UserInput` 至少对应 0~N 个 `InvestmentThesis`,由 `thesis_id` 反查。

### 2.6 与 InvestmentThesis 的关系

```text
1 个 UserInput(input_type=philosophy)
  → N 个 InvestmentThesis
    (例:用户说"科技+消费双主线" → 拆成 thesis_A_tech, thesis_B_consumer)

1 个 UserInput(input_type=industry)
  → 1 个 InvestmentThesis(单行业)

1 个 UserInput(input_type=target)
  → 1 个 InvestmentThesis(围绕该标的)
```

---

## 3. 实体 1:StrategyPolicy(策略政策)

### 3.1 必填字段(冻结)

```yaml
policy_id: string                 # 全局唯一,如 "foof_growth"
version: int                      # 自增,1 起
strategy_name: string             # 如 "FOF 成长型"
business_mode: enum               # private_strategy | fof
strategy_type: enum               # equity_long_only | long_short | quant | fof_growth | multi_strategy
market_scope: string[]            # 如 ["cn_a", "hk"]
investment_horizon: duration      # ISO 8601, 如 "P1Y"
benchmark: string                 # 基准代码,如 "CSI300"
target_return: decimal            # 年化目标
risk_budget: decimal              # 年化波动率预算
maximum_drawdown: decimal         # 0~1
leverage_limit: decimal           # 默认 1.0
liquidity_limit: duration         # 赎回周期, 如 "P30D"
position_limit: object            # {single_manager: 0.2, single_fund: 0.15, single_industry: 0.3}
allowed_universe: string[]        # 允许的管理人 ID 或策略类型
excluded_universe: string[]       # 黑名单
valuation_policy: object          # 估值容忍度,如 {pe_max: 60, pb_max: 10}
monitoring_policy: object         # 监控阈值,见 entity 5
effective_from: date
effective_to: date                # null 表示长期
approved_by: string
```

### 3.2 状态机

```text
draft → approved → active → deprecated
                ↘ rejected(分支)
```

- `draft`:可修改。
- `approved`:已签字但未生效。
- `active`:当前生效,不可修改字段(只能新增 version)。
- `deprecated`:被新版本替代,只读。

### 3.3 不可变约束

- `policy_id + version` 唯一。
- 处于 `active` 状态的同一 `policy_id` **只能有 1 个**。
- 历史 `DecisionRecord` 必须能引用旧 `version`(不允许清理旧版本)。

---

## 4. 实体 2:InvestmentThesis(投资假设)

### 4.1 必填字段(冻结)

```yaml
thesis_id: string                 # 全局唯一
user_input_id: string             # 🆕 引用 UserInput,所有 Thesis 必有源头
strategy_policy_id: string       # 引用 StrategyPolicy.policy_id
strategy_policy_version: int     # 固定本次假设使用的政策版本
title: string                     # 一句话标题
belief_statement: string          # 核心判断
time_horizon: duration            # 如 "P12M"
supporting_evidence: string[]     # 证据 ID 列表
opposing_evidence: string[]       # 反向证据
key_metrics: object               # 关键验证指标
candidate_assets: string[]        # 候选资产/管理人/行业 ID
valuation_view: object            # 估值容忍度
catalysts: string[]               # 催化剂
invalidation_conditions: string[] # 失效条件
owner: string                     # 研究员 ID
as_of_date: date                  # 数据快照日期
data_snapshot_id: string          # 强绑定
status: enum                      # 见 4.2
created_at: timestamp
next_review_at: date
```

### 4.2 状态机

```text
draft → researching → validated → approved → watching → invalidated
                                ↘            ↘
                                  closed       closed
```

| 状态 | 含义 | 触发者 |
|---|---|---|
| draft | 撰写中 | 研究员 |
| researching | 证据收集中 | 研究员 |
| validated | 证据充分,待投资经理复核 | 投资经理 |
| approved | 通过投决(阶段 3) | 投决会 |
| watching | 持续观察,不立即行动 | 投资经理 |
| invalidated | 失效条件触发 | 系统 / 投资经理 |
| closed | 主动关闭 | 任意主理人 |

### 4.3 不可变约束

- 一旦进入 `validated`,`belief_statement` / `supporting_evidence` / `as_of_date` / `data_snapshot_id` **不可修改**。
- **🆕 用户事后修订理念的处理**:不允许原地修改 `belief_statement`;必须新增 `thesis_id` 并在 `previous_thesis_id` 字段记录引用。
- 状态变更必须写入 audit_log(沿用 `0013_audit_log.sql`)。

---

## 5. 实体 3:CandidateSet(候选集合)

### 5.1 必填字段(冻结)

```yaml
candidate_set_id: string          # 一次候选集合的全局 ID
candidate_id: string               # 集合中的单个候选 ID
thesis_id: string                 # 引用 InvestmentThesis
user_input_id: string             # 🆕 引用 UserInput,用于复盘"用户当时问的什么"
asset_type: enum                  # stock | industry | fund | manager | strategy | product
asset_code: string                # 管理人 ID 或基金代码
asset_name: string
fit_score: decimal                # 认知匹配度, 0~1
evidence_score: decimal           # 证据强度, 0~1
valuation_status: enum            # undervalued | fair | overvalued | unknown
data_quality_status: enum         # sufficient | partial | insufficient
portfolio_contribution: object    # 阶段 2 填,阶段 0 可空
conflict_reasons: string[]        # 与其他候选的冲突
exclusion_reasons: string[]       # 排除原因(只增不删)
as_of_date: date
data_snapshot_id: string          # 强绑定
candidate_status: enum            # 见 5.2
```

### 5.2 状态机

```text
proposed → screening → reviewed → approved
                                ↘ rejected
```

- `proposed`:研究员初步提名。
- `screening`:数据补全中。
- `reviewed`:投资经理已审。
- `approved` / `rejected`:终态。

### 5.3 不可变约束

- `exclusion_reasons` 一旦写入,只增不删(用于复盘"为什么当时排除")。
- 同一 `thesis_id` 下 `asset_code` 唯一。

---

## 6. 实体 4:DecisionRecord(投资决策快照)

### 6.1 必填字段(冻结)

```yaml
decision_id: string
strategy_policy_id: string
strategy_policy_version: int      # 引用 StrategyPolicy.version
thesis_id: string
user_input_id: string             # 🆕 引用 UserInput
data_snapshot_id: string
candidate_set_id: string
proposed_positions: object[]      # [{asset_code, weight, role}]
rejected_positions: object[]      # [{asset_code, reason}]
risk_check_result: object         # 风险检查输出
committee_decision: enum          # approved | rejected | watching | pending_data
decision_reason: string
manual_override: object           # {field, from, to, reason, by}
reviewer: string[]
approved_at: timestamp
valid_until: date
```

### 6.2 状态机

```text
pending → approved | rejected | watching
```

- `pending`:投决备料完成,待表决。
- `approved`:通过。
- `rejected`:否决。
- `watching`:观察,延后表决。

### 6.3 不可变约束(**最重要**)

- **整行不可更新**。任何修正通过新增 `decision_id` + 引用原 decision_id 实现。
- `strategy_policy_version` / `data_snapshot_id` / `committee_decision` **绝对不可变**。
- 这是借鉴 NautilusTrader 事件重放与 LEAN 决策审计的核心约束。

### 6.4 阶段 0 和阶段 1 状态

阶段 0 只冻结字段和状态机,不建表。阶段 1 建最小版,只支持：

```text
pending → approved | rejected | watching | pending_data
```

阶段 1 的最小版只记录研究经理或投资经理的状态和理由,不实现多人投决会、投票、权限矩阵和正式审批流。完整投决会留到阶段 3。

---

## 7. 实体 5:MonitoringEvent(监控事件)

### 7.1 必填字段(冻结)

```yaml
event_id: string
strategy_policy_id: string
strategy_policy_version: int
portfolio_id: string              # 阶段 2 引入,阶段 0 留空
event_type: enum                  # holding_change | industry_drift | style_drift | manager_change | data_stale | thesis_invalidation | risk_breach
severity: enum                    # info | warning | critical
source_snapshot: string           # data_snapshot_id
trigger_value: decimal
threshold: decimal
detected_at: timestamp
assigned_to: string
action: enum                      # none | review | escalate | auto_hold
action_reason: string
resolved_at: timestamp            # null 表示未处理
```

### 7.2 状态机

```text
detected → assigned → resolving → resolved
                                      ↘ closed(无法处理,人工标记)
```

### 7.3 不可变约束

- `trigger_value` / `threshold` / `source_snapshot` 不可修改。
- 处理过程通过新增事件 + `parent_event_id` 关联,而不是修改原事件。

---

## 8. 字段命名规范(全局)

| 类别 | 规范 | 例子 |
|---|---|---|
| ID | `snake_case` | `thesis_id`, `data_snapshot_id` |
| 时间 | ISO 8601 | `2026-07-10`, `P12M`, `2026-07-10T08:00:00Z` |
| 金额 / 权重 / 比例 | `decimal`, 0~1 范围 | `0.15` 表示 15% |
| 状态 | 单词,小写 | `validated`, `approved` |
| 枚举 | 单词,小写 | `fof_growth`, `undervalued` |
| 数组 | 复数名词 | `supporting_evidence`, `exclusion_reasons` |

> **不在字段里塞表达式或脚本**。这是策略政策 YAML 的硬约束。

---

## 9. 实体关系图(完整)

```text
[UserInput]                  (用户输入,场景 A/B/C 入口)
    │ 1:N
    ↓
[InvestmentThesis]           (投资假设,研究主线)
    │ 1:N
    ↓
[CandidateSet]               (候选集合)
    │ N:1
    ↓
[DataSnapshot]               (数据快照,横切所有实体)
    │
    ├── 引用 → [StrategyPolicy] (策略政策,横向约束)
    │
    └── 引用 → [DecisionRecord] (决策快照,阶段 1 最小版)
                   ↓
              [MonitoringEvent] (监控事件,投后)
```

> **所有实体都引用 `data_snapshot_id`**。这是借鉴 Qlib 实验记录、LEAN 决策引擎、NautilusTrader 事件重放的核心。

---

## 10. 与现有字段的对照

| 本文档字段 | 现有 backend 对应 |
|---|---|
| `data_snapshot_id` | `0011_data_snapshots.sql` 已存在,**直接复用** |
| `supporting_evidence` | 现有 `label_engine` 的 evidence 表 |
| `risk_check_result` | 现有 `portfolio/constraints.py` + `acceptance.py` |
| `manual_override` | 现有 `audit.py` 留有扩展点 |
| `strategy_policy_version` | **新增**,阶段 1 引入 |
| `user_input_id` | **新增**,阶段 1 引入(用户输入追踪) |
| `session_id` | **新增**,阶段 1 引入(跨场景追问) |

> 阶段 0 复用现有 `data_snapshots` 与 `audit_log`,**不新建**。

---

## 11. 阶段 0 出口

- [x] 6 个实体的字段命名冻结
- [x] 6 个实体的状态机冻结
- [x] 不可变约束条款冻结
- [x] 至少 1 份 StrategyPolicy YAML 样例
- [ ] DecisionRecord 阶段 0 不建表,阶段 1 建最小版,阶段 3 扩展完整投决
- [ ] MonitoringEvent 不建表(阶段 1 实施)
