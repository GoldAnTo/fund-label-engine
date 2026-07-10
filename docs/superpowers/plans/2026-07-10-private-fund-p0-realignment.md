# 私募 P0 业务重定位与投研决策系统实施计划

> For agentic workers: Use the task execution skill to implement this plan task-by-task. Steps use checkbox syntax.
>
> Goal：将当前基金标签与认知选基项目重定位为“私募内部投研与组合决策系统”，先完成可追溯的研究请求、投资假设、候选集合和最小决策闭环，再扩展 FOF、组合风险、投决和投后归因。
>
> Architecture：保留现有数据门禁、标签、基准、持仓穿透和 CognitionEngine，新增治理核心层承接 ResearchInput、InvestmentThesis、CandidateSet 和最小 DecisionRecord。StrategyPolicy 先以版本化 YAML 作为输入，结果必须绑定政策版本、数据快照、引擎版本和规则版本。组合、投决会、监控和归因按阶段逐层接入，不在第一阶段建设自动交易和客户适当性。
>
> Tech Stack：Python 3、FastAPI、SQLite migrations、现有 CognitionEngine、React、TypeScript、Vite、现有前端设计系统；组合风险阶段评估 skfolio / Riskfolio-Lib，不在 P0 直接强绑定。

---

## 1. 目标产品和业务边界

### 1.1 默认业务模式

默认采用 private_strategy：

    ResearchInput
    → InvestmentThesis
    → 股票/行业/基金/策略候选
    → 估值与风险证据
    → CandidateSet
    → 最小 DecisionRecord

FOF / 母基金采用 fof 扩展模式：

    ResearchInput
    → 外部基金/管理人尽调
    → 基金候选集合
    → FOF 组合提案

阶段 0 和阶段 1 只选一个真实主业务模式作为默认演示。另一模式只保留字段和策略样例，不同时建设两套完整流程。

### 1.2 本计划包含

- P0 业务定位和领域语言。
- 快照和复现边界。
- 私募策略政策样例。
- ResearchInput 落库。
- InvestmentThesis 落库。
- CandidateSet 落库。
- 无候选和排除原因。
- 最小 DecisionRecord。
- 研究请求和结果前端页面。
- 阶段 0 三类演示。
- 阶段 1 测试和验收。

### 1.3 本计划不包含

- 自动交易、券商连接和订单管理。
- 客户适当性、销售和财富管理。
- 大模型自动产生投资观点。
- 以历史收益承诺未来收益。
- 多产品完整聚合，放到阶段 2。
- 多人投票、复杂审批和权限平台，放到阶段 3/5。
- 立即扩展到全市场所有资产。
- 用固定候选数量判断系统成功。

## 2. 当前已完成的 P0 文档调整

本轮文档调整完成以下方向修正：

- README 主业务从 FOF / 母基金改为私募内部投研与组合决策，FOF 为扩展。
- business-scope 将用户场景改为内部研究请求，并允许股票、行业、基金、管理人、策略和产品作为候选对象。
- domain-language 保留技术字段 user_input_id，但业务名统一为 ResearchInput，增加 actor_role、request_source、business_mode 和策略政策版本。
- roles 改为研究员、投资经理、投决会、风控、产品运营和系统管理员边界。
- CandidateSet 区分 candidate_set_id 和 candidate_id。
- StrategyPolicy 统一 business_mode、strategy_policy_id 和 strategy_policy_version。
- DecisionRecord 最小版本提前到阶段 1，完整投决会继续放到阶段 3。
- 新增私募主观权益策略样例。
- 新增快照架构和阶段 0 验收文档。

## 3. 重要架构决策

### 3.1 研究输入不是客户账户

技术上保留 user_input_id 以避免一次性迁移，业务上使用 ResearchInput。ResearchInput 必须记录：

    actor_role
    request_source
    business_mode
    strategy_policy_id
    strategy_policy_version
    raw_text
    data_snapshot_id
    created_at

### 3.2 投资观点和结构化解析分离

raw_text 不可修改。结构化解析如果发生变化，新增输入版本或新增 thesis，不原地覆盖历史结果。

### 3.3 候选数量不是成功标准

候选结果可以为零。成功标准是：

    有候选：有证据、有估值状态、有数据日期、有排除理由
    无候选：有 no_eligible_candidate、有门禁原因、有下一步动作

### 3.4 策略政策和计算逻辑分离

