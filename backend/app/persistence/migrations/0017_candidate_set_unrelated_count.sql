-- ============================================================
-- 0017_candidate_set_unrelated_count.sql
-- 为 candidate_set_headers 新增 unrelated_fund_count 列
-- ============================================================
-- 背景:
--   0016 发布时 candidate_set_headers 没有 unrelated_fund_count 列。
--   后续需要区分"因数据不足而无法映射"(unmapped_due_to_data_count)
--   和"有持仓但与主题方向不相关"(unrelated_fund_count)。
--   已执行过 0016 的旧库不会重新执行 0016，因此需要独立 migration。
-- ============================================================

ALTER TABLE candidate_set_headers ADD COLUMN unrelated_fund_count INTEGER NOT NULL DEFAULT 0;
