# Fund Candidate Priority v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有认知匹配基金列表升级为可解释、可复现、可审计的五档基金研究优先级，同时保留策略版本、数据快照、候选证据和历史评价结果。

**Architecture:** `CognitionEngine` 从指定 `DataSnapshot` 构建未截断的基金证据；`CognitionGovernanceService` 将证据冻结为一个版本化 CandidateSet；纯计算 `CandidatePriorityEngine` 依据显式策略门禁分档和档内排序；`CandidatePriorityRepository` 原子保存 PriorityRun、Results 与审计。API 只编排这些领域服务，不在路由中实现规则，也不输出买入建议或组合权重。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLite、PyYAML、pytest、ruff。

---

## 0. 开工前必须锁定的实现修正

本计划以 [基金候选优先级 v0 设计](../specs/2026-07-10-fund-candidate-priority-v0-design.md) 为产品基线，但代码映射暴露出三项必须在实施时同步回写设计文档的结构修正：

1. **CandidateSet 必须有集合头和冻结证据。** 现有 `candidate_sets` 一行代表一只候选，无法保存集合级扫描统计，也无法在“创建 CandidateSet”和“创建 PriorityRun”两个独立 API 之间传递完整 `FundCandidateEvidence`。新增 `candidate_set_headers`，并在候选行保存 `candidate_evidence_json`。
2. **CandidateSet 必须按快照版本化。** 现有 `UNIQUE(thesis_id, asset_code)` 会阻止同一 Thesis 在新快照下生成新集合。迁移后改为 `UNIQUE(candidate_set_id, asset_code)`，新集合幂等键为 `thesis_id + data_snapshot_id + source_method_version`。
3. **因子覆盖门禁必须有显式阈值。** 设计要求判断 `factor_coverage_insufficient`，因此 `candidate_priority` 增加 `minimum_factor_coverage_weight`；运行时不得使用代码默认值。

此外，认知引擎必须读取 `data_snapshots.source_db_path` 和 `factor_db_path`，不能复用“当前 app.state 数据库”冒充历史快照。

## 1. 文件职责图

### 新增文件

- `backend/app/services/candidate_priority.py`
  - 领域数据类、策略解析、稳定原因码、纯规则分档和档内排序。
- `backend/app/cognition/holding_source.py`
  - 只读兼容 `stock_holdings` 与 `fund_stock_holdings`，输出统一持仓结构。
- `backend/app/persistence/migrations/0016_candidate_priority_v0.sql`
  - CandidateSet 头、候选快照证据、PriorityRun、PriorityResult、不可变 trigger 和索引。
- `backend/app/persistence/candidate_priority.py`
  - PriorityRun/Result 的参数化 SQL、JSON round-trip、幂等查询和原子事务。
- `backend/app/services/cognition_governance_service.py`
  - 快照驱动的候选构建、PriorityRun 编排、失败审计和领域异常。
- `backend/tests/test_candidate_priority_engine.py`
  - 纯规则和稳定排序测试。
- `backend/tests/test_holding_source_adapter.py`
  - 两种持仓表结构兼容测试。
- `backend/tests/test_candidate_priority_migrations.py`
  - 空库升级、旧数据迁移、约束和 trigger 测试。
- `backend/tests/test_candidate_priority_repository.py`
  - 原子写入、JSON、幂等和历史保留测试。
- `backend/tests/test_cognition_governance_service.py`
  - CandidateSet/PriorityRun 编排、快照路径和失败审计测试。
- `backend/tests/test_api_candidate_priority.py`
  - 四个治理 API 和 HTTP 异常映射测试。
- `backend/tests/test_smoke_candidate_priority.py`
  - 完整链路首次运行、重复运行、反查和 `no_eligible_candidate`。

### 修改文件

- `docs/superpowers/specs/2026-07-10-fund-candidate-priority-v0-design.md`
  - 回写本节三项必要修正，确保设计和实现不分叉。
- `backend/app/cognition/asset_mapper.py`
  - 改为复用 `HoldingSourceAdapter`；趋势计算不再写死生产表字段。
- `backend/app/cognition/engine.py`
  - 抽取 `build_fund_candidate_evidence()`；现有 `run()` 保持响应兼容。
- `backend/app/persistence/governance.py`
  - 支持 CandidateSet header、冻结证据、策略详情和快照详情查询。
- `backend/app/services/governance_service.py`
  - 保留现有手工候选入口兼容，但新自动候选流程由 `CognitionGovernanceService` 负责。
- `backend/app/api/governance.py`
  - 增加 CandidateSet 创建、PriorityRun 创建/详情/历史四个路由和依赖注入。
- `config/strategy_policy/private_equity_growth_v1.yaml`
  - 新增同一 `policy_id` 的 version 2 非生产示例，显式配置候选优先级；version 1 历史文件保持不变。
- `scripts/sync_strategy_policies.py`
  - 原样同步 `candidate_priority_json`。
- `scripts/p0/smoke_e2e_private_fund.py`
  - 增加 CandidateSet -> PriorityRun -> API 反查与报告内容。
- `docs/p0/phase0-acceptance.md`
  - 新增“基金候选优先级 v0”验收分节，不改写既有阶段 0 历史结果。

### 明确不修改

- `frontend/`：本批不做页面重构。API 返回稳定原因码、五档分组和历史运行，前端工作台另开设计批次。
- 组合优化与调仓模块：不把研究优先级转成权重。
- DecisionRecord：PriorityRun 不是投决记录，不能自动写 `decision_records`。

## 2. 统一领域契约

实施中只允许以下枚举值：

```python
PRIORITY_TIERS = (
    "research_now",
    "research_next",
    "valuation_watch",
    "data_insufficient",
    "excluded",
)

ELIGIBILITY_STATUSES = ("eligible", "unassessable", "ineligible")
DATA_QUALITY_ORDER = {"sufficient": 2, "partial": 1, "insufficient": 0}
RANKED_TIERS = {"research_now", "research_next", "valuation_watch"}
```

