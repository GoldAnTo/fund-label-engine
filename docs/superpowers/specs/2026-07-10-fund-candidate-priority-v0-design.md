# 基金候选优先级 v0 设计

## 1. 目标

本阶段把现有“认知匹配后得到基金列表”的能力升级为可解释、可复现、可审计的研究优先级。

系统需要回答：

> 在同一投资假设、策略政策和数据快照下，哪些基金应当当前优先研究，哪些应当后续研究、等待估值、补充数据或明确排除，以及为什么。

本阶段输出研究顺序，不输出买入建议、组合权重、收益预测或自动投决。

## 2. 已确认的产品边界

- v0 只评价基金候选。
- 股票、行业和产业链只作为认知映射、持仓穿透、基本面和估值证据。
- CandidateSet 与 CandidatePriorityRun 分离。
- CandidateSet 回答“哪些基金与当前投资假设相关”。
- CandidatePriorityRun 回答“基于哪个策略、快照和规则版本，这些基金应当如何排序”。
- 不生成不可解释的单一综合分。
- 先执行策略和数据门禁，再分配优先级档位，最后在同一档位内稳定排序。
- 数据缺失不能解释为正面结果。
- `no_eligible_candidate` 是正常业务结果，不是系统错误。

## 3. 范围

### 3.1 本阶段包含

- 增加基金候选优先级策略配置。
- 增加纯规则 CandidatePriorityEngine。
- 改造 CognitionEngine，使治理链路可以获取未截断的完整基金候选证据。
- 区分真实目标持仓权重、已披露持仓权重和披露内匹配比例。
- 增加 CandidatePriorityRun 和 CandidatePriorityResult 持久化。
- 增加 Repository、Service、API、审计和端到端 smoke。
- 保留同一投资假设在不同数据快照下的历史优先级结果。

### 3.2 本阶段不包含

- 股票、行业、基金的跨资产统一排名。
- 单一综合投资总分。
- 未来收益预测。
- 组合权重和自动调仓。
- 买入、赎回或销售建议。
- 自动投决和多人投票。
- 前端重构。
- 大模型自由生成排名理由。
- 用历史短期收益直接决定研究优先级。

## 4. 总体数据流

```text
ResearchInput
  -> InvestmentThesis
  -> CognitionEngine 完整基金证据
  -> CandidateSet 基金候选关系
  -> CandidatePriorityEngine 规则评价
  -> CandidatePriorityRun 评价快照
  -> CandidatePriorityResult 每只基金的档位、排名和原因
  -> Governance API / smoke / 后续研究工作台
```

CandidatePriorityEngine 是纯计算组件，不读写数据库，也不直接依赖 FastAPI 或 CognitionEngine 的返回字典。

## 5. 候选集合边界

CandidateSet 不等于全市场基金列表。v0 只纳入以下基金：

- 通过股票、行业或产业链映射识别到真实目标暴露的基金。
- 被 ResearchInput 明确点名的基金。
- 已识别目标暴露，但因估值门禁进入观察的基金。
- 已识别目标暴露，但关键证据不足的基金。

未发现任何目标暴露、也未被明确点名的基金不进入 CandidateSet。

对于缺少持仓、因此无法完成映射的全市场基金，只在运行汇总中记录 `unmapped_due_to_data_count`，不为每只基金创建噪声候选。被明确点名但缺少持仓的基金仍进入 CandidateSet，并评价为 `data_insufficient`。

## 6. 基金证据契约

新增纯数据对象 `FundCandidateEvidence`，至少包含：

```text
fund_code
fund_name
matched_holding_weight
disclosed_holding_weight
normalized_match_pct
holding_report_date
holding_age_days
factor_coverage_weight
valuation
holding_trend
manager_identity
evidence_types
policy_conflicts
data_snapshot_id
```

三个持仓指标的定义：

```text
matched_holding_weight
  = 目标股票或行业占基金净值的真实权重

disclosed_holding_weight
  = 当前可见股票持仓合计占基金净值的权重

normalized_match_pct
  = matched_holding_weight / disclosed_holding_weight
```

