"""投资备忘录：从认知分析结果生成结构化投资备忘录"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class MemoSection:
    """备忘录段落"""
    section_id: str
    title: str
    thesis: str              # 段落核心论点（1-2句）
    key_figures: list[dict]  # [{label, value, unit, source}]
    content: str             # 详细内容（100-200字）

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "thesis": self.thesis,
            "key_figures": self.key_figures,
            "content": self.content,
        }


@dataclass
class InvestmentMemo:
    """投资备忘录"""
    direction: str
    generated_at: str
    decision: str            # "attractive" | "watchlist" | "avoid" | "needs_more_evidence"
    sections: list[MemoSection]
    scenario: dict           # bear/base/bull 场景
    financial_snapshot: dict # 关键财务快照

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "generated_at": self.generated_at,
            "decision": self.decision,
            "sections": [s.to_dict() for s in self.sections],
            "scenario": self.scenario,
            "financial_snapshot": self.financial_snapshot,
        }


# 固定大纲（阅读顺序）
MEMO_OUTLINE = [
    ("current_setup", "当前状况与差异视角"),
    ("business_quality", "商业模式与质量"),
    ("industry_growth", "行业与增长"),
    ("financial_quality", "财务质量"),
    ("valuation", "估值"),
    ("risks", "风险、空头论点与终止条件"),
    ("decision_summary", "决策摘要"),
]


def _extract_best_link_name(expectation_gap: dict[str, Any]) -> str:
    """从 expectation_gap 中提取最优环节名称。

    step3 的 best_link 是完整的环节 dict（含 link_name），需要取出字符串。
    """
    raw = expectation_gap.get("best_link")
    if isinstance(raw, dict):
        return raw.get("link_name", "")
    if raw:
        return str(raw)
    return ""


def generate_memo_from_cognition(
    direction: str,
    judgment: dict[str, Any],
    chain_analysis: list[dict[str, Any]],
    expectation_gap: dict[str, Any],
    fund_matches: list[dict[str, Any]],
    validation: dict[str, Any],
    portfolio: dict[str, Any],
    gated_out: list[dict[str, Any]],
) -> InvestmentMemo:
    """
    从认知分析结果生成投资备忘录。

    生成顺序（非阅读顺序）：business_quality -> industry_growth -> financial_quality
    -> risks -> valuation -> current_setup -> decision_summary
    """
    sections: list[MemoSection] = []

    top_fund = fund_matches[0] if fund_matches else {}
    top_valuation = top_fund.get("valuation", {})
    verdict = validation.get("verdict", "")
    supporting = validation.get("supporting_evidence", [])
    opposing = validation.get("opposing_evidence", [])

    # 1. 商业模式与质量
    belief = judgment.get("belief", "")
    level = judgment.get("level", "")
    key_metric = judgment.get("key_metric", "")

    sections.append(MemoSection(
        section_id="business_quality",
        title="商业模式与质量",
        thesis=f"投资信念：{belief}。认知层次：{level}，核心指标：{key_metric}。",
        key_figures=[
            {"label": "认知层次", "value": level, "unit": "", "source": "judgment"},
            {"label": "核心指标", "value": key_metric, "unit": "", "source": "judgment"},
            {"label": "估值容忍度", "value": judgment.get("valuation_tolerance", ""), "unit": "", "source": "judgment"},
        ],
        content=f"本方向的投资逻辑基于\u201c{belief}\u201d。认知层次为{level}，"
                f"意味着{'从生产力变革角度评估' if level == 'productivity' else '从市场错杀角度评估' if level == 'market' else '从产业结构角度评估'}。"
                f"核心估值指标为{key_metric}，估值容忍度{judgment.get('valuation_tolerance', '')}。"
                f"产业链共{len(chain_analysis)}个环节，其中正向预期差{len(expectation_gap.get('positive', []))}个。"
    ))

    # 2. 行业与增长
    positive_links = expectation_gap.get("positive", [])
    negative_links = expectation_gap.get("negative", [])
    best_link = _extract_best_link_name(expectation_gap)

    sections.append(MemoSection(
        section_id="industry_growth",
        title="行业与增长",
        thesis=f"最优环节：{best_link}。正向{len(positive_links)}个，负向{len(negative_links)}个。",
        key_figures=[
            {"label": "产业链环节数", "value": len(chain_analysis), "unit": "个", "source": "chain_analysis"},
            {"label": "正向预期差", "value": len(positive_links), "unit": "个", "source": "expectation_gap"},
            {"label": "负向预期差", "value": len(negative_links), "unit": "个", "source": "expectation_gap"},
            {"label": "最优环节", "value": best_link, "unit": "", "source": "expectation_gap"},
        ],
        content=f"产业链拆解后共{len(chain_analysis)}个环节。"
                f"其中{len(positive_links)}个环节呈正向预期差，{len(negative_links)}个呈负向。"
                f"预期差最大的环节为\u201c{best_link}\u201d。"
                + (f"主要正向环节：" + "、".join(l.get("link_name", "") for l in positive_links[:3]) + "。" if positive_links else "")
                + (f"主要负向环节：" + "、".join(l.get("link_name", "") for l in negative_links[:3]) + "。" if negative_links else "")
    ))

    # 3. 财务质量
    # 注意：valuation 中 weighted_roe 已是百分数制（如 15.2 表示 15.2%），无需再乘 100
    pe = top_valuation.get("weighted_pe")
    roe = top_valuation.get("weighted_roe")
    pb = top_valuation.get("weighted_pb")
    peg = top_valuation.get("peg")

    sections.append(MemoSection(
        section_id="financial_quality",
        title="财务质量",
        thesis=f"加权PE={pe or 'N/A'}，ROE={roe or 'N/A'}%，PEG={peg or 'N/A'}。",
        key_figures=[
            {"label": "加权PE", "value": pe, "unit": "", "source": "valuation"},
            {"label": "加权ROE", "value": roe, "unit": "%", "source": "valuation"},
            {"label": "加权PB", "value": pb, "unit": "", "source": "valuation"},
            {"label": "PEG", "value": peg, "unit": "", "source": "valuation"},
        ],
        content=f"顶部匹配基金{top_fund.get('fund_code', '')}({top_fund.get('fund_name', '')})"
                f"的加权估值指标：PE={pe or 'N/A'}，PB={pb or 'N/A'}，ROE={f'{roe:.1f}%' if roe else 'N/A'}，PEG={peg or 'N/A'}。"
                f"匹配度{top_fund.get('match_pct', 0)}%。"
    ))

    # 4. 风险、空头论点与终止条件
    hard_limits = judgment.get("hard_limits", {})
    kill_criteria = []
    for k, v in hard_limits.items():
        kill_criteria.append(f"{k}={v}")

    sections.append(MemoSection(
        section_id="risks",
        title="风险、空头论点与终止条件",
        thesis=f"反对证据{len(opposing)}条。终止条件：{'; '.join(kill_criteria[:3]) if kill_criteria else '无'}。",
        key_figures=[
            {"label": "反对证据", "value": len(opposing), "unit": "条", "source": "validation"},
            {"label": "支持证据", "value": len(supporting), "unit": "条", "source": "validation"},
            {"label": "门禁拦截", "value": len(gated_out), "unit": "只", "source": "gated_out"},
        ],
        content=f"认知验证裁决：{verdict}。"
                f"支持证据{len(supporting)}条，反对证据{len(opposing)}条。"
                f"被估值门禁拦截的基金{len(gated_out)}只。"
                f"终止条件：{'; '.join(kill_criteria) if kill_criteria else '无硬性终止条件'}。"
                + (f"主要风险：" + opposing[0].get("claim", str(opposing[0]))[:80] if opposing else "")
    ))

    # 5. 估值
    # 注意：weighted_val_pct 已是百分数制（如 65.0 表示 65%），无需再乘 100
    val_pct = top_valuation.get("weighted_val_pct")
    price_in = top_valuation.get("price_in_years")

    # 确定性估值锚：weighted_growth 已是百分数制，转为小数后参与计算
    growth_pct = top_valuation.get("weighted_growth")
    growth_rate = (growth_pct / 100.0) if growth_pct else 0.1
    justified_pe = min(35, max(8, 10 + growth_rate * 80))

    sections.append(MemoSection(
        section_id="valuation",
        title="估值",
        thesis=f"估值分位{val_pct or 'N/A'}%，合理PE约{justified_pe:.0f}。",
        key_figures=[
            {"label": "估值分位", "value": val_pct, "unit": "%", "source": "valuation"},
            {"label": "当前PE", "value": pe, "unit": "", "source": "valuation"},
            {"label": "合理PE(估)", "value": round(justified_pe, 1), "unit": "", "source": "deterministic_anchor"},
            {"label": "Price-in年限", "value": price_in, "unit": "年", "source": "valuation"},
        ],
        content=f"顶部基金估值分位{f'{val_pct:.0f}%' if val_pct else 'N/A'}，"
                f"当前PE={pe or 'N/A'}，基于增速{f'{growth_rate*100:.0f}%' if growth_rate else 'N/A'}"
                f"的合理PE约{justified_pe:.0f}。"
                f"{'估值偏高' if val_pct and val_pct > 70 else '估值适中' if val_pct and val_pct > 40 else '估值偏低' if val_pct else '估值数据不足'}。"
    ))

    # 6. 当前状况与差异视角
    conviction = portfolio.get("suggested_weight", 0)

    sections.append(MemoSection(
        section_id="current_setup",
        title="当前状况与差异视角",
        thesis=f"建议仓位{conviction}%。匹配基金{len(fund_matches)}只。",
        key_figures=[
            {"label": "匹配基金数", "value": len(fund_matches), "unit": "只", "source": "fund_matches"},
            {"label": "建议仓位", "value": conviction, "unit": "%", "source": "portfolio"},
            {"label": "优化方法", "value": portfolio.get("optimization_method", "heuristic"), "unit": "", "source": "portfolio"},
        ],
        content=f"当前分析匹配到{len(fund_matches)}只基金，"
                f"门禁拦截{len(gated_out)}只。"
                f"组合建议仓位{conviction}%，"
                f"优化方法：{portfolio.get('optimization_method', 'heuristic')}。"
                f"{'认知验证通过，可继续研究。' if '有效' in verdict else '认知验证存疑，需进一步观察。'}"
    ))

    # 7. 决策摘要
    if not fund_matches:
        decision = "needs_more_evidence"
        decision_text = "证据不足，需补充数据"
    elif "有效" in verdict and conviction > 0:
        # val_pct 已是百分数制，60 表示 60%
        decision = "attractive" if val_pct and val_pct < 60 else "watchlist"
        decision_text = "有吸引力" if decision == "attractive" else "列入观察名单"
    elif "存疑" in verdict:
        decision = "watchlist"
        decision_text = "列入观察名单"
    else:
        decision = "avoid"
        decision_text = "暂不参与"

    sections.append(MemoSection(
        section_id="decision_summary",
        title="决策摘要",
        thesis=f"决策：{decision_text}。",
        key_figures=[
            {"label": "决策", "value": decision_text, "unit": "", "source": "deterministic"},
            {"label": "验证裁决", "value": verdict, "unit": "", "source": "validation"},
            {"label": "Gate Score", "value": "", "unit": "", "source": "ic_review"},
        ],
        content=f"综合产业链分析、估值门禁、认知验证和组合构建，"
                f"本方向决策为\u201c{decision_text}\u201d。"
                f"认知验证裁决：{verdict}。"
                f"匹配基金{len(fund_matches)}只，建议仓位{conviction}%。"
    ))

    # 场景分析（确定性计算）
    scenario = {
        "bear": {"probability": 20, "return": -15, "thesis": "预期差未兑现，估值回归"},
        "base": {"probability": 50, "return": 10, "thesis": "产业链部分环节兑现，组合温和增长"},
        "bull": {"probability": 30, "return": 30, "thesis": "核心假设完全兑现，估值扩张"},
    }

    # 财务快照
    financial_snapshot = {
        "top_fund_code": top_fund.get("fund_code"),
        "top_fund_name": top_fund.get("fund_name"),
        "match_pct": top_fund.get("match_pct"),
        "weighted_pe": pe,
        "weighted_roe": roe,
        "weighted_pb": pb,
        "peg": peg,
        "val_pct": val_pct,
    }

    # 按阅读顺序排列
    section_map = {s.section_id: s for s in sections}
    ordered_sections = [section_map[sid] for sid, _ in MEMO_OUTLINE if sid in section_map]

    return InvestmentMemo(
        direction=direction,
        generated_at=date.today().isoformat(),
        decision=decision,
        sections=ordered_sections,
        scenario=scenario,
        financial_snapshot=financial_snapshot,
    )
