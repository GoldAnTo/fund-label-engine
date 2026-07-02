from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader


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
    mode: str = "research",
) -> dict[str, Any]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    draft = reader.get_portfolio_draft(selected_run_id, mode=mode)
    if draft is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    title = "Portfolio Final Accepted Report" if mode == "accepted" else "Portfolio Draft Report"
    lines = [
        f"# {title}",
        "",
        f"run_id: `{selected_run_id}`",
        f"mode: `{draft.get('mode', mode)}`",
        f"rule_version: `{draft.get('rule_version', '')}`",
        f"objective: `{draft['objective']}`",
        f"config_version: `{draft['config_version']}`",
        "",
        "## Draft Weights",
        "",
        "| fund_code | bucket | draft_weight_pct | optimized_weight_pct | max_weight_pct | score | roles | risk_tags |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    rows = list(draft["rows"])
    if rows:
        for row in rows:
            lines.append(
                f"| `{row['fund_code']}` | `{row['bucket']}` | "
                f"{row['draft_weight_pct']:.2f} | {row.get('optimized_weight_pct', row['draft_weight_pct']):.2f} | "
                f"{row['max_weight_pct']:.2f} | {row['score']:.2f} | {_join(row.get('portfolio_roles'))} | "
                f"{_join(row.get('risk_tags'))} |"
            )
    else:
        lines.append("| (none) |  |  |  |  |  |  |  |")

    lines += [
        "",
        "## Excluded",
        "",
        "| fund_code | reasons |",
        "| --- | --- |",
    ]
    excluded = list(draft["excluded"])
    if excluded:
        for row in excluded:
            lines.append(f"| `{row['fund_code']}` | {_join(row['reasons'])} |")
    else:
        lines.append("| (none) |  |")

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "mode": mode, "row_count": len(rows), "excluded_count": len(excluded)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--mode", choices=["research", "accepted"], default="research")
    args = parser.parse_args(argv)
    summary = render_report(
        output_db=args.output_db,
        out_md=args.out_md,
        run_id=args.run_id,
        mode=args.mode,
    )
    print(
        "wrote {out_md} (run_id={run_id}, mode={mode}, rows={row_count}, excluded={excluded_count})".format(
            out_md=args.out_md,
            **summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
