"""Portfolio optimized weight 求解器（区分 dry-run vs 正式组合权重）。

输入是 build_portfolio_draft 的输出（dry-run 权重 + max_weight_pct），
输出在每只上额外加 optimized_weight_pct，等价于：以 draft 为初始点，
按 max_weight_pct cap 后把溢出按剩余基金原比例 redistribute，
再做归一化（sum-to-100%）。

这是 LP 的 closed-form 解，零外部依赖、审计可追溯。
"""
from __future__ import annotations

from typing import Any


def optimize_draft(
    draft_rows: list[dict[str, Any]],
    *,
    total_target_pct: float = 100.0,
) -> list[dict[str, Any]]:
    """对 draft rows 求 optimized_weight_pct，并补 max_weight_pct 状态。

    返回新 list，不修改入参；每行多出：
      - optimized_weight_pct (float)
      - optimized_status ("ok" | "capped" | "below_floor")
      - optimization_method ("cap_redistribute_v1")
    """
    if not draft_rows:
        return []

    raw = [float(row.get("draft_weight_pct", 0.0)) for row in draft_rows]
    caps = [max(0.0, float(row.get("max_weight_pct", total_target_pct))) for row in draft_rows]
    optimized = _cap_redistribute(raw, caps, total_target_pct)

    out: list[dict[str, Any]] = []
    for row, opt_w, cap, raw_w in zip(draft_rows, optimized, caps, raw):
        new_row = dict(row)
        new_row["optimized_weight_pct"] = round(opt_w, 4)
        # 触发了 cap：当且仅当 draft 想超 cap 且被 LP 钉回 cap
        new_row["optimized_status"] = (
            "capped" if raw_w > cap + 1e-6 else "ok"
        )
        new_row["optimization_method"] = "cap_redistribute_v1"
        out.append(new_row)
    return out


def _cap_redistribute(
    raw_weights: list[float],
    caps: list[float],
    total: float,
) -> list[float]:
    """带 cap 的 LP 闭式解：迭代缩放 + 剩余再分配。

    算法：
    1. 把 raw 等比例缩放到 total（sum=target）。
    2. 对超 cap 的，把 weight 钉到 cap，剩余按未钉点原比例承担。
    3. 重复 2，直到所有点 ≤ cap 或全部 cap=0。
    """
    n = len(raw_weights)
    if n == 0:
        return []
    raw_sum = sum(raw_weights)
    if raw_sum <= 0:
        # 全 0 时按 cap 等分
        cap_sum = sum(caps)
        if cap_sum <= 0:
            return [total / n] * n
        return [c / cap_sum * total for c in caps]

    # 初始：缩放到 total
    w = [x / raw_sum * total for x in raw_weights]
    fixed = [False] * n
    remaining_total = total
    remaining_indices: list[int] = []

    while True:
        # 更新剩余集合
        remaining_indices = [i for i in range(n) if not fixed[i]]
        if not remaining_indices:
            break
        # 当前剩余总权重
        w_remaining = sum(w[i] for i in remaining_indices)
        if w_remaining <= 0:
            # 退化：剩余全 0，按 cap 等分
            cap_sum = sum(caps[i] for i in remaining_indices)
            for i in remaining_indices:
                w[i] = (caps[i] / cap_sum * remaining_total) if cap_sum > 0 else 0.0
            break
        # 计算每个剩余点的「若不 cap，应承担多少」
        # 需要的总 = remaining_total
        scale = remaining_total / w_remaining
        overflow = []
        for i in remaining_indices:
            target = w[i] * scale
            if target >= caps[i] - 1e-9:
                # cap
                overflow.append(i)
            else:
                w[i] = target
        if not overflow:
            # 全部 fit
            break
        # 钉死溢出
        for i in overflow:
            w[i] = caps[i]
            fixed[i] = True
        # 剩余总量 = total - sum(capped)
        remaining_total = total - sum(caps[i] for i in range(n) if fixed[i])
        if remaining_total <= 0:
            # 全部 cap 之后已超 total，剩余置 0
            for i in range(n):
                if not fixed[i]:
                    w[i] = 0.0
            break
    return w


def summarize_optimization(optimized_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """从 optimized rows 提炼顶层 summary：total / capped_count / below_floor_count。"""
    if not optimized_rows:
        return {
            "total_weight_pct": 0.0,
            "optimized_funds": 0,
            "capped_count": 0,
            "method": "cap_redistribute_v1",
        }
    return {
        "total_weight_pct": round(
            sum(row.get("optimized_weight_pct", 0.0) for row in optimized_rows), 4
        ),
        "optimized_funds": len(optimized_rows),
        "capped_count": sum(
            1 for row in optimized_rows if row.get("optimized_status") == "capped"
        ),
        "method": "cap_redistribute_v1",
    }
