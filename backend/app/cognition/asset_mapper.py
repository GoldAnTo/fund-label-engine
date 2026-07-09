"""产业链穿透引擎：持仓获取、主题匹配、持仓趋势分析。"""
from __future__ import annotations

import sqlite3
from typing import Any


def get_holdings(
    conn: sqlite3.Connection,
    fund_code: str,
    report_period: str | None = None,
) -> list[dict[str, Any]]:
    """获取基金持仓，关联行业和因子（子查询方式获取因子，避免多 LEFT JOIN 问题）。"""
    if report_period is None:
        row = conn.execute(
            "SELECT MAX(report_period) FROM stock_holdings WHERE fund_code = ?",
            (fund_code,),
        ).fetchone()
        report_period = row[0] if row else None
    if not report_period:
        return []

    rows = conn.execute(
        """
        SELECT h.stock_code, h.stock_name, h.net_value_ratio AS weight,
               COALESCE(m.sector_group, 'other') AS sector_group,
               COALESCE(m.industry_name, '未知') AS industry_name,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'pe') AS pe,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'pb') AS pb,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'roe') AS roe,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'dividend_yield') AS dividend_yield,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'profit_growth') AS profit_growth,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'valuation_percentile') AS val_pct
        FROM stock_holdings h
        LEFT JOIN stock_industry_map m ON h.stock_code = m.stock_code
        WHERE h.fund_code = ? AND h.report_period = ? AND h.net_value_ratio IS NOT NULL AND h.net_value_ratio > 0
        ORDER BY h.net_value_ratio DESC
        """,
        (fund_code, report_period),
    ).fetchall()
    return [dict(r) for r in rows]


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
    rows = conn.execute(
        "SELECT DISTINCT report_period FROM stock_holdings "
        "WHERE fund_code = ? ORDER BY report_period DESC LIMIT ?",
        (fund_code, n),
    ).fetchall()
    return [r[0] for r in rows]


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
