"""投决会门槛：硬性门槛 + 评分混合 + 覆盖机制"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class ICHurdle:
    """硬性门槛"""
    hurdle_id: str
    name: str                # 如"估值分位不超过95%"
    metric: str              # 如"val_pct"
    operator: str            # ">" | "<" | ">=" | "<="
    threshold: float
    observed: float | None = None
    passed: bool | None = None  # True/False/None(无法判断)
    rationale: str = ""


@dataclass
class ICPillar:
    """评分支柱"""
    name: str                # "conviction" | "constitution_fit" | "data_quality"
    score: float = 0.0       # 0-100
    components: list[dict] = field(default_factory=list)  # [{name, state, score, note}]

    @property
    def effective_score(self) -> float:
        """组件等权重平均，unknown=50, contradicted=min(score, 35)"""
        if not self.components:
            return self.score
        scores = []
        for c in self.components:
            state = c.get("state", "unknown")
            raw = c.get("score", 50)
            if state == "unknown":
                scores.append(50.0)
            elif state == "contradicted":
                scores.append(min(raw, 35.0))
            else:
                scores.append(float(raw))
        return round(sum(scores) / len(scores), 1) if scores else 0.0


@dataclass
class ICReviewResult:
    """投决会审查结果"""
    verdict: str             # "pass" | "fail"
    gate_score: float        # 0-100
    cutoff: float            # 通过线
    hurdles: list[ICHurdle]  # 硬性门槛
    pillars: list[ICPillar]  # 评分支柱
    fail_reason: str | None = None
    is_override: bool = False
    override_rationale: str = ""
    prior_verdict: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "gate_score": round(self.gate_score, 1),
            "cutoff": self.cutoff,
            "fail_reason": self.fail_reason,
            "is_override": self.is_override,
            "override_rationale": self.override_rationale,
            "prior_verdict": self.prior_verdict,
            "timestamp": self.timestamp,
            "hurdles": [
                {
                    "hurdle_id": h.hurdle_id,
                    "name": h.name,
                    "metric": h.metric,
                    "operator": h.operator,
                    "threshold": h.threshold,
                    "observed": h.observed,
                    "passed": h.passed,
                    "rationale": h.rationale,
                }
                for h in self.hurdles
            ],
            "pillars": [
                {
                    "name": p.name,
                    "score": p.effective_score,
                    "components": p.components,
                }
                for p in self.pillars
            ],
        }


# 默认权重和通过线
DEFAULT_BLEND = {"conviction": 0.45, "constitution_fit": 0.35, "data_quality": 0.20}
DEFAULT_CUTOFF = 70.0
SEVERE_WEAKNESS_FLOOR = 25.0


def evaluate_hurdles(hurdles: list[ICHurdle]) -> list[ICHurdle]:
    """评估硬性门槛"""
    for h in hurdles:
        if h.observed is None:
            h.passed = None  # 无法判断
            continue
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        fn = ops.get(h.operator)
        if fn:
            h.passed = fn(h.observed, h.threshold)
    return hurdles


def calculate_gate_score(pillars: list[ICPillar]) -> float:
    """计算加权分数"""
    blend = DEFAULT_BLEND
    total = 0.0
    for p in pillars:
        weight = blend.get(p.name, 0)
        total += weight * p.effective_score
    return round(total, 1)


def run_ic_review(
    hurdles: list[ICHurdle],
    pillars: list[ICPillar],
    cutoff: float = DEFAULT_CUTOFF,
) -> ICReviewResult:
    """
    执行投决会审查。

    判定顺序：
    1. 有 hurdle miss -> fail（reason: hard hurdle miss）
    2. 最弱支柱 < 25 -> fail（reason: severe weakness guardrail）
    3. gate_score >= cutoff -> pass
    4. 否则 -> fail（reason: gate score below cutoff）
    """
    # 评估硬性门槛
    hurdles = evaluate_hurdles(hurdles)

    # 检查门槛 miss
    failed_hurdles = [h for h in hurdles if h.passed is False]
    if failed_hurdles:
        names = ", ".join(h.name for h in failed_hurdles)
        return ICReviewResult(
            verdict="fail",
            gate_score=0.0,
            cutoff=cutoff,
            hurdles=hurdles,
            pillars=pillars,
            fail_reason=f"硬性门槛未通过: {names}",
            timestamp=date.today().isoformat(),
        )

    # 计算分数
    score = calculate_gate_score(pillars)

    # 检查严重薄弱
    min_pillar = min((p.effective_score for p in pillars), default=0)
    if min_pillar < SEVERE_WEAKNESS_FLOOR:
        weak = [p for p in pillars if p.effective_score < SEVERE_WEAKNESS_FLOOR]
        names = ", ".join(p.name for p in weak)
        return ICReviewResult(
            verdict="fail",
            gate_score=score,
            cutoff=cutoff,
            hurdles=hurdles,
            pillars=pillars,
            fail_reason=f"严重薄弱: {names} 低于 {SEVERE_WEAKNESS_FLOOR}",
            timestamp=date.today().isoformat(),
        )

    # 通过线
    verdict = "pass" if score >= cutoff else "fail"
    return ICReviewResult(
        verdict=verdict,
        gate_score=score,
        cutoff=cutoff,
        hurdles=hurdles,
        pillars=pillars,
        fail_reason=None if verdict == "pass" else f"评分 {score} 低于通过线 {cutoff}",
        timestamp=date.today().isoformat(),
    )


def create_ic_review_from_cognition(
    validation: dict[str, Any],
    fund_matches: list[dict[str, Any]],
    gated_out: list[dict[str, Any]],
    judgment: dict[str, Any],
    portfolio: dict[str, Any],
) -> ICReviewResult:
    """
    从认知分析结果创建投决会审查。

    硬性门槛从 judgment.hard_limits 生成。
    评分支柱从 validation 和 fund_matches 推导。
    """
    # 1. 硬性门槛
    hurdles: list[ICHurdle] = []
    hard_limits = judgment.get("hard_limits", {})

    # 估值分位门槛
    max_val_pct = hard_limits.get("max_valuation_percentile")
    if max_val_pct:
        observed = None
        if fund_matches:
            observed = fund_matches[0].get("valuation", {}).get("weighted_val_pct")
        hurdles.append(ICHurdle(
            hurdle_id="h_val_pct",
            name=f"估值分位不超过{max_val_pct}",
            metric="val_pct",
            operator="<=",
            threshold=float(max_val_pct),
            observed=observed,
        ))

    # PEG 门槛
    max_peg = hard_limits.get("max_peg")
    if max_peg:
        observed = None
        if fund_matches:
            observed = fund_matches[0].get("valuation", {}).get("peg")
        hurdles.append(ICHurdle(
            hurdle_id="h_peg",
            name=f"PEG不超过{max_peg}",
            metric="peg",
            operator="<=",
            threshold=float(max_peg),
            observed=observed,
        ))

    # PE 门槛
    max_pe = hard_limits.get("max_pe")
    if max_pe:
        observed = None
        if fund_matches:
            observed = fund_matches[0].get("valuation", {}).get("weighted_pe")
        hurdles.append(ICHurdle(
            hurdle_id="h_pe",
            name=f"PE不超过{max_pe}",
            metric="pe",
            operator="<=",
            threshold=float(max_pe),
            observed=observed,
        ))

    # 股息率门槛
    min_div = hard_limits.get("min_dividend_yield")
    if min_div:
        observed = None
        if fund_matches:
            # valuation 字典中字段名为 weighted_dividend
            observed = fund_matches[0].get("valuation", {}).get("weighted_dividend")
        hurdles.append(ICHurdle(
            hurdle_id="h_div_yield",
            name=f"股息率不低于{min_div}",
            metric="dividend_yield",
            operator=">=",
            threshold=float(min_div),
            observed=observed,
        ))

    # 2. 评分支柱
    # Conviction（投资信心）
    verdict = validation.get("verdict", "")
    supporting = validation.get("supporting_evidence", [])
    opposing = validation.get("opposing_evidence", [])

    conviction_components = [
        {
            "name": "论证强度",
            "state": "supported" if len(supporting) >= 3 else "unknown",
            "score": min(100, 40 + len(supporting) * 10),
            "note": f"{len(supporting)} 条支持证据",
        },
        {
            "name": "证据支持",
            "state": "supported" if supporting else "contradicted",
            "score": min(100, 30 + len(supporting) * 15),
            "note": f"支持 {len(supporting)} / 反对 {len(opposing)}",
        },
        {
            "name": "催化剂清晰度",
            "state": "supported" if verdict and "有效" in verdict else "unknown",
            "score": 75 if verdict and "有效" in verdict else 50,
            "note": f"裁决: {verdict}",
        },
        {
            "name": "风险调整后下行",
            "state": "supported" if len(opposing) <= 3 else "contradicted",
            "score": max(30, 80 - len(opposing) * 10),
            "note": f"{len(opposing)} 条反对证据",
        },
    ]
    conviction = ICPillar(name="conviction", components=conviction_components)

    # Constitution Fit（策略适配）
    role = judgment.get("portfolio_role", "")
    role_weight = judgment.get("role_weight_range", [0, 0])
    suggested = portfolio.get("suggested_weight", 0)
    in_range = role_weight[0] <= suggested <= role_weight[1] if role_weight and suggested else True

    fit_components = [
        {
            "name": "策略角色匹配",
            "state": "supported" if role else "unknown",
            "score": 80 if role else 50,
            "note": f"角色: {role}",
        },
        {
            "name": "权重在范围内",
            "state": "supported" if in_range else "contradicted",
            "score": 85 if in_range else 40,
            "note": f"建议 {suggested}% vs 范围 {role_weight}",
        },
        {
            "name": "认知层次匹配",
            "state": "supported",
            "score": 70,
            "note": f"层次: {judgment.get('level', '')}",
        },
    ]
    constitution_fit = ICPillar(name="constitution_fit", components=fit_components)

    # Data Quality（数据质量）
    funds_with_val = sum(1 for f in fund_matches if f.get("valuation", {}).get("weighted_pe"))
    funds_total = len(fund_matches) if fund_matches else 1
    val_coverage = funds_with_val / funds_total if funds_total else 0

    quality_components = [
        {
            "name": "数据新鲜度",
            "state": "supported",
            "score": 70,
            "note": "使用最新季报数据",
        },
        {
            "name": "估值数据完整性",
            "state": "supported" if val_coverage >= 0.8 else "unknown",
            "score": min(100, val_coverage * 100),
            "note": f"{funds_with_val}/{funds_total} 基金有估值数据",
        },
        {
            "name": "证据可溯",
            "state": "supported" if supporting else "unknown",
            "score": 75 if supporting else 40,
            "note": f"{len(supporting)} 条可溯证据",
        },
        {
            "name": "门禁覆盖",
            "state": "supported",
            "score": 80,
            "note": f"{len(gated_out)} 只基金被门禁拦截",
        },
    ]
    data_quality = ICPillar(name="data_quality", components=quality_components)

    # 3. 执行审查
    return run_ic_review(hurdles, [conviction, constitution_fit, data_quality])