`FundCandidateEvidence` 中的权重一律是 `0..1` 小数，不允许混用百分数：

```python
@dataclass(frozen=True)
class FundCandidateEvidence:
    fund_code: str
    fund_name: str | None
    matched_holding_weight: float
    disclosed_holding_weight: float
    normalized_match_pct: float
    holding_report_date: str | None
    holding_age_days: int | None
    factor_coverage_weight: float
    valuation: dict[str, Any]
    holding_trend: dict[str, Any]
    manager_identity: dict[str, Any] | None
    evidence_types: dict[str, list[dict[str, Any]]]
    policy_conflicts: tuple[str, ...]
    data_snapshot_id: str
    asset_type: str = "fund"
```

`CandidatePriorityPolicy` 不提供阈值默认值：

```python
@dataclass(frozen=True)
class CandidatePriorityPolicy:
    method_version: str
    source_method_version: str
    asset_type: str
    minimum_target_holding_weight: float
    minimum_disclosed_holding_weight: float
    minimum_factor_coverage_weight: float
    maximum_holding_age_days: int
    valuation_breach_mode: Literal["watch", "exclude"]
    require_manager_identity: bool
    require_holding_report_date: bool
    required_evidence: tuple[str, ...]
    allowed_asset_types: tuple[str, ...]
    excluded_asset_codes: tuple[str, ...]
    valuation_policy: dict[str, Any]
    approved_for_production: bool
```

若配置字段缺失或为 `null`，抛出 `CandidatePriorityConfigurationError`，HTTP 映射为 422，不写 PriorityRun。

证据类型不能只保存布尔值。`evidence_types` 的每个值都是来源记录列表，转换关系固定为：

| 证据类型 | 来源 |
|---|---|
| `business_logic` | Thesis belief + Cognition chain 的 `benefit_logic` |
| `earnings_or_cashflow` | `revenue_exposure` 或带日期的盈利/现金流因子记录 |
| `valuation` | 持仓股票因子来源、加权估值指标及 as-of date |
| `catalyst_or_expectation_gap` | Thesis catalysts 或 Cognition expectation-gap 原始维度 |
| `opposing_evidence` | Thesis opposing evidence 或 Cognition validation 的反向证据 |
| `holding_truth` | 持仓表名、报告期、股票代码和权重 |
| `holding_trend` | 多个报告期的真实目标持仓变化 |
| `manager_identity` | 基金经理或产品主体来源记录 |

若只有结论文字而没有来源标识、日期或原始维度，该证据类型视为缺失。Thesis 相关证据由 `CognitionGovernanceService` 合并，`CognitionEngine` 不反向依赖治理数据库。

估值门禁同样不读取认知链中的隐藏默认值。纯规则引擎使用 `CandidatePriorityPolicy.valuation_policy` 对 evidence 中的原始 `weighted_pe / weighted_pb / peg / weighted_val_pct` 判定；`valuation_breach_mode` 决定命中阈值后进入 `valuation_watch` 还是 `excluded`。认知链估值只可作为解释维度，不能覆盖 StrategyPolicy。

原因码和中文说明在代码中集中维护，v0 至少固定为：

```python
REASON_MESSAGES = {
    "policy_asset_type_not_allowed": "资产类型不在策略允许范围内",
    "policy_universe_excluded": "候选命中策略排除范围",
    "thesis_relation_missing": "候选与当前投资假设没有可识别关系",
    "target_exposure_below_minimum": "真实目标持仓低于策略最低要求",
    "holding_report_date_missing": "缺少持仓报告期",
    "holding_data_missing": "缺少可验证的基金持仓数据",
    "holding_data_stale": "持仓报告期超过策略允许时效",
    "disclosed_holding_weight_low": "已披露持仓权重不足",
    "factor_coverage_insufficient": "目标持仓的因子覆盖不足",
    "manager_identity_missing": "策略要求确认管理主体但当前无法识别",
    "valuation_data_missing": "策略要求的估值证据缺失",
    "valuation_soft_breach": "估值触发观察阈值",
    "valuation_hard_breach": "估值触发策略排除阈值",
    "required_evidence_missing": "策略要求的证据类型尚未齐全",
    "holding_trend_decreasing": "目标持仓呈下降趋势",
    "all_required_evidence_present": "策略要求的证据类型已齐全",
}
```

---

## Task 1: 回写设计修正并实现纯 CandidatePriorityEngine

**Files:**

- Modify: `docs/superpowers/specs/2026-07-10-fund-candidate-priority-v0-design.md`
- Create: `backend/app/services/candidate_priority.py`
- Create: `backend/tests/test_candidate_priority_engine.py`

- [ ] **Step 1: 先写失败的领域契约和规则测试**

测试必须覆盖五档、门禁先后关系、指标和稳定排序：

```python
def test_stale_high_match_fund_is_data_insufficient(policy, evidence):
    result = CandidatePriorityEngine().evaluate_one(
        replace(evidence, matched_holding_weight=0.30, holding_age_days=181),
        policy,
    )
    assert result.priority_tier == "data_insufficient"
    assert result.eligibility_status == "unassessable"
    assert "holding_data_stale" in result.reason_codes


def test_soft_valuation_breach_cannot_be_research_now(policy, evidence):
    result = CandidatePriorityEngine().evaluate_one(
        replace(evidence, valuation={"weighted_pe": 61, "weighted_pb": 5}),
        replace(policy, valuation_policy={"max_pe": 60, "max_pb": 10}),
    )
    assert result.priority_tier == "valuation_watch"


def test_real_exposure_not_normalized_purity_drives_order(policy, evidence):
    low_real_high_purity = replace(
        evidence,
        fund_code="A",
        matched_holding_weight=0.05,
        disclosed_holding_weight=0.05,
        normalized_match_pct=1.0,
    )
    high_real_low_purity = replace(
        evidence,
        fund_code="B",
        matched_holding_weight=0.10,
        disclosed_holding_weight=0.50,
        normalized_match_pct=0.20,
    )
    results = CandidatePriorityEngine().evaluate_all(
        [low_real_high_purity, high_real_low_purity], policy
    )
    assert [r.fund_code for r in results] == ["B", "A"]
```

