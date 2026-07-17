-- 0019: 为 fund_recommendation_runs 增加 portfolio_json 列
-- 存储由 recommended_universe 重建的组合方案（含 selection_source, holdings, enforced_actions, metrics, risk_review）

ALTER TABLE fund_recommendation_runs ADD COLUMN portfolio_json TEXT;