研究优先级以 `matched_holding_weight` 为主要匹配依据。`normalized_match_pct` 只用于解释已披露持仓内部的主题纯度，不能替代真实基金净值暴露。

## 7. 优先级决策顺序

规则必须严格按以下顺序执行。前一层命中后，后一层不能把结果升级。

### 7.1 策略门禁

命中任一硬门禁时：

```text
eligibility_status = ineligible
priority_tier = excluded
```

硬门禁包括：

- 候选不是基金。
- 不在策略允许的市场、产品或资产范围。
- 命中基金、管理人或产品黑名单。
- 真实目标持仓低于策略明确配置的最低要求。
- 触发策略明确标记为 hard 的估值或风险约束。
- 与当前投资假设没有可识别关系。

### 7.2 数据可信度门禁

命中任一关键数据缺口时：

```text
eligibility_status = unassessable
priority_tier = data_insufficient
```

关键数据缺口包括：

- 没有持仓报告期。
- 没有股票持仓数据。
- 已披露持仓权重低于策略要求。
- 持仓报告期超过允许时效。
- 行业映射或股票因子覆盖不足。
- 策略要求估值证据，但 PE、PB、估值分位等全部缺失。
- 策略要求确认管理主体，但无法识别基金经理或产品主体。
- 数据快照不存在。

规则纪律：

```text
估值缺失 != 估值合理
持仓缺失 != 不持有
因子缺失 != 风险较低
```

### 7.3 估值观察

基金通过策略和数据门禁，但只触发估值软限制时：

```text
eligibility_status = eligible
priority_tier = valuation_watch
```

软限制包括：

- 加权估值超过策略软限制。
- 估值分位处于高位。
- PEG 或隐含增长年限显示市场预期已透支。
- 认知成立但缺少安全边际。

估值偏贵默认进入观察，不自动永久排除。只有策略明确配置 `valuation_breach_mode: exclude` 时才进入 `excluded`。

### 7.4 当前优先研究

满足全部条件时：

```text
eligibility_status = eligible
priority_tier = research_now
```

条件：

- 已通过策略和数据门禁。
- 数据质量为 `sufficient`。
- 真实目标持仓达到策略要求。
- 策略要求的证据类型全部存在。
- 估值状态不是 `overvalued`。
- 没有重大反向证据或风格冲突。
- 持仓趋势不是明显持续下降。

### 7.5 后续研究

通过基础门禁，但存在非致命缺口时：

```text
eligibility_status = eligible
priority_tier = research_next
```

非致命缺口包括：

- 基础证据存在，但缺少催化剂、反向证据或部分辅助证据。
- 真实目标持仓达到最低要求，但认知匹配程度一般。
- 持仓趋势下降，需要进一步确认。
- 基金经理、规模或产品信息存在非关键缺口。
- 多只基金证据接近，需要人工横向比较。

## 8. 可解释指标

### 8.1 fit_score

`fit_score` 不直接复制当前 CognitionEngine 的 `match_pct`。持仓权重在运行时统一为 0 到 1 的小数，v0 的公式固定为：

```text
fit_score = min(max(matched_holding_weight, 0), 1)
```

原始的 `matched_holding_weight`、`disclosed_holding_weight` 和 `normalized_match_pct` 必须同时保留，不能只保存转换后的分数。

### 8.2 evidence_score

```text
evidence_score
  = 已满足的必需证据类型数 / 必需证据总数
```

必需证据来自策略政策，不在代码中维护第二套列表。

### 8.3 evidence_types

v0 支持以下证据类型：

- `business_logic`
- `earnings_or_cashflow`
- `valuation`
- `catalyst_or_expectation_gap`
- `opposing_evidence`
- `holding_truth`
- `holding_trend`
- `manager_identity`

每类证据必须关联原始数据或明确来源，不能只保存自然语言结论。

## 9. 档内排序

