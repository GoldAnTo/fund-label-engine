"""认知验证引擎：对认知提供正反证据、price-in 估算、综合判断。

不替代投资者判断，只提供证据。会议说"信息矛盾时靠相信"。

证据溯源机制（借鉴 zhengxi-views）：
每条证据都是结构化对象，包含 claim/source/source_type/raw_data/context，
用户可以追溯到原始数据来源，不杜撰、不外推。
"""
from __future__ import annotations

from typing import Any

from app.cognition.valuation_gate import estimate_price_in_years


def _make_evidence(
    claim: str,
    source: str,
    source_type: str,
    raw_data: dict[str, Any] | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    """构建一条可溯源的证据。

    Args:
        claim: 人类可读的判断描述（如"利润增速35%，基本面强劲"）
        source: 数据来源描述（如"2025Q4季报"）
        source_type: 来源类型 fund_report/market_data/estimate/chain_analysis/trend
        raw_data: 原始数据值（如 {"profit_growth": 35.2}）
        context: 补充说明（如"利润增速>30%属于高增长"）
    """
    evidence: dict[str, Any] = {
        "claim": claim,
        "source": source,
        "source_type": source_type,
    }
    if raw_data is not None:
        evidence["raw_data"] = raw_data
    if context is not None:
        evidence["context"] = context
    return evidence


def validate_cognition(
    link_analysis: list[dict[str, Any]],
    fund_matches: list[dict[str, Any]],
    judgment: dict[str, Any],
    fund_managers: dict[str, dict[str, Any]] | None = None,
    financial_depth: dict[str, dict[str, Any]] | None = None,
    northbound_trend: dict[str, float] | None = None,
    dragon_tiger: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """对认知提供多维证据框架。

    link_analysis: 产业链各环节的预期差分析结果
    fund_matches: 匹配基金的估值数据
    judgment: 认知判断模板（belief/level/valuation_tolerance 等）
    fund_managers: 基金经理数据 {"000001": {"name":..., "tenure_days":..., "return_pct":...}}
    financial_depth: 三大报表关键指标 {"600519": {"revenue":..., "gross_margin":..., ...}}
    northbound_trend: 北向资金净流入 {"600519": 5.2}
    dragon_tiger: 龙虎榜上榜 {"600519": {"date":..., "net_buy":..., "reason":...}}

    返回的证据均为结构化对象，含 claim/source/source_type/raw_data/context。
    """
    supporting: list[dict[str, Any]] = []
    opposing: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # === 1. 基本面证据（从产业链环节提取） ===
    positive_links = [lk for lk in link_analysis if lk.get("expectation_gap") == "positive"]
    negative_links = [lk for lk in link_analysis if lk.get("expectation_gap") == "negative"]

    if positive_links:
        names = "、".join(lk["link_name"] for lk in positive_links)
        supporting.append(_make_evidence(
            claim=f"正预期差环节：{names}（估值与增速匹配，值得配置）",
            source="产业链预期差分析",
            source_type="chain_analysis",
            raw_data={
                "positive_links": [lk["link_name"] for lk in positive_links],
                "expectation_gaps": [lk.get("expectation_gap") for lk in positive_links],
            },
            context="正预期差=估值低于增速所隐含的合理水平",
        ))

    if negative_links:
        names = "、".join(lk["link_name"] for lk in negative_links)
        opposing.append(_make_evidence(
            claim=f"负预期差环节：{names}（估值已透支增长，暂不配置）",
            source="产业链预期差分析",
            source_type="chain_analysis",
            raw_data={
                "negative_links": [lk["link_name"] for lk in negative_links],
                "expectation_gaps": [lk.get("expectation_gap") for lk in negative_links],
            },
            context="负预期差=估值已price in过多增长",
        ))

    # 从环节中提取基本面数据
    for lk in link_analysis:
        link_name = lk.get("link_name", "?")
        growth = lk.get("growth_pct")
        if growth and growth > 30:
            supporting.append(_make_evidence(
                claim=f"{link_name}利润增速 {growth:.0f}%，基本面强劲",
                source=f"{link_name}环节加权利润增速",
                source_type="chain_analysis",
                raw_data={"growth_pct": round(growth, 1)},
                context="利润增速>30%属于高增长",
            ))
        elif growth and growth > 15:
            supporting.append(_make_evidence(
                claim=f"{link_name}利润增速 {growth:.0f}%，基本面稳健",
                source=f"{link_name}环节加权利润增速",
                source_type="chain_analysis",
                raw_data={"growth_pct": round(growth, 1)},
                context="利润增速15%-30%属于稳健增长",
            ))
        elif growth and growth < 10:
            opposing.append(_make_evidence(
                claim=f"{link_name}利润增速仅 {growth:.0f}%，增长乏力",
                source=f"{link_name}环节加权利润增速",
                source_type="chain_analysis",
                raw_data={"growth_pct": round(growth, 1)},
                context="利润增速<10%增长乏力",
            ))

        roe = lk.get("roe")
        if roe and roe > 15:
            supporting.append(_make_evidence(
                claim=f"{link_name}ROE {roe:.1f}%，盈利能力强",
                source=f"{link_name}环节加权ROE",
                source_type="chain_analysis",
                raw_data={"roe": round(roe, 1)},
                context="ROE>15%属于高盈利质量",
            ))

        peg = lk.get("peg")
        if peg and peg < 1:
            supporting.append(_make_evidence(
                claim=f"{link_name}PEG {peg:.2f}，增速能支撑估值",
                source=f"{link_name}环节PEG",
                source_type="chain_analysis",
                raw_data={"peg": round(peg, 2)},
                context="PEG<1表示增速高于估值，偏低估",
            ))
        elif peg and peg > 2:
            opposing.append(_make_evidence(
                claim=f"{link_name}PEG {peg:.2f}，已price in过多增长",
                source=f"{link_name}环节PEG",
                source_type="chain_analysis",
                raw_data={"peg": round(peg, 2)},
                context="PEG>2表示估值远超增速，偏高估",
            ))

    # === 2. 估值定价证据（从基金匹配结果提取） ===
    if fund_matches:
        top_fund = fund_matches[0]
        val = top_fund.get("valuation", {})
        fund_code = top_fund.get("fund_code", "?")

        val_pct = val.get("weighted_val_pct")
        if val_pct and val_pct > 85:
            opposing.append(_make_evidence(
                claim=f"TOP基金({fund_code})估值分位 {val_pct:.0f}%，处于历史高位",
                source=f"基金{fund_code}加权PE历史分位",
                source_type="market_data",
                raw_data={"weighted_val_pct": round(val_pct, 1)},
                context="估值分位>85%处于近5年高位",
            ))
        elif val_pct and val_pct < 30:
            supporting.append(_make_evidence(
                claim=f"TOP基金({fund_code})估值分位 {val_pct:.0f}%，处于历史低位",
                source=f"基金{fund_code}加权PE历史分位",
                source_type="market_data",
                raw_data={"weighted_val_pct": round(val_pct, 1)},
                context="估值分位<30%处于近5年低位",
            ))

        pe = val.get("weighted_pe")
        growth = val.get("weighted_growth")
        price_in = val.get("price_in_years")
        if price_in is not None and price_in > 0:
            if price_in > 3:
                opposing.append(_make_evidence(
                    claim=f"当前估值已price in约 {price_in:.1f} 年增长（PE {pe:.0f}，增速 {growth:.0f}%），赔率不佳",
                    source=f"基金{fund_code} PE/增速推算",
                    source_type="estimate",
                    raw_data={"price_in_years": round(price_in, 1), "pe": pe, "growth": growth},
                    context="price-in>3年意味着当前股价已包含3年以上增长预期，线性外推风险高",
                ))
            elif price_in > 1.5:
                warnings.append(_make_evidence(
                    claim=f"当前估值已price in约 {price_in:.1f} 年增长，需关注增速持续性",
                    source=f"基金{fund_code} PE/增速推算",
                    source_type="estimate",
                    raw_data={"price_in_years": round(price_in, 1), "pe": pe, "growth": growth},
                    context="price-in 1.5-3年处于灰色地带，需判断增速能否持续",
                ))
            else:
                supporting.append(_make_evidence(
                    claim=f"当前估值仅price in约 {price_in:.1f} 年增长，安全边际尚可",
                    source=f"基金{fund_code} PE/增速推算",
                    source_type="estimate",
                    raw_data={"price_in_years": round(price_in, 1), "pe": pe, "growth": growth},
                    context="price-in<1.5年安全边际较好",
                ))

        # 横截面估值对比
        industry_median = val.get("industry_pe_median")
        premium = val.get("pe_premium_pct")
        cross_judge = val.get("cross_sectional_judge")
        if industry_median and premium is not None:
            source_claim = f"基金{fund_code}加权PE vs 同行业PE中位数"
            raw = {
                "fund_pe": pe,
                "industry_pe_median": industry_median,
                "pe_premium_pct": premium,
            }
            if premium > 50:
                opposing.append(_make_evidence(
                    claim=f"TOP基金PE高于同行 {premium:.0f}%（{cross_judge}）",
                    source=source_claim,
                    source_type="market_data",
                    raw_data=raw,
                    context="横截面对比：当前PE显著高于同行业中位数",
                ))
            elif premium < -20:
                supporting.append(_make_evidence(
                    claim=f"TOP基金PE低于同行 {abs(premium):.0f}%（{cross_judge}）",
                    source=source_claim,
                    source_type="market_data",
                    raw_data=raw,
                    context="横截面对比：当前PE低于同行业中位数，可能被低估",
                ))

    # === 3. 持仓集中度证据 ===
    if fund_matches and len(fund_matches) >= 2:
        match_pcts = [f.get("match_pct", 0) for f in fund_matches[:3]]
        if match_pcts and max(match_pcts) > 50:
            warnings.append(_make_evidence(
                claim=f"TOP基金匹配度 {max(match_pcts):.0f}%，持仓高度集中于该认知主题",
                source="基金持仓匹配度",
                source_type="chain_analysis",
                raw_data={"max_match_pct": round(max(match_pcts), 1)},
                context="匹配度>50%意味着基金持仓高度集中在该主题，行业风险集中",
            ))

    # === 4. 持仓趋势证据 ===
    for fund in fund_matches[:3]:
        trend = fund.get("trend", {}).get("trend", "")
        fund_code = fund.get("fund_code", "?")
        trend_pct = fund.get("trend", {}).get("change_pct")
        if trend == "decreasing":
            warnings.append(_make_evidence(
                claim=f"基金 {fund_code} 持仓趋势在减仓该主题",
                source=f"基金{fund_code}近2期持仓对比",
                source_type="trend",
                raw_data={"trend": trend, "change_pct": trend_pct},
                context="基金经理在减仓该主题，可能不看好短期表现",
            ))
        elif trend == "increasing":
            supporting.append(_make_evidence(
                claim=f"基金 {fund_code} 持仓趋势在加仓该主题",
                source=f"基金{fund_code}近2期持仓对比",
                source_type="trend",
                raw_data={"trend": trend, "change_pct": trend_pct},
                context="基金经理在加仓该主题，可能看好未来表现",
            ))

    # === 5. 基金经理证据 ===
    if fund_managers:
        for fund in fund_matches[:3]:
            fc = fund.get("fund_code", "?")
            mgr = fund_managers.get(fc)
            if not mgr:
                continue

            mgr_name = mgr.get("name", "?")
            tenure_days = mgr.get("tenure_days")
            return_pct = mgr.get("return_pct")

            # 任职年限
            if tenure_days and tenure_days > 1825:  # >5年
                years = tenure_days / 365
                supporting.append(_make_evidence(
                    claim=f"基金{fc}经理{mgr_name}任职{years:.1f}年，经验丰富",
                    source=f"基金{fc}基金经理任职信息",
                    source_type="fund_report",
                    raw_data={"tenure_days": tenure_days, "manager": mgr_name},
                    context="任职>5年说明经理经历过完整牛熊周期，策略稳定性更高",
                ))
            elif tenure_days is not None and tenure_days < 365:  # <1年
                warnings.append(_make_evidence(
                    claim=f"基金{fc}经理{mgr_name}任职不足1年，需观察",
                    source=f"基金{fc}基金经理任职信息",
                    source_type="fund_report",
                    raw_data={"tenure_days": tenure_days, "manager": mgr_name},
                    context="刚上任的经理可能调整持仓方向，历史数据参考价值降低",
                ))

            # 任职回报
            if return_pct is not None and return_pct > 50:
                supporting.append(_make_evidence(
                    claim=f"基金{fc}经理{mgr_name}任职回报{return_pct:.0f}%，业绩优秀",
                    source=f"基金{fc}经理任职回报",
                    source_type="fund_report",
                    raw_data={"return_pct": round(return_pct, 1), "manager": mgr_name},
                    context="任职回报>50%说明经理在该基金上取得了显著超额收益",
                ))
            elif return_pct is not None and return_pct < 0:
                opposing.append(_make_evidence(
                    claim=f"基金{fc}经理{mgr_name}任职回报{return_pct:.0f}%，业绩不佳",
                    source=f"基金{fc}经理任职回报",
                    source_type="fund_report",
                    raw_data={"return_pct": round(return_pct, 1), "manager": mgr_name},
                    context="任职回报为负说明经理管理期间基金亏损",
                ))

    # === 6. 财务深度证据（三大报表） ===
    if financial_depth and fund_matches:
        # 收集TOP基金持仓股票的财务数据
        checked_codes: set[str] = set()
        for fund in fund_matches[:3]:
            for h in fund.get("holdings", []) or []:
                code = h.get("stock_code", "")
                if code in checked_codes:
                    continue
                checked_codes.add(code)
                fin = financial_depth.get(code)
                if not fin:
                    continue

                stock_name = h.get("stock_name", code)
                # 毛利率
                gm = fin.get("gross_margin")
                if gm and gm > 50:
                    supporting.append(_make_evidence(
                        claim=f"{stock_name}毛利率 {gm:.0f}%，盈利质量高",
                        source=f"{stock_name}利润表",
                        source_type="market_data",
                        raw_data={"gross_margin": round(gm, 1)},
                        context="毛利率>50%说明产品定价权强",
                    ))
                elif gm and gm < 20:
                    opposing.append(_make_evidence(
                        claim=f"{stock_name}毛利率仅 {gm:.0f}%，盈利质量弱",
                        source=f"{stock_name}利润表",
                        source_type="market_data",
                        raw_data={"gross_margin": round(gm, 1)},
                        context="毛利率<20%说明竞争激烈、定价权弱",
                    ))

                # 自由现金流
                fcf = fin.get("free_cashflow")
                if fcf is not None and fcf > 0:
                    supporting.append(_make_evidence(
                        claim=f"{stock_name}自由现金流为正（{fcf:.1f}亿），造血能力强",
                        source=f"{stock_name}现金流量表",
                        source_type="market_data",
                        raw_data={"free_cashflow": round(fcf, 1)},
                        context="正自由现金流说明公司能自我造血，不依赖外部融资",
                    ))
                elif fcf is not None and fcf < 0:
                    warnings.append(_make_evidence(
                        claim=f"{stock_name}自由现金流为负（{fcf:.1f}亿），需关注",
                        source=f"{stock_name}现金流量表",
                        source_type="market_data",
                        raw_data={"free_cashflow": round(fcf, 1)},
                        context="负自由现金流可能是扩张期投入，也可能是经营恶化",
                    ))

                # 资产负债率
                dr = fin.get("debt_ratio")
                if dr and dr > 70:
                    opposing.append(_make_evidence(
                        claim=f"{stock_name}资产负债率 {dr:.0f}%，财务风险偏高",
                        source=f"{stock_name}资产负债表",
                        source_type="market_data",
                        raw_data={"debt_ratio": round(dr, 1)},
                        context="资产负债率>70%说明杠杆过高",
                    ))

    # === 7. 北向资金证据 ===
    if northbound_trend and fund_matches:
        # 收集TOP基金持仓股票的北向资金
        nb_inflow: list[str] = []
        nb_outflow: list[str] = []
        checked_codes_nb: set[str] = set()
        for fund in fund_matches[:3]:
            for h in fund.get("holdings", []) or []:
                code = h.get("stock_code", "")
                if code in checked_codes_nb:
                    continue
                checked_codes_nb.add(code)
                nb = northbound_trend.get(code)
                if nb is None:
                    continue
                stock_name = h.get("stock_name", code)
                if nb > 5:
                    nb_inflow.append(f"{stock_name}({nb:+.1f}亿)")
                elif nb < -5:
                    nb_outflow.append(f"{stock_name}({nb:+.1f}亿)")

        if nb_inflow:
            supporting.append(_make_evidence(
                claim=f"北向资金近期净流入：{', '.join(nb_inflow[:3])}",
                source="北向资金近30天个股净流入",
                source_type="market_data",
                raw_data={"inflow_stocks": nb_inflow[:5]},
                context="北向资金被视为外资风向标，净流入说明外资看好",
            ))
        if nb_outflow:
            opposing.append(_make_evidence(
                claim=f"北向资金近期净流出：{', '.join(nb_outflow[:3])}",
                source="北向资金近30天个股净流出",
                source_type="market_data",
                raw_data={"outflow_stocks": nb_outflow[:5]},
                context="北向资金净流出说明外资在减仓",
            ))

    # === 8. 龙虎榜证据 ===
    if dragon_tiger and fund_matches:
        # 收集TOP基金持仓股票的龙虎榜上榜情况
        dt_stocks: list[str] = []
        checked_codes_dt: set[str] = set()
        for fund in fund_matches[:3]:
            for h in fund.get("holdings", []) or []:
                code = h.get("stock_code", "")
                if code in checked_codes_dt:
                    continue
                checked_codes_dt.add(code)
                dt = dragon_tiger.get(code)
                if not dt:
                    continue
                stock_name = h.get("stock_name", code)
                net_buy = dt.get("net_buy")
                hit = dt.get("hit_count", 0)
                reason = dt.get("reason", "")
                if net_buy and net_buy > 0:
                    dt_stocks.append(f"{stock_name}(净买入{net_buy:.1f}亿)")
                elif net_buy and net_buy < 0:
                    dt_stocks.append(f"{stock_name}(净卖出{abs(net_buy):.1f}亿)")

        if dt_stocks:
            warnings.append(_make_evidence(
                claim=f"持仓股票近期上龙虎榜：{', '.join(dt_stocks[:3])}",
                source="龙虎榜近30天数据",
                source_type="market_data",
                raw_data={"dragon_tiger_stocks": dt_stocks[:5]},
                context="龙虎榜上榜说明游资活跃，短期波动可能加大",
            ))

    # === 9. 综合判断 ===
    s_count = len(supporting)
    o_count = len(opposing)

    if s_count > o_count + 1:
        verdict = "认知有效"
        verdict_detail = "基本面支撑充分，估值合理，建议配置"
    elif s_count > o_count:
        verdict = "认知基本有效"
        verdict_detail = "基本面有支撑，但存在需关注的风险点"
    elif s_count == o_count:
        verdict = "认知有分歧"
        verdict_detail = "正反证据相当，信息矛盾时靠投资者自身判断"
    else:
        verdict = "认知存疑"
        verdict_detail = "反面证据较多，建议谨慎或等待估值回落"

    # 估值容忍度调整
    val_tol = judgment.get("valuation_tolerance", "medium")
    if val_tol == "high" and o_count > 0 and o_count <= s_count:
        verdict = "认知有效"
        verdict_detail = "高估值容忍度下，基本面方向比估值水平更重要"
    elif val_tol == "low":
        for e in opposing:
            if "高位" in e.get("claim", "") or "price in" in e.get("claim", "").lower():
                verdict = "认知存疑"
                verdict_detail = "低估值容忍度下，估值偏高是硬约束"
                break

    debate = _build_debate(supporting, opposing, warnings)

    return {
        "supporting_evidence": supporting,
        "opposing_evidence": opposing,
        "warnings": warnings,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "evidence_counts": {"supporting": s_count, "opposing": o_count},
        "reasoning_chain": _build_reasoning_chain(
            judgment, supporting, opposing, warnings, verdict,
        ),
        "debate": debate,
        "cognition_feedback": _build_cognition_feedback(
            judgment, verdict, verdict_detail, opposing, warnings,
        ),
    }


def _build_debate(
    supporting: list[dict[str, Any]],
    opposing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """构建多空辩论（借鉴 TradingAgents 的 Bull/Bear 对抗机制）。

    不是静态列举正反证据，而是让 Bear 反驳 Bull 的每个论点，
    Bull 再回应 Bear 的反驳，形成动态对抗。
    """
    # 按source_type索引反面证据，用于匹配
    oppose_by_type: dict[str, list[dict[str, Any]]] = {}
    for e in opposing:
        st = e.get("source_type", "")
        oppose_by_type.setdefault(st, []).append(e)

    # 按关键词匹配正反证据
    def _find_rebuttal(bull_ev: dict[str, Any]) -> dict[str, Any] | None:
        """为Bull论点找Bear反驳。"""
        claim = bull_ev.get("claim", "")
        raw = bull_ev.get("raw_data", {})

        # 增速高 -> 反驳：PE已price in
        if "growth_pct" in raw and raw["growth_pct"] > 30:
            for e in opposing:
                if "price in" in e.get("claim", "").lower():
                    return e
            # 没有price in证据，用估值分位反驳
            for e in opposing:
                if "估值分位" in e.get("claim", "") or "高位" in e.get("claim", ""):
                    return e

        # ROE高 -> 反驳：估值分位高
        if "roe" in raw and raw["roe"] > 15:
            for e in opposing:
                if "估值" in e.get("claim", "") or "price in" in e.get("claim", "").lower():
                    return e

        # PEG低 -> 反驳：持仓趋势减仓
        if "peg" in raw and raw["peg"] < 1:
            for e in warnings:
                if "减仓" in e.get("claim", ""):
                    return e

        # 正预期差 -> 反驳：负预期差
        if "正预期差" in claim:
            for e in opposing:
                if "负预期差" in e.get("claim", ""):
                    return e

        # 估值低 -> 无反驳（利好很难反驳）
        if "估值分位" in claim and "低位" in claim:
            return None

        # 通用：同source_type的反对证据
        st = bull_ev.get("source_type", "")
        if st in oppose_by_type and oppose_by_type[st]:
            return oppose_by_type[st][0]

        return None

    def _find_response(bear_ev: dict[str, Any]) -> dict[str, Any] | None:
        """为Bear反驳找Bull回应。"""
        claim = bear_ev.get("claim", "")

        # PE已price in -> Bull回应：增速可能超预期
        if "price in" in claim.lower():
            for e in supporting:
                if "增速" in e.get("claim", "") and "强劲" in e.get("claim", ""):
                    return e

        # 估值高位 -> Bull回应：ROE高/基本面强
        if "高位" in claim or "估值分位" in claim:
            for e in supporting:
                if "ROE" in e.get("claim", ""):
                    return e

        # 减仓 -> Bull回应：正预期差
        if "减仓" in claim:
            for e in supporting:
                if "正预期差" in e.get("claim", ""):
                    return e

        return None

    debate: list[dict[str, Any]] = []
    for bull_ev in supporting:
        rebuttal = _find_rebuttal(bull_ev)
        if rebuttal:
            response = _find_response(rebuttal)
            debate.append({
                "round": len(debate) + 1,
                "bull_argument": bull_ev,
                "bear_rebuttal": rebuttal,
                "bull_response": response,
            })
        else:
            # 无反驳的Bull论点（利好无争议）
            debate.append({
                "round": len(debate) + 1,
                "bull_argument": bull_ev,
                "bear_rebuttal": None,
                "bull_response": None,
            })

    return debate


def _build_cognition_feedback(
    judgment: dict[str, Any],
    verdict: str,
    verdict_detail: str,
    opposing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建认知反馈闭环（借鉴 Vibe-Trading 的结论回写机制）。

    验证完成后，把结论回写到认知输入，给出修正建议。
    形成 认知->验证->修正认知 的闭环。
    """
    belief = judgment.get("belief", "")
    suggestions: list[str] = []

    # 根据反面证据生成修正建议
    for e in opposing:
        claim = e.get("claim", "")
        if "price in" in claim.lower():
            suggestions.append("当前估值已price in较多增长，建议降低仓位或分批建仓")
        elif "高位" in claim:
            suggestions.append("估值处于历史高位，建议等待回调后配置")
        elif "增长乏力" in claim:
            suggestions.append("部分环节增长乏力，建议聚焦高确定性环节")
        elif "负预期差" in claim:
            suggestions.append("存在负预期差环节，建议回避估值透支的细分方向")

    for e in warnings:
        claim = e.get("claim", "")
        if "减仓" in claim:
            suggestions.append("基金经理在减仓该主题，建议关注持仓变化趋势")
        elif "高度集中" in claim:
            suggestions.append("持仓高度集中，建议搭配防守仓位降低行业风险")

    # 根据verdict生成总体建议
    if verdict == "认知存疑":
        suggestions.insert(0, "验证结果存疑，建议暂缓配置或仅用小仓位试探")
    elif verdict == "认知有分歧":
        suggestions.insert(0, "正反证据相当，建议根据自身风险偏好决定是否配置")
    elif verdict == "认知基本有效":
        suggestions.append("认知基本有效但存在风险点，建议控制仓位并持续跟踪")

    # 修正后的认知描述
    if verdict == "认知有效":
        adjusted_belief = belief
    elif verdict == "认知存疑":
        adjusted_belief = f"{belief}（但当前估值偏高，需谨慎）"
    else:
        adjusted_belief = f"{belief}（需关注风险点，控制仓位）"

    return {
        "original_belief": belief,
        "validation_verdict": verdict,
        "correction_suggestions": suggestions[:5],  # 最多5条
        "adjusted_belief": adjusted_belief,
    }


def _build_reasoning_chain(
    judgment: dict[str, Any],
    supporting: list[dict[str, Any]],
    opposing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    verdict: str,
) -> list[dict[str, str]]:
    """构建可追溯的推理链：从认知输入到最终判断的完整路径。

    每个节点包含 step(步骤名)/description(描述)/evidence_ref(关联证据索引)。
    """
    chain: list[dict[str, str]] = []

    # 节点1: 认知输入
    belief = judgment.get("belief", "")
    chain.append({
        "step": "认知输入",
        "description": belief,
        "evidence_ref": "",
    })

    # 节点2: 基本面验证
    fundamental_evidence = [
        e for e in supporting + opposing
        if e.get("source_type") == "chain_analysis"
    ]
    if fundamental_evidence:
        claims = "；".join(e["claim"] for e in fundamental_evidence[:3])
        chain.append({
            "step": "基本面验证",
            "description": claims,
            "evidence_ref": f"supporting+opposing (chain_analysis, {len(fundamental_evidence)}条)",
        })

    # 节点3: 估值定价验证
    valuation_evidence = [
        e for e in supporting + opposing
        if e.get("source_type") in ("market_data", "estimate")
    ]
    if valuation_evidence:
        claims = "；".join(e["claim"] for e in valuation_evidence[:3])
        chain.append({
            "step": "估值定价验证",
            "description": claims,
            "evidence_ref": f"supporting+opposing (market_data+estimate, {len(valuation_evidence)}条)",
        })

    # 节点4: 风险提示
    if warnings:
        claims = "；".join(e["claim"] for e in warnings[:2])
        chain.append({
            "step": "风险提示",
            "description": claims,
            "evidence_ref": f"warnings ({len(warnings)}条)",
        })

    # 节点5: 综合判断
    chain.append({
        "step": "综合判断",
        "description": verdict,
        "evidence_ref": f"supporting={len(supporting)}, opposing={len(opposing)}",
    })

    return chain
