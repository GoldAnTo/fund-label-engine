from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class FundFactorExposure:
    fund_code: str
    report_date: str
    factor_code: str
    exposure_value: float
    coverage_weight: float
    holding_total_weight: float
    stock_count: int
    covered_stock_count: int
    source: str
    as_of_date: str
    computed_at: str


def aggregate_factor_exposures(
    fund_code: str,
    report_date: str | None,
    holdings: list[dict[str, Any]],
    stock_factors: list[dict[str, Any]],
    rule_config: Any,
    as_of_date: str | None = None,
) -> list[FundFactorExposure]:
    if not report_date or not holdings or not stock_factors:
        return []

    factor_by_stock = {
        str(row["stock_code"]): row for row in stock_factors if row.get("stock_code")
    }
    valid_holdings = []
    for holding in holdings:
        stock_code = holding.get("stock_code")
        weight = _as_float(holding.get("weight"))
        if not stock_code or weight is None or weight <= 0:
            continue
        valid_holdings.append((str(stock_code), weight))

    if not valid_holdings:
        return []

    holding_total_weight = sum(weight for _stock_code, weight in valid_holdings)
    stock_count = len(valid_holdings)
    covered_stock_codes = {
        stock_code
        for stock_code, _weight in valid_holdings
        if _has_any_factor(factor_by_stock.get(stock_code))
    }
    covered_stock_count = len(covered_stock_codes)
    coverage_weight = sum(
        weight for stock_code, weight in valid_holdings if stock_code in covered_stock_codes
    )
    resolved_as_of = as_of_date or _latest_factor_date(stock_factors) or report_date
    computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows: list[FundFactorExposure] = []

    for factor_code, source_field in (
        ("pb_weighted", "pb"),
        ("roe_weighted", "roe"),
        ("revenue_growth_weighted", "revenue_growth"),
        ("profit_growth_weighted", "profit_growth"),
        ("dividend_yield_weighted", "dividend_yield"),
        ("valuation_percentile_weighted", "valuation_percentile"),
    ):
        weighted_sum = 0.0
        denominator = 0.0
        for stock_code, weight in valid_holdings:
            value = _as_float((factor_by_stock.get(stock_code) or {}).get(source_field))
            if value is None:
                continue
            weighted_sum += weight * value
            denominator += weight
        if denominator <= 0:
            continue
        rows.append(
            _record(
                fund_code,
                report_date,
                factor_code,
                weighted_sum / denominator,
                denominator,
                holding_total_weight,
                stock_count,
                covered_stock_count,
                resolved_as_of,
                computed_at,
            )
        )

    deep_value_weight = 0.0
    quality_growth_weight = 0.0
    dividend_steady_weight = 0.0
    for stock_code, weight in valid_holdings:
        factors = factor_by_stock.get(stock_code) or {}
        pb = _as_float(factors.get("pb"))
        valuation_pct = _as_float(factors.get("valuation_percentile"))
        if (
            pb is not None
            and valuation_pct is not None
            and pb <= rule_config.deep_value_pb_max
            and valuation_pct <= rule_config.deep_value_valuation_pct_max
        ):
            deep_value_weight += weight

        roe = _as_float(factors.get("roe"))
        revenue_growth = _as_float(factors.get("revenue_growth"))
        if (
            roe is not None
            and revenue_growth is not None
            and roe >= rule_config.quality_growth_roe_min
            and revenue_growth >= rule_config.quality_growth_revenue_growth_min
        ):
            quality_growth_weight += weight

        dividend_yield = _as_float(factors.get("dividend_yield"))
        if dividend_yield is not None and dividend_yield >= rule_config.dividend_steady_yield_min:
            dividend_steady_weight += weight

    for factor_code, value in (
        ("deep_value_weight", deep_value_weight),
        ("quality_growth_weight", quality_growth_weight),
        ("dividend_steady_weight", dividend_steady_weight),
        ("factor_coverage_weight", coverage_weight),
    ):
        rows.append(
            _record(
                fund_code,
                report_date,
                factor_code,
                value,
                coverage_weight,
                holding_total_weight,
                stock_count,
                covered_stock_count,
                resolved_as_of,
                computed_at,
            )
        )

    return rows


def _record(
    fund_code: str,
    report_date: str,
    factor_code: str,
    exposure_value: float,
    coverage_weight: float,
    holding_total_weight: float,
    stock_count: int,
    covered_stock_count: int,
    as_of_date: str,
    computed_at: str,
) -> FundFactorExposure:
    return FundFactorExposure(
        fund_code=fund_code,
        report_date=report_date,
        factor_code=factor_code,
        exposure_value=round(exposure_value, 6),
        coverage_weight=round(coverage_weight, 6),
        holding_total_weight=round(holding_total_weight, 6),
        stock_count=stock_count,
        covered_stock_count=covered_stock_count,
        source="stock_holdings+stock_factor_values",
        as_of_date=as_of_date,
        computed_at=computed_at,
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_any_factor(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return any(
        _as_float(row.get(field)) is not None
        for field in (
            "pb",
            "roe",
            "revenue_growth",
            "profit_growth",
            "dividend_yield",
            "valuation_percentile",
        )
    )


def _latest_factor_date(stock_factors: list[dict[str, Any]]) -> str | None:
    dates = [
        str(value)
        for row in stock_factors
        for value in (row.get("as_of_date"), row.get("factor_date"))
        if value
    ]
    return max(dates) if dates else None
