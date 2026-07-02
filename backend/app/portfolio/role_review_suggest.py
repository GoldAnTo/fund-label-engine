"""根据 matrix 行生成 role review 建议（不写库）。

闭环：研究员打开工作台时能直接看到「每只 review_required 基金建议
是核心/卫星/排除」+ 理由 + 推荐上限权重；可以一键 apply，也可以
逐只修改。这把 portfolio_role_reviews 0 条的死循环打破。
"""
from __future__ import annotations

from typing import Any


# 建议的目标分桶 → role_code 映射。target_bucket 来自前端下拉，role_code
# 是 DB 里 role 维度。两个维度不冲突：target_bucket 是组合视角，role_code
# 是角色视角。研究员接受建议时二者会一起持久化。
_BUCKET_TO_ROLE = {
    "core": "core",
    "satellite": "satellite",
    "exclude": "excluded",
    "observe": "observe",
}


def suggest_role_reviews(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅对 allocation_status == 'review_required' 的行给出建议。

    每条建议含：fund_code, role_code, decision, target_bucket,
    recommended_max_weight_pct, rationale（人类可读）。
    """
    suggestions: list[dict[str, Any]] = []
    for row in matrix_rows:
        if row.get("allocation_status") != "review_required":
            continue
        blocking = [str(r) for r in row.get("blocking_reasons", []) or []]
        watch = [str(r) for r in row.get("watch_reasons", []) or []]
        suggestion = _suggest_for_row(row, blocking, watch)
        suggestions.append(suggestion)
    return suggestions


def _suggest_for_row(
    row: dict[str, Any],
    blocking: list[str],
    watch: list[str],
) -> dict[str, Any]:
    """单行决策：先看 blocking 严重度，再看 watch 的方向。

    规则（按优先级）：
    1. data_insufficient → 排除，理由「数据不足，建议先排除」
    2. manual_review_required + 风险 cap → 观察 / 卫星，cap=8%
    3. style_unclassified 但 portfolio 角色已有 → 核心（待定），cap=10%
    4. 其他 review_required → 卫星，cap=5%
    """
    fund_code = str(row["fund_code"])
    if "data_insufficient" in blocking or "missing_data_window" in blocking:
        return {
            "fund_code": fund_code,
            "role_code": _BUCKET_TO_ROLE["exclude"],
            "decision": "suggest",
            "target_bucket": "exclude",
            "recommended_max_weight_pct": 0.0,
            "rationale": "数据不足，建议先排除：{}".format(
                _join_chinese(blocking) or "blocking_reasons 缺源"
            ),
        }
    if "manual_review_required" in blocking or "risk_cap" in blocking:
        # 风险超 cap：建议用观察分桶，等研究员重核
        return {
            "fund_code": fund_code,
            "role_code": _BUCKET_TO_ROLE["observe"],
            "decision": "suggest",
            "target_bucket": "observe",
            "recommended_max_weight_pct": 8.0,
            "rationale": "风险超 cap 或需复核：{}".format(
                _join_chinese(blocking + watch) or "manual_review_required"
            ),
        }
    if "style_unclassified" in watch or "style_pending_rule_definition" in watch:
        # 风格未分但组合维度 OK：可入核心，但 cap 收窄
        return {
            "fund_code": fund_code,
            "role_code": _BUCKET_TO_ROLE["core"],
            "decision": "suggest",
            "target_bucket": "core",
            "recommended_max_weight_pct": 10.0,
            "rationale": "风格未分但组合维度合格：{}".format(
                _join_chinese(watch) or "style_pending_rule_definition"
            ),
        }
    return {
        "fund_code": fund_code,
        "role_code": _BUCKET_TO_ROLE["satellite"],
        "decision": "suggest",
        "target_bucket": "satellite",
        "recommended_max_weight_pct": 5.0,
        "rationale": "默认建议：卫星仓位，{}".format(
            _join_chinese(blocking + watch) or "review_required 兜底"
        ),
    }


def _join_chinese(reasons: list[str]) -> str:
    """把英式 reason_code 拼成一句话，保留顺序去重。"""
    seen: list[str] = []
    for reason in reasons:
        if reason and reason not in seen:
            seen.append(reason)
    return "，".join(seen)
