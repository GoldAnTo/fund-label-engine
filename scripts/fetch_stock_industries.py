"""导入股票行业映射到 factor cache DB 的 ``stock_industry_map`` 表。

MVP：以 CSV 导入为确定性入口，先覆盖红利贡献高频股票（金融 / 能源公用 /
消费 / 其它四组）。表结构与 migration
``backend/app/persistence/migrations/0009_stock_industry_map.sql`` 一致，
可被 ``load_stock_industry_map`` 直接读取。

CSV 列：stock_code, industry_code, industry_name, sector_group
sector_group 取值：financial / energy_utility / consumer / other

用法：
    python scripts/fetch_stock_industries.py \\
        --db data/stock_factors.sqlite \\
        --from-csv data/stock_industry_seed.mvp.csv \\
        --as-of-date 2026-06-26 \\
        --source manual.mvp_dividend_sector_seed
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"
VALID_SECTOR_GROUPS = {"financial", "energy_utility", "consumer", "other"}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_industry_map (
    stock_code TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    sector_group TEXT NOT NULL CHECK (
        sector_group IN ('financial', 'energy_utility', 'consumer', 'other')
    ),
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    PRIMARY KEY (stock_code, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_stock_industry_map_sector
    ON stock_industry_map (sector_group, as_of_date);
"""


def import_csv(
    conn: sqlite3.Connection,
    csv_path: Path,
    as_of_date: str,
    source: str,
) -> int:
    rows = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for item in reader:
            stock_code = (item.get("stock_code") or "").strip()
            industry_code = (item.get("industry_code") or "").strip() or "manual"
            industry_name = (item.get("industry_name") or "").strip()
            sector_group = (item.get("sector_group") or "").strip()
            if (
                not stock_code
                or not industry_name
                or sector_group not in VALID_SECTOR_GROUPS
            ):
                continue
            conn.execute(
                "INSERT OR REPLACE INTO stock_industry_map "
                "(stock_code, industry_code, industry_name, sector_group, source, as_of_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (stock_code, industry_code, industry_name, sector_group, source, as_of_date),
            )
            rows += 1
    conn.commit()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--from-csv", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--source", default="manual.mvp_dividend_sector_seed")
    args = parser.parse_args()

    csv_path = Path(args.from_csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    conn = sqlite3.connect(args.db)
    try:
        conn.executescript(CREATE_TABLE_SQL)
        inserted = import_csv(conn, csv_path, args.as_of_date, args.source)
    finally:
        conn.close()
    print(f"inserted {inserted} stock_industry_map rows from {csv_path}")


if __name__ == "__main__":
    main()
