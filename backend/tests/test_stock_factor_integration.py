"""Phase 5 股票因子接入测试：窄表优先 + 宽表 fallback。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.batch import run_batch
from app.data_access import FundRepository
from app.data_access.stock_factors import load_stock_factors
from app.persistence import LabelRunReader


def _make_db_with_holdings(tmp_path: Path) -> Path:
    """造一个最小化的 fundData 风格库，含 1 只基金 + 2 只持仓股票。"""
    db = tmp_path / "phase5.sqlite"
    sql = """
    CREATE TABLE fund_profiles (
        fund_code TEXT PRIMARY KEY,
        fund_name TEXT,
        fund_type TEXT,
        asset_size REAL
    );
    CREATE TABLE nav_history (
        fund_code TEXT, nav_date TEXT, daily_growth_rate REAL,
        PRIMARY KEY (fund_code, nav_date)
    );
    CREATE TABLE stock_holdings (
        fund_code TEXT, stock_code TEXT, stock_name TEXT,
        report_period TEXT, net_value_ratio REAL
    );
    CREATE TABLE industry_allocations (
        fund_code TEXT, industry_name TEXT, report_period TEXT, net_value_ratio REAL
    );
    CREATE TABLE fund_manager_links (
        fund_code TEXT, manager_id TEXT, tenure_days INTEGER
    );
    CREATE TABLE fee_structures (
        fund_code TEXT, fee_type TEXT, condition_name TEXT, fee REAL
    );
    INSERT INTO fund_profiles VALUES ('000001','测试基金','股票型',12.0);
    INSERT INTO stock_holdings VALUES
        ('000001','600519','贵州茅台','2025-12-31',0.40),
        ('000001','601398','工商银行','2025-12-31',0.30);
    INSERT INTO industry_allocations VALUES
        ('000001','食品饮料','2025-12-31',0.60);
    INSERT INTO fund_manager_links VALUES ('000001','M1', 2200);
    INSERT INTO fee_structures VALUES
        ('000001','运作费用','管理费率',0.012),
        ('000001','运作费用','托管费率',0.002),
        ('000001','运作费用','销售服务费率',0.0);
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    # 几天的 NAV，避免数据不足
    for i in range(30):
        conn.execute(
            "INSERT INTO nav_history VALUES (?,?,?)",
            ("000001", f"2025-12-{i+1:02d}", 0.0005),
        )
    conn.commit()
    conn.close()
    return db


