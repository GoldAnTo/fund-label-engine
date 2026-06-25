CREATE TABLE IF NOT EXISTS fund_factor_exposures (
    fund_code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    factor_code TEXT NOT NULL,
    exposure_value REAL NOT NULL,
    coverage_weight REAL NOT NULL,
    holding_total_weight REAL NOT NULL,
    stock_count INTEGER NOT NULL,
    covered_stock_count INTEGER NOT NULL,
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (fund_code, report_date, factor_code, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_fund_factor_exposures_fund_report
ON fund_factor_exposures (fund_code, report_date);

CREATE INDEX IF NOT EXISTS idx_fund_factor_exposures_factor_asof
ON fund_factor_exposures (factor_code, as_of_date);
