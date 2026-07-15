"""Thesis 投资假设层测试。"""
import sqlite3

from app.cognition.engine import CognitionEngine


def _setup_db(db_path):
    """创建测试数据库（fund_stock_holdings 表，report_date + weight）。"""
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE fund_profiles (fund_code TEXT, fund_name TEXT, fund_type TEXT)")
    conn.execute("CREATE TABLE fund_stock_holdings (fund_code TEXT, report_date TEXT, stock_code TEXT, stock_name TEXT, weight REAL, market TEXT, industry_name TEXT, sector_group TEXT)")
    conn.execute("CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)")
    conn.execute("CREATE TABLE stock_industry_map (stock_code TEXT, industry_name TEXT)")
    conn.commit()
    conn.close()


def test_thesis_has_id_and_audit_fields(tmp_path):
    """Thesis 应有 thesis_id、as_of_date、status 字段。
    用户因果链中提到不在预设链的股票时，应加入 user_stock_keywords。
    """
    db = tmp_path / "test.sqlite"
    _setup_db(db)
    # 插入一条不在预设 AI 链中的股票（中微公司不在 chain config 中）
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO fund_stock_holdings VALUES ('001', '2024-12-31', '688012', '中微公司', 0.1, NULL, '半导体', 'tech')")
    conn.commit()
    conn.close()

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(
        direction="AI",
        conviction="high",
        belief_note="AI是生产力变革",
        reasoning_chain=["AI是生产力变革", "算力是核心", "中微公司是关键"],
    )
    thesis = result.get("step0_thesis", {})
    assert "thesis_id" in thesis
    assert thesis["thesis_id"].startswith("th_")
    assert thesis["source"] == "user"
    assert thesis["belief"] == "AI是生产力变革"
    # 中微公司不在预设链中，应被提取为 user_stock_keyword
    assert "中微公司" in thesis.get("user_stock_keywords", [])
    assert "as_of_date" in thesis
    assert thesis["status"] == "draft"


def test_thesis_user_stock_expands_candidate_pool(tmp_path):
    """用户因果链中提到不在预设链的股票，该股票的持有基金应出现在最终候选中。

    端到端断言：
    - 无 Thesis：F999 不在最终候选（中微公司不在预设链）
    - 有 Thesis：F999 在最终候选（user_stock_keywords 进入 good_keywords）
    """
    db = tmp_path / "test.sqlite"
    _setup_db(db)
    # 插入一只持有"中微公司"的基金（中微公司不在 AI 预设链中）
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO fund_stock_holdings VALUES ('F999', '2024-12-31', '688012', '中微公司', 0.15, NULL, '半导体', 'tech')")
    conn.commit()
    conn.close()

    engine = CognitionEngine(source_db=str(db), factor_db=None)

    # 不带 reasoning_chain：中微公司不在预设链，F999 不应出现在最终候选
    result_no_thesis = engine.run(direction="AI", conviction="medium")
    fund_codes_no = {f["fund_code"] for f in result_no_thesis.get("step4_fund_matches", [])}
    assert "F999" not in fund_codes_no, "无 Thesis 时 F999 不应出现在候选中"

    # 带 reasoning_chain 提到中微公司：F999 应出现在最终候选
    result_with_thesis = engine.run(
        direction="AI",
        conviction="medium",
        belief_note="中微公司是国产半导体设备龙头",
        reasoning_chain=["AI算力需求爆发", "半导体设备国产替代", "中微公司是关键"],
    )
    fund_codes_with = {f["fund_code"] for f in result_with_thesis.get("step4_fund_matches", [])}
    thesis = result_with_thesis.get("step0_thesis", {})
    assert "中微公司" in thesis.get("user_stock_keywords", [])
    assert "F999" in fund_codes_with, "有 Thesis 时 F999 应出现在最终候选中"


def test_thesis_preset_when_no_belief_note(tmp_path):
    """无 belief_note 时 source 应为 preset。"""
    db = tmp_path / "test.sqlite"
    _setup_db(db)

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(direction="AI", conviction="medium")
    thesis = result.get("step0_thesis", {})
    assert thesis["source"] == "preset"
    assert thesis["user_stock_keywords"] == []


def test_thesis_falsification_conditions_auto_generated(tmp_path):
    """证伪条件应从产业链 benefit_logic 自动推导。"""
    db = tmp_path / "test.sqlite"
    _setup_db(db)

    engine = CognitionEngine(source_db=str(db), factor_db=None)
    result = engine.run(direction="AI", conviction="medium")
    thesis = result.get("step0_thesis", {})
    conditions = thesis.get("falsification_conditions", [])
    assert len(conditions) > 0
    assert all("不成立" in c for c in conditions)
