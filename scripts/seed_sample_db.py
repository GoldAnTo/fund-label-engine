"""Seed a small example SQLite database for the fund label engine.

Usage:
    python scripts/seed_sample_db.py data/sample_fund_data.sqlite

Produces 3 funds that cover:
- 000001: 数据充足，高集中度 + 经理任期长 + 费率低 + 缺少股票因子 -> 风格边界标签
- 000002: 数据不足（缺持仓、行业、经理等）-> 数据不足 + 人工复核
- 000003: 不被支持的基金类型（债券型）-> 不会进入批量
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS fund_profiles (
        fund_code TEXT PRIMARY KEY,
        fund_name TEXT NOT NULL,
        fund_type TEXT NOT NULL,
        inception_date TEXT,
        fund_company TEXT,
        fund_size REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nav_history (
        fund_code TEXT NOT NULL,
        nav_date TEXT NOT NULL,
        nav REAL,
        adjusted_nav REAL,
        daily_return REAL,
        PRIMARY KEY (fund_code, nav_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_stock_holdings (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        weight REAL NOT NULL,
        market TEXT,
        PRIMARY KEY (fund_code, report_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_industry_allocations (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        industry TEXT NOT NULL,
        weight REAL NOT NULL,
        PRIMARY KEY (fund_code, report_date, industry)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_manager_links (
        fund_code TEXT NOT NULL,
        manager_name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        tenure_years REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fee_structures (
        fund_code TEXT PRIMARY KEY,
        management_fee REAL,
        custody_fee REAL,
        sales_service_fee REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_positions (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        equity_position REAL,
        PRIMARY KEY (fund_code, report_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_factors (
        stock_code TEXT NOT NULL,
        factor_date TEXT NOT NULL,
        pb REAL,
        roe REAL,
        dividend_yield REAL,
        revenue_growth REAL,
        profit_growth REAL,
        market_cap_bucket TEXT,
        valuation_percentile REAL,
        style TEXT,
        PRIMARY KEY (stock_code, factor_date)
    )
    """,
)


def seed(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)

        conn.executemany(
            "INSERT INTO fund_profiles VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("000001", "样例消费股票", "股票型", "2015-01-01", "样例基金公司", 180.0),
                ("000002", "样例数据不全混合", "混合型-偏股", "2020-01-01", "样例基金公司", 12.0),
                ("000003", "样例债券基金", "债券型", "2018-01-01", "样例基金公司", 50.0),
            ],
        )

        conn.executemany(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            [
                ("000001", "2026-06-18", 1.20, 1.20, 0.010),
                ("000001", "2026-06-19", 1.19, 1.19, -0.008),
                ("000001", "2026-06-20", 1.21, 1.21, 0.017),
                ("000001", "2026-06-21", 1.22, 1.22, 0.008),
                ("000001", "2026-06-22", 1.21, 1.21, -0.008),
            ],
        )

        report_date = "2026-03-31"
        holdings = [
            ("600519", "贵州茅台", 0.11),
            ("000858", "五粮液", 0.09),
            ("000568", "泸州老窖", 0.08),
            ("600887", "伊利股份", 0.07),
            ("300750", "宁德时代", 0.06),
            ("002594", "比亚迪", 0.05),
            ("601318", "中国平安", 0.04),
            ("600036", "招商银行", 0.04),
            ("000333", "美的集团", 0.035),
            ("600276", "恒瑞医药", 0.035),
        ]
        conn.executemany(
            "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("000001", report_date, code, name, weight, "A")
                for code, name, weight in holdings
            ],
        )

        conn.executemany(
            "INSERT INTO fund_industry_allocations VALUES (?, ?, ?, ?)",
            [
                ("000001", report_date, "食品饮料", 0.46),
                ("000001", report_date, "电力设备", 0.11),
                ("000001", report_date, "银行", 0.08),
            ],
        )

        conn.executemany(
            "INSERT INTO fund_manager_links VALUES (?, ?, ?, ?, ?)",
            [
                ("000001", "张三", "2020-01-01", None, 6.2),
                ("000002", "李四", "2024-01-01", None, 1.5),
            ],
        )

        conn.executemany(
            "INSERT INTO fee_structures VALUES (?, ?, ?, ?)",
            [
                ("000001", 0.010, 0.002, None),
                ("000002", 0.015, 0.0025, None),
            ],
        )

        conn.executemany(
            "INSERT INTO fund_positions VALUES (?, ?, ?)",
            [
                ("000001", report_date, 0.89),
            ],
        )

        conn.commit()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: seed_sample_db.py <db_path>", file=sys.stderr)
        return 2
    seed(argv[0])
    print(f"seeded: {argv[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
