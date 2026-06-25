-- 0002_run_snapshot_and_thresholds:
-- 给已经存在的 label_runs / label_definitions 表补 rule_snapshot_json / thresholds_json 列。
-- 通过 PRAGMA + 子查询的方式手写幂等 ALTER（SQLite 不原生支持 IF NOT EXISTS 加列）。
-- 这里直接 ALTER：如果列已存在，由 migrations_runner 的 id 去重保证不会重复执行。
ALTER TABLE label_runs ADD COLUMN rule_snapshot_json TEXT;
ALTER TABLE label_definitions ADD COLUMN thresholds_json TEXT;
