"""预期差计算：市场定价 vs 基本面，找出被低估/高估的环节"""
from __future__ import annotations

from typing import Any


def calculate_link_expectation_gap(
    link: dict[str, Any],
    holdings: list[dict[str, Any]],
    revenue_data: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """计算单个产业链环节的预期差

    holdings是该环节匹配到的持仓股票列表（包含pe, profit_growth, val_pct等因子）
    revenue_data: 主营业务构成数据，用于收入暴露加权匹配

    返回：
    - pe: 加权PE
    - growth: 加权利润增速
    - peg: PEG
    - val_pct: 加权估值分位
    - expectation_gap: "positive" / "neutral" / "negative"
    - gap_reason: 预期差的原因
    - score: 预期差评分(0-100, 越高越值得投)
    """
    # 筛选属于该环节的持仓
    stock_kws = link.get("stocks", [])
    ind_kws = link.get("industry_keywords", [])
    all_kws = stock_kws + ind_kws

    matched: list[dict[str, Any]] = []
    for h in holdings:
        name = h.get("stock_name", "") or ""
        ind = h.get("industry_name", "") or ""
        code = h.get("stock_code", "")

        # 1. 尝试收入暴露
        if revenue_data and code in revenue_data:
            matched_by_revenue = False
            for segment, pct in revenue_data[code].items():
                if any(kw in segment for kw in all_kws):
                    # 收入暴露匹配，用营收占比作为权重系数
                    h_copy = dict(h)
                    h_copy["_exposure"] = pct / 100.0
                    matched.append(h_copy)
                    matched_by_revenue = True
                    break
            if matched_by_revenue:
                continue
            # 收入暴露未命中，继续尝试关键词匹配
        # 2. 关键词回退
        if any(kw in name for kw in stock_kws) or any(kw in ind for kw in ind_kws):
            matched.append(h)

    if not matched:
        return {
            "link_name": link["name"],
            "match_pct": 0,
            "pe": None,
            "growth_pct": None,
            "peg": None,
            "val_pct": None,
            "roe": None,
            "dividend_yield": None,
            "expectation_gap": "unknown",
            "gap_reason": "无匹配持仓",
            "score": 0,
            "certainty": link.get("certainty", "medium"),
            "elasticity": link.get("elasticity", "medium"),
            "matched_weight": 0,
            "matched_stocks": [],
        }

    total_weight = sum(h["weight"] for h in matched)

    # 加权计算
    def wavg(field: str, filter_fn: Any = None) -> float | None:
        data = [
            (h["weight"], h[field])
            for h in matched
            if h.get(field) is not None and (filter_fn is None or filter_fn(h[field]))
        ]
        if not data:
            return None
        return sum(w * v for w, v in data) / sum(w for w, _ in data)

    pe = wavg("pe", lambda x: x > 0)
    growth = wavg("profit_growth", lambda x: x > 0)
    val_pct = wavg("val_pct")  # 0-1
    roe = wavg("roe", lambda x: x > 0)
    div_yield = wavg("dividend_yield", lambda x: x > 0)

    # PEG
    peg: float | None = None
    if pe and growth and growth > 0:
        peg = pe / (growth * 100)

    # 预期差判断逻辑
    # 正预期差（被低估）：PEG低 + 估值分位低
    # 负预期差（被高估）：PEG高 + 估值分位高
    # 中性：两者匹配

    gap = "neutral"
    reason = ""
    score = 50  # 基础分

    if peg is not None and val_pct is not None:
        if peg < 1.0 and val_pct < 0.5:
            gap = "positive"
            reason = f"PEG {peg:.1f}（增速远超估值），估值分位 {val_pct * 100:.0f}%（历史低位）"
            score = 80
        elif peg < 1.0 and val_pct < 0.7:
            gap = "positive"
            reason = f"PEG {peg:.1f}（增速支撑估值），估值分位 {val_pct * 100:.0f}%（中等）"
            score = 70
        elif peg < 1.5 and val_pct < 0.8:
            gap = "neutral"
            reason = f"PEG {peg:.1f}（估值与增速匹配），估值分位 {val_pct * 100:.0f}%"
            score = 55
        elif peg > 2.0 or val_pct > 0.9:
            gap = "negative"
            reason = f"PEG {peg:.1f}（估值远超增速），估值分位 {val_pct * 100:.0f}%（历史高位）"
            score = 20
        else:
            gap = "neutral"
            reason = f"PEG {peg:.1f}，估值分位 {val_pct * 100:.0f}%"
            score = 45

    # 确定性加分
    certainty = link.get("certainty", "medium")
    if certainty == "high":
        score += 10
    elif certainty == "low":
        score -= 10

    # 弹性加分
    elasticity = link.get("elasticity", "medium")
    if elasticity == "high":
        score += 5

    score = max(0, min(100, score))

    return {
        "link_name": link["name"],
        "match_pct": min(round(total_weight * 100, 1), 100.0),
        "pe": round(pe, 1) if pe else None,
        "growth_pct": round(growth * 100, 0) if growth else None,
        "peg": round(peg, 2) if peg else None,
        "val_pct": round(val_pct * 100, 0) if val_pct is not None else None,
        "roe": round(roe * 100, 1) if roe else None,
        "dividend_yield": round(div_yield * 100, 2) if div_yield else None,
        "expectation_gap": gap,
        "gap_reason": reason,
        "score": score,
        "certainty": certainty,
        "elasticity": elasticity,
        "matched_weight": round(total_weight * 100, 1),
        "matched_stocks": [h.get("stock_name", "?") for h in matched[:5]],
    }
