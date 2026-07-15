"""Thesis 投资假设层测试。"""
from app.cognition.engine import CognitionEngine


def test_thesis_has_id_and_audit_fields(tmp_path):
    """Thesis 应有 thesis_id、as_of_date、status 字段。"""
    import sqlite3
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE fund_profiles (fund_code TEXT, fund_name TEXT, fund_type TEXT)")
    conn.execute("CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, stock_name TEXT, weight REAL, report_date TEXT, industry_name TEXT, sector_group TEXT)")
    conn.execute("CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)")
    conn.execute("CREATE TABLE stock_industry_map (stock_code TEXT, industry_name TEXT)")
    conn.commit()
    conn.close()

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(
        direction="AI",
        conviction="high",
        belief_note="AI是生产力变革",
        reasoning_chain=["AI是生产力变革", "算力是核心", "台积电是关键"],
    )
    thesis = result.get("step0_thesis", {})
    assert "thesis_id" in thesis
    assert thesis["thesis_id"].startswith("th_")
    assert thesis["source"] == "user"
    assert thesis["belief"] == "AI是生产力变革"
    assert "台积电" in thesis.get("user_stock_keywords", [])
    assert "as_of_date" in thesis
    assert thesis["status"] == "draft"


def test_thesis_preset_when_no_belief_note(tmp_path):
    """无 belief_note 时 source 应为 preset。"""
    import sqlite3
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE fund_profiles (fund_code TEXT, fund_name TEXT, fund_type TEXT)")
    conn.execute("CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, stock_name TEXT, weight REAL, report_date TEXT, industry_name TEXT, sector_group TEXT)")
    conn.execute("CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)")
    conn.execute("CREATE TABLE stock_industry_map (stock_code TEXT, industry_name TEXT)")
    conn.commit()
    conn.close()

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(direction="AI", conviction="medium")
    thesis = result.get("step0_thesis", {})
    assert thesis["source"] == "preset"
    assert thesis["user_stock_keywords"] == []


def test_thesis_falsification_conditions_auto_generated(tmp_path):
    """证伪条件应从产业链 benefit_logic 自动推导。"""
    import sqlite3
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE fund_profiles (fund_code TEXT, fund_name TEXT, fund_type TEXT)")
    conn.execute("CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, stock_name TEXT, weight REAL, report_date TEXT, industry_name TEXT, sector_group TEXT)")
    conn.execute("CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)")
    conn.execute("CREATE TABLE stock_industry_map (stock_code TEXT, industry_name TEXT)")
    conn.commit()
    conn.close()

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(direction="AI", conviction="medium")
    thesis = result.get("step0_thesis", {})
    conditions = thesis.get("falsification_conditions", [])
    assert len(conditions) > 0
    assert all("不成立" in c for c in conditions)
