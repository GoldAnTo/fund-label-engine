"""抓取三大财务报表，存入 factor DB 的 ``stock_financial_statements`` 表。

数据源：akshare stock_financial_report_sina()（底层是新浪财经）。
抓取利润表、资产负债表、现金流量表，用于财务深度分析。

用法：
    # 从 source DB 读取持仓股票代码，逐只抓取三大报表
    python scripts/fetch_financial_statements.py \\
        --source-db /tmp/fle-run/source.sqlite \\
        --factor-db data/stock_factors.sqlite

    # 只抓取指定股票
    python scripts/fetch_financial_statements.py \\
        --factor-db data/stock_factors.sqlite \\
        --stocks 600519,000858
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_FACTOR_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_financial_statements (
    stock_code    TEXT NOT NULL,
    report_type   TEXT NOT NULL,      -- 利润表 / 资产负债表 / 现金流量表
    report_date   TEXT NOT NULL,      -- 2025-12-31
    revenue       REAL,              -- 营业收入（亿元）
    net_profit    REAL,              -- 净利润（亿元）
    gross_margin  REAL,              -- 毛利率(%)
    net_margin    REAL,              -- 净利率(%)
    roe           REAL,              -- 净资产收益率(%)
    debt_ratio    REAL,              -- 资产负债率(%)
    free_cashflow REAL,              -- 自由现金流（亿元）
    revenue_yoy   REAL,              -- 营收同比增速(%)
    profit_yoy    REAL,              -- 净利润同比增速(%)
    PRIMARY KEY (stock_code, report_type, report_date)
);
CREATE INDEX IF NOT EXISTS idx_financial_statements_stock
    ON stock_financial_statements (stock_code);
"""


def _to_sina_symbol(stock_code: str) -> str:
    """A股代码转新浪格式（600519 -> sh600519）。"""
    code = stock_code.strip()
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "2", "3")):
        return f"sz{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return f"sz{code}"


def fetch_financial(stock_code: str) -> list[dict[str, object]]:
    """抓取单只股票的三大财务报表关键指标。

    返回: [{"stock_code":..., "report_type":..., "report_date":..., ...}]
    """
    import akshare as ak

    symbol = _to_sina_symbol(stock_code)
    records: list[dict[str, object]] = []

    for report_type, label in [("利润表", "利润表"), ("资产负债表", "资产负债表"), ("现金流量表", "现金流量表")]:
        try:
            df = ak.stock_financial_report_sina(stock=symbol, symbol=report_type)
        except Exception:
            continue

        if df is None or df.empty:
            continue

        # 只取最近4期
        for _, row in df.head(4).iterrows():
            report_date = str(row.get("报告日", "")).strip()[:10]
            if not report_date:
                continue

            def _to_float(val) -> float | None:
                if val is None:
                    return None
                s = str(val).strip().replace(",", "").replace("%", "")
                if s in ("", "nan", "None", "--"):
                    return None
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return None

            record: dict[str, object] = {
                "stock_code": stock_code,
                "report_type": report_type,
                "report_date": report_date,
            }

            # 利润表特有字段
            if report_type == "利润表":
                record["revenue"] = _to_float(row.get("营业收入")) or _to_float(row.get("营业总收入"))
                record["net_profit"] = _to_float(row.get("净利润")) or _to_float(row.get("归属母公司股东的净利润"))
                record["gross_margin"] = _to_float(row.get("销售毛利率"))
                record["net_margin"] = _to_float(row.get("销售净利率"))
                record["revenue_yoy"] = _to_float(row.get("营业收入同比增长"))
                record["profit_yoy"] = _to_float(row.get("净利润同比增长"))

            # 资产负债表特有字段
            if report_type == "资产负债表":
                record["roe"] = _to_float(row.get("净资产收益率"))
                record["debt_ratio"] = _to_float(row.get("资产负债率"))

            # 现金流量表特有字段
            if report_type == "现金流量表":
                record["free_cashflow"] = _to_float(row.get("经营活动产生的现金流量净额"))

            records.append(record)

    return records


def get_stock_codes_from_source_db(source_db: str) -> list[str]:
    """从 source DB 的 stock_holdings 表获取所有股票代码。"""
    conn = sqlite3.connect(source_db)
    rows = conn.execute(
        "SELECT DISTINCT stock_code FROM stock_holdings ORDER BY stock_code"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取三大财务报表")
    parser.add_argument("--source-db", default=None, help="funddata source SQLite（从中读取股票代码）")
    parser.add_argument("--factor-db", default=str(DEFAULT_FACTOR_DB), help="factor cache SQLite")
    parser.add_argument("--stocks", default=None, help="只抓取指定股票（逗号分隔）")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数")
    args = parser.parse_args(argv)

    factor_db = Path(args.factor_db)
    factor_db.parent.mkdir(parents=True, exist_ok=True)

    # 确定要抓取的股票代码
    if args.stocks:
        stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]
    elif args.source_db:
        stock_codes = get_stock_codes_from_source_db(args.source_db)
    else:
        print("请指定 --source-db 或 --stocks")
        return 1

    print(f"待抓取股票: {len(stock_codes)} 只", flush=True)

    # 建表
    with sqlite3.connect(factor_db) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()

    # 逐只抓取
    total = 0
    for i, code in enumerate(stock_codes):
        try:
            records = fetch_financial(code)
        except Exception as exc:
            print(f"  [{i+1}/{len(stock_codes)}] {code} 失败: {exc}", flush=True)
            time.sleep(args.delay)
            continue

        if records:
            with sqlite3.connect(factor_db) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO stock_financial_statements "
                    "(stock_code, report_type, report_date, revenue, net_profit, "
                    "gross_margin, net_margin, roe, debt_ratio, free_cashflow, "
                    "revenue_yoy, profit_yoy) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r["stock_code"], r["report_type"], r["report_date"],
                            r.get("revenue"), r.get("net_profit"),
                            r.get("gross_margin"), r.get("net_margin"),
                            r.get("roe"), r.get("debt_ratio"),
                            r.get("free_cashflow"),
                            r.get("revenue_yoy"), r.get("profit_yoy"),
                        )
                        for r in records
                    ],
                )
                conn.commit()

        total += len(records)
        print(f"  [{i+1}/{len(stock_codes)}] {code}: {len(records)} 条报表数据", flush=True)
        time.sleep(args.delay)

    # 统计
    with sqlite3.connect(factor_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM stock_financial_statements"
        ).fetchone()[0]
        stock_count = conn.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM stock_financial_statements"
        ).fetchone()[0]

    print(f"\n完成: {stock_count} 只股票, {count} 条报表数据")
    print(f"数据库: {factor_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
