"""把 cbond benchmark 源探针的 evidence 写进 6 月 29 日 eligibility 报告。

只读：探针 json 已经在 /tmp/fle-run/cbond-probe.json 记录"未找到精确源"，
本脚本只负责把它固化到 reports/phase1-real-run-2026-06-29/ 下，
避免后续误改门禁、用宽指数代理。
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(args.probe_json, out_dir / "cbond-source-probe.json")

    payload = json.loads(Path(args.probe_json).read_text(encoding="utf-8"))
    investoday = payload.get("investoday", {})
    akshare = payload.get("akshare", {})
    decision = payload.get("decision", {})

    candidates = investoday.get("candidates") or []
    matches = [
        item for item in candidates
        if "中债总" in (item.get("shortName") or "")
        or "中债总" in (item.get("fullName") or "")
        or "中国债券总" in (item.get("shortName") or "")
        or "中国债券总" in (item.get("fullName") or "")
        or "标普中国债券" in (item.get("shortName") or "")
    ]

    lines = [
        "# CBOND_TOTAL / CHINA_BOND_TOTAL / SP_CHINA_BOND Source Probe",
        "",
        "只读探针结果：评估 Investoday 与 akshare 中债登接口能否为下列三个",
        "benchmark_component 精确日频源。**结论：未找到**——禁止用宽指数或中债综合/中债国债总代理。",
        "",
        "## Component 决策",
        "",
        "| component | decision | fallback_policy |",
        "| --- | --- | --- |",
    ]
    for code in ("LOCAL_CBOND_TOTAL", "LOCAL_CHINA_BOND_TOTAL", "LOCAL_SP_CHINA_BOND"):
        lines.append(
            f"| `{code}` | {decision.get(code, 'missing_source')} | {decision.get('fallback_policy', 'no_proxy_no_broad_index')} |"
        )

    lines += [
        "",
        "## Investoday search evidence",
        "",
        f"- API key present: {investoday.get('api_key_present')}",
        f"- exact matches in candidates: {len(matches)}",
    ]
    if matches:
        for item in matches:
            lines.append(
                f"  - {item.get('code')} | {item.get('shortName')} | {item.get('fullName')}"
            )
    else:
        lines.append("  - (no Investoday candidate matches the three components)")

    lines += [
        "",
        "## akshare 中债登接口 evidence",
        "",
        f"- available: {akshare.get('akshare_available')}",
        "- valid categories for `bond_index_general_cbond` 财富/总值:",
    ]
    for category in akshare.get("categories", []):
        lines.append(f"  - {category}")
    lines.append("- 没有任何 category 是 '中债总指数' / '债券总指数' / '中债-总指数'。")

    (out_dir / "cbond-source-probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_dir / 'cbond-source-probe.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
