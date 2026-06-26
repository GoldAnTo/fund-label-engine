import sqlite3
from pathlib import Path

from app.data_access.stock_industries import load_stock_industry_map


def test_load_stock_industry_map_returns_latest_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "industries.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600000", "801780", "银行", "financial", "fixture", "2025-12-31"),
                ("600000", "801780", "银行", "financial", "fixture", "2026-06-30"),
                ("600519", "801120", "食品饮料", "consumer", "fixture", "2026-06-30"),
            ],
        )
        rows = load_stock_industry_map(conn, ["600000", "600519", "000001"], None)

    assert rows["600000"]["industry_name"] == "银行"
    assert rows["600000"]["as_of_date"] == "2026-06-30"
    assert rows["600519"]["sector_group"] == "consumer"
    assert "000001" not in rows


def test_load_stock_industry_map_returns_empty_when_table_missing(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    with sqlite3.connect(db) as conn:
        rows = load_stock_industry_map(conn, ["600000"], None)

    assert rows == {}
