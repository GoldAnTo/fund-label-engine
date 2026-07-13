-- ============================================================
-- 0016_candidate_priority_v0.sql
-- 基金候选优先级 v0：CandidateSet 头表、冻结证据、PriorityRun、PriorityResult
-- ============================================================
-- 设计要点:
--   1. candidate_sets 表的 UNIQUE 约束从 (thesis_id, asset_code) 改为
--      (candidate_set_id, asset_code),允许同一 thesis 在不同集合中重复出现
--   2. 新增 candidate_set_headers 表(集合头),记录一次扫描的元信息
--   3. 新增 candidate_evidence_json 列(冻结证据),写入后不可修改
--   4. 新增 candidate_priority_runs / candidate_priority_results 表
--   5. PriorityResult 整行不可变(禁止 UPDATE 和 DELETE)
--   6. strategy_policies 新增 candidate_priority_json 列
-- ============================================================

-- ------------------------------------------------------------
-- 1. strategy_policies 增加 candidate_priority_json 列
-- ------------------------------------------------------------
ALTER TABLE strategy_policies ADD COLUMN candidate_priority_json TEXT;

-- ------------------------------------------------------------
-- 2. candidate_set_headers 表(集合头)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_set_headers (
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

-- ------------------------------------------------------------
-- 3. 重建 candidate_sets 表(改 UNIQUE 约束 + 加 candidate_evidence_json)
-- ------------------------------------------------------------
-- SQLite 不能直接改约束,需要:
--   a) DROP VIEW v_candidate_set_full(视图依赖 candidate_sets)
--   b) 创建 candidate_set_headers(已在上方完成)
--   c) RENAME 旧 candidate_sets -> candidate_sets_legacy_0016
--   d) 创建新 candidate_sets(带 FK 到 candidate_set_headers 和 candidate_evidence_json)
--   e) 从 legacy 聚合插入 header
--   f) 从 legacy 迁移 candidate_sets 数据
--   g) DROP legacy 表
--   h) 重建视图和索引

-- a) DROP VIEW
DROP VIEW IF EXISTS v_candidate_set_full;

-- c) 重命名旧表
ALTER TABLE candidate_sets RENAME TO candidate_sets_legacy_0016;

-- d) 创建新表
CREATE TABLE candidate_sets (
    candidate_id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL,
    thesis_id TEXT NOT NULL,
    user_input_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    asset_name TEXT,
    fit_score REAL,
    evidence_score REAL,
    valuation_status TEXT,
    data_quality_status TEXT,
    portfolio_contribution_json TEXT,
    conflict_reasons_json TEXT,
    exclusion_reasons_json TEXT NOT NULL DEFAULT '[]',
    as_of_date TEXT,
    data_snapshot_id TEXT,
    candidate_status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    candidate_evidence_json TEXT,
    FOREIGN KEY (thesis_id) REFERENCES investment_theses(thesis_id),
    FOREIGN KEY (user_input_id) REFERENCES research_inputs(user_input_id),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    FOREIGN KEY (candidate_set_id) REFERENCES candidate_set_headers(candidate_set_id),
    UNIQUE (candidate_set_id, asset_code)
);

-- e) 从 legacy 聚合插入 header(INSERT OR IGNORE 防止重复)
INSERT OR IGNORE INTO candidate_set_headers (
    candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
    source_method_version, scanned_fund_count, mapped_candidate_count,
    unmapped_due_to_data_count, created_by
)
SELECT
    cs.candidate_set_id,
    cs.thesis_id,
    cs.user_input_id,
    cs.data_snapshot_id,
    'legacy_governance_v0',
    COUNT(*),
    COUNT(*),
    0,
    'system'
FROM candidate_sets_legacy_0016 cs
GROUP BY cs.candidate_set_id, cs.thesis_id, cs.user_input_id, cs.data_snapshot_id;

-- f) 从 legacy 迁移 candidate_sets 数据
INSERT INTO candidate_sets (
    candidate_id, candidate_set_id, thesis_id, user_input_id,
    asset_type, asset_code, asset_name, fit_score, evidence_score,
    valuation_status, data_quality_status, portfolio_contribution_json,
    conflict_reasons_json, exclusion_reasons_json, as_of_date,
    data_snapshot_id, candidate_status, created_at, reviewed_at
)
SELECT
    candidate_id, candidate_set_id, thesis_id, user_input_id,
    asset_type, asset_code, asset_name, fit_score, evidence_score,
    valuation_status, data_quality_status, portfolio_contribution_json,
    conflict_reasons_json, exclusion_reasons_json, as_of_date,
    data_snapshot_id, candidate_status, created_at, reviewed_at
FROM candidate_sets_legacy_0016;

-- g) 删除旧表(同时删除旧索引)
DROP TABLE candidate_sets_legacy_0016;