阈值、投资范围、监控政策和仓位边界不能继续散落在 Python 常量、YAML 关键词和前端文案中。P0 先统一 YAML 字段和版本，阶段 1 再决定是否进入数据库。

### 3.5 先决策可追溯，再做组合优化

组合优化库只能根据研究候选和策略政策计算权重，不能替代投资假设、证据判断和投决理由。

## 4. 改造规模判断

| 改造项 | 规模 | 原因 | 处理阶段 |
|---|---:|---|---|
| P0 业务定位和领域语言 | 中 | 需要统一已有文档和字段含义 | 立即 |
| ResearchInput / Thesis / CandidateSet 落库 | 大 | 新增 migration、repository、service、API 和测试 | 阶段 1 |
| StrategyPolicy 注册和版本 | 中 | 先从 YAML 校验和版本绑定开始 | 阶段 1 |
| 前端研究请求入口 | 中 | 当前 CognitionPage 直接跑分析，未形成研究任务 | 阶段 1 |
| 最小 DecisionRecord | 中 | 需要绑定候选、政策、快照和理由 | 阶段 1 |
| 多产品组合聚合 | 大 | 需要产品、账户、组合和穿透关系 | 阶段 2 |
| 风险预算和压力测试 | 大 | 需要完整历史收益、因子和组合约束 | 阶段 2 |
| 正式投决会 | 大 | 需要角色权限、多人意见、审批和不可变记录 | 阶段 3 |
| 投后归因和研究复盘 | 大 | 需要决策结果、持仓变化和时间序列 | 阶段 3 |
| 客户和企业化平台 | 很大 | 权限、租户、数据授权、SLA 和安全 | 阶段 5 |

## 5. 阶段 1 实施任务

### Task 1：冻结 P0 业务输入和策略样例

Files：

- Modify：docs/p0/README.md
- Modify：docs/p0/business-scope.md
- Modify：docs/p0/domain-language-v0.md
- Modify：docs/p0/roles.md
- Create：config/strategy_policy/private_equity_growth_v0.yaml
- Keep as extension：config/strategy_policy/foof_growth_v0.yaml
- Test：docs/p0/phase0-acceptance.md

- [ ] Step 1：确认默认 business_mode 为 private_strategy 或 fof。
- [ ] Step 2：确认 StrategyPolicy 字段名称为 policy_id、version、business_mode、strategy_type。
- [ ] Step 3：确认 InvestmentThesis 只引用 strategy_policy_id 和 strategy_policy_version。
- [ ] Step 4：确认 CandidateSet 分成集合 ID 和单个候选 ID。
- [ ] Step 5：确认所有样例政策标记为 policy_status=example、approved_for_production=false。
- [ ] Step 6：通过文档检查后冻结 P0 领域语言，不在代码中重复创建第二套实体命名。

验证命令：

    rg -n "strategy_id|policy_version|候选至少|至少 3|阶段 3.*DecisionRecord" docs/p0
    git diff --check

预期：

- 只剩下明确的历史说明或迁移说明。
- 不再存在阶段 0 强制固定数量候选。
- 不再存在阶段 1 完全不记录决策的表述。

### Task 2：建立快照和复现元数据契约

Files：

- Modify：backend/app/persistence/migrations/0011_data_snapshots.sql
- Modify：backend/app/persistence/reader.py
- Modify：backend/app/persistence/writer.py
- Create：backend/tests/test_snapshot_reproducibility.py
- Modify：docs/p0/snapshot-architecture.md

- [ ] Step 1：写测试，创建一个数据快照并保存 source manifest、as_of_date、engine_version 和 rule_version。
- [ ] Step 2：运行测试，确认当前实现缺少治理字段时失败。
- [ ] Step 3：添加最小 schema 字段，保持老数据库迁移兼容。
- [ ] Step 4：实现 snapshot writer 和 reader 的读写方法。
- [ ] Step 5：让研究结果引用 data_snapshot_id、run_id、engine_version 和 rule_version。
- [ ] Step 6：增加缺少任一复现键时的明确错误状态。
- [ ] Step 7：运行快照测试和原有 persistence 测试。

验收：

- 可以用同一快照重新生成同一输入的研究结果。
- 快照不存在、数据源变化和版本不匹配均有不同错误原因。
- 不复制整个 SQLite 数据库到 Git。

### Task 3：建立治理核心表和领域服务

Files：

