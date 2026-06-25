-- 0004_coverage_fund_type:
-- 给 fund_run_coverage 加 fund_type 列，便于 P0 覆盖率报告按基金类型聚合。
--
-- 用 CREATE TABLE IF NOT EXISTS 兜底：
--   - 表已存在（老库） => 无操作，继续往下走
--   - 表不存在（新库第一次跑 migration 但 ensure_schema 尚未执行） => 创建之
-- 后续 ALTER TABLE 补列，在已含该列的表上会报 duplicate column name，
--   migration_runner 将其视作幂等跳过。
CREATE TABLE IF NOT EXISTS fund_run_coverage (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    field TEXT NOT NULL,
    present INTEGER NOT NULL,
    review_action TEXT NOT NULL,
    fund_type TEXT,
    PRIMARY KEY (run_id, fund_code, field)
);
ALTER TABLE fund_run_coverage ADD COLUMN fund_type TEXT;