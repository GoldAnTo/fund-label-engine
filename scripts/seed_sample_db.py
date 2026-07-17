"""Seed a small example SQLite database for the fund label engine.

Usage:
    python scripts/seed_sample_db.py data/sample_fund_data.sqlite

Produces 8 funds that cover all 7 cognition directions:
- 000001: 消费方向（股票型，数据充足）
- 000002: 数据不足（缺持仓、行业、经理等）-> 数据不足 + 人工复核
- 000003: 不被支持的基金类型（债券型）-> 不会进入批量
- 000004: AI/半导体方向（股票型）
- 000005: 创新药方向（股票型）
- 000006: 红利防守方向（股票型）
- 000007: 成长投资方向（股票型）
- 000008: 价值投资方向（混合型-偏股）
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS fund_profiles (
        fund_code TEXT PRIMARY KEY,
        fund_name TEXT NOT NULL,
        fund_type TEXT NOT NULL,
        inception_date TEXT,
        fund_company TEXT,
        fund_size REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nav_history (
        fund_code TEXT NOT NULL,
        nav_date TEXT NOT NULL,
        nav REAL,
        adjusted_nav REAL,
        daily_return REAL,
        PRIMARY KEY (fund_code, nav_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_stock_holdings (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        weight REAL NOT NULL,
        market TEXT,
        PRIMARY KEY (fund_code, report_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_industry_allocations (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        industry TEXT NOT NULL,
        weight REAL NOT NULL,
        PRIMARY KEY (fund_code, report_date, industry)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_manager_links (
        fund_code TEXT NOT NULL,
        manager_name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        tenure_years REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fee_structures (
        fund_code TEXT PRIMARY KEY,
        management_fee REAL,
        custody_fee REAL,
        sales_service_fee REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_positions (
        fund_code TEXT NOT NULL,
        report_date TEXT NOT NULL,
        equity_position REAL,
        PRIMARY KEY (fund_code, report_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_factors (
        stock_code TEXT NOT NULL,
        factor_date TEXT NOT NULL,
        pb REAL,
        roe REAL,
        dividend_yield REAL,
        revenue_growth REAL,
        profit_growth REAL,
        market_cap_bucket TEXT,
        valuation_percentile REAL,
        style TEXT,
        PRIMARY KEY (stock_code, factor_date)
    )
    """,
)


