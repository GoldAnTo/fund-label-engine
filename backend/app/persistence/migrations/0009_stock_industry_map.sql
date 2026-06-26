CREATE TABLE IF NOT EXISTS stock_industry_map (
    stock_code TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    sector_group TEXT NOT NULL CHECK (
        sector_group IN ('financial', 'energy_utility', 'consumer', 'other')
    ),
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    PRIMARY KEY (stock_code, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_industry_map_sector
ON stock_industry_map (sector_group, as_of_date);
