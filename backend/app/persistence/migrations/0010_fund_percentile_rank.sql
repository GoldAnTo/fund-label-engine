CREATE TABLE IF NOT EXISTS fund_percentile_rank (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,       -- 风格标签或 'all_market'
    metric_code TEXT NOT NULL,      -- 指标名，如 annualized_return_1y
    metric_value REAL,               -- 指标值
    percentile REAL NOT NULL,        -- 百分位 [0, 1]，越大越靠前
    rank_value INTEGER NOT NULL,     -- 在该分组中的排名（从 1 开始）
    peer_count INTEGER NOT NULL,     -- 该分组的总基金数
    direction TEXT NOT NULL DEFAULT 'higher_better',  -- higher_better / lower_better
    computed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, fund_code, label_code, metric_code)
);

CREATE INDEX IF NOT EXISTS idx_percentile_rank_lookup
ON fund_percentile_rank (run_id, label_code, metric_code, percentile DESC);
