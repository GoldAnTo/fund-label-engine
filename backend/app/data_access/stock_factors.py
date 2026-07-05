"""共享的股票因子读取逻辑。

数据契约存在两种形态：
- 窄表 ``stock_factor_values(stock_code, factor_code, factor_value, as_of_date, ...)``
  由 Phase 5 的 migration 引入，未来主推；任意因子都可加列零成本。
- 宽表 ``stock_factors(stock_code, factor_date, pb, roe, dividend_yield, ...)``
  来自 sample seed 与早期 fundData 副本；字段固定。

`load_stock_factors` 同时支持两种，并把结果归一化为平铺 dict 列表：
``[{stock_code, pb, roe, dividend_yield, revenue_growth, valuation_percentile, ...}]``
这正是 engine 的 ``_factor_lookup`` 所需要的形态。

数据清洗规则（在 _sanitize_factor_row 中实现）：
- PB/PE 负值或零 → 剔除（净资产为负或亏损无法解释估值倍数）
- PB 截断到 [0.1, 200]
- PE 截断到 [0.1, 2000]，>2000 视为异常剔除
- ROE 截断到 [-0.5, 0.5]
- 利润增速截断到 [-1.0, 3.0]（即 -100% ~ +300%）
- 营收增速截断到 [-1.0, 3.0]
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
        return [_sanitize_factor_row(r) for r in narrow]
    return [_sanitize_factor_row(r) for r in _load_from_wide(conn, stock_codes, as_of)]


def _sanitize_factor_row(row: dict[str, Any]) -> dict[str, Any]:
    """对单只股票的因子行做清洗：剔除异常值、截断极端值。

    清洗规则：
    - PB: 负值/零 → None；截断到 [0.1, 200]
    - PE: 负值/零 → None；>2000 → None（异常）；截断到 [0.1, 2000]
    - ROE: 截断到 [-0.5, 0.5]
    - profit_growth: 截断到 [-1.0, 3.0]
    - revenue_growth: 截断到 [-1.0, 3.0]
    """
    def _clamp(v: Any, lo: float, hi: float) -> Any:
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN
            return None
        return max(lo, min(hi, f))

    def _drop_if_invalid(v: Any, lo: float, hi: float) -> Any:
        """超出 [lo, hi] 范围 → None（剔除），否则原值返回。"""
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN
            return None
        if f < lo or f > hi:
            return None
        return f

    result = dict(row)
    # PB: 负值/零无意义（净资产为负），极端值剔除
    pb = result.get("pb")
    if pb is not None:
        pb_f = _drop_if_invalid(pb, 0.01, 200.0)
        result["pb"] = pb_f
    # PE: 负值（亏损）无意义，极端高值剔除
    pe = result.get("pe")
    if pe is not None:
        pe_f = _drop_if_invalid(pe, 0.01, 2000.0)
        result["pe"] = pe_f
    # ROE: 截断到 [-50%, 50%]
    roe = result.get("roe")
    if roe is not None:
        result["roe"] = _clamp(roe, -0.5, 0.5)
    # 利润增速: 截断到 [-100%, 300%]
    pg = result.get("profit_growth")
    if pg is not None:
        result["profit_growth"] = _clamp(pg, -1.0, 3.0)
    # 营收增速: 截断到 [-100%, 300%]
    rg = result.get("revenue_growth")
    if rg is not None:
        result["revenue_growth"] = _clamp(rg, -1.0, 3.0)
    return result


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
