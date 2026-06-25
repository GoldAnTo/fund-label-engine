"""SQLite data access for fund label engine."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.data_access.funddata_repository import FundDataRepository
from app.data_access.repository import FundRepository


def create_repository(
    db_path: str | Path,
    source: str = "auto",
    read_only: bool = False,
    factor_db_path: str | Path | None = None,
) -> FundRepository | FundDataRepository:
    if source == "engine":
        return FundRepository(db_path, read_only=read_only)
    if source == "funddata":
        return FundDataRepository(
            db_path, read_only=read_only, factor_db_path=factor_db_path
        )
    if source != "auto":
        raise ValueError(f"unknown data source: {source}")

    tables = _table_names(db_path)
    if "fund_stock_holdings" in tables:
        return FundRepository(db_path, read_only=read_only)
    if "stock_holdings" in tables:
        return FundDataRepository(
            db_path, read_only=read_only, factor_db_path=factor_db_path
        )
    raise ValueError(
        "could not detect data source. Expected engine schema or fundData schema."
    )


def _table_names(db_path: str | Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


__all__ = ["FundDataRepository", "FundRepository", "create_repository"]
