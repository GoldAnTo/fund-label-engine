"""相对基准标签可用性审计（三层状态收口）。

把"基准源 ready"向下接一层，区分清楚一只基金能否正式展示
Alpha / Beta / 超额收益等相对基准标签。每只基金输出三层状态：

1. benchmark_source_status —— 复用 benchmark quality audit
   （ready / missing_source / mapping_required / unresolved / benchmark_missing）
2. return_window_status —— NAV 与合成基准对齐后是否满足 1Y 窗口 180 样本门槛
   （ready / nav_window_insufficient）
3. relative_label_status —— 只有前两层都 ready 才是 relative_label_ready，
   否则按根因归类：benchmark_source_missing / benchmark_mapping_required /
   benchmark_unresolved / benchmark_missing / nav_window_insufficient

口径与跑批一致：跑批相对标签按 aligned=min(nav, benchmark) 的最近 252 天窗口、
要求 >= 180 样本，因此这里用 min(nav_sample_count, benchmark_sample_count) 判定。
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.audit_benchmark_quality import build_quality_rows, read_codes

NAV_WINDOW_MIN_SAMPLES = 180

_SOURCE_BLOCK_REASON = {
    "missing_source": "benchmark_source_missing",
    "mapping_required": "benchmark_mapping_required",
    "unresolved": "benchmark_unresolved",
    "benchmark_missing": "benchmark_missing",
}


def classify_relative_eligibility(
    benchmark_source_status: str,
    nav_sample_count: int,
    benchmark_sample_count: int,
    benchmark_precision: str = "exact",
) -> dict[str, Any]:
    aligned = min(nav_sample_count, benchmark_sample_count)
    nav_ready = nav_sample_count >= NAV_WINDOW_MIN_SAMPLES
    aligned_ready = aligned >= NAV_WINDOW_MIN_SAMPLES
    return_window_status = "ready" if aligned_ready else "nav_window_insufficient"

    if benchmark_source_status != "ready":
        relative_label_status = _SOURCE_BLOCK_REASON.get(
            benchmark_source_status, "benchmark_unresolved"
        )
        blocking_reason = f"benchmark_source_status={benchmark_source_status}"
    elif not aligned_ready:
        relative_label_status = "nav_window_insufficient"
        if not nav_ready:
            blocking_reason = f"nav_sample_count={nav_sample_count}<{NAV_WINDOW_MIN_SAMPLES}"
        else:
            blocking_reason = (
                f"aligned_sample_count={aligned}<{NAV_WINDOW_MIN_SAMPLES} "
                f"(nav={nav_sample_count}, benchmark={benchmark_sample_count})"
            )
    elif benchmark_precision == "approx":
        # 源就绪、窗口足够，但基准用的是显式近似源：单列一档，
        # 相对标签可用但需按“近似基准”解读，不与精确就绪同池。
        relative_label_status = "relative_label_ready_approx"
        blocking_reason = "benchmark_precision=approx"
    else:
        relative_label_status = "relative_label_ready"
        blocking_reason = ""

    return {
        "return_window_status": return_window_status,
        "relative_label_status": relative_label_status,
        "blocking_reason": blocking_reason,
    }


def _nav_sample_count(conn: sqlite3.Connection, fund_code: str) -> int:
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(nav_history)").fetchall()
    }
    return_col = "daily_growth_rate" if "daily_growth_rate" in cols else "daily_return"
    return conn.execute(
        f"SELECT count(*) FROM nav_history "
        f"WHERE fund_code = ? AND {return_col} IS NOT NULL",
        (fund_code,),
    ).fetchone()[0]


def _benchmark_sample_count(conn: sqlite3.Connection, fund_code: str) -> int:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_returns'"
    ).fetchone()
    if table is None:
        return 0
    return conn.execute(
        "SELECT count(*) FROM benchmark_returns "
        "WHERE fund_code = ? AND daily_return IS NOT NULL",
        (fund_code,),
    ).fetchone()[0]


def build_eligibility_rows(
    conn: sqlite3.Connection,
    codes: list[str],
    quality_by_code: dict[str, dict[str, str]],
    precision_by_code: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    precision_by_code = precision_by_code or {}
    rows: list[dict[str, Any]] = []
    for fund_code in codes:
        quality = quality_by_code.get(fund_code)
        if quality is None:
            continue
        nav_count = _nav_sample_count(conn, fund_code)
        bench_count = _benchmark_sample_count(conn, fund_code)
        precision = precision_by_code.get(fund_code, "exact")
        verdict = classify_relative_eligibility(
            benchmark_source_status=quality["quality_status"],
            nav_sample_count=nav_count,
            benchmark_sample_count=bench_count,
            benchmark_precision=precision,
        )
        rows.append(
            {
                "fund_code": fund_code,
                "fund_name": quality.get("fund_name", ""),
                "benchmark_source_status": quality["quality_status"],
                "benchmark_precision": precision,
                "nav_sample_count": nav_count,
                "benchmark_sample_count": bench_count,
                "return_window_status": verdict["return_window_status"],
                "relative_label_status": verdict["relative_label_status"],
                "blocking_reason": verdict["blocking_reason"],
                "blocking_components": quality.get("blocking_components", ""),
            }
        )
    return rows


_CSV_FIELDS = [
    "fund_code",
    "fund_name",
    "benchmark_source_status",
    "benchmark_precision",
    "nav_sample_count",
    "benchmark_sample_count",
    "return_window_status",
    "relative_label_status",
    "blocking_reason",
    "blocking_components",
]


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _CSV_FIELDS})


def write_markdown(rows: list[dict[str, Any]], path: str | Path) -> None:
    rel_counts = Counter(r["relative_label_status"] for r in rows)
    src_counts = Counter(r["benchmark_source_status"] for r in rows)
    lines = [
        "# Relative-Benchmark Eligibility Audit",
        "",
        f"Total funds: {len(rows)}",
        "",
        "三层状态收口：基准源 ready 不等于相对标签 ready。relative_label_ready "
        "才是可正式展示 Alpha/Beta/超额收益的池子。",
        "",
        "## relative_label_status Counts",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status in [
        "relative_label_ready",
        "relative_label_ready_approx",
        "nav_window_insufficient",
        "benchmark_source_missing",
        "benchmark_mapping_required",
        "benchmark_unresolved",
        "benchmark_missing",
    ]:
        if rel_counts.get(status):
            lines.append(f"| `{status}` | {rel_counts[status]} |")
    lines += [
        "",
        "## benchmark_source_status Counts",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, count in src_counts.most_common():
        lines.append(f"| `{status}` | {count} |")

    insufficient = [
        r for r in rows if r["relative_label_status"] == "nav_window_insufficient"
    ]
    lines += [
        "",
        "## benchmark_ready 但 NAV 不足（可通过补 NAV 解决）",
        "",
        "| fund_code | fund_name | nav_sample_count | benchmark_sample_count | blocking_reason |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for r in sorted(insufficient, key=lambda x: x["nav_sample_count"]):
        lines.append(
            f"| `{r['fund_code']}` | {r['fund_name']} | {r['nav_sample_count']} "
            f"| {r['benchmark_sample_count']} | {r['blocking_reason']} |"
        )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--codes-file", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args(argv)

    codes = read_codes(args.codes_file)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from app.benchmark_precision import benchmark_precision_by_fund

    precision_by_code = benchmark_precision_by_fund(args.db)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        quality_rows = build_quality_rows(conn, codes)
        quality_by_code = {r["fund_code"]: r for r in quality_rows}
        rows = build_eligibility_rows(conn, codes, quality_by_code, precision_by_code)
    finally:
        conn.close()

    write_csv(rows, args.csv)
    write_markdown(rows, args.markdown)
    rel_counts = Counter(r["relative_label_status"] for r in rows)
    print(
        f"relative_label_ready={rel_counts.get('relative_label_ready', 0)} "
        f"relative_label_ready_approx={rel_counts.get('relative_label_ready_approx', 0)} "
        f"nav_window_insufficient={rel_counts.get('nav_window_insufficient', 0)} "
        f"total={len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
