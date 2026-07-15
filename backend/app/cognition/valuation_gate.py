"""估值门禁：加权估值、隐含增长年限、硬约束检查、权重建议。"""
from __future__ import annotations

import math
from typing import Any


def _wavg(data: list[tuple[float, float]]) -> float | None:
    if not data:
        return None
    return sum(w * v for w, v in data) / sum(w for w, _ in data)


def estimate_price_in_years(
    pe: float | None,
    growth_rate: float | None,
    reasonable_pe: float = 20.0,
) -> float | None:
    """估算当前估值隐含了多少年增长。

    逻辑：如果利润以 growth_rate 持续增长，需要多少年 PE 才能回落到 reasonable_pe。
    公式：years = ln(PE / reasonable_pe) / ln(1 + growth_rate)

    pe: 加权 PE
    growth_rate: 利润增速，小数制（0.50 = 50%）
    reasonable_pe: 合理 PE 水平，默认 20
    """
    if not pe or pe <= 0 or not growth_rate or growth_rate <= 0:
        return None
    if pe <= reasonable_pe:
        return 0.0
    return round(math.log(pe / reasonable_pe) / math.log(1 + growth_rate), 1)


def adjust_hard_limits_for_level(
    hard_limits: dict[str, Any],
    level: str,
) -> dict[str, Any]:
    """根据认知层次动态调整估值硬约束。

    会议说"生产力变革可以容忍高PE（PEG是关键），市场错杀要求低PE"。
    不同认知层次对应不同估值哲学。
    """
    adjusted = dict(hard_limits)

    if level == "productivity":
        # 生产力变革：放宽PE和估值分位上限，但收紧PEG
        # 会议："如果是10年级别生产力变革，当前PE 100可能只是开始"
        adjusted["max_valuation_percentile"] = max(adjusted.get("max_valuation_percentile", 85), 95)
        adjusted["max_pe"] = None  # 不设PE上限，用PEG约束
        adjusted["max_peg"] = min(adjusted.get("max_peg", 3.0), 3.0)  # PEG < 3
        adjusted["valuation_philosophy"] = "生产力变革容忍高PE，PEG是核心约束"

    elif level == "market":
        # 市场错杀：严格PE和估值分位限制
        # 会议："市场错杀要求低PE，基本面要支撑"
        adjusted["max_valuation_percentile"] = min(adjusted.get("max_valuation_percentile", 85), 50)
        adjusted["max_pe"] = min(adjusted.get("max_pe", 80), 30)
        adjusted["max_peg"] = min(adjusted.get("max_peg", 2.0), 1.0)
        adjusted["valuation_philosophy"] = "市场错杀要求低PE，估值必须处于历史低位"

    elif level == "structure":
        # 结构集中：适度限制
        adjusted["max_valuation_percentile"] = min(adjusted.get("max_valuation_percentile", 85), 75)
        adjusted["max_peg"] = min(adjusted.get("max_peg", 2.0), 2.0)
        adjusted["valuation_philosophy"] = "结构集中适度限制估值，关注集中度风险"

    elif level == "trust":
        # 信任委托：不关注估值，关注经理能力
        adjusted["max_valuation_percentile"] = 95  # 几乎不限制
        adjusted["max_pe"] = None
        adjusted["max_peg"] = None
        adjusted["valuation_philosophy"] = "信任委托不设估值硬约束，关注基金经理能力"

    return adjusted


def check_hard_limits(
    valuation: dict[str, Any],
    hard_limits: dict[str, Any],
    level: str | None = None,
) -> dict[str, Any]:
    """检查基金估值是否通过硬约束。

    hard_limits 来自 cognition_chains.yaml 的 judgment.hard_limits，例如：
      max_valuation_percentile: 85
      max_peg: 2.0
      max_pe: 80
      min_roe: 12
      min_dividend_yield: 3.0

    如果提供 level，会先根据认知层次调整阈值。
    """
    if level:
        hard_limits = adjust_hard_limits_for_level(hard_limits, level)

    violations: list[str] = []

    val_pct = valuation.get("weighted_val_pct")
    max_val_pct = hard_limits.get("max_valuation_percentile")
    if max_val_pct and val_pct and val_pct > max_val_pct:
        violations.append(
            f"估值分位 {val_pct:.0f}% 超过上限 {max_val_pct:.0f}%"
        )

    peg = valuation.get("peg")
    max_peg = hard_limits.get("max_peg")
    if max_peg and peg and peg > max_peg:
        violations.append(f"PEG {peg:.2f} 超过上限 {max_peg}")

    pe = valuation.get("weighted_pe")
    max_pe = hard_limits.get("max_pe")
    if max_pe and pe and pe > max_pe:
        violations.append(f"PE {pe:.1f} 超过上限 {max_pe}")

    roe = valuation.get("weighted_roe")
    min_roe = hard_limits.get("min_roe")
    if min_roe and roe is not None and roe < min_roe:
        violations.append(f"ROE {roe:.1f}% 低于下限 {min_roe}%")

    div = valuation.get("weighted_dividend")
    min_div = hard_limits.get("min_dividend_yield")
    if min_div and div is not None and div < min_div:
        violations.append(f"股息率 {div:.2f}% 低于下限 {min_div}%")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "valuation_philosophy": hard_limits.get("valuation_philosophy", ""),
        "adjusted_limits": {k: v for k, v in hard_limits.items() if k != "valuation_philosophy"},
    }


