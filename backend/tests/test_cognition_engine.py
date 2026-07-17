"""认知引擎模块测试。"""
from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.cognition.asset_mapper import match_theme
from app.cognition.chain_graph import get_all_stock_keywords, load_chains
from app.cognition.engine import CognitionEngine
from app.cognition.expectation_gap import calculate_link_expectation_gap
from app.cognition.portfolio_builder import build_portfolio, calculate_overlap
from app.cognition.theme_registry import load_themes
from app.cognition.validator import validate_cognition
from app.cognition.valuation_gate import (
    calculate_valuation,
    check_hard_limits,
    estimate_price_in_years,
    suggest_max_weight,
)


# ============================================================
# 测试辅助：构建 funddata 风格的测试数据库
# ============================================================
def _gen_dates(n: int = 40) -> list[str]:
    start = date(2025, 11, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _gen_returns(n: int = 40, offset: float = 0.0) -> list[float]:
    return [round(0.001 * math.sin(i * 0.3) + 0.0005 + offset, 6) for i in range(n)]


def _make_cognition_db(tmp_path: Path) -> tuple[Path, Path]:
    """创建测试用 funddata 风格数据库（source + factor 两个库）。"""
    source_db = tmp_path / "source.sqlite"
    factor_db = tmp_path / "factors.sqlite"

    conn = sqlite3.connect(source_db)
    conn.executescript(
        """
        CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_name TEXT, fund_type TEXT);
        CREATE TABLE stock_holdings (
            fund_code TEXT, stock_code TEXT, stock_name TEXT,
            report_period TEXT, net_value_ratio REAL
        );
        CREATE TABLE stock_industry_map (
            stock_code TEXT, industry_code TEXT, industry_name TEXT,
            sector_group TEXT, source TEXT, as_of_date TEXT
        );
        CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL);
        """
    )

    conn.executemany(
        "INSERT INTO fund_profiles VALUES (?, ?, ?)",
        [
            ("000001", "消费龙头基金", "股票型"),
            ("000002", "消费均衡基金", "混合型-偏股"),
            ("000003", "红利防守基金", "股票型"),
        ],
    )

    # --- 基金 000001: 消费龙头（高 consumer 匹配度，加仓趋势）---
    conn.executemany(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
        [
            ("000001", "600519", "贵州茅台", "2025-12-31", 0.12),
            ("000001", "000858", "五粮液", "2025-12-31", 0.10),
            ("000001", "000568", "泸州老窖", "2025-12-31", 0.08),
            ("000001", "600887", "伊利股份", "2025-12-31", 0.06),
            ("000001", "000333", "美的集团", "2025-12-31", 0.04),
            ("000001", "600036", "招商银行", "2025-12-31", 0.03),
            # 历史期（权重更低 → 加仓趋势）
            ("000001", "600519", "贵州茅台", "2025-06-30", 0.08),
            ("000001", "000858", "五粮液", "2025-06-30", 0.06),
            ("000001", "000568", "泸州老窖", "2025-06-30", 0.05),
            ("000001", "600887", "伊利股份", "2025-06-30", 0.04),
            ("000001", "000333", "美的集团", "2025-06-30", 0.02),
            ("000001", "600036", "招商银行", "2025-06-30", 0.05),
        ],
    )

    # --- 基金 000002: 消费均衡（中等 consumer 匹配度）---
    conn.executemany(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
        [
            ("000002", "600519", "贵州茅台", "2025-12-31", 0.05),
            ("000002", "000333", "美的集团", "2025-12-31", 0.03),
            ("000002", "300750", "宁德时代", "2025-12-31", 0.08),
            ("000002", "002594", "比亚迪", "2025-12-31", 0.06),
            ("000002", "600036", "招商银行", "2025-12-31", 0.04),
            ("000002", "600519", "贵州茅台", "2025-06-30", 0.04),
            ("000002", "000333", "美的集团", "2025-06-30", 0.02),
            ("000002", "300750", "宁德时代", "2025-06-30", 0.07),
            ("000002", "002594", "比亚迪", "2025-06-30", 0.05),
            ("000002", "600036", "招商银行", "2025-06-30", 0.04),
        ],
    )

    # --- 基金 000003: 红利防守（高 dividend_defense 匹配度）---
    conn.executemany(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
        [
            ("000003", "600036", "招商银行", "2025-12-31", 0.10),
            ("000003", "601398", "工商银行", "2025-12-31", 0.08),
            ("000003", "601318", "中国平安", "2025-12-31", 0.06),
            ("000003", "601088", "中国神华", "2025-12-31", 0.05),
            ("000003", "600519", "贵州茅台", "2025-12-31", 0.02),
            ("000003", "600036", "招商银行", "2025-06-30", 0.09),
            ("000003", "601398", "工商银行", "2025-06-30", 0.07),
            ("000003", "601318", "中国平安", "2025-06-30", 0.06),
            ("000003", "601088", "中国神华", "2025-06-30", 0.05),
            ("000003", "600519", "贵州茅台", "2025-06-30", 0.03),
        ],
    )

    # --- 行业映射 ---
    conn.executemany(
        "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("600519", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
            ("000858", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
            ("000568", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
            ("600887", "801120", "食品饮料", "consumer", "fixture", "2025-12-31"),
            ("000333", "801730", "家电", "consumer", "fixture", "2025-12-31"),
            ("600036", "801780", "银行", "financial", "fixture", "2025-12-31"),
            ("601398", "801780", "银行", "financial", "fixture", "2025-12-31"),
            ("601318", "801790", "保险", "financial", "fixture", "2025-12-31"),
            ("601088", "801020", "煤炭", "energy", "fixture", "2025-12-31"),
            ("300750", "801730", "电力设备", "other", "fixture", "2025-12-31"),
            ("002594", "801880", "汽车", "other", "fixture", "2025-12-31"),
        ],
    )

    # --- NAV 日收益（40 天，三只基金相互正相关的日收益）---
    dates = _gen_dates(40)
    returns = {
        "000001": _gen_returns(40, 0.0),
        "000002": _gen_returns(40, 0.0001),
        "000003": _gen_returns(40, -0.0001),
    }
    nav_rows = []
    for fund_code, rets in returns.items():
        for d, r in zip(dates, rets, strict=True):
            nav_rows.append((fund_code, d, r))
    conn.executemany("INSERT INTO nav_history VALUES (?, ?, ?)", nav_rows)

    conn.commit()
    conn.close()

    # --- 因子库 ---
    conn = sqlite3.connect(factor_db)
    conn.executescript(
        """
        CREATE TABLE stock_factor_values (
            stock_code TEXT, factor_code TEXT, factor_value REAL,
            as_of_date TEXT, source TEXT
        );
        """
    )
    factor_rows = []
    stock_factors = {
        "600519": {"pe": 30, "pb": 10, "roe": 0.30, "dividend_yield": 0.01, "profit_growth": 0.20, "valuation_percentile": 0.50},
        "000858": {"pe": 25, "pb": 7, "roe": 0.25, "dividend_yield": 0.02, "profit_growth": 0.15, "valuation_percentile": 0.45},
        "000568": {"pe": 22, "pb": 6, "roe": 0.28, "dividend_yield": 0.02, "profit_growth": 0.18, "valuation_percentile": 0.40},
        "600887": {"pe": 18, "pb": 4, "roe": 0.20, "dividend_yield": 0.03, "profit_growth": 0.10, "valuation_percentile": 0.35},
        "000333": {"pe": 15, "pb": 3, "roe": 0.22, "dividend_yield": 0.03, "profit_growth": 0.12, "valuation_percentile": 0.30},
        "600036": {"pe": 8, "pb": 1.2, "roe": 0.16, "dividend_yield": 0.05, "profit_growth": 0.08, "valuation_percentile": 0.20},
        "601398": {"pe": 6, "pb": 0.8, "roe": 0.12, "dividend_yield": 0.06, "profit_growth": 0.05, "valuation_percentile": 0.15},
        "601318": {"pe": 10, "pb": 1.0, "roe": 0.14, "dividend_yield": 0.04, "profit_growth": 0.10, "valuation_percentile": 0.25},
        "601088": {"pe": 9, "pb": 1.1, "roe": 0.15, "dividend_yield": 0.07, "profit_growth": 0.06, "valuation_percentile": 0.18},
        "300750": {"pe": 40, "pb": 5, "roe": 0.18, "dividend_yield": 0.005, "profit_growth": 0.30, "valuation_percentile": 0.70},
        "002594": {"pe": 35, "pb": 4, "roe": 0.15, "dividend_yield": 0.005, "profit_growth": 0.25, "valuation_percentile": 0.65},
    }
    for stock_code, factors in stock_factors.items():
        for factor_code, value in factors.items():
            factor_rows.append((stock_code, factor_code, value, "2025-12-31", "fixture"))
    conn.executemany("INSERT INTO stock_factor_values VALUES (?, ?, ?, ?, ?)", factor_rows)

    # --- 概念板块数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS concept_board_stocks (
            concept_code TEXT NOT NULL,
            concept_name TEXT NOT NULL,
            stock_code   TEXT NOT NULL,
            stock_name   TEXT NOT NULL,
            PRIMARY KEY (concept_code, stock_code)
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO concept_board_stocks VALUES (?, ?, ?, ?)",
        [
            ("BK0477", "白酒", "600519", "贵州茅台"),
            ("BK0477", "白酒", "000858", "五粮液"),
            ("BK0477", "白酒", "000568", "泸州老窖"),
            ("BK0477", "白酒", "600887", "伊利股份"),
            ("BK0800", "人工智能", "300750", "宁德时代"),
            ("BK0800", "人工智能", "002594", "比亚迪"),
        ],
    )

    # --- 主营业务构成数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_revenue_composition (
            stock_code    TEXT NOT NULL,
            segment_name  TEXT NOT NULL,
            segment_type  TEXT NOT NULL,
            revenue_pct   REAL,
            report_date   TEXT NOT NULL,
            PRIMARY KEY (stock_code, segment_name, segment_type, report_date)
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO stock_revenue_composition VALUES (?, ?, ?, ?, ?)",
        [
            # 贵州茅台：白酒95%、其他5%
            ("600519", "白酒", "按产品", 95.0, "2025-12-31"),
            ("600519", "其他业务", "按产品", 5.0, "2025-12-31"),
            # 五粮液：白酒90%
            ("000858", "白酒", "按产品", 90.0, "2025-12-31"),
            ("000858", "其他", "按产品", 10.0, "2025-12-31"),
            # 招商银行：银行业务100%
            ("600036", "银行业务", "按行业", 100.0, "2025-12-31"),
        ],
    )

    # --- 基金经理数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fund_managers (
            fund_code     TEXT NOT NULL,
            fund_name     TEXT,
            manager_name  TEXT NOT NULL,
            start_date    TEXT,
            end_date      TEXT,
            tenure_days   INTEGER,
            return_pct    REAL,
            aum_yi        REAL,
            is_current    INTEGER DEFAULT 1,
            PRIMARY KEY (fund_code, manager_name, start_date)
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO fund_managers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # 000001 消费龙头：经理张三，任职2000天（>5年），回报80%
            ("000001", "消费龙头基金", "张三", "2020-01-01", "", 2000, 80.0, 50.0, 1),
            # 000002 科技成长：经理李四，任职200天（<1年），回报-5%
            ("000002", "科技成长基金", "李四", "2025-06-01", "", 200, -5.0, 30.0, 1),
            # 000003 红利防守：经理王五，任职1000天，回报20%
            ("000003", "红利防守基金", "王五", "2023-01-01", "", 1000, 20.0, 80.0, 1),
            # 000004 无经理数据（测试缺失场景）
        ],
    )

    # --- 三大财务报表数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_financial_statements (
            stock_code    TEXT NOT NULL,
            report_type   TEXT NOT NULL,
            report_date   TEXT NOT NULL,
            revenue       REAL,
            net_profit    REAL,
            gross_margin  REAL,
            net_margin    REAL,
            roe           REAL,
            debt_ratio    REAL,
            free_cashflow REAL,
            revenue_yoy   REAL,
            profit_yoy    REAL,
            PRIMARY KEY (stock_code, report_type, report_date)
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO stock_financial_statements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # 贵州茅台 600519：毛利率91%，自由现金流+400亿，负债率25%
            ("600519", "利润表", "2025-12-31", 1500, 750, 91.5, 50.0, None, None, None, 15.0, 18.0),
            ("600519", "资产负债表", "2025-12-31", None, None, None, None, 32.0, 25.0, None, None, None),
            ("600519", "现金流量表", "2025-12-31", None, None, None, None, None, None, 400.0, None, None),
            # 招商银行 600036：毛利率（银行特殊），负债率90%
            ("600036", "资产负债表", "2025-12-31", None, None, None, None, 16.0, 90.0, None, None, None),
            ("600036", "现金流量表", "2025-12-31", None, None, None, None, None, None, -100.0, None, None),
        ],
    )

    # --- 北向资金数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS northbound_capital (
            stock_code    TEXT NOT NULL,
            trade_date    TEXT NOT NULL,
            hold_shares   REAL,
            hold_value    REAL,
            hold_pct      REAL,
            net_buy      REAL,
            PRIMARY KEY (stock_code, trade_date)
        );
        CREATE TABLE IF NOT EXISTS northbound_daily (
            trade_date    TEXT PRIMARY KEY,
            sh_net_flow    REAL,
            sz_net_flow    REAL,
            total_net_flow REAL,
            sh_balance    REAL,
            sz_balance    REAL
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO northbound_capital VALUES (?, ?, ?, ?, ?, ?)",
        [
            # 贵州茅台：北向净流入8亿
            ("600519", "2026-01-15", 9500, 1800000, 7.5, 80000),
            # 招商银行：北向净流出6亿
            ("600036", "2026-01-15", 12000, 600000, 4.0, -60000),
        ],
    )

    # --- 龙虎榜数据 ---
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dragon_tiger_list (
            stock_code    TEXT NOT NULL,
            stock_name    TEXT,
            trade_date    TEXT NOT NULL,
            reason        TEXT,
            close_price   REAL,
            change_pct    REAL,
            net_buy      REAL,
            buy_amount    REAL,
            sell_amount   REAL,
            PRIMARY KEY (stock_code, trade_date, reason)
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO dragon_tiger_list VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # 贵州茅台上龙虎榜，净买入2亿
            ("600519", "贵州茅台", "2026-01-15", "日涨幅偏离值达7%", 1800, 7.2, 20000, 30000, 10000),
        ],
    )

    conn.commit()
    conn.close()

    return source_db, factor_db


