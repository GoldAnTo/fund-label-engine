-- 0003_phase5_stock_factor_values_and_labels:
-- Phase 5 股票因子层（按 factor_code 纵向存储）+ 股票级标签骨架。
-- 现有 sample DB 已有宽表 stock_factors(stock_code, factor_date, pb, roe, ...)，
-- 为避免冲突，这里用「factor_values」窄表存任意指标；后续可视情况收敛。
CREATE TABLE IF NOT EXISTS stock_factor_values (
    stock_code TEXT NOT NULL,
    factor_code TEXT NOT NULL,
    factor_value REAL,
    as_of_date TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (stock_code, factor_code, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_factor_values_date
    ON stock_factor_values(as_of_date);

CREATE TABLE IF NOT EXISTS stock_labels (
    stock_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    confidence REAL NOT NULL,
    as_of_date TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    PRIMARY KEY (stock_code, label_code, as_of_date, rule_version)
);

CREATE INDEX IF NOT EXISTS idx_stock_labels_label
    ON stock_labels(label_code, as_of_date);