只有同一 `priority_tier` 内部进行排序。`priority_rank` 表示档内排名。

排序键固定为：

```text
matched_holding_weight DESC
evidence_score DESC
data_quality_status DESC
holding_report_date DESC
fund_code ASC
```

`data_quality_status` 的排序等级固定为：

```text
sufficient > partial > insufficient
```

档位展示顺序固定为：

```text
research_now
research_next
valuation_watch
data_insufficient
excluded
```

`data_insufficient` 和 `excluded` 不生成正式 `priority_rank`。

## 10. 策略配置

在现有 StrategyPolicy 中增加：

```yaml
candidate_priority:
  method_version: fund_priority_v0
  asset_type: fund
  minimum_target_holding_weight: null
  minimum_disclosed_holding_weight: null
  maximum_holding_age_days: null
  valuation_breach_mode: watch
  require_manager_identity: true
  require_holding_report_date: true
  required_evidence:
    - business_logic
    - earnings_or_cashflow
    - valuation
    - catalyst_or_expectation_gap
```

运行时不提供隐藏默认阈值。

- 正式策略缺少必需阈值时，返回配置错误，不生成正式 PriorityRun。
- 测试使用显式 fixture 阈值。
- 演示策略必须显式标记 `policy_status: example` 和 `approved_for_production: false`。
- 演示结果必须返回非生产标志，不能描述为正式投资制度输出。

`0016_candidate_priority_v0.sql` 同时为 `strategy_policies` 增加 `candidate_priority_json`。`scripts/sync_strategy_policies.py` 将 YAML 中的 `candidate_priority` 完整序列化到该列，保留嵌套结构，不在同步脚本中解释或补充阈值。

## 11. 持久化设计

新增 migration：

```text
backend/app/persistence/migrations/0016_candidate_priority_v0.sql
```

### 11.1 candidate_priority_runs

| 字段 | 含义 |
|---|---|
| `priority_run_id` | 优先级评价运行 ID |
| `candidate_set_id` | 被评价的 CandidateSet |
| `thesis_id` | 投资假设 |
| `user_input_id` | 原始研究请求 |
| `strategy_policy_id` | 策略政策 ID |
| `strategy_policy_version` | 策略政策版本 |
| `data_snapshot_id` | 数据快照 |
| `ranking_method_version` | 规则方法版本 |
| `result_status` | v0 成功记录固定为 completed |
| `result_type` | ranked_candidates / no_eligible_candidate |
| `scanned_fund_count` | CognitionEngine 扫描基金数 |
| `mapped_candidate_count` | 成功形成候选关系的基金数 |
| `unmapped_due_to_data_count` | 因数据不足无法映射的基金数 |
| `evaluated_candidate_count` | 实际完成评价的候选数 |
| `eligible_candidate_count` | eligible 候选数 |
| `tier_counts_json` | 各档位数量 |
| `created_by` | 操作人 |
| `created_at` | 创建时间 |

幂等键：

```text
candidate_set_id
+ strategy_policy_id
+ strategy_policy_version
+ data_snapshot_id
+ ranking_method_version
```

同一幂等键只能有一个成功结果。

### 11.2 candidate_priority_results

| 字段 | 含义 |
|---|---|
| `priority_result_id` | 单只基金评价 ID |
| `priority_run_id` | PriorityRun |
| `candidate_id` | CandidateSet 中的候选 ID |
| `fund_code` | 基金代码 |
| `fund_name` | 基金名称 |
| `eligibility_status` | eligible / unassessable / ineligible |
| `priority_tier` | 五档优先级 |
| `priority_rank` | 档内排名，可空 |
| `matched_holding_weight` | 真实目标持仓权重 |
| `disclosed_holding_weight` | 已披露持仓权重 |
| `normalized_match_pct` | 披露内匹配比例 |
| `fit_score` | 可解释认知匹配值 |
| `evidence_score` | 必需证据完成率 |
| `holdings_truth_status` | 持仓真实性状态 |
| `valuation_status` | 估值状态 |
| `data_quality_status` | 数据质量状态 |
| `holding_report_date` | 持仓报告期 |
| `dimension_results_json` | 各维度原始判定 |
| `priority_reasons_json` | 稳定原因码和说明 |
| `exclusion_reasons_json` | 排除原因，只增不删 |
| `created_at` | 创建时间 |

