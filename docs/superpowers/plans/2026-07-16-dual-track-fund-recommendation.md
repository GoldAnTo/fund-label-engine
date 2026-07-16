# 双轨基金推荐与组合输出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对每个 Thesis 分别推荐主动基金和 ETF/指数基金，并且只用推荐池构建默认混合组合。

**Architecture:** CandidateSet 保存全量相关基金；RecommendationRun 基于冻结证据执行主题优先、主动/ETF 分开的规则排序；PortfolioProposal 只能消费推荐和备选结果，再复用现有风险裁决。CandidatePriorityRun 继续只回答先研究什么。

**Tech Stack:** Python、FastAPI、Pydantic、SQLite migrations、Cognition/Governance services、React、TypeScript、pytest、Playwright。

---

## File map

| 文件 | 责任 |
|---|---|
| `config/strategy_policy/private_equity_growth_v1.yaml` | 推荐规则、阈值和权重。 |
| `backend/app/persistence/migrations/0018_fund_recommendation.sql` | 推荐 run/result 表及不可变约束。 |
| `backend/app/services/fund_recommendation.py` | 产品分类、门槛、评分、分榜单排序。 |
| `backend/app/persistence/fund_recommendation.py` | 推荐结果原子读写。 |
| `backend/app/services/cognition_governance_service.py` | 治理校验与推荐运行编排。 |
| `backend/app/api/governance.py`、`backend/app/main.py` | API 和认知自动链路。 |
| `backend/app/cognition/portfolio_builder.py` | 限制组合只使用推荐池。 |
| `frontend/src/api.ts`、`frontend/src/pages/FundRecommendationPage.tsx`、`frontend/src/App.tsx` | 双榜单和组合解释页面。 |

### Task 1: 版本化推荐政策与不可变数据库模型

**Files:**
- Modify: `config/strategy_policy/private_equity_growth_v1.yaml`
- Create: `backend/app/persistence/migrations/0018_fund_recommendation.sql`
- Modify: YAML 同步策略中当前处理 `candidate_priority_json` 的文件（先执行 `rg -n 'candidate_priority_json' backend scripts`）
- Test: `backend/tests/test_candidate_priority_migrations.py`

- [ ] **Step 1: 写失败 migration 测试**

```python
def test_recommendation_results_are_immutable(conn_with_policies):
    tables = {r[0] for r in conn_with_policies.execute(
        'SELECT name FROM sqlite_master WHERE type=\'table\''
    )}
    assert {'fund_recommendation_runs', 'fund_recommendation_results'} <= tables
    insert_recommendation_run_and_result(conn_with_policies)
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        conn_with_policies.execute(
            'UPDATE fund_recommendation_results SET total_score = 0'
        )
```

- [ ] **Step 2: 确认失败**

Run: `cd backend && python -m pytest tests/test_candidate_priority_migrations.py -k recommendation -v`

- [ ] **Step 3: 加入 YAML 和 migration**

```yaml
fund_recommendation:
  method_version: fund_recommendation_v1
  source_method_version: fund_candidate_evidence_v0
  minimum_target_holding_weight: 0.03
  maximum_holding_age_days: 180
  active_fund_limit: 3
  etf_or_index_limit: 3
  alternative_limit: 2
  weights:
    theme_exposure: 0.55
    thesis_alignment: 0.15
    risk_return: 0.15
    fund_quality: 0.15
```

Migration 给 `strategy_policies` 加 `fund_recommendation_json`，创建 `fund_recommendation_runs` 和 `fund_recommendation_results`。run 外键引用 CandidateSet、Thesis、ResearchInput、策略版本和快照；唯一键为 CandidateSet/策略版本/快照/方法版本。result 保存类别、档位、类内排名、四个分项、总分、理由、排除理由和冻结证据 JSON；UPDATE/DELETE 触发器报错必须含 `immutable`。同步器读写新 JSON。

- [ ] **Step 4: 验证并提交**

Run: `cd backend && python -m pytest tests/test_candidate_priority_migrations.py -k 'recommendation or policy' -v`

```bash
git add config/strategy_policy/private_equity_growth_v1.yaml scripts/sync_strategy_policies.py backend/app/persistence/migrations/0018_fund_recommendation.sql backend/tests/test_candidate_priority_migrations.py
git commit -m 'feat: add immutable fund recommendation schema'
```

### Task 2: 主题优先的主动/ETF 双轨推荐引擎

