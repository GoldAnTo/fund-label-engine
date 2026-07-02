CREATE TABLE IF NOT EXISTS portfolio_role_reviews (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    role_code TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('accept', 'reject', 'needs_more_data')
    ),
    target_bucket TEXT NOT NULL CHECK (
        target_bucket IN ('core', 'satellite', 'index_tool', 'cash_buffer', 'exclude')
    ),
    max_weight_pct REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, fund_code, role_code)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_role_reviews_run_bucket
ON portfolio_role_reviews (run_id, target_bucket, decision);
