-- 审计日志：记录所有写操作（复核、组合角色 review、人工操作等）。
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    run_id TEXT,
    actor TEXT NOT NULL,                   -- 谁做的：reviewer / system
    action TEXT NOT NULL,                  -- review / apply-suggestion / batch-run / snapshot-create
    target_type TEXT NOT NULL,             -- fund / label / role / batch / snapshot
    target_id TEXT NOT NULL,               -- fund_code / label_code / role_code / batch_run_id
    payload_json TEXT,                     -- 变更内容（JSON 序列化）
    source_ip TEXT,                        -- HTTP 来源（如果有）
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_log_run
    ON audit_log (run_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor, occurred_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_target
    ON audit_log (target_type, target_id, occurred_at);
