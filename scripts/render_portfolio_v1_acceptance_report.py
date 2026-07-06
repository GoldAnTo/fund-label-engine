"""portfolio_v1_acceptance_report: 渲染 28 eligible + risk review + optimized top 20 + exclude 汇总。

输出 reports/phase1-real-run-2026-06-29/portfolio-v1-acceptance.md。
不做评分，只做搬运 + 标注 + 拉出现成证据 + 留给研究员的 sign-off 问题清单。
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader
from app.portfolio.acceptance import (
    bucket_by_status,
    classify_eligible,
    exclude_reasons,
    is_risk_review_fund,
    summarize_eligible,
    top_optimized,
)
from app.portfolio.role_review_suggest import suggest_role_reviews

DEFAULT_RUN_ID = "50f9b72de7104761869dc3e86e8a36d2"
DEFAULT_OUTPUT_DB = "/tmp/fle-run/output.sqlite"
DEFAULT_SOURCE_DB = "/tmp/fle-run/source.sqlite"
DEFAULT_OUT_MD = (
    "reports/phase1-real-run-2026-06-29/portfolio-v1-acceptance.md"
)


def _fmt_pct(value: Any, digits: int = 2) -> str:
    """把 fraction 值 (例如 0.0295) 渲染成 "2.95%"。alpha_1y / vol / max_dd 都是 fraction。"""
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_weight_pct(value: Any, digits: int = 2) -> str:
    """把已经是百分比的数值 (例如 2.26) 渲染成 "2.26%"。optimized/draft/max_weight_pct 是百分比。"""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _join(values: Any) -> str:
    if not values:
        return "—"
    if isinstance(values, list):
        return ", ".join(str(x) for x in values)
    return str(values)


def _sub_class_from_draft(row: dict[str, Any]) -> str:
    """draft row 用 bucket 反推 sub_class。matrix 走 classify_eligible；draft 走这里。"""
    bucket = row.get("bucket") or ""
    if "index_tool" in (row.get("portfolio_roles") or []):
        return "index_tool"
    if bucket == "core":
        return "core"
    if bucket == "satellite":
        return "satellite"
    if bucket == "index_tool":
        return "index_tool"
    return bucket or "—"


def render_report(
    *,
    output_db: str | Path,
    source_db: str | Path | None,
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
    draft = reader.get_portfolio_draft(selected_run_id)
    role_suggestions = suggest_role_reviews(matrix["rows"])

    matrix_rows = matrix["rows"]
    bucketed = bucket_by_status(matrix_rows)
    eligible_rows = bucketed["eligible"]
    review_required_rows = bucketed["review_required"]
    observe_rows = bucketed["observe"]
    risk_review_funds = [r for r in eligible_rows + review_required_rows if is_risk_review_fund(r)]
    top20 = top_optimized(draft["rows"], n=20)
    draft_excluded = draft.get("excluded", [])
    excluded_reasons_count = exclude_reasons(draft_excluded)
    # 把 draft rows 按 fund_code 索引，给 matrix rows 补 bucket / cap / opt
    draft_by_code = {r["fund_code"]: r for r in draft["rows"]}
    for r in matrix_rows:
        d = draft_by_code.get(r["fund_code"])
        if d is not None:
            r["bucket"] = d.get("bucket")
            r["max_weight_pct"] = d.get("max_weight_pct")
            r["optimized_weight_pct"] = d.get("optimized_weight_pct")
            r["optimized_status"] = d.get("optimized_status")
    eligible_summary = summarize_eligible(eligible_rows)

    lines: list[str] = []
    lines += [
        "# Portfolio v1 Acceptance Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"run_at: `{matrix.get('run_at', '—')}`",
        f"rule_version: `{matrix.get('rule_version', '—')}`",
        f"total_count: {matrix.get('total_count', 0)}",
        "",
        "> 本报告是 product acceptance 用人话解释，不做评分或自动化决策。",
        "> 每只基金附 alpha_1y / sharpe / IR / drawdown / 优化权重 / max cap，",
        "> 由研究员在『Sign-off Checklist』小节做最终决定。",
        "",
        "## Status Breakdown",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    for status, rows in bucketed.items():
        if rows:
            lines.append(f"| {status} | {len(rows)} |")

    lines += [
        "",
        f"draft.included_rows = {len(draft['rows'])}",
        f"draft.excluded_rows = {len(draft_excluded)}",
        f"optimized summary = {draft.get('optimization_summary')}",
        f"role suggestions generated = {len(role_suggestions)}",
        "",
        "## Eligible Funds (28) — Classified",
        "",
        f"counts: {eligible_summary}",
        "",
        "| fund_code | sub_class | bucket | role | alpha_1y | sharpe | IR | vol | max_dd | max_cap | opt_w |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    eligible_sorted = sorted(
        eligible_rows,
        key=lambda r: (
            {"core": 0, "core_pending_risk_review": 1, "satellite": 2, "index_tool": 3}.get(
                classify_eligible(r), 9
            ),
            -float(r.get("alpha_1y") or 0.0),
        ),
    )
    for r in eligible_sorted:
        sub = classify_eligible(r)
        d = draft_by_code.get(r["fund_code"])
        cap_str = (
            _fmt_weight_pct(d.get("max_weight_pct"), digits=1) if d and d.get("max_weight_pct") is not None else "—"
        )
        opt_str = _fmt_weight_pct(d.get("optimized_weight_pct"), digits=2) if d else "—"
        lines.append(
            "| `{fc}` | {sub} | {bucket} | {role} | {alpha} | {sharpe} | {ir} | {vol} | {dd} | {cap} | {opt} |".format(
                fc=r["fund_code"],
                sub=sub,
                bucket=d.get("bucket") if d else "—",
                role=_join(r.get("portfolio_roles")),
                alpha=_fmt_pct(r.get("alpha_1y")),
                sharpe=_fmt_num(r.get("sharpe_ratio_1y")),
                ir=_fmt_num(r.get("information_ratio_1y")),
                vol=_fmt_pct(r.get("annualized_volatility_1y")),
                dd=_fmt_pct(r.get("max_drawdown_1y")),
                cap=cap_str,
                opt=opt_str,
            )
        )

    lines += [
        "",
        "<details><summary>含 optimized weight 的扩展表（点击展开）</summary>",
        "",
        "| fund_code | sub_class | opt_w | dry_run | max_cap | capped |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for r in eligible_sorted:
        d = draft_by_code.get(r["fund_code"])
        opt_w = _fmt_weight_pct(d.get("optimized_weight_pct"), digits=2) if d else "—"
        dry = _fmt_weight_pct(d.get("draft_weight_pct"), digits=2) if d else "—"
        cap = _fmt_weight_pct(d.get("max_weight_pct"), digits=1) if d else "—"
        capped = d.get("optimized_status", "—") if d else "—"
        lines.append(
            "| `{fc}` | {sub} | {opt} | {dry} | {cap} | {capped} |".format(
                fc=r["fund_code"], sub=classify_eligible(r), opt=opt_w, dry=dry, cap=cap, capped=capped
            )
        )
    lines += ["", "</details>", ""]

    # 风险复核基金
    lines += [
        "## Risk Review Funds",
        "",
        f"检测到 {len(risk_review_funds)} 只含风险标记（risk_tags high_volatility/large_drawdown/high_turnover "
        "或 max_dd<-30% / vol>30% 或 watch_reasons 含 allocation_risk_review）。",
        "",
        "| fund_code | status | risk_tags | watch_reasons | alpha_1y | vol | max_dd | bucket | opt_w |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    risk_review_sorted = sorted(
        risk_review_funds,
        key=lambda r: float(r.get("max_drawdown_1y") or 0.0),
    )
    for r in risk_review_sorted:
        d = draft_by_code.get(r["fund_code"])
        opt_w = _fmt_weight_pct(d.get("optimized_weight_pct"), digits=2) if d else "—"
        lines.append(
            "| `{fc}` | {status} | {tags} | {watch} | {alpha} | {vol} | {dd} | {bucket} | {opt} |".format(
                fc=r["fund_code"],
                status=r.get("allocation_status", "—"),
                tags=_join(r.get("risk_tags")),
                watch=_join(r.get("watch_reasons")),
                alpha=_fmt_pct(r.get("alpha_1y")),
                vol=_fmt_pct(r.get("annualized_volatility_1y")),
                dd=_fmt_pct(r.get("max_drawdown_1y")),
                bucket=d.get("bucket") if d else "—",
                opt=opt_w,
            )
        )

    # Optimized top 20
    lines += [
        "",
        "## Optimized Top 20 by Weight",
        "",
        f"method = {draft.get('optimization_summary', {}).get('method', '—')}, "
        f"capped_count = {draft.get('optimization_summary', {}).get('capped_count', 0)}, "
        f"total_weight = {draft.get('optimization_summary', {}).get('total_weight_pct', 0):.2f}%",
        "",
        "| rank | fund_code | opt_w | dry_run | max_cap | capped | bucket | role | sub_class |",
        "| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for rank, r in enumerate(top20, 1):
        # draft row 没有 allocation_status，sub_class 用 bucket 反推：
        # core 且 opt_w > 0.5% → core；satellite → satellite；index_tool → index_tool
        sub = _sub_class_from_draft(r)
        lines.append(
            "| {rank} | `{fc}` | {opt} | {dry} | {cap} | {capped} | {bucket} | {role} | {sub} |".format(
                rank=rank,
                fc=r.get("fund_code"),
                opt=_fmt_weight_pct(r.get("optimized_weight_pct"), digits=2),
                dry=_fmt_weight_pct(r.get("draft_weight_pct"), digits=2),
                cap=_fmt_weight_pct(r.get("max_weight_pct"), digits=1),
                capped=r.get("optimized_status", "—"),
                bucket=r.get("bucket", "—"),
                role=_join(r.get("portfolio_roles")),
                sub=sub,
            )
        )

    # Exclude 原因 top
    lines += [
        "",
        "## Excluded (from draft) — Reason Top",
        "",
        "| reason | count |",
        "| --- | ---: |",
    ]
    if excluded_reasons_count:
        for reason, count in sorted(
            excluded_reasons_count.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"| `{reason}` | {count} |")
    else:
        lines.append("| `(none)` | 0 |")

    # observe + review_required 分布
    lines += [
        "",
        "## observe / review_required 现状",
        "",
        f"observe: {len(observe_rows)} 只（不进入 draft，但保留作为后续监控池）",
        f"review_required: {len(review_required_rows)} 只（已通过 suggest API 给出预填建议）",
        "",
        "observe 主要由低 coverage（factor_coverage_weight < 0.5）+ 数据不足组成，",
        "下一阶段补 benchmark/因子覆盖后再回滚评估。",
        "",
    ]

    # role suggestions 摘要
    if role_suggestions:
        lines += [
            "## Role Suggestion 预填（review_required 自动产出）",
            "",
            "| fund_code | suggested_bucket | role_code | max_w | rationale |",
            "| --- | --- | --- | ---: | --- |",
        ]
        for s in role_suggestions[:20]:
            lines.append(
                "| `{fc}` | {bucket} | {role} | {mw} | {rat} |".format(
                    fc=s["fund_code"],
                    bucket=s["target_bucket"],
                    role=s["role_code"],
                    mw=f"{s['recommended_max_weight_pct']:.1f}%",
                    rat=(s["rationale"] or "")[:80].replace("|", "/"),
                )
            )
        if len(role_suggestions) > 20:
            lines.append(f"| ... | ... | ... | ... | （共 {len(role_suggestions)} 条） |")
        lines.append("")

    # Sign-off Checklist
    lines += [
        "## Sign-off Checklist（researcher 决定）",
        "",
        "下面 4 个问题是 product acceptance 的关键决策点：",
        "",
        "1. **核心/卫星池是否成立**",
        "   - 当前 `core` = {} 只，`core_pending_risk_review` = {} 只，`satellite` = {} 只，`index_tool` = {} 只".format(
            eligible_summary.get("core", 0),
            eligible_summary.get("core_pending_risk_review", 0),
            eligible_summary.get("satellite", 0),
            eligible_summary.get("index_tool", 0),
        ),
        "   - 你是否接受这些角色分布？哪只应该 core 但被分到 satellite？哪只应该降级？",
        "",
        "2. **风险复核基金的 max cap 是否合理**",
        f"   - 当前 {len(risk_review_funds)} 只风险复核基金全部以 draft 权重进入",
        "   - 这些基金 max_drawdown / volatility 是否需要收窄 cap（5% → 3%）或转 satellite？",
        "",
        "3. **optimized top 20 权重分配是否符合预期**",
        "   - 头部 5 只权重偏高（约 2~3%/只），是否符合「核心+卫星」直觉？",
        "   - 哪只应该降权？哪只应该升到 core？",
        "",
        "4. **排除原因可信度**",
        f"   - benchmark_data_missing 是主因（{excluded_reasons_count.get('benchmark_data_missing', 0)} 只），是项目设计选择",
        "   - style_factor_coverage_low 是数据覆盖问题（95 只），不阻塞本次 acceptance",
        "",
        "## 下一步",
        "",
        "- 在前端工作台对每只 core/satellite 走一遍 manual override（写入 portfolio_role_reviews）",
        "- 重生成 portfolio-draft 报告看 human override 之后的 draft 权重",
        "- 把 sign-off 结果固化到 `config/portfolio_constraints.v1.json` 的 cap / weight_min 阈值",
        "",
    ]

    out_path = Path(out_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "run_id": selected_run_id,
        "eligible_count": len(eligible_rows),
        "risk_review_count": len(risk_review_funds),
        "draft_rows": len(draft["rows"]),
        "excluded_count": len(draft_excluded),
        "eligible_summary": eligible_summary,
        "out_md": str(out_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--output-db", default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    args = parser.parse_args()
    summary = render_report(
        output_db=args.output_db,
        source_db=args.source_db,
        out_md=args.out_md,
        run_id=args.run_id,
    )
    print(
        f"wrote {summary['out_md']} (run_id={summary['run_id']}, "
        f"eligible={summary['eligible_count']}, risk_review={summary['risk_review_count']}, "
        f"draft_rows={summary['draft_rows']}, excluded={summary['excluded_count']})"
    )


if __name__ == "__main__":
    main()
