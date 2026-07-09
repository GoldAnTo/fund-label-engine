"""抓取北向资金数据，存入 factor DB 的 ``northbound_capital`` 表。

数据源：akshare stock_hsgt_*()（底层是东方财富）。
抓取北向资金每日净流入和个股北向持股数据。

用法：
    # 抓取最近30天北向资金数据
    python scripts/fetch_northbound_capital.py \\
        --factor-db data/stock_factors.sqlite \\
        --days 30

    # 从 source DB 读取持仓股票，抓取个股北向持股
    python scripts/fetch_northbound_capital.py \\
        --source-db /tmp/fle-run/source.sqlite \\
        --factor-db data/stock_factors.sqlite
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_FACTOR_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS northbound_capital (
    stock_code    TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    hold_shares   REAL,           -- 持股数量（万股）
    hold_value    REAL,           -- 持股市值（万元）
    hold_pct      REAL,           -- 持股比例(%)
    net_buy      REAL,           -- 当日净买入（万元）
    PRIMARY KEY (stock_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_northbound_date
    ON northbound_capital (trade_date);

CREATE TABLE IF NOT EXISTS northbound_daily (
    trade_date    TEXT PRIMARY KEY,
    sh_net_flow    REAL,          -- 沪股通净流入（万元）
    sz_net_flow    REAL,          -- 深股通净流入（万元）
    total_net_flow REAL,         -- 合计净流入（万元）
    sh_balance    REAL,          -- 沪股通余额（万元）
    sz_balance    REAL,          -- 深股通余额（万元）
);
"""


def fetch_daily_flow(days: int = 30) -> list[dict[str, object]]:
    """抓取北向资金每日净流入汇总数据。"""
    import akshare as ak

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    records: list[dict[str, object]] = []
    try:
        # 北向资金每日净流入
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            # 只取最近 days 天
            df = df.tail(days)
            for _, row in df.iterrows():
                trade_date = str(row.get("日期", "")).strip()[:10]
                if not trade_date:
                    continue
                net_flow = row.get("当日资金流入", None)
                try:
                    net_flow = float(net_flow) if net_flow and str(net_flow) != "nan" else None
                except (ValueError, TypeError):
                    net_flow = None
                records.append({
                    "trade_date": trade_date,
                    "total_net_flow": net_flow,
                    "sh_net_flow": None,
                    "sz_net_flow": None,
                    "sh_balance": None,
                    "sz_balance": None,
                })
    except Exception as exc:
        print(f"北向资金汇总数据抓取失败: {exc}", file=sys.stderr)

    return records


def fetch_stock_holding(stock_code: str) -> list[dict[str, object]]:
    """抓取单只股票的北向持股历史。"""
    import akshare as ak

    records: list[dict[str, object]] = []
    try:
        df = ak.stock_hsgt_individual_em(stock=stock_code)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                trade_date = str(row.get("日期", "")).strip()[:10]
                if not trade_date:
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

                records.append({
                    "stock_code": stock_code,
                    "trade_date": trade_date,
                    "hold_shares": _to_float(row.get("持股数量")),
                    "hold_value": _to_float(row.get("持股市值")),
                    "hold_pct": _to_float(row.get("持股比例")),
                    "net_buy": _to_float(row.get("当日买入")) or _to_float(row.get("当日成交净买额")),
                })
    except Exception:
        pass

    return records


def get_stock_codes_from_source_db(source_db: str) -> list[str]:
    conn = sqlite3.connect(source_db)
    rows = conn.execute(
        "SELECT DISTINCT stock_code FROM stock_holdings ORDER BY stock_code"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取北向资金数据")
    parser.add_argument("--source-db", default=None, help="source SQLite（从中读取股票代码）")
    parser.add_argument("--factor-db", default=str(DEFAULT_FACTOR_DB), help="factor cache SQLite")
    parser.add_argument("--stocks", default=None, help="只抓取指定股票（逗号分隔）")
    parser.add_argument("--days", type=int, default=30, help="抓取最近N天汇总数据")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数")
    args = parser.parse_args(argv)

    factor_db = Path(args.factor_db)
    factor_db.parent.mkdir(parents=True, exist_ok=True)

    # 建表
    with sqlite3.connect(factor_db) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()

    # 1. 抓取北向资金每日汇总
    print("正在抓取北向资金每日汇总...", flush=True)
    daily_records = fetch_daily_flow(args.days)
    if daily_records:
        with sqlite3.connect(factor_db) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO northbound_daily "
                "(trade_date, sh_net_flow, sz_net_flow, total_net_flow, sh_balance, sz_balance) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        r["trade_date"], r.get("sh_net_flow"), r.get("sz_net_flow"),
                        r.get("total_net_flow"), r.get("sh_balance"), r.get("sz_balance"),
                    )
                    for r in daily_records
                ],
            )
            conn.commit()
        print(f"北向汇总: {len(daily_records)} 天数据", flush=True)

    # 2. 抓取个股北向持股
    if args.stocks:
        stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]
    elif args.source_db:
        stock_codes = get_stock_codes_from_source_db(args.source_db)
    else:
        stock_codes = []

    if stock_codes:
        print(f"\n开始抓取 {len(stock_codes)} 只股票的北向持股...", flush=True)
        total = 0
        for i, code in enumerate(stock_codes):
            try:
                records = fetch_stock_holding(code)
            except Exception as exc:
                print(f"  [{i+1}/{len(stock_codes)}] {code} 失败: {exc}", flush=True)
                time.sleep(args.delay)
                continue

            if records:
                with sqlite3.connect(factor_db) as conn:
                    conn.executemany(
                        "INSERT OR REPLACE INTO northbound_capital "
                        "(stock_code, trade_date, hold_shares, hold_value, hold_pct, net_buy) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (
                                r["stock_code"], r["trade_date"],
                                r.get("hold_shares"), r.get("hold_value"),
                                r.get("hold_pct"), r.get("net_buy"),
                            )
                            for r in records
                        ],
                    )
                    conn.commit()

            total += len(records)
            print(f"  [{i+1}/{len(stock_codes)}] {code}: {len(records)} 条", flush=True)
            time.sleep(args.delay)

        print(f"\n个股北向: {total} 条记录", flush=True)

    # 统计
    with sqlite3.connect(factor_db) as conn:
        daily_count = conn.execute("SELECT COUNT(*) FROM northbound_daily").fetchone()[0]
        stock_count = conn.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM northbound_capital"
        ).fetchone()[0]

    print(f"\n完成: {daily_count} 天汇总, {stock_count} 只个股")
    print(f"数据库: {factor_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