-- h) 重建索引
CREATE INDEX IF NOT EXISTS idx_candidate_sets_set
    ON candidate_sets (candidate_set_id);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_thesis
    ON candidate_sets (thesis_id, candidate_status);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_input
    ON candidate_sets (user_input_id);

CREATE INDEX IF NOT EXISTS idx_candidate_sets_status
    ON candidate_sets (candidate_status, created_at DESC);

-- candidate_evidence_json 不可变 trigger
CREATE TRIGGER trg_candidate_sets_evidence_immutable
BEFORE UPDATE OF candidate_evidence_json ON candidate_sets
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'candidate_sets.candidate_evidence_json is immutable');
END;

-- candidate_set_headers 关键字段不可变（整行不可变）
CREATE TRIGGER trg_candidate_set_headers_immutable
BEFORE UPDATE ON candidate_set_headers
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'candidate_set_headers is immutable after creation');
END;

-- candidate_sets 冻结字段不可变（fit_score, asset_code, asset_type, candidate_set_id, thesis_id, data_snapshot_id, candidate_evidence_json）
CREATE TRIGGER trg_candidate_sets_frozen_fields_immutable
BEFORE UPDATE OF fit_score, asset_code, asset_type, candidate_set_id, thesis_id, data_snapshot_id, candidate_evidence_json ON candidate_sets
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'candidate_sets frozen fields are immutable');
END;

-- i) 重建视图(增加 candidate_evidence_json 列)
CREATE VIEW v_candidate_set_full AS
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
    cs.data_snapshot_id,
    cs.candidate_evidence_json
FROM candidate_sets cs
JOIN investment_theses it ON cs.thesis_id = it.thesis_id
JOIN research_inputs ri ON cs.user_input_id = ri.user_input_id;

-- ------------------------------------------------------------
-- 4. candidate_priority_runs 表(优先级计算运行)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_priority_runs (
    priority_run_id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL,
    thesis_id TEXT NOT NULL,
    user_input_id TEXT NOT NULL,
    strategy_policy_id TEXT NOT NULL,
    strategy_policy_version INTEGER NOT NULL,
    data_snapshot_id TEXT,
    ranking_method_version TEXT NOT NULL,
    result_status TEXT NOT NULL DEFAULT 'completed',
    result_type TEXT NOT NULL,
    scanned_fund_count INTEGER,
    mapped_candidate_count INTEGER,
    unmapped_due_to_data_count INTEGER,
    evaluated_candidate_count INTEGER NOT NULL,
    eligible_candidate_count INTEGER NOT NULL,
    tier_counts_json TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (candidate_set_id) REFERENCES candidate_set_headers(candidate_set_id),
    FOREIGN KEY (thesis_id) REFERENCES investment_theses(thesis_id),
    FOREIGN KEY (user_input_id) REFERENCES research_inputs(user_input_id),
    FOREIGN KEY (strategy_policy_id, strategy_policy_version)
        REFERENCES strategy_policies(policy_id, version),
    FOREIGN KEY (data_snapshot_id) REFERENCES data_snapshots(snapshot_id),
    UNIQUE (
        candidate_set_id, strategy_policy_id, strategy_policy_version,
        data_snapshot_id, ranking_method_version
    )
);

CREATE INDEX IF NOT EXISTS idx_priority_runs_thesis
    ON candidate_priority_runs (thesis_id, created_at DESC);

-- ------------------------------------------------------------
-- 5. candidate_priority_results 表(优先级计算结果)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_priority_results (
    priority_result_id TEXT PRIMARY KEY,
    priority_run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    fund_name TEXT,
    eligibility_status TEXT NOT NULL,
    priority_tier TEXT NOT NULL,
    priority_rank INTEGER,
    matched_holding_weight REAL,
    disclosed_holding_weight REAL,
    normalized_match_pct REAL,
    fit_score REAL,
    evidence_score REAL,
    holdings_truth_status TEXT,
    valuation_status TEXT,
    data_quality_status TEXT,
    holding_report_date TEXT,
    dimension_results_json TEXT,
    priority_reasons_json TEXT,
    exclusion_reasons_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (priority_run_id) REFERENCES candidate_priority_runs(priority_run_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_sets(candidate_id),
    UNIQUE (priority_run_id, candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_priority_results_run
    ON candidate_priority_results (priority_run_id, priority_tier);

-- PriorityResult 不可变 trigger(禁止 UPDATE)
CREATE TRIGGER trg_candidate_priority_results_no_update
BEFORE UPDATE ON candidate_priority_results
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'candidate_priority_results is immutable; create a new PriorityRun instead');
END;

-- PriorityResult 不可变 trigger(禁止 DELETE)
CREATE TRIGGER trg_candidate_priority_results_no_delete
BEFORE DELETE ON candidate_priority_results
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'candidate_priority_results cannot be deleted');
END;