还需覆盖：硬门禁优先于数据缺口、估值 hard breach、黑名单、持仓缺失、报告期缺失、披露权重不足、因子覆盖不足、经理缺失、估值证据缺失、证据完成率、下降趋势进入 `research_next`、全部证据进入 `research_now`、同输入重复运行完全一致、`excluded/data_insufficient` 的 `priority_rank is None`。

- [ ] **Step 2: 运行目标测试，确认因模块不存在而失败**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_candidate_priority_engine.py -q
```

Expected: collection 阶段因 `app.services.candidate_priority` 不存在而失败。

- [ ] **Step 3: 实现不可变数据类、配置解析和原因码字典**

实现以下公开对象：

```python
class CandidatePriorityError(Exception): ...
class CandidatePriorityConfigurationError(CandidatePriorityError): ...

@dataclass(frozen=True)
class PriorityReason:
    code: str
    message: str

@dataclass(frozen=True)
class CandidatePriorityResult:
    fund_code: str
    fund_name: str | None
    eligibility_status: str
    priority_tier: str
    priority_rank: int | None
    fit_score: float
    evidence_score: float
    dimension_results: dict[str, Any]
    reasons: tuple[PriorityReason, ...]
    exclusion_reasons: tuple[PriorityReason, ...]
    evidence: FundCandidateEvidence

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reasons)
```

`parse_candidate_priority_policy(policy_row)` 同时读取 `candidate_priority`、`valuation_policy`、`allowed_universe`、`excluded_universe` 和 `approved_for_production`，只做类型校验与转换，不补阈值。

- [ ] **Step 4: 按固定顺序实现纯规则引擎**

公开接口固定为：

```python
class CandidatePriorityEngine:
    def evaluate_all(
        self,
        evidences: Sequence[FundCandidateEvidence],
        policy: CandidatePriorityPolicy,
    ) -> list[CandidatePriorityResult]: ...

    def evaluate_one(
        self,
        evidence: FundCandidateEvidence,
        policy: CandidatePriorityPolicy,
    ) -> CandidatePriorityResult: ...
```

执行顺序必须是：策略硬门禁 -> 数据可信度门禁 -> 估值软门禁 -> `research_now` -> `research_next`。档内排序键固定为：

```python
def _descending_iso_date(value: str | None) -> int:
    return -date.fromisoformat(value).toordinal() if value else 0


(
    -result.evidence.matched_holding_weight,
    -result.evidence_score,
    -DATA_QUALITY_ORDER[result.dimension_results["data_quality_status"]],
    _descending_iso_date(result.evidence.holding_report_date),
    result.fund_code,
)
```

每个可排名档位独立从 1 编号；不得生成跨档总排名和综合总分。

- [ ] **Step 5: 运行规则测试并通过**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_candidate_priority_engine.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 回写设计文档三项实现修正并检查占位符**

Run:

```bash
rg -n 'TO''DO|T''BD|待''定|place''holder' \
  docs/superpowers/specs/2026-07-10-fund-candidate-priority-v0-design.md \
  backend/app/services/candidate_priority.py \
  backend/tests/test_candidate_priority_engine.py
```

Expected: 无输出。

- [ ] **Step 7: 提交纯规则层**

```bash
git add docs/superpowers/specs/2026-07-10-fund-candidate-priority-v0-design.md \
  backend/app/services/candidate_priority.py \
  backend/tests/test_candidate_priority_engine.py
git commit -m "feat: add explainable fund priority rules"
```

## Task 2: 建立只读 HoldingSourceAdapter

**Files:**

- Create: `backend/app/cognition/holding_source.py`
- Create: `backend/tests/test_holding_source_adapter.py`
- Modify: `backend/app/cognition/asset_mapper.py`
- Modify: `backend/tests/test_cognition_engine.py`

- [ ] **Step 1: 写两种持仓表结构的等价测试**

分别创建：

```sql
CREATE TABLE stock_holdings (
  fund_code TEXT, stock_code TEXT, stock_name TEXT,
  report_period TEXT, net_value_ratio REAL
);
```

和：

```sql
CREATE TABLE fund_stock_holdings (
  fund_code TEXT, stock_code TEXT, stock_name TEXT,
  report_date TEXT, weight REAL
);
```

断言适配结果都严格等于：

```python
{
    "fund_code": "000001",
    "holding_report_date": "2025-12-31",
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "weight": 0.12,
    "market": None,
}
```

同时测试：两表并存优先 `stock_holdings`；两表都不存在抛 `HoldingSourceUnavailableError`；适配器运行后 `sqlite_master` 没有新增表。

再增加 factor DB 未 attach 的测试：基础持仓仍可读取，PE/PB/ROE/估值分位返回 `None`，后续规则将其判断为证据不足，而不是让 SQL 因 `factordb` schema 不存在而崩溃。

- [ ] **Step 2: 运行测试，确认失败**

```bash
.venv/bin/python -m pytest backend/tests/test_holding_source_adapter.py -q
```

Expected: 模块不存在导致失败。

- [ ] **Step 3: 实现统一只读接口**

```python
class HoldingSourceUnavailableError(RuntimeError): ...

class HoldingSourceAdapter:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def schema_name(self) -> Literal["stock_holdings", "fund_stock_holdings"]: ...
    def list_fund_codes(self) -> list[str]: ...
    def list_report_dates(self, fund_code: str, limit: int = 4) -> list[str]: ...
    def load_holdings(
        self, fund_code: str, report_date: str | None = None
    ) -> list[dict[str, Any]]: ...