唯一约束：

```text
(priority_run_id, candidate_id)
```

PriorityResult 禁止 UPDATE 和 DELETE。重新评价必须生成新的 PriorityRun。

CandidateSet 当前没有独立的集合头表，因此 v0 由 Service 校验 `candidate_set_id` 存在且所有候选属于同一 thesis。PriorityResult 通过 `candidate_id` 外键绑定具体候选。

## 12. 组件职责

### 12.1 CandidatePriorityEngine

文件：

```text
backend/app/services/candidate_priority.py
```

职责：

- 接收 `FundCandidateEvidence` 和 `CandidatePriorityPolicy`。
- 执行门禁和档位判定。
- 生成稳定原因码、维度结果和档内排序键。
- 不访问数据库。

### 12.2 CognitionGovernanceService

文件：

```text
backend/app/services/cognition_governance_service.py
```

职责：

- 读取 ResearchInput 和 InvestmentThesis。
- 调用 CognitionEngine 的完整候选证据接口。
- 生成 CandidateSet，包括通过候选、估值观察候选和数据不完整候选。
- 将 CognitionEngine 输出转换为 `FundCandidateEvidence`。
- 调用 CandidatePriorityEngine。
- 编排 PriorityRun、PriorityResult 和 audit_log 原子落库。

### 12.3 CandidatePriorityRepository

文件：

```text
backend/app/persistence/candidate_priority.py
```

职责：

- 参数绑定和 SQL。
- PriorityRun/Result 批量写入。
- JSON 序列化与反序列化。
- 幂等键查询。
- 单连接事务和外键约束。
- 不包含业务门禁和档位逻辑。

## 13. CognitionEngine 改造

新增内部接口：

```python
build_fund_candidate_evidence(...)
```

该接口返回：

```text
all_candidates
valuation_gated_candidates
scanned_fund_count
unmapped_due_to_data_count
```

每个候选包含完整持仓、估值、趋势、报告期和覆盖度，不执行 `top_n` 截断。

现有 `run()` 保持当前响应兼容：调用新接口后继续按原逻辑生成 `step4_fund_matches[:top_n]` 和前端字段。

不能通过把 `top_n` 临时改成大数字来模拟完整候选池。

### 13.1 持仓来源兼容

当前项目存在两种持仓输入结构：

```text
stock_holdings
  report_period / net_value_ratio

fund_stock_holdings
  report_date / weight
```

新增只读 `HoldingSourceAdapter`，将两种结构统一转换为 CognitionEngine 使用的规范字段：

```text
fund_code
holding_report_date
stock_code
stock_name
weight
market
```

读取优先级固定为：

1. 数据库存在 `stock_holdings` 时读取生产结构。
2. 不存在生产结构但存在 `fund_stock_holdings` 时读取样例/标签引擎结构。
3. 两张表都不存在时返回明确的数据源不可用错误。

适配器只读取和转换，不在源数据库创建兼容表，不复制持仓数据。CognitionEngine、smoke 和 CandidatePriorityService 必须复用同一个适配器，不能分别维护 SQL。

## 14. 事务与失败行为

成功 PriorityRun 的落库顺序：

```text
验证 thesis / candidate_set / policy / snapshot
  -> 在内存中完成全部候选评价和排序
  -> 写 candidate_priority_runs
  -> 批量写 candidate_priority_results
  -> 写 audit_log
  -> commit
```

任意结果写入失败时整次事务回滚，不保留半套结果。

v0 只持久化成功完成的 PriorityRun。计算或配置失败写入 `audit_log`，但不创建半完成 PriorityRun。后续异步任务化时再扩展 running/failed 状态。