# ============================================================
# 测试 1：主题加载
# ============================================================
def test_load_themes() -> None:
    themes = load_themes()
    assert "AI" in themes
    assert "consumer" in themes
    assert "dividend_defense" in themes
    assert "innovation_drug" in themes

    ai = themes["AI"]
    assert ai["name"]
    assert ai["belief"]
    assert len(ai["logic_chain"]) >= 2
    assert "chain_links" in ai
    assert len(ai["chain_links"]) >= 2
    for link in ai["chain_links"].values():
        assert "industry_keywords" in link
        assert "stock_keywords" in link
    assert ai["defense_theme"] == "dividend_defense"

    defense = themes["dividend_defense"]
    assert defense["defense_theme"] is None


# ============================================================
# 测试 2：产业链匹配
# ============================================================
def test_match_theme() -> None:
    themes = load_themes()
    consumer = themes["consumer"]

    holdings = [
        {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 0.12, "industry_name": "食品饮料"},
        {"stock_code": "000858", "stock_name": "五粮液", "weight": 0.10, "industry_name": "食品饮料"},
        {"stock_code": "000333", "stock_name": "美的集团", "weight": 0.04, "industry_name": "家电"},
        {"stock_code": "600036", "stock_name": "招商银行", "weight": 0.03, "industry_name": "银行"},
    ]

    result = match_theme(holdings, consumer)
    assert result["match_pct"] > 0
    assert "食品饮料" in result["chain_breakdown"]
    assert "家电" in result["chain_breakdown"]
    assert result["chain_breakdown"]["食品饮料"] > result["chain_breakdown"]["家电"]
    assert len(result["matched_stocks"]) > 0
    assert result["matched_stocks"][0]["stock_name"] == "贵州茅台"


