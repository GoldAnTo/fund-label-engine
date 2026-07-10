"""监控面板 v1：风险信号识别。

设计 §9 阶段 3：持仓历史、估值历史和监控预警。

风险信号类别：
- stale_valuation: 估值快照超过 N 天没更新
- high_concentration: 第一大重仓股权重 > 阈值（如 15%）
- valuation_drift: 估值分位短期上跳或下跌超过阈值
- holding_drift: 同一只股票重仓从最近一期消失或新进 top5
- missing_data: 关键字段缺失（PE / ROE / 持仓数）
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

# 风险信号阈值
STALE_VALUATION_DAYS = 60  # 估值快照超过 60 天没更新
HIGH_CONCENTRATION_THRESHOLD = 0.15  # 第一大重仓 > 15%
VALUATION_DRIFT_THRESHOLD = 15.0  # 估值分位上跳/下跌 > 15 pp
MISSING_DATA_FIELDS = ("weighted_pe", "weighted_pb", "weighted_roe")


def _date_from_str(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except (ValueError, TypeError):
        return None


def detect_risk_signals(
    valuation_history: list[dict[str, Any]],
    holding_history: list[dict[str, Any]],
    as_of_today: date | None = None,
) -> list[dict[str, Any]]:
    """根据估值快照 + 持仓历史检测风险信号。

    Args:
        valuation_history: 按 as_of_date DESC 排序的快照
        holding_history: 按 report_period DESC 排序的持仓摘要
        as_of_today: 用于"过期"判断的当前日期（默认今天）

    Returns:
        [{code, level, title, detail, value}, ...]
        level: warning | info | critical
    """
    today = as_of_today or date.today()
    signals: list[dict[str, Any]] = []

    # 1) stale_valuation
    if valuation_history:
        latest = valuation_history[0]
        latest_date = _date_from_str(latest.get("as_of_date"))
        if latest_date:
            age_days = (today - latest_date).days
            if age_days > STALE_VALUATION_DAYS:
                signals.append({
                    "code": "stale_valuation",
                    "level": "warning",
                    "title": "估值快照过期",
                    "detail": (
                        f"最新估值快照 {latest.get('as_of_date')}, "
                        f"距今 {age_days} 天（> {STALE_VALUATION_DAYS} 天）"
                    ),
                    "value": age_days,
                })
    else:
        signals.append({
            "code": "no_valuation_history",
            "level": "warning",
            "title": "无估值快照历史",
            "detail": "监控面板需要至少一次 batch run 写入估值快照",
            "value": 0,
        })

    # 2) high_concentration
    if valuation_history:
        latest = valuation_history[0]
        top_w = latest.get("top_holding_weight")
        if top_w is not None and top_w > HIGH_CONCENTRATION_THRESHOLD:
            signals.append({
                "code": "high_concentration",
                "level": "warning",
                "title": "持仓集中度偏高",
                "detail": (
                    f"第一大重仓 {top_w:.1%} > {HIGH_CONCENTRATION_THRESHOLD:.0%} 阈值"
                ),
                "value": top_w,
            })

    # 3) valuation_drift（连续两期估值分位上跳或下跌 > 阈值）
    if len(valuation_history) >= 2:
        cur_pct = valuation_history[0].get("weighted_val_pct")
        prev_pct = valuation_history[1].get("weighted_val_pct")
        if cur_pct is not None and prev_pct is not None:
            diff = cur_pct - prev_pct
            if abs(diff) > VALUATION_DRIFT_THRESHOLD:
                direction = "上跳" if diff > 0 else "下跌"
                signals.append({
                    "code": "valuation_drift",
                    "level": "info",
                    "title": f"估值分位{direction}",
                    "detail": (
                        f"分位 {prev_pct:.0f} → {cur_pct:.0f}（{diff:+.0f} pp）"
                        f"，变化 > {VALUATION_DRIFT_THRESHOLD:.0f} pp 阈值"
                    ),
                    "value": diff,
                })

    # 4) holding_drift（最新期 top5 与上期 top5 出现 2 只及以上替换）
    if len(holding_history) >= 2:
        cur_top5 = {
            h["stock_code"]
            for h in holding_history[0].get("top_holdings", [])
        }
        prev_top5 = {
            h["stock_code"]
            for h in holding_history[1].get("top_holdings", [])
        }
        new_in = cur_top5 - prev_top5
        dropped = prev_top5 - cur_top5
        if len(new_in) >= 2 and len(dropped) >= 2:
            signals.append({
                "code": "holding_drift",
                "level": "info",
                "title": "重仓股显著变化",
                "detail": (
                    f"上期→本期 top5 替换 {len(new_in)} 只："
                    f"新增 {', '.join(list(new_in)[:3])}，"
                    f"退出 {', '.join(list(dropped)[:3])}"
                ),
                "value": len(new_in),
            })

    # 5) missing_data
    if valuation_history:
        latest = valuation_history[0]
        missing = [
            f for f in MISSING_DATA_FIELDS
            if latest.get(f) is None
        ]
        if len(missing) >= 2:
            signals.append({
                "code": "missing_data",
                "level": "critical",
                "title": "关键字段缺失",
                "detail": f"最新快照缺少 {', '.join(missing)}，估值判断受限",
                "value": len(missing),
            })

    return signals