def seed(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)

        # ===== 基金基本信息 =====
        conn.executemany(
            "INSERT INTO fund_profiles VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("000001", "样例消费股票", "股票型", "2015-01-01", "样例基金公司", 180.0),
                ("000002", "样例数据不全混合", "混合型-偏股", "2020-01-01", "样例基金公司", 12.0),
                ("000003", "样例债券基金", "债券型", "2018-01-01", "样例基金公司", 50.0),
                ("000004", "样例科技股票", "股票型", "2019-06-01", "样例基金公司", 45.0),
                ("000005", "样例医药股票", "股票型", "2017-03-01", "样例基金公司", 30.0),
                ("000006", "样例红利股票", "股票型", "2016-01-01", "样例基金公司", 60.0),
                ("000007", "样例成长股票", "股票型", "2018-09-01", "样例基金公司", 35.0),
                ("000008", "样例价值混合", "混合型-偏股", "2015-05-01", "样例基金公司", 25.0),
            ],
        )

        # ===== NAV 历史 =====
        conn.executemany(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            [
                # 000001 消费
                ("000001", "2026-06-18", 1.20, 1.20, 0.010),
                ("000001", "2026-06-19", 1.19, 1.19, -0.008),
                ("000001", "2026-06-20", 1.21, 1.21, 0.017),
                ("000001", "2026-06-21", 1.22, 1.22, 0.008),
                ("000001", "2026-06-22", 1.21, 1.21, -0.008),
                # 000004 科技/AI
                ("000004", "2026-06-18", 1.52, 1.52, 0.013),
                ("000004", "2026-06-19", 1.55, 1.55, 0.020),
                ("000004", "2026-06-20", 1.53, 1.53, -0.013),
                ("000004", "2026-06-21", 1.56, 1.56, 0.020),
                ("000004", "2026-06-22", 1.54, 1.54, -0.013),
                # 000005 医药
                ("000005", "2026-06-18", 1.31, 1.31, 0.008),
                ("000005", "2026-06-19", 1.30, 1.30, -0.008),
                ("000005", "2026-06-20", 1.32, 1.32, 0.015),
                ("000005", "2026-06-21", 1.33, 1.33, 0.008),
                ("000005", "2026-06-22", 1.32, 1.32, -0.008),
                # 000006 红利
                ("000006", "2026-06-18", 1.10, 1.10, 0.005),
                ("000006", "2026-06-19", 1.11, 1.11, 0.009),
                ("000006", "2026-06-20", 1.10, 1.10, -0.009),
                ("000006", "2026-06-21", 1.11, 1.11, 0.009),
                ("000006", "2026-06-22", 1.12, 1.12, 0.009),
                # 000007 成长
                ("000007", "2026-06-18", 1.42, 1.42, 0.014),
                ("000007", "2026-06-19", 1.40, 1.40, -0.014),
                ("000007", "2026-06-20", 1.43, 1.43, 0.021),
                ("000007", "2026-06-21", 1.45, 1.45, 0.014),
                ("000007", "2026-06-22", 1.44, 1.44, -0.007),
                # 000008 价值
                ("000008", "2026-06-18", 1.15, 1.15, 0.004),
                ("000008", "2026-06-19", 1.16, 1.16, 0.009),
                ("000008", "2026-06-20", 1.15, 1.15, -0.009),
                ("000008", "2026-06-21", 1.16, 1.16, 0.009),
                ("000008", "2026-06-22", 1.17, 1.17, 0.009),
            ],
        )

        report_date = "2026-03-31"

        # ===== 持仓数据 =====
        # 000001 消费（保留现有）
        holdings_000001 = [
            ("600519", "贵州茅台", 0.153),
            ("000858", "五粮液", 0.125),
            ("000568", "泸州老窖", 0.111),
            ("600887", "伊利股份", 0.098),
            ("300750", "宁德时代", 0.084),
            ("002594", "比亚迪", 0.07),
            ("601318", "中国平安", 0.056),
            ("600036", "招商银行", 0.056),
            ("000333", "美的集团", 0.049),
            ("600276", "恒瑞医药", 0.049),
        ]
        # 000004 科技/AI
        holdings_000004 = [
            ("688256", "寒武纪", 0.111),
            ("688041", "海光信息", 0.099),
            ("688008", "澜起科技", 0.086),
            ("688981", "中芯国际", 0.099),
            ("600584", "长电科技", 0.062),
            ("002156", "通富微电", 0.062),
            ("300308", "中际旭创", 0.123),
            ("300394", "天孚通信", 0.074),
            ("300502", "新易盛", 0.074),
            ("002463", "沪电股份", 0.062),
        ]
        # 000005 医药
        holdings_000005 = [
            ("600276", "恒瑞医药", 0.131),
            ("688235", "百济神州", 0.105),
            ("01801", "信达生物", 0.078),
            ("603259", "药明康德", 0.118),
            ("002821", "凯莱英", 0.092),
            ("301259", "康龙化成", 0.078),
            ("300347", "泰格医药", 0.078),
            ("600436", "片仔癀", 0.065),
            ("000538", "云南白药", 0.052),
            ("300015", "爱尔眼科", 0.052),
        ]
        # 000006 红利
        holdings_000006 = [
            ("600900", "长江电力", 0.131),
            ("601088", "中国神华", 0.118),
            ("00883", "中国海洋石油", 0.105),
            ("601398", "工商银行", 0.092),
            ("601939", "建设银行", 0.092),
            ("601288", "农业银行", 0.078),
            ("601318", "中国平安", 0.065),
            ("600036", "招商银行", 0.065),
            ("601628", "中国人寿", 0.052),
            ("600028", "中国石化", 0.052),
        ]
        # 000007 成长
        holdings_000007 = [
            ("300750", "宁德时代", 0.146),
            ("002594", "比亚迪", 0.12),
            ("601012", "隆基绿能", 0.106),
            ("300274", "阳光电源", 0.093),
            ("600089", "特变电工", 0.066),
            ("601877", "五矿资本", 0.053),
            ("002129", "中环股份", 0.08),
            ("002460", "赣锋锂业", 0.066),
            ("600438", "通威股份", 0.066),
            ("300316", "晶盛机电", 0.053),
        ]
        # 000008 价值
        holdings_000008 = [
            ("000002", "万科", 0.113),
            ("600048", "保利发展", 0.099),
            ("600036", "招商银行", 0.113),
            ("601166", "兴业银行", 0.099),
            ("601318", "中国平安", 0.085),
            ("601398", "工商银行", 0.085),
            ("600000", "浦发银行", 0.071),
            ("601668", "中国建筑", 0.071),
            ("600585", "海螺水泥", 0.057),
            ("000651", "格力电器", 0.057),
        ]

        # HK 股票代码标记为 "HK" 市场，其余为 "A"
        hk_stock_codes = {"00883", "01801"}
        all_holdings = (
            [("000001", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000001]
            + [("000004", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000004]
            + [("000005", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000005]
            + [("000006", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000006]
            + [("000007", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000007]
            + [("000008", report_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in holdings_000008]
        )
        conn.executemany(
            "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
            all_holdings,
        )

        # ===== 历史持仓（2025-12-31），用于计算持仓趋势 =====
        prev_date = "2025-12-31"
        # 000001 消费：白酒权重小幅上升 -> stable
        prev_000001 = [
            ("600519", "贵州茅台", 0.13),
            ("000858", "五粮液", 0.115),
            ("000568", "泸州老窖", 0.101),
            ("600887", "伊利股份", 0.101),
            ("300750", "宁德时代", 0.101),
            ("002594", "比亚迪", 0.086),
            ("601318", "中国平安", 0.058),
            ("600036", "招商银行", 0.058),
            ("000333", "美的集团", 0.05),
            ("600276", "恒瑞医药", 0.05),
        ]
        # 000004 科技/AI：AI股权重更低 -> increasing
        prev_000004 = [
            ("688256", "寒武纪", 0.071),
            ("688041", "海光信息", 0.071),
            ("688008", "澜起科技", 0.071),
            ("688981", "中芯国际", 0.085),
            ("600584", "长电科技", 0.071),
            ("002156", "通富微电", 0.071),
            ("300308", "中际旭创", 0.085),
            ("300394", "天孚通信", 0.057),
            ("300502", "新易盛", 0.057),
            ("002463", "沪电股份", 0.057),
            ("600519", "贵州茅台", 0.085),
            ("601318", "中国平安", 0.071),
        ]
        # 000005 医药：医药股权重更低 -> increasing
        prev_000005 = [
            ("600276", "恒瑞医药", 0.091),
            ("688235", "百济神州", 0.076),
            ("01801", "信达生物", 0.061),
            ("603259", "药明康德", 0.076),
            ("002821", "凯莱英", 0.061),
            ("301259", "康龙化成", 0.061),
            ("300347", "泰格医药", 0.061),
            ("600436", "片仔癀", 0.061),
            ("000538", "云南白药", 0.061),
            ("300015", "爱尔眼科", 0.046),
            ("600519", "贵州茅台", 0.106),
            ("601318", "中国平安", 0.091),
        ]
        # 000006 红利：红利股权重相近 -> stable
        prev_000006 = [
            ("600900", "长江电力", 0.131),
            ("601088", "中国神华", 0.118),
            ("00883", "中国海洋石油", 0.105),
            ("601398", "工商银行", 0.092),
            ("601939", "建设银行", 0.092),
            ("601288", "农业银行", 0.078),
            ("601318", "中国平安", 0.065),
            ("600036", "招商银行", 0.065),
            ("601628", "中国人寿", 0.052),
            ("600028", "中国石化", 0.052),
        ]
        # 000007 成长：成长股权重更高 -> decreasing
        prev_000007 = [
            ("300750", "宁德时代", 0.158),
            ("002594", "比亚迪", 0.134),
            ("601012", "隆基绿能", 0.121),
            ("300274", "阳光电源", 0.109),
            ("600089", "特变电工", 0.061),
            ("601877", "五矿资本", 0.049),
            ("002129", "中环股份", 0.073),
            ("002460", "赣锋锂业", 0.061),
            ("600438", "通威股份", 0.049),
            ("300316", "晶盛机电", 0.036),
        ]
        # 000008 价值：价值股权重相近 -> stable
        prev_000008 = [
            ("000002", "万科", 0.113),
            ("600048", "保利发展", 0.099),
            ("600036", "招商银行", 0.113),
            ("601166", "兴业银行", 0.099),
            ("601318", "中国平安", 0.085),
            ("601398", "工商银行", 0.085),
            ("600000", "浦发银行", 0.071),
            ("601668", "中国建筑", 0.071),
            ("600585", "海螺水泥", 0.057),
            ("000651", "格力电器", 0.057),
        ]
        prev_holdings = (
            [("000001", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000001]
            + [("000004", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000004]
            + [("000005", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000005]
            + [("000006", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000006]
            + [("000007", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000007]
            + [("000008", prev_date, c, n, w, "HK" if c in hk_stock_codes else "A") for c, n, w in prev_000008]
        )
        conn.executemany(
            "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
            prev_holdings,
        )

        # ===== 行业配置 =====
        # 每只基金在 report_date 与 prev_date 两个报告期使用相同的行业配置，合计约 0.85
        industry_rows = [
            # 000001 消费
            ("000001", report_date, "食品饮料", 0.50),
            ("000001", report_date, "医药", 0.05),
            ("000001", report_date, "家电", 0.05),
            ("000001", report_date, "非银金融", 0.06),
            ("000001", report_date, "汽车", 0.04),
            ("000001", report_date, "电池", 0.05),
            ("000001", report_date, "电力设备", 0.05),
            ("000001", report_date, "银行", 0.05),
            # 000004 科技/AI
            ("000004", report_date, "半导体", 0.35),
            ("000004", report_date, "通信设备", 0.22),
            ("000004", report_date, "电子元件", 0.10),
            ("000004", report_date, "消费电子", 0.10),
            ("000004", report_date, "计算机设备", 0.08),
            # 000005 医药
            ("000005", report_date, "化学制药", 0.25),
            ("000005", report_date, "生物制品", 0.20),
            ("000005", report_date, "医疗服务", 0.15),
            ("000005", report_date, "中药", 0.12),
            ("000005", report_date, "医疗器械", 0.08),
            ("000005", report_date, "医药商业", 0.05),
            # 000006 红利
            ("000006", report_date, "银行", 0.25),
            ("000006", report_date, "电力", 0.18),
            ("000006", report_date, "煤炭", 0.12),
            ("000006", report_date, "保险", 0.08),
            ("000006", report_date, "石油石化", 0.12),
            ("000006", report_date, "证券", 0.10),
            # 000007 成长
            ("000007", report_date, "新能源", 0.30),
            ("000007", report_date, "有色金属", 0.15),
            ("000007", report_date, "化工", 0.10),
            ("000007", report_date, "电气设备", 0.12),
            ("000007", report_date, "金融", 0.08),
            ("000007", report_date, "机械", 0.10),
            # 000008 价值
            ("000008", report_date, "银行", 0.26),
            ("000008", report_date, "房地产", 0.15),
            ("000008", report_date, "建筑", 0.12),
            ("000008", report_date, "保险", 0.10),
            ("000008", report_date, "建材", 0.08),
            ("000008", report_date, "家电", 0.07),
            ("000008", report_date, "水泥", 0.07),
        ]
        # 历史报告期使用相同的行业配置
        industry_rows += [
            (fund, prev_date, ind, w) for (fund, _, ind, w) in industry_rows
        ]
        conn.executemany(
            "INSERT INTO fund_industry_allocations VALUES (?, ?, ?, ?)",
            industry_rows,
        )

        # ===== 基金经理 =====
        conn.executemany(
            "INSERT INTO fund_manager_links VALUES (?, ?, ?, ?, ?)",
            [
                ("000001", "张三", "2020-01-01", None, 6.2),
                ("000002", "李四", "2024-01-01", None, 1.5),
                ("000004", "王五", "2021-06-01", None, 4.8),
                ("000005", "赵六", "2019-03-01", None, 7.1),
                ("000006", "孙七", "2018-01-01", None, 8.2),
                ("000007", "周八", "2020-09-01", None, 5.5),
                ("000008", "吴九", "2017-05-01", None, 9.0),
            ],
        )

        # ===== 费率 =====
        conn.executemany(
            "INSERT INTO fee_structures VALUES (?, ?, ?, ?)",
            [
                ("000001", 0.010, 0.002, None),
                ("000002", 0.015, 0.0025, None),
                ("000004", 0.012, 0.002, None),
                ("000005", 0.015, 0.0025, None),
                ("000006", 0.008, 0.002, None),
                ("000007", 0.012, 0.002, None),
                ("000008", 0.010, 0.002, None),
            ],
        )

        # ===== 股票仓位 =====
        conn.executemany(
            "INSERT INTO fund_positions VALUES (?, ?, ?)",
            [
                ("000001", report_date, 0.89),
                ("000004", report_date, 0.92),
                ("000005", report_date, 0.88),
                ("000006", report_date, 0.85),
                ("000007", report_date, 0.90),
                ("000008", report_date, 0.90),
                # 历史仓位
                ("000001", prev_date, 0.88),
                ("000004", prev_date, 0.90),
                ("000005", prev_date, 0.89),
                ("000006", prev_date, 0.89),
                ("000007", prev_date, 0.91),
                ("000008", prev_date, 0.89),
            ],
        )

        # ===== 股票因子数据 =====
        # factor_date 统一使用报告期，字段：pb, roe, dividend_yield,
        # revenue_growth, profit_growth, market_cap_bucket, valuation_percentile, style
        factor_date = "2026-03-31"

        # 消费类股票：PE 中等(20-40)，ROE 高(20-35%)，增速稳定(10-20%)，估值分位中等(30-60)
        consumer_factors = [
            ("600519", "贵州茅台", 8.5, 0.30, 0.010, 0.15, 0.18, "large_cap", 0.45, "consumer_quality"),
            ("000858", "五粮液", 5.2, 0.22, 0.020, 0.12, 0.14, "large_cap", 0.40, "consumer_quality"),
            ("000568", "泸州老窖", 6.0, 0.25, 0.020, 0.15, 0.20, "large_cap", 0.42, "consumer_quality"),
            ("600887", "伊利股份", 3.5, 0.20, 0.030, 0.10, 0.12, "large_cap", 0.35, "consumer_quality"),
            ("000333", "美的集团", 3.8, 0.24, 0.030, 0.12, 0.15, "large_cap", 0.38, "consumer_quality"),
            ("000651", "格力电器", 2.2, 0.22, 0.050, 0.08, 0.10, "large_cap", 0.25, "consumer_quality"),
        ]

        # 科技/AI 类股票：PE 较高(40-80)，ROE 中等(10-20%)，营收增速高(30-60%)，估值分位较高(60-85)
        ai_factors = [
            ("688256", "寒武纪", 12.0, 0.05, 0.000, 0.60, 0.80, "mid_cap", 0.82, "quality_growth"),
            ("688041", "海光信息", 10.5, 0.12, 0.000, 0.45, 0.55, "mid_cap", 0.78, "quality_growth"),
            ("688008", "澜起科技", 8.0, 0.15, 0.005, 0.35, 0.40, "mid_cap", 0.70, "quality_growth"),
            ("688981", "中芯国际", 4.5, 0.08, 0.010, 0.30, 0.25, "large_cap", 0.65, "quality_growth"),
            ("600584", "长电科技", 3.5, 0.10, 0.010, 0.35, 0.30, "mid_cap", 0.62, "quality_growth"),
            ("002156", "通富微电", 3.8, 0.08, 0.005, 0.40, 0.35, "mid_cap", 0.68, "quality_growth"),
            ("300308", "中际旭创", 9.5, 0.18, 0.005, 0.55, 0.70, "mid_cap", 0.80, "quality_growth"),
            ("300394", "天孚通信", 8.5, 0.16, 0.010, 0.50, 0.60, "mid_cap", 0.75, "quality_growth"),
            ("300502", "新易盛", 7.5, 0.14, 0.010, 0.50, 0.55, "mid_cap", 0.72, "quality_growth"),
            ("002463", "沪电股份", 6.0, 0.15, 0.010, 0.40, 0.45, "mid_cap", 0.70, "quality_growth"),
        ]

        # 医药类股票：PE 较高(30-60)，ROE 中等(10-20%)，增速中高(15-30%)，估值分位中等(40-65)
        pharma_factors = [
            ("600276", "恒瑞医药", 7.0, 0.15, 0.005, 0.20, 0.25, "large_cap", 0.55, "quality_growth"),
            ("688235", "百济神州", 8.0, -0.05, 0.000, 0.30, 0.40, "mid_cap", 0.60, "quality_growth"),
            ("01801", "信达生物", 5.5, -0.03, 0.000, 0.25, 0.35, "mid_cap", 0.50, "quality_growth"),
            ("603259", "药明康德", 5.0, 0.18, 0.010, 0.25, 0.30, "large_cap", 0.45, "quality_growth"),
            ("002821", "凯莱英", 6.5, 0.16, 0.005, 0.28, 0.32, "mid_cap", 0.50, "quality_growth"),
            ("301259", "康龙化成", 4.5, 0.12, 0.005, 0.22, 0.28, "mid_cap", 0.48, "quality_growth"),
            ("300347", "泰格医药", 5.0, 0.14, 0.010, 0.18, 0.22, "mid_cap", 0.45, "quality_growth"),
            ("600436", "片仔癀", 9.0, 0.20, 0.010, 0.15, 0.18, "mid_cap", 0.55, "quality_growth"),
            ("000538", "云南白药", 3.5, 0.12, 0.020, 0.10, 0.12, "mid_cap", 0.40, "quality_growth"),
            ("300015", "爱尔眼科", 8.5, 0.15, 0.005, 0.25, 0.30, "mid_cap", 0.58, "quality_growth"),
        ]

        # 红利防守类股票：PE 低(5-15)，ROE 稳定(10-15%)，增速低(0-8%)，估值分位低(10-35)
        dividend_factors = [
            ("600900", "长江电力", 2.8, 0.15, 0.035, 0.05, 0.06, "large_cap", 0.25, "dividend_steady"),
            ("601088", "中国神华", 1.5, 0.14, 0.060, 0.03, 0.05, "large_cap", 0.20, "dividend_steady"),
            ("00883", "中国海洋石油", 1.8, 0.15, 0.050, 0.06, 0.08, "large_cap", 0.22, "dividend_steady"),
            ("601398", "工商银行", 0.8, 0.12, 0.055, 0.02, 0.03, "large_cap", 0.15, "high_dividend_financial"),
            ("601939", "建设银行", 0.75, 0.13, 0.060, 0.03, 0.04, "large_cap", 0.18, "high_dividend_financial"),
            ("601288", "农业银行", 0.70, 0.12, 0.060, 0.04, 0.05, "large_cap", 0.15, "high_dividend_financial"),
            ("601318", "中国平安", 1.2, 0.13, 0.040, 0.05, 0.08, "large_cap", 0.30, "high_dividend_financial"),
            ("600036", "招商银行", 1.3, 0.16, 0.045, 0.06, 0.10, "large_cap", 0.28, "high_dividend_financial"),
            ("601628", "中国人寿", 1.5, 0.10, 0.030, 0.05, 0.07, "large_cap", 0.25, "high_dividend_financial"),
            ("600028", "中国石化", 0.9, 0.10, 0.060, 0.02, 0.03, "large_cap", 0.18, "dividend_steady"),
        ]

        # 成长类股票：PE 高(30-70)，ROE 中等(8-18%)，增速高(25-50%)，估值分位较高(55-80)
        growth_factors = [
            ("300750", "宁德时代", 5.0, 0.15, 0.005, 0.35, 0.40, "large_cap", 0.60, "quality_growth"),
            ("002594", "比亚迪", 4.5, 0.12, 0.000, 0.40, 0.50, "large_cap", 0.65, "quality_growth"),
            ("601012", "隆基绿能", 2.5, 0.10, 0.010, 0.25, 0.20, "large_cap", 0.55, "quality_growth"),
            ("300274", "阳光电源", 6.0, 0.18, 0.005, 0.45, 0.55, "mid_cap", 0.70, "quality_growth"),
            ("600089", "特变电工", 1.5, 0.12, 0.030, 0.30, 0.35, "mid_cap", 0.50, "quality_growth"),
            ("601877", "五矿资本", 1.2, 0.10, 0.020, 0.25, 0.30, "mid_cap", 0.55, "quality_growth"),
            ("002129", "中环股份", 2.0, 0.08, 0.010, 0.35, 0.30, "mid_cap", 0.60, "quality_growth"),
            ("002460", "赣锋锂业", 2.5, 0.10, 0.010, 0.30, 0.35, "mid_cap", 0.58, "quality_growth"),
            ("600438", "通威股份", 1.8, 0.12, 0.010, 0.35, 0.40, "mid_cap", 0.55, "quality_growth"),
            ("300316", "晶盛机电", 3.5, 0.15, 0.010, 0.40, 0.45, "mid_cap", 0.65, "quality_growth"),
        ]

        # 价值类股票：PE 低(5-12)，ROE 中等(8-15%)，增速低(0-5%)，估值分位低(10-30)
        value_factors = [
            ("000002", "万科", 0.70, 0.08, 0.050, 0.00, -0.05, "large_cap", 0.10, "deep_value"),
            ("600048", "保利发展", 0.80, 0.10, 0.040, 0.02, 0.00, "large_cap", 0.15, "deep_value"),
            ("601166", "兴业银行", 0.65, 0.12, 0.060, 0.03, 0.04, "large_cap", 0.12, "high_dividend_financial"),
            ("600000", "浦发银行", 0.50, 0.09, 0.050, 0.02, 0.03, "large_cap", 0.10, "high_dividend_financial"),
            ("601668", "中国建筑", 0.70, 0.11, 0.040, 0.05, 0.06, "large_cap", 0.15, "deep_value"),
            ("600585", "海螺水泥", 0.90, 0.10, 0.040, 0.03, 0.05, "large_cap", 0.20, "deep_value"),
        ]

        all_factors = (
            consumer_factors
            + ai_factors
            + pharma_factors
            + dividend_factors
            + growth_factors
            + value_factors
        )
        conn.executemany(
            "INSERT INTO stock_factors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (code, factor_date, pb, roe, div_yield, rev_growth,
                 profit_growth, cap_bucket, val_pct, style)
                for (code, _name, pb, roe, div_yield, rev_growth,
                     profit_growth, cap_bucket, val_pct, style) in all_factors
            ],
        )

        conn.commit()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: seed_sample_db.py <db_path>", file=sys.stderr)
        return 2
    seed(argv[0])
    print(f"seeded: {argv[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
