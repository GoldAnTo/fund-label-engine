-- ============================================================
-- 0018_fund_recommendation.sql
-- 基金推荐 v1：RecommendationRun / RecommendationResult
-- ============================================================
-- 设计要点:
--   1. strategy_policies 新增 fund_recommendation_json 列
--   2. fund_recommendation_runs 表(推荐运行头)
--      外键引用 CandidateSet、Thesis、ResearchInput、策略版本和快照
--      唯一键为 CandidateSet/策略版本/快照/方法版本
--   3. fund_recommendation_results 表(推荐结果)
--      保存类别、档位、类内排名、四个分项、总分、理由、排除理由和冻结证据 JSON
--      UPDATE/DELETE 触发器报错必须含 'immutable'
-- ============================================================

-- ------------------------------------------------------------
-- 1. strategy_policies 增加 fund_recommendation_json 列
-- ------------------------------------------------------------
ALTER TABLE strategy_policies ADD COLUMN fund_recommendation_json TEXT;

-- ------------------------------------------------------------
-- 2. fund_recommendation_runs 表(推荐运行)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fund_recommendation_runs (
    recommendation_run_id TEXT PRIMARY KEY,
    candidate_set_id TEXT NOT NULL,
    thesis_id TEXT NOT NULL,
    user_input_id TEXT NOT NULL,
    strategy_policy_id TEXT NOT NULL,
    strategy_policy_version INTEGER NOT NULL,
    data_snapshot_id TEXT,
    recommendation_method_version TEXT NOT NULL,
    result_status TEXT NOT NULL DEFAULT 'completed',
    result_type TEXT NOT NULL,
    evaluated_candidate_count INTEGER NOT NULL,
    recommended_count INTEGER NOT NULL DEFAULT 0,
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
        data_snapshot_id, recommendation_method_version
    )
);

CREATE INDEX IF NOT EXISTS idx_recommendation_runs_thesis
    ON fund_recommendation_runs (thesis_id, created_at DESC);

-- ------------------------------------------------------------
-- 3. fund_recommendation_results 表(推荐结果)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fund_recommendation_results (
    recommendation_result_id TEXT PRIMARY KEY,
    recommendation_run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    fund_name TEXT,
    product_category TEXT NOT NULL,
    recommendation_tier TEXT NOT NULL,
    category_rank INTEGER,
    theme_exposure_score REAL,
    thesis_alignment_score REAL,
    risk_return_score REAL,
    fund_quality_score REAL,
    total_score REAL NOT NULL,
    recommendation_reasons_json TEXT,
    exclusion_reasons_json TEXT,
    frozen_evidence_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (recommendation_run_id) REFERENCES fund_recommendation_runs(recommendation_run_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_sets(candidate_id),
    UNIQUE (recommendation_run_id, candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_results_run
    ON fund_recommendation_results (recommendation_run_id, recommendation_tier);

CREATE INDEX IF NOT EXISTS idx_recommendation_results_category
    ON fund_recommendation_results (recommendation_run_id, product_category, category_rank);

-- RecommendationResult 不可变 trigger(禁止 UPDATE)
CREATE TRIGGER trg_fund_recommendation_results_no_update
BEFORE UPDATE ON fund_recommendation_results
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'fund_recommendation_results is immutable; create a new RecommendationRun instead');
END;

-- RecommendationResult 不可变 trigger(禁止 DELETE)
CREATE TRIGGER trg_fund_recommendation_results_no_delete
BEFORE DELETE ON fund_recommendation_results
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'fund_recommendation_results cannot be deleted; immutable');
END;