- Create：backend/app/persistence/migrations/0015_governance_core.sql
- Create：backend/app/governance/__init__.py
- Create：backend/app/governance/models.py
- Create：backend/app/governance/repository.py
- Create：backend/app/governance/service.py
- Test：backend/tests/test_governance_core.py

- [ ] Step 1：写失败测试，验证 raw_text、strategy_policy_version、data_snapshot_id 和 actor_role 必须存在。
- [ ] Step 2：写失败测试，验证 raw_text 不可原地修改。
- [ ] Step 3：写失败测试，验证 thesis、candidate_set 和 decision_record 都能反查 research_input_id。
- [ ] Step 4：创建 user_input 表。

字段：

    user_input_id TEXT PRIMARY KEY
    input_type TEXT NOT NULL
    raw_text TEXT NOT NULL
    business_mode TEXT NOT NULL
    actor_role TEXT NOT NULL
    request_source TEXT NOT NULL
    strategy_policy_id TEXT NOT NULL
    strategy_policy_version INTEGER NOT NULL
    data_snapshot_id TEXT NOT NULL
    session_id TEXT
    previous_user_input_id TEXT
    status TEXT NOT NULL
    created_at TEXT NOT NULL

- [ ] Step 5：创建 investment_thesis 表，保存 belief_statement、supporting_evidence、opposing_evidence、key_metrics、invalidation_conditions、owner、status 和 next_review_at。
- [ ] Step 6：创建 candidate_sets 和 candidates 表，明确集合与单个候选的 1:N 关系。
- [ ] Step 7：创建最小 decision_records 表，保存 candidate_set_id、policy version、data snapshot、decision status 和 reason。
- [ ] Step 8：实现以下 service 方法：

    create_research_input(payload)
    get_research_input(input_id)
    create_thesis(input_id, payload)
    create_candidate_set(thesis_id, candidates)
    record_minimal_decision(candidate_set_id, payload)

- [ ] Step 9：对所有不可变对象使用新增版本或新增记录，不使用 UPDATE 覆盖历史。
- [ ] Step 10：运行 governance 测试、migration 测试和全量后端测试。

验收：

- 原始输入可追溯。
- 历史假设和候选不可被静默覆盖。
- 最小决策可以记录 approved、rejected、watching 和 pending_data。
- 所有结果能反查策略政策和数据快照。

### Task 4：增加 ResearchInput API

Files：

- Modify：backend/app/main.py
- Create：backend/app/governance/api.py
- Test：backend/tests/test_governance_api.py

API：

    POST /v1/research/inputs
    GET /v1/research/inputs/{input_id}
    GET /v1/research/inputs/{input_id}/result
    POST /v1/research/inputs/{input_id}/thesis
    POST /v1/research/candidate-sets/{candidate_set_id}/decision

请求模型 ResearchInputRequest：

    input_type
    raw_text
    business_mode
    strategy_policy_id
    strategy_policy_version
    actor_role
    request_source
    data_snapshot_id
    target_assets

- [ ] Step 1：写 API 失败测试，缺少 raw_text、policy version 或 snapshot 时返回 422。
- [ ] Step 2：写 API 失败测试，未知 policy_id 或 snapshot_id 返回业务化错误。
- [ ] Step 3：实现 POST /v1/research/inputs，只落库和返回 input_id，不在没有明确分析动作时自动生成候选。
- [ ] Step 4：实现 GET /v1/research/inputs/{input_id}，返回原始输入和当前状态。
- [ ] Step 5：实现显式分析动作，将现有 CognitionEngine 结果写入 thesis 和 candidate_set。
- [ ] Step 6：实现最小决策接口，限制状态转换并写 audit_log。
- [ ] Step 7：运行 API 测试和现有 cognition API 测试。

验收：

- 创建输入不会自动产生候选。
- 用户点击或调用显式分析动作后才生成候选。
- API 不把原始异常暴露成 500。
- 返回中包含 input_id、thesis_id、candidate_set_id 和 snapshot_id。

### Task 5：将现有 CognitionEngine 接入治理服务

Files：

- Modify：backend/app/cognition/engine.py
- Modify：backend/app/cognition/input.py
- Create：backend/tests/test_cognition_governance_bridge.py
- Modify：config/strategy_policy/private_equity_growth_v0.yaml