**Files:**
- Create: `backend/app/services/fund_recommendation.py`
- Test: `backend/tests/test_fund_recommendation.py`

- [ ] **Step 1: 写失败规则测试**

```python
def test_active_and_etf_rankings_are_independent():
    results = FundRecommendationEngine().evaluate_all(
        [active('A', exposure=.40), etf('E', exposure=.35), active('B', exposure=.30)],
        policy(),
    )
    assert by_code(results, 'A').category_rank == 1
    assert by_code(results, 'E').category_rank == 1

def test_low_exposure_never_becomes_recommended():
    result = evaluate(active('A', exposure=.02, quality=1), policy(minimum=.03))
    assert result.recommendation_tier == 'excluded'
    assert 'target_exposure_below_minimum' in result.exclusion_codes

def test_theme_exposure_has_largest_weight():
    results = evaluate_all([active('A', exposure=.50), active('B', exposure=.35, quality=1)], policy())
    assert by_code(results, 'A').category_rank == 1
```

补充测试：持仓缺失或过期为 `data_insufficient`；产品类别未知为 `unsupported` 且不可推荐；每类最多 3 个 `recommended` 和 2 个 `alternative`；同分按基金代码稳定排序。

- [ ] **Step 2: 确认失败**

Run: `cd backend && python -m pytest tests/test_fund_recommendation.py -v`

- [ ] **Step 3: 实现纯规则引擎**

创建 `FundRecommendationPolicy`、`RecommendationReason`、`FundRecommendationResult`、`FundRecommendationEngine`。复用 `FundCandidateEvidence`，但产品类别必须来自可靠元数据，不能按名称猜测。规则顺序固定为：类别识别、数据新鲜度、最低主题暴露、硬冲突、评分、类内分档。

```python
total_score = (
    theme_exposure_score * .55
    + thesis_alignment_score * .15
    + risk_return_score * .15
    + fund_quality_score * .15
)
```

主动基金质量看经理稳定性、规模、费率、持仓稳定性；ETF/指数基金看指数主题纯度、费率、规模流动性、跟踪质量。缺失不可得满分或被解释为低风险；理由使用稳定 code。

- [ ] **Step 4: 验证并提交**

Run: `cd backend && python -m pytest tests/test_fund_recommendation.py -v`

```bash
git add backend/app/services/fund_recommendation.py backend/tests/test_fund_recommendation.py
git commit -m 'feat: rank active funds and ETFs separately'
```

### Task 3: 推荐运行持久化与治理服务

**Files:**
- Create: `backend/app/persistence/fund_recommendation.py`
- Modify: `backend/app/services/cognition_governance_service.py`
- Test: `backend/tests/test_cognition_governance_service.py`

- [ ] **Step 1: 写失败服务测试**

```python
def test_create_recommendation_run_writes_two_category_results(service, ids):
    created = service.create_recommendation_run(
        thesis_id=ids.thesis_id, candidate_set_id=ids.candidate_set_id,
        data_snapshot_id=ids.snapshot_id,
        recommendation_method_version='fund_recommendation_v1', actor_id='researcher_1',
    )
    detail = service.get_recommendation_run(created['recommendation_run_id'])
    assert set(detail['candidates_by_category']) == {'active_fund', 'etf_or_index'}
    assert all(x['recommendation_tier'] in {'recommended', 'alternative'}
               for x in detail['recommended_universe'])

def test_duplicate_recommendation_run_returns_existing_id(service, ids):
    kwargs = {
        'thesis_id': ids.thesis_id, 'candidate_set_id': ids.candidate_set_id,
        'data_snapshot_id': ids.snapshot_id,
        'recommendation_method_version': 'fund_recommendation_v1',
        'actor_id': 'researcher_1',
    }
    service.create_recommendation_run(**kwargs)
    with pytest.raises(DuplicateRecommendationRunError) as exc:
        service.create_recommendation_run(**kwargs)
    assert exc.value.recommendation_run_id.startswith('frr_')
```

另测：引用不一致拒绝；result 插入失败时 run/result/audit 全回滚。

- [ ] **Step 2: 确认失败**

Run: `cd backend && python -m pytest tests/test_cognition_governance_service.py -k recommendation -v`

- [ ] **Step 3: 实现 repository 和服务方法**