def test_match_theme_empty_holdings() -> None:
    themes = load_themes()
    result = match_theme([], themes["AI"])
    assert result["match_pct"] == 0
    assert result["matched_stocks"] == []


# ============================================================
# 测试 3：估值计算
# ============================================================
def test_calculate_valuation() -> None:
    holdings = [
        {"weight": 0.12, "pe": 30, "pb": 10, "roe": 0.30, "dividend_yield": 0.01,
         "profit_growth": 0.20, "val_pct": 0.50},
        {"weight": 0.10, "pe": 25, "pb": 7, "roe": 0.25, "dividend_yield": 0.02,
         "profit_growth": 0.15, "val_pct": 0.45},
    ]

    result = calculate_valuation(holdings)
    assert result["weighted_pe"] is not None
    assert result["weighted_pe"] > 0
    assert result["weighted_pb"] is not None
    assert result["weighted_roe"] is not None
    # ROE 存储为小数，显示乘 100
    assert result["weighted_roe"] > 20
    assert result["weighted_val_pct"] is not None
    assert result["peg"] is not None
    assert result["peg"] > 0
    assert result["val_judge"] in {"偏低", "合理", "偏贵", "极度偏贵"}
    assert "suggested_max_weight" in result
    assert result["suggested_max_weight"] > 0


def test_calculate_valuation_empty() -> None:
    result = calculate_valuation([])
    assert result["weighted_pe"] is None
    assert result["peg"] is None
    assert result["val_judge"] == "—"


def test_suggest_max_weight() -> None:
    assert suggest_max_weight({"weighted_val_pct": 90}) == 5.0
    assert suggest_max_weight({"weighted_val_pct": 75}) == 8.0
    assert suggest_max_weight({"weighted_val_pct": 50}) == 12.0
    assert suggest_max_weight({"weighted_val_pct": None}) == 12.0


# ============================================================
# 测试 4：组合构建
# ============================================================
def test_build_portfolio() -> None:
    candidates = [
        {
            "fund_code": "000001",
            "fund_name": "消费龙头基金",
            "match_pct": 90,
            "valuation": {"weighted_val_pct": 50, "weighted_pe": 25},
            "trend": {"trend": "stable"},
            "corr_with": {},
        },
        {
            "fund_code": "000002",
            "fund_name": "消费均衡基金",
            "match_pct": 30,
            "valuation": {"weighted_val_pct": 40, "weighted_pe": 20},
            "trend": {"trend": "stable"},
            "corr_with": {},
        },
    ]
    defense = {
        "fund_code": "000003",
        "fund_name": "红利防守基金",
        "match_pct": 95,
        "valuation": {"weighted_dividend": 5.5},
    }

    result = build_portfolio(candidates, defense)
    assert len(result["selected_funds"]) >= 1
    assert result["selected_funds"][0]["fund_code"] == "000001"
    assert result["defense_position"] is not None
    assert result["defense_position"]["fund_code"] == "000003"
    assert result["cash_pct"] >= 0
    assert result["total_invested"] > 0
    # 认知仓位 25% + 防守 10% = 35%，现金 65%
    assert result["total_invested"] <= 36


def test_build_portfolio_no_defense() -> None:
    candidates = [
        {
            "fund_code": "000001",
            "fund_name": "基金A",
            "match_pct": 80,
            "valuation": {"weighted_val_pct": 50},
            "trend": {"trend": "stable"},
            "corr_with": {},
        },
    ]
    result = build_portfolio(candidates, None)
    assert len(result["selected_funds"]) == 1
    assert result["defense_position"] is None
    assert result["cash_pct"] > 50


def test_build_portfolio_high_correlation_skips() -> None:
    candidates = [
        {
            "fund_code": "000001",
            "fund_name": "基金A",
            "match_pct": 80,
            "valuation": {"weighted_val_pct": 50},
            "trend": {"trend": "stable"},
            "corr_with": {},
        },
        {
            "fund_code": "000002",
            "fund_name": "基金B",
            "match_pct": 70,
            "valuation": {"weighted_val_pct": 50},
            "trend": {"trend": "stable"},
            "corr_with": {},
        },
    ]
    # 模拟 000001 已选，与 000002 高度相关
    candidates[0]["corr_with"] = {"000002": 0.95}
    result = build_portfolio(candidates, None)
    assert len(result["selected_funds"]) == 1
    assert result["selected_funds"][0]["fund_code"] == "000001"


def test_calculate_overlap() -> None:
    holdings_a = [
        {"stock_code": "600519", "weight": 0.12},
        {"stock_code": "000858", "weight": 0.10},
        {"stock_code": "600036", "weight": 0.03},
    ]
    holdings_b = [
        {"stock_code": "600519", "weight": 0.08},
        {"stock_code": "000858", "weight": 0.06},
        {"stock_code": "300750", "weight": 0.05},
    ]
    result = calculate_overlap(holdings_a, holdings_b)
    assert result["common_count"] == 2
    assert result["overlap_a_pct"] > 0
    assert result["overlap_b_pct"] > 0
    assert "judge" in result


# ============================================================
# 测试 5：产业链图谱加载
# ============================================================
def test_load_chains() -> None:
    chains = load_chains()
    assert "AI" in chains
    assert "consumer" in chains
    assert "dividend_defense" in chains
    assert "innovation_drug" in chains

    ai = chains["AI"]
    assert ai["judgment"]["belief"]
    assert ai["judgment"]["portfolio_role"] == "core"
    assert len(ai["chain"]) >= 2
    for link in ai["chain"]:
        assert "name" in link
        assert "stocks" in link
        assert "industry_keywords" in link
        assert "certainty" in link
        assert "elasticity" in link
    assert ai["defense"] == "dividend_defense"


def test_get_all_stock_keywords() -> None:
    chains = load_chains()
    ai = chains["AI"]
    kws = get_all_stock_keywords(ai)
    # 应该包含非exclude环节的股票
    assert "寒武纪" in kws
    assert "中际旭创" in kws
    # 应用层被exclude，不应包含其股票
    assert len(kws) > 0


# ============================================================
# 测试 6：预期差计算
# ============================================================
def test_calculate_link_expectation_gap() -> None:
    link = {
        "name": "测试环节",
        "stocks": ["贵州茅台"],
        "industry_keywords": ["食品饮料"],
        "certainty": "high",
        "elasticity": "low",
    }
    holdings = [
        {"stock_name": "贵州茅台", "industry_name": "食品饮料", "weight": 0.12,
         "pe": 30, "profit_growth": 0.20, "val_pct": 0.50, "roe": 0.30, "dividend_yield": 0.01},
        {"stock_name": "五粮液", "industry_name": "食品饮料", "weight": 0.10,
         "pe": 25, "profit_growth": 0.15, "val_pct": 0.45, "roe": 0.25, "dividend_yield": 0.02},
    ]
    result = calculate_link_expectation_gap(link, holdings)
    assert result["link_name"] == "测试环节"
    assert result["pe"] is not None
    assert result["peg"] is not None
    assert result["val_pct"] is not None
    assert result["expectation_gap"] in {"positive", "neutral", "negative"}
    assert result["score"] > 0
    assert result["matched_weight"] > 0
    assert len(result["matched_stocks"]) > 0


def test_calculate_link_expectation_gap_no_match() -> None:
    link = {
        "name": "测试环节",
        "stocks": ["不存在的股票"],
        "industry_keywords": ["不存在的行业"],
        "certainty": "medium",
        "elasticity": "medium",
    }
    holdings = [
        {"stock_name": "贵州茅台", "industry_name": "食品饮料", "weight": 0.12,
         "pe": 30, "profit_growth": 0.20, "val_pct": 0.50},
    ]
    result = calculate_link_expectation_gap(link, holdings)
    assert result["expectation_gap"] == "unknown"
    assert result["score"] == 0
    assert result["matched_weight"] == 0


