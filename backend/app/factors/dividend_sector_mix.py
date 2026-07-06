from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.factors.exposure_aggregator import FundFactorExposure

_SOURCE = "fund_equity_style_contributions+stock_industry_map"
_SECTOR_CODES = (
    ("dividend_sector_financial_ratio", "financial"),
    ("dividend_sector_energy_utility_ratio", "energy_utility"),
    ("dividend_sector_consumer_ratio", "consumer"),
)


def aggregate_dividend_sector_mix(
    fund_code: str,
    report_date: str | None,
    contributions: list[dict[str, Any]],
    industry_map: dict[str, dict[str, Any]],
) -> list[FundFactorExposure]:
    if not report_date:
        return []
    rows = [
        row
        for row in contributions
        if str(row.get("style_code") or "") == "dividend_steady"
        and int(row.get("matched") or 0) == 1
        and _as_float(row.get("contribution_weight")) > 0
    ]
    if not rows:
        return []

    total = sum(_as_float(row.get("contribution_weight")) for row in rows)
    mapped_total = 0.0
    sector_weight = {"financial": 0.0, "energy_utility": 0.0, "consumer": 0.0}
    industry_dates: list[str] = []
    for row in rows:
        stock_code = str(row.get("stock_code") or "")
        weight = _as_float(row.get("contribution_weight"))
        industry = industry_map.get(stock_code)
        if not industry:
            continue
        sector = str(industry.get("sector_group") or "other")
        mapped_total += weight
        if sector in sector_weight:
            sector_weight[sector] += weight
        if industry.get("as_of_date"):
            industry_dates.append(str(industry["as_of_date"]))

    coverage = mapped_total / total if total > 0 else 0.0
    as_of_date = max(industry_dates) if industry_dates else report_date
    computed_at = datetime.now(UTC).isoformat(timespec="seconds")
    result = [
        _record(
            fund_code,
            report_date,
            "dividend_sector_coverage",
            coverage,
            coverage,
            total,
            len(rows),
            int(round(len(rows) * coverage)),
            as_of_date,
            computed_at,
        )
    ]
    for factor_code, sector in _SECTOR_CODES:
        ratio = sector_weight[sector] / mapped_total if mapped_total > 0 else 0.0
        result.append(
            _record(
                fund_code,
                report_date,
                factor_code,
                ratio,
                coverage,
                total,
                len(rows),
                int(round(len(rows) * coverage)),
                as_of_date,
                computed_at,
            )
        )
    return result


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
        source=_SOURCE,
        as_of_date=as_of_date,
        computed_at=computed_at,
    )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
