"""投资假设追踪闭环：Brier Score + 贝叶斯更新

会议记录提到："从我相信什么开始，验证它，纠正它"。

本模块实现假设追踪的完整闭环：
1. Brier Score 量化预测准确度：Brier = (1/N) * Σ(fi - oi)²
   - fi = 预测概率，oi = 实际结果（1=发生, 0=未发生）
   - Brier 越低越好（0=完美, 0.25=随机, 1=完全反向）
2. 贝叶斯更新：当新证据出现时动态更新假设置信度
   - 简化公式：posterior = (prior * lr) / (prior * lr + (1 - prior))
   - lr = likelihood_ratio（>1 支持证据, <1 反对证据）
3. 历史假设的回顾和复盘
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class EvidenceEvent:
    """一条证据事件"""
    evidence_id: str
    thesis_id: str
    timestamp: str                    # ISO 日期
    description: str                  # 证据描述
    direction: str                    # "support" | "oppose"
    likelihood_ratio: float           # 似然比（>1 支持, <1 反对）
    source: str                       # 证据来源
    raw_data: dict[str, Any] | None = None  # 原始数据


@dataclass
class ThesisPrediction:
    """一个假设的预测"""
    prediction_id: str
    thesis_id: str
    timestamp: str
    prediction: str                   # 预测内容
    probability: float                # 预测概率 [0, 1]
    time_horizon: str                 # "short" | "mid" | "long"
    benchmark: str                    # 比较基准
    resolved: bool = False            # 是否已验证
    outcome: float | None = None      # 实际结果 [0, 1]
    resolution_date: str | None = None


@dataclass
class WatchItem:
    """投资假设监控项

    借鉴 FundOps 的 WatchItemSpec，对投资假设的关键指标进行持续监控。
    每个监控项定义一个指标、比较器和阈值，表达"健康区间"，
    通过状态机（intact/watch/broken）跟踪假设是否仍然成立。
    """
    item_id: str
    item_type: str           # "assumption" | "return_driver" | "risk" | "kill_criterion"
    title: str               # 如"基金经理持续加仓AI方向"
    tracking_mode: str       # "quantitative" | "qualitative" | "unsupported"
    metric: str | None       # 指标名（如 "match_pct", "pe", "val_pct", "trend"）
    comparator: str          # ">" | ">=" | "<" | "<="  -- 表达健康区间
    threshold: float | None  # 阈值
    cadence: str             # "quarterly" | "monthly"（检查频率）
    confirmation_periods: int # 连续 breach 几期才确认 broken（默认 2）
    immediate_kill: bool     # 是否立即触发退出审查
    why_matters: str         # 该指标在假设中的作用
    # 运行时状态
    status: str = "unknown"  # "intact" | "watch" | "broken" | "unknown" | "data_gap"
    consecutive_breaches: int = 0
    last_checked: str | None = None
    last_value: float | None = None
    check_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ThesisTracker:
    """假设追踪器

    持有一个投资假设的先验/后验概率、预测列表、证据历史和 Brier Score 记录，
    支持贝叶斯更新和预测验证。同时持有 WatchItem 列表，用于假设健康监控。
    """
    thesis_id: str
    prior_probability: float          # 初始置信度
    posterior_probability: float      # 当前后验概率
    predictions: list[ThesisPrediction] = field(default_factory=list)
    evidence_history: list[EvidenceEvent] = field(default_factory=list)
    brier_scores: list[dict[str, Any]] = field(default_factory=list)
    watch_items: list[WatchItem] = field(default_factory=list)

    def add_evidence(self, evidence: EvidenceEvent) -> float:
        """添加证据，更新后验概率（贝叶斯更新）

        使用简化贝叶斯公式：posterior = (prior * lr) / (prior * lr + (1 - prior))
        并将后验限制在 [0.01, 0.99] 区间，避免极端值导致后续更新失效。
        """
        self.evidence_history.append(evidence)
        lr = evidence.likelihood_ratio
        prior = self.posterior_probability
        # 贝叶斯更新
        posterior = (prior * lr) / (prior * lr + (1 - prior))
        # 防止 0 和 1
        posterior = max(0.01, min(0.99, posterior))
        self.posterior_probability = round(posterior, 4)
        return self.posterior_probability

    def add_prediction(self, prediction: ThesisPrediction) -> None:
        """添加预测"""
        self.predictions.append(prediction)

    def resolve_prediction(self, prediction_id: str, outcome: float) -> dict[str, Any]:
        """验证预测，计算 Brier Score

        outcome 为实际结果（1=预测发生, 0=未发生），
        Brier Score = (probability - outcome)²。
        """
        for p in self.predictions:
            if p.prediction_id == prediction_id:
                p.resolved = True
                p.outcome = outcome
                p.resolution_date = date.today().isoformat()
                brier = (p.probability - outcome) ** 2
                result = {
                    "prediction_id": prediction_id,
                    "prediction": p.prediction,
                    "probability": p.probability,
                    "outcome": outcome,
                    "brier_score": round(brier, 4),
                    "resolution_date": p.resolution_date,
                }
                self.brier_scores.append(result)
                return result
        raise ValueError(f"Prediction {prediction_id} not found")

    def get_summary(self) -> dict[str, Any]:
        """获取假设追踪摘要

        汇总先验/后验概率变化、证据计数、预测数量、平均 Brier Score 和准确度评级。
        """
        resolved = [p for p in self.predictions if p.resolved]
        avg_brier = (
            sum((p.probability - p.outcome) ** 2 for p in resolved) / len(resolved)
            if resolved else None
        )
        return {
            "thesis_id": self.thesis_id,
            "prior_probability": self.prior_probability,
            "posterior_probability": self.posterior_probability,
            "probability_change": round(self.posterior_probability - self.prior_probability, 4),
            "total_evidence": len(self.evidence_history),
            "supporting_evidence": sum(1 for e in self.evidence_history if e.direction == "support"),
            "opposing_evidence": sum(1 for e in self.evidence_history if e.direction == "oppose"),
            "total_predictions": len(self.predictions),
            "resolved_predictions": len(resolved),
            "avg_brier_score": round(avg_brier, 4) if avg_brier is not None else None,
            "prediction_accuracy": "good" if avg_brier and avg_brier < 0.15 else "fair" if avg_brier and avg_brier < 0.25 else "poor" if avg_brier else "untested",
        }

    def set_watch_plan(self, items: list[WatchItem]) -> None:
        """设置监控计划"""
        self.watch_items = items

    def refresh_health(self, current_metrics: dict[str, float | None]) -> dict[str, Any]:
        """刷新健康状态，返回摘要

        用最新指标值刷新所有监控项状态，并聚合出健康标签。
        """
        self.watch_items = refresh_watch_items(self.watch_items, current_metrics)
        label = summary_label(self.watch_items)
        return {
            "health_label": label,
            "total_items": len(self.watch_items),
            "intact": sum(1 for i in self.watch_items if i.status == "intact"),
            "watch": sum(1 for i in self.watch_items if i.status == "watch"),
            "broken": sum(1 for i in self.watch_items if i.status == "broken"),
            "data_gap": sum(1 for i in self.watch_items if i.status == "data_gap"),
            "items": [
                {
                    "item_id": i.item_id,
                    "item_type": i.item_type,
                    "title": i.title,
                    "metric": i.metric,
                    "status": i.status,
                    "last_value": i.last_value,
                    "threshold": i.threshold,
                    "comparator": i.comparator,
                    "consecutive_breaches": i.consecutive_breaches,
                    "confirmation_periods": i.confirmation_periods,
                    "immediate_kill": i.immediate_kill,
                    "why_matters": i.why_matters,
                }
                for i in self.watch_items
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典

        将 summary 字段展开到顶层，方便前端直接访问概率变化、证据计数、
        Brier Score 等关键字段，同时保留嵌套的 summary 供程序化使用。
        """
        summary = self.get_summary()
        return {
            **summary,
            "predictions": [
                {
                    "prediction_id": p.prediction_id,
                    "timestamp": p.timestamp,
                    "prediction": p.prediction,
                    "probability": p.probability,
                    "time_horizon": p.time_horizon,
                    "benchmark": p.benchmark,
                    "resolved": p.resolved,
                    "outcome": p.outcome,
                    "resolution_date": p.resolution_date,
                }
                for p in self.predictions
            ],
            "evidence_history": [
                {
                    "evidence_id": e.evidence_id,
                    "timestamp": e.timestamp,
                    "description": e.description,
                    "direction": e.direction,
                    "likelihood_ratio": e.likelihood_ratio,
                    "source": e.source,
                }
                for e in self.evidence_history
            ],
            "brier_scores": self.brier_scores,
            "watch_items": [
                {
                    "item_id": w.item_id,
                    "item_type": w.item_type,
                    "title": w.title,
                    "tracking_mode": w.tracking_mode,
                    "metric": w.metric,
                    "comparator": w.comparator,
                    "threshold": w.threshold,
                    "cadence": w.cadence,
                    "confirmation_periods": w.confirmation_periods,
                    "immediate_kill": w.immediate_kill,
                    "why_matters": w.why_matters,
                    "status": w.status,
                    "consecutive_breaches": w.consecutive_breaches,
                    "last_checked": w.last_checked,
                    "last_value": w.last_value,
                }
                for w in self.watch_items
            ],
            "summary": summary,
        }


