-- ============================================================
-- 0015_governance_core.sql
-- 阶段 1 治理核心表:策略政策 / 研究请求 / 投资假设 / 候选集合 / 最小决策记录
-- ============================================================
-- 设计依据:
--   - docs/p0/domain-language-v0.md (字段 / 状态机 / 不可变约束)
--   - docs/p0/business-scope.md (3 个研究请求场景)
--   - docs/p0/phase0-acceptance.md (阶段 0 验收与立项)
--
-- 设计原则:
--   1. 字段命名 / 状态机与 domain-language-v0.md 完全一致
--   2. 严格不可变:research_inputs / investment_theses / decision_records 表的
--      "已冻结"字段用 TRIGGER 阻止 UPDATE;candidate_sets 允许更新状态字段
--      (exclusion_reasons 只增不删)
--   3. 复用 data_snapshots(0011)和 audit_log(0013),不重建
--   4. strategy_policies 在阶段 1 从 YAML 同步到表;阶段 2 再决定是否用表覆盖 YAML
--   5. decision_records 只建最小版(committee_decision / decision_reason),
--      完整投决会流程(多人审批 / 表决记录)留到阶段 3
--
-- 落库后第一步:
--   1. 跑此 migration
--   2. 写 sync_strategy_policies.py 把 2 份 YAML 同步到 strategy_policies 表
--   3. 写 research_inputs API(POST/GET),把 smoke 演示落库
-- ============================================================

-- ------------------------------------------------------------
-- 1. strategy_policies(策略政策)
-- ------------------------------------------------------------
-- 字段对齐 domain-language-v0.md 第 3 节;YAML 中的嵌套对象(JSON 字符串存储)
-- 状态机: draft → approved → active → deprecated (+ rejected)
CREATE TABLE IF NOT EXISTS strategy_policies (
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    business_mode TEXT NOT NULL,                 -- private_strategy | fof
    policy_status TEXT NOT NULL DEFAULT 'draft', -- draft|approved|active|deprecated|rejected
    approved_for_production INTEGER NOT NULL DEFAULT 0,  -- 0/1
    strategy_name TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    market_scope_json TEXT,                      -- JSON 数组
    investment_horizon TEXT,                     -- ISO 8601 duration, 如 P1Y
    benchmark TEXT,
    target_return REAL,
    risk_budget REAL,
    maximum_drawdown REAL,
    leverage_limit REAL DEFAULT 1.0,
    liquidity_limit TEXT,
    position_limit_json TEXT,                    -- JSON 对象
    allowed_universe_json TEXT,                  -- JSON 数组
    excluded_universe_json TEXT,                 -- JSON 数组
    valuation_policy_json TEXT,                  -- JSON 对象
    investment_policy_json TEXT,                 -- JSON 对象(投资政策:preferred_styles/required_evidence 等)
    monitoring_policy_json TEXT,                 -- JSON 对象(对应 monitoring_event 阈值)
    effective_from TEXT,                         -- ISO date
    effective_to TEXT,                           -- ISO date, NULL 表示长期
    approved_by TEXT,
    schema_doc TEXT,                             -- 指向 domain-language 文档路径,用于审计
    change_policy TEXT DEFAULT 'append_new_version',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (policy_id, version)
);

-- 同一 policy_id 只能有 1 个 active
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_policies_one_active
    ON strategy_policies (policy_id)
    WHERE policy_status = 'active';

CREATE INDEX IF NOT EXISTS idx_strategy_policies_status
    ON strategy_policies (policy_status, business_mode);


-- ------------------------------------------------------------
-- 2. research_inputs(研究请求 / UserInput)
-- ------------------------------------------------------------
-- 业务名 ResearchInput,技术名沿用 user_input_id 以保持代码兼容
-- raw_text 不可修改:用 TRIGGER 阻止 UPDATE
-- 状态机: received → parsed → expanded → closed (+ failed)
CREATE TABLE IF NOT EXISTS research_inputs (
    user_input_id TEXT PRIMARY KEY,
    input_type TEXT NOT NULL,                    -- philosophy|industry|target|manager|strategy
    business_mode TEXT NOT NULL,                 -- private_strategy|fof
    strategy_policy_id TEXT NOT NULL,
    strategy_policy_version INTEGER NOT NULL,
    actor_role TEXT NOT NULL,                    -- researcher|portfolio_manager|risk|product
    actor_id TEXT,                               -- 具体人员 ID,可选
    request_source TEXT NOT NULL,                -- research_meeting|ad_hoc_research|portfolio_review|risk_review
    raw_text TEXT NOT NULL,
    structured_intent_json TEXT,                 -- 解析后的结构化意图(JSON)
    target_assets_json TEXT,                     -- 场景 C/D 时的具体标的(JSON 数组)
    implicit_intent TEXT,                        -- copy|alternative|hedge|correlate
    session_id TEXT,                             -- 跨场景追问的会话
    previous_user_input_id TEXT,                 -- 修订时引用上一条
    as_of_date TEXT,                             -- ISO date
    data_snapshot_id TEXT,                       -- 引用 data_snapshots.snapshot_id
    status TEXT NOT NULL DEFAULT 'received',     -- received|parsed|expanded|closed|failed
    failure_reason TEXT,                         -- 解析失败时填
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    FOREIGN KEY (strategy_policy_id, strategy_policy_version)
        REFERENCES strategy_policies(policy_id, version),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    FOREIGN KEY (previous_user_input_id) REFERENCES research_inputs(user_input_id)
);

