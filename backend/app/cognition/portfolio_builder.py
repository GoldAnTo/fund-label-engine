"""组合构建器：持仓重叠度、基金相关性、组合方案构建。"""
from __future__ import annotations

import sqlite3
import statistics
from typing import Any


def calculate_overlap(
    holdings_a: list[dict[str, Any]],
    holdings_b: list[dict[str, Any]],
) -> dict[str, Any]:
    """计算两只基金的持仓重叠度。"""
    map_a = {h["stock_code"]: h["weight"] for h in holdings_a}
    map_b = {h["stock_code"]: h["weight"] for h in holdings_b}
    common = set(map_a.keys()) & set(map_b.keys())

    overlap_a = sum(map_a[s] for s in common)
    overlap_b = sum(map_b[s] for s in common)

    if overlap_a > 0.4:
        judge = "高度重叠，建议只选一只"
    elif overlap_a > 0.2:
        judge = "中度重叠，需评估分散效果"
    else:
        judge = "低重叠，分散效果良好"

    return {
        "common_count": len(common),
        "overlap_a_pct": round(overlap_a * 100, 1),
        "overlap_b_pct": round(overlap_b * 100, 1),
        "judge": judge,
        "common_stocks": sorted(
            [
                {"code": s, "a": round(map_a[s] * 100, 2), "b": round(map_b[s] * 100, 2)}
                for s in common
            ],
            key=lambda x: x["a"] + x["b"],
            reverse=True,
        )[:3],
    }


def calculate_correlation(
    conn: sqlite3.Connection,
    fund_a: str,
    fund_b: str,
) -> float | None:
    """计算两只基金的 NAV 日收益相关系数（共同交易日 < 30 返回 None）。"""
    rows_a = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history "
        "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
        (fund_a,),
    ).fetchall()
    rows_b = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history "
        "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
        (fund_b,),
    ).fetchall()

    map_a = {r[0]: r[1] for r in rows_a}
    map_b = {r[0]: r[1] for r in rows_b}
    common = sorted(set(map_a.keys()) & set(map_b.keys()))

    if len(common) < 30:
        return None

    returns_a = [map_a[d] for d in common]
    returns_b = [map_b[d] for d in common]
    return round(statistics.correlation(returns_a, returns_b), 3)


def build_portfolio(
    candidates: list[dict[str, Any]],
    defense_fund: dict[str, Any] | None,
    corr_threshold: float = 0.85,
    total_cognition_weight: float = 25.0,
    defense_weight_pct: float = 10.0,
    max_funds: int = 3,
) -> dict[str, Any]:
    """构建认知匹配的组合方案。

    候选基金按匹配度排序，依次选入（跳过相关性过高的），
    估值/趋势约束决定单只上限，认知仓位合计 total_cognition_weight%，防守仓位 defense_weight_pct%。
    """
    candidates.sort(key=lambda x: x["match_pct"], reverse=True)

    selected: list[dict[str, Any]] = []
    for c in candidates:
        if c["match_pct"] < 5:
            continue

        val_pct = c.get("valuation", {}).get("weighted_val_pct")
        if val_pct and val_pct > 85:
            max_weight = 5
        elif val_pct and val_pct > 70:
            max_weight = 8
        else:
            max_weight = 12

        trend = c.get("trend", {}).get("trend", "")
        if trend == "decreasing":
            max_weight = min(max_weight, 5)

        too_correlated = False
        for s in selected:
            if s.get("corr_with", {}).get(c["fund_code"], 0) > corr_threshold:
                too_correlated = True
                break
        if too_correlated:
            continue

        selected.append({**c, "max_weight": max_weight})

        if len(selected) >= max_funds:
            break

    total_match = sum(s["match_pct"] for s in selected) or 1
    for s in selected:
        raw = s["match_pct"] / total_match * total_cognition_weight
        s["weight"] = round(min(raw, s["max_weight"]), 1)

    defense_weight = 0
    if defense_fund:
        defense_weight = defense_weight_pct
        defense_fund["weight"] = defense_weight

    total = sum(s["weight"] for s in selected) + defense_weight
    cash = max(0, 100 - total)

    return {
        "selected_funds": selected,
        "defense_position": defense_fund,
        "cash_pct": round(cash, 1),
        "total_invested": round(total, 1),
    }