# ============================================================
# 测试 7：端到端冒烟测试（自动推导5步引擎）
# ============================================================
def test_cognition_engine_smoke(tmp_path: Path) -> None:
    source_db, factor_db = _make_cognition_db(tmp_path)

    engine = CognitionEngine(source_db, factor_db)
    try:
        # 产业链图谱加载
        chains = engine.get_chains()
        assert "consumer" in chains
        assert "AI" in chains

        # 自动推导5步
        result = engine.run("consumer")

        # 第1步：判断
        step1 = result["step1_judgment"]
        assert step1["direction"] == "consumer"
        assert step1["belief"]
        assert step1["portfolio_role"] == "base"
        assert step1["role_weight_range"] == [10, 20]

        # 第2步：受益链路
        step2 = result["step2_chain"]
        assert len(step2) >= 1
        for link in step2:
            assert "link_name" in link
            assert "expectation_gap" in link
            assert "score" in link
            assert "benefit_logic" in link
        # 应该按score降序排列
        scores = [lk["score"] for lk in step2]
        assert scores == sorted(scores, reverse=True)

        # 第3步：预期差分析
        step3 = result["step3_expectation_gap"]
        assert "positive" in step3
        assert "neutral" in step3
        assert "negative" in step3
        assert "summary" in step3
        assert step3["best_link"] is not None or len(step2) == 0

        # 第4步：基金匹配
        step4 = result["step4_fund_matches"]
        # 000001消费龙头基金应该匹配度最高
        assert len(step4) >= 1
        assert step4[0]["fund_code"] == "000001"
        assert step4[0]["match_pct"] > 50
        # 估值字段存在
        assert step4[0]["valuation"]["weighted_pe"] is not None
        # 趋势：从 2025-06-30 到 2025-12-31 加仓
        assert step4[0]["trend"]["trend"] == "increasing"

        # 第5步：组合构建
        step5 = result["step5_portfolio"]
        assert step5["role"] == "base"
        assert step5["total_cognition_weight"] > 0
        assert step5["total_cognition_weight"] <= 20
        assert step5["cash_pct"] >= 0
        assert step5["rationale"]
        # 防守基金
        assert step5["defense_position"] is not None
        assert step5["defense_position"]["fund_code"] == "000003"
        assert step5["defense_weight_pct"] == 10
        # 认知验证（新增）
        assert "step5_validation" in result
        assert "supporting_evidence" in result["step5_validation"]
        assert "opposing_evidence" in result["step5_validation"]
        assert "verdict" in result["step5_validation"]

        # === 测试不带 belief_link（默认分析所有环节）===
        assert result["belief_link"] is None
        assert result["conviction"] == "medium"
        assert result["available_links"]  # consumer 有可选环节

        # === 测试带 belief_link 和 conviction ===
        result_ai = engine.run("AI", belief_link="光模块/连接", conviction="high")
        assert result_ai["belief_link"] == "光模块/连接"
        assert result_ai["conviction"] == "high"
        assert "光模块/连接" in result_ai["available_links"]
        # high 信心取仓位上限（AI role_weight_range=[15, 25]）
        assert result_ai["step5_portfolio"]["total_cognition_weight"] == 25.0

        # low 信心取下限的一半（consumer role_weight_range=[10, 20] -> 5.0）
        result_low = engine.run("consumer", conviction="low")
        assert result_low["conviction"] == "low"
        assert result_low["step5_portfolio"]["total_cognition_weight"] == 5.0
    finally:
        engine.close()


def test_cognition_engine_custom_direction(tmp_path: Path) -> None:
    """自定义方向走动态产业链构建，不再抛 KeyError。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # 无匹配行业的自定义方向：返回空环节但不报错
        result = engine.run("nonexistent")
        assert result["direction"] == "nonexistent"
        assert result["available_links"] == []
        assert result["step1_judgment"]["belief"] == "我相信nonexistent方向"
        assert result["step1_judgment"]["portfolio_role"] == "satellite"
        assert result["conviction"] == "medium"

        # 命中行业的自定义方向（测试库含"食品饮料"行业）
        result_food = engine.run("食品")
        assert result_food["direction"] == "食品"
        assert "食品饮料" in result_food["available_links"]
        assert result_food["step1_judgment"]["belief"] == "我相信食品方向"
    finally:
        engine.close()


# ============================================================
# 新增测试：估值门禁、认知验证、完整7步流程
# ============================================================


def test_estimate_price_in_years() -> None:
    """隐含增长年限估算。"""
    # PE=100, growth=50%, reasonable_pe=20 -> ln(5)/ln(1.5) ≈ 3.97
    years = estimate_price_in_years(100, 0.5, reasonable_pe=20)
    assert years is not None
    assert 3.5 < years < 4.5

    # PE 已经低于 reasonable_pe -> 0 年
    assert estimate_price_in_years(15, 0.3) == 0.0

    # 无效输入 -> None
    assert estimate_price_in_years(None, 0.5) is None
    assert estimate_price_in_years(100, None) is None
    assert estimate_price_in_years(100, 0) is None
    assert estimate_price_in_years(-1, 0.5) is None


def test_check_hard_limits_pass() -> None:
    """估值通过硬约束。"""
    valuation = {
        "weighted_val_pct": 50,
        "peg": 1.2,
        "weighted_pe": 30,
        "weighted_roe": 18,
    }
    hard_limits = {
        "max_valuation_percentile": 85,
        "max_peg": 2.0,
        "max_pe": 80,
        "min_roe": 12,
    }
    result = check_hard_limits(valuation, hard_limits)
    assert result["passed"] is True
    assert result["violations"] == []


def test_check_hard_limits_fail() -> None:
    """估值违反硬约束。"""
    valuation = {
        "weighted_val_pct": 90,
        "peg": 2.5,
        "weighted_pe": 100,
        "weighted_roe": 8,
    }
    hard_limits = {
        "max_valuation_percentile": 85,
        "max_peg": 2.0,
        "max_pe": 80,
        "min_roe": 12,
    }
    result = check_hard_limits(valuation, hard_limits)
    assert result["passed"] is False
    assert len(result["violations"]) == 4
    assert any("估值分位" in v for v in result["violations"])
    assert any("PEG" in v for v in result["violations"])
    assert any("PE" in v for v in result["violations"])
    assert any("ROE" in v for v in result["violations"])


def test_check_hard_limits_empty() -> None:
    """无硬约束时始终通过。"""
    result = check_hard_limits({"weighted_pe": 999}, {})
    assert result["passed"] is True


def test_validate_cognition_positive() -> None:
    """认知验证：正预期差 + 低估值 -> 认知有效。"""
    link_analysis = [
        {
            "link_name": "光模块",
            "expectation_gap": "positive",
            "growth_pct": 40,
            "roe": 20,
            "peg": 0.8,
            "score": 80,
        },
    ]
    fund_matches = [
        {
            "fund_code": "000001",
            "match_pct": 35,
            "valuation": {
                "weighted_val_pct": 40,
                "weighted_pe": 25,
                "weighted_growth": 40,
                "price_in_years": 0.5,
            },
            "trend": {"trend": "increasing"},
        },
    ]
    judgment = {"valuation_tolerance": "medium", "belief": "AI基础设施"}

    result = validate_cognition(link_analysis, fund_matches, judgment)
    assert result["verdict"] in ("认知有效", "认知基本有效")
    assert len(result["supporting_evidence"]) > 0
    assert result["evidence_counts"]["supporting"] > 0


def test_validate_cognition_negative() -> None:
    """认知验证：负预期差 + 高估值 -> 认知存疑。"""
    link_analysis = [
        {
            "link_name": "芯片设计",
            "expectation_gap": "negative",
            "growth_pct": 5,
            "roe": 8,
            "peg": 3.0,
            "score": 20,
        },
    ]
    fund_matches = [
        {
            "fund_code": "000001",
            "match_pct": 55,
            "valuation": {
                "weighted_val_pct": 90,
                "weighted_pe": 80,
                "weighted_growth": 15,
                "price_in_years": 4.0,
            },
            "trend": {"trend": "decreasing"},
        },
    ]
    judgment = {"valuation_tolerance": "low", "belief": "芯片设计"}

    result = validate_cognition(link_analysis, fund_matches, judgment)
    assert result["verdict"] == "认知存疑"
    assert len(result["opposing_evidence"]) > 0


def test_cognition_engine_hard_limits_gating(tmp_path: Path) -> None:
    """估值门禁：超过硬约束的基金被拦截。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # 用极低的 max_valuation_percentile 强制拦截
        result = engine.run("consumer", max_valuation_percentile=0.1)
        # 所有基金都应该被拦截（val_pct > 0.1%）
        gated = result.get("gated_out_funds", [])
        assert len(gated) > 0
        # 每个被拦截的基金都有 violations
        for f in gated:
            assert len(f["violations"]) > 0
            assert any("估值分位" in v for v in f["violations"])
    finally:
        engine.close()


