from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.label_engine.engine import SUPPORTED_ACTIVE_EQUITY_TYPES, FundInput


# 真库里大量 ETF / LOF 在 fee_structures 表只存了「场内ETF-无费率信息」
# 这一占位行不等于管理费/托管费为 0，不能作为正式 fee_low 证据。
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
            industry_row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='stock_industry_map'"
            ).fetchone()
            if industry_row is None:
                attached_row = conn.execute(
                    "SELECT name FROM factordb.sqlite_master "
                    "WHERE type='table' AND name='stock_industry_map'"
                ).fetchone()
                if attached_row is not None:
                    conn.execute(
                        "CREATE TEMP VIEW stock_industry_map AS "
                        "SELECT * FROM factordb.stock_industry_map"
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
            # 只出现「场内ETF-无费率信息」占位时，保持 None，让 fee_structure
            # gate 显式失败；等抓到真实运作费用后再输出 fee_low/fee_high。
            if etf_no_fee and management_fee is None and custody_fee is None:
                sales_service_fee = None

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
            factor_exposures = self._load_factor_exposures(
                conn,
                fund_code,
                latest_holding_date,
            )

        return FundInput(
            fund_code=profile["fund_code"],
            fund_name=profile["fund_name"] or profile["fund_code"],
            fund_type=profile["fund_type"],
            nav_returns=nav_returns,
            stock_holdings=stock_holdings,
            industry_allocations=industry_allocations,
            stock_factors=stock_factors,
            factor_exposures=factor_exposures,
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

    def list_recent_holding_periods(
        self, fund_code: str, limit: int
    ) -> list[str]:
        """返回该基金最近 ``limit`` 个有持仓披露的 report_period（降序）。

        用于多期风格稳定性分析：风格漂移需要同一只基金在多个报告期的
        基金级因子暴露序列。这里只返回有 stock_holdings 数据的期次。
        """
        if limit <= 0:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT report_period FROM stock_holdings "
                "WHERE fund_code = ? AND report_period IS NOT NULL "
                "ORDER BY report_period DESC LIMIT ?",
                (fund_code, limit),
            ).fetchall()
        return [row["report_period"] for row in rows]

    def load_holdings_for_period(
        self, fund_code: str, report_period: str
    ) -> list[dict[str, Any]]:
        """加载某只基金指定 report_period 的股票持仓（与 load_fund_input 同口径）。"""
        with self._connect() as conn:
            return self._rows_to_dicts(
                conn,
                "SELECT stock_code, stock_name, net_value_ratio AS weight, 'A' AS market "
                "FROM stock_holdings "
                "WHERE fund_code = ? AND report_period = ? "
                "AND net_value_ratio IS NOT NULL "
                "ORDER BY net_value_ratio DESC",
                (fund_code, report_period),
            )

    def load_stock_factors(self, stock_codes: list[str]) -> list[dict[str, Any]]:
        """加载一批股票的最新因子快照（透明走外挂 factor DB 或主库）。

        多期风格稳定性分析复用同一份最新因子快照作为稳定“透镜”，衡量各报告期
        持仓组合的因子暴露漂移；这与设计文档「loader 只有单一快照日期时对所有
        exposure 行使用该快照日期」的约定一致。
        """
        if not stock_codes:
            return []
        from app.data_access.stock_factors import load_stock_factors

        with self._connect() as conn:
            return load_stock_factors(conn, stock_codes, None)

    def load_stock_industry_map(
        self,
        stock_codes: list[str],
        as_of: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        if not stock_codes:
            return {}
        from app.data_access.stock_industries import load_stock_industry_map

        with self._connect() as conn:
            return load_stock_industry_map(conn, stock_codes, as_of)

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
    def _rows_to_dicts(
        conn: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...] | None,
    ) -> list[dict[str, Any]]:
        if params is None:
            return []
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