```

所有表名只从内部白名单选择，基金代码和日期继续使用参数绑定。权重不乘 100。

- [ ] **Step 4: 改造 asset_mapper 复用适配器**

`get_holdings()` 保留现有函数签名以兼容调用方，但内部先由适配器读取基础持仓，再批量补行业和因子。`_get_recent_periods()` 和 `calculate_holding_trend()` 不再直接查询 `report_period`。

- [ ] **Step 5: 运行适配器和现有认知引擎测试**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_holding_source_adapter.py \
  backend/tests/test_cognition_engine.py -q
```

Expected: 全部通过，现有 `CognitionEngine.run()` 响应测试零破坏。

- [ ] **Step 6: 提交持仓适配层**

```bash
git add backend/app/cognition/holding_source.py \
  backend/app/cognition/asset_mapper.py \
  backend/tests/test_holding_source_adapter.py \
  backend/tests/test_cognition_engine.py
git commit -m "refactor: unify fund holding sources"
```

## Task 3: 抽取 CognitionEngine 完整候选证据接口

**Files:**

- Modify: `backend/app/cognition/engine.py`
- Modify: `backend/tests/test_cognition_engine.py`

- [ ] **Step 1: 写未截断候选和真实权重测试**

新增测试断言：

```python
evidence = engine.build_fund_candidate_evidence(
    direction="AI",
    conviction="medium",
    time_horizon="long",
    risk_tolerance="moderate",
    data_snapshot_id="snap1",
    as_of_date="2026-01-15",
)
assert len(evidence.all_candidates) > 1
assert evidence.scanned_fund_count == 3
assert evidence.all_candidates[0].matched_holding_weight <= 1
assert evidence.all_candidates[0].disclosed_holding_weight <= 1
assert evidence.all_candidates[0].normalized_match_pct <= 1
```

另用 `run(..., top_n=1)` 断言旧响应仍只返回 1 只，但 `build_fund_candidate_evidence()` 返回完整集合。

- [ ] **Step 2: 运行目标测试，确认新方法不存在**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_engine.py -q
```

Expected: 新测试因方法不存在而失败，既有测试仍通过。

- [ ] **Step 3: 新增批次返回对象**

```python
@dataclass(frozen=True)
class FundCandidateEvidenceBatch:
    all_candidates: tuple[FundCandidateEvidence, ...]
    valuation_gated_candidates: tuple[FundCandidateEvidence, ...]
    scanned_fund_count: int
    mapped_candidate_count: int
    unmapped_due_to_data_count: int
```

`mapped_candidate_count` 是进入 CandidateSet 的基金数；被明确点名但数据不足的基金计入 mapped；没有映射且未点名的基金只计入 `unmapped_due_to_data_count`。

- [ ] **Step 4: 把当前 run() 的 Step 2-4 抽成完整证据构建**

公开签名：

```python
def build_fund_candidate_evidence(
    self,
    *,
    direction: str,
    belief_link: str | None = None,
    conviction: str,
    time_horizon: str,
    risk_tolerance: str,
    data_snapshot_id: str,
    as_of_date: str,
    explicitly_named_fund_codes: Sequence[str] = (),
    max_valuation_percentile: float | None = None,
) -> FundCandidateEvidenceBatch: ...
```

计算公式固定为：

```python
disclosed = sum(h["weight"] for h in holdings)
matched = match["matched_weight"]
normalized = matched / disclosed if disclosed > 0 else 0.0
fit_score = min(max(matched, 0.0), 1.0)
factor_coverage = (
    sum(h["weight"] for h in holdings if _has_required_factor(h)) / disclosed
    if disclosed > 0 else 0.0
)
```

`holding_report_date` 来自适配器的实际报告期；`holding_age_days` 使用调用方传入的 `as_of_date` 计算，禁止使用系统今天日期。

- [ ] **Step 5: 让现有 run() 调用新接口但保持兼容**

`run()` 继续输出原有 `match_pct` 百分数和 `step4_fund_matches[:top_n]`；它只是把新证据转换回旧字典。不得删除现有组合输出字段，也不得让治理链路调用组合构建。

- [ ] **Step 6: 运行认知测试**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_engine.py -q
```

Expected: 全部通过；完整候选接口不受 `top_n` 影响。

- [ ] **Step 7: 提交认知证据接口**

```bash
git add backend/app/cognition/engine.py backend/tests/test_cognition_engine.py
git commit -m "feat: expose complete fund candidate evidence"
```

## Task 4: 实现 0016 migration、CandidateSet 版本化和策略同步

**Files:**

- Create: `backend/app/persistence/migrations/0016_candidate_priority_v0.sql`
- Create: `backend/tests/test_candidate_priority_migrations.py`
- Modify: `backend/tests/test_governance_migrations.py`
- Modify: `scripts/sync_strategy_policies.py`
- Create: `config/strategy_policy/private_equity_growth_v1.yaml`

- [ ] **Step 1: 写空库、旧库升级和不可变测试**

测试必须验证：

- 空库依次运行全部 migration 成功。
- 0015 已有 CandidateSet 行在 0016 后仍可查询。
- 同一 Thesis/基金可在两个不同 `candidate_set_id` 中存在。
- 同一集合内重复基金失败。
- PriorityResult UPDATE/DELETE 都由 trigger 拒绝。
- CandidateSet 冻结字段和 `candidate_evidence_json` 不能 UPDATE。
- 同一 PriorityRun 幂等组合只能成功一次。
- `candidate_priority_json` 能完整 round-trip，嵌套数组不被压平。

- [ ] **Step 2: 运行 migration 测试，确认缺少 0016**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_candidate_priority_migrations.py \
  backend/tests/test_governance_migrations.py -q