def test_cognition_engine_risk_tolerance(tmp_path: Path) -> None:
    """风险偏好影响防守仓位和仓位总量。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result_mod = engine.run("consumer", risk_tolerance="moderate")
        result_con = engine.run("consumer", risk_tolerance="conservative")
        result_agg = engine.run("consumer", risk_tolerance="aggressive")

        # 保守 > 适中 > 激进的防守仓位
        assert result_con["step5_portfolio"]["defense_weight_pct"] == 15.0
        assert result_mod["step5_portfolio"]["defense_weight_pct"] == 10.0
        assert result_agg["step5_portfolio"]["defense_weight_pct"] == 5.0
    finally:
        engine.close()


def test_cognition_engine_step5_validation_exists(tmp_path: Path) -> None:
    """7步流程输出包含认知验证结果。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("AI")
        assert "step5_validation" in result
        val = result["step5_validation"]
        assert "supporting_evidence" in val
        assert "opposing_evidence" in val
        assert "warnings" in val
        assert "verdict" in val
        assert "verdict_detail" in val
        assert "evidence_counts" in val
    finally:
        engine.close()


def test_cognition_engine_overlap_analysis(tmp_path: Path) -> None:
    """组合输出包含持仓重叠度分析。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        portfolio = result["step5_portfolio"]
        assert "overlap_analysis" in portfolio
        overlap = portfolio["overlap_analysis"]
        # overlap_analysis 是 dict 形式：max_overlap_pct / high_overlap_pairs / pairs
        if overlap.get("max_overlap_pct", 0) > 0:
            assert "high_overlap_pairs" in overlap
            assert isinstance(overlap["high_overlap_pairs"], list)
    finally:
        engine.close()


def test_cognition_engine_hard_limits_in_step1(tmp_path: Path) -> None:
    """Step 1 输出包含 hard_limits。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("AI")
        step1 = result["step1_judgment"]
        assert "hard_limits" in step1
        assert "max_valuation_percentile" in step1["hard_limits"]
        assert "max_peg" in step1["hard_limits"]
        # AI chain 的默认 max_valuation_percentile 是 95
        assert step1["hard_limits"]["max_valuation_percentile"] == 95
    finally:
        engine.close()


def test_cognition_engine_gate_in_fund_matches(tmp_path: Path) -> None:
    """基金匹配结果包含估值门禁结果。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        for fund in result["step4_fund_matches"]:
            assert "gate" in fund
            assert "passed" in fund["gate"]
            assert "violations" in fund["gate"]
    finally:
        engine.close()


# ============================================================
# 概念板块测试
# ============================================================


def test_search_concepts(tmp_path: Path) -> None:
    """概念板块搜索。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # 搜索"白" -> 应该找到"白酒"板块
        results = engine.search_concepts("白")
        assert len(results) >= 1
        assert any(r["name"] == "白酒" for r in results)
        baijiu = [r for r in results if r["name"] == "白酒"][0]
        assert baijiu["code"] == "BK0477"
        assert baijiu["stock_count"] == 4

        # 搜索"人工" -> 应该找到"人工智能"板块
        results = engine.search_concepts("人工")
        assert len(results) >= 1
        assert results[0]["name"] == "人工智能"
    finally:
        engine.close()


def test_get_concept_stocks(tmp_path: Path) -> None:
    """获取概念板块成分股。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        stocks = engine.get_concept_stocks("BK0477")
        assert len(stocks) == 4
        names = [s["name"] for s in stocks]
        assert "贵州茅台" in names
        assert "五粮液" in names
    finally:
        engine.close()


def test_run_concept(tmp_path: Path) -> None:
    """用概念板块运行认知转化。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run_concept("BK0477", "白酒", conviction="high")
        assert result["direction"] == "白酒"
        assert "error" not in result
        # 应该能匹配到持有白酒股的基金
        assert "step4_fund_matches" in result
        # 000001 消费龙头持有贵州茅台/五粮液等 -> 应该匹配
        if result["step4_fund_matches"]:
            assert result["step4_fund_matches"][0]["fund_code"] == "000001"
        # 组合方案
        assert "step5_portfolio" in result
        assert "step5_validation" in result
    finally:
        engine.close()


def test_run_concept_no_data(tmp_path: Path) -> None:
    """概念板块无数据时返回错误。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run_concept("BK9999", "不存在")
        assert "error" in result
    finally:
        engine.close()


# ============================================================
# 横截面估值测试
# ============================================================


def test_cross_sectional_valuation(tmp_path: Path) -> None:
    """基金匹配结果包含横截面估值对比。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        for fund in result["step4_fund_matches"]:
            val = fund["valuation"]
            # 横截面估值字段应该存在（如果行业PE中位数有数据）
            if "industry_pe_median" in val:
                assert val["industry_pe_median"] > 0
                assert "pe_premium_pct" in val
                assert "cross_sectional_judge" in val
    finally:
        engine.close()


def test_industry_pe_medians(tmp_path: Path) -> None:
    """行业PE中位数计算。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        medians = engine._get_industry_pe_medians(conn)
        # 测试库有"食品饮料"行业的股票（茅台30/五粮液25/老窖22/伊利18）
        # 中位数 = (22+25)/2 = 23.5
        assert "食品饮料" in medians
        assert 20 < medians["食品饮料"] < 27
        # "银行"行业（招商8/工商6）中位数 = 7
        assert "银行" in medians
        assert 5 < medians["银行"] < 9
    finally:
        engine.close()


# ============================================================
# 收入暴露分析测试
# ============================================================


def test_load_revenue_exposure(tmp_path: Path) -> None:
    """主营业务构成数据加载。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        exposure = engine._load_revenue_exposure(conn)
        # 贵州茅台有"白酒"95%
        assert "600519" in exposure
        assert "白酒" in exposure["600519"]
        assert exposure["600519"]["白酒"] == 95.0
        # 五粮液有"白酒"90%
        assert "000858" in exposure
        assert exposure["000858"]["白酒"] == 90.0
        # 招商银行有"银行业务"100%
        assert "600036" in exposure
        assert exposure["600036"]["银行业务"] == 100.0
    finally:
        engine.close()


def test_match_with_revenue_exposure(tmp_path: Path) -> None:
    """收入暴露加权匹配 vs 纯关键词匹配。

    有收入数据的股票按营收占比打折（茅台95% -> 暴露度0.95），
    无收入数据的股票回退到关键词匹配（暴露度1.0）。
    因此有收入数据时 match_pct 应低于无收入数据时。
    """
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        holdings = [
            {"stock_code": "600519", "stock_name": "贵州茅台", "industry_name": "食品饮料", "weight": 0.12},
            {"stock_code": "000858", "stock_name": "五粮液", "industry_name": "食品饮料", "weight": 0.10},
            {"stock_code": "000568", "stock_name": "泸州老窖", "industry_name": "食品饮料", "weight": 0.08},
        ]
        stock_kws = ["贵州茅台", "五粮液", "泸州老窖"]
        ind_kws = ["白酒", "食品饮料"]

        # 有收入暴露数据：茅台0.95 + 五粮液0.90 + 老窖(无数据,回退1.0)
        exposure = engine._load_revenue_exposure(conn)
        match_with = engine._match_fund_to_chain(holdings, stock_kws, ind_kws, exposure)
        # 0.12*0.95 + 0.10*0.90 + 0.08*1.0 = 0.114 + 0.09 + 0.08 = 0.284
        # total = 0.30, match_pct = 0.284/0.30*100 = 94.7
        assert match_with["match_pct"] < 100.0  # 不是100%，因为收入暴露打了折

        # 无收入暴露数据：纯关键词匹配 -> 100%
        match_without = engine._match_fund_to_chain(holdings, stock_kws, ind_kws, None)
        assert match_without["match_pct"] == 100.0  # 三只都命中关键词

        # 有收入暴露的 match_pct 应该更低
        assert match_with["match_pct"] < match_without["match_pct"]
    finally:
        engine.close()


