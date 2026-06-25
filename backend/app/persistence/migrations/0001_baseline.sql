-- 0001_baseline: 基线 schema 在 LabelRunWriter.ensure_schema() 的 SCHEMA_STATEMENTS 中维护
-- 这条 migration 是占位，确保 schema_migrations 表里有第一条记录，便于排查。
-- 真实的表创建仍然走 CREATE TABLE IF NOT EXISTS，这样老库零改动可用。
CREATE TABLE IF NOT EXISTS schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
