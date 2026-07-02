"""portfolio_v1_acceptance_report: 把 28 只 eligible / 13 risk review / optimized top 20 / exclude 汇总
成一个可人工校准的 markdown 报告。

不做任何评分；只做搬运 + 标注，让研究员能直接 sign-off。
"""
from __future__ import annotations

from collections import Counter
from typing import Any

RISK_REVIEW_RISK_TAGS = {"high_volatility", "large_drawdown", "high_turnover"}


def is_risk_review_fund(row: dict[str, Any]) -> bool:
    """一只基金属于「风险复核」集合的判定。

    规则（任一命中）：
    - watch_reasons / blocking_reasons 含 'allocation_risk_review'
    - risk_tags 含 RISK_REVIEW_RISK_TAGS 之一
    - 风格/类别组合下 max_drawdown_1y 极差（< -0.3）或 annualized_volatility_1y 极高（> 0.3）
    """
    watch = {str(x) for x in row.get("watch_reasons", []) or []}
    blocking = {str(x) for x in row.get("blocking_reasons", []) or []}
    risk = {str(x) for x in row.get("risk_tags", []) or []}
    if "allocation_risk_review" in watch or "allocation_risk_review" in blocking:
        return True
    if risk & RISK_REVIEW_RISK_TAGS:
        return True
    max_dd = row.get("max_drawdown_1y")
    if max_dd is not None and float(max_dd) < -0.3:
        return True
    vol = row.get("annualized_volatility_1y")
    if vol is not None and float(vol) > 0.3:
        return True
    return False


def classify_eligible(row: dict[str, Any]) -> str:
    """把 eligible 基金二次分类为「真核心/卫星/index_tool/needs_more_data」。

    真核心 = bucket=core 且无风险复核标记，且 alpha_1y > 0
    卫星 = bucket=satellite 或 真核心之外的 eligible
    index_tool = 含 index_tool portfolio_role
    needs_more_data = role review 提示数据不足（excluded/observe 不算）
    """
    bucket = row.get("bucket") or ""
    if bucket == "core" and not is_risk_review_fund(row):
        alpha = row.get("alpha_1y")
        if alpha is None:
            return "needs_more_data"
        if float(alpha) > 0:
            return "core"
    if "index_tool" in (row.get("portfolio_roles") or []):
        return "index_tool"
    if bucket == "core" and is_risk_review_fund(row):
        return "core_pending_risk_review"
    return "satellite"


def bucket_by_status(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "eligible": [],
        "review_required": [],
        "observe": [],
        "excluded": [],
        "manual_review": [],
    }
    for r in rows:
        out.setdefault(r.get("allocation_status", ""), []).append(r)
    return out


def summarize_eligible(rows: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter(classify_eligible(r) for r in rows if r.get("allocation_status") == "eligible")
    return dict(c)


def top_optimized(draft_rows: list[dict[str, Any]], n: int = 20) -> list[dict[str, Any]]:
    rows = [dict(r) for r in draft_rows]
    rows.sort(key=lambda r: float(r.get("optimized_weight_pct", 0) or 0), reverse=True)
    return rows[:n]


def exclude_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    """从 excluded rows + observe rows 收集排除/降级原因 top 列表。

    来自 draft.excluded 里的 reasons 列表。
    """
    counts: Counter = Counter()
    for r in rows:
        for reason in r.get("reasons", []) or []:
            counts[reason] += 1
    return dict(counts)
