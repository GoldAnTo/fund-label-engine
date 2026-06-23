from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_ACTIVE_EQUITY_TYPES = {
    "股票型",
    "混合型-偏股",
    "混合型-灵活",
    "指数型-股票",
}


@dataclass(frozen=True)
class FundInput:
    fund_code: str
    fund_name: str
    fund_type: str
    nav_returns: list[float] = field(default_factory=list)
    stock_holdings: list[dict[str, Any]] = field(default_factory=list)
    industry_allocations: list[dict[str, Any]] = field(default_factory=list)
    stock_factors: list[dict[str, Any]] = field(default_factory=list)
    manager_tenure_years: float | None = None
    management_fee: float | None = None
    custody_fee: float | None = None
    sales_service_fee: float | None = None
    fund_size: float | None = None
    equity_position: float | None = None


@dataclass(frozen=True)
class LabelResult:
    label_code: str
    label_name: str
    category: str
    confidence: float
    status: str = "active"


@dataclass(frozen=True)
class EvidenceItem:
    label_code: str
    metric: str
    value: float | str
    threshold: float | str
    source: str
    message: str


@dataclass(frozen=True)
class EngineResult:
    fund_code: str
    labels: list[LabelResult]
    evidence: list[EvidenceItem]
    review_action: str
    coverage: dict[str, bool]


class LabelEngine:
    def evaluate(self, fund: FundInput) -> EngineResult:
        labels: list[LabelResult] = []
        evidence: list[EvidenceItem] = []
        coverage = self._coverage(fund)

        if not all(coverage.values()):
            missing = [name for name, ok in coverage.items() if not ok]
            labels.append(
                LabelResult(
                    label_code="data_insufficient",
                    label_name="数据不足",
                    category="data_quality",
                    confidence=1.0,
                    status="observe",
                )
            )
            labels.append(
                LabelResult(
                    label_code="manual_review_required",
                    label_name="需人工复核",
                    category="review",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="data_insufficient",
                    metric="missing_required_fields",
                    value=",".join(missing),
                    threshold="all_required_fields_present",
                    source="coverage_check",
                    message=f"缺少必要数据：{','.join(missing)}，不能生成正式标签。",
                )
            )
            return EngineResult(
                fund_code=fund.fund_code,
                labels=labels,
                evidence=evidence,
                review_action="manual_review",
                coverage=coverage,
            )

        labels.append(
            LabelResult(
                label_code="data_sufficient",
                label_name="数据充足",
                category="data_quality",
                confidence=0.95,
            )
        )
        evidence.append(
            EvidenceItem(
                label_code="data_sufficient",
                metric="required_fields_present",
                value="yes",
                threshold="all_required_fields_present",
                source="coverage_check",
                message="基础净值、持仓、行业、经理、费率和规模数据均已提供。",
            )
        )

        self._add_holding_labels(fund, labels, evidence)
        self._add_manager_labels(fund, labels, evidence)
        self._add_fee_labels(fund, labels, evidence)
        self._add_style_boundary_labels(fund, labels, evidence)

        return EngineResult(
            fund_code=fund.fund_code,
            labels=labels,
            evidence=evidence,
            review_action="observe",
            coverage=coverage,
        )

    def _coverage(self, fund: FundInput) -> dict[str, bool]:
        return {
            "supported_fund_type": fund.fund_type in SUPPORTED_ACTIVE_EQUITY_TYPES,
            "nav_returns": bool(fund.nav_returns),
            "stock_holdings": bool(fund.stock_holdings),
            "industry_allocations": bool(fund.industry_allocations),
            "manager_tenure_years": fund.manager_tenure_years is not None,
            "fee_structure": fund.management_fee is not None and fund.custody_fee is not None,
            "fund_size": fund.fund_size is not None,
            "equity_position": fund.equity_position is not None,
        }

    def _add_holding_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        top_10_weight = round(
            sum(float(item.get("weight", 0.0)) for item in fund.stock_holdings[:10]),
            4,
        )
        if top_10_weight >= 0.55:
            labels.append(
                LabelResult(
                    label_code="holding_concentration_high",
                    label_name="持仓集中度高",
                    category="holding_structure",
                    confidence=0.9,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="holding_concentration_high",
                    metric="top_10_holding_weight",
                    value=top_10_weight,
                    threshold=0.55,
                    source="fund_stock_holdings",
                    message=f"前十大持仓合计 {top_10_weight:.2%}，达到持仓集中度高阈值 55%。",
                )
            )

    def _add_manager_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        tenure = fund.manager_tenure_years or 0.0
        if tenure >= 5.0:
            labels.append(
                LabelResult(
                    label_code="manager_tenure_long",
                    label_name="经理任期较长",
                    category="manager",
                    confidence=0.9,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="manager_tenure_long",
                    metric="manager_tenure_years",
                    value=round(tenure, 2),
                    threshold=5.0,
                    source="fund_manager_links",
                    message=f"当前基金经理任期 {tenure:.1f} 年，达到 5 年稳定性阈值。",
                )
            )

    def _add_fee_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        total_fee = (fund.management_fee or 0.0) + (fund.custody_fee or 0.0) + (
            fund.sales_service_fee or 0.0
        )
        total_fee = round(total_fee, 4)
        if total_fee <= 0.015:
            labels.append(
                LabelResult(
                    label_code="fee_low",
                    label_name="费率较低",
                    category="fee_size",
                    confidence=0.85,
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="fee_low",
                    metric="total_annual_fee",
                    value=total_fee,
                    threshold=0.015,
                    source="fee_structures",
                    message=f"管理费、托管费和销售服务费合计 {total_fee:.2%}，不高于 1.50%。",
                )
            )

    def _add_style_boundary_labels(
        self,
        fund: FundInput,
        labels: list[LabelResult],
        evidence: list[EvidenceItem],
    ) -> None:
        if fund.stock_holdings and not fund.stock_factors:
            labels.append(
                LabelResult(
                    label_code="style_unlabeled_stock_factors_missing",
                    label_name="风格未标注：缺少股票因子",
                    category="style_boundary",
                    confidence=1.0,
                    status="observe",
                )
            )
            evidence.append(
                EvidenceItem(
                    label_code="style_unlabeled_stock_factors_missing",
                    metric="stock_factors_present",
                    value="no",
                    threshold="required_for_style_labels",
                    source="stock_factors",
                    message="有基金持仓，但缺少 PB、ROE、股息率、成长性等股票因子，不能输出正式风格标签。",
                )
            )