def evaluate_item(item: WatchItem, observed: float | None) -> str:
    """确定性评估监控项状态。

    状态机逻辑：
    - observed 为 None -> "data_gap"（保留先前状态）
    - 满足 comparator -> "intact"，breaches 清零
    - 不满足 -> breaches+1：
      - breaches >= confirmation_periods -> "broken"
      - 否则 -> "watch"
    """
    if observed is None:
        return "data_gap"

    threshold = item.threshold
    if threshold is None:
        return "data_gap"

    cmp = item.comparator
    if cmp == ">":
        ok = observed > threshold
    elif cmp == ">=":
        ok = observed >= threshold
    elif cmp == "<":
        ok = observed < threshold
    elif cmp == "<=":
        ok = observed <= threshold
    else:
        return "data_gap"

    if ok:
        item.consecutive_breaches = 0
        return "intact"
    else:
        item.consecutive_breaches += 1
        if item.consecutive_breaches >= item.confirmation_periods:
            return "broken"
        return "watch"


def summary_label(items: list[WatchItem]) -> str:
    """从所有 quantitative items 聚合健康标签。

    - 全部 unknown/data_gap -> "Not Checked"
    - 有 broken -> "Broken"
    - 有 watch -> "Watching"
    - 否则 -> "Intact"
    """
    # 只看 quantitative 类型的监控项
    quant_items = [i for i in items if i.tracking_mode == "quantitative"]
    if not quant_items:
        return "Not Checked"

    statuses = {i.status for i in quant_items}
    # 全部未检查
    if statuses.issubset({"unknown", "data_gap"}):
        return "Not Checked"
    # 有 broken 优先
    if "broken" in statuses:
        return "Broken"
    # 有 watch
    if "watch" in statuses:
        return "Watching"
    # 否则全部 intact
    return "Intact"


