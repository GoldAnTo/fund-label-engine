"""基金候选优先级纯规则引擎。

职责边界(严格遵守):
    - 接收 FundCandidateEvidence 和 CandidatePriorityPolicy
    - 执行策略门禁、数据门禁、估值门禁和档位判定
    - 生成稳定原因码、维度结果和档内排序键
    - 不访问数据库，纯计算
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

# ============================================================
# 常量
# ============================================================
PRIORITY_TIERS = (
    "research_now",
    "research_next",
    "valuation_watch",
    "data_insufficient",
    "excluded",
)
ELIGIBILITY_STATUSES = ("eligible", "unassessable", "ineligible")
DATA_QUALITY_ORDER = {"sufficient": 2, "partial": 1, "insufficient": 0}
RANKED_TIERS = {"research_now", "research_next", "valuation_watch"}

REASON_MESSAGES = {
    "policy_asset_type_not_allowed": "资产类型不在策略允许范围内",
    "policy_universe_excluded": "候选命中策略排除范围",
    "thesis_relation_missing": "候选与当前投资假设没有可识别关系",
    "target_exposure_below_minimum": "真实目标持仓低于策略最低要求",
    "holding_report_date_missing": "缺少持仓报告期",
    "holding_data_missing": "缺少可验证的基金持仓数据",
    "holding_data_stale": "持仓报告期超过策略允许时效",
    "disclosed_holding_weight_low": "已披露持仓权重不足",
    "factor_coverage_insufficient": "目标持仓的因子覆盖不足",
    "manager_identity_missing": "策略要求确认管理主体但当前无法识别",
    "valuation_data_missing": "策略要求的估值证据缺失",
    "valuation_soft_breach": "估值触发观察阈值",
    "valuation_hard_breach": "估值触发策略排除阈值",
    "required_evidence_missing": "策略要求的证据类型尚未齐全",
    "holding_trend_decreasing": "目标持仓呈下降趋势",
    "all_required_evidence_present": "策略要求的证据类型已齐全",
}


# ============================================================
# 异常
# ============================================================
class CandidatePriorityError(Exception):
    """候选优先级领域错误基类。"""


class CandidatePriorityConfigurationError(CandidatePriorityError):
    """策略配置缺失或字段非法。"""


# ============================================================
# 不可变数据类
# ============================================================
@dataclass(frozen=True)
class FundCandidateEvidence:
    """基金候选证据，纯数据对象。"""

    fund_code: str
    fund_name: str | None
    matched_holding_weight: float
    disclosed_holding_weight: float
    normalized_match_pct: float
    holding_report_date: str | None
    holding_age_days: int | None
    factor_coverage_weight: float
    valuation: dict[str, Any]
    holding_trend: dict[str, Any]
    manager_identity: dict[str, Any] | None
    evidence_types: dict[str, list[dict[str, Any]]]
    policy_conflicts: tuple[str, ...]
    data_snapshot_id: str
    asset_type: str = "fund"


@dataclass(frozen=True)
class CandidatePriorityPolicy:
    """候选优先级策略配置。"""

    method_version: str
    source_method_version: str
    asset_type: str
    minimum_target_holding_weight: float
    minimum_disclosed_holding_weight: float
    minimum_factor_coverage_weight: float
    maximum_holding_age_days: int
    valuation_breach_mode: Literal["watch", "exclude"]
    require_manager_identity: bool
    require_holding_report_date: bool
    required_evidence: tuple[str, ...]
    allowed_asset_types: tuple[str, ...]
    excluded_asset_codes: tuple[str, ...]
    valuation_policy: dict[str, Any]
    approved_for_production: bool


@dataclass(frozen=True)
class PriorityReason:
    """稳定原因码和说明。"""

    code: str
    message: str


@dataclass(frozen=True)
class CandidatePriorityResult:
    """单只基金评价结果。"""

    fund_code: str
    fund_name: str | None
    eligibility_status: str
    priority_tier: str
    priority_rank: int | None
    fit_score: float
    evidence_score: float
    dimension_results: dict[str, Any]
    reasons: tuple[PriorityReason, ...]
    exclusion_reasons: tuple[PriorityReason, ...]
    evidence: FundCandidateEvidence

    @property
    def reason_codes(self) -> tuple[str, ...]:
        """返回原因码元组。"""
        return tuple(reason.code for reason in self.reasons)


# ============================================================
# 配置解析
# ============================================================
# candidate_priority 内部必需字段（不含 valuation_policy / allowed_asset_types /
# excluded_asset_codes / approved_for_production，这些从 policy_row 顶层读取）
_POLICY_REQUIRED_FIELDS = (
    "method_version",
    "source_method_version",
    "asset_type",
    "minimum_target_holding_weight",
    "minimum_disclosed_holding_weight",
    "minimum_factor_coverage_weight",
    "maximum_holding_age_days",
    "valuation_breach_mode",
    "require_manager_identity",
    "require_holding_report_date",
    "required_evidence",
)


def _ensure_not_none(value: Any, field_name: str) -> None:
    """校验字段值不为 None。"""
    if value is None:
        raise CandidatePriorityConfigurationError(
            f"candidate_priority 配置字段 {field_name!r} 为 None"
        )


def parse_candidate_priority_policy(policy_row: dict[str, Any]) -> CandidatePriorityPolicy:
    """从数据库策略行解析 CandidatePriorityPolicy。

    只做类型校验与转换，不补阈值。
    candidate_priority 为 None 或缺少必需字段或字段为 None 时抛出配置错误。

    真实 YAML 把 valuation_policy / allowed_universe / excluded_universe /
    approved_for_production 放在策略顶层，同步脚本把它们分别存为独立 JSON 列。
    本函数从 policy_row 顶层读取这些字段。
    """
    raw = policy_row.get("candidate_priority")
    if raw is None:
        raise CandidatePriorityConfigurationError("candidate_priority 配置缺失")
    # 支持 JSON 字符串
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CandidatePriorityConfigurationError(
                f"candidate_priority 不是合法 JSON: {exc}"
            ) from exc
    if not isinstance(raw, dict):
        raise CandidatePriorityConfigurationError(
            "candidate_priority 必须是字典或 JSON 字符串"
        )

    # 校验 candidate_priority 内部必需字段（不含 valuation_policy 等）
    for field_name in _POLICY_REQUIRED_FIELDS:
        if field_name not in raw:
            raise CandidatePriorityConfigurationError(
                f"candidate_priority 缺少必需字段: {field_name!r}"
            )
        _ensure_not_none(raw[field_name], field_name)

    # 校验 valuation_breach_mode 取值
    breach_mode = raw["valuation_breach_mode"]
    if breach_mode not in ("watch", "exclude"):
        raise CandidatePriorityConfigurationError(
            f"valuation_breach_mode 取值非法: {breach_mode!r}"
        )

    # 从 policy_row 顶层读取 valuation_policy
    valuation_policy = policy_row.get("valuation_policy")
    if valuation_policy is None:
        raise CandidatePriorityConfigurationError("valuation_policy 配置缺失")
    if isinstance(valuation_policy, str):
        try:
            valuation_policy = json.loads(valuation_policy)
        except json.JSONDecodeError as exc:
            raise CandidatePriorityConfigurationError(
                f"valuation_policy 不是合法 JSON: {exc}"
            ) from exc
    if not isinstance(valuation_policy, dict):
        raise CandidatePriorityConfigurationError(
            "valuation_policy 必须是字典或 JSON 字符串"
        )

    # 从 policy_row 顶层读取 approved_for_production
    approved_for_production = bool(policy_row.get("approved_for_production", 0))

    # 从 policy_row 顶层读取 allowed_universe（含 asset_types 列表）
    allowed_universe = policy_row.get("allowed_universe")
    if isinstance(allowed_universe, str):
        allowed_universe = json.loads(allowed_universe)
    if allowed_universe and isinstance(allowed_universe, dict):
        allowed_asset_types = tuple(allowed_universe.get("asset_types", []))
    else:
        allowed_asset_types = tuple(raw.get("allowed_asset_types", ()))

    # 从 policy_row 顶层读取 excluded_universe（列表格式，每项有 reason 和 assets）
    excluded_universe = policy_row.get("excluded_universe")
    if isinstance(excluded_universe, str):
        excluded_universe = json.loads(excluded_universe)
    excluded_asset_codes: tuple[str, ...] = ()
    if excluded_universe and isinstance(excluded_universe, list):
        for item in excluded_universe:
            if isinstance(item, dict):
                assets = item.get("assets", [])
                excluded_asset_codes = excluded_asset_codes + tuple(assets)
    # 回退：检查 candidate_priority 内部是否有 excluded_asset_codes
    if not excluded_asset_codes and raw.get("excluded_asset_codes"):
        excluded_asset_codes = tuple(raw["excluded_asset_codes"])

    return CandidatePriorityPolicy(
        method_version=str(raw["method_version"]),
        source_method_version=str(raw["source_method_version"]),
        asset_type=str(raw["asset_type"]),
        minimum_target_holding_weight=float(raw["minimum_target_holding_weight"]),
        minimum_disclosed_holding_weight=float(raw["minimum_disclosed_holding_weight"]),
        minimum_factor_coverage_weight=float(raw["minimum_factor_coverage_weight"]),
        maximum_holding_age_days=int(raw["maximum_holding_age_days"]),
        valuation_breach_mode=breach_mode,
        require_manager_identity=bool(raw["require_manager_identity"]),
        require_holding_report_date=bool(raw["require_holding_report_date"]),
        required_evidence=tuple(raw["required_evidence"]),
        allowed_asset_types=allowed_asset_types,
        excluded_asset_codes=excluded_asset_codes,
        valuation_policy=valuation_policy,
        approved_for_production=approved_for_production,
    )


# ============================================================
# 纯规则引擎
# ============================================================
@dataclass
class _EvaluationContext:
    """单次评价中间结果，内部可变状态。"""

    evidence: FundCandidateEvidence
    policy: CandidatePriorityPolicy
    reasons: list[PriorityReason] = field(default_factory=list)
    exclusion_reasons: list[PriorityReason] = field(default_factory=list)
    dimension_results: dict[str, Any] = field(default_factory=dict)
    data_gaps: list[str] = field(default_factory=list)


class CandidatePriorityEngine:
    """基金候选优先级纯规则引擎。

    执行顺序(严格，前一层命中后不能升级):
        1. 策略硬门禁 -> ineligible / excluded
        2. 数据可信度门禁 -> unassessable / data_insufficient
        3. 估值软门禁 -> eligible / valuation_watch
        4. research_now 检查
        5. 否则 research_next
    """

    def evaluate_all(
        self,
        evidences: Sequence[FundCandidateEvidence],
        policy: CandidatePriorityPolicy,
    ) -> list[CandidatePriorityResult]:
        """评价全部候选并生成档内排序。

        返回顺序按档位展示顺序固定为:
        research_now -> research_next -> valuation_watch -> data_insufficient -> excluded
        每个可排名档位内部按固定排序键从 1 编号。
        """
        results = [self.evaluate_one(ev, policy) for ev in evidences]
        # 按档位展示顺序分组
        ordered: list[CandidatePriorityResult] = []
        for tier in PRIORITY_TIERS:
            tier_results = [r for r in results if r.priority_tier == tier]
            if not tier_results:
                continue
            if tier in RANKED_TIERS:
                tier_results = self._rank_and_assign(tier_results)
            ordered.extend(tier_results)
        return ordered

    def evaluate_one(
        self,
        evidence: FundCandidateEvidence,
        policy: CandidatePriorityPolicy,
    ) -> CandidatePriorityResult:
        """评价单只基金候选。"""
        ctx = _EvaluationContext(evidence=evidence, policy=policy)

        # 1. 策略硬门禁
        excluded = self._check_policy_gates(ctx)
        if excluded:
            return self._build_result(ctx, "excluded", "ineligible")

        # 2. 数据可信度门禁
        data_gap = self._check_data_gates(ctx)
        if data_gap:
            self._compute_dimension_results(ctx, data_gap=True)
            return self._build_result(ctx, "data_insufficient", "unassessable")

        # 2b. 真实目标持仓低于最低要求（在数据门禁之后检查）
        # 数据齐全但匹配权重不足，说明基金持仓与主题方向关联度不够
        if ctx.evidence.matched_holding_weight < ctx.policy.minimum_target_holding_weight:
            ctx.exclusion_reasons.append(
                PriorityReason(
                    code="target_exposure_below_minimum",
                    message=REASON_MESSAGES["target_exposure_below_minimum"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return self._build_result(ctx, "excluded", "ineligible")

        # 3. 估值软门禁
        valuation_tier = self._check_valuation_gate(ctx)
        if valuation_tier == "excluded":
            self._compute_dimension_results(ctx, data_gap=False)
            return self._build_result(ctx, "excluded", "ineligible")
        if valuation_tier == "valuation_watch":
            self._compute_dimension_results(ctx, data_gap=False)
            return self._build_result(ctx, "valuation_watch", "eligible")

        # 4. research_now 检查
        self._compute_dimension_results(ctx, data_gap=False)
        if self._check_research_now(ctx):
            ctx.reasons.append(
                PriorityReason(
                    code="all_required_evidence_present",
                    message=REASON_MESSAGES["all_required_evidence_present"],
                )
            )
            return self._build_result(ctx, "research_now", "eligible")

        # 5. 否则 research_next
        return self._build_result(ctx, "research_next", "eligible")

    # ----------------------------------------------------------
    # 策略硬门禁
    # ----------------------------------------------------------
    def _check_policy_gates(self, ctx: _EvaluationContext) -> bool:
        """检查策略硬门禁，命中任一返回 True。"""
        ev = ctx.evidence
        pol = ctx.policy

        # asset_type 不在 allowed_asset_types
        if ev.asset_type not in pol.allowed_asset_types:
            ctx.exclusion_reasons.append(
                PriorityReason(
                    code="policy_asset_type_not_allowed",
                    message=REASON_MESSAGES["policy_asset_type_not_allowed"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return True

        # v0 产品边界：策略 asset_type 必须与证据 asset_type 一致
        # 真实策略 allowed_universe 可能包含 stock/industry/fund/strategy，
        # 但 candidate_priority.asset_type="fund" 时只评价基金
        if ev.asset_type != pol.asset_type:
            ctx.exclusion_reasons.append(
                PriorityReason(
                    code="policy_asset_type_not_allowed",
                    message=REASON_MESSAGES["policy_asset_type_not_allowed"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return True

        # fund_code 在 excluded_asset_codes
        if ev.fund_code in pol.excluded_asset_codes:
            ctx.exclusion_reasons.append(
                PriorityReason(
                    code="policy_universe_excluded",
                    message=REASON_MESSAGES["policy_universe_excluded"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return True

        return False

    # ----------------------------------------------------------
    # 数据可信度门禁
    # ----------------------------------------------------------
    def _check_data_gates(self, ctx: _EvaluationContext) -> bool:
        """检查数据可信度门禁，命中任一数据缺口返回 True。"""
        ev = ctx.evidence
        pol = ctx.policy

        # 持仓报告期缺失
        if pol.require_holding_report_date and ev.holding_report_date is None:
            ctx.reasons.append(
                PriorityReason(
                    code="holding_report_date_missing",
                    message=REASON_MESSAGES["holding_report_date_missing"],
                )
            )
            ctx.data_gaps.append("holding_report_date_missing")

        # 已披露持仓权重 <= 0
        if ev.disclosed_holding_weight <= 0:
            ctx.reasons.append(
                PriorityReason(
                    code="holding_data_missing",
                    message=REASON_MESSAGES["holding_data_missing"],
                )
            )
            ctx.data_gaps.append("holding_data_missing")

        # 持仓过期
        if ev.holding_age_days is not None and ev.holding_age_days > pol.maximum_holding_age_days:
            ctx.reasons.append(
                PriorityReason(
                    code="holding_data_stale",
                    message=REASON_MESSAGES["holding_data_stale"],
                )
            )
            ctx.data_gaps.append("holding_data_stale")

        # 已披露持仓权重不足
        if ev.disclosed_holding_weight < pol.minimum_disclosed_holding_weight:
            ctx.reasons.append(
                PriorityReason(
                    code="disclosed_holding_weight_low",
                    message=REASON_MESSAGES["disclosed_holding_weight_low"],
                )
            )
            ctx.data_gaps.append("disclosed_holding_weight_low")

        # 因子覆盖不足
        if ev.factor_coverage_weight < pol.minimum_factor_coverage_weight:
            ctx.reasons.append(
                PriorityReason(
                    code="factor_coverage_insufficient",
                    message=REASON_MESSAGES["factor_coverage_insufficient"],
                )
            )
            ctx.data_gaps.append("factor_coverage_insufficient")

        # 经理缺失
        if pol.require_manager_identity and ev.manager_identity is None:
            ctx.reasons.append(
                PriorityReason(
                    code="manager_identity_missing",
                    message=REASON_MESSAGES["manager_identity_missing"],
                )
            )
            ctx.data_gaps.append("manager_identity_missing")

        # 估值证据缺失
        if "valuation" in pol.required_evidence and not self._has_valuation_data(ev.valuation):
            ctx.reasons.append(
                PriorityReason(
                    code="valuation_data_missing",
                    message=REASON_MESSAGES["valuation_data_missing"],
                )
            )
            ctx.data_gaps.append("valuation_data_missing")

        return len(ctx.data_gaps) > 0

    @staticmethod
    def _has_valuation_data(valuation: dict[str, Any]) -> bool:
        """检查估值数据是否包含有效的 weighted_pe 或 weighted_pb（值非 None）。"""
        if not valuation:
            return False
        weighted_pe = valuation.get("weighted_pe")
        weighted_pb = valuation.get("weighted_pb")
        return weighted_pe is not None or weighted_pb is not None

    # ----------------------------------------------------------
    # 估值软门禁
    # ----------------------------------------------------------
    def _check_valuation_gate(self, ctx: _EvaluationContext) -> str | None:
        """检查估值门禁，返回 "excluded" / "valuation_watch" / None。"""
        ev = ctx.evidence
        pol = ctx.policy
        vp = pol.valuation_policy

        soft_breach = False
        valuation = ev.valuation

        # 检查 PE
        weighted_pe = valuation.get("weighted_pe")
        max_pe = vp.get("max_pe")
        if weighted_pe is not None and max_pe is not None and weighted_pe > max_pe:
            soft_breach = True

        # 检查 PB
        weighted_pb = valuation.get("weighted_pb")
        max_pb = vp.get("max_pb")
        if weighted_pb is not None and max_pb is not None and weighted_pb > max_pb:
            soft_breach = True

        # 检查 PEG
        peg = valuation.get("peg")
        max_peg = vp.get("max_peg")
        if peg is not None and max_peg is not None and peg > max_peg:
            soft_breach = True

        # 检查估值分位 - 同时检查两种可能的字段名
        percentile = valuation.get("weighted_val_pct") or valuation.get("valuation_percentile")
        max_percentile = vp.get("max_valuation_percentile")
        if percentile is not None and max_percentile is not None and percentile > max_percentile:
            soft_breach = True

        if not soft_breach:
            return None

        if pol.valuation_breach_mode == "exclude":
            ctx.exclusion_reasons.append(
                PriorityReason(
                    code="valuation_hard_breach",
                    message=REASON_MESSAGES["valuation_hard_breach"],
                )
            )
            ctx.reasons.append(ctx.exclusion_reasons[-1])
            return "excluded"

        ctx.reasons.append(
            PriorityReason(
                code="valuation_soft_breach",
                message=REASON_MESSAGES["valuation_soft_breach"],
            )
        )
        return "valuation_watch"

    # ----------------------------------------------------------
    # research_now 检查
    # ----------------------------------------------------------
    def _check_research_now(self, ctx: _EvaluationContext) -> bool:
        """检查是否满足 research_now 条件。"""
        ev = ctx.evidence
        pol = ctx.policy

        # 必需证据全部存在且有非空来源记录
        all_evidence_present = True
        for etype in pol.required_evidence:
            sources = ev.evidence_types.get(etype)
            if not sources:
                ctx.reasons.append(
                    PriorityReason(
                        code="required_evidence_missing",
                        message=REASON_MESSAGES["required_evidence_missing"],
                    )
                )
                all_evidence_present = False
                break

        if not all_evidence_present:
            return False

        # 持仓趋势不是 decreasing
        trend = ev.holding_trend.get("trend") if ev.holding_trend else None
        if trend == "decreasing":
            ctx.reasons.append(
                PriorityReason(
                    code="holding_trend_decreasing",
                    message=REASON_MESSAGES["holding_trend_decreasing"],
                )
            )
            return False

        # 无 policy_conflicts
        if ev.policy_conflicts:
            return False

        return True

    # ----------------------------------------------------------
    # 维度结果计算
    # ----------------------------------------------------------
    def _compute_dimension_results(self, ctx: _EvaluationContext, *, data_gap: bool) -> None:
        """计算 dimension_results 中的各维度状态。"""
        ev = ctx.evidence
        pol = ctx.policy

        # data_quality_status
        if data_gap:
            data_quality_status = "insufficient"
        else:
            all_evidence_present = all(
                ev.evidence_types.get(etype) for etype in pol.required_evidence
            )
            if all_evidence_present and not ctx.data_gaps:
                data_quality_status = "sufficient"
            else:
                data_quality_status = "partial"

        # valuation_status
        valuation = ev.valuation
        weighted_pe = valuation.get("weighted_pe")
        max_pe = pol.valuation_policy.get("max_pe")
        if not valuation:
            valuation_status = "unknown"
        elif (
            weighted_pe is not None
            and max_pe is not None
            and weighted_pe > max_pe
        ):
            valuation_status = "overvalued"
        elif weighted_pe is not None and max_pe is not None and weighted_pe < max_pe * 0.5:
            valuation_status = "undervalued"
        else:
            valuation_status = "fair"

        # holding_truth_status
        if ev.holding_report_date is None or ev.disclosed_holding_weight <= 0:
            holding_truth_status = "missing"
        elif ev.holding_age_days is not None and ev.holding_age_days > pol.maximum_holding_age_days:
            holding_truth_status = "stale"
        else:
            holding_truth_status = "verified"

        ctx.dimension_results = {
            "data_quality_status": data_quality_status,
            "valuation_status": valuation_status,
            "holding_truth_status": holding_truth_status,
        }

    # ----------------------------------------------------------
    # 结果构造
    # ----------------------------------------------------------
    def _build_result(
        self,
        ctx: _EvaluationContext,
        priority_tier: str,
        eligibility_status: str,
    ) -> CandidatePriorityResult:
        """构造最终 CandidatePriorityResult。"""
        ev = ctx.evidence
        fit_score = min(max(ev.matched_holding_weight, 0.0), 1.0)
        evidence_score = self._compute_evidence_score(ev, ctx.policy)

        # 确保非 research_now 档位不残留 all_required_evidence_present
        reasons = ctx.reasons
        if priority_tier != "research_now":
            reasons = [r for r in reasons if r.code != "all_required_evidence_present"]

        return CandidatePriorityResult(
            fund_code=ev.fund_code,
            fund_name=ev.fund_name,
            eligibility_status=eligibility_status,
            priority_tier=priority_tier,
            priority_rank=None,
            fit_score=fit_score,
            evidence_score=evidence_score,
            dimension_results=dict(ctx.dimension_results),
            reasons=tuple(reasons),
            exclusion_reasons=tuple(ctx.exclusion_reasons),
            evidence=ev,
        )

    @staticmethod
    def _compute_evidence_score(
        evidence: FundCandidateEvidence, policy: CandidatePriorityPolicy
    ) -> float:
        """计算证据完成率 = 已满足的必需证据类型数 / 必需证据总数。"""
        required = policy.required_evidence
        if not required:
            return 1.0
        satisfied = 0
        for etype in required:
            sources = evidence.evidence_types.get(etype)
            if sources:
                satisfied += 1
        return satisfied / len(required)

    # ----------------------------------------------------------
    # 档内排序
    # ----------------------------------------------------------
    @staticmethod
    def _rank_and_assign(
        tier_results: list[CandidatePriorityResult],
    ) -> list[CandidatePriorityResult]:
        """对指定档位内的结果按固定排序键编号，返回排序后的新列表。"""
        from dataclasses import replace as _replace

        tier_results.sort(key=CandidatePriorityEngine._sort_key)
        return [
            _replace(result, priority_rank=idx)
            for idx, result in enumerate(tier_results, start=1)
        ]

    @staticmethod
    def _descending_iso_date(value: str | None) -> int:
        """ISO 日期降序辅助键。"""
        return -date.fromisoformat(value).toordinal() if value else 0

    @staticmethod
    def _sort_key(result: CandidatePriorityResult) -> tuple[Any, ...]:
        """档内排序键。"""
        return (
            -result.evidence.matched_holding_weight,
            -result.evidence_score,
            -DATA_QUALITY_ORDER[result.dimension_results["data_quality_status"]],
            CandidatePriorityEngine._descending_iso_date(result.evidence.holding_report_date),
            result.fund_code,
        )
