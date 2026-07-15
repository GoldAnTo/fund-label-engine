"""组合构建器：持仓重叠度、基金相关性、组合方案构建。"""
from __future__ import annotations

import sqlite3
import statistics
from typing import Any

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns, risk_models


def calculate_overlap(
    holdings_a: list[dict[str, Any]],
    holdings_b: list[dict[str, Any]],
) -> dict[str, Any]:
    """计算两只基金的持仓重叠度。"""
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
            [
                {"code": s, "a": round(map_a[s] * 100, 2), "b": round(map_b[s] * 100, 2)}
                for s in common
            ],
            key=lambda x: x["a"] + x["b"],
            reverse=True,
        )[:3],
    }


def calculate_correlation(
    conn: sqlite3.Connection,
    fund_a: str,
    fund_b: str,
) -> float | None:
    """计算两只基金的 NAV 日收益相关系数（共同交易日 < 30 返回 None）。"""
    rows_a = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history "
        "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
        (fund_a,),
    ).fetchall()
    rows_b = conn.execute(
        "SELECT nav_date, daily_growth_rate FROM nav_history "
        "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
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


def build_portfolio(
    candidates: list[dict[str, Any]],
    defense_fund: dict[str, Any] | None,
    corr_threshold: float = 0.85,
    total_cognition_weight: float = 25.0,
    defense_weight_pct: float = 10.0,
    max_funds: int = 3,
) -> dict[str, Any]:
    """构建认知匹配的组合方案。

    候选基金按匹配度排序，依次选入（跳过相关性过高的），
    估值/趋势约束决定单只上限，认知仓位合计 total_cognition_weight%，防守仓位 defense_weight_pct%。

    无候选时（candidates 为空或全部 match_pct < 5）：
    - 不生成防守基金占位（避免展示"默认防守组合"误导用户）
    - 返回空 selected + 100% cash
    - 调用方应通过 selected_funds 长度判断是否有可投组合
    """
    # 短路：candidates 为空 → 立即返回空组合，不选防守基金
    # （设计文档 §4.4：无候选时不形成默认防守组合）
    if not candidates:
        return {
            "selected_funds": [],
            "defense_position": None,
            "cash_pct": 100.0,
            "total_invested": 0.0,
            "suggested_weight": 0.0,
            "defense_weight": 0.0,
            "no_candidates": True,
        }

    candidates.sort(key=lambda x: x["match_pct"], reverse=True)

    selected: list[dict[str, Any]] = []
    for c in candidates:
        if c["match_pct"] < 5:
            continue

        val_pct = c.get("valuation", {}).get("weighted_val_pct")
        if val_pct and val_pct > 85:
            max_weight = 5
        elif val_pct and val_pct > 70:
            max_weight = 8
        else:
            max_weight = 12

        trend = c.get("trend", {}).get("trend", "")
        if trend == "decreasing":
            max_weight = min(max_weight, 5)

        too_correlated = False
        for s in selected:
            if s.get("corr_with", {}).get(c["fund_code"], 0) > corr_threshold:
                too_correlated = True
                break
        if too_correlated:
            continue

        selected.append({**c, "max_weight": max_weight})

        if len(selected) >= max_funds:
            break

    total_match = sum(s["match_pct"] for s in selected) or 1
    for s in selected:
        raw = s["match_pct"] / total_match * total_cognition_weight
        s["weight"] = round(min(raw, s["max_weight"]), 1)

    defense_weight = 0
    if defense_fund:
        defense_weight = defense_weight_pct
        defense_fund["weight"] = defense_weight

    total = sum(s["weight"] for s in selected) + defense_weight
    cash = max(0, 100 - total)

    result = {
        "selected_funds": selected,
        "defense_position": defense_fund,
        "cash_pct": round(cash, 1),
        "total_invested": round(total, 1),
    }

    # 前端兼容字段
    result["suggested_weight"] = round(sum(s["weight"] for s in selected), 1)
    result["defense_weight"] = round(defense_weight, 1)
    return result


def _detect_return_column(conn: sqlite3.Connection) -> str:
    """检测 nav_history 表中日收益率列名（daily_growth_rate 或 daily_return）。"""
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(nav_history)").fetchall()
    }
    if "daily_growth_rate" in cols:
        return "daily_growth_rate"
    if "daily_return" in cols:
        return "daily_return"
    return "daily_growth_rate"