## 15. API 设计

### 15.1 从投资假设生成 CandidateSet

```http
POST /v1/governance/theses/{thesis_id}/candidate-sets
```

请求：

```json
{
  "data_snapshot_id": "snap_xxx",
  "actor_id": "researcher_001"
}
```

该接口调用 CognitionGovernanceService，生成未截断的基金 CandidateSet。认知参数必须已经保存在 ResearchInput 的 `structured_intent` 中，v0 至少要求：

```json
{
  "direction": "AI",
  "belief_link": "光模块",
  "conviction": "medium",
  "time_horizon": "long",
  "risk_tolerance": "moderate"
}
```

`direction`、`conviction`、`time_horizon` 和 `risk_tolerance` 必填，`belief_link` 可空。CandidateSet 创建接口不修改 ResearchInput 的原始文本或结构化意图。缺少必填结构化意图时返回 422，要求调用方通过新建或修订 ResearchInput 补充，不在分析接口中静默推断。

成功返回 201：

```json
{
  "candidate_set_id": "cs_xxx",
  "thesis_id": "th_xxx",
  "mapped_candidate_count": 12,
  "scanned_fund_count": 142,
  "unmapped_due_to_data_count": 8,
  "data_snapshot_id": "snap_xxx"
}
```

### 15.2 创建优先级评价

```http
POST /v1/governance/theses/{thesis_id}/candidate-priority-runs
```

请求：

```json
{
  "candidate_set_id": "cs_xxx",
  "data_snapshot_id": "snap_xxx",
  "ranking_method_version": "fund_priority_v0",
  "actor_id": "researcher_001"
}
```

成功返回 201：

```json
{
  "priority_run_id": "cpr_xxx",
  "result_type": "ranked_candidates",
  "evaluated_candidate_count": 12,
  "eligible_candidate_count": 9,
  "tier_counts": {
    "research_now": 3,
    "research_next": 4,
    "valuation_watch": 2,
    "data_insufficient": 2,
    "excluded": 1
  },
  "approved_for_production": false
}
```

同一幂等键重复创建返回 409，并在响应 detail 中返回已有 `priority_run_id`。

### 15.3 查询优先级结果

```http
GET /v1/governance/candidate-priority-runs/{priority_run_id}
```

返回：

- ResearchInput、Thesis、CandidateSet 引用。
- StrategyPolicy 和数据快照。
- 排名方法版本。
- 运行统计。
- 五档候选列表。
- 每只基金的原始指标、原因码和证据状态。

### 15.4 查询投资假设的历史评价

```http
GET /v1/governance/theses/{thesis_id}/candidate-priority-runs
```

按创建时间倒序返回，用于比较不同持仓快照、策略版本和规则版本。

## 16. HTTP 错误映射

| 状态码 | 情况 |
|---|---|
| 404 | thesis、candidate_set、policy、snapshot 或 priority_run 不存在 |
| 409 | 同一幂等键已经存在成功 PriorityRun |
| 422 | 策略配置不完整、候选集合不一致、输入非法 |
| 503 | CognitionEngine 必需数据源不可用 |
| 500 | 未预期内部错误 |

`no_eligible_candidate` 返回成功业务响应，不返回错误状态码。

## 17. 稳定原因码

优先级理由必须由规则生成，并至少支持：

```text
policy_asset_type_not_allowed
policy_universe_excluded
target_exposure_below_minimum
holding_report_date_missing
holding_data_missing
holding_data_stale
disclosed_holding_weight_low
factor_coverage_insufficient
valuation_data_missing
valuation_soft_breach
valuation_hard_breach
required_evidence_missing
holding_trend_decreasing
all_required_evidence_present
```

API 同时返回稳定原因码和人类可读说明。前端未来依赖原因码，不解析自然语言。

## 18. 测试设计

### 18.1 纯规则测试