仿照 `CandidatePriorityRepository` 新建 `FundRecommendationRepository`，提供 `transaction`、`get_run`、`get_results`、`list_runs_by_thesis`、`get_existing_run_id`。在 `CognitionGovernanceService` 添加 `create_recommendation_run`、`get_recommendation_run`、`list_recommendation_runs`、`DuplicateRecommendationRunError`。复用 CandidateSet 的 `candidate_evidence_json`，不重新扫描；run、results、`audit_log(action='create_recommendation_run')` 同一事务写入。详情必须固定返回两个类别、各五个档位，和只由 `recommended`/`alternative` 构成的 `recommended_universe`。

- [ ] **Step 4: 验证并提交**

Run: `cd backend && python -m pytest tests/test_cognition_governance_service.py tests/test_fund_recommendation.py -v`

```bash
git add backend/app/persistence/fund_recommendation.py backend/app/services/cognition_governance_service.py backend/tests/test_cognition_governance_service.py
git commit -m 'feat: persist auditable fund recommendation runs'
```

### Task 4: 治理 API 与自动认知链路

**Files:**
- Modify: `backend/app/api/governance.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_fund_recommendation.py`
- Modify: `backend/tests/test_thesis_persistence.py`

- [ ] **Step 1: 写失败 API 测试**

```python
def test_create_and_read_recommendation_run(client, ids):
    res = client.post(f'/v1/governance/theses/{ids.thesis_id}/fund-recommendation-runs', json={
        'candidate_set_id': ids.candidate_set_id, 'data_snapshot_id': ids.snapshot_id,
        'recommendation_method_version': 'fund_recommendation_v1', 'actor_id': 'researcher_1',
    })
    assert res.status_code == 201
    assert client.get(f'/v1/governance/fund-recommendation-runs/{res.json()["recommendation_run_id"]}').status_code == 200

def test_cognition_result_references_persisted_recommendation_run(tmp_path):
    result = run_cognition_with_persisted_thesis(tmp_path)
    assert result['step0_thesis']['recommendation_run_id'].startswith('frr_')
```

- [ ] **Step 2: 确认失败**

Run: `cd backend && python -m pytest tests/test_api_fund_recommendation.py tests/test_thesis_persistence.py -k recommendation -v`

- [ ] **Step 3: 实现 API 与自动调用**

新增：`POST /v1/governance/theses/{thesis_id}/fund-recommendation-runs`、`GET /v1/governance/fund-recommendation-runs/{recommendation_run_id}`、`GET /v1/governance/theses/{thesis_id}/fund-recommendation-runs`。404 用于不存在引用，409 用于幂等冲突且 detail 含已有 ID，422 用于策略或方法版本不一致。`main.py` 在 `_persist_thesis`、`_create_candidate_set` 后调用 `_create_recommendation_run`；成功同步 ID 至 `step0_thesis`、`thesis_tracker`、`step5_portfolio`。失败只能标记 `recommendation_persistence_status='degraded'` 和错误信息，不能伪装成审计结果。

- [ ] **Step 4: 验证并提交**

Run: `cd backend && python -m pytest tests/test_api_fund_recommendation.py tests/test_thesis_persistence.py -v`

```bash
git add backend/app/api/governance.py backend/app/main.py backend/tests/test_api_fund_recommendation.py backend/tests/test_thesis_persistence.py
git commit -m 'feat: expose fund recommendation governance API'
```

### Task 5: 将组合输入限制为推荐池

**Files:**
- Modify: `backend/app/cognition/portfolio_builder.py`
- Modify: `backend/app/cognition/engine.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cognition_engine.py`

- [ ] **Step 1: 写失败组合来源测试**

```python
def test_portfolio_never_allocates_outside_recommended_universe():
    proposal = build_portfolio(
        recommended_candidates=[recommended('A'), alternative('B')],
        defense_fund=None, recommendation_run_ids=['frr_1'],
    )
    assert {p['fund_code'] for p in proposal['holdings']} <= {'A', 'B'}
    assert proposal['selection_source'] == 'recommended_universe'

def test_empty_recommendation_universe_is_not_fake_portfolio():
    proposal = build_portfolio([], defense_fund=None, recommendation_run_ids=['frr_1'])
    assert proposal['status'] == 'insufficient_recommendations'
    assert proposal['holdings'] == []
```

- [ ] **Step 2: 确认失败**

Run: `cd backend && python -m pytest tests/test_cognition_engine.py -k recommended_universe -v`

- [ ] **Step 3: 实现输入契约**

