from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class EquityStyleContribution:
    fund_code: str
    report_date: str
    stock_code: str
    stock_name: str | None
    weight: float
    style_code: str
    style_name: str
    matched: int
    contribution_weight: float
    factor_values_json: str
    rule_snapshot_json: str
    factor_as_of_date: str
    source: str
    computed_at: str


_STYLE_NAMES = {
    "deep_value": "深度价值",
    "quality_growth": "质量成长",
    "dividend_steady": "红利稳健",
    "high_valuation": "高估值",
    "low_valuation": "低估值",
    "large_cap": "大盘",
    "mid_cap": "中盘",
    "small_cap": "小盘",
    "high_roe": "高盈利质量",
    "profit_growth_strong": "利润高增长",
}

_SOURCE = "stock_holdings+stock_factor_values"


def build_equity_style_contributions(
    fund_code: str,
    report_date: str | None,
    holdings: list[dict[str, Any]],
    stock_factors: list[dict[str, Any]],
    rule_config: Any,
    as_of_date: str | None = None,
) -> list[EquityStyleContribution]:
    if not report_date or not holdings or not stock_factors:
        return []

    factor_by_stock = {
        str(row["stock_code"]): row for row in stock_factors if row.get("stock_code")
    }
    computed_at = datetime.now(UTC).isoformat(timespec="seconds")

    rows: list[EquityStyleContribution] = []
    for holding in holdings:
        stock_code = holding.get("stock_code")
        weight = _as_float(holding.get("weight"))
        if not stock_code or weight is None or weight <= 0:
            continue
        stock_code = str(stock_code)
        factors = factor_by_stock.get(stock_code) or {}
        resolved_as_of = (
            as_of_date
            or _factor_date(factors)
            or _latest_factor_date(stock_factors)
            or report_date
        )

        for style_code, matched, factor_values, rule_snapshot in _evaluate_styles(
            factors, rule_config
        ):
            if not matched:
                continue
            rows.append(
                EquityStyleContribution(
                    fund_code=fund_code,
                    report_date=report_date,
                    stock_code=stock_code,
                    stock_name=holding.get("stock_name"),
                    weight=round(weight, 6),
                    style_code=style_code,
                    style_name=_STYLE_NAMES[style_code],
                    matched=1,
                    contribution_weight=round(weight, 6),
                    factor_values_json=json.dumps(factor_values, ensure_ascii=False),
                    rule_snapshot_json=json.dumps(rule_snapshot, ensure_ascii=False),
                    factor_as_of_date=resolved_as_of,
                    source=_SOURCE,
                    computed_at=computed_at,
                )
            )

    return rows


def _evaluate_styles(factors: dict[str, Any], cfg: Any):
    pb = _as_float(factors.get("pb"))
    valuation_pct = _as_float(factors.get("valuation_percentile"))
    roe = _as_float(factors.get("roe"))
    revenue_growth = _as_float(factors.get("revenue_growth"))
    dividend_yield = _as_float(factors.get("dividend_yield"))
    profit_growth = _as_float(factors.get("profit_growth"))
    log10_mcap = _as_float(factors.get("log10_market_cap"))

    # 高级风格标签（原 3 个）
    deep_value_matched = (
        pb is not None
        and valuation_pct is not None
        and pb <= cfg.deep_value_pb_max
        and valuation_pct <= cfg.deep_value_valuation_pct_max
    )
    quality_growth_matched = (
        roe is not None
        and revenue_growth is not None
        and roe >= cfg.quality_growth_roe_min
        and revenue_growth >= cfg.quality_growth_revenue_growth_min
    )
    dividend_steady_matched = (
        dividend_yield is not None and dividend_yield >= cfg.dividend_steady_yield_min
    )

    # 扩展风格标签（股票级判断，用 RuleConfig 阈值）
    high_valuation_matched = (
        (pb is not None and pb >= cfg.high_valuation_pb_min)
        or (pb is not None and pb >= 8.0)
    )
    low_valuation_matched = (
        (pb is not None and pb <= cfg.low_valuation_pb_max)
        or (pb is not None and pb <= 3.0)
    )
    large_cap_matched = (
        log10_mcap is not None and log10_mcap >= cfg.large_cap_log10_mcap_min
    )
    mid_cap_matched = (
        log10_mcap is not None
        and cfg.mid_cap_log10_mcap_min <= log10_mcap < cfg.mid_cap_log10_mcap_max
    )
    small_cap_matched = (
        log10_mcap is not None and log10_mcap < cfg.small_cap_log10_mcap_max
    )
    high_roe_matched = roe is not None and roe >= cfg.high_roe_threshold
    profit_growth_matched = (
        profit_growth is not None
        and profit_growth >= cfg.profit_growth_strong_threshold
    )

    yield (
        "deep_value",
        deep_value_matched,
        {"pb": pb, "valuation_percentile": valuation_pct},
        {
            "pb_max": cfg.deep_value_pb_max,
            "valuation_percentile_max": cfg.deep_value_valuation_pct_max,
        },
    )
    yield (
        "quality_growth",
        quality_growth_matched,
        {"roe": roe, "revenue_growth": revenue_growth},
        {
            "roe_min": cfg.quality_growth_roe_min,
            "revenue_growth_min": cfg.quality_growth_revenue_growth_min,
        },
    )
    yield (
        "dividend_steady",
        dividend_steady_matched,
        {"dividend_yield": dividend_yield},
        {"dividend_yield_min": cfg.dividend_steady_yield_min},
    )
    # 估值高低互斥：deep_value 优先级最高，high/low 互不同时触发
    yield (
        "high_valuation",
        high_valuation_matched and not deep_value_matched,
        {"pb": pb},
        {"pb_min": cfg.high_valuation_pb_min},
    )
    yield (
        "low_valuation",
        low_valuation_matched
        and not deep_value_matched
        and not high_valuation_matched,
        {"pb": pb},
        {"pb_max": cfg.low_valuation_pb_max},
    )
    yield (
        "large_cap",
        large_cap_matched,
        {"log10_market_cap": log10_mcap},
        {"log10_mcap_min": cfg.large_cap_log10_mcap_min},
    )
    yield (
        "mid_cap",
        mid_cap_matched,
        {"log10_market_cap": log10_mcap},
        {
            "log10_mcap_min": cfg.mid_cap_log10_mcap_min,
            "log10_mcap_max": cfg.mid_cap_log10_mcap_max,
        },
    )
    yield (
        "small_cap",
        small_cap_matched,
        {"log10_market_cap": log10_mcap},
        {"log10_mcap_max": cfg.small_cap_log10_mcap_max},
    )
    # high_roe 与 quality_growth 互斥：quality_growth 包含 growth 维度，优先级更高
    yield (
        "high_roe",
        high_roe_matched and not quality_growth_matched,
        {"roe": roe},
        {"roe_min": cfg.high_roe_threshold},
    )
    yield (
        "profit_growth_strong",
        profit_growth_matched,
        {"profit_growth": profit_growth},
        {"profit_growth_min": cfg.profit_growth_strong_threshold},
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _factor_date(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for value in (row.get("as_of_date"), row.get("factor_date")):
        if value:
            return str(value)
    return None


def _latest_factor_date(stock_factors: list[dict[str, Any]]) -> str | None:
    dates = [
        str(value)
        for row in stock_factors
        for value in (row.get("as_of_date"), row.get("factor_date"))
        if value
    ]
    return max(dates) if dates else None
