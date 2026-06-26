from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.label_engine.engine import SUPPORTED_ACTIVE_EQUITY_TYPES, FundInput


class FundRepository:
    """按 docs/data-contract.md 的表结构从 SQLite 装配 FundInput。"""

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        self._db_path = str(db_path)
        self._read_only = read_only

    def _connect(self) -> sqlite3.Connection:
        if self._read_only:
            uri = f"file:{self._db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_supported_fund_codes(self) -> list[str]:
        """返回 fund_type 落在支持类型集合内的基金代码。"""
        placeholders = ",".join("?" for _ in SUPPORTED_ACTIVE_EQUITY_TYPES)
        sql = (
            f"SELECT fund_code FROM fund_profiles "
            f"WHERE fund_type IN ({placeholders}) ORDER BY fund_code"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(SUPPORTED_ACTIVE_EQUITY_TYPES)).fetchall()
        return [row["fund_code"] for row in rows]

    def list_all_fund_codes(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fund_code FROM fund_profiles ORDER BY fund_code"
            ).fetchall()
        return [row["fund_code"] for row in rows]

    def load_fund_input(self, fund_code: str) -> FundInput | None:
        """读取单只基金的全部输入数据，找不到 profile 返回 None。"""
        with self._connect() as conn:
            profile = conn.execute(
                "SELECT fund_code, fund_name, fund_type, fund_size "
                "FROM fund_profiles WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()
            if profile is None:
                return None

            nav_returns = [
                row["daily_return"]
                for row in conn.execute(
                    "SELECT daily_return FROM nav_history "
                    "WHERE fund_code = ? AND daily_return IS NOT NULL "
                    "ORDER BY nav_date",
                    (fund_code,),
                ).fetchall()
            ]
            benchmark_returns = self._load_benchmark_returns(conn, fund_code)

            latest_holding_date = conn.execute(
                "SELECT MAX(report_date) AS d FROM fund_stock_holdings "
                "WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()["d"]
            stock_holdings = self._rows_to_dicts(
                conn,
                "SELECT stock_code, stock_name, weight, market "
                "FROM fund_stock_holdings "
                "WHERE fund_code = ? AND report_date = ? "
                "ORDER BY weight DESC",
                (fund_code, latest_holding_date) if latest_holding_date else None,
            )

            latest_industry_date = conn.execute(
                "SELECT MAX(report_date) AS d FROM fund_industry_allocations "
                "WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()["d"]
            industry_allocations = self._rows_to_dicts(
                conn,
                "SELECT industry, weight FROM fund_industry_allocations "
                "WHERE fund_code = ? AND report_date = ? "
                "ORDER BY weight DESC",
                (fund_code, latest_industry_date) if latest_industry_date else None,
            )

            stock_codes = [item["stock_code"] for item in stock_holdings]
            stock_factors = self._load_latest_stock_factors(
                conn,
                stock_codes,
                as_of=latest_holding_date,
            )
            factor_exposures = self._load_factor_exposures(
                conn,
                fund_code,
                latest_holding_date,
            )

            manager_row = conn.execute(
                "SELECT MAX(tenure_years) AS tenure FROM fund_manager_links "
                "WHERE fund_code = ? AND (end_date IS NULL OR end_date = '')",
                (fund_code,),
            ).fetchone()
            manager_tenure = (
                manager_row["tenure"] if manager_row and manager_row["tenure"] is not None else None
            )

            fee_row = conn.execute(
                "SELECT management_fee, custody_fee, sales_service_fee "
                "FROM fee_structures WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()

            equity_row = conn.execute(
                "SELECT equity_position FROM fund_positions "
                "WHERE fund_code = ? ORDER BY report_date DESC LIMIT 1",
                (fund_code,),
            ).fetchone()
            equity_position = (
                equity_row["equity_position"]
                if equity_row and equity_row["equity_position"] is not None
                else None
            )

        return FundInput(
            fund_code=profile["fund_code"],
            fund_name=profile["fund_name"],
            fund_type=profile["fund_type"],
            nav_returns=nav_returns,
            stock_holdings=stock_holdings,
            industry_allocations=industry_allocations,
            stock_factors=stock_factors,
            factor_exposures=factor_exposures,
            benchmark_returns=benchmark_returns,
            manager_tenure_years=manager_tenure,
            management_fee=fee_row["management_fee"] if fee_row else None,
            custody_fee=fee_row["custody_fee"] if fee_row else None,
            sales_service_fee=fee_row["sales_service_fee"] if fee_row else None,
            fund_size=profile["fund_size"],
            equity_position=equity_position,
            holding_report_date=latest_holding_date,
            industry_report_date=latest_industry_date,
        )

    @staticmethod
    def _rows_to_dicts(
        conn: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...] | None,
    ) -> list[dict[str, Any]]:
        if params is None:
            return []
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _load_factor_exposures(
        conn: sqlite3.Connection,
        fund_code: str,
        as_of: str | None,
    ) -> list[dict[str, Any]]:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fund_factor_exposures'"
        ).fetchone()
        if table is None:
            return []

        if as_of is None:
            rows = conn.execute(
                "SELECT fund_code, report_date, factor_code, exposure_value, "
                "coverage_weight, holding_total_weight, stock_count, covered_stock_count, "
                "source, as_of_date, computed_at "
                "FROM fund_factor_exposures WHERE fund_code = ? "
                "ORDER BY report_date, factor_code",
                (fund_code,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT fund_code, report_date, factor_code, exposure_value, "
                "coverage_weight, holding_total_weight, stock_count, covered_stock_count, "
                "source, as_of_date, computed_at "
                "FROM fund_factor_exposures WHERE fund_code = ? AND report_date <= ? "
                "ORDER BY report_date, factor_code",
                (fund_code, as_of),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _load_benchmark_returns(
        conn: sqlite3.Connection,
        fund_code: str,
    ) -> list[float]:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_returns'"
        ).fetchone()
        if table is None:
            return []
        rows = conn.execute(
            "SELECT daily_return FROM benchmark_returns "
            "WHERE fund_code = ? AND daily_return IS NOT NULL ORDER BY trade_date",
            (fund_code,),
        ).fetchall()
        return [row["daily_return"] for row in rows]

    @staticmethod
    def _load_latest_stock_factors(
        conn: sqlite3.Connection,
        stock_codes: list[str],
        as_of: str | None,
    ) -> list[dict[str, Any]]:
        from app.data_access.stock_factors import load_stock_factors

        return load_stock_factors(conn, stock_codes, as_of)

    def load_stock_industry_map(
        self,
        stock_codes: list[str],
        as_of: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            from app.data_access.stock_industries import load_stock_industry_map

            return load_stock_industry_map(conn, stock_codes, as_of)