```

Expected: 新表/新列不存在导致失败。

- [ ] **Step 3: 编写 0016 schema**

核心表头必须是：

```sql
CREATE TABLE candidate_set_headers (
    candidate_set_id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL REFERENCES investment_theses(thesis_id),
    user_input_id TEXT NOT NULL REFERENCES research_inputs(user_input_id),
    data_snapshot_id TEXT REFERENCES data_snapshots(snapshot_id),
    source_method_version TEXT NOT NULL,
    scanned_fund_count INTEGER NOT NULL,
    mapped_candidate_count INTEGER NOT NULL,
    unmapped_due_to_data_count INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (thesis_id, data_snapshot_id, source_method_version)
);
```

重建 `candidate_sets` 时保留现有列，增加：

```sql
candidate_evidence_json TEXT,
FOREIGN KEY (candidate_set_id) REFERENCES candidate_set_headers(candidate_set_id),
UNIQUE (candidate_set_id, asset_code)
```

迁移旧数据前，按已有 `candidate_set_id` 聚合插入 header，`source_method_version='legacy_governance_v0'`；旧行的 `candidate_evidence_json` 为 NULL，仅新自动流程要求非空。先 DROP 依赖视图，再重建表和视图，避免 SQLite rename 后视图指向 legacy 表。

PriorityRun/Result 使用设计文档第 11 节全部字段，并增加外键：

```sql
FOREIGN KEY (candidate_set_id) REFERENCES candidate_set_headers(candidate_set_id),
FOREIGN KEY (candidate_id) REFERENCES candidate_sets(candidate_id),
UNIQUE (
  candidate_set_id, strategy_policy_id, strategy_policy_version,
  data_snapshot_id, ranking_method_version
),
UNIQUE (priority_run_id, candidate_id)
```

- [ ] **Step 4: 增加策略列和同步字段**

```sql
ALTER TABLE strategy_policies ADD COLUMN candidate_priority_json TEXT;
```

在 `scripts/sync_strategy_policies.py` 的 `json_keys` 增加 `candidate_priority`，不解释、不默认、不覆盖已存在版本。

不得修改已存在的 `private_equity_growth_v0.yaml`（policy version 1）。复制其业务基础字段到 `private_equity_growth_v1.yaml`，保持 `policy_id: private_equity_growth`，把 `version` 设为 2，并显式增加非生产参数：

```yaml
candidate_priority:
  method_version: fund_priority_v0
  source_method_version: fund_candidate_evidence_v0
  asset_type: fund
  minimum_target_holding_weight: 0.03
  minimum_disclosed_holding_weight: 0.10
  minimum_factor_coverage_weight: 0.50
  maximum_holding_age_days: 180
  valuation_breach_mode: watch
  require_manager_identity: true
  require_holding_report_date: true
  required_evidence:
    - business_logic
    - earnings_or_cashflow
    - valuation
    - catalyst_or_expectation_gap
```

同一非生产示例还要把已有 `valuation_policy` 的 `max_pe / max_pb / max_peg / max_valuation_percentile` 设置为显式数值，保证 smoke 没有隐藏估值阈值。示例值固定为 `60 / 10 / 2.0 / 85`，并继续保留 `status: example`；这些数值不得解释为公司正式估值纪律。

这些值只属于 `policy_status: example` 且 `approved_for_production: false` 的 smoke 示例，不得写成公司正式制度。

`foof_growth_v0.yaml` 保持扩展样例原样，不为它虚构私募候选优先级阈值。smoke 必须显式使用 `private_equity_growth v2`，不能选择“数据库里最新的一条”作为隐式策略。

- [ ] **Step 5: 运行 migration 和同步测试**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_candidate_priority_migrations.py \
  backend/tests/test_governance_migrations.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交数据库契约**

```bash
git add backend/app/persistence/migrations/0016_candidate_priority_v0.sql \
  backend/tests/test_candidate_priority_migrations.py \
  backend/tests/test_governance_migrations.py \
  scripts/sync_strategy_policies.py \
  config/strategy_policy/private_equity_growth_v1.yaml
git commit -m "feat: persist versioned candidate priority data"
```

## Task 5: 扩展 GovernanceRepository 保存冻结 CandidateSet

**Files:**

- Modify: `backend/app/persistence/governance.py`
- Modify: `backend/tests/test_governance_repository.py`
- Modify: `backend/app/services/governance_service.py`
- Modify: `backend/tests/test_governance_service.py`

- [ ] **Step 1: 写 header、证据和策略/快照详情测试**

新增测试覆盖：`insert_candidate_set_header()` 与候选行同事务；任一候选失败时 header、候选、audit 全回滚；`get_candidate_set_header()`、`get_strategy_policy()`、`get_data_snapshot()` 返回 JSON 解析后的字典；坏 JSON 抛 `ValueError`；旧 `create_candidates()` 仍可使用但会生成 `legacy_manual_v0` header。

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_governance_repository.py \
  backend/tests/test_governance_service.py -q
```

- [ ] **Step 3: 实现 Repository 接口**

```python
def insert_candidate_set_header(
    self,
    *,
    candidate_set_id: str,
    thesis_id: str,
    user_input_id: str,
    data_snapshot_id: str | None,
    source_method_version: str,
    scanned_fund_count: int,
    mapped_candidate_count: int,
    unmapped_due_to_data_count: int,
    created_by: str,
) -> str: ...

def get_candidate_set_header(self, candidate_set_id: str) -> dict[str, Any] | None: ...
def get_strategy_policy(self, policy_id: str, version: int) -> dict[str, Any] | None: ...
def get_data_snapshot(self, snapshot_id: str) -> dict[str, Any] | None: ...
```

`insert_candidates()` 新增读取 `candidate_evidence` 并写 `candidate_evidence_json`；row mapper 还原为 `candidate_evidence`。

- [ ] **Step 4: 兼容 GovernanceService 的手工候选入口**