def refresh_watch_items(
    items: list[WatchItem],
    current_metrics: dict[str, float | None],
) -> list[WatchItem]:
    """用最新指标值刷新所有监控项状态。

    current_metrics 是一个字典，包含：
    - "match_pct": 顶部基金匹配度
    - "pe": 加权PE
    - "val_pct": 估值分位
    - "peg": PEG
    - "trend": 趋势值（1=increasing, 0=stable, -1=decreasing）
    - "opposing_count": 反对证据数量
    """
    today = date.today().isoformat()
    for item in items:
        if item.tracking_mode != "quantitative" or item.metric is None:
            continue
        observed = current_metrics.get(item.metric)
        item.last_value = observed
        item.last_checked = today
        item.status = evaluate_item(item, observed)
        item.check_history.append({
            "date": today,
            "value": observed,
            "status": item.status,
            "consecutive_breaches": item.consecutive_breaches,
        })
    return items


def create_watch_plan_from_cognition(
    direction: str,
    validation_result: dict[str, Any],
    fund_matches: list[dict[str, Any]],
    judgment: dict[str, Any],
) -> list[WatchItem]:
    """从认知分析结果自动生成 4-6 个监控项。

    生成规则：
    1. kill_criterion: 估值分位超过 hard_limits.max_valuation_percentile
    2. kill_criterion: PEG 超过 hard_limits.max_peg（如果有）
    3. return_driver: 匹配度维持
    4. assumption: 持仓趋势不逆转
    5. risk: 反对证据数量不激增
    6. return_driver: 核心指标（key_metric）在健康区间
    """
    items: list[WatchItem] = []
    hard_limits = judgment.get("hard_limits", {})
    max_val_pct = hard_limits.get("max_valuation_percentile")
    max_peg = hard_limits.get("max_peg")

    # 顶部基金的匹配度（用于设置匹配度维持阈值）
    top_match_pct = fund_matches[0].get("match_pct") if fund_matches else None

    # 当前反对证据数量
    current_opposing = len(validation_result.get("opposing_evidence", []))

    # 1. kill_criterion: 估值分位不超过硬上限
    if max_val_pct is not None:
        items.append(WatchItem(
            item_id=f"{direction}_kill_valpct",
            item_type="kill_criterion",
            title="估值分位不超过硬约束上限",
            tracking_mode="quantitative",
            metric="val_pct",
            comparator="<=",
            threshold=float(max_val_pct),
            cadence="quarterly",
            confirmation_periods=1,
            immediate_kill=True,
            why_matters="估值分位超限是退出审查的硬触发条件",
        ))

    # 2. kill_criterion: PEG 不超过硬上限
    if max_peg is not None:
        items.append(WatchItem(
            item_id=f"{direction}_kill_peg",
            item_type="kill_criterion",
            title="PEG 不超过硬约束上限",
            tracking_mode="quantitative",
            metric="peg",
            comparator="<=",
            threshold=float(max_peg),
            cadence="quarterly",
            confirmation_periods=1,
            immediate_kill=True,
            why_matters="PEG 超限意味着增速无法支撑估值，触发退出审查",
        ))

    # 3. return_driver: 匹配度维持（不低于顶部基金匹配度的 70%）
    if top_match_pct is not None:
        items.append(WatchItem(
            item_id=f"{direction}_driver_match",
            item_type="return_driver",
            title="基金匹配度维持在合理水平",
            tracking_mode="quantitative",
            metric="match_pct",
            comparator=">=",
            threshold=round(top_match_pct * 0.7, 1),
            cadence="quarterly",
            confirmation_periods=2,
            immediate_kill=False,
            why_matters="匹配度持续下降意味着基金持仓偏离认知方向",
        ))

    # 4. assumption: 持仓趋势不逆转（非 decreasing）
    items.append(WatchItem(
        item_id=f"{direction}_assumption_trend",
        item_type="assumption",
        title="持仓趋势不逆转",
        tracking_mode="quantitative",
        metric="trend",
        comparator=">=",
        threshold=0,
        cadence="quarterly",
        confirmation_periods=2,
        immediate_kill=False,
        why_matters="持仓趋势逆转意味着资金正在撤出该方向",
    ))

    # 5. risk: 反对证据数量不激增
    items.append(WatchItem(
        item_id=f"{direction}_risk_opposing",
        item_type="risk",
        title="反对证据数量不激增",
        tracking_mode="quantitative",
        metric="opposing_count",
        comparator="<=",
        threshold=float(current_opposing + 3),
        cadence="monthly",
        confirmation_periods=2,
        immediate_kill=False,
        why_matters="反对证据激增意味着认知基础可能被动摇",
    ))

    # 6. return_driver: 核心指标在健康区间
    key_metric = judgment.get("key_metric", "")
    # key_metric 到监控指标的映射
    key_metric_map = {
        "peg": ("peg", "<=", float(max_peg) if max_peg else 2.0),
        "pe": ("pe", "<=", 50.0),
        "val_pct": ("val_pct", "<=", float(max_val_pct) if max_val_pct else 85.0),
    }
    if key_metric in key_metric_map:
        metric_name, cmp, thr = key_metric_map[key_metric]
        # 避免与 kill_criterion 重复
        existing_metrics = {i.metric for i in items if i.item_type == "kill_criterion"}
        if metric_name not in existing_metrics:
            items.append(WatchItem(
                item_id=f"{direction}_driver_keymetric",
                item_type="return_driver",
                title=f"核心指标 {key_metric} 维持在健康区间",
                tracking_mode="quantitative",
                metric=metric_name,
                comparator=cmp,
                threshold=thr,
                cadence="quarterly",
                confirmation_periods=2,
                immediate_kill=False,
                why_matters=f"核心指标 {key_metric} 是判断该方向投资价值的关键",
            ))

    return items


