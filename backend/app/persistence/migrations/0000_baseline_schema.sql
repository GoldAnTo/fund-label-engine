-- ============================================================
-- 0000_baseline_schema.sql
-- 把 LabelRunWriter.SCHEMA_STATEMENTS 提到 migration 层
-- 目的:让 migrations_runner 单独跑也能从空库完整初始化
-- 之前:基线表只在 writer.py 中以 Python tuple 形式存在,
--       纯 migration 启动会在 0002 失败(label_runs 不存在)
-- 现在:0000 建表,0001~0014 仍以 ALTER/索引增量演进
-- 兼容:writer.ensure_schema() 仍保留 SCHEMA_STATEMENTS 兜底,
--       IF NOT EXISTS 保证幂等
-- ============================================================

CREATE TABLE IF NOT EXISTS label_definitions (
    label_code TEXT NOT NULL,
    label_name TEXT NOT NULL,
    category TEXT NOT NULL,
    fund_types TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    description TEXT NOT NULL,
    thresholds_json TEXT,
    PRIMARY KEY (label_code, rule_version)
);

CREATE TABLE IF NOT EXISTS label_runs (
    run_id TEXT PRIMARY KEY,
    run_at TEXT NOT NULL,
    data_as_of TEXT,
    rule_version TEXT NOT NULL,
    status TEXT NOT NULL,
    rule_snapshot_json TEXT
);

CREATE TABLE IF NOT EXISTS fund_label_results (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    label_name TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, label_code)
);

CREATE TABLE IF NOT EXISTS fund_label_evidence (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    metric TEXT NOT NULL,
    value TEXT NOT NULL,
    threshold TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_values (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    feature_code TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_percentile_rank (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    metric_value REAL,
    percentile REAL NOT NULL,
    rank_value INTEGER NOT NULL,
    peer_count INTEGER NOT NULL,
    direction TEXT NOT NULL DEFAULT 'higher_better',
    computed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, label_code, metric_code)
);

CREATE TABLE IF NOT EXISTS fund_run_coverage (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    field TEXT NOT NULL,
    present INTEGER NOT NULL,
    review_action TEXT NOT NULL,
    fund_type TEXT,
    PRIMARY KEY (run_id, fund_code, field)
);

CREATE TABLE IF NOT EXISTS label_reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    comment TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_run_failures (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    stage TEXT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, stage)
);

CREATE TABLE IF NOT EXISTS label_calculation_states (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    label_name TEXT NOT NULL,
    category TEXT NOT NULL,
    state TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    observed TEXT NOT NULL,
    threshold TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, label_code)
);

CREATE TABLE IF NOT EXISTS fund_classification_results (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    dimension TEXT NOT NULL,
    classification_code TEXT NOT NULL,
    classification_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason_code TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, dimension)
);

CREATE TABLE IF NOT EXISTS fund_group_results (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    group_code TEXT NOT NULL,
    group_name TEXT NOT NULL,
    group_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, group_code)
);
