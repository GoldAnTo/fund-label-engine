from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
    computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
