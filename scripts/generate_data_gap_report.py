"""data_gap_pool 缺口归因报告生成脚本。

从 source.sqlite + output.sqlite 读取，分析 data_gap_pool 中每只基金
失败的 coverage 字段，按单字段/字段组合/根因维度归因，输出 Markdown 报告。

用法:
    python scripts/generate_data_gap_report.py \
        --source /path/to/source.sqlite \
        --output /path/to/output.sqlite \
        --report /path/to/report.md
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="data_gap_pool 缺口归因报告")
    ap.add_argument("--source", required=True, help="source.sqlite 路径")
    ap.add_argument("--output", required=True, help="output.sqlite 路径")
    ap.add_argument("--report", required=True, help="输出报告 markdown 路径")
    args = ap.parse_args()

    src = sqlite3.connect(args.source)
    src.row_factory = sqlite3.Row
    out = sqlite3.connect(args.output)
    out.row_factory = sqlite3.Row

    total = out.execute(
        "SELECT COUNT(DISTINCT fund_code) FROM fund_run_coverage"
    ).fetchone()[0]
    gap_funds = [
        r[0]
        for r in out.execute(
            "SELECT DISTINCT fund_code FROM fund_group_results "
            "WHERE group_code='data_gap_pool'"
        ).fetchall()
    ]
    ready = total - len(gap_funds)

    # 单字段失败计数
    field_fail: Counter[str] = Counter()
    # 字段组合
    combo: Counter[tuple[str, ...]] = Counter()
    fund_fields: dict[str, list[str]] = defaultdict(list)

    for r in out.execute(
        "SELECT fund_code, field FROM fund_run_coverage WHERE present=0"
    ).fetchall():
        fc = r["fund_code"]
        if fc not in set(gap_funds):
            continue
        field_fail[r["field"]] += 1
        fund_fields[fc].append(r["field"])

    for fc, fields in fund_fields.items():
        combo[tuple(sorted(set(fields)))] += 1

    # 根因分析：fee_structure only
    only_fee = {
        fc
        for fc, fields in fund_fields.items()
        if set(fields) == {"fee_structure"}
    }
    fee_has_row = fee_only_subscription = 0
    for fc in only_fee:
        n = src.execute(
            "SELECT COUNT(*) FROM fee_structures WHERE fund_code=?", (fc,)
        ).fetchone()[0]
        if n > 0:
            fee_has_row += 1
            types = [
                r[0]
                for r in src.execute(
                    "SELECT DISTINCT fee_type FROM fee_structures WHERE fund_code=?",
                    (fc,),
                ).fetchall()
            ]
            if "运作费用" not in types:
                fee_only_subscription += 1

    # 根因分析：持仓三件套
    triple = {
        fc
        for fc, fields in fund_fields.items()
        if set(fields) == {"stock_holdings", "industry_allocations", "equity_position"}
    }
    triple_types: Counter[str] = Counter()
    triple_no_holding = 0
    for fc in triple:
        r = src.execute(
            "SELECT fund_type FROM funds WHERE fund_code=?", (fc,)
        ).fetchone()
        ft = r["fund_type"] if r and r["fund_type"] else "(空)"
        triple_types[ft] += 1
        n = src.execute(
            "SELECT COUNT(*) FROM stock_holdings WHERE fund_code=?", (fc,)
        ).fetchone()[0]
        if n == 0:
            triple_no_holding += 1

    # 根因分析：fee + 持仓双重
    dual = {
        fc
        for fc, fields in fund_fields.items()
        if set(fields)
        == {"fee_structure", "stock_holdings", "industry_allocations", "equity_position"}
    }

    # nav only
    only_nav = {
        fc
        for fc, fields in fund_fields.items()
        if set(fields) == {"nav_returns"}
    }

    lines: list[str] = []
    w = lines.append

    w("# data_gap_pool 缺口归因报告")
    w("")
    w(f"- 数据来源：source=`{args.source}`，output=`{args.output}`")
    w(f"- 基金总数：{total}")
    w(f"- label_ready_pool：{ready}（{ready/total:.1%}）")
    w(f"- **data_gap_pool：{len(gap_funds)}（{len(gap_funds)/total:.1%}）**")
    w("")

    w("## 1. 单字段失败计数")
    w("")
    w("| 字段 | 失败基金数 | 占 gap_pool |")
    w("|---|---:|---:|")
    for k, v in field_fail.most_common():
        w(f"| `{k}` | {v} | {v/len(gap_funds):.1%} |")
    w("")
    w("> 注意：单字段计数会重叠（一只基金可能多字段失败），合计 > gap_pool 总数。")
    w("")

    w("## 2. 字段组合失败（互斥桶）")
    w("")
    w("| 组合 | 基金数 | 占 gap_pool |")
    w("|---|---:|---:|")
    for k, v in combo.most_common(15):
        w(f"| {', '.join(k)} | {v} | {v/len(gap_funds):.1%} |")
    w("")

    w("## 3. 根因分析")
    w("")

    w(f"### 3.1 fee_structure 单独缺失（{len(only_fee)} 只）")
    w("")
    w(f"- fee_structures 表有行：{fee_has_row}")
    w(f"- 其中只有 `申购费率`、缺 `运作费用`（管理费/托管费）：**{fee_only_subscription} 只**")
    w("- 根因：数据采集只抓了申购费率，未抓运作费用类。")
    w("- 修复方向：补 `运作费用` 采集（fee_type=运作费用，condition_name=管理费率/托管费率）。")
    w("")

    w(f"### 3.2 持仓三件套缺失（{len(triple)} 只）")
    w("")
    w("- stock_holdings + industry_allocations + equity_position 同时缺失")
    w(f"- stock_holdings 表零行：{triple_no_holding} 只")
    w("- fund_type 分布：")
    w("")
    w("| fund_type | 数量 |")
    w("|---|---:|")
    for k, v in triple_types.most_common(10):
        w(f"| {k} | {v} |")
    w("")
    w("- 根因：持仓数据从未采集（非加载 bug，stock_holdings 表无行）。")
    w("- 修复方向：补持仓采集；其中指数型股票基金（被动）可考虑走 ETF 成分股替代路径。")
    w("")

    w(f"### 3.3 fee + 持仓双重缺失（{len(dual)} 只）")
    w("")
    w("- 同时缺运作费用和持仓数据，需两路同时修。")
    w("")

    w(f"### 3.4 nav_returns 单独缺失（{len(only_nav)} 只）")
    w("")
    w("- 极小量，多为混合型基金净值未采集。")
    w("")

    w("## 4. 可执行优先级")
    w("")
    w("| 优先级 | 修复项 | 受益基金 | gap_pool 降幅 | 难度 |")
    w("|---|---|---:|---:|---|")
    w(f"| P0 | 补 `运作费用` 采集（管理费/托管费） | {fee_only_subscription} | {fee_only_subscription/len(gap_funds):.1%} | 低（单表补抓） |")
    w(f"| P1 | 补持仓采集（指数型优先走 ETF 成分股） | {len(triple)} | {len(triple)/len(gap_funds):.1%} | 中 |")
    w(f"| P2 | 补 nav_returns 采集 | {len(only_nav)} | {len(only_nav)/len(gap_funds):.1%} | 低 |")
    w(f"| — | fee+持仓双重缺失 | {len(dual)} | — | 随 P0+P1 一起解决 |")
    w("")
    w("### 预期效果")
    w("")
    remaining = len(gap_funds) - fee_only_subscription - len(triple) - len(dual) - len(only_nav)
    w(f"- 完成 P0（运作费用采集）：gap_pool {len(gap_funds)} → {len(gap_funds)-fee_only_subscription}")
    w(f"- 完成 P0+P1：gap_pool → {len(gap_funds)-fee_only_subscription-len(triple)-len(dual) if False else remaining+len(only_nav)}")
    w(f"- 完成 P0+P1+P2：gap_pool → ~{remaining}")
    w("")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成：{report_path}")
    src.close()
    out.close()


if __name__ == "__main__":
    main()
