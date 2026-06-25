"""共享的股票因子读取逻辑。

数据契约存在两种形态：
- 窄表 ``stock_factor_values(stock_code, factor_code, factor_value, as_of_date, ...)``
  由 Phase 5 的 migration 引入，未来主推；任意因子都可加列零成本。
- 宽表 ``stock_factors(stock_code, factor_date, pb, roe, dividend_yield, ...)``
  来自 sample seed 与早期 fundData 副本；字段固定。

`load_stock_factors` 同时支持两种，并把结果归一化为平铺 dict 列表：
``[{stock_code, pb, roe, dividend_yield, revenue_growth, valuation_percentile, ...}]``
这正是 engine 的 ``_factor_lookup`` 所需要的形态。
"""
from __future__ import annotations

import sqlite3
from typing import Any

# 窄表中的 factor_code 命名 -> FundInput.stock_factors 字段名映射
NARROW_FACTOR_FIELD_MAP: dict[str, str] = {
    "pb": "pb",
    "pe": "pe",
    "roe": "roe",
    "dividend_yield": "dividend_yield",
    "revenue_growth": "revenue_growth",
    "profit_growth": "profit_growth",
    "valuation_percentile": "valuation_percentile",
    "market_cap_bucket": "market_cap_bucket",
    "style": "style",
}


def load_stock_factors(
    conn: sqlite3.Connection,
    stock_codes: list[str],
    as_of: str | None,
) -> list[dict[str, Any]]:
    if not stock_codes:
        return []
    narrow = _load_from_narrow(conn, stock_codes, as_of)
    if narrow:
        return narrow
    return _load_from_wide(conn, stock_codes, as_of)


def _load_from_narrow(
    conn: sqlite3.Connection,
    stock_codes: list[str],
    as_of: str | None,
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in stock_codes)
    base_sql = (
        "SELECT stock_code, factor_code, factor_value, as_of_date "
        f"FROM stock_factor_values sf "
        f"WHERE sf.stock_code IN ({placeholders}) "
    )
    params: tuple[Any, ...]
    if as_of:
        sql = base_sql + (
            "AND sf.as_of_date = ("
            "  SELECT MAX(as_of_date) FROM stock_factor_values "
            "  WHERE stock_code = sf.stock_code AND factor_code = sf.factor_code "
            "        AND as_of_date <= ?"
            ") "
            "ORDER BY sf.stock_code, sf.factor_code"
        )
        params = tuple(stock_codes) + (as_of,)
    else:
        sql = base_sql + (
            "AND sf.as_of_date = ("
            "  SELECT MAX(as_of_date) FROM stock_factor_values "
            "  WHERE stock_code = sf.stock_code AND factor_code = sf.factor_code"
            ") "
            "ORDER BY sf.stock_code, sf.factor_code"
        )
        params = tuple(stock_codes)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []

    # 透视：把多条 (stock_code, factor_code) 行合并为一条平铺 dict
    pivoted: dict[str, dict[str, Any]] = {}
    for row in rows:
        # 兼容 row_factory 是 tuple 或 Row 两种连接
        stock_code, factor_code, factor_value, _as_of = row[0], row[1], row[2], row[3]
        target = pivoted.setdefault(stock_code, {"stock_code": stock_code})
        field = NARROW_FACTOR_FIELD_MAP.get(factor_code, factor_code)
        target[field] = factor_value
        target["as_of_date"] = max(str(target.get("as_of_date") or ""), str(_as_of or ""))
    return list(pivoted.values())


def _load_from_wide(
    conn: sqlite3.Connection,
    stock_codes: list[str],
    as_of: str | None,
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in stock_codes)
    sql = (
        "SELECT sf.stock_code, sf.factor_date, sf.pb, sf.roe, sf.dividend_yield, "
        "sf.revenue_growth, sf.profit_growth, sf.market_cap_bucket, "
        "sf.valuation_percentile, sf.style "
        "FROM stock_factors sf "
        f"WHERE sf.stock_code IN ({placeholders}) "
    )
    params: tuple[Any, ...]
    if as_of:
        sql += (
            "AND sf.factor_date = ("
            "  SELECT MAX(factor_date) FROM stock_factors "
            "  WHERE stock_code = sf.stock_code AND factor_date <= ?"
            ") "
            "ORDER BY sf.stock_code"
        )
        params = tuple(stock_codes) + (as_of,)
    else:
        sql += (
            "AND sf.factor_date = ("
            "  SELECT MAX(factor_date) FROM stock_factors "
            "  WHERE stock_code = sf.stock_code"
            ") "
            "ORDER BY sf.stock_code"
        )
        params = tuple(stock_codes)
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    # 兼容 row_factory 不是 Row 的情况：用列序对齐回字段
    columns = (
        "stock_code",
        "factor_date",
        "pb",
        "roe",
        "dividend_yield",
        "revenue_growth",
        "profit_growth",
        "market_cap_bucket",
        "valuation_percentile",
        "style",
    )
    return [dict(zip(columns, row)) for row in rows]