`create_candidates()` 在同一事务先写 header，再写行。若调用方没有 `data_snapshot_id`，header 允许 NULL，但该集合不能用于正式 PriorityRun；自动候选 API 始终要求非空快照。

- [ ] **Step 5: 运行治理 Repository/Service 回归**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_governance_repository.py \
  backend/tests/test_governance_service.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交 CandidateSet 持久化**

```bash
git add backend/app/persistence/governance.py \
  backend/app/services/governance_service.py \
  backend/tests/test_governance_repository.py \
  backend/tests/test_governance_service.py
git commit -m "feat: freeze candidate set evidence by snapshot"
```

## Task 6: 实现 CandidatePriorityRepository

**Files:**

- Create: `backend/app/persistence/candidate_priority.py`
- Create: `backend/tests/test_candidate_priority_repository.py`

- [ ] **Step 1: 写原子性、幂等、历史和查询测试**

必须覆盖：run + N results + audit 一次提交；第 N 个 result 失败则三类数据全部回滚；相同幂等键查询到已有 ID；新 snapshot 生成新 run；旧 run 不变；按 Thesis 历史倒序；JSON 坏数据不静默；参数化查询可抵御包含引号的 fund code。

- [ ] **Step 2: 运行测试确认模块不存在**

```bash
.venv/bin/python -m pytest backend/tests/test_candidate_priority_repository.py -q
```

- [ ] **Step 3: 实现单连接事务类**

```python
class CandidatePriorityTransaction:
    def insert_run(self, run: Mapping[str, Any]) -> str: ...
    def insert_results(self, results: Sequence[Mapping[str, Any]]) -> list[str]: ...
    def insert_audit_log(self, **kwargs: Any) -> str: ...
    def get_existing_run_id(self, idempotency_key: PriorityRunKey) -> str | None: ...

class CandidatePriorityRepository:
    def transaction(self) -> CandidatePriorityTransaction: ...
    def get_run(self, priority_run_id: str) -> dict[str, Any] | None: ...
    def get_results(self, priority_run_id: str) -> list[dict[str, Any]]: ...
    def list_runs_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]: ...
```

Repository 只负责 SQL、JSON 和 row mapping；不判断档位，不生成原因码。

- [ ] **Step 4: 运行 Repository 测试**

```bash
.venv/bin/python -m pytest backend/tests/test_candidate_priority_repository.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 提交 Priority Repository**

```bash
git add backend/app/persistence/candidate_priority.py \
  backend/tests/test_candidate_priority_repository.py
git commit -m "feat: add atomic candidate priority repository"
```

## Task 7: 实现 CognitionGovernanceService 的 CandidateSet 创建

**Files:**

- Create: `backend/app/services/cognition_governance_service.py`
- Create: `backend/tests/test_cognition_governance_service.py`

- [ ] **Step 1: 写快照驱动和 structured_intent 边界测试**

测试必须证明：

- 缺 `direction/conviction/time_horizon/risk_tolerance` 任一字段返回领域 422 异常。
- `belief_link` 可空。
- 服务使用 snapshot 行中的 source/factor 路径，而不是 app 当前路径。
- snapshot 路径不存在抛 `CandidateDataSourceUnavailableError`。
- 自动 CandidateSet 只包含基金。
- 通过、估值观察、数据不足和明确点名但无持仓的基金都按设计纳入。
- 全市场无映射且未点名的基金只进入计数，不创建噪声行。
- 相同 Thesis/snapshot/source method 重试返回冲突及已有 `candidate_set_id`。
- 服务不更新 `research_inputs.structured_intent_json`。

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_governance_service.py -q
```

- [ ] **Step 3: 实现领域异常和 Engine factory**

```python
class ThesisNotFoundError(GovernanceError): ...
class CandidateSetNotFoundError(GovernanceError): ...
class StructuredIntentIncompleteError(GovernanceError): ...
class CandidateDataSourceUnavailableError(GovernanceError): ...
class DuplicateCandidateSetError(GovernanceError):
    def __init__(self, candidate_set_id: str) -> None:
        self.candidate_set_id = candidate_set_id
```

Engine factory 签名固定为 `Callable[[str, str | None], CognitionEngine]`，便于测试注入。生产实现从 snapshot 字段创建短生命周期 engine，并在 `finally` 中关闭。

- [ ] **Step 4: 实现 create_candidate_set()**

```python
def create_candidate_set(
    self,
    *,
    thesis_id: str,
    data_snapshot_id: str,
    actor_id: str,
    source_ip: str | None = None,
) -> dict[str, Any]: ...
```

流程严格为：读 Thesis -> 读 ResearchInput -> 校验 policy/snapshot 对齐 -> 校验 structured intent -> 用 snapshot 路径构建完整 evidence -> 在单事务写 header、候选和 audit。CandidateSet 中的 `fit_score` 使用真实目标权重，`candidate_evidence_json` 保存完整证据。

- [ ] **Step 5: 运行服务测试**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_governance_service.py -q
```

Expected: CandidateSet 链路全部通过。

- [ ] **Step 6: 提交 CandidateSet 编排**

```bash
git add backend/app/services/cognition_governance_service.py \
  backend/tests/test_cognition_governance_service.py
git commit -m "feat: build governed candidate sets from cognition"
```

## Task 8: 实现 PriorityRun 编排、幂等和失败审计

**Files:**

- Modify: `backend/app/services/cognition_governance_service.py`
- Modify: `backend/tests/test_cognition_governance_service.py`

- [ ] **Step 1: 写 PriorityRun 服务测试**

覆盖：策略/快照/Thesis/CandidateSet 不存在；集合属于其他 Thesis；集合快照与请求不一致；candidate evidence 缺失；策略 method version 不一致；重复幂等冲突携带已有 ID；所有候选排除时 `result_type=no_eligible_candidate` 且 HTTP 业务成功；计算异常只写失败 audit，不写 run；结果写入异常整套回滚。

- [ ] **Step 2: 运行测试确认缺少方法**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_governance_service.py -q
```