def optimize_portfolio(
    candidates: list[dict[str, Any]],
    conn: sqlite3.Connection,
    total_cognition_weight: float = 25.0,
    max_single_weight: float = 12.0,
    min_single_weight: float = 3.0,
) -> dict[str, Any] | None:
    """用均值-方差优化分配基金权重。

    方法：
    1. 从 nav_history 提取候选基金的日收益率
    2. 计算预期收益（年化均值）和协方差矩阵
    3. 用 EfficientFrontier.max_sharpe() 优化，失败时回退到 min_volatility()
    4. 约束：单只 [min_single_weight, max_single_weight]，总和 = total_cognition_weight

    返回 None 时表示优化失败（数据不足或无可行解），调用方应回退到 build_portfolio()。
    """
    # 候选基金少于 2 只无法做组合优化
    if len(candidates) < 2:
        return None

    fund_codes = [c["fund_code"] for c in candidates]

    # 检测日收益率列名
    return_col = _detect_return_column(conn)

    # 提取日收益率矩阵
    returns_data: dict[str, dict[str, float]] = {}
    for fc in fund_codes:
        rows = conn.execute(
            f"SELECT nav_date, {return_col} FROM nav_history "
            f"WHERE fund_code = ? AND {return_col} IS NOT NULL "
            f"ORDER BY nav_date",
            (fc,),
        ).fetchall()
        if len(rows) < 30:
            return None  # 数据不足
        returns_data[fc] = {r[0]: r[1] for r in rows}

    # 对齐日期，取所有基金的共同交易日
    all_dates: set[str] = set()
    for d in returns_data.values():
        all_dates.update(d.keys())
    all_dates_sorted = sorted(all_dates)

    if len(all_dates_sorted) < 30:
        return None

    # 构建 DataFrame，缺失值用 NaN 填充后 dropna
    df = pd.DataFrame(
        {fc: [returns_data[fc].get(d, np.nan) for d in all_dates_sorted] for fc in fund_codes}
    )
    df = df.dropna()

    if len(df) < 30:
        return None

    # 计算预期收益和协方差（日收益率已经是小数形式，用 returns_data=True）
    try:
        mu = expected_returns.mean_historical_return(df, returns_data=True, frequency=252)
        S = risk_models.sample_cov(df, returns_data=True, frequency=252)
    except Exception:
        return None

    # 协方差矩阵奇异时无法优化
    try:
        _ = np.linalg.inv(S.values)
    except np.linalg.LinAlgError:
        return None

    # 归一化权重的上下界（最终权重 = 归一化权重 * total_cognition_weight）
    lower_bound = min_single_weight / total_cognition_weight
    upper_bound = max_single_weight / total_cognition_weight

    # 候选基金数量太少导致约束不可行时直接返回 None
    if len(fund_codes) * upper_bound < 1.0 or len(fund_codes) * lower_bound > 1.0:
        return None

    ef = EfficientFrontier(mu, S, weight_bounds=(lower_bound, upper_bound))

    optimization_method = "max_sharpe"
    try:
        weights = ef.max_sharpe()
    except Exception:
        # max_sharpe 失败（可能是约束变换导致不可行），回退到最小波动率
        ef = EfficientFrontier(mu, S, weight_bounds=(lower_bound, upper_bound))
        try:
            weights = ef.min_volatility()
            optimization_method = "min_volatility"
        except Exception:
            return None

    # 清理权重：过滤极小值，缩放到总仓位百分比
    clean_weights = {
        k: round(v * total_cognition_weight, 1)
        for k, v in weights.items()
        if v > 0.001
    }

    # 缩放校正：确保总和精确等于 total_cognition_weight（允许 +-0.1 误差）
    total = sum(clean_weights.values())
    if total <= 0:
        return None

    # 如果误差超过 0.1，按比例微调
    if abs(total - total_cognition_weight) > 0.1:
        scale = total_cognition_weight / total
        clean_weights = {k: round(v * scale, 1) for k, v in clean_weights.items()}

    # 构建结果，保留候选基金原始信息并附加权重
    selected: list[dict[str, Any]] = []
    for c in candidates:
        w = clean_weights.get(c["fund_code"], 0)
        if w > 0:
            selected.append({**c, "weight": w, "max_weight": max_single_weight})

    if not selected:
        return None

    total_invested = round(sum(s["weight"] for s in selected), 1)

    return {
        "selected_funds": selected,
        "optimization_method": optimization_method,
        "suggested_weight": total_invested,
        "total_invested": total_invested,
    }


