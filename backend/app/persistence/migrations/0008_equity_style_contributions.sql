CREATE TABLE IF NOT EXISTS fund_equity_style_contributions (
    fund_code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    weight REAL NOT NULL,
    style_code TEXT NOT NULL,
    style_name TEXT NOT NULL,
    matched INTEGER NOT NULL,
    contribution_weight REAL NOT NULL,
    factor_values_json TEXT NOT NULL,
    rule_snapshot_json TEXT NOT NULL,
    factor_as_of_date TEXT NOT NULL,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (fund_code, report_date, stock_code, style_code, factor_as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_equity_style_contrib_fund_report
ON fund_equity_style_contributions (fund_code, report_date);

CREATE INDEX IF NOT EXISTS idx_equity_style_contrib_style
ON fund_equity_style_contributions (style_code, factor_as_of_date);
