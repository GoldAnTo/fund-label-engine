"""
认知匹配演示脚本

用 142 只基金的持仓数据，演示"投资者认知 → 基金匹配"的流程。
不依赖标签引擎，直接从持仓穿透，回答"我相信X，哪些基金最匹配"。

用法:
    PYTHONPATH=backend python scripts/cognition_match_demo.py
    PYTHONPATH=backend python scripts/cognition_match_demo.py --belief AI
    PYTHONPATH=backend python scripts/cognition_match_demo.py --belief all
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

# --- 数据路径 ---
SOURCE_DB = Path("/tmp/fle-run/source.sqlite")
FACTOR_DB = Path(__file__).resolve().parents[1] / "data" / "stock_factors.sqlite"
FUND_LIST = Path(__file__).resolve().parents[1] / "data" / "phase1_fund_codes_v1_official.txt"


# --- 认知主题定义 ---
# 基于现有 sector_group（8类）+ 关键个股关键词
# 这就是"认知 → 资产"的映射库雏形
THEME_MAP: dict[str, dict[str, Any]] = {
    "AI": {
        "name": "AI / 科技",
        "description": "我相信 AI 是巨大生产力变革",
        "sector_groups": ["tech"],
        # 关键个股关键词（持仓股票名称包含这些词就算匹配）
        "stock_keywords": [
            "寒武纪", "中际旭创", "海光信息", "工业富联", "浪潮信息",
            "紫光国微", "北方华创", "中微公司", "沪电股份", "兆易创新",
            "韦尔股份", "三安光电", "闻泰科技", "立讯精密", "歌尔股份",
            "科大讯飞", "恒生电子", "金山办公", "中科曙光", "景嘉微",
        ],
    },
    "innovation_drug": {
        "name": "创新药",
        "description": "我相信创新药被错杀",
        "sector_groups": ["healthcare"],
        "stock_keywords": [
            "恒瑞医药", "百济神州", "信达生物", "药明康德", "凯莱英",
            "智飞生物", "长春高新", "片仔癀", "云南白药", "泰格医药",
            "康龙化成", "药明生物", "复星医药", "沃森生物", "康泰生物",
        ],
    },
    "consumer": {
        "name": "消费升级",
        "description": "我相信消费升级是长期趋势",
        "sector_groups": ["consumer"],
        "stock_keywords": [
            "贵州茅台", "五粮液", "泸州老窖", "洋河股份", "古井贡酒",
            "伊利股份", "海天味业", "美的集团", "格力电器", "海尔智家",
            "中国中免", "珀莱雅", "安井食品", "绝味食品", "三只松鼠",
        ],
    },
    "dividend_defense": {
        "name": "红利低波（防守）",
        "description": "我需要红利低波作为防守仓位",
        "sector_groups": ["financial", "energy_utility"],
        "stock_keywords": [
            "招商银行", "工商银行", "建设银行", "农业银行", "中国银行",
            "中国神华", "中国石油", "中国石化", "长江电力", "大秦铁路",
            "中国建筑", "中国交建", "中国铁建", "中国中铁", "交通银行",
        ],
    },
    "cyclical": {
        "name": "周期复苏",
        "description": "我相信周期行业会复苏",
        "sector_groups": ["cyclical"],
        "stock_keywords": [
            "宝钢股份", "紫金矿业", "洛阳钼业", "江西铜业", "中国铝业",
            "海螺水泥", "万华化学", "荣盛石化", "恒力石化", "桐昆股份",
        ],
    },
}


def load_fund_codes() -> list[str]:
    """读取 Phase1 基金清单"""
    return [line.strip() for line in FUND_LIST.read_text().splitlines() if line.strip()]


def get_connection() -> sqlite3.Connection:
    """连接源库并挂载因子库"""
    conn = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    if FACTOR_DB.exists():
        conn.execute(f"ATTACH DATABASE '{FACTOR_DB.resolve()}' AS factordb")
    return conn


def get_fund_holdings(conn: sqlite3.Connection, fund_code: str) -> list[dict[str, Any]]:
    """获取基金最新报告期的持仓，关联行业映射和因子"""
    rows = conn.execute(
        """
        SELECT
            h.stock_code,
            h.stock_name,
            h.net_value_ratio AS weight,
            COALESCE(m.sector_group, 'other') AS sector_group,
            COALESCE(m.industry_name, '未知') AS industry_name,
            (SELECT f.factor_value FROM factordb.stock_factor_values f
             WHERE f.stock_code = h.stock_code AND f.factor_code = 'pb') AS pb,
            (SELECT f.factor_value FROM factordb.stock_factor_values f
             WHERE f.stock_code = h.stock_code AND f.factor_code = 'pe') AS pe,
            (SELECT f.factor_value FROM factordb.stock_factor_values f
             WHERE f.stock_code = h.stock_code AND f.factor_code = 'roe') AS roe,
            (SELECT f.factor_value FROM factordb.stock_factor_values f
             WHERE f.stock_code = h.stock_code AND f.factor_code = 'dividend_yield') AS dividend_yield
        FROM stock_holdings h
        LEFT JOIN stock_industry_map m ON h.stock_code = m.stock_code
        WHERE h.fund_code = ?
            AND h.report_period = (
                SELECT MAX(report_period) FROM stock_holdings WHERE fund_code = ?
            )
            AND h.net_value_ratio IS NOT NULL
            AND h.net_value_ratio > 0
        ORDER BY h.net_value_ratio DESC
        """,
        (fund_code, fund_code),
    ).fetchall()
    return [dict(row) for row in rows]


def get_fund_profile(conn: sqlite3.Connection, fund_code: str) -> dict[str, Any]:
    """获取基金基础信息"""
    row = conn.execute(
        "SELECT fund_code, fund_name, fund_type, asset_size FROM fund_profiles WHERE fund_code = ?",
        (fund_code,),
    ).fetchone()
    return dict(row) if row else {"fund_code": fund_code, "fund_name": "?", "fund_type": "?", "asset_size": None}


def calculate_theme_match(holdings: list[dict[str, Any]], theme: dict[str, Any]) -> dict[str, Any]:
    """计算基金对某个认知主题的匹配度"""
    total_weight = sum(h["weight"] for h in holdings)
    if total_weight == 0:
        return {"match_pct": 0, "matched_stocks": [], "sector_breakdown": {}}

    # 1. 按行业匹配
    sector_groups = set(theme["sector_groups"])
    sector_matched_weight = sum(
        h["weight"] for h in holdings if h["sector_group"] in sector_groups
    )

    # 2. 按个股关键词匹配
    keywords = theme["stock_keywords"]
    keyword_matched_stocks = []
    keyword_matched_weight = 0.0
    for h in holdings:
        stock_name = h.get("stock_name") or ""
        if any(kw in stock_name for kw in keywords):
            keyword_matched_stocks.append(h)
            keyword_matched_weight += h["weight"]

    # 3. 合并匹配（取行业匹配和个股匹配的并集，避免重复计算）
    matched_stock_codes = set()
    matched_stocks = []
    matched_weight = 0.0
    for h in holdings:
        stock_name = h.get("stock_name") or ""
        is_sector_match = h["sector_group"] in sector_groups
        is_keyword_match = any(kw in stock_name for kw in keywords)
        if is_sector_match or is_keyword_match:
            if h["stock_code"] not in matched_stock_codes:
                matched_stock_codes.add(h["stock_code"])
                matched_stocks.append(h)
                matched_weight += h["weight"]

    # 4. 行业分布（匹配部分）
    sector_breakdown: dict[str, float] = {}
    for h in matched_stocks:
        sg = h["sector_group"]
        sector_breakdown[sg] = sector_breakdown.get(sg, 0) + h["weight"]

    match_pct = (matched_weight / total_weight * 100) if total_weight > 0 else 0

    return {
        "match_pct": round(match_pct, 1),
        "matched_weight": round(matched_weight * 100, 1),
        "total_weight": round(total_weight * 100, 1),
        "matched_count": len(matched_stocks),
        "matched_stocks": sorted(matched_stocks, key=lambda x: x["weight"], reverse=True)[:5],
        "sector_breakdown": sector_breakdown,
    }


def calculate_valuation(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """计算基金加权估值"""
    total_weight = sum(h["weight"] for h in holdings)
    if total_weight == 0:
        return {"weighted_pe": None, "weighted_pb": None, "weighted_roe": None, "weighted_dividend": None}

    def weighted_avg(field: str, pct: bool = False) -> float | None:
        valid = [(h["weight"], h[field]) for h in holdings if h.get(field) is not None and h[field] > 0]
        if not valid:
            return None
        val = sum(w * v for w, v in valid) / sum(w for w, _ in valid)
        if pct:
            val *= 100  # ROE 和股息率存储为小数，转成百分比
        return round(val, 2)

    return {
        "weighted_pe": weighted_avg("pe"),
        "weighted_pb": weighted_avg("pb"),
        "weighted_roe": weighted_avg("roe", pct=True),
        "weighted_dividend": weighted_avg("dividend_yield", pct=True),
    }


def run_cognition_match(belief: str = "all", top_n: int = 10) -> None:
    """运行认知匹配演示"""
    fund_codes = load_fund_codes()
    conn = get_connection()

    themes_to_run = (
        list(THEME_MAP.keys()) if belief == "all" else [belief]
    )

    for theme_key in themes_to_run:
        theme = THEME_MAP[theme_key]
        print(f"\n{'='*72}")
        print(f"  认知：{theme['description']}")
        print(f"  主题：{theme['name']}（{theme_key}）")
        print(f"  匹配方式：行业分组 {theme['sector_groups']} + {len(theme['stock_keywords'])} 只关键个股")
        print(f"{'='*72}")

        results: list[dict[str, Any]] = []
        for fund_code in fund_codes:
            holdings = get_fund_holdings(conn, fund_code)
            if not holdings:
                continue
            profile = get_fund_profile(conn, fund_code)
            match = calculate_theme_match(holdings, theme)
            valuation = calculate_valuation(holdings)
            results.append({
                "fund_code": fund_code,
                "fund_name": profile.get("fund_name", "?"),
                "fund_type": profile.get("fund_type", "?"),
                "fund_size": profile.get("asset_size"),
                **match,
                **valuation,
            })

        # 按匹配度排序
        results.sort(key=lambda x: x["match_pct"], reverse=True)
        # 过滤掉匹配度为0的
        matched = [r for r in results if r["match_pct"] > 0]

        print(f"\n  匹配基金数：{len(matched)} / {len(results)} 只有持仓")
        print(f"\n  TOP {min(top_n, len(matched))} 匹配基金：")
        print(f"  {'基金代码':<10} {'基金名称':<24} {'匹配度':>6} {'加权PE':>8} {'加权PB':>8} {'加权ROE':>8} {'股息率':>8}")
        print(f"  {'-'*10} {'-'*24} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for r in matched[:top_n]:
            name = r["fund_name"][:22] if r["fund_name"] else "?"
            pe_str = f"{r['weighted_pe']:.1f}" if r["weighted_pe"] else "—"
            pb_str = f"{r['weighted_pb']:.2f}" if r["weighted_pb"] else "—"
            roe_str = f"{r['weighted_roe']:.1f}%" if r["weighted_roe"] else "—"
            div_str = f"{r['weighted_dividend']:.2f}%" if r["weighted_dividend"] else "—"
            print(f"  {r['fund_code']:<10} {name:<24} {r['match_pct']:>5.1f}% {pe_str:>8} {pb_str:>8} {roe_str:>8} {div_str:>8}")

        # 展示 TOP 1 的持仓穿透
        if matched:
            top1 = matched[0]
            print(f"\n  --- 持仓穿透：{top1['fund_code']} {top1['fund_name']} ---")
            print(f"  匹配度 {top1['match_pct']}%，匹配 {top1['matched_count']} 只股票，合计权重 {top1['matched_weight']}%")
            print(f"  加权 PE: {top1['weighted_pe'] or '—'}, 加权 PB: {top1['weighted_pb'] or '—'}, 加权 ROE: {top1['weighted_roe'] or '—'}")

            # 估值判断
            if top1["weighted_pe"]:
                if top1["weighted_pe"] > 50:
                    valuation_note = "偏贵（PE>50）"
                elif top1["weighted_pe"] > 30:
                    valuation_note = "中等偏高（PE 30-50）"
                elif top1["weighted_pe"] > 15:
                    valuation_note = "合理（PE 15-30）"
                else:
                    valuation_note = "偏低（PE<15）"
                print(f"  估值判断：{valuation_note}")

            print(f"\n  TOP 5 匹配个股：")
            print(f"  {'股票代码':<10} {'股票名称':<12} {'权重':>8} {'行业':<10} {'PE':>8} {'PB':>8} {'ROE':>8}")
            print(f"  {'-'*10} {'-'*12} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
            for s in top1["matched_stocks"]:
                pe = f"{s['pe']:.1f}" if s.get("pe") and s["pe"] > 0 else "—"
                pb = f"{s['pb']:.2f}" if s.get("pb") and s["pb"] > 0 else "—"
                roe = f"{s['roe']*100:.1f}%" if s.get("roe") else "—"
                name = s.get("stock_name", "?")[:10]
                print(f"  {s['stock_code']:<10} {name:<12} {s['weight']*100:>7.2f}% {s.get('industry_name','?')[:8]:<10} {pe:>8} {pb:>8} {roe:>8}")

            # 行业分布
            if top1["sector_breakdown"]:
                print(f"\n  匹配部分行业分布：")
                for sg, w in sorted(top1["sector_breakdown"].items(), key=lambda x: x[1], reverse=True):
                    print(f"    {sg:<16} {w*100:>6.2f}%")

    conn.close()

    # 输出认知 → 组合建议
    if belief == "all":
        print(f"\n{'='*72}")
        print("  认知组合建议（示例）")
        print(f"{'='*72}")
        print("""
  如果你的认知是"我相信 AI"，基于以上匹配结果：

  1. 认知匹配：选择 AI 匹配度 TOP 3 的基金
  2. 估值检查：看加权 PE 是否偏高
     - 如果 PE > 50（偏贵），控制仓位不超过 15%
     - 如果 PE 30-50（中等），可以配 20-25%
     - 如果 PE < 30（合理），可以配 25-30%
  3. 防守对冲：配置红利低波匹配度 TOP 1 的基金，占比 10-15%
  4. 分散检查：看 TOP 3 基金的持仓重叠度，避免买同一批股票

  ⚠️ 注意：这个演示只用了行业分组+关键个股匹配，
     实际认知引擎还需要：
     - 产业链拆解（AI基础设施 vs AI应用层）
     - 估值历史分位（当前PE在历史什么位置）
     - price in 估算（隐含了多少年增长）
     - 认知验证（基本面支撑 vs 反面证据）
""")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="认知匹配演示")
    parser.add_argument(
        "--belief",
        default="all",
        choices=["all"] + list(THEME_MAP.keys()),
        help="选择认知主题",
    )
    parser.add_argument("--top", type=int, default=10, help="每个主题展示前N只基金")
    args = parser.parse_args(argv)

    if not SOURCE_DB.exists():
        print(f"错误：源数据库不存在: {SOURCE_DB}", file=sys.stderr)
        return 1

    run_cognition_match(belief=args.belief, top_n=args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
