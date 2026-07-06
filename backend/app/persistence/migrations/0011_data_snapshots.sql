-- 数据快照版本表：记录每次跑批所依赖的数据源信息，用于审计追溯。
CREATE TABLE IF NOT EXISTS data_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_db_path TEXT NOT NULL,
    source_db_mtime TEXT,
    factor_db_path TEXT,
    factor_db_mtime TEXT,
    nav_date_min TEXT,
    nav_date_max TEXT,
    fund_count INTEGER DEFAULT 0,
    factor_count INTEGER DEFAULT 0,
    benchmark_returns_count INTEGER DEFAULT 0,
    holding_report_date TEXT,
    factor_as_of_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 给 label_runs 增加快照外键列
ALTER TABLE label_runs ADD COLUMN data_snapshot_id TEXT REFERENCES data_snapshots(snapshot_id);
