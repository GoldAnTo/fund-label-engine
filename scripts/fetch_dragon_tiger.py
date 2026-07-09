"""抓取龙虎榜数据，存入 factor DB 的 ``dragon_tiger_list`` 表。

数据源：akshare stock_lhb_detail_em()（底层是东方财富）。
抓取指定日期范围内的龙虎榜明细，用于游资动向分析。

用法：
    # 抓取最近30天龙虎榜
    python scripts/fetch_dragon_tiger.py \\
        --factor-db data/stock_factors.sqlite \\
        --days 30

    # 指定日期范围
    python scripts/fetch_dragon_tiger.py \\
        --factor-db data/stock_factors.sqlite \\
        --start 20260101 --end 20260131
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
CREATE TABLE IF NOT EXISTS dragon_tiger_list (
    stock_code    TEXT NOT NULL,
    stock_name    TEXT,
    trade_date    TEXT NOT NULL,
    reason        TEXT,            -- 上榜原因
    close_price   REAL,            -- 收盘价
    change_pct    REAL,            -- 涨跌幅(%)
    net_buy      REAL,            -- 净买入额（万元）
    buy_amount    REAL,            -- 买入额（万元）
    sell_amount   REAL,            -- 卖出额（万元）
    PRIMARY KEY (stock_code, trade_date, reason)
);
CREATE INDEX IF NOT EXISTS idx_dragon_tiger_date
    ON dragon_tiger_list (trade_date);
CREATE INDEX IF NOT EXISTS idx_dragon_tiger_stock
    ON dragon_tiger_list (stock_code);
"""


def fetch_lhb(start_date: str, end_date: str) -> list[dict[str, object]]:
    """抓取指定日期范围内的龙虎榜明细。"""
    import akshare as ak

    records: list[dict[str, object]] = []

    try:
        df = ak.stock_lhb_detail_em(
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        print(f"龙虎榜抓取失败: {exc}", file=sys.stderr)
        return records

    if df is None or df.empty:
        return records

    for _, row in df.iterrows():
        stock_code = str(row.get("代码", "")).strip().zfill(6)
        if not stock_code:
            continue

        def _to_float(val) -> float | None:
            if val is None:
                return None
            s = str(val).strip().replace(",", "").replace("%", "").replace("万", "")
            if s in ("", "nan", "None", "--"):
                return None
            try:
                return float(s)
            except (ValueError, TypeError):
                return None

        trade_date = str(row.get("上榜日", "")).strip()[:10]
        if not trade_date:
            continue

        records.append({
            "stock_code": stock_code,
            "stock_name": str(row.get("名称", "")).strip(),
            "trade_date": trade_date,
            "reason": str(row.get("解读", "")).strip(),
            "close_price": _to_float(row.get("收盘价")),
            "change_pct": _to_float(row.get("涨跌幅")),
            "net_buy": _to_float(row.get("龙虎榜净买额")),
            "buy_amount": _to_float(row.get("龙虎榜买入额")),
            "sell_amount": _to_float(row.get("龙虎榜卖出额")),
        })

    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取龙虎榜数据")
    parser.add_argument("--factor-db", default=str(DEFAULT_FACTOR_DB), help="factor cache SQLite")
    parser.add_argument("--days", type=int, default=30, help="抓取最近N天")
    parser.add_argument("--start", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    args = parser.parse_args(argv)

    factor_db = Path(args.factor_db)
    factor_db.parent.mkdir(parents=True, exist_ok=True)

    # 确定日期范围
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")

    print(f"抓取龙虎榜: {start_date} ~ {end_date}", flush=True)

    # 建表
    with sqlite3.connect(factor_db) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()

    # 分段抓取（每次最多30天，避免超时）
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    total = 0

    while start_dt <= end_dt:
        chunk_end = min(start_dt + timedelta(days=30), end_dt)
        chunk_start_str = start_dt.strftime("%Y%m%d")
        chunk_end_str = chunk_end.strftime("%Y%m%d")

        print(f"  抓取 {chunk_start_str} ~ {chunk_end_str}...", flush=True, end=" ")
        try:
            records = fetch_lhb(chunk_start_str, chunk_end_str)
        except Exception as exc:
            print(f"失败: {exc}", flush=True)
            start_dt = chunk_end + timedelta(days=1)
            time.sleep(1)
            continue

        if records:
            with sqlite3.connect(factor_db) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO dragon_tiger_list "
                    "(stock_code, stock_name, trade_date, reason, "
                    "close_price, change_pct, net_buy, buy_amount, sell_amount) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r["stock_code"], r["stock_name"], r["trade_date"],
                            r.get("reason"), r.get("close_price"),
                            r.get("change_pct"), r.get("net_buy"),
                            r.get("buy_amount"), r.get("sell_amount"),
                        )
                        for r in records
                    ],
                )
                conn.commit()

        total += len(records)
        print(f"{len(records)} 条", flush=True)
        start_dt = chunk_end + timedelta(days=1)
        time.sleep(0.5)

    # 统计
    with sqlite3.connect(factor_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM dragon_tiger_list").fetchone()[0]
        stock_count = conn.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM dragon_tiger_list"
        ).fetchone()[0]

    print(f"\n完成: {stock_count} 只股票, {count} 条龙虎榜记录")
    print(f"数据库: {factor_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