- [ ] **Step 3: 实现 create_priority_run()**

```python
def create_priority_run(
    self,
    *,
    thesis_id: str,
    candidate_set_id: str,
    data_snapshot_id: str,
    ranking_method_version: str,
    actor_id: str,
    source_ip: str | None = None,
) -> dict[str, Any]: ...
```

先在内存完成所有评价和档内排序，再开启写事务。`eligible_candidate_count` 统计 eligibility 为 `eligible` 的基金；只要存在任一 eligible，`result_type=ranked_candidates`，否则为 `no_eligible_candidate`。

失败审计使用独立短事务，仅记录：action、thesis/candidate set、policy/snapshot/method、actor、异常类型和稳定错误码；不得写原始持仓明细或敏感路径。

- [ ] **Step 4: 实现查询服务**

```python
def get_priority_run(self, priority_run_id: str) -> dict[str, Any] | None: ...
def list_priority_runs(self, thesis_id: str) -> list[dict[str, Any]]: ...
```

详情按固定五档分组，候选行同时返回原因码、人类说明、原始可解释指标和 `approved_for_production`，但不返回 `suggested_max_weight` 等组合建议字段。

- [ ] **Step 5: 运行完整服务测试**

```bash
.venv/bin/python -m pytest backend/tests/test_cognition_governance_service.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交 PriorityRun 服务**

```bash
git add backend/app/services/cognition_governance_service.py \
  backend/tests/test_cognition_governance_service.py
git commit -m "feat: orchestrate auditable fund priority runs"
```

## Task 9: 增加四个治理 API

**Files:**

- Modify: `backend/app/api/governance.py`
- Create: `backend/tests/test_api_candidate_priority.py`
- Modify: `backend/tests/test_api_governance.py`

- [ ] **Step 1: 写 API 契约测试**

覆盖四条路由：

```text
POST /v1/governance/theses/{thesis_id}/candidate-sets
POST /v1/governance/theses/{thesis_id}/candidate-priority-runs
GET  /v1/governance/candidate-priority-runs/{priority_run_id}
GET  /v1/governance/theses/{thesis_id}/candidate-priority-runs
```

断言 201/200 响应字段、409 detail 含 existing ID、422 structured intent/config、404 上游实体、503 snapshot 数据源、`no_eligible_candidate` 返回 201。

- [ ] **Step 2: 运行 API 测试确认 404 路由失败**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_api_candidate_priority.py \
  backend/tests/test_api_governance.py -q
```

- [ ] **Step 3: 增加 Pydantic request/response 模型**

```python
class CreateCandidateSetRequest(BaseModel):
    data_snapshot_id: str
    actor_id: str

class CreatePriorityRunRequest(BaseModel):
    candidate_set_id: str
    data_snapshot_id: str
    ranking_method_version: str
    actor_id: str
```

列表字段使用 `Field(default_factory=list)`，字典字段使用 `Field(default_factory=dict)`，避免可变默认值。

- [ ] **Step 4: 增加服务依赖和异常映射**

治理 DB 选择仍为 `output_db_path -> db_path -> source_db_path`。认知数据路径不从 app.state 直接取，而由服务按 `data_snapshot_id` 读取。

异常映射：

```text
Thesis/CandidateSet/Policy/Snapshot/PriorityRun not found -> 404
DuplicateCandidateSet/DuplicatePriorityRun             -> 409
Configuration/Intent/Consistency                       -> 422
CandidateDataSourceUnavailable                         -> 503
```

只信任现有 `_get_source_ip()` 的代理边界，不重新实现 XFF 解析。

- [ ] **Step 5: 实现路由并运行测试**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_api_candidate_priority.py \
  backend/tests/test_api_governance.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交 API**

```bash
git add backend/app/api/governance.py \
  backend/tests/test_api_candidate_priority.py \
  backend/tests/test_api_governance.py
git commit -m "feat: expose governed candidate priority APIs"
```

## Task 10: 扩展 smoke、真实 ID 报告和反查验收

**Files:**

- Modify: `scripts/p0/smoke_e2e_private_fund.py`
- Create: `backend/tests/test_smoke_candidate_priority.py`
- Modify: `backend/tests/test_smoke_persist.py`
- Modify: `docs/p0/phase0-acceptance.md`

- [ ] **Step 1: 写完整链路 smoke 测试**

测试第一次运行：

```text
ResearchInput -> Thesis -> Cognition evidence -> CandidateSet
-> CandidatePriorityRun -> CandidatePriorityResult -> API reverse lookup
```

测试第二次同 `run-id`：ResearchInput、Thesis、CandidateSet 和 PriorityRun 均不重复；报告仍引用第一次真实 ID。再用新 snapshot ID 运行，断言生成新 CandidateSet/PriorityRun，旧结果仍可查询。

- [ ] **Step 2: 运行 smoke 测试确认失败**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_smoke_candidate_priority.py \
  backend/tests/test_smoke_persist.py -q
```

- [ ] **Step 3: 扩展 --persist 流程**

smoke 必须调用 Service，不直接写 CandidateSet/PriorityRun SQL。运行报告展示：

- 真实 `research_input_id / thesis_id / candidate_set_id / priority_run_id`
- `strategy_policy_id + version`
- `data_snapshot_id`
- `ranking_method_version`
- 扫描、映射、数据无法映射、评价和 eligible 数量
- 五档计数
- 每只基金的档内排名、真实目标权重、披露权重、证据完成率和原因码
- `approved_for_production: false`

报告不得出现“推荐买入”“建议仓位”“预期收益”。

- [ ] **Step 4: 增加 API 反查验证**

smoke 使用 `TestClient` 或已启动 API 调用 GET 详情，核对：PriorityRun -> CandidateSet -> Thesis -> ResearchInput -> Policy -> Snapshot 全链 ID 与数据库一致。

- [ ] **Step 5: 运行 smoke 测试**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_smoke_candidate_priority.py \
  backend/tests/test_smoke_persist.py -q
```

