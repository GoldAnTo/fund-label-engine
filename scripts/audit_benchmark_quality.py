from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Any


QUALITY_ORDER = {
    "ready": 0,
    "missing_source": 1,
    "mapping_required": 2,
    "unresolved": 3,
    "benchmark_missing": 4,
}


def read_codes(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def classify_component(component: dict[str, Any], component_codes_with_returns: set[str]) -> str:
    status = str(component.get("status") or "")
    reason = str(component.get("reason") or "")
    code = component.get("component_code")
    if reason == "benchmark_missing":
        return "benchmark_missing"
    if reason == "exact_component_mapping_required":
        return "mapping_required"
    if status != "resolved":
        return "unresolved"
    if code and str(code) in component_codes_with_returns:
        return "ready"
    return "missing_source"


def summarize_fund_quality(
    components: list[dict[str, Any]],
    component_codes_with_returns: set[str],
) -> dict[str, str]:
    if not components:
        return {
            "quality_status": "benchmark_missing",
            "blocking_components": "",
        }
    classified = [
        (classify_component(component, component_codes_with_returns), component)
        for component in components
    ]
    worst_status = max(classified, key=lambda item: QUALITY_ORDER[item[0]])[0]
    blockers = [
        f"{component.get('component_code') or ''}:{component.get('component_name') or ''}".strip(":")
        for status, component in classified
        if status != "ready"
    ]
    return {
        "quality_status": worst_status,
        "blocking_components": ";".join(blockers),
    }


def load_component_codes_with_returns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT benchmark_code AS component_code
        FROM benchmark_returns
        WHERE benchmark_code IS NOT NULL
        UNION
        SELECT DISTINCT component_code
        FROM benchmark_component_returns
        WHERE component_code IS NOT NULL
        """
    ).fetchall()
    return {str(row["component_code"]) for row in rows if row["component_code"]}


def build_quality_rows(conn: sqlite3.Connection, codes: list[str]) -> list[dict[str, str]]:
    component_codes_with_returns = load_component_codes_with_returns(conn)
    placeholders = ",".join("?" for _ in codes)
    profile_rows = conn.execute(
        f"""
        SELECT fund_code, fund_name, fund_type, benchmark, tracking_target
        FROM fund_profiles
        WHERE fund_code IN ({placeholders})
        ORDER BY fund_code
        """,
        codes,
    ).fetchall()
    rows: list[dict[str, str]] = []
    for profile in profile_rows:
        components = [
            dict(row)
            for row in conn.execute(
                """
                SELECT component_code, component_name, weight, source_text, status, reason, secid
                FROM benchmark_components
                WHERE fund_code = ?
                ORDER BY component_order
                """,
                (profile["fund_code"],),
            ).fetchall()
        ]
        summary = summarize_fund_quality(components, component_codes_with_returns)
        has_returns = conn.execute(
            "SELECT 1 FROM benchmark_returns WHERE fund_code = ? LIMIT 1",
            (profile["fund_code"],),
        ).fetchone()
        rows.append(
            {
                "fund_code": profile["fund_code"],
                "fund_name": profile["fund_name"] or "",
                "fund_type": profile["fund_type"] or "",
                "quality_status": summary["quality_status"],
                "has_benchmark_returns": "yes" if has_returns else "no",
                "blocking_components": summary["blocking_components"],
                "benchmark": profile["benchmark"] or "",
                "tracking_target": profile["tracking_target"] or "",
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    fieldnames = [
        "fund_code",
        "fund_name",
        "fund_type",
        "quality_status",
        "has_benchmark_returns",
        "blocking_components",
        "benchmark",
        "tracking_target",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], path: str | Path) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["quality_status"]] = counts.get(row["quality_status"], 0) + 1
    lines = [
        "# Benchmark Quality Gate Report",
        "",
        "## Status Counts",
        "",
        "| status | funds |",
        "|---|---:|",
    ]
    for status, count in sorted(counts.items(), key=lambda item: item[0]):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Blocked Funds",
            "",
            "| fund_code | fund_name | status | blocking_components | benchmark |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        if row["quality_status"] == "ready":
            continue
        benchmark = row["benchmark"].replace("|", "/")
        blockers = row["blocking_components"].replace("|", "/")
        lines.append(
            f"| `{row['fund_code']}` | {row['fund_name']} | `{row['quality_status']}` | "
            f"{blockers} | {benchmark} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit benchmark mapping and source quality.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--codes-file", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args(argv)

    codes = read_codes(args.codes_file)
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        rows = build_quality_rows(conn, codes)
    write_csv(rows, args.csv)
    write_markdown(rows, args.markdown)
    print(f"benchmark_quality_rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