- [ ] Step 1：写失败测试，验证 engine 结果可以映射为 InvestmentThesis。
- [ ] Step 2：写失败测试，验证每个候选都有 match、valuation、data quality、exclusion reasons。
- [ ] Step 3：写失败测试，验证没有通过门禁的候选返回 no_eligible_candidate，而不是默认组合。
- [ ] Step 4：增加 business_mode 和 strategy policy 作为显式输入。
- [ ] Step 5：保留现有七步认知计算，不重新写第二个标签引擎。
- [ ] Step 6：将结果拆成 supporting evidence、opposing evidence、pending evidence。
- [ ] Step 7：将候选状态标准化为 continue_research、valuation_watch、data_insufficient、excluded、no_eligible_candidate。
- [ ] Step 8：运行 cognition_engine 全量测试和治理桥接测试。

专业建议：

- belief_note 不能只停留在前端展示，阶段 1 应保存为 belief_statement 或 thesis source。
- 结构化解析可以先采用主题、行业、股票和策略政策的确定性映射，不要在 P0 宣称具备完整 NLU。
- 任何 LLM 解析结果都必须保留原文、解析版本和人工确认状态。

### Task 6：建设研究请求和结果前端

Files：

- Modify：frontend/src/App.tsx
- Create：frontend/src/pages/ResearchInputPage.tsx
- Create：frontend/src/pages/ResearchInputResultPage.tsx
- Create：frontend/src/components/ResearchInputComponents.tsx
- Modify：frontend/src/api.ts
- Modify：frontend/src/styles.css
- Test：frontend/e2e/private-research-input.spec.ts

页面：

    /inputs
    /inputs/:id

- [ ] Step 1：写 E2E 失败测试，访问 /inputs 能看到研究请求入口。
- [ ] Step 2：写 E2E 失败测试，提交观点后得到 input_id，不自动显示候选。
- [ ] Step 3：写 E2E 失败测试，点击“开始分析”后显示证据和候选。
- [ ] Step 4：实现业务模式和策略政策选择。
- [ ] Step 5：实现 raw_text、input_type、actor_role 和 request_source 输入。
- [ ] Step 6：实现结果页：研究简报、支持/反向证据、候选、排除原因、数据状态。
- [ ] Step 7：无候选时显示无候选状态，不出现“推荐”或默认组合语义。
- [ ] Step 8：研究候选页面增加“进入组合提案”按钮，但阶段 1 只生成草案，不批准组合。
- [ ] Step 9：将当前 CognitionPage 作为分析组件或兼容入口，不立即删除。
- [ ] Step 10：为表单补齐 label、focus-visible、aria-live、键盘操作和 URL 状态。
- [ ] Step 11：运行 TypeScript、Vite build 和 E2E。

验收：

- 研究请求是一级对象，不是一次不可追踪的按钮点击。
- 结果页能回答为什么选择、为什么排除和数据是否过期。
- 用户可以复制当前 URL 重现研究请求。

### Task 7：建立 P0 最短演示和报告

Files：

- Create：scripts/p0/smoke_e2e_private_fund.py
- Create：reports/p0/smoke-e2e-report.md
- Test：backend/tests/test_p0_smoke.py

演示场景：

1. private_strategy + 投资观点。
2. private_strategy + 行业方向。
3. private_strategy + 具体股票或基金标的。
4. 如果公司确认 FOF，再增加 fof + 外部基金场景。

- [ ] Step 1：为每个场景使用现有可追溯数据，不创建无来源假数据。
- [ ] Step 2：每个场景保存 ResearchInput 元数据。
- [ ] Step 3：每个场景生成 CandidateSet 或 no_eligible_candidate。
- [ ] Step 4：报告展示政策版本、快照、候选和排除原因。
- [ ] Step 5：脚本再次运行时验证结果可以复现。
- [ ] Step 6：在报告中明确哪些是样例政策、哪些是生产数据。
- [ ] Step 7：运行 smoke test 并把实际输出写入报告。

禁止：

- 伪造至少三只基金。
- 用 seed_sample_db 伪造机构覆盖。
- 把样例阈值写成正式投资制度。
- 把分析输出描述成交易建议。

### Task 8：阶段 1 的专业验收和风险评估

Files：

- Modify：docs/p0/phase0-acceptance.md
- Create：docs/p1/phase1-acceptance.md
- Create：docs/p1/data-quality-and-coverage-gate.md
- Create：docs/p1/risk-and-model-governance.md

