# 阶段 0 · 私募内部角色说明 v0.3

> 文档状态：阶段 0 角色和权限草案
>
> 适用范围：私募内部投研与组合决策；FOF 模式复用同一套角色
>
> 核心原则：所谓“用户”是研究请求的发起人，不是外部客户角色。

## 1. 角色总览

| 角色 | 主要目标 | 阶段 0 权限 |
|---|---|---|
| 研究员 | 提出研究请求、维护投资假设、收集证据 | 创建和编辑自己的 ResearchInput / InvestmentThesis |
| 投资经理 | 审阅候选、判断组合影响、形成最小决策 | 查看全部研究结果，更新候选状态和最小决策理由 |
| 投决会成员 | 对重要策略和组合进行正式表决 | 阶段 0 只审阅样例，阶段 1 不实现完整投票 |
| 风险管理 | 检查暴露、政策限制和监控事件 | 查看全部候选和组合风险，提出 warning / hold |
| 产品/运营 | 管理策略政策、数据批次和产品目录 | 创建和发布 Policy 版本，触发数据快照 |
| 系统管理员 | 管理账号、权限、供应商和运行环境 | 阶段 0 不纳入，阶段 5 再实现 |

## 2. 研究请求发起人

技术上使用 user_input_id，业务上称为 ResearchInput。

研究请求必须记录：

- actor_role：researcher / portfolio_manager / risk / product
- request_source：research_meeting / ad_hoc_research / portfolio_review / risk_review
- business_mode：private_strategy / fof
- strategy_policy_id
- raw_text
- data_snapshot_id

研究请求发起人可以是研究员、投资经理、风控或产品运营，但不能绕过策略政策和数据快照直接生成正式候选。

允许：

- 提交研究观点、行业、股票、基金、管理人或策略。
- 查看研究请求历史。
- 查看候选证据和排除原因。
- 追问候选为什么入选或被排除。

不允许：

- 修改已经冻结的原始输入。
- 修改已验证投资假设的历史证据。
- 直接改变策略政策。
- 直接生成 approved 决策。

## 3. 研究员

### 输入

- ResearchInput。
- StrategyPolicy 当前版本。
- 基金、股票、行业、经理和基准证据。
- 历史研究案例。

### 输出

- InvestmentThesis。
- CandidateSet。
- 支持和反向证据。
- 数据不足和排除原因。
- 研究下一步建议。

### 权限

| 动作 | 权限 |
|---|---|
| 创建研究请求 | 允许 |
| 创建 InvestmentThesis | 允许 |
| 修改 draft / researching | 允许 |
| 提交 validated | 需要投资经理复核 |
| 修改 active Policy | 不允许 |
| 修改历史决策 | 不允许，只能新增版本或补充事件 |

## 4. 投资经理

### 输入

- 研究员提交的 InvestmentThesis。
- 候选集合。
- 持仓穿透、估值、风险和组合影响。
- 反向证据与数据质量。

### 输出

- 候选优先级。
- PortfolioProposal。
- 最小 DecisionRecord。
- 观察、批准、否决或补数据的理由。

### 权限

| 动作 | 权限 |
|---|---|
| 查看全部研究请求和候选 | 允许 |
| 将 thesis 从 researching 改为 validated | 允许 |
| 将候选标记为 watching / rejected | 允许 |
| 形成最小 DecisionRecord | 允许 |
| 修改 StrategyPolicy | 只能提出变更建议 |
| 覆盖风险门禁 | 必须记录理由并触发审计 |

## 5. 投决会成员

阶段 0 只看投决备料包，包括 ResearchInput、InvestmentThesis、CandidateSet、Policy version、Data snapshot、Risk check 和支持/反向证据。

阶段 0 不实现正式投票。阶段 1 只保留最小决策状态：

- pending
- approved
- rejected
- watching
- pending_data

阶段 3 再实现多人投票、权限矩阵、表决意见、会议批次、决议版本和正式组合批准。

## 6. 风险管理人员

### 输入

- 策略政策。
- 候选和组合提案。
- 持仓、行业、风格、估值和流动性暴露。
- 监控事件。

### 输出

- 风险提示。
- 规则触发证据。
- 需要补数据的字段。
- 允许继续研究、观察、挂起或升级的意见。

风险管理不负责修改研究观点，但可以标记风险冲突、要求候选进入 watching、触发 risk_breach、建议暂停进入组合，并对策略政策风险字段提出变更建议。

## 7. 产品/运营

### 输入

- 公司策略目录。
- 私募产品目录。
- 数据供应商交付。
- 策略政策变更申请。

### 输出

- StrategyPolicy 新版本。
- 数据快照和批次说明。
- 产品和策略关联关系。
- 数据源质量和 SLA 状态。

产品/运营不能修改研究员的原始输入、InvestmentThesis 的证据或 DecisionRecord，也不能直接改变投决结果。

## 8. 跨角色流程

研究员或投资经理发起 ResearchInput，研究员维护 InvestmentThesis，系统生成 CandidateSet 与证据，投资经理检查候选和组合影响，风险管理检查政策和暴露，阶段 1 形成最小 DecisionRecord，阶段 3 再进入正式投决会。

## 9. 阶段 0 明确排除

- 客户经理和销售。
- 外部客户账户。
- 财富管理适当性。
- 自动交易。
- 系统管理员权限平台。
- 正式投决会表决。

这些不是永远不做，而是不能混入私募内部投研 P0。
