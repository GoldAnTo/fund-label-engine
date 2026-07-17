"""基金推荐纯规则引擎：主题优先的主动/ETF 双轨推荐。

职责边界(严格遵守):
    - 接收 FundCandidateEvidence 和 FundRecommendationPolicy
    - 执行产品类别识别、数据新鲜度、最低主题暴露、硬冲突、评分、类内分档
    - 生成稳定原因码、分项评分和类内排名
    - 不访问数据库，纯计算
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.services.candidate_priority import FundCandidateEvidence

# ============================================================
# 常量
# ============================================================
PRODUCT_CATEGORIES = ("active_fund", "etf_or_index")
RECOMMENDATION_TIERS = (
    "candidate_pool",
    "alternative",
    "watch",
    "excluded",
    "data_insufficient",
)
RANKED_TIERS = {"candidate_pool", "alternative", "watch"}

REASON_MESSAGES = {
    "product_category_unknown": "产品类别无法从可靠元数据识别",
    "holding_data_missing": "缺少可验证的基金持仓数据",
    "holding_data_stale": "持仓报告期超过策略允许时效",
    "target_exposure_below_minimum": "主题暴露低于策略最低要求",
    "policy_conflict_detected": "候选存在策略硬冲突",
    "high_theme_exposure": "主题暴露纯度高，与投资方向高度匹配",
    "adequate_theme_exposure": "主题暴露达标，与投资方向匹配",
    "strong_thesis_alignment": "证据链完整，与投资假设高度一致",
    "good_risk_return": "风险收益指标良好（含波动率、回撤、Sharpe）",
    "strong_fund_quality": "基金质量指标良好",
    "data_gap_partial_scores": "部分评分维度数据缺失，按保守口径评分",
    "top_ranked_in_category": "同类产品中排名领先",
    "adequate_ranked_in_category": "同类产品中排名达标，列为备选",
}


# ============================================================
# 异常
# ============================================================
class FundRecommendationError(Exception):
    """基金推荐领域错误基类。"""


class FundRecommendationConfigurationError(FundRecommendationError):
    """推荐策略配置缺失或字段非法。"""


# ============================================================
# 不可变数据类
# ============================================================
@dataclass(frozen=True)
class FundRecommendationPolicy:
    """基金推荐策略配置。"""

    method_version: str
    source_method_version: str
    minimum_target_holding_weight: float
    maximum_holding_age_days: int
    active_fund_limit: int
    etf_or_index_limit: int
    alternative_limit: int
    weights: dict[str, float]


@dataclass(frozen=True)
class RecommendationReason:
    """稳定原因码和说明。"""

    code: str
    message: str


@dataclass(frozen=True)
class FundRecommendationResult:
    """单只基金推荐结果。"""

    fund_code: str
    fund_name: str | None
    product_category: str
    recommendation_tier: str
    category_rank: int | None
    theme_exposure_score: float
    thesis_alignment_score: float
    risk_return_score: float
    fund_quality_score: float
    total_score: float
    reasons: tuple[RecommendationReason, ...]
    exclusion_reasons: tuple[RecommendationReason, ...]
    evidence: FundCandidateEvidence

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.reasons)

    @property
    def exclusion_codes(self) -> tuple[str, ...]:
        return tuple(reason.code for reason in self.exclusion_reasons)


# ============================================================
# 配置解析
# ============================================================
_POLICY_REQUIRED_FIELDS = (
    "method_version",
    "source_method_version",
    "minimum_target_holding_weight",
    "maximum_holding_age_days",
    "active_fund_limit",
    "etf_or_index_limit",
    "alternative_limit",
    "weights",
)

_REQUIRED_WEIGHT_KEYS = ("theme_exposure", "thesis_alignment", "risk_return", "fund_quality")


def parse_fund_recommendation_policy(policy_row: dict[str, Any]) -> FundRecommendationPolicy:
    """从数据库策略行解析 FundRecommendationPolicy。

    从 policy_row['fund_recommendation'] 读取配置。
    """
    raw = policy_row.get("fund_recommendation")
    if raw is None:
        raise FundRecommendationConfigurationError("fund_recommendation 配置缺失")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FundRecommendationConfigurationError(
                f"fund_recommendation 不是合法 JSON: {exc}"
            ) from exc
    if not isinstance(raw, dict):
        raise FundRecommendationConfigurationError(
            "fund_recommendation 必须是字典或 JSON 字符串"
        )

    for field_name in _POLICY_REQUIRED_FIELDS:
        if field_name not in raw:
            raise FundRecommendationConfigurationError(
                f"fund_recommendation 缺少必需字段: {field_name!r}"
            )

    weights = raw["weights"]
    if not isinstance(weights, dict):
        raise FundRecommendationConfigurationError("weights 必须是字典")
    for wk in _REQUIRED_WEIGHT_KEYS:
        if wk not in weights:
            raise FundRecommendationConfigurationError(
                f"weights 缺少必需键: {wk!r}"
            )

    # 校验权重总和约为 1.0
    total_w = sum(float(weights[wk]) for wk in _REQUIRED_WEIGHT_KEYS)
    if abs(total_w - 1.0) > 0.01:
        raise FundRecommendationConfigurationError(
            f"weights 总和应为 1.0，当前为 {total_w:.4f}"
        )

    return FundRecommendationPolicy(
        method_version=str(raw["method_version"]),
        source_method_version=str(raw["source_method_version"]),
        minimum_target_holding_weight=float(raw["minimum_target_holding_weight"]),
        maximum_holding_age_days=int(raw["maximum_holding_age_days"]),
        active_fund_limit=int(raw["active_fund_limit"]),
        etf_or_index_limit=int(raw["etf_or_index_limit"]),
        alternative_limit=int(raw["alternative_limit"]),
        weights={k: float(v) for k, v in weights.items()},
    )


# ============================================================
# 纯规则引擎
# ============================================================
@dataclass
class _EvalContext:
    """单次评价中间结果，内部可变状态。"""

    evidence: FundCandidateEvidence
    policy: FundRecommendationPolicy
    reasons: list[RecommendationReason] = field(default_factory=list)
    exclusion_reasons: list[RecommendationReason] = field(default_factory=list)
    theme_exposure_score: float = 0.0
    thesis_alignment_score: float = 0.0
    risk_return_score: float = 0.0
    fund_quality_score: float = 0.0
    total_score: float = 0.0
    data_gap: bool = False


class FundRecommendationEngine:
    """基金推荐纯规则引擎。

    执行顺序(严格，前一层命中后不能升级):
        1. 类别识别 -> unknown -> excluded(unsupported)
        2. 数据新鲜度 -> data_insufficient
        3. 最低主题暴露 -> excluded
        4. 硬冲突 -> excluded
        5. 评分（四维加权）
        6. 类内分档（recommended / alternative / watch）
    """

    def evaluate_all(
        self,
        evidences: Sequence[FundCandidateEvidence],
        policy: FundRecommendationPolicy,
    ) -> list[FundRecommendationResult]:
        """评价全部候选并生成类内排序。

        返回顺序：先 active_fund 后 etf_or_index，每类内按 recommended -> alternative -> watch -> excluded -> data_insufficient。
        """
        results = [self.evaluate_one(ev, policy) for ev in evidences]

        # 按类别分组
        ordered: list[FundRecommendationResult] = []
        for category in PRODUCT_CATEGORIES:
            cat_results = [r for r in results if r.product_category == category]
            if not cat_results:
                continue
            cat_results = self._rank_within_category(cat_results, policy, category)
            ordered.extend(cat_results)

        # 无法识别类别的统一放最后
        unknown = [r for r in results if r.product_category not in PRODUCT_CATEGORIES]
        ordered.extend(unknown)

        return ordered

    def evaluate_one(
        self,
        evidence: FundCandidateEvidence,
        policy: FundRecommendationPolicy,
    ) -> FundRecommendationResult:
        """评价单只基金候选。"""
        ctx = _EvalContext(evidence=evidence, policy=policy)

        # 1. 类别识别
        category = evidence.product_category
        if category not in PRODUCT_CATEGORIES:
            ctx.exclusion_reasons.append(
                RecommendationReason(
                    code="product_category_unknown",
                    message=REASON_MESSAGES["product_category_unknown"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return self._build_result(ctx, "excluded", "unsupported")

        # 2. 数据新鲜度
        if self._check_data_gates(ctx):
            return self._build_result(ctx, "data_insufficient", category)

        # 3. 最低主题暴露
        if evidence.matched_holding_weight < policy.minimum_target_holding_weight:
            ctx.exclusion_reasons.append(
                RecommendationReason(
                    code="target_exposure_below_minimum",
                    message=REASON_MESSAGES["target_exposure_below_minimum"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return self._build_result(ctx, "excluded", category)

        # 4. 硬冲突
        if evidence.policy_conflicts:
            ctx.exclusion_reasons.append(
                RecommendationReason(
                    code="policy_conflict_detected",
                    message=REASON_MESSAGES["policy_conflict_detected"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return self._build_result(ctx, "excluded", category)

        # 5. 评分
        self._compute_scores(ctx)

        # 6. 类内分档（在 evaluate_all 中完成排名后确定）
        # 单独 evaluate_one 时先返回 watch，排名在 evaluate_all 中修正
        return self._build_result(ctx, "watch", category)

    # ----------------------------------------------------------
    # 数据新鲜度门禁
    # ----------------------------------------------------------
    def _check_data_gates(self, ctx: _EvalContext) -> bool:
        """检查数据新鲜度，命中任一返回 True。"""
        ev = ctx.evidence
        pol = ctx.policy

        # 持仓缺失
        if ev.disclosed_holding_weight <= 0 or ev.holding_report_date is None:
            ctx.reasons.append(
                RecommendationReason(
                    code="holding_data_missing",
                    message=REASON_MESSAGES["holding_data_missing"],
                )
            )
            ctx.data_gap = True
            return True

        # 持仓过期
        if ev.holding_age_days is not None and ev.holding_age_days > pol.maximum_holding_age_days:
            ctx.reasons.append(
                RecommendationReason(
                    code="holding_data_stale",
                    message=REASON_MESSAGES["holding_data_stale"],
                )
            )
            ctx.data_gap = True
            return True

        return False

    # ----------------------------------------------------------
    # 评分计算
    # ----------------------------------------------------------
    def _compute_scores(self, ctx: _EvalContext) -> None:
        """计算四个分项评分和加权总分。"""
        ev = ctx.evidence
        pol = ctx.policy
        w = pol.weights

        # 1. 主题暴露评分 (0..1)
        # matched_holding_weight 已经是 0..1 范围的小数
        ctx.theme_exposure_score = min(max(ev.matched_holding_weight, 0.0), 1.0)
        if ctx.theme_exposure_score >= 0.3:
            ctx.reasons.append(
                RecommendationReason(
                    code="high_theme_exposure",
                    message=REASON_MESSAGES["high_theme_exposure"],
                )
            )
        elif ctx.theme_exposure_score >= pol.minimum_target_holding_weight:
            ctx.reasons.append(
                RecommendationReason(
                    code="adequate_theme_exposure",
                    message=REASON_MESSAGES["adequate_theme_exposure"],
                )
            )

        # 2. 投资假设对齐评分 (0..1)
        # 基于证据类型完整度
        required_types = ("business_logic", "earnings_or_cashflow", "valuation", "catalyst_or_expectation_gap")
        present = sum(1 for et in required_types if ev.evidence_types.get(et))
        ctx.thesis_alignment_score = present / len(required_types)
        if ctx.thesis_alignment_score >= 0.75:
            ctx.reasons.append(
                RecommendationReason(
                    code="strong_thesis_alignment",
                    message=REASON_MESSAGES["strong_thesis_alignment"],
                )
            )

        # 3. 风险收益评分 (0..1)
        # 基于估值分位和持仓趋势
        ctx.risk_return_score = self._compute_risk_return_score(ev)
        if ctx.risk_return_score >= 0.6:
            ctx.reasons.append(
                RecommendationReason(
                    code="good_risk_return",
                    message=REASON_MESSAGES["good_risk_return"],
                )
            )

        # 4. 基金质量评分 (0..1)
        # 主动基金看经理稳定性、规模、费率、持仓稳定性
        # ETF/指数基金看指数主题纯度、费率、规模流动性、跟踪质量
        ctx.fund_quality_score = self._compute_fund_quality_score(ev)
        if ctx.fund_quality_score >= 0.6:
            ctx.reasons.append(
                RecommendationReason(
                    code="strong_fund_quality",
                    message=REASON_MESSAGES["strong_fund_quality"],
                )
            )

        # 数据缺失时记录保守口径说明
        if ctx.theme_exposure_score == 0 or ctx.thesis_alignment_score == 0:
            ctx.reasons.append(
                RecommendationReason(
                    code="data_gap_partial_scores",
                    message=REASON_MESSAGES["data_gap_partial_scores"],
                )
            )

        # 加权总分
        ctx.total_score = (
            ctx.theme_exposure_score * w["theme_exposure"]
            + ctx.thesis_alignment_score * w["thesis_alignment"]
            + ctx.risk_return_score * w["risk_return"]
            + ctx.fund_quality_score * w["fund_quality"]
        )

    @staticmethod
    def _compute_risk_return_score(ev: FundCandidateEvidence) -> float:
        """计算风险收益评分。

        当 NAV 数据充足（>=10 个日收益率）时，使用真实风险收益指标：
          40% Sharpe ratio + 30% 回撤控制 + 20% 估值分位 + 10% 持仓趋势
        当 NAV 数据不足时，回退到估值分位 + 持仓趋势（各 50%）。
        """
        nav = ev.nav_metrics

        if nav is not None and nav.get("nav_sample_count", 0) >= 10:
            # --- NAV 数据充足：真实风险收益评分 ---
            score = 0.0

            # Sharpe ratio（40%）：映射 0..2 -> 0..1，负值给 0
            sharpe = nav.get("sharpe_ratio", 0.0)
            score += max(0.0, min(sharpe / 2.0, 1.0)) * 0.4

            # 回撤控制（30%）：max_drawdown 0..0.5 -> 1..0
            max_dd = nav.get("max_drawdown", 0.5)
            score += max(0.0, 1.0 - max_dd / 0.5) * 0.3

            # 估值分位（20%）
            valuation = ev.valuation or {}
            percentile = valuation.get("weighted_val_pct") or valuation.get("valuation_percentile")
            if percentile is not None:
                score += max(0.0, 1.0 - percentile / 100.0) * 0.2
            else:
                score += 0.25 * 0.2

            # 持仓趋势（10%）
            trend = ev.holding_trend.get("trend") if ev.holding_trend else None
            if trend == "increasing":
                score += 0.1
            elif trend == "stable":
                score += 0.08
            elif trend == "decreasing":
                score += 0.02
            else:
                score += 0.04

            return min(score, 1.0)

        # --- NAV 数据不足：回退到估值分位 + 持仓趋势 ---
        score = 0.0

        # 估值分位（50%）
        valuation = ev.valuation or {}
        percentile = valuation.get("weighted_val_pct") or valuation.get("valuation_percentile")
        if percentile is not None:
            score += max(0.0, 1.0 - percentile / 100.0) * 0.5
        else:
            score += 0.25 * 0.5

        # 持仓趋势（50%）
        trend = ev.holding_trend.get("trend") if ev.holding_trend else None
        if trend == "increasing":
            score += 0.5
        elif trend == "stable":
            score += 0.4
        elif trend == "decreasing":
            score += 0.1
        else:
            score += 0.2

        return min(score, 1.0)

    @staticmethod
    def _compute_fund_quality_score(ev: FundCandidateEvidence) -> float:
        """计算基金质量评分。

        主动基金：经理稳定性(30%) + 规模适度(25%) + 费率竞争力(20%) + 因子覆盖(15%) + 持仓稳定(10%)
        ETF/指数：主题纯度(30%) + 费率竞争力(25%) + 规模流动性(20%) + 因子覆盖(15%) + 经理(10%)
        """
        score = 0.0
        category = ev.product_category

        if category == "etf_or_index":
            # 主题纯度（30%）
            score += min(ev.normalized_match_pct, 1.0) * 0.30

            # 费率竞争力（25%）：ETF 费率通常 0.15%-0.5%，越低越好
            if ev.management_fee is not None:
                # 0.15% -> 1.0, 0.5% -> 0.3, 1.0% -> 0.0
                fee_score = max(0.0, 1.0 - (ev.management_fee - 0.0015) / 0.0085)
                score += fee_score * 0.25
            else:
                score += 0.10  # 缺失保守

            # 规模流动性（20%）：> 10 亿为优，< 1 亿为差
            if ev.fund_size is not None:
                if ev.fund_size >= 10:
                    score += 0.20
                elif ev.fund_size >= 5:
                    score += 0.15
                elif ev.fund_size >= 1:
                    score += 0.10
                else:
                    score += 0.05
            else:
                score += 0.08

            # 因子覆盖（15%）
            score += min(ev.factor_coverage_weight, 1.0) * 0.15

            # 经理信息（10%）
            if ev.manager_identity:
                score += 0.10
            else:
                score += 0.04
        else:
            # 主动基金
            # 经理稳定性（30%）
            if ev.manager_identity:
                tenure_years = ev.manager_identity.get("tenure_years")
                if tenure_years is None:
                    tenure_days = ev.manager_identity.get("tenure_days", 0)
                    tenure_years = tenure_days / 365 if tenure_days else 0
                if tenure_years >= 5:
                    score += 0.30
                elif tenure_years >= 3:
                    score += 0.22
                elif tenure_years >= 1:
                    score += 0.15
                else:
                    score += 0.08
            else:
                score += 0.05

            # 规模适度（25%）：10-100 亿为优，过大或过小扣分
            if ev.fund_size is not None:
                if 10 <= ev.fund_size <= 100:
                    score += 0.25
                elif 5 <= ev.fund_size < 10 or 100 < ev.fund_size <= 200:
                    score += 0.18
                elif 1 <= ev.fund_size < 5 or ev.fund_size > 200:
                    score += 0.12
                else:
                    score += 0.05
            else:
                score += 0.10

            # 费率竞争力（20%）：主动基金费率通常 0.8%-1.5%
            if ev.management_fee is not None:
                # 0.8% -> 1.0, 1.5% -> 0.3, 2.0% -> 0.0
                fee_score = max(0.0, 1.0 - (ev.management_fee - 0.008) / 0.012)
                score += fee_score * 0.20
            else:
                score += 0.08

            # 因子覆盖（15%）
            score += min(ev.factor_coverage_weight, 1.0) * 0.15

            # 持仓趋势稳定（10%）
            trend = ev.holding_trend.get("trend") if ev.holding_trend else None
            if trend in ("stable", "increasing"):
                score += 0.10
            elif trend == "decreasing":
                score += 0.03
            else:
                score += 0.05

        return min(score, 1.0)

    # ----------------------------------------------------------
    # 类内分档和排名
    # ----------------------------------------------------------
    def _rank_within_category(
        self,
        results: list[FundRecommendationResult],
        policy: FundRecommendationPolicy,
        category: str,
    ) -> list[FundRecommendationResult]:
        """对同一类别内的结果按总分排序并分档。"""
        from dataclasses import replace as _replace

        # 分离可排名和不可排名
        rankable: list[FundRecommendationResult] = []
        non_rankable: list[FundRecommendationResult] = []
        for r in results:
            if r.recommendation_tier in ("excluded", "data_insufficient"):
                non_rankable.append(r)
            else:
                rankable.append(r)

        # 按总分降序，同分按基金代码稳定排序
        rankable.sort(key=lambda r: (-r.total_score, r.fund_code))

        # 确定各类的推荐上限
        recommended_limit = (
            policy.active_fund_limit if category == "active_fund" else policy.etf_or_index_limit
        )
        alternative_limit = policy.alternative_limit

        # 分档
        ranked: list[FundRecommendationResult] = []
        for idx, r in enumerate(rankable, start=1):
            if idx <= recommended_limit:
                tier = "candidate_pool"
                reasons = list(r.reasons)
                reasons.append(
                    RecommendationReason(
                        code="top_ranked_in_category",
                        message=REASON_MESSAGES["top_ranked_in_category"],
                    )
                )
                ranked.append(_replace(r, recommendation_tier=tier, category_rank=idx, reasons=tuple(reasons)))
            elif idx <= recommended_limit + alternative_limit:
                tier = "alternative"
                reasons = list(r.reasons)
                reasons.append(
                    RecommendationReason(
                        code="adequate_ranked_in_category",
                        message=REASON_MESSAGES["adequate_ranked_in_category"],
                    )
                )
                ranked.append(_replace(r, recommendation_tier=tier, category_rank=idx, reasons=tuple(reasons)))
            else:
                ranked.append(_replace(r, recommendation_tier="watch", category_rank=idx))

        # 不可排名的保持原档位，rank=None
        for r in non_rankable:
            ranked.append(_replace(r, category_rank=None))

        return ranked

    # ----------------------------------------------------------
    # 结果构造
    # ----------------------------------------------------------
    def _build_result(
        self,
        ctx: _EvalContext,
        recommendation_tier: str,
        product_category: str,
    ) -> FundRecommendationResult:
        """构造最终 FundRecommendationResult。"""
        return FundRecommendationResult(
            fund_code=ctx.evidence.fund_code,
            fund_name=ctx.evidence.fund_name,
            product_category=product_category,
            recommendation_tier=recommendation_tier,
            category_rank=None,
            theme_exposure_score=ctx.theme_exposure_score,
            thesis_alignment_score=ctx.thesis_alignment_score,
            risk_return_score=ctx.risk_return_score,
            fund_quality_score=ctx.fund_quality_score,
            total_score=ctx.total_score,
            reasons=tuple(ctx.reasons),
            exclusion_reasons=tuple(ctx.exclusion_reasons),
            evidence=ctx.evidence,
        )
