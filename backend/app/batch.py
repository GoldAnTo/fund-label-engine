"""Batch label calculation CLI.

Examples:
    # Same-db read/write (legacy, simplest):
    python -m app.batch --db data/fund_data.sqlite

    # Separated read/write (recommended for production fundData):
    python -m app.batch \\
        --source-db data/fundData.sqlite \\
        --output-db data/label_results.sqlite \\
        --source funddata
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from typing import Any

from app.data_access import create_repository
from app.factors.exposure_aggregator import aggregate_factor_exposures
from app.label_engine import LabelEngine
from app.label_engine.engine import FundInput, RuleConfig
from app.persistence import LabelRunWriter


def _compute_exposures(
    repo: Any,
    fund: FundInput,
    rule_config: RuleConfig,
    style_history_periods: int,
) -> list[Any]:
    """计算基金级因子暴露，支持单期或多期（用于风格稳定性分析）。

    - ``style_history_periods <= 1``：仅计算最新一期持仓的暴露（历史行为）。
    - ``style_history_periods >= 2``：计算最近 N 个有持仓的报告期，每期独立
      聚合；最新一期复用已加载的 ``fund.stock_holdings`` / ``fund.stock_factors``，
      历史期通过 repo 重新加载持仓与因子快照。所有期次的暴露拼成同一份列表，
      交给引擎的 ``_style_history_periods`` 识别多期主导风格变化。

    风格稳定性需要 ≥2 个覆盖率达标的期次才会触发标签；这里多算期次只是提供
    原料，是否打标由引擎按 ``style_stability_min_periods`` 与覆盖率阈值决定。
    """
    if style_history_periods <= 1 or not hasattr(repo, "list_recent_holding_periods"):
        return aggregate_factor_exposures(
            fund_code=fund.fund_code,
            report_date=fund.holding_report_date,
            holdings=fund.stock_holdings,
            stock_factors=fund.stock_factors,
            rule_config=rule_config,
        )

    periods = repo.list_recent_holding_periods(fund.fund_code, style_history_periods)
    if not periods:
        return aggregate_factor_exposures(
            fund_code=fund.fund_code,
            report_date=fund.holding_report_date,
            holdings=fund.stock_holdings,
            stock_factors=fund.stock_factors,
            rule_config=rule_config,
        )

    # periods 为降序；最新一期直接复用 fund 上已加载的持仓与因子，避免重复拉取。
    # 历史期复用同一份最新因子快照（设计文档约定），因此把所有历史期持仓涉及的
    # 股票代码合并后只查一次因子库，再按期切分——避免每期都 ATTACH+查一遍因子库。
    latest_period = fund.holding_report_date
    historical_periods = [p for p in periods if p != latest_period]
    historical_holdings: dict[str, list[dict[str, Any]]] = {}
    historical_stock_codes: set[str] = set()
    for period in historical_periods:
        holdings = repo.load_holdings_for_period(fund.fund_code, period)
        historical_holdings[period] = holdings
        historical_stock_codes.update(
            h["stock_code"] for h in holdings if h.get("stock_code")
        )
    historical_factors = (
        repo.load_stock_factors(sorted(historical_stock_codes))
        if historical_stock_codes
        else []
    )

    all_exposures: list[Any] = []
    for period in periods:
        if period == latest_period:
            holdings = fund.stock_holdings
            stock_factors = fund.stock_factors
        else:
            holdings = historical_holdings.get(period, [])
            stock_factors = historical_factors
        exposures = aggregate_factor_exposures(
            fund_code=fund.fund_code,
            report_date=period,
            holdings=holdings,
            stock_factors=stock_factors,
            rule_config=rule_config,
        )
        all_exposures.extend(exposures)
    return all_exposures


def run_batch(
    db_path: str | Path | None = None,
    rule_version: str = "v1",
    source: str = "auto",
    *,
    source_db: str | Path | None = None,
    output_db: str | Path | None = None,
    rule_config: RuleConfig | None = None,
    factor_db: str | Path | None = None,
    style_history_periods: int = 1,
) -> tuple[str, int]:
    """对支持的基金类型执行一次全量标签计算并落库。

    用法：
    - 单库模式：传 db_path（旧用法），源和结果都在同一个 SQLite。
    - 双库模式：传 source_db + output_db，源库以只读方式打开，结果写到 output_db。
      当 output_db 省略时自动退化为单库模式。

    单只基金失败不会中断整个批次：错误记入 fund_run_failures。
    全部成功 -> status="succeeded"；有失败 -> "completed_with_errors"。

    返回 (run_id, processed_count)。
    """
    if db_path is not None and source_db is not None:
        raise ValueError("Pass either db_path or source_db, not both.")
    if db_path is None and source_db is None:
        raise ValueError("Either db_path or source_db must be provided.")

    resolved_source = str(source_db if source_db is not None else db_path)
    resolved_output = str(
        output_db if output_db is not None else (db_path if db_path is not None else source_db)
    )
    separated = resolved_source != resolved_output

    repo = create_repository(
        resolved_source,
        source=source,
        read_only=separated,
        factor_db_path=factor_db,
    )
    rule_config = rule_config or RuleConfig()
    # 若调用方未显式配置 gate_data_as_of，自动注入本次 run 的启动日期，
    # 让 stale-days 校验有默认基准，避免静默跳过。
    if rule_config.gate_data_as_of is None:
        rule_config = replace(
            rule_config, gate_data_as_of=date.today().isoformat()
        )
    writer = LabelRunWriter(
        resolved_output,
        rule_version=rule_version,
        rule_config=rule_config,
    )
    engine = LabelEngine(rule_config)

    writer.ensure_schema()
    run_id = writer.start_run(rule_snapshot=rule_config)

    fund_codes = repo.list_supported_fund_codes()
    processed = 0
    failure_count = 0
    for fund_code in fund_codes:
        try:
            fund = repo.load_fund_input(fund_code)
            if fund is None:
                continue
            if not fund.factor_exposures and fund.stock_holdings and fund.stock_factors:
                try:
                    exposures = _compute_exposures(
                        repo=repo,
                        fund=fund,
                        rule_config=rule_config,
                        style_history_periods=style_history_periods,
                    )
                    writer.write_factor_exposures(exposures)
                    if exposures:
                        fund = replace(
                            fund,
                            factor_exposures=[asdict(item) for item in exposures],
                        )
                except Exception as exc:  # noqa: BLE001 - 聚合失败降级走旧路径
                    writer.write_failure(
                        run_id=run_id,
                        fund_code=fund_code,
                        stage="aggregate_exposures",
                        error_type=type(exc).__name__,
                        message=str(exc)[:500],
                    )
                    failure_count += 1
            result = engine.evaluate(fund)
            writer.write_result(run_id, result)
            processed += 1
        except Exception as exc:  # noqa: BLE001 - 单只基金错误被隔离记录，不中断批次
            writer.write_failure(
                run_id=run_id,
                fund_code=fund_code,
                stage="evaluate",
                error_type=type(exc).__name__,
                message=str(exc)[:500],
            )
            failure_count += 1

    final_status = "succeeded" if failure_count == 0 else "completed_with_errors"
    writer.finish_run(run_id, status=final_status)
    return run_id, processed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fund label batch calculation.")
    parser.add_argument(
        "--db",
        help="Single SQLite path for both reading fund data and writing results.",
    )
    parser.add_argument(
        "--source-db",
        help="Read-only SQLite path that holds fundData. Use together with --output-db.",
    )
    parser.add_argument(
        "--output-db",
        help="SQLite path that receives label_runs / fund_label_results / evidence / features.",
    )
    parser.add_argument(
        "--rule-version",
        default="v1",
        help="Rule version tag recorded on label_runs (default: v1).",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "engine", "funddata"),
        default="auto",
        help="Input schema source: auto, engine, or funddata (default: auto).",
    )
    parser.add_argument(
        "--min-nav-samples",
        type=int,
        default=None,
        help=(
            "Optional NAV gate. When set, fund_run_coverage 中的 nav_returns "
            "字段要求至少这么多条 daily_growth_rate 才算 ok。默认沿用 RuleConfig 默认值。"
        ),
    )
    parser.add_argument(
        "--min-holding-total-weight",
        type=float,
        default=None,
        help=(
            "Optional holding gate. When set, latest stock holding total weight "
            "must be at least this value, useful for detecting ETF-linker pass-through gaps."
        ),
    )
    parser.add_argument(
        "--deep-value-weight-min",
        type=float,
        default=None,
        help="深度价值标签触发的最小持仓权重占比。默认 0.6。",
    )
    parser.add_argument(
        "--quality-growth-weight-min",
        type=float,
        default=None,
        help="质量成长标签触发的最小持仓权重占比。默认 0.5。",
    )
    parser.add_argument(
        "--factor-db",
        default=None,
        help=(
            "可选的外挂股票因子 SQLite 路径。当 source DB 自身没有完整的 "
            "stock_factor_values 时，把这个 DB 用 ATTACH 挂上去再查。"
            "由 backend/scripts/fetch_stock_factors.py 生成。"
        ),
    )
    parser.add_argument(
        "--rule-config",
        default=None,
        help="可选 JSON 规则配置文件路径。命令行上的单项阈值覆盖优先级更高。",
    )
    parser.add_argument(
        "--style-history-periods",
        type=int,
        default=1,
        help=(
            "风格稳定性分析使用的最近报告期数。默认 1（仅算最新一期，不触发风格稳定性"
            "标签）。设为 ≥2 时，会为每只基金计算最近 N 个有持仓的报告期的因子暴露，"
            "供引擎识别多期主导风格变化（style_stable / style_drift / style_recent_shift）。"
        ),
    )
    args = parser.parse_args(argv)

    if args.db and (args.source_db or args.output_db):
        parser.error("--db cannot be combined with --source-db / --output-db")
    if not args.db and not args.source_db:
        parser.error("either --db or --source-db is required")
    if args.source_db and not args.output_db:
        parser.error("--source-db requires --output-db")

    rule_config = RuleConfig.from_file(args.rule_config) if args.rule_config else None
    rule_kwargs: dict[str, float | int] = {}
    if args.min_nav_samples is not None:
        rule_kwargs["gate_min_nav_samples"] = args.min_nav_samples
    if args.min_holding_total_weight is not None:
        rule_kwargs["gate_min_holding_total_weight"] = args.min_holding_total_weight
    if args.deep_value_weight_min is not None:
        rule_kwargs["deep_value_weight_min"] = args.deep_value_weight_min
    if args.quality_growth_weight_min is not None:
        rule_kwargs["quality_growth_weight_min"] = args.quality_growth_weight_min
    if rule_kwargs:
        rule_config = (
            replace(rule_config, **rule_kwargs)
            if rule_config is not None
            else RuleConfig(**rule_kwargs)
        )

    run_id, processed = run_batch(
        db_path=args.db,
        source_db=args.source_db,
        output_db=args.output_db,
        rule_version=args.rule_version,
        source=args.source,
        rule_config=rule_config,
        factor_db=args.factor_db,
        style_history_periods=args.style_history_periods,
    )
    print(f"run_id={run_id} processed={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
