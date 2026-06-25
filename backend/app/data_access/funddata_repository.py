from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.label_engine.engine import SUPPORTED_ACTIVE_EQUITY_TYPES, FundInput


# 真库里大量 ETF / LOF 在 fee_structures 表只存了「场内ETF-无费率信息」
# 这一占位行，没有标准的「管理费率/托管费率/销售服务费率」三件套。
# 这种情况下视为 ETF 隐含费率：management/custody/sales 三项都按 0 兜底，
# 让 fee_structure gate 能通过；evidence 仍会显示 total_annual_fee=0，
# 留给复核判断是否需要打补丁。
_ETF_NO_FEE_CONDITION = "场内ETF-无费率信息"


def _read_phase1_codes() -> set[str] | None:
    """读取 FLE_PHASE1_CODES_FILE 指向的清单，每行一个 fund_code。

    返回 None 表示不启用首期范围过滤（默认行为，向后兼容）。
    """
    path = os.environ.get("FLE_PHASE1_CODES_FILE")
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    codes: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        code = line.strip()
        if code and not code.startswith("#"):
            codes.add(code)
    return codes or None


class FundDataRepository:
    """Read the existing fundData SQLite schema and adapt it to FundInput."""

    def __init__(
        self,
        db_path: str | Path,
        read_only: bool = False,
        factor_db_path: str | Path | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._read_only = read_only
        # 外挂 factor cache DB（由 backend/scripts/fetch_stock_factors.py 生成）。
        # 若为 None，则继续在主库里查 stock_factor_values / stock_factors
        # （兼容 sample seed 和 fundData 真库自带的旧表）。
        self._factor_db_path = str(factor_db_path) if factor_db_path else None

    def _connect(self) -> sqlite3.Connection:
        if self._read_only:
            uri = f"file:{self._db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        # 把外挂 factor DB 以 schema 名 ``factordb`` 挂上，使
        # ``factordb.stock_factor_values`` 可在同一连接里被查询。
        # 透明 ATTACH 后，``load_stock_factors`` 仍然只看到 ``stock_factor_values``
        # 这个名字 —— 通过下面的 view 让它指向 factordb。
        if self._factor_db_path:
            conn.execute("ATTACH DATABASE ? AS factordb", (self._factor_db_path,))
            # 避免与主库里同名表冲突：只在主库里没有 stock_factor_values
            # 数据时才建 view。检查方法：主库表是否存在；存在则保持原行为。
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='stock_factor_values'"
            ).fetchone()
            if row is None:
                conn.execute(
                    "CREATE TEMP VIEW stock_factor_values AS "
                    "SELECT * FROM factordb.stock_factor_values"
                )
        return conn

    def list_supported_fund_codes(self) -> list[str]:
        placeholders = ",".join("?" for _ in SUPPORTED_ACTIVE_EQUITY_TYPES)
        sql = (
            "SELECT fund_code FROM fund_profiles "
            f"WHERE fund_type IN ({placeholders}) ORDER BY fund_code"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(SUPPORTED_ACTIVE_EQUITY_TYPES)).fetchall()
        codes = [row["fund_code"] for row in rows]

        # 首期范围过滤：当配置了 FLE_PHASE1_CODES_FILE，只保留清单内的基金。
        # 用于把跑批范围锁回业务认可的 168 只（或后续放大的清单），避免被全库
        # 14k+ 的数据陪跑干扰。
        phase1 = _read_phase1_codes()
        if phase1 is not None:
            codes = [c for c in codes if c in phase1]
        return codes

    def list_all_fund_codes(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fund_code FROM fund_profiles ORDER BY fund_code"
            ).fetchall()
        return [row["fund_code"] for row in rows]

    def load_fund_input(self, fund_code: str) -> FundInput | None:
        with self._connect() as conn:
            profile = conn.execute(
                "SELECT fund_code, fund_name, fund_type, asset_size "
                "FROM fund_profiles WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()
            if profile is None:
                return None

            nav_returns = [
                row["daily_growth_rate"]
                for row in conn.execute(
                    "SELECT daily_growth_rate FROM nav_history "
                    "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL "
                    "ORDER BY nav_date",
                    (fund_code,),
                ).fetchall()
            ]
            benchmark_returns = self._load_benchmark_returns(conn, fund_code)

            latest_holding_date = conn.execute(
                "SELECT MAX(report_period) AS d FROM stock_holdings "
                "WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()["d"]
            stock_holdings = self._rows_to_dicts(
                conn,
                "SELECT stock_code, stock_name, net_value_ratio AS weight, 'A' AS market "
                "FROM stock_holdings "
                "WHERE fund_code = ? AND report_period = ? "
                "AND net_value_ratio IS NOT NULL "
                "ORDER BY net_value_ratio DESC",
                (fund_code, latest_holding_date) if latest_holding_date else None,
            )

            latest_industry_date = conn.execute(
                "SELECT MAX(report_period) AS d FROM industry_allocations "
                "WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()["d"]
            industry_allocations = self._rows_to_dicts(
                conn,
                "SELECT industry_name AS industry, net_value_ratio AS weight "
                "FROM industry_allocations "
                "WHERE fund_code = ? AND report_period = ? "
                "AND net_value_ratio IS NOT NULL "
                "ORDER BY net_value_ratio DESC",
                (fund_code, latest_industry_date) if latest_industry_date else None,
            )

            manager_row = conn.execute(
                "SELECT MAX(tenure_days) AS tenure_days FROM fund_manager_links "
                "WHERE fund_code = ?",
                (fund_code,),
            ).fetchone()
            tenure_days = (
                manager_row["tenure_days"]
                if manager_row and manager_row["tenure_days"] is not None
                else None
            )
            manager_tenure = tenure_days / 365.25 if tenure_days is not None else None

            fee_row = conn.execute(
                "SELECT "
                "MAX(CASE WHEN condition_name = '管理费率' THEN fee END) AS management_fee, "
                "MAX(CASE WHEN condition_name = '托管费率' THEN fee END) AS custody_fee, "
                "MAX(CASE WHEN condition_name = '销售服务费率' THEN fee END) AS sales_service_fee, "
                "MAX(CASE WHEN condition_name = ? THEN 1 ELSE 0 END) AS etf_no_fee_flag "
                "FROM fee_structures "
                "WHERE fund_code = ? AND fee_type = '运作费用'",
                (_ETF_NO_FEE_CONDITION, fund_code),
            ).fetchone()

            management_fee = fee_row["management_fee"] if fee_row else None
            custody_fee = fee_row["custody_fee"] if fee_row else None
            sales_service_fee = fee_row["sales_service_fee"] if fee_row else None
            etf_no_fee = bool(fee_row["etf_no_fee_flag"]) if fee_row else False
            # ETF 场内只在表里挂了「无费率信息」占位 → 三项费率按 0 兜底，
            # 与标准基金保持同一套 fee_structure gate；下游标签若关心绝对值
            # 仍可通过 total_annual_fee=0 + evidence 看到这是 ETF 兜底而非真低。
            if (
                etf_no_fee
                and management_fee is None
                and custody_fee is None
                and sales_service_fee is None
            ):
                management_fee = 0.0
                custody_fee = 0.0
                sales_service_fee = 0.0

            equity_row = conn.execute(
                "SELECT SUM(net_value_ratio) AS equity_position "
                "FROM stock_holdings "
                "WHERE fund_code = ? AND report_period = ? "
                "AND net_value_ratio IS NOT NULL",
                (fund_code, latest_holding_date),
            ).fetchone()
            equity_position = (
                equity_row["equity_position"]
                if equity_row and equity_row["equity_position"] is not None
                else None
            )

            from app.data_access.stock_factors import load_stock_factors

            stock_codes = [
                row["stock_code"] for row in stock_holdings if row.get("stock_code")
            ]
            # 用 None = 取每个因子的最新值，而不是要求 as_of <= latest_holding_date。
            # 因子横截面通常比持仓报告期更新；用持仓日期会让全部因子查不到（一份基金
            # 季报通常 60~120 天前发布，因子已经更新）。
            stock_factors = load_stock_factors(conn, stock_codes, None)

        return FundInput(
            fund_code=profile["fund_code"],
            fund_name=profile["fund_name"] or profile["fund_code"],
            fund_type=profile["fund_type"],
            nav_returns=nav_returns,
            stock_holdings=stock_holdings,
            industry_allocations=industry_allocations,
            stock_factors=stock_factors,
            benchmark_returns=benchmark_returns,
            manager_tenure_years=manager_tenure,
            management_fee=management_fee,
            custody_fee=custody_fee,
            sales_service_fee=sales_service_fee,
            fund_size=profile["asset_size"],
            equity_position=equity_position,
            holding_report_date=latest_holding_date,
            industry_report_date=latest_industry_date,
        )

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
    def _rows_to_dicts(
        conn: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...] | None,
    ) -> list[dict[str, Any]]:
        if params is None:
            return []
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
