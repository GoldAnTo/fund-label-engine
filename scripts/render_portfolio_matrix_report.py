"""Portfolio Matrix v1 报告。

把每只基金的原子标签、分组、分类和特征压成组合构建视角：
- allocation_status: eligible / observe / review_required
- portfolio_roles: core / satellite / defensive / style / low_cost 等候选角色
- watch / risk / data blockers: 解释为什么不能直接进入组合池
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader

CORE_RISK_REVIEW_TAGS = {
    "beta_high",
    "drawdown_high",
    "volatility_high",
}
ALLOCATION_RISK_REVIEW_TAGS = CORE_RISK_REVIEW_TAGS | {
    "holding_concentration_high",
    "industry_concentration_high",
}
STYLE_WEIGHT_KEYS = (
    "quality_growth_weight",
    "deep_value_weight",
    "dividend_steady_weight",
)


def _style_pending_reason(row: dict[str, Any]) -> str:
    features = row.get("features", {})
    has_style_weight = any(features.get(key) is not None for key in STYLE_WEIGHT_KEYS)
    if not has_style_weight:
        return "style_weight_missing"
    if not row.get("style_tags"):
        return "style_weight_below_formal_threshold"
    return "style_label_present_but_watch_not_cleared"


def _join(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return ", ".join(str(item) for item in values)
    if isinstance(values, dict):
        return ", ".join(f"{key}={value}" for key, value in values.items())
    return str(values)


def _count_values(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, list):
            counts.update(str(item) for item in value)
        elif value:
            counts[str(value)] += 1
    return counts


def _format_count_table(title: str, counts: Counter[str]) -> list[str]:
    lines = [f"## {title}", "", "| item | count |", "| --- | ---: |"]
    if not counts:
        lines.append("| (none) | 0 |")
        lines.append("")
        return lines
    for item, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{item}` | {count} |")
    lines.append("")
    return lines


def _format_fund_table(title: str, rows: list[dict[str, Any]], limit: int) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| fund_code | status | roles | style_tags | return_tags | risk_tags | watch/blocking |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| (none) |  |  |  |  |  |  |")
        lines.append("")
        return lines
    for row in rows[:limit]:
        reasons = row.get("blocking_reasons") or row.get("watch_reasons") or []
        lines.append(
            "| `{fund_code}` | `{status}` | {roles} | {style_tags} | "
            "{return_tags} | {risk_tags} | {reasons} |".format(
                fund_code=row["fund_code"],
                status=row["allocation_status"],
                roles=_join(row.get("portfolio_roles")),
                style_tags=_join(row.get("style_tags")),
                return_tags=_join(row.get("return_tags")),
                risk_tags=_join(row.get("risk_tags")),
                reasons=_join(reasons),
            )
        )
    lines.append("")
    return lines


def _has_any(row: dict[str, Any], key: str, values: set[str]) -> bool:
    return bool(set(row.get(key) or []) & values)


def _role_quality_checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = [
        {
            "check": "eligible_with_allocation_risk_review",
            "description": "Eligible means data-ready, but these funds still need risk sizing review.",
            "rows": [
                row
                for row in rows
                if row["allocation_status"] == "eligible"
                and _has_any(row, "risk_tags", ALLOCATION_RISK_REVIEW_TAGS)
            ],
        },
        {
            "check": "core_candidate_with_core_risk_review",
            "description": "Core candidates with high beta/drawdown/volatility tags should not be treated as final core holdings.",
            "rows": [
                row
                for row in rows
                if "core_holding_candidate" in row.get("portfolio_roles", [])
                and _has_any(row, "risk_tags", CORE_RISK_REVIEW_TAGS)
            ],
        },
        {
            "check": "active_equity_waiting_style_rule",
            "description": "Active equity candidates still blocked by pending style rules.",
            "rows": [
                row
                for row in rows
                if "active_equity_candidate" in row.get("portfolio_roles", [])
                and "style_pending_rule_definition" in row.get("watch_reasons", [])
            ],
        },
        {
            "check": "benchmark_data_missing",
            "description": "Relative labels should not be trusted for these funds until benchmark data is completed.",
            "rows": [
                row
                for row in rows
                if "benchmark_data_missing" in row.get("watch_reasons", [])
            ],
        },
    ]
    return [
        {
            "check": item["check"],
            "description": item["description"],
            "count": len(item["rows"]),
            "examples": [row["fund_code"] for row in item["rows"][:8]],
        }
        for item in checks
    ]


def _format_quality_checks(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Role Quality Checks",
        "",
        "| check | count | examples | note |",
        "| --- | ---: | --- | --- |",
    ]
    for item in _role_quality_checks(rows):
        lines.append(
            "| `{check}` | {count} | {examples} | {description} |".format(
                check=item["check"],
                count=item["count"],
                examples=", ".join(f"`{code}`" for code in item["examples"]),
                description=item["description"],
            )
        )
    lines.append("")
    return lines


def _format_style_pending_reasons(rows: list[dict[str, Any]]) -> list[str]:
    pending = [
        row
        for row in rows
        if "style_pending_rule_definition" in row.get("watch_reasons", [])
    ]
    counts = Counter(_style_pending_reason(row) for row in pending)
    lines = [
        "## Style Pending Reasons",
        "",
        "| reason | count |",
        "| --- | ---: |",
    ]
    if not counts:
        lines.append("| (none) | 0 |")
    else:
        for reason, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| `{reason}` | {count} |")
    lines.append("")
    return lines


def render_report(
    *,
    output_db: str | Path,
    out_md: str | Path,
    run_id: str | None = None,
    top_n: int = 30,
) -> dict[str, Any]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")

    matrix = reader.get_portfolio_matrix(selected_run_id)
    if matrix is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    rows = list(matrix["rows"])
    status_counts = Counter(str(row["allocation_status"]) for row in rows)
    role_counts = _count_values(rows, "portfolio_roles")
    watch_counts = _count_values(rows, "watch_reasons")
    risk_counts = _count_values(rows, "risk_tags")
    blocking_counts = _count_values(rows, "blocking_reasons")

    eligible_rows = [
        row for row in rows if row["allocation_status"] == "eligible"
    ]
    observe_rows = [
        row
        for row in rows
        if row["allocation_status"] in {"observe", "review_required"}
    ]

    config = matrix.get("portfolio_config", {})
    lines = [
        "# Portfolio Matrix v1 Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"rule_version: `{matrix.get('rule_version', '')}`",
        f"portfolio_objective: `{config.get('objective', '')}`",
        f"portfolio_config_version: `{config.get('version', '')}`",
        f"total_count: {matrix.get('total_count', len(rows))}",
        "",
        "## How To Read",
        "",
        "- `eligible`: data-ready for role screening; still obey risk tags before sizing.",
        "- `observe`: has useful labels, but still has watch reasons that need calibration or source completion.",
        "- `review_required`: blocked by missing data or manual review.",
        "",
    ]
    lines += _format_count_table("Allocation Status", status_counts)
    lines += _format_count_table("Portfolio Roles", role_counts)
    lines += _format_quality_checks(rows)
    lines += _format_style_pending_reasons(rows)
    lines += _format_count_table("Watch Reasons", watch_counts)
    lines += _format_count_table("Risk Tags", risk_counts)
    lines += _format_count_table("Blocking Reasons", blocking_counts)
    lines += _format_fund_table("Eligible Funds", eligible_rows, top_n)
    lines += _format_fund_table("Observe / Review Work Queue", observe_rows, top_n)

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "run_id": selected_run_id,
        "total_count": len(rows),
        "eligible_count": status_counts.get("eligible", 0),
        "observe_count": status_counts.get("observe", 0),
        "review_required_count": status_counts.get("review_required", 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--top-n", type=int, default=30)
    args = parser.parse_args(argv)

    summary = render_report(
        output_db=args.output_db,
        out_md=args.out_md,
        run_id=args.run_id,
        top_n=args.top_n,
    )
    print(
        "wrote {out_md} "
        "(run_id={run_id}, total={total_count}, eligible={eligible_count})".format(
            out_md=args.out_md,
            **summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