Expected: 首次、重复、新快照和反查全部通过。

- [ ] **Step 6: 更新验收文档**

在 `phase0-acceptance.md` 新增独立的“阶段 1：基金候选优先级 v0”小节，记录实际命令和实际测试数；不得把阶段 0 的 539 条历史结果改写成当前结果。

- [ ] **Step 7: 提交 smoke 和验收**

```bash
git add scripts/p0/smoke_e2e_private_fund.py \
  backend/tests/test_smoke_candidate_priority.py \
  backend/tests/test_smoke_persist.py \
  docs/p0/phase0-acceptance.md
git commit -m "test: verify candidate priority end to end"
```

## Task 11: 全量回归、边界审计和阶段验收

**Files:**

- Review only: all changed files
- Modify only if verification reveals a defect in this feature's scope

- [ ] **Step 1: 运行候选优先级核心测试矩阵**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_candidate_priority_engine.py \
  backend/tests/test_holding_source_adapter.py \
  backend/tests/test_candidate_priority_migrations.py \
  backend/tests/test_candidate_priority_repository.py \
  backend/tests/test_cognition_governance_service.py \
  backend/tests/test_api_candidate_priority.py \
  backend/tests/test_smoke_candidate_priority.py -q
```

Expected: 0 failed。

- [ ] **Step 2: 运行治理与认知邻接回归**

```bash
.venv/bin/python -m pytest \
  backend/tests/test_governance_migrations.py \
  backend/tests/test_governance_repository.py \
  backend/tests/test_governance_service.py \
  backend/tests/test_api_governance.py \
  backend/tests/test_cognition_engine.py \
  backend/tests/test_smoke_persist.py -q
```

Expected: 0 failed。

- [ ] **Step 3: 运行全量后端测试**

```bash
.venv/bin/python -m pytest backend/tests -q
```

Expected: 0 failed；记录实际 passed/skipped 数，不预写数字。

- [ ] **Step 4: 运行 lint 和 diff 检查**

```bash
.venv/bin/python -m ruff check backend/app backend/tests \
  scripts/p0/smoke_e2e_private_fund.py scripts/sync_strategy_policies.py
git diff --check
```

Expected: 两条命令均退出 0。

- [ ] **Step 5: 做产品边界扫描**

```bash
rg -n '推荐买入|建议买入|建议仓位|自动调仓|预测收益|综合总分|total_score' \
  backend/app/services/candidate_priority.py \
  backend/app/services/cognition_governance_service.py \
  backend/app/api/governance.py \
  scripts/p0/smoke_e2e_private_fund.py
```

Expected: 无输出；若原因说明中必须提及边界，只允许“本结果不是买入建议”这种否定性文案。

- [ ] **Step 6: 做 schema 和类型一致性审计**

人工逐项核对：

- 所有权重持久化为 `0..1`，只有展示层可转百分比。
- `matched_holding_weight` 与 `normalized_match_pct` 未混用。
- PriorityResult 五档互斥且穷尽。
- `data_insufficient/excluded` 无正式档内排名。
- 原因码来自固定字典，不由大模型自由生成。
- snapshot 路径来自 `data_snapshots`。
- CandidateSet evidence、PriorityResult 均不可变。
- 重复幂等请求返回已有 ID，不伪装成新创建。
- 新快照产生新历史，旧结果不覆盖。

- [ ] **Step 7: 最终提交（仅在前面修复产生未提交变更时）**

```bash
git status --short
git add <本阶段验证修复涉及的明确文件>
git commit -m "fix: close candidate priority acceptance gaps"
```

`<本阶段验证修复涉及的明确文件>` 不能直接复制执行；执行者必须把它替换为本任务实际修复的文件列表，禁止 `git add .`，避免带入用户的其他未提交改动。

## 3. API 完成后的前端边界

本批结束时，网页版仍不会自动变成机构级研究工作台，这是有意边界，而不是遗漏。后续前端批次应只消费已经冻结的 API 契约，优先建设一个页面：**投资假设详情 / 基金研究优先级**。

该页面后续应包含：

- 顶部：Thesis、Policy version、Snapshot、Method version、是否生产批准。
- 主区：五档泳道或分组表，不显示跨档总排名。
- 候选行：真实目标持仓、披露覆盖、估值状态、数据质量、档内排名。
- 侧栏：原因码、证据来源、持仓穿透和历史 PriorityRun 对比。
- 明确文案：这是研究顺序，不是买入建议。

前端设计开始条件：本计划 Task 9 的 API 契约和 Task 10 的真实 smoke 结果均已通过。条件未满足前，不应先画一个依赖模拟数据的“高级客户端”。

## 4. 最终完成定义

只有以下事实同时成立，才可以宣布 v0 完成：

1. 同一结构化 ResearchInput 可以生成快照化 CandidateSet。
2. CandidateSet 持久保存完整 FundCandidateEvidence，独立 API 调用之间不丢证据。
3. 同一 Thesis 在新 Snapshot 下可生成新集合，旧集合仍可查询。
4. 每只基金严格进入五档之一，并保留稳定原因码和原始维度。
5. 同档排序稳定，不存在跨档总分。
6. PriorityRun/Result 与 audit 原子提交，Result 不可更新或删除。
7. 同幂等键返回 409 和已有 ID；新快照产生新 Run。
8. 全部候选不可用时返回成功的 `no_eligible_candidate`。
9. API 可反查 ResearchInput、Thesis、CandidateSet、Policy、Snapshot 和 Method version。
10. 全量测试、ruff、`git diff --check` 全部通过。
11. 输出不包含买入建议、组合权重、自动调仓或收益预测。
12. 当前批次未用前端包装掩盖后端证据和治理缺口。
