"""
认知驱动基金配置引擎——完整版

整合5个机构级能力，实现从"认知→验证→穿透→估值→组合"的端到端链路：

1. 产业链穿透：按细分行业 + 关键个股匹配，不是粗分sector_group
2. 估值多维判断：历史分位 + PEG + price in估算
3. 持仓变化趋势：多期持仓对比，判断加仓/减仓
4. 持仓重叠度：基金间共同持仓分析
5. 基金相关性：NAV日收益相关系数

用法:
    python scripts/cognition_engine.py --belief AI
    python scripts/cognition_engine.py --belief innovation_drug
    python scripts/cognition_engine.py --belief all
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path
from typing import Any

SOURCE_DB = Path("/tmp/fle-run/source.sqlite")
FACTOR_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"
FUND_LIST = Path(__file__).resolve().parents[1] / "data" / "phase1_fund_codes_v1_official.txt"


# ============================================================
# 认知主题与产业链映射
# ============================================================
THEMES: dict[str, dict[str, Any]] = {
    "AI": {
        "name": "AI / 算力基础设施",
        "belief": "我相信AI基础设施会先于应用层变现",
        "logic_chain": [
            "AI服务器/芯片收入确认先于大模型商业化",
            "基础设施公司已确认大量收入，应用层仍在亏损",
            "因此基础设施环节确定性更高",
        ],
        # 产业链环节：按细分行业 + 关键个股
        "chain_links": {
            "光模块/连接": {
                "industry_keywords": ["光模块", "光通信", "通信设备"],
                "stock_keywords": ["中际旭创", "天孚通信", "新易盛", "光迅科技"],
            },
            "PCB/电子元件": {
                "industry_keywords": ["电子元件", "印制电路", "电子设备"],
                "stock_keywords": ["沪电股份", "深南电路", "生益科技", "景旺电子", "鹏鼎控股", "胜宏科技", "生益电子"],
            },
            "芯片设计": {
                "industry_keywords": ["半导体", "芯片"],
                "stock_keywords": ["寒武纪", "海光信息", "澜起科技", "紫光国微"],
            },
            "服务器/算力": {
                "industry_keywords": ["计算机设备", "服务器"],
                "stock_keywords": ["工业富联", "浪潮信息", "紫光股份"],
            },
        },
        "defense_theme": "dividend_defense",
    },
    "innovation_drug": {
        "name": "创新药",
        "belief": "我相信创新药被错杀",
        "logic_chain": [
            "中国创新药BD交易额占全球30%，超过美国",
            "创新药有技术含量，是生产力升级",
            "当前估值处于历史低位",
        ],
        "chain_links": {
            "创新药研发": {
                "industry_keywords": ["医药生物", "化学制药", "生物制品"],
                "stock_keywords": ["恒瑞医药", "百济神州", "信达生物", "君实生物", "荣昌生物"],
            },
            "CXO服务": {
                "industry_keywords": ["医疗服务", "医疗研发"],
                "stock_keywords": ["药明康德", "凯莱英", "康龙化成", "泰格医药"],
            },
            "医疗器械": {
                "industry_keywords": ["医疗器械"],
                "stock_keywords": ["迈瑞医疗", "南微医学", "联影医疗"],
            },
        },
        "defense_theme": "dividend_defense",
    },
    "consumer": {
        "name": "消费升级",
        "belief": "我相信消费升级是长期趋势",
        "logic_chain": [
            "中国14亿人口的消费市场",
            "消费龙头ROE持续高于市场平均",
            "当前估值合理",
        ],
        "chain_links": {
            "食品饮料": {
                "industry_keywords": ["食品饮料", "白酒", "乳品"],
                "stock_keywords": ["贵州茅台", "五粮液", "泸州老窖", "伊利股份", "海天味业"],
            },
            "家电": {
                "industry_keywords": ["家电", "白色家电"],
                "stock_keywords": ["美的集团", "格力电器", "海尔智家"],
            },
            "免税零售": {
                "industry_keywords": ["零售", "免税"],
                "stock_keywords": ["中国中免", "珀莱雅"],
            },
        },
        "defense_theme": "dividend_defense",
    },
    "dividend_defense": {
        "name": "红利低波（防守）",
        "belief": "我需要红利低波作为防守仓位",
        "logic_chain": [
            "金融/能源板块估值低、股息率高",
            "与成长板块相关性低，对冲效果好",
            "提供安全垫",
        ],
        "chain_links": {
            "银行保险": {
                "industry_keywords": ["银行", "保险"],
                "stock_keywords": ["招商银行", "工商银行", "中国平安", "中国太保", "宁波银行"],
            },
            "能源公用": {
                "industry_keywords": ["石油", "煤炭", "电力", "公用"],
                "stock_keywords": ["中国神华", "中国石油", "长江电力", "大秦铁路"],
            },
        },
        "defense_theme": None,
    },
}


# ============================================================
# 数据访问层
# ============================================================
def load_fund_codes() -> list[str]:
    return [line.strip() for line in FUND_LIST.read_text().splitlines() if line.strip()]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute(f"ATTACH DATABASE '{FACTOR_DB.resolve()}' AS factordb")
    return conn


def get_fund_holdings(conn: sqlite3.Connection, fund_code: str, report_period: str | None = None) -> list[dict[str, Any]]:
    """获取基金持仓，关联行业和因子"""
    if report_period is None:
        report_period = conn.execute(
            "SELECT MAX(report_period) FROM stock_holdings WHERE fund_code = ?", (fund_code,)
        ).fetchone()[0]
    if not report_period:
        return []

    rows = conn.execute(
        """
        SELECT h.stock_code, h.stock_name, h.net_value_ratio AS weight,
               COALESCE(m.sector_group, 'other') AS sector_group,
               COALESCE(m.industry_name, '未知') AS industry_name,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'pe') AS pe,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'pb') AS pb,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'roe') AS roe,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'dividend_yield') AS dividend_yield,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'profit_growth') AS profit_growth,
               (SELECT f.factor_value FROM factordb.stock_factor_values f
                WHERE f.stock_code = h.stock_code AND f.factor_code = 'valuation_percentile') AS val_pct
        FROM stock_holdings h
        LEFT JOIN stock_industry_map m ON h.stock_code = m.stock_code
        WHERE h.fund_code = ? AND h.report_period = ? AND h.net_value_ratio IS NOT NULL AND h.net_value_ratio > 0
        ORDER BY h.net_value_ratio DESC
        """,
        (fund_code, report_period),
    ).fetchall()
    return [dict(r) for r in rows]


def get_fund_name(conn: sqlite3.Connection, fund_code: str) -> str:
    row = conn.execute("SELECT fund_name FROM fund_profiles WHERE fund_code = ?", (fund_code,)).fetchone()
    return row[0] if row else "?"


def get_recent_periods(conn: sqlite3.Connection, fund_code: str, n: int = 4) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT report_period FROM stock_holdings WHERE fund_code = ? ORDER BY report_period DESC LIMIT ?",
        (fund_code, n),
    ).fetchall()
    return [r[0] for r in rows]


# ============================================================
# 能力1：产业链穿透匹配
# ============================================================
def match_theme(holdings: list[dict], theme: dict) -> dict[str, Any]:
    """按产业链环节计算匹配度"""
    total_weight = sum(h["weight"] for h in holdings)
    if total_weight == 0:
        return {"match_pct": 0, "chain_breakdown": {}, "matched_stocks": []}

    chain_breakdown: dict[str, float] = {}
    matched_stocks: list[dict] = []

    for link_name, link_def in theme["chain_links"].items():
        industry_kws = link_def["industry_keywords"]
        stock_kws = link_def["stock_keywords"]
        link_weight = 0.0
        link_stocks = []

        for h in holdings:
            ind = h.get("industry_name", "")
            name = h.get("stock_name", "")
            is_industry = any(kw in ind for kw in industry_kws)
            is_stock = any(kw in name for kw in stock_kws)
            if is_industry or is_stock:
                link_weight += h["weight"]
                link_stocks.append(h)
                if h not in matched_stocks:
                    matched_stocks.append(h)

        chain_breakdown[link_name] = round(link_weight * 100, 1)

    matched_weight = sum(h["weight"] for h in matched_stocks)
    match_pct = (matched_weight / total_weight * 100) if total_weight > 0 else 0

    return {
        "match_pct": round(match_pct, 1),
        "matched_weight": round(matched_weight * 100, 1),
        "total_weight": round(total_weight * 100, 1),
        "chain_breakdown": chain_breakdown,
        "matched_stocks": sorted(matched_stocks, key=lambda x: x["weight"], reverse=True)[:5],
    }


# ============================================================
# 能力2：估值多维判断
# ============================================================
def calculate_valuation(holdings: list[dict]) -> dict[str, Any]:
    """计算加权估值：PE、估值分位、PEG"""
    valid_pe = [(h["weight"], h["pe"]) for h in holdings if h.get("pe") and h["pe"] > 0]
    valid_pct = [(h["weight"], h["val_pct"]) for h in holdings if h.get("val_pct") is not None]
    valid_growth = [(h["weight"], h["profit_growth"]) for h in holdings if h.get("profit_growth") and h["profit_growth"] > 0]
    valid_roe = [(h["weight"], h["roe"]) for h in holdings if h.get("roe") and h["roe"] > 0]
    valid_div = [(h["weight"], h["dividend_yield"]) for h in holdings if h.get("dividend_yield") and h["dividend_yield"] > 0]
    valid_pb = [(h["weight"], h["pb"]) for h in holdings if h.get("pb") and h["pb"] > 0]

    def wavg(data):
        if not data:
            return None
        return sum(w * v for w, v in data) / sum(w for w, _ in data)

    w_pe = wavg(valid_pe)
    w_pct = wavg(valid_pct)
    w_growth = wavg(valid_growth)
    w_roe = wavg(valid_roe)
    w_div = wavg(valid_div)
    w_pb = wavg(valid_pb)

    # PEG
    peg = None
    if w_pe and w_growth and w_growth > 0:
        peg = w_pe / (w_growth * 100)

    # 估值判断
    if w_pct is not None:
        if w_pct > 0.85:
            val_judge = "极度偏贵"
        elif w_pct > 0.70:
            val_judge = "偏贵"
        elif w_pct > 0.30:
            val_judge = "合理"
        else:
            val_judge = "偏低"
    else:
        val_judge = "—"

    # PEG判断
    if peg is not None:
        if peg < 1:
            peg_judge = "增速能支撑估值"
        elif peg < 1.5:
            peg_judge = "估值与增速匹配"
        elif peg < 2:
            peg_judge = "偏贵但可接受"
        else:
            peg_judge = "已price in过多增长"
    else:
        peg_judge = "—"

    return {
        "weighted_pe": round(w_pe, 1) if w_pe else None,
        "weighted_pb": round(w_pb, 2) if w_pb else None,
        "weighted_roe": round(w_roe * 100, 1) if w_roe else None,
        "weighted_dividend": round(w_div * 100, 2) if w_div else None,
        "weighted_val_pct": round(w_pct * 100, 0) if w_pct is not None else None,
        "weighted_growth": round(w_growth * 100, 0) if w_growth else None,
        "peg": round(peg, 2) if peg else None,
        "val_judge": val_judge,
        "peg_judge": peg_judge,
    }


# ============================================================
# 能力3：持仓变化趋势
# ============================================================
def calculate_holding_trend(conn: sqlite3.Connection, fund_code: str, theme: dict) -> dict[str, Any]:
    """计算基金对该认知主题的持仓变化趋势"""
    periods = get_recent_periods(conn, fund_code, 4)
    if len(periods) < 2:
        return {"trend": "insufficient_data", "periods": []}

    # 收集所有产业链关键词
    all_stock_kws = []
    all_industry_kws = []
    for link in theme["chain_links"].values():
        all_stock_kws.extend(link["stock_keywords"])
        all_industry_kws.extend(link["industry_keywords"])

    trend_data = []
    for period in periods:
        holdings = get_fund_holdings(conn, fund_code, period)
        matched_weight = 0.0
        for h in holdings:
            ind = h.get("industry_name", "")
            name = h.get("stock_name", "")
            if any(kw in ind for kw in all_industry_kws) or any(kw in name for kw in all_stock_kws):
                matched_weight += h["weight"]
        trend_data.append({"period": period, "weight": round(matched_weight * 100, 1)})

    # 判断趋势
    latest = trend_data[0]["weight"]
    earliest = trend_data[-1]["weight"]
    diff = latest - earliest

    if diff > 5:
        trend = "increasing"
    elif diff < -5:
        trend = "decreasing"
    else:
        trend = "stable"

    return {"trend": trend, "diff": round(diff, 1), "periods": trend_data}


# ============================================================
# 能力4：持仓重叠度
# ============================================================
def calculate_overlap(holdings_a: list[dict], holdings_b: list[dict]) -> dict[str, Any]:
    """计算两只基金的持仓重叠度"""
    map_a = {h["stock_code"]: h["weight"] for h in holdings_a}
    map_b = {h["stock_code"]: h["weight"] for h in holdings_b}
    common = set(map_a.keys()) & set(map_b.keys())

    overlap_a = sum(map_a[s] for s in common)
    overlap_b = sum(map_b[s] for s in common)

    if overlap_a > 0.4:
        judge = "高度重叠，建议只选一只"
    elif overlap_a > 0.2:
        judge = "中度重叠，需评估分散效果"
    else:
        judge = "低重叠，分散效果良好"

    return {
        "common_count": len(common),
        "overlap_a_pct": round(overlap_a * 100, 1),
        "overlap_b_pct": round(overlap_b * 100, 1),
        "judge": judge,
        "common_stocks": sorted(
            [{"code": s, "a": round(map_a[s] * 100, 2), "b": round(map_b[s] * 100, 2)} for s in common],
            key=lambda x: x["a"] + x["b"],
            reverse=True,
        )[:3],
    }


# ============================================================
# 能力5：基金相关性
# ============================================================
def calculate_correlation(conn: sqlite3.Connection, fund_a: str, fund_b: str) -> float | None:
    """计算两只基金的NAV日收益相关系数"""
    rows_a = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
        (fund_a,),
    ).fetchall()
    rows_b = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
        (fund_b,),
    ).fetchall()

    map_a = {r[0]: r[1] for r in rows_a}
    map_b = {r[0]: r[1] for r in rows_b}
    common = sorted(set(map_a.keys()) & set(map_b.keys()))

    if len(common) < 30:
        return None

    returns_a = [map_a[d] for d in common]
    returns_b = [map_b[d] for d in common]
    return round(statistics.correlation(returns_a, returns_b), 3)


# ============================================================
# 认知验证
# ============================================================
def validate_cognition(holdings_top: list[dict], valuation: dict) -> dict[str, Any]:
    """对认知提供正反证据"""
    supporting = []
    opposing = []

    # 基本面：利润增速
    growth = valuation.get("weighted_growth")
    if growth and growth > 30:
        supporting.append(f"利润增速 {growth}%，基本面强劲")
    elif growth and growth > 15:
        supporting.append(f"利润增速 {growth}%，基本面稳健")
    elif growth:
        opposing.append(f"利润增速仅 {growth}%，增长乏力")

    # ROE
    roe = valuation.get("weighted_roe")
    if roe and roe > 15:
        supporting.append(f"加权ROE {roe}%，盈利能力强")

    # 估值分位
    val_pct = valuation.get("weighted_val_pct")
    if val_pct and val_pct > 85:
        opposing.append(f"估值分位 {val_pct}%，处于历史高位")
    elif val_pct and val_pct < 30:
        supporting.append(f"估值分位 {val_pct}%，处于历史低位")

    # PEG
    peg = valuation.get("peg")
    if peg and peg < 1:
        supporting.append(f"PEG {peg}，增速能支撑估值")
    elif peg and peg > 2:
        opposing.append(f"PEG {peg}，已price in过多增长")

    # 股息率
    div = valuation.get("weighted_dividend")
    if div and div > 3:
        supporting.append(f"股息率 {div}%，有安全垫")

    if len(supporting) > len(opposing):
        verdict = "认知有效"
    elif len(supporting) == len(opposing):
        verdict = "认知有分歧"
    else:
        verdict = "认知存疑"

    return {
        "supporting": supporting,
        "opposing": opposing,
        "verdict": verdict,
    }


# ============================================================
# 组合构建
# ============================================================
def build_portfolio(candidates: list[dict], defense_fund: dict | None, corr_threshold: float = 0.8) -> dict[str, Any]:
    """构建认知匹配的组合方案"""
    # 按匹配度排序
    candidates.sort(key=lambda x: x["match_pct"], reverse=True)

    selected = []
    for c in candidates:
        if c["match_pct"] < 10:
            continue
        # 估值约束：极度偏贵时降低权重上限
        val_pct = c["valuation"].get("weighted_val_pct")
        if val_pct and val_pct > 85:
            max_weight = 5
        elif val_pct and val_pct > 70:
            max_weight = 8
        else:
            max_weight = 12

        # 趋势约束：减仓的基金降低权重
        if c["trend"]["trend"] == "decreasing":
            max_weight = min(max_weight, 5)

        # 相关性检查：与已选基金相关性太高则跳过
        too_correlated = False
        for s in selected:
            if s.get("corr_with", {}).get(c["fund_code"], 0) > corr_threshold:
                too_correlated = True
                break
        if too_correlated:
            continue

        selected.append({**c, "max_weight": max_weight})

        if len(selected) >= 3:
            break

    # 分配权重
    total_match = sum(s["match_pct"] for s in selected) or 1
    for s in selected:
        raw = s["match_pct"] / total_match * 25  # 认知仓位合计25%
        s["weight"] = min(raw, s["max_weight"])

    # 防守仓位
    defense_weight = 0
    if defense_fund:
        defense_weight = 10
        defense_fund["weight"] = defense_weight

    # 归一化
    total = sum(s["weight"] for s in selected) + defense_weight
    cash = max(0, 100 - total)

    return {
        "selected": selected,
        "defense": defense_fund,
        "cash_pct": round(cash, 1),
        "total_invested": round(total, 1),
    }


# ============================================================
# 主流程
# ============================================================
def run_cognition_engine(conn: sqlite3.Connection, theme_key: str, top_n: int = 5) -> None:
    theme = THEMES[theme_key]

    print(f"\n{'#'*72}")
    print(f"  认知：{theme['belief']}")
    print(f"{'#'*72}")

    # --- 认知逻辑链 ---
    print(f"\n  投资逻辑：")
    for i, logic in enumerate(theme["logic_chain"], 1):
        print(f"    {i}. {logic}")

    # --- 产业链环节 ---
    print(f"\n  产业链环节：")
    for link_name in theme["chain_links"]:
        kws = theme["chain_links"][link_name]["stock_keywords"]
        print(f"    {link_name}：{', '.join(kws[:4])}...")

    # --- 基金匹配 ---
    fund_codes = load_fund_codes()
    candidates = []
    for fund_code in fund_codes:
        holdings = get_fund_holdings(conn, fund_code)
        if not holdings:
            continue

        match = match_theme(holdings, theme)
        if match["match_pct"] < 5:
            continue

        valuation = calculate_valuation(holdings)
        trend = calculate_holding_trend(conn, fund_code, theme)
        fund_name = get_fund_name(conn, fund_code)

        candidates.append({
            "fund_code": fund_code,
            "fund_name": fund_name,
            "match_pct": match["match_pct"],
            "chain_breakdown": match["chain_breakdown"],
            "matched_stocks": match["matched_stocks"],
            "valuation": valuation,
            "trend": trend,
            "holdings": holdings,
        })

    candidates.sort(key=lambda x: x["match_pct"], reverse=True)
    top_candidates = candidates[:top_n]

    # --- 认知验证（用TOP1基金的数据） ---
    if top_candidates:
        validation = validate_cognition(top_candidates[0]["matched_stocks"], top_candidates[0]["valuation"])
        print(f"\n  ┌─ 认知验证 ──────────────────────────────────────┐")
        print(f"  │ 支持证据：")
        for s in validation["supporting"]:
            print(f"  │   ✅ {s}")
        if not validation["supporting"]:
            print(f"  │   （无）")
        print(f"  │ 反面证据：")
        for o in validation["opposing"]:
            print(f"  │   ⚠️  {o}")
        if not validation["opposing"]:
            print(f"  │   （无）")
        print(f"  │ 判断：{validation['verdict']}")
        print(f"  └──────────────────────────────────────────────────┘")

    # --- 基金筛选结果 ---
    print(f"\n  匹配基金：{len(candidates)} / {len(fund_codes)} 只")
    print(f"\n  TOP {len(top_candidates)} 基金：")
    print(f"  {'代码':<8} {'名称':<20} {'匹配':>5} {'PE':>7} {'分位':>5} {'PEG':>5} {'趋势':>6} {'判断':>8}")
    print(f"  {'-'*8} {'-'*20} {'-'*5} {'-'*7} {'-'*5} {'-'*5} {'-'*6} {'-'*8}")

    for c in top_candidates:
        name = c["fund_name"][:18]
        pe = f"{c['valuation']['weighted_pe']:.0f}" if c["valuation"]["weighted_pe"] else "—"
        pct = f"{c['valuation']['weighted_val_pct']:.0f}%" if c["valuation"]["weighted_val_pct"] is not None else "—"
        peg = f"{c['valuation']['peg']:.1f}" if c["valuation"]["peg"] else "—"
        trend_map = {"increasing": "↑加仓", "decreasing": "↓减仓", "stable": "→持平", "insufficient_data": "?不足"}
        trend_str = trend_map.get(c["trend"]["trend"], "?")
        judge = c["valuation"]["val_judge"]
        print(f"  {c['fund_code']:<8} {name:<20} {c['match_pct']:>4.0f}% {pe:>7} {pct:>5} {peg:>5} {trend_str:>6} {judge:>8}")

    # --- 持仓穿透（TOP1） ---
    if top_candidates:
        c = top_candidates[0]
        print(f"\n  ┌─ 持仓穿透：{c['fund_code']} {c['fund_name']} ──────────────┐")
        print(f"  │ 匹配度 {c['match_pct']}% | 估值分位 {c['valuation']['weighted_val_pct'] or '—'}% | PEG {c['valuation']['peg'] or '—'}")
        print(f"  │")
        print(f"  │ 产业链分布：")
        for link, w in sorted(c["chain_breakdown"].items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(w / 3)
            print(f"  │   {link:<16} {w:>5.1f}% {bar}")
        print(f"  │")
        print(f"  │ TOP 5 匹配个股：")
        print(f"  │   {'股票':<8} {'名称':<8} {'权重':>6} {'PE':>7} {'分位':>5} {'PEG':>5}")
        for s in c["matched_stocks"][:5]:
            pe = f"{s['pe']:.0f}" if s.get("pe") and s["pe"] > 0 else "—"
            pct = f"{s['val_pct']*100:.0f}%" if s.get("val_pct") is not None else "—"
            peg = f"{s['pe']/ (s['profit_growth']*100):.1f}" if s.get("pe") and s.get("profit_growth") and s["profit_growth"] > 0 else "—"
            name = (s.get("stock_name") or "?")[:6]
            print(f"  │   {s['stock_code']:<8} {name:<8} {s['weight']*100:>5.1f}% {pe:>7} {pct:>5} {peg:>5}")

        # 持仓趋势
        if c["trend"]["periods"]:
            print(f"  │")
            print(f"  │ 持仓变化趋势：")
            for p in c["trend"]["periods"]:
                bar = "█" * int(p["weight"] / 3)
                print(f"  │   {p['period']}  {p['weight']:>5.1f}% {bar}")
            trend_map = {"increasing": "持续加仓 → 认知匹配可信", "decreasing": "持续减仓 → 需警惕", "stable": "持仓稳定", "insufficient_data": "数据不足"}
            print(f"  │   → {trend_map.get(c['trend']['trend'], '?')}")
        print(f"  └──────────────────────────────────────────────────┘")

    # --- 组合分析 ---
    if len(top_candidates) >= 2:
        print(f"\n  ┌─ 组合分析 ──────────────────────────────────────┐")

        # 持仓重叠度
        for i in range(min(3, len(top_candidates))):
            for j in range(i + 1, min(3, len(top_candidates))):
                a, b = top_candidates[i], top_candidates[j]
                overlap = calculate_overlap(a["holdings"], b["holdings"])
                print(f"  │ {a['fund_code']} vs {b['fund_code']} 重叠度: {overlap['overlap_a_pct']}% ({overlap['judge']})")

        # 相关性
        for i in range(min(3, len(top_candidates))):
            for j in range(i + 1, min(3, len(top_candidates))):
                a, b = top_candidates[i], top_candidates[j]
                corr = calculate_correlation(conn, a["fund_code"], b["fund_code"])
                if corr is not None:
                    if corr > 0.8:
                        corr_judge = "高度相关，分散差"
                    elif corr > 0.6:
                        corr_judge = "中度相关"
                    else:
                        corr_judge = "低相关，分散好"
                    print(f"  │ {a['fund_code']} vs {b['fund_code']} 相关性: {corr} ({corr_judge})")

        # 防守基金
        defense_fund = None
        if theme.get("defense_theme"):
            defense_key = theme["defense_theme"]
            defense_theme = THEMES.get(defense_key)
            if defense_theme:
                defense_candidates = []
                for fund_code in fund_codes:
                    holdings = get_fund_holdings(conn, fund_code)
                    if not holdings:
                        continue
                    match = match_theme(holdings, defense_theme)
                    if match["match_pct"] > 30:
                        valuation = calculate_valuation(holdings)
                        defense_candidates.append({
                            "fund_code": fund_code,
                            "fund_name": get_fund_name(conn, fund_code),
                            "match_pct": match["match_pct"],
                            "valuation": valuation,
                            "holdings": holdings,
                        })
                defense_candidates.sort(key=lambda x: x["match_pct"], reverse=True)
                if defense_candidates:
                    defense_fund = defense_candidates[0]
                    d = defense_fund
                    print(f"  │")
                    print(f"  │ 防守基金：{d['fund_code']} {d['fund_name']}")
                    print(f"  │   匹配度 {d['match_pct']}% | PE {d['valuation']['weighted_pe'] or '—'} | 股息率 {d['valuation']['weighted_dividend'] or '—'}%")

                    # AI与防守基金相关性
                    corr_defense = calculate_correlation(conn, top_candidates[0]["fund_code"], d["fund_code"])
                    if corr_defense is not None:
                        print(f"  │   与认知基金相关性: {corr_defense}", end="")
                        if corr_defense < 0.3:
                            print(f" → 对冲效果极好")
                        elif corr_defense < 0.6:
                            print(f" → 对冲效果一般")
                        else:
                            print(f" → 对冲效果差")

        print(f"  └──────────────────────────────────────────────────┘")

        # --- 组合方案 ---
        portfolio = build_portfolio(top_candidates, defense_fund)
        print(f"\n  ┌─ 认知组合方案 ──────────────────────────────────┐")
        print(f"  │")
        for s in portfolio["selected"]:
            print(f"  │ {s['fund_code']} {s['fund_name'][:16]:<16} {s['weight']:>5.1f}%  (匹配{s['match_pct']:.0f}%, PE {s['valuation']['weighted_pe'] or '—'}, 上限{s['max_weight']}%)")
        if portfolio["defense"]:
            d = portfolio["defense"]
            print(f"  │ {d['fund_code']} {d['fund_name'][:16]:<16} {d['weight']:>5.1f}%  (防守, 股息{d['valuation']['weighted_dividend'] or '—'}%)")
        print(f"  │ {'现金':<24} {portfolio['cash_pct']:>5.1f}%")
        print(f"  │")
        print(f"  │ 总投资: {portfolio['total_invested']}% | 现金: {portfolio['cash_pct']}%")
        print(f"  └──────────────────────────────────────────────────┘")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="认知驱动基金配置引擎")
    parser.add_argument("--belief", default="AI", choices=list(THEMES.keys()) + ["all"])
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args(argv)

    if not SOURCE_DB.exists():
        print(f"错误：{SOURCE_DB} 不存在", file=sys.stderr)
        return 1

    conn = get_conn()
    themes = list(THEMES.keys()) if args.belief == "all" else [args.belief]
    for theme_key in themes:
        run_cognition_engine(conn, theme_key, args.top)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
