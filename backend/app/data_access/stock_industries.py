from __future__ import annotations

import sqlite3
from typing import Any


def load_stock_industry_map(
    conn: sqlite3.Connection,
    stock_codes: list[str],
    as_of: str | None = None,
) -> dict[str, dict[str, Any]]:
    codes = sorted({str(code) for code in stock_codes if code})
    if not codes or not _table_or_view_exists(conn, "stock_industry_map"):
        return {}

    original_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in codes)
        params: list[Any] = list(codes)
        date_filter = ""
        if as_of is not None:
            date_filter = "AND sim.as_of_date <= ?"
            params.append(as_of)

        sql = f"""
            SELECT sim.stock_code, sim.industry_code, sim.industry_name,
                   sim.sector_group, sim.source, sim.as_of_date
            FROM stock_industry_map sim
            JOIN (
                SELECT stock_code, MAX(as_of_date) AS max_date
                FROM stock_industry_map
                WHERE stock_code IN ({placeholders}) {date_filter}
                GROUP BY stock_code
            ) latest
              ON latest.stock_code = sim.stock_code
             AND latest.max_date = sim.as_of_date
            ORDER BY sim.stock_code
        """
        return {
            row["stock_code"]: dict(row)
            for row in conn.execute(sql, params).fetchall()
        }
    finally:
        conn.row_factory = original_factory


def _table_or_view_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    if row is not None:
        return True
    row = conn.execute(
        "SELECT name FROM sqlite_temp_master WHERE type='view' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
