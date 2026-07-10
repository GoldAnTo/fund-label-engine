"""数据质量综合报告渲染（Markdown + Makefile target）。

调用 :mod:`scripts.data_quality_inspection` 的检查项，输出：
1. 顶部 KPI 行（基金池 / NAV 覆盖 / 持仓覆盖 / 因子覆盖 / 基准解析率）
2. 按严重度汇总 finding（critical / warning / info）
3. 每个 finding 详写（title / detail / 样本）

用法:
    python scripts/render_data_quality_report.py \
        --db /path/to/source.sqlite \
        --output-db /path/to/output.sqlite \
        --report /path/to/report.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

# 确保项目根目录在 sys.path，使 scripts.data_quality_inspection 可被 import
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.data_quality_inspection import (
    collect_overview,
    inspect_benchmark_gaps,
    inspect_factor_freshness,
    inspect_holding_count_outliers,
    inspect_holding_report_period_coverage,
    inspect_holding_weight_outliers,
    inspect_holdings_staleness,
    inspect_nav_history,
    inspect_nav_return_outliers,
    InspectionFinding,
)


SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
SEVERITY_ICON = {"critical": "✗", "warning": "⚠", "info": "·"}


def _format_pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "—"
    return f"{numerator / denominator * 100:.1f}%"


def _format_date(s: str | None) -> str:
    return s or "—"


def _format_days(days: float | None) -> str:
    if days is None:
        return "—"
    return f"{days:.0f} 天前"


def _days(date_str: str | None) -> float | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        now = datetime.now(UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (now - dt).total_seconds() / 86400
    except ValueError:
        return None


def render_kpi_row(overview: dict, summary: dict[str, int]) -> list[str]:
    """顶部 KPI 行：基金池 + 各维度覆盖率。"""
    nav_days = _days(overview.get("latest_nav_date"))
    holding_days = _days(overview.get("latest_holding_period"))
    factor_days = _days(overview.get("latest_factor_as_of"))

    total = overview.get("total_funds") or 0
    nav_covered = overview.get("nav_covered_funds") or 0
    holding_covered = overview.get("holding_covered_funds") or 0
    bench_total = overview.get("benchmark_total_funds") or 0
    bench_resolved = overview.get("benchmark_resolved_funds") or 0

    lines = [
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 基金池 | {total} 只 |",
        f"| NAV 覆盖 | {nav_covered} / {total} ({_format_pct(nav_covered, total)}) — 最近 {_format_date(overview.get('latest_nav_date'))}（{_format_days(nav_days)}）|",
        f"| 持仓覆盖 | {holding_covered} / {total} ({_format_pct(holding_covered, total)}) — 最近报告期 {_format_date(overview.get('latest_holding_period'))}（{_format_days(holding_days)}）|",
        f"| 因子覆盖 | {overview.get('factor_stock_count', 0)} 只股票 — 最新 as_of {_format_date(overview.get('latest_factor_as_of'))}（{_format_days(factor_days)}）|",
        f"| 基准解析 | {bench_resolved} / {bench_total} ({_format_pct(bench_resolved, bench_total)}) |",
        "",
        "| 严重度 | 计数 |",
        "|---|---:|",
        f"| ✗ critical | {summary.get('critical', 0)} |",
        f"| ⚠ warning | {summary.get('warning', 0)} |",
        f"| · info | {summary.get('info', 0)} |",
        "",
    ]
    return lines


def render_findings(findings: list[InspectionFinding]) -> list[str]:
    if not findings:
        return ["## 检查发现", "", "✅ 未发现数据质量问题。", ""]
    # 按类别聚合
    by_category: dict[str, list[InspectionFinding]] = {}
    for f in findings:
        by_category.setdefault(f.category, []).append(f)

    lines: list[str] = ["## 检查发现", ""]
    # 类别标题
    for cat, items in sorted(by_category.items(), key=lambda kv: min(SEVERITY_ORDER.get(f.severity, 9) for f in kv[1])):
        worst = min(items, key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
        lines.append(f"### `{cat}`（{len(items)} 项）")
        lines.append("")
        for finding in items:
            icon = SEVERITY_ICON.get(finding.severity, "?")
            lines.append(f"#### {icon} {finding.severity.upper()} — {finding.title}")
            lines.append("")
            if finding.detail:
                lines.append(finding.detail)
                lines.append("")
            if finding.count:
                lines.append(f"- **影响基金/记录数**：{finding.count}")
            if finding.samples:
                shown = finding.samples[:5]
                lines.append(f"- **样本**：{', '.join(shown)}" + (" …" if len(finding.samples) > 5 else ""))
            lines.append("")
    return lines


def run_all_checks(conn: sqlite3.Connection) -> list[InspectionFinding]:
    findings: list[InspectionFinding] = []
    findings.extend(inspect_nav_history(conn, 7))
    findings.extend(inspect_holdings_staleness(conn, 120))
    findings.extend(inspect_factor_freshness(conn, 7))
    findings.extend(inspect_benchmark_gaps(conn))
    findings.extend(inspect_nav_return_outliers(conn))
    findings.extend(inspect_holding_weight_outliers(conn))
    findings.extend(inspect_holding_count_outliers(conn))
    findings.extend(inspect_holding_report_period_coverage(conn))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="数据质量综合报告渲染")
    parser.add_argument("--db", required=True, help="source SQLite 路径")
    parser.add_argument("--output-db", default=None, help="output SQLite 路径（用于 data_snapshots 检查）")
    parser.add_argument("--report", required=True, help="输出 Markdown 报告路径")
    parser.add_argument("--json", default=None, help="同步输出 JSON 路径（供前端消费）")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ DB 不存在: {db_path}", file=sys.stderr)
        return 1

    findings: list[InspectionFinding] = []
    overview: dict = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        findings = run_all_checks(conn)
        overview = collect_overview(conn)

    summary: dict[str, int] = {}
    for f in findings:
        summary[f.severity] = summary.get(f.severity, 0) + 1

    # 渲染 Markdown
    lines: list[str] = []
    w = lines.append
    w("# 数据质量综合报告")
    w("")
    w(f"- 生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}")
    w(f"- 数据源：`{args.db}`")
    if args.output_db:
        w(f"- 输出 DB：`{args.output_db}`")
    w("")

    w("## 概览")
    w("")
    lines.extend(render_kpi_row(overview, summary))
    lines.extend(render_findings(findings))

    # 可执行优先级（基于 finding 类别给出建议）
    w("## 修复优先级建议")
    w("")
    w("| 优先级 | 类别 | 触发条件 | 建议动作 |")
    w("|---|---|---|---|")
    w("| P0 | `stock_factors` / `nav_history` | 因子/NAV 表为空或全部陈旧 | 立即重跑 fetch_*_factors.py / fetch_nav_history.py |")
    w("| P0 | `report_period_coverage` | 最近一期覆盖率 < 40% | 检查 fetch_fund_holdings.py（采集遗漏） |")
    w("| P0 | `holding_outliers` | 持仓权重 > 30% 或 < 0 | 排查单位错（百分比 vs 小数） |")
    w("| P0 | `nav_outliers` | 日收益 > 20% 超过 50 条 | 检查 NAV 是否误抓累计净值/分红除权 |")
    w("| P1 | `benchmark_components` | unresolved 组件存在 | 补解析规则或接入新基准源 |")
    w("| P1 | `stock_holdings` | 持仓陈旧 > 120 天 | 补最近季度持仓采集 |")
    w("| P2 | `holding_count_outliers` | 单期持仓 > 100 | 检查重复抓取 |")
    w("| P3 | `data_snapshots` | 快照 > 30 天未更新 | 用最新 batch 触发一次 |")
    w("")

    w("## 复现命令")
    w("")
    w("```bash")
    w("# CLI 巡检")
    w(f"python scripts/data_quality_inspection.py --db {args.db} --json /tmp/dq.json")
    w("")
    w("# API")
    w("curl http://localhost:8000/v1/data-quality | jq")
    w("")
    w("# 重新生成此报告")
    w(f"python scripts/render_data_quality_report.py --db {args.db} --report {args.report}")
    w("```")
    w("")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 报告已生成：{report_path}")
    print(
        f"   发现: critical={summary.get('critical', 0)}, "
        f"warning={summary.get('warning', 0)}, info={summary.get('info', 0)}"
    )

    # 同步输出 JSON
    if args.json:
        json_payload = {
            "inspected_at": datetime.now(UTC).isoformat(),
            "overview": overview,
            "summary": summary,
            "findings": [asdict(f) for f in findings],
        }
        Path(args.json).write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"   JSON: {args.json}")

    return 0 if summary.get("critical", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