- 高匹配但持仓过期：`data_insufficient`。
- 高匹配但估值偏贵：`valuation_watch`。
- 必需证据完整且估值合理：`research_now`。
- 缺少非关键证据：`research_next`。
- 策略黑名单：`excluded`。
- 估值缺失：不能进入 `research_now`。
- 持仓缺失：不能推断为零暴露。

### 18.2 指标测试

- 真实目标持仓 5%、已披露持仓 10% 时，保存真实暴露 5% 和披露内匹配 50%，排序使用 5%。
- evidence_score 严格等于必需证据完成率。
- 同档排序对相同输入稳定。

### 18.3 持久化测试

- 空库 migration 成功。
- PriorityRun 和 Results 原子写入。
- Result 禁止 UPDATE 和 DELETE。
- 相同幂等键不重复创建。
- 新快照生成新 PriorityRun，旧结果保留。

### 18.4 集成测试

- HoldingSourceAdapter 对两种持仓表结构生成相同规范字段。
- 两种持仓表都不存在时返回数据源不可用错误。
- CognitionEngine 完整候选接口不受 `top_n` 截断。
- 通过候选和估值观察候选都进入 CandidateSet。
- CandidateSet 创建接口不能覆盖已冻结的 structured_intent。
- API 能从 PriorityRun 反查 Thesis、ResearchInput、Policy 和 Snapshot。
- 全部候选被排除时返回 `no_eligible_candidate`。

### 18.5 smoke 验收

```text
ResearchInput
  -> Thesis
  -> Cognition candidate evidence
  -> CandidateSet
  -> CandidatePriorityRun
  -> CandidatePriorityResult
  -> API reverse lookup
```

报告必须展示真实 `priority_run_id`、策略版本、数据快照、档位数量、基金档内排名和原因码。

## 19. 实施顺序

1. 纯 CandidatePriorityEngine 与规则测试。
2. HoldingSourceAdapter、持仓真实权重和披露覆盖改造。
3. `0016_candidate_priority_v0.sql` 和 migration 测试。
4. CandidatePriorityRepository 和事务测试。
5. CandidatePriorityService 和幂等、审计测试。
6. CognitionEngine 完整候选接口和兼容测试。
7. CognitionGovernanceService 集成。
8. CandidateSet 创建和 PriorityRun 查询 API。
9. smoke 端到端和报告。
10. 全量回归和阶段验收文档。

## 20. 验收标准

本阶段完成时必须满足：

1. 输入一个已经结构化的投资假设，可以通过治理 Service 和 API 形成基金 CandidateSet。
2. 每只候选基金都有真实目标持仓、披露覆盖、持仓日期和数据质量。
3. 每只基金只能进入五个优先级档位之一。
4. 每个档位都有稳定原因码和原始证据。
5. 同一档内排序确定且可复现。
6. 相同候选、策略、快照和规则版本不重复生成结果。
7. 新数据快照生成新 PriorityRun，旧结果保持不可变。
8. 无合格候选时返回正常的 `no_eligible_candidate`。
9. API 可以反查 ResearchInput、Thesis、CandidateSet、Policy、Snapshot 和规则版本。
10. 系统不输出买入建议、组合权重或预测收益。

## 21. 实施修正

以下修正基于代码映射暴露出的结构问题，在 v0 实施时同步回写：

1. **CandidateSet 增加集合头和不可变证据。** 新增 `candidate_set_headers` 表，并在候选行保存 `candidate_evidence_json`，避免两次 API 调用之间证据丢失。
2. **CandidateSet 唯一约束调整为 (candidate_set_id, asset_code)。** 支持同一 Thesis 在不同数据快照下生成新集合。新集合幂等键为 `thesis_id + data_snapshot_id + source_method_version`。
3. **因子覆盖门禁增加显式阈值。** `candidate_priority` 策略配置增加 `minimum_factor_coverage_weight`，运行时不使用代码默认值。

此外，认知引擎必须按 `data_snapshots.source_db_path` 和 `factor_db_path` 读取历史数据源，不能复用当前 app.state 数据库冒充历史快照。
