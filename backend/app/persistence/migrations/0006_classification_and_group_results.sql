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

CREATE INDEX IF NOT EXISTS idx_fund_classification_results_code
    ON fund_classification_results(run_id, dimension, classification_code);

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

CREATE INDEX IF NOT EXISTS idx_fund_group_results_code
    ON fund_group_results(run_id, group_type, group_code);
