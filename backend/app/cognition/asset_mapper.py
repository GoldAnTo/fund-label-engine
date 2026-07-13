"""产业链穿透引擎：持仓获取、主题匹配、持仓趋势分析。"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.cognition.holding_source import (
    HoldingSourceAdapter,
    HoldingSourceUnavailableError,
)


def get_holdings(
    conn: sqlite3.Connection,
    fund_code: str,
    report_period: str | None = None,
) -> list[dict[str, Any]]:
    """获取基金持仓，关联行业和因子。

    内部使用 HoldingSourceAdapter 读取基础持仓（统一字段），
    再批量补充行业映射和因子数据。
    如果持仓表不存在，返回空列表（向后兼容）。
    """
    try:
        adapter = HoldingSourceAdapter(conn)
    except HoldingSourceUnavailableError:
        return []

    # 读取基础持仓（已按权重降序排列，已过滤 weight > 0）
    base = adapter.load_holdings(fund_code, report_period)
    if not base:
        return []

    # 安全过滤：确保 weight 有效
    base = [h for h in base if h["weight"] is not None and h["weight"] > 0]
    if not base:
        return []

    stock_codes = [h["stock_code"] for h in base]
    placeholders = ",".join("?" * len(stock_codes))

    # 批量查询行业映射
    industry_map: dict[str, dict[str, Any]] = {}
    try:
        rows = conn.execute(
            f"SELECT stock_code, sector_group, industry_name "
            f"FROM stock_industry_map WHERE stock_code IN ({placeholders})",
            stock_codes,
        ).fetchall()
        for r in rows:
            industry_map[r[0]] = {"sector_group": r[1], "industry_name": r[2]}
    except Exception:
        pass

    # 批量查询因子数据（factordb 未 attach 时静默降级）
    factor_map: dict[str, dict[str, Any]] = {}
    try:
        rows = conn.execute(
            f"SELECT stock_code, factor_code, factor_value "
            f"FROM factordb.stock_factor_values WHERE stock_code IN ({placeholders})",
            stock_codes,
        ).fetchall()
        for r in rows:
            factor_map.setdefault(r[0], {})[r[1]] = r[2]
    except Exception:
        pass

    # 组装返回结果，保持字段名和值与原实现一致
    result: list[dict[str, Any]] = []
    for h in base:
        stock_code = h["stock_code"]
        ind = industry_map.get(stock_code, {})
        factors = factor_map.get(stock_code, {})

        sector_group = ind.get("sector_group")
        if sector_group is None:
            sector_group = "other"

        industry_name = ind.get("industry_name")
        if industry_name is None:
            industry_name = "未知"

        result.append({
            "stock_code": stock_code,
            "stock_name": h["stock_name"],
            "weight": h["weight"],
            "sector_group": sector_group,
            "industry_name": industry_name,
            "pe": factors.get("pe"),
            "pb": factors.get("pb"),
            "roe": factors.get("roe"),
            "dividend_yield": factors.get("dividend_yield"),
            "profit_growth": factors.get("profit_growth"),
            "val_pct": factors.get("valuation_percentile"),
        })

    return result


def match_theme(holdings: list[dict[str, Any]], theme: dict[str, Any]) -> dict[str, Any]:
    """按产业链环节计算匹配度。"""
    total_weight = sum(h["weight"] for h in holdings)
    if total_weight == 0:
        return {"match_pct": 0, "chain_breakdown": {}, "matched_stocks": []}

    chain_breakdown: dict[str, float] = {}
    matched_stocks: list[dict[str, Any]] = []

    for link_name, link_def in theme["chain_links"].items():
        industry_kws = link_def["industry_keywords"]
        stock_kws = link_def["stock_keywords"]
        link_weight = 0.0

        for h in holdings:
            ind = h.get("industry_name", "")
            name = h.get("stock_name", "")
            is_industry = any(kw in ind for kw in industry_kws)
            is_stock = any(kw in name for kw in stock_kws)
            if is_industry or is_stock:
                link_weight += h["weight"]
                if h not in matched_stocks:
                    matched_stocks.append(h)

        chain_breakdown[link_name] = round(link_weight * 100, 1)

    matched_weight = sum(h["weight"] for h in matched_stocks)
    match_pct = (matched_weight / total_weight * 100) if total_weight > 0 else 0

    return {
        "match_pct": round(match_pct, 1),
        "matched_weight": round(matched_weight * 100, 1),
        "total_weight": round(total_weight * 100, 1),
        "chain_breakdown": chain_breakdown,
        "matched_stocks": sorted(matched_stocks, key=lambda x: x["weight"], reverse=True)[:5],
    }


def _get_recent_periods(conn: sqlite3.Connection, fund_code: str, n: int = 4) -> list[str]:
    """获取基金最近 N 个报告期（倒序）。使用适配器以兼容两种表结构。"""
    try:
        adapter = HoldingSourceAdapter(conn)
    except HoldingSourceUnavailableError:
        return []
    return adapter.list_report_dates(fund_code, limit=n)


def calculate_holding_trend(
    conn: sqlite3.Connection,
    fund_code: str,
    theme: dict[str, Any],
    fund_codes: list[str] | None = None,
) -> dict[str, Any]:
    """计算基金对该认知主题的持仓变化趋势（多期对比）。"""
    periods = _get_recent_periods(conn, fund_code, 4)
    if len(periods) < 2:
        return {"trend": "insufficient_data", "diff": 0.0, "periods": []}

    all_stock_kws: list[str] = []
    all_industry_kws: list[str] = []
    for link in theme["chain_links"].values():
        all_stock_kws.extend(link["stock_keywords"])
        all_industry_kws.extend(link["industry_keywords"])

    trend_data: list[dict[str, Any]] = []
    for period in periods:
        holdings = get_holdings(conn, fund_code, period)
        matched_weight = 0.0
        for h in holdings:
            ind = h.get("industry_name", "")
            name = h.get("stock_name", "")
            if any(kw in ind for kw in all_industry_kws) or any(kw in name for kw in all_stock_kws):
                matched_weight += h["weight"]
        trend_data.append({"period": period, "weight": round(matched_weight * 100, 1)})

    latest = trend_data[0]["weight"]
    earliest = trend_data[-1]["weight"]
    diff = latest - earliest

    if diff > 5:
        trend = "increasing"
    elif diff < -5:
        trend = "decreasing"
    else:
        trend = "stable"

    return {"trend": trend, "diff": round(diff, 1), "periods": trend_data}