`build_portfolio` 和 `optimize_portfolio` 接收 `recommended_candidates`、`recommendation_run_ids`，删除推荐池为空时回退全量 CandidateSet 的分支。

```python
{
  'status': 'complete' | 'insufficient_recommendations',
  'selection_source': 'recommended_universe',
  'recommendation_run_ids': ['frr_0123456789ab'],
  'holdings': [], 'enforced_actions': [], 'metrics': {}, 'risk_review': {},
}
```

保留已有去重、重叠、行业、波动、回撤裁决及调权后重算；只有 `complete` 才归一化权重。

- [ ] **Step 4: 验证并提交**

Run: `cd backend && python -m pytest tests/test_cognition_engine.py tests/test_thesis_persistence.py -v`

```bash
git add backend/app/cognition/portfolio_builder.py backend/app/cognition/engine.py backend/app/main.py backend/tests/test_cognition_engine.py
git commit -m 'feat: build portfolios from recommended funds only'
```

### Task 6: 双榜单和组合解释 UI

**Files:**
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/pages/FundRecommendationPage.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/e2e/fund-recommendation.spec.ts`

- [ ] **Step 1: 写失败浏览器测试**

```ts
test('shows separate fund lists before the final portfolio', async ({ page }) => {
  await page.goto('/recommendations?run=frr_fixture')
  await expect(page.getByRole('heading', { name: '主题基金推荐' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '主动基金推荐' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'ETF / 指数基金推荐' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '最终组合建议' })).toBeVisible()
  await expect(page.getByText('主题暴露纯度')).toBeVisible()
})
```

- [ ] **Step 2: 确认失败**

Run: `cd frontend && npx playwright test e2e/fund-recommendation.spec.ts`

- [ ] **Step 3: 实现页面**

在 `api.ts` 增加类型和读取函数。页面阅读顺序固定：Thesis/快照/运行 ID → 主动基金榜单 → ETF/指数基金榜单 → 单基金四项评分、三条以内理由、未选原因、证据日期 → 最终组合。组合区只在 `selection_source='recommended_universe'` 时展示，并显示风险强制调权和更新后的指标。空榜单必须说明没有满足主题暴露和数据门槛的基金；不加入审批控件、收益保证或买卖指令。

- [ ] **Step 4: 构建、e2e、提交**

Run: `cd frontend && npm run build && npx playwright test e2e/fund-recommendation.spec.ts`

```bash
git add frontend/src/api.ts frontend/src/pages/FundRecommendationPage.tsx frontend/src/App.tsx frontend/e2e/fund-recommendation.spec.ts
git commit -m 'feat: show separate active and ETF fund recommendations'
```

### Task 7: 全链路 smoke、文档和最终验证

**Files:**
- Modify: `backend/tests/test_smoke_persist.py`
- Modify: `docs/cognition-driven-fund-engine-design.md`
- Modify: `docs/walkthrough-style-overview-2026-07-06.md`

- [ ] **Step 1: 扩展 smoke 断言**

```python
assert result['step0_thesis']['recommendation_run_id'].startswith('frr_')
assert result['step5_portfolio']['selection_source'] == 'recommended_universe'
assert result['step5_portfolio']['recommendation_run_ids']
```

- [ ] **Step 2: 更新文档**

明确 CandidateSet 是候选、PriorityRun 是研究顺序、RecommendationRun 才是选基、PortfolioProposal 只能消费推荐池；记录主动/ETF 分榜和默认混合组合。

- [ ] **Step 3: 完整验证**

```bash
cd backend && python -m pytest -q
cd ../frontend && npm run build && npx playwright test
```

若 smoke 重新生成 `reports/p0/smoke-e2e-report.md`，将其视为测试副作用，不混入功能提交。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_smoke_persist.py docs/cognition-driven-fund-engine-design.md docs/walkthrough-style-overview-2026-07-06.md
git commit -m 'docs: explain dual-track fund recommendation flow'
```

## Plan self-review

- 覆盖：任务 1-4 实现可审计推荐，任务 5 收紧组合来源，任务 6 呈现用户结果，任务 7 验证契约与文档。
- 边界：不新增审批流、预测模型、自动交易；不把 CandidatePriorityRun 混同为推荐。
- 一致性：ID 前缀 `frr_`；档位为 `recommended/alternative/watch/excluded/data_insufficient`；组合来源固定为 `recommended_universe`。
