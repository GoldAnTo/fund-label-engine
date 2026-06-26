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
import sqlite3
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from typing import Any

from app.data_access import create_repository
from app.factors.exposure_aggregator import aggregate_factor_exposures
from app.factors.equity_contributions import build_equity_style_contributions
from app.factors.dividend_sector_mix import aggregate_dividend_sector_mix
from app.label_engine import LabelEngine
from app.label_engine.engine import FundInput, RuleConfig
from app.persistence import LabelRunWriter


STYLE_LABEL_CODES = (
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
)
# 拆分出的红利系标签复用 dividend_steady 的贡献明细行。
STYLE_CONTRIBUTION_CODE = {
    "deep_value": "deep_value",
    "quality_growth": "quality_growth",
    "dividend_steady": "dividend_steady",
    "high_dividend_financial": "dividend_steady",
    "consumer_quality": "dividend_steady",
}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _factor_row_count(conn: sqlite3.Connection) -> int:
    count = 0
    if _table_exists(conn, "stock_factor_values"):
        count += int(
            conn.execute("SELECT COUNT(*) FROM stock_factor_values").fetchone()[0]
        )
    if _table_exists(conn, "stock_factors"):
        count += int(conn.execute("SELECT COUNT(*) FROM stock_factors").fetchone()[0])
    return count


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def validate_equity_factor_inputs(
    *,
    source_db: str | Path,
    factor_db: str | Path | None,
) -> None:
    """Fail early when a real separated batch has no usable stock-factor rows."""
    candidate = Path(factor_db) if factor_db is not None else Path(source_db)
    if not candidate.is_file():
        raise ValueError(f"equity factor DB does not exist: {candidate}")
    with sqlite3.connect(candidate) as conn:
        rows = _factor_row_count(conn)
    if rows <= 0:
        raise ValueError(
            f"equity factor DB must contain stock factor rows: {candidate}"
        )