def calculate_portfolio_metrics(
    conn: sqlite3.Connection,
    selected_funds: list[dict[str, Any]],
    defense_fund: dict[str, Any] | None,
    all_holdings: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """计算组合级风险指标：加权PE、年化波动率、最大回撤、持仓穿透、行业暴露。

    需要传入 conn 以读取 nav_history 计算波动率和回撤。
    all_holdings 用于获取防守基金的持仓数据（defense_fund 不含 holdings）。
    """
    # 构建权重表 fund_code -> 权重(小数)
    weight_map: dict[str, float] = {}
    for f in selected_funds:
        weight_map[f["fund_code"]] = f.get("weight", 0) / 100.0
    if defense_fund and defense_fund.get("fund_code"):
        weight_map[defense_fund["fund_code"]] = defense_fund.get("weight", 0) / 100.0

    invested_fraction = sum(weight_map.values()) or 1.0

    # --- 1. 组合加权PE ---
    pe_data: list[tuple[float, float]] = []
    for f in selected_funds:
        pe = f.get("valuation", {}).get("weighted_pe")
        w = f.get("weight", 0) / 100.0
        if pe and pe > 0 and w > 0:
            pe_data.append((w, pe))
    if defense_fund:
        pe = defense_fund.get("valuation", {}).get("weighted_pe")
        w = defense_fund.get("weight", 0) / 100.0
        if pe and pe > 0 and w > 0:
            pe_data.append((w, pe))
    portfolio_pe = (
        round(sum(w * pe for w, pe in pe_data) / sum(w for w, _ in pe_data), 1)
        if pe_data else None
    )

    # --- 2. 组合年化波动率 + 最大回撤 ---
    portfolio_volatility: float | None = None
    portfolio_max_drawdown: float | None = None

    fund_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    for fc in weight_map:
        try:
            rows = conn.execute(
                "SELECT nav_date, daily_growth_rate FROM nav_history "
                "WHERE fund_code = ? AND daily_growth_rate IS NOT NULL",
                (fc,),
            ).fetchall()
        except Exception:
            rows = []
        if rows:
            fund_returns[fc] = {r[0]: r[1] for r in rows}
            all_dates.update(r[0] for r in rows)

    if len(all_dates) >= 30:
        sorted_dates = sorted(all_dates)
        daily_returns: list[float] = []
        for date in sorted_dates:
            ret = 0.0
            for fc, w in weight_map.items():
                r = fund_returns.get(fc, {}).get(date)
                if r is not None:
                    ret += w * r
            daily_returns.append(ret)

        if len(daily_returns) >= 30:
            std_ret = statistics.stdev(daily_returns)
            portfolio_volatility = round(std_ret * (252 ** 0.5), 1)

            # 最大回撤
            cumulative = 1.0
            peak = 1.0
            max_dd = 0.0
            for r in daily_returns:
                cumulative *= (1 + r / 100)
                if cumulative > peak:
                    peak = cumulative
                dd = (peak - cumulative) / peak
                if dd > max_dd:
                    max_dd = dd
            portfolio_max_drawdown = round(-max_dd * 100, 1)

    # --- 3. 持仓穿透（底层股票明细） ---
    stock_map: dict[str, dict[str, Any]] = {}
    for f in selected_funds:
        fw = f.get("weight", 0) / 100.0
        for h in f.get("holdings") or []:
            code = h.get("stock_code", "")
            if not code:
                continue
            eff = fw * h.get("weight", 0)
            if code not in stock_map:
                stock_map[code] = {
                    "stock_code": code,
                    "stock_name": h.get("stock_name", ""),
                    "weight": 0.0,
                    "industry_name": h.get("industry_name", ""),
                    "sector_group": h.get("sector_group", ""),
                    "pe": h.get("pe"),
                    "roe": h.get("roe"),
                }
            stock_map[code]["weight"] += eff

    # 防守基金持仓
    if defense_fund and all_holdings:
        df_code = defense_fund.get("fund_code")
        dw = defense_fund.get("weight", 0) / 100.0
        for h in all_holdings.get(df_code, []):
            code = h.get("stock_code", "")
            if not code:
                continue
            eff = dw * h.get("weight", 0)
            if code not in stock_map:
                stock_map[code] = {
                    "stock_code": code,
                    "stock_name": h.get("stock_name", ""),
                    "weight": 0.0,
                    "industry_name": h.get("industry_name", ""),
                    "sector_group": h.get("sector_group", ""),
                    "pe": h.get("pe"),
                    "roe": h.get("roe"),
                }
            stock_map[code]["weight"] += eff

    holdings_penetration = sorted(stock_map.values(), key=lambda x: x["weight"], reverse=True)[:10]
    for h in holdings_penetration:
        h["weight"] = round(h["weight"] * 100, 2)

    # --- 4. 行业暴露 ---
    # 注意：line 290 已把 h["weight"] 转为 percentage (e.g. 1.1 = 1.1%)
    # 所以 industry_weights 累加的也是 percentage，不应该再 * 100
    # 这是 P0 修复：原代码 * 100 导致 industry_exposure / sector_exposure
    # 数字比真实值大 100 倍（例如真实 2.3% 显示成 230.0%）
    industry_weights: dict[str, float] = {}
    sector_weights: dict[str, float] = {}
    for h in stock_map.values():
        ind = h["industry_name"] or "未知"
        sec = h["sector_group"] or "other"
        w = h["weight"]
        industry_weights[ind] = industry_weights.get(ind, 0) + w
        sector_weights[sec] = sector_weights.get(sec, 0) + w

    industry_exposure = sorted(
        [{"name": k, "weight": round(v, 1)} for k, v in industry_weights.items()],
        key=lambda x: x["weight"],
        reverse=True,
    )[:8]
    sector_exposure = sorted(
        [{"name": k, "weight": round(v, 1)} for k, v in sector_weights.items()],
        key=lambda x: x["weight"],
        reverse=True,
    )[:6]

    return {
        "portfolio_pe": portfolio_pe,
        "portfolio_volatility": portfolio_volatility,
        "portfolio_max_drawdown": portfolio_max_drawdown,
        "holdings_penetration": holdings_penetration,
        "industry_exposure": industry_exposure,
        "sector_exposure": sector_exposure,
    }


def portfolio_risk_review(
    metrics: dict[str, Any],
    overlap_summary: dict[str, Any],
    selected_funds: list[dict[str, Any]],
    conviction: str = "medium",
) -> dict[str, Any]:
    """组合级二次裁决：行业暴露/持仓重叠/回撤/波动率约束。

    返回：
    - verdict: "pass" / "warn" / "fail"
    - violations: 具体违规项列表
    - recommendations: 调整建议
    """
    # 约束阈值随信心强度调整：高信心更宽容
    thresholds = {
        "high": {"max_industry": 50, "max_stock": 12, "max_overlap": 50, "max_drawdown": -35, "max_volatility": 35},
        "medium": {"max_industry": 40, "max_stock": 10, "max_overlap": 40, "max_drawdown": -25, "max_volatility": 30},
        "low": {"max_industry": 30, "max_stock": 8, "max_overlap": 30, "max_drawdown": -20, "max_volatility": 25},
    }
    th = thresholds.get(conviction, thresholds["medium"])

    violations: list[dict[str, Any]] = []
    recommendations: list[str] = []

    # 1. 行业集中度
    industry_exposure = metrics.get("industry_exposure", [])
    for ind in industry_exposure:
        if ind["weight"] > th["max_industry"]:
            violations.append({
                "type": "industry_concentration",
                "severity": "warn",
                "detail": f"行业「{ind['name']}」占比 {ind['weight']:.1f}%，超过上限 {th['max_industry']}%",
            })
            recommendations.append(f"考虑降低「{ind['name']}」行业暴露，增加其他行业配置")

    # 2. 个股集中度
    for stock in metrics.get("holdings_penetration", []):
        if stock["weight"] > th["max_stock"]:
            violations.append({
                "type": "stock_concentration",
                "severity": "warn",
                "detail": f"个股「{stock.get('stock_name', stock.get('stock_code', ''))}」占比 {stock['weight']:.2f}%，超过上限 {th['max_stock']}%",
            })
            recommendations.append(f"个股「{stock.get('stock_name', '')}」过于集中，考虑分散")

    # 3. 持仓重叠度
    max_overlap = overlap_summary.get("max_overlap_pct", 0)
    high_pairs = overlap_summary.get("high_overlap_pairs", [])
    if max_overlap > th["max_overlap"]:
        violations.append({
            "type": "holdings_overlap",
            "severity": "warn",
            "detail": f"基金间最大持仓重叠 {max_overlap:.1f}%，超过上限 {th['max_overlap']}%（{len(high_pairs)} 对高重叠）",
        })
        recommendations.append("高重叠基金实质上是同一头寸的重复，考虑去重或替换其中一只")

    # 4. 最大回撤
    max_dd = metrics.get("portfolio_max_drawdown")
    if max_dd is not None and max_dd < th["max_drawdown"]:
        violations.append({
            "type": "max_drawdown",
            "severity": "fail" if max_dd < th["max_drawdown"] - 10 else "warn",
            "detail": f"组合历史最大回撤 {max_dd:.1f}%，超过容忍线 {th['max_drawdown']}%",
        })
        recommendations.append("组合回撤风险偏高，考虑增加防守仓位或降低整体仓位")

    # 5. 波动率
    vol = metrics.get("portfolio_volatility")
    if vol is not None and vol > th["max_volatility"]:
        violations.append({
            "type": "volatility",
            "severity": "warn",
            "detail": f"组合年化波动率 {vol:.1f}%，超过上限 {th['max_volatility']}%",
        })
        recommendations.append("波动率偏高，考虑增加低波动资产")

    # 裁决
    has_fail = any(v["severity"] == "fail" for v in violations)
    has_warn = any(v["severity"] == "warn" for v in violations)
    if has_fail:
        verdict = "fail"
    elif has_warn:
        verdict = "warn"
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "violations": violations,
        "recommendations": recommendations,
        "thresholds": th,
        "fund_count": len(selected_funds),
    }
