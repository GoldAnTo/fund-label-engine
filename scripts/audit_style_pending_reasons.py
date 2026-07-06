from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader

STYLE_WEIGHT_KEYS = (
    "quality_growth_weight",
    "deep_value_weight",
    "dividend_steady_weight",
)


# 二级拆分阈值（与 rules.v1.json 的 style_exposure_*_coverage_threshold 对齐）
COVERAGE_LOW = 0.5
COVERAGE_FORMAL = 0.7
# 风格权重：>= 0.2 视为「显著」（与 style_balanced_weight_min 对齐）
STYLE_WEIGHT_SIGNIFICANT = 0.2


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def style_pending_reason(row: dict[str, Any]) -> str:
    """二级拆分：让 95 → {data_missing, coverage_low, coverage_observe, exposure_imbalanced, label_conflict}。

    优先级：data_missing > coverage_low > coverage_observe > exposure_imbalanced > label_conflict
    """
    features = row.get("features", {})
    weights = [_to_float(features.get(key)) for key in STYLE_WEIGHT_KEYS]
    has_any_weight = any(w is not None for w in weights)

    if not has_any_weight:
        return "style_data_missing"

    coverage = _to_float(features.get("factor_coverage_weight"))
    if coverage is None or coverage < COVERAGE_LOW:
        return "style_factor_coverage_low"
    if coverage < COVERAGE_FORMAL:
        return "style_factor_coverage_observe"

    significant_count = sum(1 for w in weights if w is not None and w >= STYLE_WEIGHT_SIGNIFICANT)
    if significant_count < 2:
        return "style_exposure_imbalanced"

    if row.get("style_tags"):
        return "style_label_emitted_but_pending"

    return "style_exposure_below_formal_threshold"


def _join(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return ", ".join(str(item) for item in values)
    return str(values)


def render_report(
    *,
    output_db: str | Path,
    out_md: str | Path,
    run_id: str | None = None,
) -> dict[str, Any]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    matrix = reader.get_portfolio_matrix(selected_run_id)
    if matrix is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    rows = [
        row
        for row in matrix["rows"]
        if "style_pending_rule_definition" in row.get("watch_reasons", [])
    ]
    reason_counts = Counter(style_pending_reason(row) for row in rows)

    lines = [
        "# Style Pending Reason Audit",
        "",
        f"run_id: `{selected_run_id}`",
        "style_pending_label: `style_pending_rule_definition`",
        f"style_pending_count: {len(rows)}",
        "",
        "| reason | count |",
        "| --- | ---: |",
    ]
    if reason_counts:
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{reason}` | {count} |")
    else:
        lines.append("| `(none)` | 0 |")

    lines += [
        "",
        "## Examples",
        "",
        "| fund_code | reason | roles | style_tags | style_weights | watch_reasons |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if rows:
        for row in rows[:50]:
            features = row.get("features", {})
            style_weights = ", ".join(
                f"{key}={features.get(key)}"
                for key in STYLE_WEIGHT_KEYS
                if features.get(key) is not None
            )
            lines.append(
                f"| `{row['fund_code']}` | `{style_pending_reason(row)}` | "
                f"{_join(row.get('portfolio_roles'))} | {_join(row.get('style_tags'))} | "
                f"{style_weights} | {_join(row.get('watch_reasons'))} |"
            )
    else:
        lines.append("| (none) |  |  |  |  |  |")

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "style_pending_count": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    summary = render_report(
        output_db=args.output_db,
        out_md=args.out_md,
        run_id=args.run_id,
    )
    print(
        "wrote {out_md} (run_id={run_id}, pending={style_pending_count})".format(
            out_md=args.out_md,
            **summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
