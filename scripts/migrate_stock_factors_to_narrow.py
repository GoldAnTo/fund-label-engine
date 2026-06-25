"""把宽表 stock_factors 一次性迁移到窄表 stock_factor_values。

用法：
    python scripts/migrate_stock_factors_to_narrow.py /path/to/db.sqlite [--as-of 2025-12-31]

设计：
- 幂等：插入用 INSERT OR REPLACE。
- 只把宽表里非空的指标列写入窄表（每个 stock_code × factor_code × as_of_date 一条）。
- 不删除宽表，保留作为 fallback。
- as_of 默认取宽表里的 factor_date 字段；如 factor_date 为空可用 --as-of 覆盖。

迁移完成后 funddata_repository / repository 会自动改走窄表读取路径。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# 宽表列名 → 窄表 factor_code
WIDE_TO_NARROW: dict[str, str] = {
    "pb": "pb",
    "roe": "roe",
    "dividend_yield": "dividend_yield",
    "revenue_growth": "revenue_growth",
    "profit_growth": "profit_growth",
    "valuation_percentile": "valuation_percentile",
    "market_cap_bucket": "market_cap_bucket",
    "style": "style",
}


def migrate(db_path: str | Path, as_of_override: str | None = None) -> int:
    """从 stock_factors 宽表写入 stock_factor_values 窄表。返回插入条目数。"""
    conn = sqlite3.connect(str(db_path))
    try:
        # 确保窄表存在（同 0003 migration）
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stock_factor_values (
                stock_code TEXT NOT NULL,
                factor_code TEXT NOT NULL,
                factor_value REAL,
                as_of_date TEXT NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (stock_code, factor_code, as_of_date)
            );
            """
        )
        try:
            rows = conn.execute(
                "SELECT stock_code, factor_date, pb, roe, dividend_yield, "
                "revenue_growth, profit_growth, valuation_percentile "
                "FROM stock_factors"
            ).fetchall()
        except sqlite3.OperationalError:
            print("no wide stock_factors table found, nothing to migrate", file=sys.stderr)
            return 0

        columns = (
            "stock_code",
            "factor_date",
            "pb",
            "roe",
            "dividend_yield",
            "revenue_growth",
            "profit_growth",
            "valuation_percentile",
        )
        inserted = 0
        for row in rows:
            d = dict(zip(columns, row))
            as_of = as_of_override or d["factor_date"]
            if not as_of:
                continue
            for wide_col, factor_code in WIDE_TO_NARROW.items():
                value = d.get(wide_col)
                if value is None:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO stock_factor_values "
                    "(stock_code, factor_code, factor_value, as_of_date, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (d["stock_code"], factor_code, value, as_of, "migrated_from_wide"),
                )
                inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path", help="SQLite db path")
    parser.add_argument(
        "--as-of",
        help="若宽表里 factor_date 为空，可指定一个 as_of_date 覆盖。",
    )
    args = parser.parse_args()
    n = migrate(args.db_path, args.as_of)
    print(f"migrated {n} stock_factor_values entries")


if __name__ == "__main__":
    main()