def create_tracker_from_cognition(
    thesis_id: str,
    validation_result: dict[str, Any],
    initial_probability: float = 0.5,
    direction: str | None = None,
    fund_matches: list[dict[str, Any]] | None = None,
    judgment: dict[str, Any] | None = None,
) -> ThesisTracker:
    """从认知验证结果创建假设追踪器。

    将 step5_validation 中的支持/反对证据转化为 EvidenceEvent，
    初始概率根据裁决结果设置。如果传入 direction/fund_matches/judgment，
    则自动生成假设健康监控计划。

    Args:
        thesis_id: 假设唯一标识
        validation_result: engine.py 中 validate_cognition 返回的 validation 字典
        initial_probability: 初始先验概率，默认 0.5
        direction: 投资方向（用于生成监控项 ID）
        fund_matches: 匹配基金列表（用于提取顶部基金指标）
        judgment: 认知判断模板（用于提取 hard_limits 和 key_metric）

    Returns:
        已填充证据并完成贝叶斯更新的 ThesisTracker
    """
    tracker = ThesisTracker(
        thesis_id=thesis_id,
        prior_probability=initial_probability,
        posterior_probability=initial_probability,
    )

    # 根据裁决结果调整初始概率
    verdict = validation_result.get("verdict", "")
    if "有效" in verdict:
        tracker.posterior_probability = min(0.85, initial_probability + 0.2)
    elif "存疑" in verdict:
        tracker.posterior_probability = max(0.15, initial_probability - 0.15)

    # 将支持证据添加为支持事件
    for i, evidence in enumerate(validation_result.get("supporting_evidence", [])[:10]):
        tracker.add_evidence(EvidenceEvent(
            evidence_id=f"{thesis_id}_sup_{i}",
            thesis_id=thesis_id,
            timestamp=date.today().isoformat(),
            description=evidence.get("claim", str(evidence)[:100]),
            direction="support",
            likelihood_ratio=1.3,  # 默认似然比
            source=evidence.get("source", "cognition_engine"),
        ))

    # 将反对证据添加为反对事件
    for i, evidence in enumerate(validation_result.get("opposing_evidence", [])[:10]):
        tracker.add_evidence(EvidenceEvent(
            evidence_id=f"{thesis_id}_opp_{i}",
            thesis_id=thesis_id,
            timestamp=date.today().isoformat(),
            description=evidence.get("claim", str(evidence)[:100]),
            direction="oppose",
            likelihood_ratio=0.7,  # 默认似然比
            source=evidence.get("source", "cognition_engine"),
        ))

    # 从认知结果自动生成假设健康监控计划
    if direction is not None and fund_matches is not None and judgment is not None:
        watch_plan = create_watch_plan_from_cognition(
            direction, validation_result, fund_matches, judgment,
        )
        tracker.set_watch_plan(watch_plan)

    return tracker
