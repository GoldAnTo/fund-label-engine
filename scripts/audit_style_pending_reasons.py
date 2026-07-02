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


def style_pending_reason(row: dict[str, Any]) -> str:
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
        f"style_pending_label: `style_pending_rule_definition`",
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
