"""只读持仓源适配器：统一读取 stock_holdings 和 fund_stock_holdings 两种表结构。

两种表结构差异：
- stock_holdings:     report_period + net_value_ratio（无 market 列）
- fund_stock_holdings: report_date + weight + market

适配器在构造时自动检测哪张表存在（优先 stock_holdings），
对外暴露统一的持仓 dict：fund_code, holding_report_date, stock_code, stock_name, weight, market。

所有操作只读，不创建或修改任何表。表名只从内部白名单选择，不接受外部传入。
"""
from __future__ import annotations

import sqlite3
from typing import Any, Literal


class HoldingSourceUnavailableError(RuntimeError):
    """持仓源不可用：stock_holdings 和 fund_stock_holdings 两张表都不存在。"""


# 内部白名单：只允许这两种表名
_ALLOWED_TABLES: tuple[str, ...] = ("stock_holdings", "fund_stock_holdings")


class HoldingSourceAdapter:
    """只读持仓源适配器，统一两种持仓表结构。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._table = self._detect_table()

    def _detect_table(self) -> str:
        """检查连接中哪张持仓表存在，优先 stock_holdings。"""
        for table in _ALLOWED_TABLES:
            row = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if row:
                return table
        raise HoldingSourceUnavailableError(
            "找不到持仓表（stock_holdings 或 fund_stock_holdings 均不存在）"
        )

    def schema_name(self) -> Literal["stock_holdings", "fund_stock_holdings"]:
        """返回当前使用的表名。"""
        return self._table  # type: ignore[return-value]

    def list_fund_codes(self) -> list[str]:
        """返回所有基金代码列表（升序）。"""
        rows = self._conn.execute(
            f"SELECT DISTINCT fund_code FROM {self._table} ORDER BY fund_code"
        ).fetchall()
        return [r[0] for r in rows]

    def list_report_dates(self, fund_code: str, limit: int = 4) -> list[str]:
        """返回指定基金的报告期列表（倒序，默认 limit=4）。"""
        date_col = self._date_column()
        rows = self._conn.execute(
            f"SELECT DISTINCT {date_col} FROM {self._table} "
            f"WHERE fund_code = ? ORDER BY {date_col} DESC LIMIT ?",
            (fund_code, limit),
        ).fetchall()
        return [r[0] for r in rows if r[0] is not None]

    def load_holdings(
        self, fund_code: str, report_date: str | None = None
    ) -> list[dict[str, Any]]:
        """加载基金持仓，输出统一字段。

        不指定 report_date 时取最新一期。
        权重保持 0..1 小数，不乘 100。
        只返回 weight > 0 的记录，按权重降序排列。
        """
        if report_date is None:
            dates = self.list_report_dates(fund_code, limit=1)
            if not dates:
                return []
            report_date = dates[0]

        date_col = self._date_column()
        if self._table == "stock_holdings":
            weight_col = "net_value_ratio"
            market_expr = "NULL"
        else:
            weight_col = "weight"
            market_expr = "market"

        rows = self._conn.execute(
            f"SELECT fund_code, {date_col} AS holding_report_date, "
            f"stock_code, stock_name, {weight_col} AS weight, "
            f"{market_expr} AS market "
            f"FROM {self._table} "
            f"WHERE fund_code = ? AND {date_col} = ? "
            f"AND {weight_col} IS NOT NULL AND {weight_col} > 0 "
            f"ORDER BY {weight_col} DESC",
            (fund_code, report_date),
        ).fetchall()

        return [
            {
                "fund_code": r[0],
                "holding_report_date": r[1],
                "stock_code": r[2],
                "stock_name": r[3],
                "weight": r[4],
                "market": r[5],
            }
            for r in rows
        ]

    def _date_column(self) -> str:
        """返回当前表使用的日期列名。"""
        return "report_period" if self._table == "stock_holdings" else "report_date"