CREATE INDEX IF NOT EXISTS idx_research_inputs_status
    ON research_inputs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_inputs_policy
    ON research_inputs (strategy_policy_id, strategy_policy_version);

CREATE INDEX IF NOT EXISTS idx_research_inputs_session
    ON research_inputs (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_inputs_snapshot
    ON research_inputs (data_snapshot_id);

-- raw_text 绝对不可变:从插入起就不允许 UPDATE
-- 修正:不再绑状态机,任何状态都禁止改 raw_text。
-- 若需修正,新增一条 ResearchInput 并通过 previous_user_input_id 引用。
CREATE TRIGGER IF NOT EXISTS trg_research_inputs_raw_text_immutable
BEFORE UPDATE OF raw_text ON research_inputs
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'research_inputs.raw_text is immutable; insert new row with previous_user_input_id instead');
END;


-- ------------------------------------------------------------
-- 3. investment_theses(投资假设)
-- ------------------------------------------------------------
-- 状态机: draft → researching → validated → approved → watching → invalidated
--                                            ↘ closed
-- validated 之后 belief_statement / as_of_date / data_snapshot_id 不可变
CREATE TABLE IF NOT EXISTS investment_theses (
    thesis_id TEXT PRIMARY KEY,
    user_input_id TEXT NOT NULL,                 -- 必有源头
    strategy_policy_id TEXT NOT NULL,
    strategy_policy_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    belief_statement TEXT NOT NULL,
    time_horizon TEXT,
    supporting_evidence_json TEXT,               -- 证据 ID 列表(JSON 数组)
    opposing_evidence_json TEXT,
    key_metrics_json TEXT,
    candidate_assets_json TEXT,                  -- 候选资产/行业/管理人 ID(JSON 数组)
    valuation_view_json TEXT,
    catalysts_json TEXT,
    invalidation_conditions_json TEXT,
    previous_thesis_id TEXT,                     -- 修订时引用上一条
    owner TEXT NOT NULL,                         -- 研究员 ID
    as_of_date TEXT,
    data_snapshot_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    next_review_at TEXT,
    invalidated_reason TEXT,
    closed_at TEXT,
    FOREIGN KEY (user_input_id) REFERENCES research_inputs(user_input_id),
    FOREIGN KEY (strategy_policy_id, strategy_policy_version)
        REFERENCES strategy_policies(policy_id, version),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    FOREIGN KEY (previous_thesis_id) REFERENCES investment_theses(thesis_id)
);

