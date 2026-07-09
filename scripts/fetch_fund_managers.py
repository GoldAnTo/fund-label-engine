"""抓取基金经理数据，存入 source DB 的 ``fund_managers`` 表。

数据源：akshare fund_manager_em()（底层是东方财富）。
抓取全市场基金经理的任职信息、管理规模、任职回报。

用法：
    # 抓取全部基金经理数据
    python scripts/fetch_fund_managers.py --source-db /tmp/fle-run/source.sqlite

    # 从CSV导入（备用方案）
    # CSV格式: fund_code,fund_name,manager_name,start_date,end_date,tenure_days,return_pct,aum_yi,is_current
    python scripts/fetch_fund_managers.py --source-db /tmp/fle-run/source.sqlite --from-csv data/fund_managers.csv
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS fund_managers (
    fund_code     TEXT NOT NULL,
    fund_name     TEXT,
    manager_name  TEXT NOT NULL,
    start_date    TEXT,
    end_date      TEXT,
    tenure_days   INTEGER,
    return_pct    REAL,
    aum_yi        REAL,
    is_current    INTEGER DEFAULT 1,
    PRIMARY KEY (fund_code, manager_name, start_date)
);
CREATE INDEX IF NOT EXISTS idx_fund_managers_code ON fund_managers (fund_code);
CREATE INDEX IF NOT EXISTS idx_fund_managers_current ON fund_managers (fund_code, is_current);
"""


def fetch_via_akshare() -> list[dict[str, object]]:
    """用akshare抓取全市场基金经理数据。"""
    import akshare as ak

    df = ak.fund_manager_em()
    if df is None or df.empty:
        return []

    records: list[dict[str, object]] = []
    for _, row in df.iterrows():
        fund_code = str(row.get("基金代码", "")).strip().zfill(6)
        if not fund_code:
            continue

        manager_name = str(row.get("基金经理", "")).strip()
        if not manager_name:
            continue

        # 任职起始日期
        start_date = str(row.get("任职日期", "")).strip()[:10] if row.get("任职日期") else ""

        # 离任日期
        end_date_raw = row.get("离任日期", "")
        end_date = str(end_date_raw).strip()[:10] if end_date_raw and str(end_date_raw).strip() != "NaT" else ""
        is_current = 0 if end_date else 1

        # 任职天数
        tenure_days = row.get("任职天数", None)
        try:
            tenure_days = int(tenure_days) if tenure_days and str(tenure_days) != "nan" else None
        except (ValueError, TypeError):
            tenure_days = None

        # 任职回报
        return_pct = row.get("任职回报", None)
        try:
            return_pct = float(return_pct) if return_pct and str(return_pct) != "nan" else None
        except (ValueError, TypeError):
            return_pct = None

        # 管理规模（亿元）
        aum = row.get("管理规模", None) or row.get("基金规模", None)
        try:
            aum_yi = float(aum) if aum and str(aum) != "nan" else None
        except (ValueError, TypeError):
            aum_yi = None

        records.append({
            "fund_code": fund_code,
            "fund_name": str(row.get("基金简称", "")).strip(),
            "manager_name": manager_name,
            "start_date": start_date,
            "end_date": end_date,
            "tenure_days": tenure_days,
            "return_pct": return_pct,
            "aum_yi": aum_yi,
            "is_current": is_current,
        })

    return records


def import_from_csv(csv_path: str, source_db: str) -> int:
    """从CSV导入基金经理数据（备用方案）。"""
    count = 0
    with sqlite3.connect(source_db) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_managers "
                    "(fund_code, fund_name, manager_name, start_date, end_date, "
                    "tenure_days, return_pct, aum_yi, is_current) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["fund_code"],
                        row.get("fund_name", ""),
                        row["manager_name"],
                        row.get("start_date", ""),
                        row.get("end_date", ""),
                        int(row.get("tenure_days", 0)) or None,
                        float(row.get("return_pct", 0)) or None,
                        float(row.get("aum_yi", 0)) or None,
                        int(row.get("is_current", 1)),
                    ),
                )
                count += 1
        conn.commit()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取基金经理数据")
    parser.add_argument("--source-db", required=True, help="source SQLite 数据库路径")
    parser.add_argument("--from-csv", default=None, help="从CSV导入（备用方案）")
    args = parser.parse_args(argv)

    db_path = Path(args.source_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # CSV 导入模式
    if args.from_csv:
        count = import_from_csv(args.from_csv, str(db_path))
        print(f"CSV导入完成: {count} 条基金经理记录 -> {db_path}")
        return 0

    # akshare 抓取
    print("正在通过akshare抓取基金经理数据...", flush=True)
    try:
        records = fetch_via_akshare()
    except Exception as exc:
        print(f"akshare抓取失败: {exc}", file=sys.stderr)
        print("提示: 可使用 --from-csv 从CSV导入", file=sys.stderr)
        return 1

    if not records:
        print("未获取到基金经理数据")
        return 0

    # 写入SQLite
    with sqlite3.connect(db_path) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.executemany(
            "INSERT OR REPLACE INTO fund_managers "
            "(fund_code, fund_name, manager_name, start_date, end_date, "
            "tenure_days, return_pct, aum_yi, is_current) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["fund_code"], r["fund_name"], r["manager_name"],
                    r["start_date"], r["end_date"], r["tenure_days"],
                    r["return_pct"], r["aum_yi"], r["is_current"],
                )
                for r in records
            ],
        )
        conn.commit()

        # 统计
        total = conn.execute("SELECT COUNT(*) FROM fund_managers").fetchone()[0]
        current = conn.execute(
            "SELECT COUNT(*) FROM fund_managers WHERE is_current = 1"
        ).fetchone()[0]
        funds = conn.execute(
            "SELECT COUNT(DISTINCT fund_code) FROM fund_managers"
        ).fetchone()[0]

    print(f"\n完成: {funds} 只基金, {total} 条经理记录 ({current} 条在任)")
    print(f"数据库: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
