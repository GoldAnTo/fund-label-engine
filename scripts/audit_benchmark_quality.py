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


def _component_has_source(component: dict[str, Any], component_codes_with_returns: set[str]) -> bool:
    """判断单个组件是否有可用日收益源。

    - synthetic 利率组件（secid 形如 ``synthetic:xxx``）可被确定性合成，自带源。
    - 可实时拉取的数字指数码（secid 形如 ``1.000300`` / ``0.399006`` / ``2.932000``）
      由 fetch 脚本直接从行情源取，视为有源；它们在 ``benchmark_returns`` 里以复合串
      形式落库，不会以单个 code 出现，因此不能靠字符串匹配来判断。
    - 其余（LOCAL_* 债券指数等）只有出现在已落库的收益表里才算有源。
    """
    secid = str(component.get("secid") or "")
    code = component.get("component_code")
    if secid.startswith("synthetic:"):
        return True
    if _is_live_numeric_secid(secid):
        return True
    return bool(code) and str(code) in component_codes_with_returns


def _is_live_numeric_secid(secid: str) -> bool:
    prefix, _, body = secid.partition(".")
    return prefix in {"0", "1", "2"} and body.isdigit()


def classify_component(component: dict[str, Any], component_codes_with_returns: set[str]) -> str:
    status = str(component.get("status") or "")
    reason = str(component.get("reason") or "")
    if reason == "benchmark_missing":
        return "benchmark_missing"
    if reason == "exact_component_mapping_required":
        return "mapping_required"
    if status != "resolved":
        return "unresolved"
    if _component_has_source(component, component_codes_with_returns):
        return "ready"
    return "missing_source"


def summarize_fund_quality(
    components: list[dict[str, Any]],
    component_codes_with_returns: set[str],
    has_composed_returns: bool = False,
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
    # 真相优先：所有组件都 resolved 且实际已合成出 benchmark_returns，即为 ready。
    # 这避免了债券/利率等组件因不单独落库而把已成功合成的基金误判为 missing_source。
    if has_composed_returns and all(status != "unresolved" and status != "mapping_required" and status != "benchmark_missing" for status, _ in classified):
        return {"quality_status": "ready", "blocking_components": ""}
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
    """返回已合成/落库的成分代码集合。

    当 source DB 缺 benchmark_returns / benchmark_component_returns 表时
    （例如历史库未跑过 fetch_benchmark_returns），优雅降级返回空集，
    让上层 audit 把它判为 benchmark_source_missing，而不是抛 503。
    """
    codes: set[str] = set()
    for table in ("benchmark_returns", "benchmark_component_returns"):
        try:
            rows = conn.execute(
                f"""
                SELECT DISTINCT benchmark_code AS component_code
                FROM {table}
                WHERE benchmark_code IS NOT NULL
                """
                if table == "benchmark_returns"
                else f"""
                SELECT DISTINCT component_code
                FROM {table}
                WHERE component_code IS NOT NULL
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "no such table" in msg or "no such column" in msg:
                continue
            raise
        for row in rows:
            value = row["component_code"]
            if value:
                codes.add(str(value))
    return codes


def build_quality_rows(conn: sqlite3.Connection, codes: list[str]) -> list[dict[str, str]]:
    component_codes_with_returns = load_component_codes_with_returns(conn)
    placeholders = ",".join("?" for _ in codes)

    # 探测 source DB 是否含 benchmark_components / benchmark_returns。
    # 缺表时（未跑过 fetch_benchmark_returns）优雅降级：每个基金都判为
    # benchmark_source_missing，不抛 503。
    def _has_table(name: str) -> bool:
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
            return row is not None
        except sqlite3.OperationalError:
            return False

    has_components_table = _has_table("benchmark_components")
    has_returns_table = _has_table("benchmark_returns")

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
        components: list[dict[str, Any]] = []
        if has_components_table:
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
        has_returns = None
        if has_returns_table:
            has_returns = conn.execute(
                "SELECT 1 FROM benchmark_returns WHERE fund_code = ? LIMIT 1",
                (profile["fund_code"],),
            ).fetchone()
        summary = summarize_fund_quality(
            components,
            component_codes_with_returns,
            has_composed_returns=bool(has_returns),
        )
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