CREATE INDEX IF NOT EXISTS idx_investment_theses_status
    ON investment_theses (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_investment_theses_input
    ON investment_theses (user_input_id);

CREATE INDEX IF NOT EXISTS idx_investment_theses_policy
    ON investment_theses (strategy_policy_id, strategy_policy_version);

CREATE INDEX IF NOT EXISTS idx_investment_theses_review
    ON investment_theses (next_review_at)
    WHERE status IN ('approved', 'watching');

-- validated 之后核心字段不可变
CREATE TRIGGER IF NOT EXISTS trg_investment_theses_core_immutable
BEFORE UPDATE OF belief_statement, as_of_date, data_snapshot_id ON investment_theses
FOR EACH ROW
WHEN OLD.status NOT IN ('draft', 'researching')
BEGIN
    SELECT RAISE(ABORT, 'investment_theses.{belief_statement,as_of_date,data_snapshot_id} immutable after validated');
END;


-- ------------------------------------------------------------
-- 4. candidate_sets(候选集合)
-- ------------------------------------------------------------
-- 一行 = 一个 thesis 下的一个候选
-- 状态机: proposed → screening → reviewed → approved / rejected
-- exclusion_reasons 只增不删:在 application 层用 JSON 数组 append 模式管理
CREATE TABLE IF NOT EXISTS candidate_sets (
    candidate_id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL,              -- 同一次研究请求的所有候选共享
    thesis_id TEXT NOT NULL,
    user_input_id TEXT NOT NULL,                 -- 用于反查
    asset_type TEXT NOT NULL,                    -- stock|fund|manager|strategy|industry|product
    asset_code TEXT NOT NULL,
    asset_name TEXT,
    fit_score REAL,                              -- 0~1
    evidence_score REAL,                         -- 0~1
    valuation_status TEXT,                       -- undervalued|fair|overvalued|unknown
    data_quality_status TEXT,                    -- sufficient|partial|insufficient
    portfolio_contribution_json TEXT,            -- 阶段 2 填,阶段 0/1 可空
    conflict_reasons_json TEXT,                  -- JSON 数组
    exclusion_reasons_json TEXT NOT NULL DEFAULT '[]',  -- JSON 数组,只增不删
    as_of_date TEXT,
    data_snapshot_id TEXT,
    candidate_status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    FOREIGN KEY (thesis_id) REFERENCES investment_theses(thesis_id),
    FOREIGN KEY (user_input_id) REFERENCES research_inputs(user_input_id),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    UNIQUE (thesis_id, asset_code)
);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_set
    ON candidate_sets (candidate_set_id);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_thesis
    ON candidate_sets (thesis_id, candidate_status);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_input
    ON candidate_sets (user_input_id);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_status
    ON candidate_sets (candidate_status, created_at DESC);


-- ------------------------------------------------------------
-- 5. decision_records(最小决策记录)
-- ------------------------------------------------------------
-- 阶段 1 最小版:支持 approved/rejected/watching 3 个终态
-- 完整投决会(多人审批 / 投票记录)留到阶段 3 在此表加列或新建 decision_votes 表
-- 不可变:整行不可更新(任何修正通过新增 decision_id + 引用原 decision_id)
CREATE TABLE IF NOT EXISTS decision_records (
    decision_id TEXT PRIMARY KEY,
    strategy_policy_id TEXT NOT NULL,
    strategy_policy_version INTEGER NOT NULL,
    user_input_id TEXT NOT NULL,
    thesis_id TEXT NOT NULL,
    candidate_set_id TEXT NOT NULL,
    data_snapshot_id TEXT NOT NULL,
    proposed_positions_json TEXT,                -- JSON 数组 [{asset_code, weight, role}]
    rejected_positions_json TEXT,                -- JSON 数组 [{asset_code, reason}]
    risk_check_result_json TEXT,                 -- 风险检查输出
    committee_decision TEXT NOT NULL,            -- approved|rejected|watching|pending_data
    decision_reason TEXT,                        -- 投决理由(自然语言)
    manual_override_json TEXT,                   -- {field, from, to, reason, by}
    reviewer_json TEXT,                          -- JSON 数组(阶段 1 只放 1 人;阶段 3 扩展多人)
    previous_decision_id TEXT,                   -- 修正时引用原 decision
    approved_at TEXT,                            -- 决策时间
    valid_until TEXT,                            -- 失效时间
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (strategy_policy_id, strategy_policy_version)
        REFERENCES strategy_policies(policy_id, version),
    FOREIGN KEY (user_input_id) REFERENCES research_inputs(user_input_id),
    FOREIGN KEY (thesis_id) REFERENCES investment_theses(thesis_id),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    FOREIGN KEY (previous_decision_id) REFERENCES decision_records(decision_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_records_decision
    ON decision_records (committee_decision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_decision_records_thesis
    ON decision_records (thesis_id);

CREATE INDEX IF NOT EXISTS idx_decision_records_input
    ON decision_records (user_input_id);

CREATE INDEX IF NOT EXISTS idx_decision_records_snapshot
    ON decision_records (data_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_decision_records_policy
    ON decision_records (strategy_policy_id, strategy_policy_version, created_at DESC);

-- 整行不可变:阻止任何 UPDATE
CREATE TRIGGER IF NOT EXISTS trg_decision_records_no_update
BEFORE UPDATE ON decision_records
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'decision_records is append-only; use new decision_id with previous_decision_id');
END;

-- 阻止任何 DELETE(防止人工清理历史)
CREATE TRIGGER IF NOT EXISTS trg_decision_records_no_delete
BEFORE DELETE ON decision_records
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'decision_records cannot be deleted');
END;


-- ------------------------------------------------------------
-- 6. 视图(便于查询和审计)
-- ------------------------------------------------------------
-- 6.1 候选集合全景视图
CREATE VIEW IF NOT EXISTS v_candidate_set_full AS
SELECT
    cs.candidate_set_id,
    ri.user_input_id,
    ri.input_type,
    ri.actor_role,
    ri.raw_text,
    ri.business_mode,
    ri.strategy_policy_id,
    ri.strategy_policy_version,
    it.thesis_id,
    it.belief_statement,
    it.status AS thesis_status,
    cs.candidate_id,
    cs.asset_type,
    cs.asset_code,
    cs.asset_name,
    cs.fit_score,
    cs.evidence_score,
    cs.valuation_status,
    cs.data_quality_status,
    cs.candidate_status,
    cs.as_of_date,
    cs.data_snapshot_id
FROM candidate_sets cs
JOIN investment_theses it ON cs.thesis_id = it.thesis_id
JOIN research_inputs ri ON cs.user_input_id = ri.user_input_id;

-- 6.2 决策全景视图
CREATE VIEW IF NOT EXISTS v_decision_record_full AS
SELECT
    dr.decision_id,
    dr.committee_decision,
    dr.approved_at,
    dr.valid_until,
    dr.data_snapshot_id,
    dr.strategy_policy_id,
    dr.strategy_policy_version,
    ri.user_input_id,
    ri.actor_role,
    ri.input_type,
    ri.raw_text,
    it.thesis_id,
    it.belief_statement,
    dr.candidate_set_id
FROM decision_records dr
JOIN research_inputs ri ON dr.user_input_id = ri.user_input_id
JOIN investment_theses it ON dr.thesis_id = it.thesis_id;
