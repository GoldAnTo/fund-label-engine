-- 监控面板 v1：基金估值历史快照
-- 每次 batch run 时为每只参与计算的基金写一行估值快照（PE / 估值分位 / PEG 等）
-- 用作监控面板 v1 的估值时间序列数据源
CREATE TABLE IF NOT EXISTS fund_valuation_history (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    as_of_date TEXT NOT NULL,           -- run_at 截断到日
    weighted_pe REAL,
    weighted_pb REAL,
    weighted_roe REAL,
    weighted_dividend_yield REAL,
    weighted_val_pct REAL,              -- 0-100 百分位
    weighted_peg REAL,
    price_in_years REAL,                -- 隐含增长年限
    position_count INTEGER,             -- 持仓股票数（用于风险信号）
    top_holding_weight REAL,            -- 第一大重仓股权重（用于集中度风险）
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, fund_code)
);

CREATE INDEX IF NOT EXISTS idx_fund_valuation_history_fund_date
    ON fund_valuation_history (fund_code, as_of_date DESC);

CREATE INDEX IF NOT EXISTS idx_fund_valuation_history_run
    ON fund_valuation_history (run_id);
