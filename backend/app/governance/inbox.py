"""决策队列：attention item + 响应记录 + 幂等去重"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# === Attention Item 类型定义 ===

ATTENTION_TYPES = {
    "thesis_break": {
        "display_name": "假设断裂",
        "severity": "high",
        "response_set": ["open", "reviewed", "not_material", "thesis_still_intact", "already_acted", "snooze"],
    },
    "portfolio_pressure": {
        "display_name": "组合压力",
        "severity": "medium",
        "response_set": ["open", "reviewed", "not_material", "thesis_still_intact", "already_acted", "snooze", "dismiss"],
    },
    "constitution_fit": {
        "display_name": "策略适配",
        "severity": "medium",
        "response_set": ["open", "interested", "watch", "not_strategy_fit", "too_risky", "already_know", "dismiss"],
    },
    "ic_review_fail": {
        "display_name": "投决会未通过",
        "severity": "high",
        "response_set": ["open", "override", "reviewed", "dismiss"],
    },
    "valuation_breach": {
        "display_name": "估值突破",
        "severity": "high",
        "response_set": ["open", "reviewed", "already_acted", "snooze", "dismiss"],
    },
    "data_gap": {
        "display_name": "数据缺口",
        "severity": "low",
        "response_set": ["open", "dismiss", "snooze"],
    },
    "workflow_failure": {
        "display_name": "工作流失败",
        "severity": "medium",
        "response_set": ["open", "retry", "dismiss"],
    },
}

# feedback 响应（成为学习信号）
FEEDBACK_RESPONSES = {"interested", "watch", "not_strategy_fit", "too_risky", "already_know", "not_material", "thesis_still_intact"}


@dataclass
class AttentionItem:
    """决策队列项"""
    item_id: str
    source_type: str           # 引用 ATTENTION_TYPES
    source_id: str             # 来源 ID（如 thesis_id, fund_code）
    source_version: str        # 版本（用于幂等去重）
    title: str
    body: str
    severity: str              # "high" | "medium" | "low"
    fund_code: str | None = None
    direction: str | None = None
    response_set: list[str] = field(default_factory=list)
    status: str = "open"       # "open" | "resolved" | "dismissed" | "snoozed"
    response: str | None = None
    response_note: str = ""
    created_at: str = ""
    responded_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_type": self.source_type,
            "source_type_display": ATTENTION_TYPES.get(self.source_type, {}).get("display_name", self.source_type),
            "source_id": self.source_id,
            "source_version": self.source_version,
            "title": self.title,
            "body": self.body,
            "severity": self.severity,
            "fund_code": self.fund_code,
            "direction": self.direction,
            "response_set": self.response_set,
            "status": self.status,
            "response": self.response,
            "response_note": self.response_note,
            "created_at": self.created_at,
            "responded_at": self.responded_at,
        }


@dataclass
class InboxSnapshot:
    """Inbox 快照"""
    total_items: int
    open_items: int
    high_severity: int
    medium_severity: int
    low_severity: int
    items: list[AttentionItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "open_items": self.open_items,
            "high_severity": self.high_severity,
            "medium_severity": self.medium_severity,
            "low_severity": self.low_severity,
            "items": [i.to_dict() for i in self.items],
        }


def create_attention_item(
    source_type: str,
    source_id: str,
    source_version: str,
    title: str,
    body: str,
    fund_code: str | None = None,
    direction: str | None = None,
) -> AttentionItem:
    """创建 attention item"""
    config = ATTENTION_TYPES.get(source_type, {})
    return AttentionItem(
        item_id=f"att_{source_type}_{source_id}_{source_version}"[:64],
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        title=title,
        body=body,
        severity=config.get("severity", "medium"),
        fund_code=fund_code,
        direction=direction,
        response_set=config.get("response_set", ["open", "dismiss"]),
        created_at=datetime.now().isoformat(),
    )


def create_inbox_from_cognition(
    direction: str,
    ic_review: dict[str, Any],
    thesis_health: dict[str, Any],
    fund_matches: list[dict[str, Any]],
    gated_out: list[dict[str, Any]],
) -> list[AttentionItem]:
    """
    从认知分析结果生成 attention items。

    规则：
    1. IC Review fail -> ic_review_fail item
    2. Thesis Health broken -> thesis_break item
    3. Thesis Health watch -> thesis_break item (severity=medium)
    4. 估值门禁拦截 -> valuation_breach item
    5. 数据缺口 -> data_gap item
    """
    items: list[AttentionItem] = []
    version = datetime.now().strftime("%Y%m%d")

    # 1. IC Review fail
    if ic_review.get("verdict") == "fail":
        items.append(create_attention_item(
            source_type="ic_review_fail",
            source_id=direction,
            source_version=version,
            title=f"{direction} 投决会未通过",
            body=f"Gate Score: {ic_review.get('gate_score', 0)}/{ic_review.get('cutoff', 70)}. "
                 f"原因: {ic_review.get('fail_reason', '未知')}",
            direction=direction,
        ))

    # 2. Thesis Health
    health_label = thesis_health.get("health_label", "")
    if health_label == "Broken":
        broken_items = [i for i in thesis_health.get("items", []) if i.get("status") == "broken"]
        for bi in broken_items:
            items.append(create_attention_item(
                source_type="thesis_break",
                source_id=f"{direction}_{bi.get('item_id', '')}",
                source_version=version,
                title=f"假设监控项断裂: {bi.get('title', '')}",
                body=f"指标 {bi.get('metric')}: 观测值 {bi.get('last_value')}, "
                     f"阈值 {bi.get('comparator')} {bi.get('threshold')}. "
                     f"连续违规 {bi.get('consecutive_breaches')}/{bi.get('confirmation_periods')} 期. "
                     f"原因: {bi.get('why_matters', '')}",
                direction=direction,
            ))
    elif health_label == "Watching":
        watch_items = [i for i in thesis_health.get("items", []) if i.get("status") == "watch"]
        for wi in watch_items:
            # 创建低优先级的 watch item
            item = create_attention_item(
                source_type="thesis_break",
                source_id=f"{direction}_{wi.get('item_id', '')}",
                source_version=version,
                title=f"假设监控项观察: {wi.get('title', '')}",
                body=f"指标 {wi.get('metric')}: 观测值 {wi.get('last_value')}, "
                     f"阈值 {wi.get('comparator')} {wi.get('threshold')}. "
                     f"连续违规 {wi.get('consecutive_breaches')}/{wi.get('confirmation_periods')} 期.",
                direction=direction,
            )
            item.severity = "medium"
            items.append(item)

    # 3. 估值门禁拦截
    for g in gated_out[:5]:
        violations = g.get("violations", [])
        violation_text = "; ".join(violations) if violations else "未知"
        items.append(create_attention_item(
            source_type="valuation_breach",
            source_id=g.get("fund_code", ""),
            source_version=version,
            title=f"基金 {g.get('fund_code', '')} 被估值门禁拦截",
            body=f"匹配度 {g.get('match_pct', 0)}%. 违规: {violation_text}",
            fund_code=g.get("fund_code"),
            direction=direction,
        ))

    # 4. 数据缺口
    for fm in fund_matches:
        val = fm.get("valuation", {})
        if not val.get("weighted_pe"):
            items.append(create_attention_item(
                source_type="data_gap",
                source_id=fm.get("fund_code", ""),
                source_version=version,
                title=f"基金 {fm.get('fund_code', '')} 缺少估值数据",
                body=f"匹配度 {fm.get('match_pct', 0)}%, 但缺少加权PE等估值指标.",
                fund_code=fm.get("fund_code"),
                direction=direction,
            ))

    return items


def build_inbox_snapshot(items: list[AttentionItem]) -> InboxSnapshot:
    """构建 Inbox 快照"""
    open_items = [i for i in items if i.status == "open"]
    return InboxSnapshot(
        total_items=len(items),
        open_items=len(open_items),
        high_severity=sum(1 for i in open_items if i.severity == "high"),
        medium_severity=sum(1 for i in open_items if i.severity == "medium"),
        low_severity=sum(1 for i in open_items if i.severity == "low"),
        items=sorted(open_items, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity, 3)),
    )
