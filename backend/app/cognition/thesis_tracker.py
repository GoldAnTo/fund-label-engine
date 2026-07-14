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
class ThesisTracker:
    """假设追踪器

    持有一个投资假设的先验/后验概率、预测列表、证据历史和 Brier Score 记录，
    支持贝叶斯更新和预测验证。
    """
    thesis_id: str
    prior_probability: float          # 初始置信度
    posterior_probability: float      # 当前后验概率
    predictions: list[ThesisPrediction] = field(default_factory=list)
    evidence_history: list[EvidenceEvent] = field(default_factory=list)
    brier_scores: list[dict[str, Any]] = field(default_factory=list)

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
            "summary": summary,
        }


def create_tracker_from_cognition(
    thesis_id: str,
    validation_result: dict[str, Any],
    initial_probability: float = 0.5,
) -> ThesisTracker:
    """从认知验证结果创建假设追踪器。

    将 step5_validation 中的支持/反对证据转化为 EvidenceEvent，
    初始概率根据裁决结果设置。

    Args:
        thesis_id: 假设唯一标识
        validation_result: engine.py 中 validate_cognition 返回的 validation 字典
        initial_probability: 初始先验概率，默认 0.5

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

    return tracker
