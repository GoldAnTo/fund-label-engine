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
# 与 RuleConfig 默认风格阈值保持一致（基金级 *_weight 阈值）。
STYLE_WEIGHT_THRESHOLDS = {
    "deep_value": 0.60,
    "quality_growth": 0.50,
    "dividend_steady": 0.50,
}
# 金融类启发式：贡献股票名称中包含这些关键字即视为金融持仓。
FINANCIAL_KEYWORDS = ("银行", "保险", "证券", "金融", "租赁", "信托", "财险", "人寿", "太保", "平安")


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

    # 按 style 聚合。多期模式下同一基金有多个报告期，标签判定基于单期，
    # 因此报告也按 (fund, report_date, style) 聚合，再对每个基金取最新报告期作为
    # 代表，避免跨期累加导致贡献权重 > 100%。
    style_counts = {code: 0 for code in STYLE_CODES}
    # (fund, style) -> {report_date -> 累计贡献权重}
    period_weight: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    # (fund, style) -> {report_date -> [贡献行]}
    period_stocks: dict[tuple[str, str], dict[str, list]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in contributions:
        code = row["style_code"]
        style_counts[code] = style_counts.get(code, 0) + 1
        key = (row["fund_code"], code)
        period_weight[key][row["report_date"]] += row["contribution_weight"]
        period_stocks[key][row["report_date"]].append(row)

    def _latest(d: dict[str, float] | dict[str, list]) -> str:
        return max(d.keys())

    # 取每个基金最新报告期作为代表
    fund_style_weight: dict[tuple[str, str], float] = {}
    style_funds_with_contrib = defaultdict(set)
    by_style_stock = defaultdict(list)  # 仅含各基金最新期的贡献行
    for key, by_period in period_weight.items():
        fund, code = key
        latest = _latest(by_period)
        fund_style_weight[key] = by_period[latest]
        style_funds_with_contrib[code].add(fund)
        by_style_stock[code].extend(period_stocks[key][latest])

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

    # 4) 有贡献但未成标签：贡献权重达不到基金级阈值的基金分布
    lines.append("## 有贡献但未成标签（按风格）")
    lines.append("")
    lines.append("规则：累计贡献权重 < 基金级阈值即不会打标签。")
    lines.append("")
    lines.append("| 风格 | 阈值 | 有贡献基金数 | 已成标签 | 有贡献未成标签 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    contrib_not_labeled: dict[str, list[tuple[str, float]]] = {}
    for code in STYLE_CODES:
        thr = STYLE_WEIGHT_THRESHOLDS[code]
        with_contrib = style_funds_with_contrib.get(code, set())
        labeled = style_label_funds.get(code, set())
        not_labeled = sorted(
            (
                (fund, fund_style_weight[(fund, code)])
                for fund in with_contrib
                if fund not in labeled
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        contrib_not_labeled[code] = not_labeled
        lines.append(
            f"| {code} ({STYLE_NAMES[code]}) | {thr:.0%} | {len(with_contrib)} | "
            f"{len(labeled)} | {len(not_labeled)} |"
        )
    lines.append("")
    for code in STYLE_CODES:
        not_labeled = contrib_not_labeled[code]
        if not not_labeled:
            continue
        lines.append(f"### {code} ({STYLE_NAMES[code]}) 临界未成标签 Top 20")
        lines.append("")
        lines.append("| 基金 | 累计贡献权重 | 距阈值 |")
        lines.append("| --- | ---: | ---: |")
        thr = STYLE_WEIGHT_THRESHOLDS[code]
        for fund, weight in not_labeled[:20]:
            lines.append(f"| {fund} | {weight:.2%} | {thr - weight:+.2%} |")
        lines.append("")

    # 5) 风格重叠分析：deep_value 与 dividend_steady 同时成标签，是否金融主导
    lines.append("## 风格重叠分析")
    lines.append("")
    dv = style_label_funds.get("deep_value", set())
    ds = style_label_funds.get("dividend_steady", set())
    qg = style_label_funds.get("quality_growth", set())
    pairs = [
        ("deep_value ∩ dividend_steady", dv & ds),
        ("deep_value ∩ quality_growth", dv & qg),
        ("quality_growth ∩ dividend_steady", qg & ds),
        ("deep_value ∩ dividend_steady ∩ quality_growth", dv & ds & qg),
    ]
    lines.append("| 标签组合 | 重叠基金数 |")
    lines.append("| --- | ---: |")
    for name, funds in pairs:
        lines.append(f"| {name} | {len(funds)} |")
    lines.append("")

    # 金融主导判定：在 dv ∩ ds 的基金里，看金融贡献股票权重占比
    overlap = dv & ds
    lines.append("### deep_value ∩ dividend_steady 金融主导度 Top 20")
    lines.append("")
    if not overlap:
        lines.append("_无重叠基金_")
        lines.append("")
    else:
        # 用 dividend_steady 贡献股票判断金融占比（红利贡献最能反映银行保险地产）
        ds_stock_by_fund = defaultdict(list)
        for r in by_style_stock["dividend_steady"]:
            if r["fund_code"] in overlap:
                ds_stock_by_fund[r["fund_code"]].append(r)
        fin_ratio: list[tuple[str, float, float]] = []
        for fund, rows in ds_stock_by_fund.items():
            total = sum(r["contribution_weight"] for r in rows)
            fin = sum(
                r["contribution_weight"]
                for r in rows
                if r["stock_name"]
                and any(k in r["stock_name"] for k in FINANCIAL_KEYWORDS)
            )
            ratio = (fin / total) if total > 0 else 0.0
            fin_ratio.append((fund, ratio, total))
        fin_ratio.sort(key=lambda item: item[1], reverse=True)
        high_fin = sum(1 for _f, ratio, _t in fin_ratio if ratio >= 0.6)
        lines.append(
            f"重叠基金 {len(overlap)} 只，其中红利贡献中金融占比 ≥ 60% 的有 "
            f"{high_fin} 只（{high_fin / len(overlap):.0%}）。"
        )
        lines.append("")
        lines.append("| 基金 | 金融贡献占比 | 红利累计贡献 |")
        lines.append("| --- | ---: | ---: |")
        for fund, ratio, total in fin_ratio[:20]:
            lines.append(f"| {fund} | {ratio:.0%} | {total:.2%} |")
        lines.append("")

    # 6) 异常清单：有风格标签但没有贡献明细
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