- [ ] Step 1：验收 ResearchInput、InvestmentThesis、CandidateSet 和最小 DecisionRecord 的完整关系链。
- [ ] Step 2：验收无候选、数据不足、估值过高、政策排除和人工覆盖五种状态。
- [ ] Step 3：验收结果绑定数据快照、政策版本和规则版本。
- [ ] Step 4：验收任何人工覆盖都有理由、人员和时间。
- [ ] Step 5：验收报告不把历史表现描述成未来收益承诺。
- [ ] Step 6：验收所有策略政策样例标记为 example，未经审批不可用于生产。
- [ ] Step 7：管理层决定是否进入阶段 2。

## 6. 阶段 2：组合提案和风险

阶段 2 在阶段 1 通过后执行，不应提前并入 ResearchInput 第一批。

### 6.1 目标

把候选集合转成某个策略的 PortfolioProposal，并展示穿透后的风险。

### 6.2 新增对象

    portfolio_proposal
    portfolio_position
    portfolio_exposure
    risk_check_result

### 6.3 必须支持

- 单票、行业、主题和策略仓位上限。
- 自有产品之间的总暴露。
- 外部基金穿透后的行业和股票重叠。
- 相关性和集中度。
- 估值过高和数据过期的组合影响。
- 情景分析和压力测试。
- 组合版本。

### 6.4 组合库边界

先用现有 portfolio_builder 作为适配器，统一输出 PortfolioProposal。之后单独评估 skfolio 或 Riskfolio-Lib：

- skfolio：更适合验证、模型选择和时间序列防泄露。
- Riskfolio-Lib：更适合风险度量、风险贡献和多种优化目标。
- PyPortfolioOpt：适合快速原型和 Black-Litterman、HRP 等常见方法。

优化结果必须保存输入、约束、风险模型、算法版本和输出权重。

## 7. 阶段 3：投决会、监控和归因

### 7.1 投决会

阶段 3 增加：

- 多人意见。
- 投票和否决。
- 会议批次。
- 决议版本。
- 权限矩阵。
- 人工覆盖审计。
- 正式组合批准。

### 7.2 监控

监控事件不应只记录信号，还要记录处理过程：

    detected
    → assigned
    → resolving
    → resolved / closed

每个事件必须保留 trigger_value、threshold、source_snapshot、assigned_to、action 和 action_reason。

### 7.3 归因和复盘

至少记录：

- 研究观点兑现度。
- 候选进入后收益和回撤。
- 行业、风格和股票归因。
- 估值判断是否正确。
- 研究员和策略的历史命中率。
- 被排除候选的后续表现。
- 人工覆盖后的结果。
- 研究假设失效时间。

系统最终要回答：哪些观点、策略和候选方法真正有价值。

## 8. 阶段 5：企业化能力

仅在内部投研闭环有效后实现：

- 角色权限。
- 多团队和多策略。
- 数据权限和供应商授权。
- 生产数据 SLA。
- 备份和灾备。
- 运行监控。
- 审计导出。
- 报告模板和 API。
- 客户/LP 报告。
- 财富管理适当性。

## 9. 专业化建议

### 9.1 不使用单一综合推荐分

同时展示：

- 认知匹配度。
- 证据强度。
- 估值状态。
- 数据完整度。
- 风险冲突。
- 组合增益。
- 人工判断。

单一总分只能作为排序辅助，不能作为投资结论。

### 9.2 把事实、判断和政策分开

每个结果分成三类：

    Fact：持仓、估值、净值、经理和报告期
    Interpretation：风格、预期差、认知匹配
    Policy：是否符合某个策略的准入和风险限制

这三类不能混成一个标签。

### 9.3 每条结论必须有失效条件

没有失效条件的投资假设不能进入 validated。

### 9.4 先证明流程价值，再扩大数据规模

先跑通一条真实私募投研流程，再决定是否购买更多数据、引入更多模型和扩大基金 universe。

### 9.5 对历史数据和未来判断保持边界

历史表现、历史持仓和历史估值只能作为证据，不能直接等同于未来收益预测。任何前视信息、盈利预测和情景假设必须单独标记来源和有效期。

## 10. 计划完成标准

计划执行完成后，系统应达到：

- 研究员可以提交一条研究请求。
- 系统可以保存原文、策略和数据上下文。
- 系统可以生成投资假设和候选集合。
- 系统可以展示证据、反向证据和排除原因。
- 系统可以返回无候选状态。
- 投资经理可以形成最小决策。
- 所有结果可以绑定快照和政策版本。
- 阶段 2 可以在此基础上接入组合风险。
- 阶段 3 可以在此基础上接入投决会和投后归因。