def test_revenue_exposure_no_match_fallback(tmp_path: Path) -> None:
    """有收入数据但不匹配关键词时不命中（不回退到关键词）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        # 招商银行有收入数据"银行业务"，但不匹配"白酒"关键词
        holdings = [
            {"stock_code": "600036", "stock_name": "招商银行", "industry_name": "银行", "weight": 0.10},
        ]
        exposure = engine._load_revenue_exposure(conn)

        # 有收入数据但不匹配 -> 不命中
        match = engine._match_fund_to_chain(holdings, ["白酒"], ["白酒"], exposure)
        assert match["match_pct"] == 0.0

        # 无收入数据时回退到关键词 -> 也不命中（"招商银行"不含"白酒"）
        match_no_data = engine._match_fund_to_chain(holdings, ["白酒"], ["白酒"], None)
        assert match_no_data["match_pct"] == 0.0
    finally:
        engine.close()


def test_engine_uses_revenue_exposure(tmp_path: Path) -> None:
    """引擎 run() 使用收入暴露数据。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # 运行 consumer 认知分析
        result = engine.run("consumer")
        # 应该能匹配到消费基金
        assert len(result["step4_fund_matches"]) >= 1
        # 000001 消费龙头应该匹配度最高
        assert result["step4_fund_matches"][0]["fund_code"] == "000001"
    finally:
        engine.close()


# ============================================================
# 证据溯源机制测试
# ============================================================

_VALID_SOURCE_TYPES = {"chain_analysis", "market_data", "estimate", "trend", "fund_report"}


def test_evidence_traceability_structure(tmp_path: Path) -> None:
    """每条证据都是结构化对象，含 claim/source/source_type。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        # 检查所有证据列表
        for key in ("supporting_evidence", "opposing_evidence", "warnings"):
            for ev in validation[key]:
                assert isinstance(ev, dict), f"{key} 中的证据应该是dict"
                assert "claim" in ev, "证据缺少claim字段"
                assert "source" in ev, "证据缺少source字段"
                assert "source_type" in ev, "证据缺少source_type字段"
                assert ev["source_type"] in _VALID_SOURCE_TYPES, \
                    f"source_type={ev['source_type']} 不在合法集合中"
                assert isinstance(ev["claim"], str) and len(ev["claim"]) > 0
                assert isinstance(ev["source"], str) and len(ev["source"]) > 0
    finally:
        engine.close()


def test_evidence_has_raw_data(tmp_path: Path) -> None:
    """证据包含原始数据（raw_data），可追溯到具体数值。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        # 至少有一些证据包含 raw_data
        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
            + validation["warnings"]
        )
        has_raw_data = any("raw_data" in ev for ev in all_evidence)
        assert has_raw_data, "应该至少有一条证据包含raw_data"

        # 检查 raw_data 是 dict
        for ev in all_evidence:
            if "raw_data" in ev:
                assert isinstance(ev["raw_data"], dict)
    finally:
        engine.close()


def test_evidence_has_context(tmp_path: Path) -> None:
    """证据包含上下文说明（context）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
            + validation["warnings"]
        )
        # 至少有一些证据包含 context
        has_context = any("context" in ev for ev in all_evidence)
        assert has_context, "应该至少有一条证据包含context"
    finally:
        engine.close()


def test_reasoning_chain_exists(tmp_path: Path) -> None:
    """验证结果包含推理链（reasoning_chain）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        assert "reasoning_chain" in validation
        chain = validation["reasoning_chain"]
        assert isinstance(chain, list)
        assert len(chain) >= 2  # 至少有"认知输入"和"综合判断"

        # 检查推理链结构
        for node in chain:
            assert "step" in node
            assert "description" in node
            assert "evidence_ref" in node

        # 第一个节点应该是"认知输入"
        assert chain[0]["step"] == "认知输入"
        # 最后一个节点应该是"综合判断"
        assert chain[-1]["step"] == "综合判断"
    finally:
        engine.close()


def test_evidence_source_type_diversity(tmp_path: Path) -> None:
    """证据来源类型应该有多样性（不止一种source_type）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
        )
        if all_evidence:
            source_types = {ev["source_type"] for ev in all_evidence}
            # 至少有2种不同的来源类型
            assert len(source_types) >= 2, \
                f"证据来源类型应该有多样性，实际只有: {source_types}"
    finally:
        engine.close()


# ============================================================
# 多空辩论测试（借鉴 TradingAgents）
# ============================================================


def test_debate_exists(tmp_path: Path) -> None:
    """验证结果包含多空辩论（debate）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        assert "debate" in validation
        debate = validation["debate"]
        assert isinstance(debate, list)
        assert len(debate) > 0

        # 检查辩论结构
        for round_data in debate:
            assert "round" in round_data
            assert "bull_argument" in round_data
            assert "bear_rebuttal" in round_data
            assert "bull_response" in round_data
            # bull_argument 应该是结构化证据
            assert "claim" in round_data["bull_argument"]
    finally:
        engine.close()


def test_debate_has_rebuttals(tmp_path: Path) -> None:
    """辩论中应该有Bear反驳（不是所有round的bear_rebuttal都是None）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]
        debate = validation["debate"]

        # 至少有一个round有bear_rebuttal
        has_rebuttal = any(r["bear_rebuttal"] is not None for r in debate)
        # 如果没有rebuttal，说明所有证据都是利好无争议，这也是合理的
        # 但大多数情况下应该有争议
        if validation["evidence_counts"]["opposing"] > 0:
            assert has_rebuttal, "有反对证据时，辩论中应该有Bear反驳"
    finally:
        engine.close()


# ============================================================
# 认知反馈闭环测试（借鉴 Vibe-Trading）
# ============================================================


def test_cognition_feedback_exists(tmp_path: Path) -> None:
    """验证结果包含认知反馈（cognition_feedback）。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]

        assert "cognition_feedback" in validation
        feedback = validation["cognition_feedback"]

        assert "original_belief" in feedback
        assert "validation_verdict" in feedback
        assert "correction_suggestions" in feedback
        assert "adjusted_belief" in feedback

        assert isinstance(feedback["correction_suggestions"], list)
        assert feedback["original_belief"] != ""
        assert feedback["validation_verdict"] == validation["verdict"]
    finally:
        engine.close()


def test_cognition_feedback_suggestions(tmp_path: Path) -> None:
    """认知反馈包含修正建议。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        feedback = result["step5_validation"]["cognition_feedback"]

        # 如果verdict不是"认知有效"，应该有修正建议
        if feedback["validation_verdict"] != "认知有效":
            assert len(feedback["correction_suggestions"]) > 0, \
                "非有效认知应该有修正建议"

        # adjusted_belief 应该与 original_belief 不同（除非认知有效）
        if feedback["validation_verdict"] != "认知有效":
            assert feedback["adjusted_belief"] != feedback["original_belief"]
    finally:
        engine.close()


# ============================================================
# 投资风格认知测试（借鉴 AI Hedge Fund）
# ============================================================


def test_value_investing_chain(tmp_path: Path) -> None:
    """价值投资认知链。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        chains = engine.get_chains()
        assert "value_investing" in chains
        chain = chains["value_investing"]

        # 价值投资要求低估值
        assert chain["judgment"]["valuation_tolerance"] == "low"
        assert chain["judgment"]["hard_limits"]["max_pe"] == 20
        assert chain["judgment"]["hard_limits"]["min_roe"] == 15
        assert chain["judgment"]["hard_limits"]["max_valuation_percentile"] == 40
        assert chain["judgment"]["portfolio_role"] == "core"
    finally:
        engine.close()


def test_growth_investing_chain(tmp_path: Path) -> None:
    """成长投资认知链。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        chains = engine.get_chains()
        assert "growth_investing" in chains
        chain = chains["growth_investing"]

        # 成长投资容忍高估值
        assert chain["judgment"]["valuation_tolerance"] == "high"
        assert chain["judgment"]["hard_limits"]["min_growth"] == 25
        assert chain["judgment"]["hard_limits"]["max_valuation_percentile"] == 90
        assert chain["judgment"]["portfolio_role"] == "satellite"
    finally:
        engine.close()


def test_contrarian_investing_chain(tmp_path: Path) -> None:
    """逆向投资认知链。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        chains = engine.get_chains()
        assert "contrarian_investing" in chains
        chain = chains["contrarian_investing"]

        # 逆向投资只选底部估值
        assert chain["judgment"]["hard_limits"]["max_valuation_percentile"] == 25
        assert chain["judgment"]["hard_limits"]["min_roe"] == 10
        assert chain["judgment"]["portfolio_role"] == "satellite"
    finally:
        engine.close()


