"""抓取股票主营业务构成，存入 factor cache DB 的 ``stock_revenue_composition`` 表。

数据源：东财 datacenter-web 接口（RPT_F10_FN_MAINOPCOMPO）。
按产品和按行业两种维度都抓取，用于收入暴露分析。

用法：
    # 从 source DB 读取持仓股票代码，逐只抓取主营构成
    python scripts/fetch_revenue_composition.py \\
        --source-db /tmp/fle-run/source.sqlite \\
        --factor-db data/stock_factors.sqlite

    # 只抓取指定股票
    python scripts/fetch_revenue_composition.py \\
        --factor-db data/stock_factors.sqlite \\
        --stocks 300308,600519,000858

    # 从CSV导入（备用方案，格式：stock_code,segment_name,segment_type,revenue_pct,report_date）
    python scripts/fetch_revenue_composition.py \\
        --factor-db data/stock_factors.sqlite \\
        --from-csv data/revenue_composition.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_FACTOR_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_revenue_composition (
    stock_code    TEXT NOT NULL,
    segment_name  TEXT NOT NULL,
    segment_type  TEXT NOT NULL,   -- 按产品 / 按行业
    revenue_pct   REAL,            -- 85.2 表示 85.2%
    report_date   TEXT NOT NULL,
    PRIMARY KEY (stock_code, segment_name, segment_type, report_date)
);
CREATE INDEX IF NOT EXISTS idx_revenue_composition_stock
    ON stock_revenue_composition (stock_code);
CREATE INDEX IF NOT EXISTS idx_revenue_composition_segment
    ON stock_revenue_composition (segment_name);
"""


def _to_secucode(stock_code: str) -> str:
    """A股代码转东财 SECUCODE 格式（600519 -> 600519.SH）。"""
    code = stock_code.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("8", "4")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _curl_get(url: str, retries: int = 3) -> dict:
    """用 curl 调东财接口，返回 JSON dict。"""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if not out.strip():
                raise ValueError("empty body")
            return json.loads(out)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2 + attempt * 2)
    assert last_exc is not None
    raise last_exc


def fetch_main_business(stock_code: str) -> list[dict[str, str | float | None]]:
    """抓取单只股票的主营业务构成。

    返回: [{"stock_code":..., "segment_name":..., "segment_type":..., "revenue_pct":..., "report_date":...}]
    """
    secucode = _to_secucode(stock_code)
    url = (
        "https://datacenter-web.eastmoney.com/api/data/v1/get"
        f"?reportName=RPT_F10_FN_MAINOPCOMPO"
        f"&columns=SECUCODE,SECURITY_CODE,REPORT_DATE,ITEM_TYPE,ITEM_NAME,MAIN_BUSINESS_INCOME,MAIN_BUSINESS_RATIO"
        f"&filter=(SECUCODE=%22{secucode}%22)"
        f"&pageNumber=1&pageSize=50"
        f"&sortColumns=REPORT_DATE&sortTypes=-1"
    )
    data = _curl_get(url)
    if not data or data.get("result") is None:
        return []

    rows = data["result"].get("data", []) or []
    result: list[dict[str, str | float | None]] = []
    for r in rows:
        item_type = r.get("ITEM_TYPE", "")
        # 只取"按产品"和"按行业"两种
        if item_type not in ("按产品", "按行业"):
            continue
        item_name = r.get("ITEM_NAME", "").strip()
        if not item_name:
            continue
        ratio = r.get("MAIN_BUSINESS_RATIO")
        try:
            revenue_pct = float(ratio) if ratio else None
        except (ValueError, TypeError):
            revenue_pct = None
        report_date = r.get("REPORT_DATE", "")[:10] if r.get("REPORT_DATE") else ""
        result.append({
            "stock_code": stock_code,
            "segment_name": item_name,
            "segment_type": item_type,
            "revenue_pct": revenue_pct,
            "report_date": report_date,
        })
    return result


def get_stock_codes_from_source_db(source_db: str) -> list[str]:
    """从 source DB 的 stock_holdings 表获取所有股票代码。"""
    conn = sqlite3.connect(source_db)
    rows = conn.execute(
        "SELECT DISTINCT stock_code FROM stock_holdings ORDER BY stock_code"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def import_from_csv(csv_path: str, factor_db: str) -> int:
    """从CSV导入主营业务构成（备用方案）。"""
    count = 0
    with sqlite3.connect(factor_db) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_revenue_composition "
                    "(stock_code, segment_name, segment_type, revenue_pct, report_date) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        row["stock_code"],
                        row["segment_name"],
                        row.get("segment_type", "按产品"),
                        float(row.get("revenue_pct", 0)),
                        row.get("report_date", "2025-12-31"),
                    ),
                )
                count += 1
        conn.commit()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取股票主营业务构成")
    parser.add_argument("--source-db", default=None, help="funddata source SQLite（从中读取股票代码）")
    parser.add_argument("--factor-db", default=str(DEFAULT_FACTOR_DB), help="factor cache SQLite")
    parser.add_argument("--stocks", default=None, help="只抓取指定股票（逗号分隔）")
    parser.add_argument("--from-csv", default=None, help="从CSV导入（备用方案）")
    parser.add_argument("--delay", type=float, default=0.3, help="请求间隔秒数")
    args = parser.parse_args(argv)

    factor_db = Path(args.factor_db)
    factor_db.parent.mkdir(parents=True, exist_ok=True)

    # CSV 导入模式
    if args.from_csv:
        count = import_from_csv(args.from_csv, str(factor_db))
        print(f"CSV导入完成: {count} 条记录 -> {factor_db}")
        return 0

    # 确定要抓取的股票代码
    if args.stocks:
        stock_codes = [s.strip() for s in args.stocks.split(",") if s.strip()]
    elif args.source_db:
        stock_codes = get_stock_codes_from_source_db(args.source_db)
    else:
        print("请指定 --source-db 或 --stocks 或 --from-csv")
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
            records = fetch_main_business(code)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i+1}/{len(stock_codes)}] {code} 失败: {exc}", flush=True)
            time.sleep(args.delay)
            continue

        if records:
            with sqlite3.connect(factor_db) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO stock_revenue_composition "
                    "(stock_code, segment_name, segment_type, revenue_pct, report_date) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        (r["stock_code"], r["segment_name"], r["segment_type"],
                         r["revenue_pct"], r["report_date"])
                        for r in records
                    ],
                )
                conn.commit()

        total += len(records)
        segments = ", ".join(r["segment_name"] for r in records[:3])
        print(
            f"  [{i+1}/{len(stock_codes)}] {code}: {len(records)} 条"
            + (f" ({segments}...)" if segments else ""),
            flush=True,
        )
        time.sleep(args.delay)

    # 统计
    with sqlite3.connect(factor_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM stock_revenue_composition"
        ).fetchone()[0]
        stock_count = conn.execute(
            "SELECT COUNT(DISTINCT stock_code) FROM stock_revenue_composition"
        ).fetchone()[0]

    print(f"\n完成: {stock_count} 只股票, {count} 条主营构成记录")
    print(f"数据库: {factor_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
