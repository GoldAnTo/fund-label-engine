"""证据系统：证据源 + 冻结 bundle + 共享证据包"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class EvidenceSource:
    """证据源"""
    source_id: str             # 唯一 ID
    kind: str                  # "holding" | "nav" | "factor" | "industry" | "manager" | "valuation" | "chain_link" | "validation"
    locator: str               # 数据定位（表名+主键 或 URL）
    title: str                 # 标题
    publisher: str             # 数据来源（如 "akshare", "天天基金", "cognition_engine"）
    content_hash: str          # SHA-256 内容哈希
    excerpt: str               # 短摘录（< 200 字）
    snapshot: str | None       # 完整内容快照（JSON 字符串），None 表示不存全文
    fetched_at: str            # 抓取时间

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "locator": self.locator,
            "title": self.title,
            "publisher": self.publisher,
            "content_hash": self.content_hash,
            "excerpt": self.excerpt,
            "has_snapshot": self.snapshot is not None,
            "fetched_at": self.fetched_at,
        }


@dataclass
class EvidenceBundle:
    """冻结的证据包"""
    bundle_id: str
    manifest: dict[str, Any]   # 包含 evidence_ids, versions, inclusion_notes
    created_at: str
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "manifest": self.manifest,
            "created_at": self.created_at,
            "source_ids": self.source_ids,
        }


def compute_content_hash(content: str | dict | list) -> str:
    """计算内容的 SHA-256 哈希"""
    if isinstance(content, (dict, list)):
        content = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def create_evidence_source(
    kind: str,
    locator: str,
    title: str,
    publisher: str,
    content: str | dict | list,
    excerpt: str = "",
    store_snapshot: bool = False,
) -> EvidenceSource:
    """创建证据源"""
    content_str = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if not excerpt:
        excerpt = content_str[:200]
    return EvidenceSource(
        source_id=f"ev_{compute_content_hash(content_str)}",
        kind=kind,
        locator=locator,
        title=title,
        publisher=publisher,
        content_hash=compute_content_hash(content_str),
        excerpt=excerpt,
        snapshot=content_str if store_snapshot else None,
        fetched_at=date.today().isoformat(),
    )


def freeze_bundle(
    sources: list[EvidenceSource],
    inclusion_notes: str = "",
    context: dict[str, Any] | None = None,
) -> EvidenceBundle:
    """
    冻结证据包。

    在 artifact 写入前调用，确保所有证据不可变。
    """
    source_ids = [s.source_id for s in sources]
    manifest = {
        "evidence_ids": source_ids,
        "evidence_count": len(source_ids),
        "inclusion_notes": inclusion_notes,
        "context": context or {},
        "frozen_at": date.today().isoformat(),
    }
    bundle_id = f"bundle_{compute_content_hash(manifest)}"
    return EvidenceBundle(
        bundle_id=bundle_id,
        manifest=manifest,
        created_at=date.today().isoformat(),
        source_ids=source_ids,
    )


# === 基金证据包 ===
@dataclass
class FundEvidencePacket:
    """基金证据包：Thesis/IC/Memo 共用的确定性证据"""
    fund_code: str
    fund_name: str
    identity: dict[str, Any]           # 基金基本信息
    latest_metrics: dict[str, Any]     # 最新指标
    holdings: list[dict[str, Any]]     # 最新持仓
    holdings_history: list[dict]       # 持仓历史（多期）
    valuation: dict[str, Any]          # 估值数据
    trend: dict[str, Any]             # 持仓趋势
    manager: dict[str, Any] | None     # 基金经理
    match_analysis: dict[str, Any]     # 认知匹配分析
    data_quality_notes: list[str]      # 数据缺口说明
    evidence_sources: list[EvidenceSource]  # 证据源列表
    evidence_bundle: EvidenceBundle | None  # 冻结的证据包

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "identity": self.identity,
            "latest_metrics": self.latest_metrics,
            "holdings": self.holdings,
            "holdings_history": self.holdings_history,
            "valuation": self.valuation,
            "trend": self.trend,
            "manager": self.manager,
            "match_analysis": self.match_analysis,
            "data_quality_notes": self.data_quality_notes,
            "evidence_sources": [s.to_dict() for s in self.evidence_sources],
            "evidence_bundle": self.evidence_bundle.to_dict() if self.evidence_bundle else None,
        }


def build_fund_evidence_packet(
    fund_code: str,
    fund_name: str,
    fund_match: dict[str, Any],
    holdings: list[dict[str, Any]],
    holdings_history: list[dict] | None = None,
    direction: str = "",
) -> FundEvidencePacket:
    """
    构建基金证据包。

    从认知分析结果和持仓数据构建确定性证据包，
    供 IC Review / Investment Memo / Thesis Tracker 共用。

    关键原则（借鉴 FundOps ADR-0013）：
    - 工作流产物（IC verdicts / memos）永不回流入证据包
    - 证据包只从原始数据构建
    """
    sources: list[EvidenceSource] = []
    data_quality_notes: list[str] = []

    # 1. 基金基本信息
    identity = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_match.get("fund_type", ""),
        "fund_company": fund_match.get("fund_company", ""),
    }
    sources.append(create_evidence_source(
        kind="identity",
        locator=f"fund_profiles:{fund_code}",
        title=f"{fund_name} 基本信息",
        publisher="source_db",
        content=identity,
    ))

    # 2. 持仓数据
    if holdings:
        sources.append(create_evidence_source(
            kind="holding",
            locator=f"fund_stock_holdings:{fund_code}:latest",
            title=f"{fund_name} 最新持仓",
            publisher="source_db",
            content=holdings,
            excerpt=f"共 {len(holdings)} 只持仓股票",
        ))
    else:
        data_quality_notes.append("缺少持仓数据")

    # 3. 持仓历史
    if holdings_history:
        sources.append(create_evidence_source(
            kind="holding",
            locator=f"fund_stock_holdings:{fund_code}:history",
            title=f"{fund_name} 持仓历史",
            publisher="source_db",
            content=holdings_history,
            excerpt=f"共 {len(holdings_history)} 期持仓记录",
        ))

    # 4. 估值数据
    valuation = fund_match.get("valuation", {})
    if valuation:
        sources.append(create_evidence_source(
            kind="valuation",
            locator=f"valuation:{fund_code}",
            title=f"{fund_name} 估值数据",
            publisher="cognition_engine",
            content=valuation,
        ))
    else:
        data_quality_notes.append("缺少估值数据")

    # 5. 趋势数据
    trend = fund_match.get("trend", {})
    if trend and trend.get("trend") != "insufficient_data":
        sources.append(create_evidence_source(
            kind="trend",
            locator=f"trend:{fund_code}",
            title=f"{fund_name} 持仓趋势",
            publisher="cognition_engine",
            content=trend,
        ))
    else:
        data_quality_notes.append("持仓趋势数据不足")

    # 6. 基金经理
    manager = fund_match.get("manager")
    if manager:
        sources.append(create_evidence_source(
            kind="manager",
            locator=f"fund_manager_links:{fund_code}",
            title=f"{fund_name} 基金经理",
            publisher="source_db",
            content=manager,
        ))
    else:
        data_quality_notes.append("缺少基金经理信息")

    # 7. 认知匹配分析
    match_analysis = {
        "match_pct": fund_match.get("match_pct", 0),
        "chain_breakdown": fund_match.get("chain_breakdown", {}),
        "gate": fund_match.get("gate", {}),
    }
    sources.append(create_evidence_source(
        kind="validation",
        locator=f"match:{fund_code}:{direction}",
        title=f"{fund_name} 认知匹配分析",
        publisher="cognition_engine",
        content=match_analysis,
    ))

    # 8. 门禁结果
    gate = fund_match.get("gate", {})
    if gate:
        sources.append(create_evidence_source(
            kind="validation",
            locator=f"gate:{fund_code}",
            title=f"{fund_name} 估值门禁结果",
            publisher="cognition_engine",
            content=gate,
        ))

    # 冻结证据包
    bundle = freeze_bundle(
        sources,
        inclusion_notes=f"基金 {fund_code} 的证据包，方向: {direction}",
        context={"direction": direction, "fund_code": fund_code},
    )

    return FundEvidencePacket(
        fund_code=fund_code,
        fund_name=fund_name,
        identity=identity,
        latest_metrics={
            "match_pct": fund_match.get("match_pct", 0),
            "weighted_pe": valuation.get("weighted_pe"),
            "weighted_pb": valuation.get("weighted_pb"),
            "weighted_roe": valuation.get("weighted_roe"),
            "peg": valuation.get("peg"),
            "val_pct": valuation.get("weighted_val_pct"),
        },
        holdings=holdings,
        holdings_history=holdings_history or [],
        valuation=valuation,
        trend=trend,
        manager=manager,
        match_analysis=match_analysis,
        data_quality_notes=data_quality_notes,
        evidence_sources=sources,
        evidence_bundle=bundle,
    )