def calculate_valuation(holdings: list[dict[str, Any]], level: str | None = None) -> dict[str, Any]:
    """计算加权估值：PE、PB、ROE、股息率、估值分位、PEG、隐含增长年限。

    ROE 和 dividend_yield 在数据库中存储为小数（0.31 = 31%），显示时乘 100。
    valuation_percentile 存储为 0-1 的小数，显示时乘 100。
    profit_growth 存储为小数（0.50 = 50%），显示时乘 100。
    """
    valid_pe = [(h["weight"], h["pe"]) for h in holdings if h.get("pe") and h["pe"] > 0]
    valid_pct = [(h["weight"], h["val_pct"]) for h in holdings if h.get("val_pct") is not None]
    valid_growth = [
        (h["weight"], h["profit_growth"])
        for h in holdings
        if h.get("profit_growth") and h["profit_growth"] > 0
    ]
    valid_roe = [(h["weight"], h["roe"]) for h in holdings if h.get("roe") and h["roe"] > 0]
    valid_div = [
        (h["weight"], h["dividend_yield"])
        for h in holdings
        if h.get("dividend_yield") and h["dividend_yield"] > 0
    ]
    valid_pb = [(h["weight"], h["pb"]) for h in holdings if h.get("pb") and h["pb"] > 0]

    w_pe = _wavg(valid_pe)
    w_pct = _wavg(valid_pct)
    w_growth = _wavg(valid_growth)
    w_roe = _wavg(valid_roe)
    w_div = _wavg(valid_div)
    w_pb = _wavg(valid_pb)

    peg: float | None = None
    if w_pe and w_growth and w_growth > 0:
        peg = w_pe / (w_growth * 100)

    if w_pct is not None:
        if w_pct > 0.85:
            val_judge = "极度偏贵"
        elif w_pct > 0.70:
            val_judge = "偏贵"
        elif w_pct > 0.30:
            val_judge = "合理"
        else:
            val_judge = "偏低"
    else:
        val_judge = "—"

    if peg is not None:
        if peg < 1:
            peg_judge = "增速能支撑估值"
        elif peg < 1.5:
            peg_judge = "估值与增速匹配"
        elif peg < 2:
            peg_judge = "偏贵但可接受"
        else:
            peg_judge = "已price in过多增长"
    else:
        peg_judge = "—"

    result = {
        "weighted_pe": round(w_pe, 1) if w_pe else None,
        "weighted_pb": round(w_pb, 2) if w_pb else None,
        "weighted_roe": round(w_roe * 100, 1) if w_roe else None,
        "weighted_dividend": round(w_div * 100, 2) if w_div else None,
        "weighted_val_pct": round(w_pct * 100, 0) if w_pct is not None else None,
        "weighted_growth": round(w_growth * 100, 0) if w_growth else None,
        "peg": round(peg, 2) if peg else None,
        "val_judge": val_judge,
        "peg_judge": peg_judge,
        "price_in_years": estimate_price_in_years(w_pe, w_growth),
    }
    result["suggested_max_weight"] = suggest_max_weight(result, level=level)
    return result


def suggest_max_weight(valuation: dict[str, Any], level: str | None = None) -> float:
    """根据估值建议权重上限（%）。"""
    val_pct = valuation.get("weighted_val_pct")

    if level == "productivity":
        # 生产力变革可以给更高权重
        if val_pct and val_pct > 85:
            return 10.0  # 而非5%
        if val_pct and val_pct > 70:
            return 15.0
        return 20.0
    elif level == "market":
        # 市场错杀要更保守
        if val_pct and val_pct > 40:
            return 3.0
        if val_pct and val_pct > 30:
            return 5.0
        return 8.0
    elif level == "trust":
        return 15.0  # 信任委托可以给较高权重

    # 默认（structure 或 None）
    if val_pct and val_pct > 85:
        return 5.0
    if val_pct and val_pct > 70:
        return 8.0
    return 12.0