def validate_equity_factor_outputs(output_db: str | Path, *, run_id: str) -> None:
    """Validate that a batch run actually produced equity-factor analysis."""
    with sqlite3.connect(output_db) as conn:
        exposure_count = 0
        if _table_exists(conn, "fund_factor_exposures"):
            if "run_id" in _table_columns(conn, "fund_factor_exposures"):
                exposure_count = conn.execute(
                    "SELECT COUNT(*) FROM fund_factor_exposures WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            else:
                exposure_count = conn.execute(
                    "SELECT COUNT(*) FROM fund_factor_exposures"
                ).fetchone()[0]
        if exposure_count <= 0:
            raise ValueError(
                "equity factor validation failed: fund_factor_exposures is empty"
            )

        ready_count = (
            conn.execute(
                """
                SELECT COUNT(DISTINCT fund_code)
                FROM fund_group_results
                WHERE run_id = ? AND group_code = 'style_factor_ready_pool'
                """,
                (run_id,),
            ).fetchone()[0]
            if _table_exists(conn, "fund_group_results")
            else 0
        )
        if ready_count <= 0:
            raise ValueError(
                "equity factor validation failed: style_factor_ready_pool is empty"
            )

        style_state_count = (
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM label_calculation_states
                WHERE run_id = ?
                  AND label_code IN ({",".join("?" for _ in STYLE_LABEL_CODES)})
                  AND state != 'not_computed'
                """,
                (run_id, *STYLE_LABEL_CODES),
            ).fetchone()[0]
            if _table_exists(conn, "label_calculation_states")
            else 0
        )
        if style_state_count <= 0:
            raise ValueError(
                "equity factor validation failed: holding-style labels were not evaluated"
            )

        if _table_exists(conn, "fund_label_results"):
            triggered = conn.execute(
                f"""
                SELECT DISTINCT fund_code, label_code
                FROM fund_label_results
                WHERE run_id = ?
                  AND label_code IN ({",".join("?" for _ in STYLE_LABEL_CODES)})
                """,
                (run_id, *STYLE_LABEL_CODES),
            ).fetchall()
            if triggered and _table_exists(conn, "fund_equity_style_contributions"):
                for fund_code, label_code in triggered:
                    contribution_code = STYLE_CONTRIBUTION_CODE.get(
                        label_code, label_code
                    )
                    contrib_count = conn.execute(
                        "SELECT COUNT(*) FROM fund_equity_style_contributions "
                        "WHERE fund_code = ? AND style_code = ? AND matched = 1",
                        (fund_code, contribution_code),
                    ).fetchone()[0]
                    if contrib_count <= 0:
                        raise ValueError(
                            "equity factor validation failed: missing equity style "
                            f"contributions for {fund_code}/{label_code}"
                        )
            elif triggered:
                raise ValueError(
                    "equity factor validation failed: equity style contributions "
                    "table is missing while style labels were triggered"
                )


def _should_validate_equity_factors(args: argparse.Namespace) -> bool:
    return bool(
        args.source_db
        and args.output_db
        and args.source in {"auto", "funddata"}
        and not args.skip_equity_factor_check
    )


def _collect_period_inputs(
    repo: Any,
    fund: FundInput,
    style_history_periods: int,
) -> list[tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]]:
    """收集用于因子暴露与贡献明细的逐期持仓/因子输入。

    返回 ``(report_date, holdings, stock_factors)`` 列表，单期与多期共用同一份口径，
    确保基金级暴露（决定标签）与股票级贡献明细（解释标签）报告期一致。
    """
    if style_history_periods <= 1 or not hasattr(repo, "list_recent_holding_periods"):
        return [(fund.holding_report_date, fund.stock_holdings, fund.stock_factors)]

    periods = repo.list_recent_holding_periods(fund.fund_code, style_history_periods)
    if not periods:
        return [(fund.holding_report_date, fund.stock_holdings, fund.stock_factors)]

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

    period_inputs: list[
        tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]
    ] = []
    for period in periods:
        if period == latest_period:
            period_inputs.append(
                (period, fund.stock_holdings, fund.stock_factors)
            )
        else:
            period_inputs.append(
                (period, historical_holdings.get(period, []), historical_factors)
            )
    return period_inputs


def _compute_exposures(
    repo: Any,
    fund: FundInput,
    rule_config: RuleConfig,
    style_history_periods: int,
) -> list[Any]:
    """计算基金级因子暴露，支持单期或多期（用于风格稳定性分析）。

    - ``style_history_periods <= 1``：仅计算最新一期持仓的暴露（历史行为）。
    - ``style_history_periods >= 2``：计算最近 N 个有持仓的报告期，每期独立
      聚合，所有期次的暴露拼成同一份列表，交给引擎的 ``_style_history_periods``
      识别多期主导风格变化。

    风格稳定性需要 ≥2 个覆盖率达标的期次才会触发标签；这里多算期次只是提供
    原料，是否打标由引擎按 ``style_stability_min_periods`` 与覆盖率阈值决定。
    """
    all_exposures: list[Any] = []
    for report_date, holdings, stock_factors in _collect_period_inputs(
        repo, fund, style_history_periods
    ):
        all_exposures.extend(
            aggregate_factor_exposures(
                fund_code=fund.fund_code,
                report_date=report_date,
                holdings=holdings,
                stock_factors=stock_factors,
                rule_config=rule_config,
            )
        )
    return all_exposures


def _compute_equity_contributions(
    repo: Any,
    fund: FundInput,
    rule_config: RuleConfig,
    style_history_periods: int,
) -> list[Any]:
    """生成股票级风格贡献明细，逐期口径与 ``_compute_exposures`` 完全一致。"""
    all_contributions: list[Any] = []
    for report_date, holdings, stock_factors in _collect_period_inputs(
        repo, fund, style_history_periods
    ):
        all_contributions.extend(
            build_equity_style_contributions(
                fund_code=fund.fund_code,
                report_date=report_date,
                holdings=holdings,
                stock_factors=stock_factors,
                rule_config=rule_config,
            )
        )
    return all_contributions


def _compute_dividend_sector_exposures(
    repo: Any,
    fund: FundInput,
    contributions: list[Any],
) -> list[Any]:
    """基于最新报告期的红利贡献明细 + 股票行业映射，算红利行业占比暴露。"""
    if not contributions or not hasattr(repo, "load_stock_industry_map"):
        return []
    latest_report_date = max(str(row.report_date) for row in contributions)
    latest_rows = [
        asdict(row)
        for row in contributions
        if str(row.report_date) == latest_report_date
    ]
    stock_codes = sorted(
        {row["stock_code"] for row in latest_rows if row.get("stock_code")}
    )
    industry_map = repo.load_stock_industry_map(stock_codes, None)
    return aggregate_dividend_sector_mix(
        fund_code=fund.fund_code,
        report_date=latest_report_date,
        contributions=latest_rows,
        industry_map=industry_map,
    )


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
                    contributions = _compute_equity_contributions(
                        repo=repo,
                        fund=fund,
                        rule_config=rule_config,
                        style_history_periods=style_history_periods,
                    )
                    writer.write_equity_style_contributions(contributions)
                    sector_exposures = _compute_dividend_sector_exposures(
                        repo=repo,
                        fund=fund,
                        contributions=contributions,
                    )
                    if sector_exposures:
                        writer.write_factor_exposures(sector_exposures)
                        merged_exposures = [asdict(item) for item in exposures]
                        merged_exposures.extend(
                            asdict(item) for item in sector_exposures
                        )
                        fund = replace(fund, factor_exposures=merged_exposures)
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
        "--skip-equity-factor-check",
        action="store_true",
        help=(
            "跳过真实双库 batch 的权益因子输入/输出校验。仅用于无权益因子的小样本 smoke。"
        ),
    )
    parser.add_argument(
        "--rule-config",
        default=None,
        help="可选 JSON 规则配置文件路径。命令行上的单项阈值覆盖优先级更高。",
    )
    parser.add_argument(
        "--disable-rule",
        action="append",
        default=[],
        metavar="LABEL_CODE",
        help=(
            "停用指定规则（label_code），可多次指定。停用的规则不会出现在输出里，"
            "也不影响分类/分组判定。data_quality/review 类标签不可停用。"
        ),
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

    # 命令行 --disable-rule 追加到 disabled_rules（与 --rule-config 里的合并）
    if args.disable_rule:
        existing = rule_config.disabled_rules if rule_config else frozenset()
        merged = existing | frozenset(args.disable_rule)
        rule_config = (
            replace(rule_config, disabled_rules=merged)
            if rule_config is not None
            else RuleConfig(disabled_rules=merged)
        )

    validate_equity_factors = _should_validate_equity_factors(args)
    if validate_equity_factors:
        try:
            validate_equity_factor_inputs(
                source_db=args.source_db,
                factor_db=args.factor_db,
            )
        except ValueError as exc:
            parser.error(str(exc))

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
    if validate_equity_factors:
        try:
            validate_equity_factor_outputs(args.output_db, run_id=run_id)
        except ValueError as exc:
            parser.error(str(exc))
    print(f"run_id={run_id} processed={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
