"""推荐效果校准测试：用真实基金数据验证 Top 3 推荐是否符合投资直觉。

每个基准用例包含：
- 主题方向（theme_key）+ 投资参数
- 预期主动基金 Top 3（fund_code 列表）
- 预期 ETF/指数基金 Top 3（fund_code 列表）
- 偏差原因记录（校准后填写）

数据源：seed_sample_db.py 生成 8 只主动基金 + 3 只 ETF/指数基金（本文件追加）。
运行后如果实际结果与预期不符，测试会输出详细偏差信息，
便于定位问题：主题暴露不准、产品分类错、数据过期、权重不合理等。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# 确保 scripts/ 目录可导入
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from seed_sample_db import seed  # noqa: E402

from app.cognition.engine import CognitionEngine  # noqa: E402
from app.services.fund_recommendation import (  # noqa: E402
    FundRecommendationEngine,
    FundRecommendationPolicy,
)


# ============================================================
# 数据源：seed 8 只主动基金 + 追加 3 只 ETF/指数基金
# ============================================================
_ETF_FUNDS = [
    {
        "fund_code": "159001",
        "fund_name": "消费ETF",
        "fund_type": "ETF",
        "inception_date": "2015-01-01",
        "fund_company": "样例基金公司",
        "fund_size": 50.0,
        "holdings": [
            ("600519", "贵州茅台", 0.20),
            ("000858", "五粮液", 0.15),
            ("600887", "伊利股份", 0.12),
            ("000568", "泸州老窖", 0.10),
        ],
        "industries": [("食品饮料", 0.57), ("电力设备", 0.08)],
        "manager": ("ETF管理团队", 365, 0.08, 1),
    },
    {
        "fund_code": "159002",
        "fund_name": "芯片ETF",
        "fund_type": "ETF",
        "inception_date": "2019-06-01",
        "fund_company": "样例基金公司",
        "fund_size": 40.0,
        "holdings": [
            ("688256", "寒武纪", 0.12),
            ("688981", "中芯国际", 0.10),
            ("300308", "中际旭创", 0.10),
            ("300394", "天孚通信", 0.08),
        ],
        "industries": [("半导体", 0.32), ("通信设备", 0.20)],
        "manager": ("ETF管理团队", 365, 0.06, 1),
    },
    {
        "fund_code": "159003",
        "fund_name": "红利指数",
        "fund_type": "指数型",
        "inception_date": "2016-01-01",
        "fund_company": "样例基金公司",
        "fund_size": 55.0,
        "holdings": [
            ("600900", "长江电力", 0.12),
            ("601088", "中国神华", 0.10),
            ("601398", "工商银行", 0.08),
            ("601318", "中国平安", 0.06),
        ],
        "industries": [("银行", 0.22), ("电力", 0.16), ("煤炭", 0.10)],
        "manager": ("指数管理团队", 730, 0.05, 1),
    },
    {
        "fund_code": "159004",
        "fund_name": "白酒ETF",
        "fund_type": "ETF",
        "inception_date": "2015-01-01",
        "fund_company": "样例基金公司",
        "fund_size": 80.0,
        "holdings": [
            ("600519", "贵州茅台", 0.25),
            ("000858", "五粮液", 0.20),
            ("000568", "泸州老窖", 0.15),
            ("600809", "山西汾酒", 0.10),
            ("002304", "洋河股份", 0.08),
        ],
        "industries": [("白酒", 0.78), ("食品饮料", 0.85)],
        "manager": ("ETF管理团队", 365, 0.12, 1),
    },
]


def _add_etf_funds(db_path: Path) -> None:
    """向 source DB 追加 4 只 ETF/指数基金。"""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        for f in _ETF_FUNDS:
            # fund_profiles
            conn.execute(
                "INSERT OR REPLACE INTO fund_profiles "
                "(fund_code, fund_name, fund_type, inception_date, fund_company, fund_size) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (f["fund_code"], f["fund_name"], f["fund_type"],
                 f["inception_date"], f["fund_company"], f["fund_size"]),
            )
            # fund_stock_holdings（当期 + 上期，用于趋势计算）
            for stock_code, stock_name, weight in f["holdings"]:
                for report_date in ("2026-03-31", "2025-12-31"):
                    conn.execute(
                        "INSERT INTO fund_stock_holdings "
                        "(fund_code, report_date, stock_code, stock_name, weight, market) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (f["fund_code"], report_date, stock_code, stock_name, weight, "A股"),
                    )
            # fund_industry_allocations
            for ind_name, weight in f["industries"]:
                conn.execute(
                    "INSERT INTO fund_industry_allocations "
                    "(fund_code, report_date, industry, weight) "
                    "VALUES (?, ?, ?, ?)",
                    (f["fund_code"], "2026-03-31", ind_name, weight),
                )
            # fund_manager_links
            mgr = f["manager"]
            conn.execute(
                "INSERT INTO fund_manager_links "
                "(fund_code, manager_name, start_date, end_date, tenure_years) "
                "VALUES (?, ?, ?, ?, ?)",
                (f["fund_code"], mgr[0], "2024-01-01", None, mgr[1] / 365),
            )
            # nav_history
            for d in range(18, 23):
                conn.execute(
                    "INSERT INTO nav_history "
                    "(fund_code, nav_date, daily_return) "
                    "VALUES (?, ?, ?)",
                    (f["fund_code"], f"2026-06-{d:02d}", 0.001),
                )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 基准用例定义
# ============================================================
AS_OF_DATE = "2026-03-31"
SNAPSHOT_ID = "snap_calibration"

# 默认推荐策略配置（与 private_equity_growth_v1.yaml 对齐）
DEFAULT_POLICY = FundRecommendationPolicy(
    method_version="fund_recommendation_v1",
    source_method_version="fund_candidate_evidence_v0",
    minimum_target_holding_weight=0.10,
    maximum_holding_age_days=180,
    active_fund_limit=3,
    etf_or_index_limit=3,
    alternative_limit=2,
    weights={
        "theme_exposure": 0.55,
        "thesis_alignment": 0.15,
        "risk_return": 0.15,
        "fund_quality": 0.15,
    },
)


@pytest.fixture(scope="module")
def source_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """创建带 ETF 基金的 source DB（模块级共享）。"""
    db_path = tmp_path_factory.mktemp("calib") / "source.sqlite"
    seed(db_path)
    _add_etf_funds(db_path)
    return db_path


@pytest.fixture(scope="module")
def engine(source_db: Path) -> CognitionEngine:
    """创建认知引擎（模块级共享）。"""
    factor_db = _PROJECT_ROOT / "data" / "stock_factors.sqlite"
    eng = CognitionEngine(source_db, str(factor_db) if factor_db.exists() else "")
    yield eng
    eng.close()


def _run_recommendation(
    engine: CognitionEngine,
    direction: str,
    conviction: str = "medium",
    time_horizon: str = "long",
    risk_tolerance: str = "moderate",
) -> dict[str, Any]:
    """运行一条 Thesis 的推荐评价，返回双榜单 Top 3。"""
    batch = engine.build_fund_candidate_evidence(
        direction=direction,
        conviction=conviction,
        time_horizon=time_horizon,
        risk_tolerance=risk_tolerance,
        data_snapshot_id=SNAPSHOT_ID,
        as_of_date=AS_OF_DATE,
    )
    rec_engine = FundRecommendationEngine()
    results = rec_engine.evaluate_all(batch.all_candidates, DEFAULT_POLICY)

    active = [r for r in results if r.product_category == "active_fund" and r.recommendation_tier in ("candidate_pool", "alternative")]
    etf = [r for r in results if r.product_category == "etf_or_index" and r.recommendation_tier in ("candidate_pool", "alternative")]
    excluded = [r for r in results if r.recommendation_tier == "excluded"]
    insufficient = [r for r in results if r.recommendation_tier == "data_insufficient"]

    return {
        "active_top3": [r.fund_code for r in active[:3]],
        "active_detail": [
            {
                "fund_code": r.fund_code,
                "fund_name": r.fund_name,
                "tier": r.recommendation_tier,
                "total_score": round(r.total_score, 3),
                "theme_exposure": round(r.theme_exposure_score, 3),
                "product_category": r.product_category,
                "reasons": [reason.code for reason in r.reasons],
                "exclusion_reasons": [reason.code for reason in r.exclusion_reasons],
            }
            for r in active[:5]
        ],
        "etf_top3": [r.fund_code for r in etf[:3]],
        "etf_detail": [
            {
                "fund_code": r.fund_code,
                "fund_name": r.fund_name,
                "tier": r.recommendation_tier,
                "total_score": round(r.total_score, 3),
                "theme_exposure": round(r.theme_exposure_score, 3),
            }
            for r in etf[:5]
        ],
        "excluded": [{"fund_code": r.fund_code, "reasons": [reason.code for reason in r.exclusion_reasons]} for r in excluded],
        "insufficient": [{"fund_code": r.fund_code} for r in insufficient],
        "total_candidates": len(results),
    }


# ============================================================
# 基准用例
# ============================================================
# 每条用例：
#   direction: 主题方向
#   conviction/time_horizon/risk_tolerance: 投资参数
#   expected_active_top1: 预期主动基金 #1（fund_code）
#   expected_etf_top1: 预期 ETF/指数基金 #1（fund_code，None 表示无 ETF 候选）
#   deviation_notes: 偏差原因（校准后填写）

BENCHMARK_CASES = [
    {
        "id": "consumer_medium",
        "direction": "consumer",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000001",  # 样例消费股票，食品饮料 46%
        "expected_etf_top1": "159004",  # 白酒ETF，白酒暴露 68%
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "consumer_high",
        "direction": "consumer",
        "conviction": "high",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000001",
        "expected_etf_top1": "159004",
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "ai_medium",
        "direction": "AI",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000004",  # 样例科技股票，半导体 35%
        "expected_etf_top1": "159002",  # 芯片ETF
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "ai_high",
        "direction": "AI",
        "conviction": "high",
        "time_horizon": "mid",
        "risk_tolerance": "aggressive",
        "expected_active_top1": "000004",
        "expected_etf_top1": "159002",
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "innovation_drug_medium",
        "direction": "innovation_drug",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000005",  # 样例医药股票，化学制药 25%
        "expected_etf_top1": None,  # 无医药ETF
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "innovation_drug_high",
        "direction": "innovation_drug",
        "conviction": "high",
        "time_horizon": "mid",
        "risk_tolerance": "aggressive",
        "expected_active_top1": "000005",
        "expected_etf_top1": None,
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "dividend_defense_medium",
        "direction": "dividend_defense",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "conservative",
        "expected_active_top1": "000006",  # 样例红利股票，银行 25%
        "expected_etf_top1": "159003",  # 红利指数
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "growth_investing_medium",
        "direction": "growth_investing",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "aggressive",
        "expected_active_top1": "000007",  # 样例成长股票，电力设备 30%
        "expected_etf_top1": "159002",  # 芯片ETF，持有寒武纪/中际旭创等成长股
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "value_investing_medium",
        "direction": "value_investing",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000008",  # 样例价值混合，银行 26%
        "expected_etf_top1": "159003",  # 红利指数，持有银行/能源股
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "contrarian_investing_medium",
        "direction": "contrarian_investing",
        "conviction": "medium",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000008",  # 价值混合，被错杀
        "expected_etf_top1": "159003",  # 红利指数，持有银行/能源股
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "consumer_conservative",
        "direction": "consumer",
        "conviction": "low",
        "time_horizon": "long",
        "risk_tolerance": "conservative",
        "expected_active_top1": "000001",
        "expected_etf_top1": "159004",
        "xfail": False,
        "deviation_notes": "",
    },
    {
        "id": "ai_low_conviction",
        "direction": "AI",
        "conviction": "low",
        "time_horizon": "long",
        "risk_tolerance": "moderate",
        "expected_active_top1": "000004",
        "expected_etf_top1": "159002",
        "xfail": False,
        "deviation_notes": "",
    },
]


# ============================================================
# 测试：逐条运行基准用例并对比
# ============================================================
@pytest.mark.parametrize("case", BENCHMARK_CASES, ids=[c["id"] for c in BENCHMARK_CASES])
def test_calibration(case: dict, engine: CognitionEngine):
    """每条基准用例：运行推荐 -> 对比 Top 1 -> 记录偏差。

    xfail=True 的用例是已知偏差（校准发现的问题），不会阻断 CI。
    如果后续改进使 xfail 用例通过（xpass），说明偏差已修复，应更新预期值并移除 xfail 标记。
    """
    result = _run_recommendation(
        engine,
        direction=case["direction"],
        conviction=case["conviction"],
        time_horizon=case["time_horizon"],
        risk_tolerance=case["risk_tolerance"],
    )

    is_xfail = case.get("xfail", False)
    deviation_msg = ""

    # 对比主动基金 Top 1
    actual_active_top1 = result["active_top3"][0] if result["active_top3"] else None
    expected_active_top1 = case["expected_active_top1"]

    if actual_active_top1 != expected_active_top1:
        detail = "\n".join(
            f"  {d['fund_code']} {d['fund_name']} tier={d['tier']} "
            f"total={d['total_score']} theme={d['theme_exposure']}"
            for d in result["active_detail"]
        ) or "  (none)"
        excluded_info = ", ".join(
            f"{e['fund_code']}({','.join(e['reasons'])})"
            for e in result["excluded"]
        ) or "(none)"
        deviation_msg = (
            f"[{case['id']}] 主动基金 Top 1 偏差: "
            f"expected={expected_active_top1} actual={actual_active_top1}\n"
            f"  active_detail:\n{detail}\n"
            f"  excluded: {excluded_info}\n"
            f"  insufficient: {[e['fund_code'] for e in result['insufficient']]}\n"
            f"  total_candidates: {result['total_candidates']}\n"
            f"  deviation_notes: {case.get('deviation_notes', '')}"
        )

    # 对比 ETF/指数基金 Top 1
    if not deviation_msg:
        actual_etf_top1 = result["etf_top3"][0] if result["etf_top3"] else None
        expected_etf_top1 = case["expected_etf_top1"]

        if actual_etf_top1 != expected_etf_top1:
            etf_detail = "\n".join(
                f"  {d['fund_code']} {d['fund_name']} tier={d['tier']} total={d['total_score']}"
                for d in result["etf_detail"]
            ) or "  (none)"
            deviation_msg = (
                f"[{case['id']}] ETF/指数基金 Top 1 偏差: "
                f"expected={expected_etf_top1} actual={actual_etf_top1}\n"
                f"  etf_detail:\n{etf_detail}\n"
                f"  deviation_notes: {case.get('deviation_notes', '')}"
            )

    # 根据偏差和 xfail 标记决定结果
    if deviation_msg:
        if is_xfail:
            pytest.xfail(deviation_msg)
        else:
            pytest.fail(deviation_msg)


def test_calibration_summary(engine: CognitionEngine):
    """汇总所有主题的推荐结果，便于一次性查看校准状态。"""
    summary_lines = []
    for case in BENCHMARK_CASES:
        result = _run_recommendation(
            engine,
            direction=case["direction"],
            conviction=case["conviction"],
            time_horizon=case["time_horizon"],
            risk_tolerance=case["risk_tolerance"],
        )
        active_top1 = result["active_top3"][0] if result["active_top3"] else None
        etf_top1 = result["etf_top3"][0] if result["etf_top3"] else None
        active_match = "OK" if active_top1 == case["expected_active_top1"] else ("XFAIL" if case.get("xfail") else "MISS")
        etf_match = "OK" if etf_top1 == case["expected_etf_top1"] else ("XFAIL" if case.get("xfail") else "MISS")
        summary_lines.append(
            f"| {case['id']:30s} | active={active_top1 or '-'} (exp={case['expected_active_top1'] or '-'}) {active_match} "
            f"| etf={etf_top1 or '-'} (exp={case['expected_etf_top1'] or '-'}) {etf_match} "
            f"| total={result['total_candidates']} |"
        )
    summary = "\n".join(summary_lines)
    # 此测试只输出汇总，不断言（作为校准报告）
    # 如果有偏差，上面的 parametrize 测试会失败
    print(f"\n=== 推荐校准汇总 ===\n{summary}\n")