def _add_narrow_factors(db: Path) -> None:
    sql = """
    CREATE TABLE stock_factor_values (
        stock_code TEXT, factor_code TEXT, factor_value REAL,
        as_of_date TEXT, source TEXT,
        PRIMARY KEY (stock_code, factor_code, as_of_date)
    );
    INSERT INTO stock_factor_values VALUES
        ('600519','pb',1.0,'2025-12-31','fundamentals'),
        ('600519','valuation_percentile',0.10,'2025-12-31','fundamentals'),
        ('600519','roe',0.20,'2025-12-31','fundamentals'),
        ('600519','revenue_growth',0.18,'2025-12-31','fundamentals'),
        ('600519','dividend_yield',0.04,'2025-12-31','fundamentals'),
        ('601398','pb',0.8,'2025-12-31','fundamentals'),
        ('601398','valuation_percentile',0.15,'2025-12-31','fundamentals'),
        ('601398','roe',0.16,'2025-12-31','fundamentals'),
        ('601398','revenue_growth',0.16,'2025-12-31','fundamentals'),
        ('601398','dividend_yield',0.05,'2025-12-31','fundamentals');
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    conn.close()


def _add_wide_factors(db: Path) -> None:
    sql = """
    CREATE TABLE stock_factors (
        stock_code TEXT, factor_date TEXT, pb REAL, roe REAL,
        dividend_yield REAL, revenue_growth REAL, profit_growth REAL,
        market_cap_bucket TEXT, valuation_percentile REAL, style TEXT,
        PRIMARY KEY (stock_code, factor_date)
    );
    INSERT INTO stock_factors VALUES
        ('600519','2025-12-31',1.0,0.20,0.04,0.18,0.20,'large',0.10,'value'),
        ('601398','2025-12-31',0.8,0.16,0.05,0.16,0.10,'large',0.15,'value');
    """
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    conn.close()


def test_load_stock_factors_returns_empty_when_neither_table_exists(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(db).close()  # 建空库
    with sqlite3.connect(db) as conn:
        rows = load_stock_factors(conn, ["600519"], "2025-12-31")
    assert rows == []


def test_load_stock_factors_prefers_narrow_table(tmp_path: Path) -> None:
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)
    # 同时也插入宽表，但内容不同（pb=99 用来证明没被使用）
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE stock_factors (stock_code TEXT, factor_date TEXT, pb REAL,"
            " roe REAL, dividend_yield REAL, revenue_growth REAL, profit_growth REAL,"
            " market_cap_bucket TEXT, valuation_percentile REAL, style TEXT,"
            " PRIMARY KEY (stock_code, factor_date));"
            "INSERT INTO stock_factors VALUES "
            "('600519','2025-12-31',99,0,0,0,0,'large',1.0,'x');"
        )
        rows = load_stock_factors(conn, ["600519", "601398"], "2025-12-31")
    by_code = {r["stock_code"]: r for r in rows}
    # 走的是窄表，所以 pb=1.0 而不是 99
    assert by_code["600519"]["pb"] == 1.0
    assert by_code["600519"]["roe"] == 0.20


def test_load_stock_factors_falls_back_to_wide_when_narrow_missing(
    tmp_path: Path,
) -> None:
    db = _make_db_with_holdings(tmp_path)
    _add_wide_factors(db)  # 只装宽表
    with sqlite3.connect(db) as conn:
        rows = load_stock_factors(conn, ["600519", "601398"], "2025-12-31")
    by_code = {r["stock_code"]: r for r in rows}
    assert by_code["600519"]["pb"] == 1.0
    assert by_code["601398"]["pb"] == 0.8


def test_repository_loads_multi_period_factor_exposures(tmp_path: Path) -> None:
    db = tmp_path / "exposures.sqlite"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE fund_factor_exposures (
                fund_code TEXT,
                report_date TEXT,
                factor_code TEXT,
                exposure_value REAL,
                coverage_weight REAL,
                holding_total_weight REAL,
                stock_count INTEGER,
                covered_stock_count INTEGER,
                source TEXT,
                as_of_date TEXT,
                computed_at TEXT
            );
            INSERT INTO fund_factor_exposures VALUES
                ('000001','2025-03-31','deep_value_weight',0.62,0.85,0.70,2,2,'test','2025-03-31','now'),
                ('000001','2025-06-30','quality_growth_weight',0.58,0.86,0.70,2,2,'test','2025-06-30','now');
            """
        )

        rows = FundRepository._load_factor_exposures(conn, "000001", None)

    assert {row["report_date"] for row in rows} == {"2025-03-31", "2025-06-30"}


def test_funddata_repository_emits_style_labels_when_narrow_factors_provided(
    tmp_path: Path,
) -> None:
    """端到端：funddata schema + 窄表股票因子 → deep_value / quality_growth / dividend_steady 同时出。"""
    db = _make_db_with_holdings(tmp_path)
    _add_narrow_factors(db)

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    report = LabelRunReader(db).get_fund_report(run_id, "000001")
    assert report is not None
    label_codes = {item["label_code"] for item in report["labels"]}
    # 两只股票 weight=0.4 + 0.3 = 0.7 同时满足三类阈值
    assert "deep_value" in label_codes
    assert "quality_growth" in label_codes
    assert "dividend_steady" in label_codes
    assert "style_unlabeled_stock_factors_missing" not in label_codes
