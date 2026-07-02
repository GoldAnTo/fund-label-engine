from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader


def _join(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, list):
        return ", ".join(str(item) for item in values)
    return str(values)


def _calculation_state(
    conn: sqlite3.Connection,
    run_id: str,
    fund_code: str,
    label_code: str,
) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            "SELECT state, reason_code, observed, threshold, source, message "
            "FROM label_calculation_states "
            "WHERE run_id = ? AND fund_code = ? AND label_code = ?",
            (run_id, fund_code, label_code),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _benchmark_profile(conn: sqlite3.Connection, fund_code: str) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    try:
        row = conn.execute(
            "SELECT benchmark, tracking_target FROM fund_profiles WHERE fund_code = ?",
            (fund_code,),
        ).fetchone()
        if row:
            profile.update(dict(row))
    except sqlite3.OperationalError:
        pass
    try:
        components = conn.execute(
            "SELECT component_code, component_name, weight, status, reason, secid "
            "FROM benchmark_components WHERE fund_code = ? ORDER BY component_order",
            (fund_code,),
        ).fetchall()
        profile["components"] = [dict(row) for row in components]
    except sqlite3.OperationalError:
        profile["components"] = []
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM benchmark_returns "
            "WHERE fund_code = ? AND daily_return IS NOT NULL",
            (fund_code,),
        ).fetchone()["c"]
        profile["benchmark_sample_count"] = int(count or 0)
    except sqlite3.OperationalError:
        profile["benchmark_sample_count"] = 0
    return profile


def _required_fix(profile: dict[str, Any], state: dict[str, Any] | None) -> str:
    components = profile.get("components", [])
    if not components:
        return "complete_benchmark_mapping"
    unresolved = [row for row in components if row.get("status") != "resolved"]
    mapping_required = [
        row
        for row in components
        if row.get("reason") == "exact_component_mapping_required"
    ]
    if mapping_required:
        return "confirm_exact_component_mapping"
    if unresolved:
        return "resolve_benchmark_components"
    if profile.get("benchmark_sample_count", 0) < 180:
        return "complete_benchmark_quote_window"
    if state and state.get("state") != "not_triggered":
        return "rerun_labels_after_benchmark_source_fix"
    return "verify_benchmark_gap_clearance"


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
        if "benchmark_data_missing" in row.get("watch_reasons", [])
    ]
    details: list[dict[str, Any]] = []
    with sqlite3.connect(output_db) as conn:
        conn.row_factory = sqlite3.Row
        for row in rows:
            fund_code = row["fund_code"]
            state = _calculation_state(
                conn,
                selected_run_id,
                fund_code,
                "benchmark_data_missing",
            )
            profile = _benchmark_profile(conn, fund_code)
            details.append(
                {
                    "fund_code": fund_code,
                    "roles": row.get("portfolio_roles", []),
                    "return_tags": row.get("return_tags", []),
                    "risk_tags": row.get("risk_tags", []),
                    "allocation_status": row.get("allocation_status"),
                    "benchmark": profile.get("benchmark", ""),
                    "tracking_target": profile.get("tracking_target", ""),
                    "benchmark_sample_count": profile.get("benchmark_sample_count", 0),
                    "calculation_state": state.get("state", "") if state else "missing_state",
                    "calculation_reason": state.get("reason_code", "") if state else "missing_state",
                    "required_fix": _required_fix(profile, state),
                }
            )

    fix_counts = Counter(row["required_fix"] for row in details)
    lines = [
        "# Benchmark Gap Portfolio Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"benchmark_data_missing_count: {len(details)}",
        "",
        "## Required Fix Counts",
        "",
        "| required_fix | count |",
        "| --- | ---: |",
    ]
    if fix_counts:
        for fix, count in sorted(fix_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{fix}` | {count} |")
    else:
        lines.append("| `(none)` | 0 |")

    lines += [
        "",
        "## Benchmark Gap Funds",
        "",
        "| fund_code | status | roles | return_tags | risk_tags | bench_n | calc_state | required_fix | benchmark |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    if details:
        for row in sorted(details, key=lambda item: (item["required_fix"], item["fund_code"])):
            benchmark = str(row.get("benchmark") or row.get("tracking_target") or "").replace("|", "/")
            lines.append(
                f"| `{row['fund_code']}` | `{row['allocation_status']}` | {_join(row['roles'])} | "
                f"{_join(row['return_tags'])} | {_join(row['risk_tags'])} | "
                f"{row['benchmark_sample_count']} | `{row['calculation_state']}:{row['calculation_reason']}` | "
                f"`{row['required_fix']}` | {benchmark} |"
            )
    else:
        lines.append("| (none) |  |  |  |  | 0 |  |  |  |")

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "gap_count": len(details)}


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
    print(f"wrote {args.out_md} (run_id={summary['run_id']}, gaps={summary['gap_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