def test_value_investing_run(tmp_path: Path) -> None:
    """价值投资认知分析能正常运行。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("value_investing")
        assert result["direction"] == "value_investing"
        assert "step1_judgment" in result
        assert result["step1_judgment"]["hard_limits"]["max_pe"] == 20
        # 应该有验证结果
        assert "step5_validation" in result
    finally:
        engine.close()


def test_growth_investing_run(tmp_path: Path) -> None:
    """成长投资认知分析能正常运行。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("growth_investing")
        assert result["direction"] == "growth_investing"
        assert "step1_judgment" in result
        assert result["step1_judgment"]["hard_limits"]["max_valuation_percentile"] == 90
    finally:
        engine.close()


def test_investment_style_themes_loaded(tmp_path: Path) -> None:
    """投资风格主题已加载到themes。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        themes = engine.get_themes()
        assert "value_investing" in themes
        assert "growth_investing" in themes
        assert "contrarian_investing" in themes
        assert themes["value_investing"]["name"] == "价值投资"
        assert themes["growth_investing"]["name"] == "成长投资"
        assert themes["contrarian_investing"]["name"] == "逆向投资"
    finally:
        engine.close()


# ============================================================
# 基金经理数据测试
# ============================================================


def test_load_fund_managers(tmp_path: Path) -> None:
    """基金经理数据加载。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        managers = engine._load_fund_managers(conn)
        # 000001 经理张三，任职2000天
        assert "000001" in managers
        assert managers["000001"]["name"] == "张三"
        assert managers["000001"]["tenure_days"] == 2000
        assert managers["000001"]["return_pct"] == 80.0
        # 000002 经理李四，任职200天
        assert "000002" in managers
        assert managers["000002"]["tenure_days"] == 200
    finally:
        engine.close()


def test_fund_manager_in_fund_matches(tmp_path: Path) -> None:
    """基金匹配结果包含基金经理信息。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        # 000001 应该匹配到，且附带经理信息
        for fund in result["step4_fund_matches"]:
            if fund["fund_code"] == "000001":
                assert "manager" in fund
                assert fund["manager"]["name"] == "张三"
                break
    finally:
        engine.close()


def test_fund_manager_evidence_in_validation(tmp_path: Path) -> None:
    """认知验证包含基金经理证据。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]
        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
            + validation["warnings"]
        )
        # 应该有 fund_report 类型的证据（基金经理数据）
        has_fund_report = any(
            e.get("source_type") == "fund_report" for e in all_evidence
        )
        assert has_fund_report, "应该有基金经理相关证据（source_type=fund_report）"

        # 000001 经理张三任职2000天（>5年）-> 支持证据
        has_tenure_support = any(
            "任职" in e.get("claim", "") and "经验丰富" in e.get("claim", "")
            for e in validation["supporting_evidence"]
        )
        assert has_tenure_support, "应该有任职年限的支持证据"

        # 000001 经理张三回报80% -> 支持证据
        has_return_support = any(
            "任职回报" in e.get("claim", "") and "优秀" in e.get("claim", "")
            for e in validation["supporting_evidence"]
        )
        assert has_return_support, "应该有任职回报的支持证据"
    finally:
        engine.close()


def test_fund_manager_no_data_graceful(tmp_path: Path) -> None:
    """无基金经理数据时优雅降级。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # fund_managers 表存在但000004无数据
        conn = engine._get_conn()
        managers = engine._load_fund_managers(conn)
        assert "000004" not in managers  # 无数据
        # 但其他基金有数据
        assert "000001" in managers
    finally:
        engine.close()


# ============================================================
# 三大财务报表测试
# ============================================================


def test_load_financial_depth(tmp_path: Path) -> None:
    """三大报表数据加载。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        fin = engine._load_financial_depth(conn)
        # 贵州茅台 600519
        assert "600519" in fin
        assert fin["600519"]["gross_margin"] == 91.5
        assert fin["600519"]["free_cashflow"] == 400.0
        assert fin["600519"]["debt_ratio"] == 25.0
        # 招商银行 600036
        assert "600036" in fin
        assert fin["600036"]["debt_ratio"] == 90.0
    finally:
        engine.close()


def test_financial_evidence_in_validation(tmp_path: Path) -> None:
    """认知验证包含财务深度证据。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]
        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
            + validation["warnings"]
        )
        # 茅台毛利率91% -> 支持证据
        has_gm = any(
            "毛利率" in e.get("claim", "")
            for e in all_evidence
        )
        assert has_gm, "应该有毛利率证据"

        # 茅台自由现金流+400亿 -> 支持证据
        has_fcf = any(
            "自由现金流" in e.get("claim", "")
            for e in all_evidence
        )
        assert has_fcf, "应该有自由现金流证据"

        # 招商银行负债率90% -> 反对证据
        has_dr = any(
            "资产负债率" in e.get("claim", "") and "90" in e.get("claim", "")
            for e in all_evidence
        )
        assert has_dr, "应该有资产负债率证据"
    finally:
        engine.close()


# ============================================================
# 北向资金测试
# ============================================================


def test_load_northbound_trend(tmp_path: Path) -> None:
    """北向资金数据加载。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        nb = engine._load_northbound_trend(conn)
        # 茅台北向净流入8万 -> 8亿
        assert "600519" in nb
        assert nb["600519"] > 0
        # 招行北向净流出6万 -> 6亿
        assert "600036" in nb
        assert nb["600036"] < 0
    finally:
        engine.close()


def test_northbound_evidence_in_validation(tmp_path: Path) -> None:
    """认知验证包含北向资金证据。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]
        all_evidence = (
            validation["supporting_evidence"]
            + validation["opposing_evidence"]
        )
        # 茅台北向净流入 -> 支持证据
        has_inflow = any(
            "北向" in e.get("claim", "") and "流入" in e.get("claim", "")
            for e in all_evidence
        )
        assert has_inflow, "应该有北向资金流入的支持证据"

        # 招行北向净流出 -> 反对证据
        has_outflow = any(
            "北向" in e.get("claim", "") and "流出" in e.get("claim", "")
            for e in all_evidence
        )
        assert has_outflow, "应该有北向资金流出的反对证据"
    finally:
        engine.close()


# ============================================================
# 龙虎榜测试
# ============================================================


def test_load_dragon_tiger(tmp_path: Path) -> None:
    """龙虎榜数据加载。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        conn = engine._get_conn()
        dt = engine._load_dragon_tiger_stocks(conn)
        # 茅台上龙虎榜
        assert "600519" in dt
        assert dt["600519"]["hit_count"] >= 1
        assert dt["600519"]["net_buy"] is not None
    finally:
        engine.close()


