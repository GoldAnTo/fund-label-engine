-- 标签变化追踪表：记录相邻两次 batch 之间标签状态的变化。
CREATE TABLE IF NOT EXISTS label_changes (
    run_id TEXT NOT NULL,
    previous_run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    label_code TEXT NOT NULL,
    label_name TEXT,
    change_type TEXT NOT NULL,          -- added / removed / status_changed
    previous_status TEXT,               -- 上次的 status（added 时为 NULL）
    current_status TEXT,                -- 本次的 status（removed 时为 NULL）
    is_risk_warning INTEGER DEFAULT 0,  -- 1=风险标签从非 active 变为 active
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, fund_code, label_code)
);

CREATE INDEX IF NOT EXISTS idx_label_changes_risk
    ON label_changes (run_id, is_risk_warning)
    WHERE is_risk_warning = 1;

CREATE INDEX IF NOT EXISTS idx_label_changes_fund
    ON label_changes (run_id, fund_code);
