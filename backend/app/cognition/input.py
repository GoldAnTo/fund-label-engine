"""认知引擎数据模型（TypedDict 用于类型文档，运行时仍为普通 dict）。"""
from __future__ import annotations

from typing import Any, TypedDict


class ChainLink(TypedDict):
    industry_keywords: list[str]
    stock_keywords: list[str]


class Theme(TypedDict):
    name: str
    belief: str
    logic_chain: list[str]
    chain_links: dict[str, ChainLink]
    defense_theme: str | None


class CognitionInput(TypedDict):
    belief: str
    cognition_type: str
    theme_key: str
    conviction: float
    time_horizon: str
    risk_tolerance: str
    max_valuation_percentile: float | None


class ValuationResult(TypedDict):
    weighted_pe: float | None
    weighted_pb: float | None
    weighted_roe: float | None
    weighted_dividend: float | None
    weighted_val_pct: float | None
    weighted_growth: float | None
    peg: float | None
    val_judge: str
    peg_judge: str
    suggested_max_weight: float


class TrendResult(TypedDict):
    trend: str
    diff: float
    periods: list[dict[str, Any]]


class CognitionValidation(TypedDict):
    supporting_evidence: list[str]
    opposing_evidence: list[str]
    valuation_assessment: str
    verdict: str


class FundMatch(TypedDict):
    fund_code: str
    fund_name: str
    match_pct: float
    chain_breakdown: dict[str, float]
    matched_stocks: list[dict[str, Any]]
    valuation: ValuationResult
    trend: TrendResult


class OverlapResult(TypedDict):
    common_count: int
    overlap_a_pct: float
    overlap_b_pct: float
    judge: str


class PortfolioPosition(TypedDict):
    fund_code: str
    fund_name: str
    weight: float
    match_pct: float
    bucket: str
    max_weight: float
    valuation: ValuationResult


class CognitionPortfolio(TypedDict):
    selected_funds: list[PortfolioPosition]
    defense_position: PortfolioPosition | None
    overlap_analysis: list[dict[str, Any]]
    correlation_matrix: dict[str, dict[str, float | None]]
    risk_metrics: dict[str, Any]
    cash_pct: float
