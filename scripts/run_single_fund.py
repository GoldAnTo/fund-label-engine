"""对一只基金跑标签引擎并把结果直接打印到控制台。

不写库，不动 label_runs，便于本地排查「这只基金为什么进/不进数据充足 gate、
为什么打出/没打出某个标签」。

Usage 示例：

    # 用 seed 出来的示例库
    python scripts/seed_sample_db.py data/sample.sqlite
    python scripts/run_single_fund.py --db data/sample.sqlite --fund-code 000001

    # 对接真实 fundData（只读）
    python scripts/run_single_fund.py \
        --source-db data/fundData.sqlite --fund-code 110022 --source funddata

    # 只想看 gate 检测结果，不输出收益风险/风格/费率等标签明细
    python scripts/run_single_fund.py --db data/sample.sqlite \
        --fund-code 000001 --only-gate

    # 收紧 gate（演示新增的 equity_position / return_window 阈值）
    python scripts/run_single_fund.py --db data/sample.sqlite --fund-code 000001 \
        --min-equity-position 0.6 --min-return-window 1y
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 让脚本可以从仓库根目录直接执行：python scripts/run_single_fund.py ...
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.data_access import create_repository  # noqa: E402
from app.label_engine import LabelEngine  # noqa: E402
from app.label_engine.engine import RuleConfig  # noqa: E402


def _format_coverage(coverage: dict[str, bool]) -> str:
    lines = []
    for field, ok in coverage.items():
        mark = "OK " if ok else "FAIL"
        lines.append(f"  [{mark}] {field}")
    return "\n".join(lines)


def _format_labels(labels) -> str:
    lines = []
    for label in labels:
        lines.append(
            f"  - {label.label_code:35s} "
            f"status={label.status:8s} confidence={label.confidence:.2f} "
            f"({label.category})"
        )
    return "\n".join(lines)


def _format_evidence(evidence, only_label: str | None = None) -> str:
    lines = []
    for item in evidence:
        if only_label and item.label_code != only_label:
            continue
        lines.append(
            f"  - [{item.label_code}] {item.metric}\n"
            f"      value     = {item.value}\n"
            f"      threshold = {item.threshold}\n"
            f"      source    = {item.source}\n"
            f"      message   = {item.message}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="对一只基金跑标签引擎并打印结果（不落库）。"
    )
    parser.add_argument(
        "--db",
        help="单库模式：同时作为源库的 SQLite 路径。",
    )
    parser.add_argument(
        "--source-db",
        help="双库模式：源库 SQLite 路径（只读打开）。",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "engine", "funddata"),
        default="auto",
        help="输入 schema 来源：auto / engine / funddata，默认 auto。",
    )
    parser.add_argument(
        "--factor-db",
        default=None,
        help="可选的外挂股票因子 SQLite。",
    )
    parser.add_argument(
        "--fund-code",
        required=True,
        help="要测试的基金代码。",
    )
    parser.add_argument(
        "--only-gate",
        action="store_true",
        help="只打印 coverage / 数据充足性检查结果，不打印其他标签明细。",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出，便于二次加工。",
    )
    # gate 阈值（可选）
    parser.add_argument("--min-nav-samples", type=int, default=None)
    parser.add_argument("--min-stock-holding-count", type=int, default=None)
    parser.add_argument("--min-holding-total-weight", type=float, default=None)
    parser.add_argument("--min-industry-count", type=int, default=None)
    parser.add_argument("--min-equity-position", type=float, default=None)
    parser.add_argument(
        "--min-return-window",
        choices=("1m", "3m", "1y", "3y"),
        default=None,
    )
    parser.add_argument("--max-holding-stale-days", type=int, default=None)
    parser.add_argument("--max-industry-stale-days", type=int, default=None)
    parser.add_argument(
        "--data-as-of",
        default=None,
        help="形如 2026-06-24，配合 --max-*-stale-days 使用。",
    )
    # 风格阈值（可选，便于排查规则）
    parser.add_argument("--deep-value-weight-min", type=float, default=None)
    parser.add_argument("--quality-growth-weight-min", type=float, default=None)
    parser.add_argument("--dividend-steady-weight-min", type=float, default=None)
    args = parser.parse_args(argv)

    if not args.db and not args.source_db:
        parser.error("必须提供 --db 或 --source-db 之一。")
    if args.db and args.source_db:
        parser.error("--db 与 --source-db 不能同时使用。")
    db_path = args.db or args.source_db
    read_only = args.source_db is not None

    repo = create_repository(
        db_path,
        source=args.source,
        read_only=read_only,
        factor_db_path=args.factor_db,
    )

    fund = repo.load_fund_input(args.fund_code)
    if fund is None:
        print(f"未找到基金 {args.fund_code}", file=sys.stderr)
        return 1

    # 构造 RuleConfig：只覆盖用户显式提供的字段
    overrides: dict = {}
    for attr in (
        "min_nav_samples",
        "min_stock_holding_count",
        "min_holding_total_weight",
        "min_industry_count",
        "min_equity_position",
        "min_return_window",
        "max_holding_stale_days",
        "max_industry_stale_days",
        "data_as_of",
    ):
        val = getattr(args, attr)
        if val is not None:
            overrides[f"gate_{attr}"] = val
    for attr in (
        "deep_value_weight_min",
        "quality_growth_weight_min",
        "dividend_steady_weight_min",
    ):
        val = getattr(args, attr)
        if val is not None:
            overrides[attr] = val
    cfg = RuleConfig(**overrides) if overrides else RuleConfig()

    result = LabelEngine(cfg).evaluate(fund)

    if args.json:
        payload = {
            "fund_code": result.fund_code,
            "fund_type": result.fund_type,
            "review_action": result.review_action,
            "coverage": result.coverage,
            "labels": [
                {
                    "label_code": label.label_code,
                    "label_name": label.label_name,
                    "category": label.category,
                    "status": label.status,
                    "confidence": label.confidence,
                }
                for label in result.labels
            ],
            "evidence": [
                {
                    "label_code": item.label_code,
                    "metric": item.metric,
                    "value": item.value,
                    "threshold": item.threshold,
                    "source": item.source,
                    "message": item.message,
                }
                for item in result.evidence
            ],
            "features": [
                {
                    "feature_code": item.feature_code,
                    "value": item.value,
                    "source": item.source,
                }
                for item in result.features
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"基金代码：{result.fund_code}")
    print(f"基金名称：{fund.fund_name}")
    print(f"基金类型：{result.fund_type}")
    print(f"review_action：{result.review_action}")

    print("\n== 数据充足性 Coverage ==")
    print(_format_coverage(result.coverage))

    insufficient_evidence = [
        item for item in result.evidence if item.source == "coverage_gate"
    ]
    if insufficient_evidence:
        print("\n== 未通过 Gate 的子原因 ==")
        for item in insufficient_evidence:
            print(f"  - {item.metric}: {item.message}")

    if args.only_gate:
        return 0

    print("\n== 标签 ==")
    print(_format_labels(result.labels))

    print("\n== 证据 ==")
    print(_format_evidence(result.evidence))

    print("\n== 关键特征 ==")
    for item in result.features:
        print(f"  - {item.feature_code} = {item.value}  (source={item.source})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
