from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader

RISK_REVIEW_TAGS = {
    "beta_high",
    "drawdown_high",
    "holding_concentration_high",
    "industry_concentration_high",
    "volatility_high",
}
CORE_RISK_REVIEW_TAGS = {
    "beta_high",
    "drawdown_high",
    "volatility_high",
}
CALIBRATION_ROLES = {
    "core_holding_candidate",
    "satellite_alpha",
    "index_tool",
}


def _join(values: list[str] | None) -> str:
    return ", ".join(values or [])


def _decision_reason(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    risk_tags = set(row.get("risk_tags") or [])
    roles = set(row.get("portfolio_roles") or [])
    watch_reasons = set(row.get("watch_reasons") or [])

    if row["allocation_status"] == "eligible":
        reasons.append("eligible_candidate")
    if risk_tags & RISK_REVIEW_TAGS:
        reasons.append("eligible_with_allocation_risk_review")
    if "core_holding_candidate" in roles and risk_tags & CORE_RISK_REVIEW_TAGS:
        reasons.append("core_candidate_with_core_risk_review")
    if "style_pending_rule_definition" in watch_reasons:
        reasons.append("active_equity_waiting_style_rule")
    if "benchmark_data_missing" in watch_reasons:
        reasons.append("benchmark_data_missing")
    return ", ".join(reasons or ["human_decision_required"])


def _requires_calibration(row: dict[str, Any]) -> bool:
    roles = set(row.get("portfolio_roles") or [])
    watch_reasons = set(row.get("watch_reasons") or [])
    return (
        row["allocation_status"] == "eligible"
        or bool(roles & CALIBRATION_ROLES)
        or "benchmark_data_missing" in watch_reasons
    )


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

    rows = [row for row in matrix["rows"] if _requires_calibration(row)]
    rows = sorted(
        rows,
        key=lambda row: (
            row["allocation_status"] != "eligible",
            "benchmark_data_missing" in row.get("watch_reasons", []),
            row["fund_code"],
        ),
    )

    lines = [
        "# Portfolio Calibration Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"candidate_count: {len(rows)}",
        "",
        "| fund_code | status | roles | return_tags | risk_tags | watch | decision_reason | required_action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        decision_reason = _decision_reason(row)
        required_action = "human_decision_required"
        lines.append(
            f"| `{row['fund_code']}` | `{row['allocation_status']}` | "
            f"{_join(row.get('portfolio_roles'))} | {_join(row.get('return_tags'))} | "
            f"{_join(row.get('risk_tags'))} | {_join(row.get('watch_reasons'))} | "
            f"{decision_reason} | `{required_action}` |"
        )

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "candidate_count": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
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
        f"wrote {args.out_md} "
        f"(run_id={summary['run_id']}, candidates={summary['candidate_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
