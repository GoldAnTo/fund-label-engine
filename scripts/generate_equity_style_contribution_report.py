"""权益风格贡献明细报告生成脚本。

从 output.sqlite 的 fund_equity_style_contributions + fund_label_results 读取，
解释 deep_value / quality_growth / dividend_steady 标签到底由哪些股票贡献，
输出 Markdown 报告。

用法:
    python scripts/generate_equity_style_contribution_report.py \
        --db /path/to/output.sqlite \
        --run-id <run_id> \
        --out reports/equity_style_contributions_<run_id>.md
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

STYLE_CODES = ("deep_value", "quality_growth", "dividend_steady")
STYLE_NAMES = {
    "deep_value": "深度价值",
    "quality_growth": "质量成长",
    "dividend_steady": "红利稳健",
}


def generate_report(db_path: str, run_id: str, out_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    contributions = conn.execute(
        "SELECT fund_code, report_date, stock_code, stock_name, weight, "
        "style_code, style_name, contribution_weight, factor_as_of_date "
        "FROM fund_equity_style_contributions WHERE matched = 1"
    ).fetchall()

    style_label_funds = defaultdict(set)
    try:
        for row in conn.execute(
            "SELECT DISTINCT fund_code, label_code FROM fund_label_results "
            "WHERE run_id = ? AND label_code IN (?, ?, ?)",
            (run_id, *STYLE_CODES),
        ).fetchall():
            style_label_funds[row["label_code"]].add(row["fund_code"])
    except sqlite3.OperationalError:
        pass
    conn.close()

    # 按 style 聚合
    style_counts = {code: 0 for code in STYLE_CODES}
    fund_style_weight: dict[tuple[str, str], float] = defaultdict(float)
    style_funds_with_contrib = defaultdict(set)
    by_style_stock = defaultdict(list)
    for row in contributions:
        code = row["style_code"]
        style_counts[code] = style_counts.get(code, 0) + 1
        fund_style_weight[(row["fund_code"], code)] += row["contribution_weight"]
        style_funds_with_contrib[code].add(row["fund_code"])
        by_style_stock[code].append(row)

    lines: list[str] = []
    lines.append(f"# 权益风格贡献明细报告")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- 数据库: `{db_path}`")
    lines.append(f"- 命中贡献行总数: {len(contributions)}")
    lines.append("")

    # 1) 按风格的汇总计数
    lines.append("## 风格汇总")
    lines.append("")
    lines.append("| 风格 | 贡献行数 | 涉及基金数 | 有标签基金数 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for code in STYLE_CODES:
        lines.append(
            f"| {code} ({STYLE_NAMES[code]}) | {style_counts.get(code, 0)} | "
            f"{len(style_funds_with_contrib.get(code, set()))} | "
            f"{len(style_label_funds.get(code, set()))} |"
        )
    lines.append("")

    # 2) 每个风格 top 20 基金（按总贡献权重）
    for code in STYLE_CODES:
        lines.append(f"## {code} ({STYLE_NAMES[code]}) 贡献权重 Top 20 基金")
        lines.append("")
        ranked = sorted(
            (
                (fund, weight)
                for (fund, sc), weight in fund_style_weight.items()
                if sc == code
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:20]
        if not ranked:
            lines.append("_无贡献明细_")
            lines.append("")
            continue
        lines.append("| 基金 | 累计贡献权重 |")
        lines.append("| --- | ---: |")
        for fund, weight in ranked:
            lines.append(f"| {fund} | {weight:.2%} |")
        lines.append("")

    # 3) 单基金贡献股票明细（取每个风格累计贡献最高的基金）
    lines.append("## 单基金贡献股票样例")
    lines.append("")
    for code in STYLE_CODES:
        ranked = sorted(
            (
                (fund, weight)
                for (fund, sc), weight in fund_style_weight.items()
                if sc == code
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked:
            continue
        top_fund = ranked[0][0]
        lines.append(f"### {code} ({STYLE_NAMES[code]}) - 基金 {top_fund}")
        lines.append("")
        lines.append("| 股票 | 名称 | 持仓权重 |")
        lines.append("| --- | --- | ---: |")
        stocks = sorted(
            (r for r in by_style_stock[code] if r["fund_code"] == top_fund),
            key=lambda r: r["contribution_weight"],
            reverse=True,
        )
        for r in stocks:
            lines.append(
                f"| {r['stock_code']} | {r['stock_name'] or ''} | "
                f"{r['contribution_weight']:.2%} |"
            )
        lines.append("")

    # 4) 异常清单：有风格标签但没有贡献明细
    lines.append("## 异常清单：有风格标签但缺贡献明细")
    lines.append("")
    warnings: list[str] = []
    for code in STYLE_CODES:
        missing = style_label_funds.get(code, set()) - style_funds_with_contrib.get(
            code, set()
        )
        for fund in sorted(missing):
            warnings.append(f"- {fund}: 有 `{code}` 标签但无对应贡献明细")
    if warnings:
        lines.extend(warnings)
    else:
        lines.append("_无异常_")
    lines.append("")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="权益风格贡献明细报告")
    ap.add_argument("--db", required=True, help="output.sqlite 路径")
    ap.add_argument("--run-id", required=True, help="目标 run_id")
    ap.add_argument("--out", required=True, help="输出报告 markdown 路径")
    args = ap.parse_args()
    generate_report(db_path=args.db, run_id=args.run_id, out_path=args.out)
    print(f"报告已写入 {args.out}")


if __name__ == "__main__":
    main()
