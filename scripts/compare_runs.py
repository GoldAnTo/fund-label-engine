#!/usr/bin/env python3
"""对比两次 label run 的标签差异，用于规则回放 / 阈值复盘。

用法：
    python scripts/compare_runs.py \\
        --before /path/to/before.sqlite \\
        --after  /path/to/after.sqlite \\
        --report /path/to/report.md

可选：
    --before-run RUN_ID  指定 before 库的 run_id（默认取最新）
    --after-run  RUN_ID  指定 after 库的 run_id（默认取最新）
    --label CODE          只对比指定标签（可多次）
    --fund CODE           只对比指定基金（可多次）

输出：
    1. 总览：两 run 的基金数、标签数对比
    2. 标签级差异：每个 label_code 的 active/observe 计数变化
    3. 基金级翻转：某基金在某标签上从 active→observe 或反向的清单
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LabelRow:
    fund_code: str
    label_code: str
    status: str


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM label_runs ORDER BY run_at DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _load_labels(
    conn: sqlite3.Connection,
    run_id: str,
    label_filter: set[str] | None = None,
    fund_filter: set[str] | None = None,
) -> dict[tuple[str, str], str]:
    """返回 {(fund_code, label_code): status}。"""
    sql = "SELECT fund_code, label_code, status FROM fund_label_results WHERE run_id = ?"
    params: list = [run_id]
    if label_filter:
        placeholders = ",".join("?" * len(label_filter))
        sql += f" AND label_code IN ({placeholders})"
        params.extend(label_filter)
    if fund_filter:
        placeholders = ",".join("?" * len(fund_filter))
        sql += f" AND fund_code IN ({placeholders})"
        params.extend(fund_filter)
    return {
        (r[0], r[1]): r[2]
        for r in conn.execute(sql, params).fetchall()
    }


def compare(
    before_db: str,
    after_db: str,
    report_path: str,
    before_run: str | None = None,
    after_run: str | None = None,
    label_filter: set[str] | None = None,
    fund_filter: set[str] | None = None,
) -> None:
    before_conn = sqlite3.connect(before_db)
    after_conn = sqlite3.connect(after_db)

    before_run = before_run or _latest_run_id(before_conn)
    after_run = after_run or _latest_run_id(after_conn)

    if not before_run:
        raise ValueError(f"No label_runs found in {before_db}")
    if not after_run:
        raise ValueError(f"No label_runs found in {after_db}")

    before_labels = _load_labels(before_conn, before_run, label_filter, fund_filter)
    after_labels = _load_labels(after_conn, after_run, label_filter, fund_filter)

    before_conn.close()
    after_conn.close()

    # --- 总览 ---
    before_funds = {fc for fc, _ in before_labels}
    after_funds = {fc for fc, _ in after_labels}
    common_funds = before_funds & after_funds

    # --- 标签级计数 ---
    def _status_counts(labels: dict[tuple[str, str], str]) -> dict[str, Counter]:
        out: dict[str, Counter] = defaultdict(Counter)
        for (_, lc), status in labels.items():
            out[lc][status] += 1
        return out

    before_counts = _status_counts(before_labels)
    after_counts = _status_counts(after_labels)
    all_label_codes = sorted(set(before_counts) | set(after_counts))

    # --- 基金级翻转 ---
    flips: list[tuple[str, str, str, str]] = []  # (fund, label, before_status, after_status)
    for key in set(before_labels) & set(after_labels):
        b = before_labels[key]
        a = after_labels[key]
        if b != a:
            flips.append((key[0], key[1], b, a))

    # 新增标签（after 有 before 无）
    added = sorted(set(after_labels) - set(before_labels))
    removed = sorted(set(before_labels) - set(after_labels))

    # --- 写报告 ---
    lines: list[str] = []
    lines.append("# 规则回放对比报告\n")
    lines.append(f"- before: `{before_db}` run_id=`{before_run}`")
    lines.append(f"- after:  `{after_db}` run_id=`{after_run}`")
    lines.append(f"- 基金数: before={len(before_funds)} after={len(after_funds)} 共同={len(common_funds)}")
    lines.append(f"- 标签行数: before={len(before_labels)} after={len(after_labels)}")
    lines.append(f"- 状态翻转: {len(flips)} | 新增: {len(added)} | 消失: {len(removed)}\n")

    # 标签级差异表
    lines.append("## 1. 标签级计数对比\n")
    lines.append("| label_code | before(active) | before(observe) | after(active) | after(observe) | Δ(active) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for lc in all_label_codes:
        bc = before_counts.get(lc, Counter())
        ac = after_counts.get(lc, Counter())
        ba = bc.get("active", 0)
        bo = bc.get("observe", 0)
        aa = ac.get("active", 0)
        ao = ac.get("observe", 0)
        delta = aa - ba
        lines.append(f"| `{lc}` | {ba} | {bo} | {aa} | {ao} | {delta:+d} |")
    lines.append("")

    # 翻转明细
    lines.append(f"## 2. 基金级状态翻转（{len(flips)} 条）\n")
    if flips:
        lines.append("| fund_code | label_code | before | after |")
        lines.append("|---|---|---|---|")
        # 按标签分组，每标签最多列 20 条
        by_label: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
        for f in flips:
            by_label[f[1]].append(f)
        for lc in sorted(by_label):
            items = by_label[lc]
            lines.append(f"| _{lc}（{len(items)} 条）_ | | | |")
            for fund, _, b, a in items[:20]:
                lines.append(f"| {fund} | {lc} | {b} | {a} |")
            if len(items) > 20:
                lines.append(f"| ... | ({len(items) - 20} more) | | |")
    else:
        lines.append("无状态翻转。\n")
    lines.append("")

    # 新增/消失
    if added:
        lines.append(f"## 3. after 新增标签（{len(added)} 条）\n")
        lines.append("| fund_code | label_code | status |")
        lines.append("|---|---|---|")
        for fc, lc in added[:50]:
            lines.append(f"| {fc} | {lc} | {after_labels[(fc, lc)]} |")
        if len(added) > 50:
            lines.append(f"| ... | ({len(added) - 50} more) | |")
        lines.append("")
    if removed:
        lines.append(f"## 4. after 消失标签（{len(removed)} 条）\n")
        lines.append("| fund_code | label_code | before_status |")
        lines.append("|---|---|---|")
        for fc, lc in removed[:50]:
            lines.append(f"| {fc} | {lc} | {before_labels[(fc, lc)]} |")
        if len(removed) > 50:
            lines.append(f"| ... | ({len(removed) - 50} more) | |")
        lines.append("")

    Path(report_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成：{report_path}")
    print(f"  翻转={len(flips)} 新增={len(added)} 消失={len(removed)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="对比两次 label run 的标签差异")
    ap.add_argument("--before", required=True, help="before output.sqlite 路径")
    ap.add_argument("--after", required=True, help="after output.sqlite 路径")
    ap.add_argument("--report", required=True, help="输出报告 markdown 路径")
    ap.add_argument("--before-run", default=None, help="before 库的 run_id（默认最新）")
    ap.add_argument("--after-run", default=None, help="after 库的 run_id（默认最新）")
    ap.add_argument("--label", action="append", default=[], help="只对比指定标签（可多次）")
    ap.add_argument("--fund", action="append", default=[], help="只对比指定基金（可多次）")
    args = ap.parse_args(argv)

    compare(
        before_db=args.before,
        after_db=args.after,
        report_path=args.report,
        before_run=args.before_run,
        after_run=args.after_run,
        label_filter=set(args.label) if args.label else None,
        fund_filter=set(args.fund) if args.fund else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