def test_dragon_tiger_evidence_in_validation(tmp_path: Path) -> None:
    """认知验证包含龙虎榜证据。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        result = engine.run("consumer")
        validation = result["step5_validation"]
        all_warnings = validation["warnings"]
        # 茅台上龙虎榜 -> 警告
        has_lhb = any(
            "龙虎榜" in e.get("claim", "")
            for e in all_warnings
        )
        assert has_lhb, "应该有龙虎榜警告"
    finally:
        engine.close()


# ===========================================================================
# 认知选基 v1：百分比单位 + 无候选不产默认防守
# 设计文档 §6：必须修复组合穿透暴露的百分比单位
# 设计文档 §4.4 + §6：无候选时不形成默认防守组合
# ===========================================================================


def test_build_portfolio_no_candidates_returns_no_defense() -> None:
    """无候选时返回空 selected + 100% cash + no_candidates=True，不选防守基金。"""
    result = build_portfolio([], defense_fund=None)
    assert result["selected_funds"] == []
    assert result["defense_position"] is None
    assert result["cash_pct"] == 100.0
    assert result["total_invested"] == 0.0
    assert result["suggested_weight"] == 0.0
    assert result["defense_weight"] == 0.0
    assert result["no_candidates"] is True


def test_build_portfolio_ignores_defense_fund_when_empty() -> None:
    """无候选时即使传入 defense_fund 也应被忽略（短路在 first 行）。"""
    defense = {
        "fund_code": "000999",
        "fund_name": "防守基金",
        "match_pct": 50,
        "valuation": {"weighted_pe": 10},
    }
    result = build_portfolio([], defense_fund=defense)
    # defense_fund 不应被赋 weight（避免展示默认防守组合）
    assert defense.get("weight") is None
    assert result["selected_funds"] == []
    assert result["no_candidates"] is True


def test_calculate_portfolio_metrics_industry_exposure_is_percentage() -> None:
    """行业暴露数字应是百分比（不是 double-percentage）。

    修复前：industry_weights 累加 percentage (e.g. 1.1)，
    `round(v * 100, 1)` 把它转成 110.0
    真实 exposure 1.1% 显示成 110.0% (bug)

    修复后：line 303 改为 round(v, 1)，直接返回 percentage
    """
    import sqlite3

    from app.cognition.portfolio_builder import calculate_portfolio_metrics

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)"
    )

    # selected 基金自身带 holdings（line 250 从 f.get("holdings") 读取）
    selected = [
        {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "match_pct": 80,
            "weight": 25.0,  # 25% 仓位
            "valuation": {"weighted_pe": 20, "weighted_val_pct": 50},
            "holdings": [
                {"stock_code": "600000", "stock_name": "A", "weight": 0.05, "industry_name": "金融", "sector_group": "金融"},
                {"stock_code": "600001", "stock_name": "B", "weight": 0.05, "industry_name": "金融", "sector_group": "金融"},
                {"stock_code": "600002", "stock_name": "C", "weight": 0.05, "industry_name": "科技", "sector_group": "科技"},
            ],
        }
    ]
    metrics = calculate_portfolio_metrics(conn, selected, defense_fund=None, all_holdings=None)

    # 验证 industry_exposure 数字是合理百分比 (0-100)
    # 真实 exposure: 0.25 * 0.05 * 2 = 2.5% (金融), 0.25 * 0.05 = 1.25% (科技)
    industry = {x["name"]: x["weight"] for x in metrics["industry_exposure"]}
    assert "金融" in industry
    assert "科技" in industry
    # 修复 bug 前：金融会显示成 250.0, 科技 125.0（错）
    # 修复后：金融 ~2.5, 科技 ~1.25
    assert industry["金融"] < 10, f"金融 exposure 应 < 10%，实际 {industry['金融']}"
    assert industry["科技"] < 10, f"科技 exposure 应 < 10%，实际 {industry['科技']}"
    assert industry["金融"] > 0
    assert industry["科技"] > 0

    # 同样验证 sector_exposure
    sector = {x["name"]: x["weight"] for x in metrics["sector_exposure"]}
    assert all(v < 10 for v in sector.values()), f"sector 数字应 < 10，实际 {sector}"


def test_calculate_portfolio_metrics_holdings_penetration_is_percentage() -> None:
    """holdings_penetration.weight 应是 percentage（0-100 范围）。"""
    import sqlite3

    from app.cognition.portfolio_builder import calculate_portfolio_metrics

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL)"
    )
    selected = [
        {
            "fund_code": "000001",
            "fund_name": "X",
            "match_pct": 80,
            "weight": 25.0,  # 25% 仓位
            "valuation": {"weighted_pe": 20},
            "holdings": [
                {"stock_code": "600000", "stock_name": "A", "weight": 0.10, "industry_name": "金融", "sector_group": "金融"},
            ],
        }
    ]
    metrics = calculate_portfolio_metrics(conn, selected, defense_fund=None, all_holdings=None)
    hp = metrics["holdings_penetration"]
    assert len(hp) == 1
    # 0.25 * 0.10 = 0.025 (2.5%)
    assert hp[0]["weight"] < 10, f"持仓穿透应是百分比，实际 {hp[0]['weight']}"
    assert hp[0]["weight"] > 0
    assert 0 < hp[0]["weight"] < 5


# ============================================================
# build_fund_candidate_evidence：完整候选证据接口
# ============================================================
def test_build_fund_candidate_evidence_returns_all_candidates(tmp_path: Path) -> None:
    """build_fund_candidate_evidence 返回所有候选，不受 top_n 截断。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        evidence = engine.build_fund_candidate_evidence(
            direction="consumer",
            conviction="medium",
            time_horizon="long",
            risk_tolerance="moderate",
            data_snapshot_id="snap1",
            as_of_date="2026-01-15",
        )
        # 返回所有候选，不受 top_n 截断
        assert len(evidence.all_candidates) > 1
        # scanned_fund_count 等于数据库中基金数
        assert evidence.scanned_fund_count == 3
        # 权重都是 0..1 小数
        for c in evidence.all_candidates:
            assert 0 <= c.matched_holding_weight <= 1
            assert 0 <= c.disclosed_holding_weight <= 1
            assert 0 <= c.normalized_match_pct <= 1
    finally:
        engine.close()


def test_build_fund_candidate_evidence_independent_of_top_n(tmp_path: Path) -> None:
    """build_fund_candidate_evidence 返回完整集合，与 run() 的 top_n 截断无关。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        # run() 只返回 top_n=1
        result = engine.run("consumer", top_n=1)
        assert len(result["step4_fund_matches"]) == 1
        # 但 build_fund_candidate_evidence() 返回完整集合
        evidence = engine.build_fund_candidate_evidence(
            direction="consumer",
            conviction="medium",
            time_horizon="long",
            risk_tolerance="moderate",
            data_snapshot_id="snap1",
            as_of_date="2026-01-15",
        )
        assert len(evidence.all_candidates) > 1
    finally:
        engine.close()


def test_build_fund_candidate_evidence_has_mapped_and_unmapped_counts(tmp_path: Path) -> None:
    """scanned_fund_count == mapped_candidate_count + unmapped_due_to_data_count。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        evidence = engine.build_fund_candidate_evidence(
            direction="consumer",
            conviction="medium",
            time_horizon="long",
            risk_tolerance="moderate",
            data_snapshot_id="snap1",
            as_of_date="2026-01-15",
        )
        assert evidence.mapped_candidate_count > 0
        assert (
            evidence.scanned_fund_count
            == evidence.mapped_candidate_count + evidence.unmapped_due_to_data_count
        )
    finally:
        engine.close()


def test_build_fund_candidate_evidence_has_valuation_gated(tmp_path: Path) -> None:
    """valuation_gated_candidates 是被估值门禁拦下的基金元组。"""
    source_db, factor_db = _make_cognition_db(tmp_path)
    engine = CognitionEngine(source_db, factor_db)
    try:
        evidence = engine.build_fund_candidate_evidence(
            direction="consumer",
            conviction="medium",
            time_horizon="long",
            risk_tolerance="moderate",
            data_snapshot_id="snap1",
            as_of_date="2026-01-15",
        )
        assert isinstance(evidence.valuation_gated_candidates, tuple)
    finally:
        engine.close()


# ============================================================
# 推荐池组合构建测试
# ============================================================
def test_portfolio_never_allocates_outside_recommended_universe() -> None:
    """组合只能从推荐池中选基。"""
    from app.cognition.portfolio_builder import build_portfolio

    rec_a = {"fund_code": "A", "match_pct": 80, "valuation": {}, "trend": {}, "holdings": []}
    rec_b = {"fund_code": "B", "match_pct": 60, "valuation": {}, "trend": {}, "holdings": []}
    proposal = build_portfolio(
        recommended_candidates=[rec_a, rec_b],
        defense_fund=None,
        recommendation_run_ids=["frr_1"],
    )
    assert {p["fund_code"] for p in proposal["holdings"]} <= {"A", "B"}
    assert proposal["selection_source"] == "recommended_universe"
    assert proposal["status"] == "complete"
    assert proposal["recommendation_run_ids"] == ["frr_1"]


def test_empty_recommendation_universe_is_not_fake_portfolio() -> None:
    """推荐池为空时返回 insufficient_recommendations，不生成假组合。"""
    from app.cognition.portfolio_builder import build_portfolio

    proposal = build_portfolio(
        recommended_candidates=[],
        defense_fund=None,
        recommendation_run_ids=["frr_1"],
    )
    assert proposal["status"] == "insufficient_recommendations"
    assert proposal["holdings"] == []
    assert proposal["selection_source"] == "recommended_universe"
