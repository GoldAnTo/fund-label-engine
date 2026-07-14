"""确定性筛选器：评估准则 + 百分位排名 + 失败原因记录

FundOps 的 Screener 是完全确定性的：AI 绝不参与筛选或排名。
四阶段流水线：fetch_metrics -> evaluate -> rank -> snapshot
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.governance.constitution import Criterion, MetricDef, METRIC_CATALOG


@dataclass
class ScreenResult:
    """单个基金的筛选结果"""
    fund_code: str
    fund_name: str
    passed: bool                    # 是否通过所有 screen 准则
    fail_reasons: list[dict]        # 失败原因列表
    pass_evidence: list[dict]       # 通过的准则列表
    metrics: dict[str, float | None]  # 指标观测值
    rank_score: float = 0.0        # 排名得分（百分位加权）
    rank_components: list[dict] = field(default_factory=list)  # 排名明细

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "passed": self.passed,
            "fail_reasons": self.fail_reasons,
            "pass_evidence": self.pass_evidence,
            "metrics": self.metrics,
            "rank_score": round(self.rank_score, 2),
            "rank_components": self.rank_components,
        }


@dataclass
class ScreenSnapshot:
    """筛选快照"""
    direction: str
    total_funds: int
    passed_funds: int
    failed_funds: int
    results: list[ScreenResult]
    screen_criteria: list[Criterion]    # 使用的筛选准则
    ranking_blend: list[dict]           # 使用的排名混合
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "total_funds": self.total_funds,
            "passed_funds": self.passed_funds,
            "failed_funds": self.failed_funds,
            "results": [r.to_dict() for r in self.results],
            "screen_criteria_count": len(self.screen_criteria),
            "ranking_blend": self.ranking_blend,
            "created_at": self.created_at,
        }


def extract_fund_metrics(fund_match: dict[str, Any]) -> dict[str, float | None]:
    """从基金匹配结果提取指标观测值"""
    valuation = fund_match.get("valuation", {})
    trend = fund_match.get("trend", {})
    return {
        "pe": valuation.get("weighted_pe"),
        "pb": valuation.get("weighted_pb"),
        "roe": valuation.get("weighted_roe"),
        "peg": valuation.get("peg"),
        "val_pct": valuation.get("weighted_val_pct"),
        "match_pct": fund_match.get("match_pct"),
        "dividend_yield": valuation.get("weighted_dividend"),
        "revenue_growth": valuation.get("weighted_growth"),
    }


def evaluate_fund(
    fund_code: str,
    fund_name: str,
    fund_match: dict[str, Any],
    screen_criteria: list[Criterion],
) -> ScreenResult:
    """
    评估单个基金是否通过所有筛选准则。

    关键设计（借鉴 FundOps）：
    - 评估 ALL 准则，不是遇到第一个失败就停
    - 缺失数据 -> satisfied=None，记为 "数据不足"
    - 所有失败原因都记录
    """
    metrics = extract_fund_metrics(fund_match)
    fail_reasons: list[dict] = []
    pass_evidence: list[dict] = []

    for crit in screen_criteria:
        observed = metrics.get(crit.metric)
        passed, reason = crit.evaluate(observed)

        entry = {
            "criterion_id": crit.criterion_id,
            "metric": crit.metric,
            "operator": crit.operator,
            "threshold": crit.value,
            "observed": observed,
            "passed": passed,
            "reason": reason,
        }

        if passed is True:
            pass_evidence.append(entry)
        elif passed is False:
            fail_reasons.append(entry)
        else:
            # None = 数据不足，也算失败原因
            fail_reasons.append(entry)

    return ScreenResult(
        fund_code=fund_code,
        fund_name=fund_name,
        passed=len(fail_reasons) == 0,
        fail_reasons=fail_reasons,
        pass_evidence=pass_evidence,
        metrics=metrics,
    )


def percentile_rank(
    values: list[tuple[str, float]],
    lower_is_better: bool = False,
) -> dict[str, float]:
    """
    百分位排名。

    输入：[(fund_code, value), ...]
    输出：{fund_code: percentile}（0-100，越高越好）

    使用半秩百分位：(below + 0.5 * equal) / len * 100
    """
    if not values:
        return {}

    n = len(values)
    result: dict[str, float] = {}

    for code, val in values:
        if val is None:
            result[code] = 0.0
            continue
        below = sum(1 for _, v in values if v is not None and v < val)
        equal = sum(1 for _, v in values if v is not None and v == val)
        pct = (below + 0.5 * equal) / n * 100
        if lower_is_better:
            pct = 100 - pct
        result[code] = round(pct, 1)

    return result


def rank_funds(
    passed_results: list[ScreenResult],
    ranking_blend: list[dict],
) -> list[ScreenResult]:
    """
    对通过筛选的基金做百分位排名。

    ranking_blend 格式：[{"metric": "match_pct", "weight": 0.5, "invert": False}, ...]
    """
    if not passed_results or not ranking_blend:
        return passed_results

    for item in ranking_blend:
        metric = item["metric"]
        weight = item.get("weight", 1.0)
        invert = item.get("invert", False)

        metric_def = METRIC_CATALOG.get(metric)
        lower_is_better = invert if invert else (metric_def.lower_is_better if metric_def else False)

        values = [(r.fund_code, r.metrics.get(metric)) for r in passed_results]
        percentiles = percentile_rank(values, lower_is_better)

        for r in passed_results:
            pct = percentiles.get(r.fund_code, 0)
            contribution = pct * weight
            r.rank_score += contribution
            r.rank_components.append({
                "metric": metric,
                "weight": weight,
                "observed": r.metrics.get(metric),
                "percentile": pct,
                "contribution": round(contribution, 2),
            })

    # 归一化权重
    total_weight = sum(item.get("weight", 1.0) for item in ranking_blend)
    if total_weight > 0:
        for r in passed_results:
            r.rank_score = round(r.rank_score / total_weight, 2)

    # 按得分降序
    passed_results.sort(key=lambda x: x.rank_score, reverse=True)
    return passed_results


def run_screener(
    direction: str,
    fund_matches: list[dict[str, Any]],
    compiled: dict[str, Any],
) -> ScreenSnapshot:
    """
    执行确定性筛选。

    流程：
    1. 提取 screen_criteria 和 ranking_blend
    2. 对每个基金评估所有准则
    3. 对通过的基金做百分位排名
    4. 返回快照
    """
    from datetime import date

    screen_criteria = compiled.get("screen_requirements", [])
    ranking_blend = compiled.get("ranking_blend", [])

    results: list[ScreenResult] = []
    for fm in fund_matches:
        r = evaluate_fund(
            fund_code=fm["fund_code"],
            fund_name=fm.get("fund_name", ""),
            fund_match=fm,
            screen_criteria=screen_criteria,
        )
        results.append(r)

    # 分离通过/未通过
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    # 排名
    passed = rank_funds(passed, ranking_blend)

    # 合并（通过的在前，按排名；未通过的在后）
    all_results = passed + failed

    return ScreenSnapshot(
        direction=direction,
        total_funds=len(results),
        passed_funds=len(passed),
        failed_funds=len(failed),
        results=all_results,
        screen_criteria=screen_criteria,
        ranking_blend=ranking_blend,
        created_at=date.today().isoformat(),
    )
