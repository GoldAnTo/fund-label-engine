"""认知引擎主模块：7步认知转化引擎。

认知采集 -> 产业链拆解 -> 预期差分析 -> 资产穿透+估值门禁 -> 认知验证 -> 组合构建 -> 组合输出
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.cognition.asset_mapper import calculate_holding_trend, get_holdings
from app.cognition.chain_graph import (
    enrich_chain_with_industry_db,
    get_all_industry_keywords,
    get_all_stock_keywords,
    load_chains,
)
from app.cognition.expectation_gap import calculate_link_expectation_gap
from app.cognition.holding_source import HoldingSourceAdapter
from app.cognition.industry_db import IndustryDB
from app.cognition.portfolio_builder import (
    build_portfolio,
    calculate_overlap,
    calculate_portfolio_metrics,
    optimize_portfolio,
)
from app.cognition.theme_registry import load_themes
from app.cognition.thesis_tracker import create_tracker_from_cognition
from app.cognition.validator import validate_cognition
from app.cognition.valuation_gate import calculate_valuation, check_hard_limits
from app.services.candidate_priority import FundCandidateEvidence

_MATCH_THRESHOLD = 5.0


@dataclass(frozen=True)
class FundCandidateEvidenceBatch:
    """基金候选证据批次：包含所有候选（未截断）和统计信息。"""

    all_candidates: tuple[FundCandidateEvidence, ...]
    valuation_gated_candidates: tuple[FundCandidateEvidence, ...]
    scanned_fund_count: int
    mapped_candidate_count: int
    unmapped_due_to_data_count: int  # 因数据不足而无法映射的基金数
    unrelated_fund_count: int  # 有持仓但与主题方向不相关的基金数


class CognitionEngine:
    """认知驱动基金配置引擎（自动推导式）。

    用法::

        engine = CognitionEngine("/tmp/fle-run/source.sqlite", "data/stock_factors.sqlite")
        result = engine.run("AI")
        engine.close()
    """

    def __init__(
        self,
        source_db: str | Path,
        factor_db: str | Path,
        industry_db: IndustryDB | None = None,
    ) -> None:
        self._source_db = Path(source_db)
        self._factor_db = Path(factor_db).resolve() if factor_db else None
        self._themes = load_themes()
        self._chains = load_chains()
        self._conn: sqlite3.Connection | None = None
        # 行业数据库：用于产业链匹配的补充查询，为 None 时回退到纯关键词匹配
        self._industry_db = industry_db

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            # check_same_thread=False: FastAPI 通过 anyio 把同步处理函数调度到
            # 工作线程，CognitionEngine 实例在 lifespan/工厂阶段创建，但
            # run() 在请求线程执行。共享连接需要跨线程，否则 SQLite 拒绝访问。
            conn = sqlite3.connect(
                f"file:{self._source_db}?mode=ro", uri=True, check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            if self._factor_db and self._factor_db.exists():
                conn.execute(f"ATTACH DATABASE '{self._factor_db}' AS factordb")
            self._conn = conn
            # 如果未显式传入 industry_db，尝试从 source DB 自动加载
            if self._industry_db is None:
                auto_db = IndustryDB()
                auto_db.load_from_sqlite(conn)
                if auto_db.is_loaded():
                    self._industry_db = auto_db
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # 主题 / 方向
    # ------------------------------------------------------------------
    def get_themes(self) -> dict[str, dict[str, Any]]:
        return self._themes

    def get_chains(self) -> dict[str, dict[str, Any]]:
        return self._chains

    # ------------------------------------------------------------------
    # 概念板块搜索（动态主题扩展）
    # ------------------------------------------------------------------
    def search_concepts(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """按关键词搜索概念板块，返回板块列表+成分股数量。

        依赖 factor DB 中的 concept_board_stocks 表（由 fetch_concept_boards.py 抓取）。
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT concept_code, concept_name,
                   COUNT(stock_code) AS stock_count
            FROM concept_board_stocks
            WHERE concept_name LIKE ?
            GROUP BY concept_code, concept_name
            ORDER BY stock_count DESC
            LIMIT ?
            """,
            (f"%{keyword}%", limit),
        ).fetchall()
        return [
            {"code": r[0], "name": r[1], "stock_count": r[2]}
            for r in rows
        ]

    def get_concept_stocks(self, concept_code: str) -> list[dict[str, str]]:
        """获取某概念板块的成分股列表。"""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT stock_code, stock_name
            FROM concept_board_stocks
            WHERE concept_code = ?
            ORDER BY stock_name
            """,
            (concept_code,),
        ).fetchall()
        return [{"code": r[0], "name": r[1]} for r in rows]

    def run_concept(
        self,
        concept_code: str,
        concept_name: str,
        conviction: str = "medium",
        time_horizon: str = "long",
        risk_tolerance: str = "moderate",
        max_valuation_percentile: float | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """用概念板块成分股作为产业链 stocks 运行 7 步认知转化。

        与 run() 的区别：用概念板块成分股替代预设的 chain stocks，
        构建单环节产业链，judgment 使用自适应默认模板。
        """
        stocks = self.get_concept_stocks(concept_code)
        if not stocks:
            return {
                "direction": concept_name,
                "error": f"概念板块 {concept_code} 无成分股数据",
            }

        stock_names = [s["name"] for s in stocks]

        # 构建动态链
        chain = {
            "judgment": {
                "level": "market",
                "belief": f"我相信{concept_name}方向",
                "time_horizon": time_horizon,
                "valuation_tolerance": "medium",
                "key_metric": "peg",
                "hard_limits": {
                    "max_valuation_percentile": max_valuation_percentile or 85,
                    "max_peg": 2.0,
                },
                "portfolio_role": "satellite",
                "role_weight_range": [5, 15],
            },
            "chain": [{
                "name": concept_name,
                "stocks": stock_names,
                "industry_keywords": [],
                "certainty": "medium",
                "elasticity": "medium",
                "benefit_logic": f"{concept_name}概念板块成分股",
            }],
            "defense": "dividend_defense",
        }

        # 复用 run() 的逻辑，但传入自定义 chain
        return self._run_with_chain(
            chain, concept_name, None, conviction,
            time_horizon, risk_tolerance, max_valuation_percentile, top_n,
        )

    # ------------------------------------------------------------------
    # 个股认知：按股票穿透基金持仓
    # ------------------------------------------------------------------
    def search_stocks(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """按关键词搜索股票，返回持有该股票的基金数量和估值数据。

        依赖 stock_holdings + stock_industry_map + factordb.stock_factor_values。
        """
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT h.stock_code, h.stock_name,
                   m.industry_name, m.sector_group,
                   COUNT(DISTINCT h.fund_code) AS fund_count,
                   (SELECT f.factor_value FROM factordb.stock_factor_values f
                    WHERE f.stock_code = h.stock_code AND f.factor_code = 'pe') AS pe,
                   (SELECT f.factor_value FROM factordb.stock_factor_values f
                    WHERE f.stock_code = h.stock_code AND f.factor_code = 'roe') AS roe,
                   (SELECT f.factor_value FROM factordb.stock_factor_values f
                    WHERE f.stock_code = h.stock_code AND f.factor_code = 'valuation_percentile') AS val_pct
            FROM stock_holdings h
            LEFT JOIN stock_industry_map m ON h.stock_code = m.stock_code
            WHERE h.stock_name LIKE ? OR h.stock_code LIKE ?
            GROUP BY h.stock_code, h.stock_name
            ORDER BY fund_count DESC
            LIMIT ?
            """,
            (f"%{keyword}%", f"%{keyword}%", limit),
        ).fetchall()
        return [
            {
                "stock_code": r[0],
                "stock_name": r[1],
                "industry_name": r[2] or "",
                "sector_group": r[3] or "",
                "fund_count": r[4],
                "pe": round(r[5], 1) if r[5] else None,
                "roe": round(r[6] * 100, 1) if r[6] else None,
                "val_pct": round(r[7] * 100, 0) if r[7] is not None else None,
            }
            for r in rows
        ]

    def run_stock_cognition(
        self,
        stock_code: str,
        stock_name: str | None = None,
        conviction: str = "medium",
        time_horizon: str = "long",
        risk_tolerance: str = "moderate",
        max_valuation_percentile: float | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """个股认知：找到持有该股票占比最高的基金，附估值检查。

        流程：
        1. 搜索所有持有该股票的基金
        2. 按该股票在基金中的权重排序
        3. 对每只基金做估值门禁
        4. 构建组合
        """
        conn = self._get_conn()

        # 查找持有该股票的基金
        rows = conn.execute(
            """
            SELECT h.fund_code, h.stock_code, h.stock_name,
                   h.net_value_ratio AS weight, h.report_period
            FROM stock_holdings h
            WHERE h.stock_code = ? OR h.stock_name LIKE ?
            ORDER BY h.net_value_ratio DESC
            """,
            (stock_code, f"%{stock_name or stock_code}%"),
        ).fetchall()

        if not rows:
            return {
                "stock_code": stock_code,
                "stock_name": stock_name or stock_code,
                "error": "未找到持有该股票的基金",
            }

        # 获取股票估值
        stock_info = self._get_stock_valuation(conn, stock_code)

        # 按基金聚合，取每只基金最新一期的权重
        fund_latest: dict[str, dict[str, Any]] = {}
        for r in rows:
            fc = r[0]
            if fc not in fund_latest or r[4] > fund_latest[fc]["report_period"]:
                fund_latest[fc] = {
                    "fund_code": fc,
                    "stock_weight": r[3],
                    "report_period": r[4],
                }

        # 加载基金持仓和估值
        hard_limits: dict[str, Any] = {}
        if max_valuation_percentile is not None:
            hard_limits["max_valuation_percentile"] = max_valuation_percentile
        else:
            hard_limits["max_valuation_percentile"] = 85

        fund_matches: list[dict[str, Any]] = []
        gated_out: list[dict[str, Any]] = []

        for fc, info in fund_latest.items():
            holdings = get_holdings(conn, fc)
            if not holdings:
                continue

            valuation = calculate_valuation(holdings)
            industry_pe_medians = self._get_industry_pe_medians(conn)
            self._enrich_cross_sectional(holdings, valuation, industry_pe_medians)

            gate = check_hard_limits(valuation, hard_limits)

            trend = calculate_holding_trend(
                conn,
                fc,
                {"chain_links": {"_": {"stock_keywords": [stock_name or stock_code], "industry_keywords": []}}},
            )

            fund_data = {
                "fund_code": fc,
                "fund_name": self._get_fund_name(conn, fc),
                "match_pct": round(info["stock_weight"] * 100, 1),
                "stock_weight": round(info["stock_weight"] * 100, 2),
                "valuation": valuation,
                "trend": trend,
                "gate": gate,
                "holdings": holdings,
            }

            if gate["passed"]:
                fund_matches.append(fund_data)
            else:
                gated_out.append(fund_data)

        fund_matches.sort(key=lambda x: x["match_pct"], reverse=True)
        top_funds = fund_matches[:top_n]

        # 加载基金经理数据
        fund_managers = self._load_fund_managers(conn)
        for fund in top_funds:
            mgr = fund_managers.get(fund["fund_code"])
            if mgr:
                fund["manager"] = mgr

        # 仓位计算
        if conviction == "high":
            total_weight = 20.0
        elif conviction == "medium":
            total_weight = 12.0
        else:
            total_weight = 5.0

        if risk_tolerance == "conservative":
            defense_weight_pct = 15.0
        elif risk_tolerance == "aggressive":
            defense_weight_pct = 5.0
        else:
            defense_weight_pct = 10.0

        # 防守基金
        defense_fund = self._find_defense_fund(
            conn,
            {fc: get_holdings(conn, fc) for fc in fund_latest},
            self._chains.get("dividend_defense", {}),
        )

        portfolio = build_portfolio(
            fund_matches,
            defense_fund,
            corr_threshold=0.85,
            total_cognition_weight=total_weight,
            defense_weight_pct=defense_weight_pct,
        )

        # 组合级指标
        all_holdings_local = {fc: get_holdings(conn, fc) for fc in fund_latest}
        portfolio_metrics = calculate_portfolio_metrics(
            conn,
            portfolio.get("selected_funds", []),
            defense_fund,
            all_holdings_local,
        )

        portfolio["metrics"] = portfolio_metrics
        portfolio["top_funds"] = portfolio.get("selected_funds", [])
        portfolio["defense_fund"] = defense_fund

        # 估值判断
        val_assessment = "数据不足"
        if stock_info and stock_info.get("pe"):
            pe = stock_info["pe"]
            val_pct = stock_info.get("val_pct")
            if val_pct is not None:
                if val_pct > 85:
                    val_assessment = f"PE {pe:.0f}，估值分位 {val_pct:.0f}%，极度偏贵"
                elif val_pct > 70:
                    val_assessment = f"PE {pe:.0f}，估值分位 {val_pct:.0f}%，偏贵"
                elif val_pct > 30:
                    val_assessment = f"PE {pe:.0f}，估值分位 {val_pct:.0f}%，合理"
                else:
                    val_assessment = f"PE {pe:.0f}，估值分位 {val_pct:.0f}%，偏低"

        return {
            "stock_code": stock_code,
            "stock_name": stock_name or stock_info.get("stock_name", stock_code) if stock_info else stock_code,
            "stock_info": stock_info,
            "valuation_assessment": val_assessment,
            "conviction": conviction,
            "step4_fund_matches": top_funds,
            "matches": top_funds,
            "candidates": top_funds,
            "step5_portfolio": portfolio,
            "gated_out_funds": [
                {
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "match_pct": f["match_pct"],
                    "violations": f["gate"]["violations"],
                }
                for f in gated_out[:5]
            ],
        }

    def _get_stock_valuation(
        self, conn: sqlite3.Connection, stock_code: str
    ) -> dict[str, Any] | None:
        """获取单只股票的估值数据。"""
        try:
            rows = conn.execute(
                """
                SELECT f.factor_code, f.factor_value
                FROM factordb.stock_factor_values f
                WHERE f.stock_code = ?
                """,
                (stock_code,),
            ).fetchall()
        except Exception:
            return None

        factors = {r[0]: r[1] for r in rows}
        if not factors:
            return None

        # 获取股票名和行业
        name_row = conn.execute(
            "SELECT stock_name FROM stock_holdings WHERE stock_code = ? LIMIT 1",
            (stock_code,),
        ).fetchone()
        ind_row = conn.execute(
            "SELECT industry_name, sector_group FROM stock_industry_map WHERE stock_code = ? LIMIT 1",
            (stock_code,),
        ).fetchone()

        return {
            "stock_code": stock_code,
            "stock_name": name_row[0] if name_row else stock_code,
            "industry_name": ind_row[0] if ind_row else "",
            "sector_group": ind_row[1] if ind_row else "",
            "pe": round(factors.get("pe"), 1) if factors.get("pe") else None,
            "pb": round(factors.get("pb"), 2) if factors.get("pb") else None,
            "roe": round(factors.get("roe") * 100, 1) if factors.get("roe") else None,
            "dividend_yield": round(factors.get("dividend_yield") * 100, 2) if factors.get("dividend_yield") else None,
            "profit_growth": round(factors.get("profit_growth") * 100, 0) if factors.get("profit_growth") else None,
            "val_pct": round(factors.get("valuation_percentile") * 100, 0) if factors.get("valuation_percentile") is not None else None,
        }

    # ------------------------------------------------------------------
    # 多认知组合合并
    # ------------------------------------------------------------------
    def combine_cognitions(
        self,
        cognition_items: list[dict[str, Any]],
        risk_tolerance: str = "moderate",
    ) -> dict[str, Any]:
        """合并多个认知结果为一个组合。

        cognition_items: [{"direction": "AI", "weight_pct": 30, "result": {...}}, ...]
        每个 result 是 run() 的返回值，包含 step5_portfolio。

        合并逻辑：
        1. 每个认知的基金按其分配权重缩放
        2. 同一基金出现在多个认知中时合并权重
        3. 重新计算组合级指标
        """
        conn = self._get_conn()

        merged_funds: dict[str, dict[str, Any]] = {}
        cognition_breakdown: list[dict[str, Any]] = []
        total_allocated = 0.0

        for item in cognition_items:
            direction = item.get("direction", "?")
            weight_pct = item.get("weight_pct", 10)
            result = item.get("result") or {}
            portfolio = result.get("step5_portfolio", {})
            selected = portfolio.get("selected_funds", [])

            cognition_total = 0.0
            for fund in selected:
                fc = fund["fund_code"]
                # 缩放权重：基金原权重 × 认知分配比例
                scaled_weight = round(fund.get("weight", 0) * weight_pct / 100, 1)

                if fc not in merged_funds:
                    merged_funds[fc] = {
                        "fund_code": fc,
                        "fund_name": fund.get("fund_name", fc),
                        "weight": 0.0,
                        "match_pct": fund.get("match_pct", 0),
                        "valuation": fund.get("valuation", {}),
                        "holdings": fund.get("holdings", []),
                        "cognitions": [],
                    }
                merged_funds[fc]["weight"] += scaled_weight
                merged_funds[fc]["cognitions"].append(direction)
                cognition_total += scaled_weight

            total_allocated += cognition_total
            cognition_breakdown.append({
                "direction": direction,
                "allocation_pct": weight_pct,
                "actual_weight": round(cognition_total, 1),
                "fund_count": len(selected),
            })

        # 合并后的基金列表
        all_funds = sorted(merged_funds.values(), key=lambda x: x["weight"], reverse=True)

        # 计算组合级指标
        # 构建防守权重
        defense_fund = None
        for item in cognition_items:
            result = item.get("result") or {}
            portfolio = result.get("step5_portfolio", {})
            df = portfolio.get("defense_position")
            if df:
                defense_fund = df
                break

        all_holdings_local = {f["fund_code"]: f.get("holdings", []) for f in all_funds}
        portfolio_metrics = calculate_portfolio_metrics(
            conn,
            all_funds,
            defense_fund,
            all_holdings_local,
        )

        total_weight = sum(f["weight"] for f in all_funds)
        defense_weight = defense_fund.get("weight", 0) if defense_fund else 0
        cash_pct = max(0, 100 - total_weight - defense_weight)

        return {
            "cognitions": cognition_breakdown,
            "combined_funds": [
                {
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "weight": f["weight"],
                    "match_pct": f["match_pct"],
                    "cognitions": f["cognitions"],
                    "valuation": f["valuation"],
                }
                for f in all_funds
            ],
            "defense_fund": defense_fund,
            "cash_pct": round(cash_pct, 1),
            "total_invested": round(total_weight + defense_weight, 1),
            "metrics": portfolio_metrics,
            "overlap_analysis": {
                "max_overlap_pct": 0,
                "high_overlap_pairs": [],
            },
        }

    def _run_with_chain(
        self,
        chain: dict[str, Any],
        direction: str,
        belief_link: str | None,
        conviction: str,
        time_horizon: str,
        risk_tolerance: str,
        max_valuation_percentile: float | None,
        top_n: int,
    ) -> dict[str, Any]:
        """用指定 chain 运行 7 步流程（供 run() 和 run_concept() 复用）。"""
        # 临时把 chain 放进 self._chains 以复用 run() 的逻辑
        original = self._chains.get(direction)
        self._chains[direction] = chain
        try:
            return self.run(
                direction, belief_link, conviction,
                time_horizon, risk_tolerance,
                max_valuation_percentile, top_n,
            )
        finally:
            if original is not None:
                self._chains[direction] = original
            else:
                self._chains.pop(direction, None)

    # ------------------------------------------------------------------
    # 辅助查询
    # ------------------------------------------------------------------
    def _get_fund_name(self, conn: sqlite3.Connection, fund_code: str) -> str:
        row = conn.execute(
            "SELECT fund_name FROM fund_profiles WHERE fund_code = ?", (fund_code,)
        ).fetchone()
        return row[0] if row else "?"

    def _load_fund_codes(self, conn: sqlite3.Connection) -> list[str]:
        """加载所有基金代码，复用 HoldingSourceAdapter。"""
        from app.cognition.holding_source import (
            HoldingSourceAdapter,
            HoldingSourceUnavailableError,
        )

        try:
            adapter = HoldingSourceAdapter(conn)
            return adapter.list_fund_codes()
        except HoldingSourceUnavailableError:
            return []

    def _get_industry_pe_medians(self, conn: sqlite3.Connection) -> dict[str, float]:
        """获取各行业PE中位数（横截面估值对比基准）。

        从 factordb.stock_factor_values 和 stock_industry_map 关联计算。
        返回: {"半导体": 45.2, "通信设备": 28.5, ...}
        """
        try:
            rows = conn.execute(
                """
                SELECT m.industry_name, f.factor_value
                FROM factordb.stock_factor_values f
                JOIN stock_industry_map m ON f.stock_code = m.stock_code
                WHERE f.factor_code = 'pe' AND f.factor_value > 0
                    AND m.industry_name IS NOT NULL
                """
            ).fetchall()
        except Exception:
            return {}

        industry_pes: dict[str, list[float]] = {}
        for row in rows:
            ind = row[0]
            if ind:
                industry_pes.setdefault(ind, []).append(row[1])

        medians: dict[str, float] = {}
        for ind, pes in industry_pes.items():
            pes.sort()
            n = len(pes)
            if n > 0:
                medians[ind] = round(
                    pes[n // 2] if n % 2 == 1 else (pes[n // 2 - 1] + pes[n // 2]) / 2,
                    1,
                )
        return medians

    def _enrich_cross_sectional(
        self,
        holdings: list[dict[str, Any]],
        valuation: dict[str, Any],
        industry_medians: dict[str, float],
    ) -> None:
        """给估值结果增加横截面对比（vs 同行业PE中位数）。"""
        if not industry_medians:
            return

        # 计算基金持仓的加权行业PE中位数
        total_weight = 0.0
        weighted_median_pe = 0.0
        for h in holdings:
            ind = h.get("industry_name", "")
            w = h.get("weight", 0)
            med = industry_medians.get(ind)
            if med and w:
                weighted_median_pe += med * w
                total_weight += w

        if total_weight > 0 and weighted_median_pe > 0:
            fund_pe = valuation.get("weighted_pe")
            industry_median = round(weighted_median_pe / total_weight, 1)
            valuation["industry_pe_median"] = industry_median
            if fund_pe and fund_pe > 0:
                premium = round((fund_pe / industry_median - 1) * 100, 0)
                valuation["pe_premium_pct"] = premium
                if premium > 50:
                    valuation["cross_sectional_judge"] = "显著高于同行"
                elif premium > 20:
                    valuation["cross_sectional_judge"] = "高于同行"
                elif premium > -20:
                    valuation["cross_sectional_judge"] = "与同行相当"
                else:
                    valuation["cross_sectional_judge"] = "低于同行"

    def _load_revenue_exposure(self, conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
        """加载主营业务构成数据，用于收入暴露分析。

        返回: {"300308": {"光模块": 85.2, "通信设备": 10.3}, ...}
        如果表不存在或无数据，返回空 dict（回退到关键词匹配）。
        """
        try:
            rows = conn.execute(
                """
                SELECT stock_code, segment_name, revenue_pct
                FROM factordb.stock_revenue_composition
                WHERE revenue_pct IS NOT NULL AND revenue_pct > 0
                """
            ).fetchall()
        except Exception:
            return {}

        exposure: dict[str, dict[str, float]] = {}
        for row in rows:
            code = row[0]
            segment = row[1]
            pct = row[2]
            if code and segment:
                exposure.setdefault(code, {})[segment] = pct
        return exposure

    def _load_fund_managers(self, conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        """加载基金经理数据，用于认知验证。

        返回: {"000001": {"name": "张三", "tenure_days": 1825, "return_pct": 15.2, "is_current": 1}, ...}
        只返回在任基金经理。如果表不存在，返回空 dict。
        """
        try:
            rows = conn.execute(
                """
                SELECT fund_code, manager_name, tenure_days, return_pct, is_current
                FROM fund_managers
                WHERE is_current = 1
                ORDER BY tenure_days DESC
                """
            ).fetchall()
        except Exception:
            return {}

        managers: dict[str, dict[str, Any]] = {}
        for row in rows:
            fc = row[0]
            if fc not in managers:  # 只取任职最长的在任经理
                managers[fc] = {
                    "name": row[1],
                    "tenure_days": row[2],
                    "return_pct": row[3],
                    "is_current": row[4],
                }
        return managers

    def _load_financial_depth(self, conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        """加载三大报表最新一期关键指标，用于财务深度验证。

        返回: {"600519": {"revenue":480, "net_profit":250, "gross_margin":91.5, ...}, ...}
        """
        try:
            rows = conn.execute(
                """
                SELECT stock_code,
                       MAX(CASE WHEN report_type='利润表' THEN revenue END) AS revenue,
                       MAX(CASE WHEN report_type='利润表' THEN net_profit END) AS net_profit,
                   MAX(CASE WHEN report_type='利润表' THEN gross_margin END) AS gross_margin,
                   MAX(CASE WHEN report_type='利润表' THEN net_margin END) AS net_margin,
                   MAX(CASE WHEN report_type='利润表' THEN revenue_yoy END) AS revenue_yoy,
                   MAX(CASE WHEN report_type='利润表' THEN profit_yoy END) AS profit_yoy,
                   MAX(CASE WHEN report_type='资产负债表' THEN roe END) AS roe,
                   MAX(CASE WHEN report_type='资产负债表' THEN debt_ratio END) AS debt_ratio,
                   MAX(CASE WHEN report_type='现金流量表' THEN free_cashflow END) AS free_cashflow
                FROM factordb.stock_financial_statements
                WHERE report_date = (SELECT MAX(report_date) FROM factordb.stock_financial_statements)
                GROUP BY stock_code
                """
            ).fetchall()
        except Exception:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            code = row[0]
            if code:
                result[code] = {
                    "revenue": row[1],
                    "net_profit": row[2],
                    "gross_margin": row[3],
                    "net_margin": row[4],
                    "revenue_yoy": row[5],
                    "profit_yoy": row[6],
                    "roe": row[7],
                    "debt_ratio": row[8],
                    "free_cashflow": row[9],
                }
        return result

    def _load_northbound_trend(self, conn: sqlite3.Connection) -> dict[str, float]:
        """加载个股北向资金近期净流入趋势。

        返回: {"600519": 5.2, ...}（正数=净流入，单位亿元）
        """
        try:
            rows = conn.execute(
                """
                SELECT stock_code, SUM(net_buy) as total_net_buy
                FROM factordb.northbound_capital
                GROUP BY stock_code
                """
            ).fetchall()
        except Exception:
            return {}

        return {row[0]: round(row[1] / 10000, 2) for row in rows if row[0] and row[1]}

    def _load_dragon_tiger_stocks(self, conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        """加载近期龙虎榜上榜股票，用于游资动向分析。

        返回: {"600519": {"date":"2026-01-15", "net_buy":2.5, "reason":"日涨幅偏离值达7%"}, ...}
        """
        try:
            rows = conn.execute(
                """
                SELECT stock_code, MAX(trade_date) AS latest_date,
                       AVG(net_buy) AS avg_net_buy, MAX(reason) AS reason,
                       COUNT(*) AS hit_count
                FROM factordb.dragon_tiger_list
                GROUP BY stock_code
                """
            ).fetchall()
        except Exception:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            code = row[0]
            if code:
                result[code] = {
                    "date": row[1],
                    "net_buy": round(row[2] / 10000, 2) if row[2] else None,
                    "reason": row[3],
                    "hit_count": row[4],
                }
        return result

    # ------------------------------------------------------------------
    # 主流程：自动推导5步
    # ------------------------------------------------------------------
    def run(
        self,
        direction: str,
        belief_link: str | None = None,
        conviction: str = "medium",
        time_horizon: str = "long",
        risk_tolerance: str = "moderate",
        max_valuation_percentile: float | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """7步认知转化：采集 -> 拆解 -> 预期差 -> 穿透+门禁 -> 验证 -> 组合 -> 输出

        direction: 投资方向（预设的如"AI"，或自定义的如"新能源"）
        belief_link: 投资人相信的产业链环节（如"光模块/连接"），None表示分析所有环节
        conviction: 信心强度 low/medium/high
        time_horizon: 投资周期 short/mid/long
        risk_tolerance: 风险偏好 conservative/moderate/aggressive
        max_valuation_percentile: 估值分位上限覆盖（None用chain默认值）
        top_n: 返回基金数量
        """
        conn = self._get_conn()
        chain = self._chains.get(direction)
        if not chain:
            chain = self._build_dynamic_chain(conn, direction)

        # 用行业数据库增强产业链环节的股票列表（补充 extra_stocks）
        if self._industry_db and self._industry_db.is_loaded():
            chain = enrich_chain_with_industry_db(chain, self._industry_db)

        judgment = chain["judgment"]

        # 估值硬约束：用户可覆盖默认值
        hard_limits = dict(judgment.get("hard_limits", {}))
        if max_valuation_percentile is not None:
            hard_limits["max_valuation_percentile"] = max_valuation_percentile

        # === Step 1: 认知采集 ===
        step1 = {
            "direction": direction,
            "belief": judgment["belief"],
            "level": judgment["level"],
            "time_horizon": time_horizon,
            "conviction": conviction,
            "risk_tolerance": risk_tolerance,
            "valuation_tolerance": judgment["valuation_tolerance"],
            "key_metric": judgment["key_metric"],
            "portfolio_role": judgment["portfolio_role"],
            "role_weight_range": judgment["role_weight_range"],
            "hard_limits": hard_limits,
        }

        # === Step 2: 产业链拆解 ===
        fund_codes = self._load_fund_codes(conn)
        all_holdings: dict[str, list[dict[str, Any]]] = {}
        for fc in fund_codes:
            h = get_holdings(conn, fc)
            if h:
                all_holdings[fc] = h

        # 收入暴露数据：主营业务构成（无数据时回退到关键词匹配）
        revenue_exposure = self._load_revenue_exposure(conn)

        link_analysis: list[dict[str, Any]] = []
        for link in chain["chain"]:
            if link.get("exclude"):
                continue
            if belief_link and link["name"] != belief_link:
                continue
            all_matched_holdings: list[dict[str, Any]] = []
            for fc, holdings in all_holdings.items():
                stock_kws = link.get("stocks", [])
                ind_kws = link.get("industry_keywords", [])
                for h in holdings:
                    name = h.get("stock_name", "") or ""
                    ind = h.get("industry_name", "") or ""
                    # 关键词子串匹配
                    if any(kw in name for kw in stock_kws) or any(kw in ind for kw in ind_kws):
                        all_matched_holdings.append(h)
                        continue
                    # 行业数据库补充匹配
                    if self._industry_db and self._industry_db.is_loaded():
                        code = h.get("stock_code", "") or ""
                        stock_industries = self._industry_db.get_industries_by_stock(code)
                        if any(kw in si for si in stock_industries for kw in ind_kws):
                            all_matched_holdings.append(h)

            gap = calculate_link_expectation_gap(link, all_matched_holdings, revenue_exposure)
            gap["benefit_logic"] = link.get("benefit_logic", "")
            link_analysis.append(gap)

        link_analysis.sort(key=lambda x: x["score"], reverse=True)

        # === Step 3: 预期差分析 ===
        positive_links = [lk for lk in link_analysis if lk["expectation_gap"] == "positive"]
        neutral_links = [lk for lk in link_analysis if lk["expectation_gap"] == "neutral"]
        negative_links = [lk for lk in link_analysis if lk["expectation_gap"] == "negative"]

        step3 = {
            "positive": positive_links,
            "neutral": neutral_links,
            "negative": negative_links,
            "best_link": link_analysis[0] if link_analysis else None,
            "summary": self._build_gap_summary(positive_links, negative_links, judgment),
        }

        # === Step 4: 资产穿透 + 估值门禁 ===
        good_keywords: list[str] = []
        good_industry_kws: list[str] = []
        for link in chain["chain"]:
            if link.get("exclude"):
                continue
            if belief_link and link["name"] != belief_link:
                continue
            for la in link_analysis:
                if la["link_name"] == link["name"] and la["expectation_gap"] != "negative":
                    good_keywords.extend(link.get("stocks", []))
                    good_industry_kws.extend(link.get("industry_keywords", []))

        fund_matches: list[dict[str, Any]] = []
        gated_out: list[dict[str, Any]] = []

        # 横截面估值基准：各行业PE中位数
        industry_pe_medians = self._get_industry_pe_medians(conn)

        for fc, holdings in all_holdings.items():
            match = self._match_fund_to_chain(
                holdings, good_keywords, good_industry_kws, revenue_exposure,
            )
            if match["match_pct"] >= _MATCH_THRESHOLD:
                valuation = calculate_valuation(holdings)
                # 横截面估值对比
                self._enrich_cross_sectional(holdings, valuation, industry_pe_medians)
                trend = calculate_holding_trend(
                    conn,
                    fc,
                    {
                        "chain_links": {
                            "_": {
                                "stock_keywords": good_keywords,
                                "industry_keywords": good_industry_kws,
                            }
                        }
                    },
                )

                # 估值门禁：检查硬约束
                gate = check_hard_limits(valuation, hard_limits)

                fund_data = {
                    "fund_code": fc,
                    "fund_name": self._get_fund_name(conn, fc),
                    "match_pct": match["match_pct"],
                    "chain_breakdown": match["chain_breakdown"],
                    "valuation": valuation,
                    "trend": trend,
                    "gate": gate,
                    "holdings": holdings,
                }

                if gate["passed"]:
                    fund_matches.append(fund_data)
                else:
                    gated_out.append(fund_data)

        fund_matches.sort(key=lambda x: x["match_pct"], reverse=True)
        top_funds = fund_matches[:top_n]

        # 加载基金经理数据
        fund_managers = self._load_fund_managers(conn)
        # 给基金匹配结果附带经理信息
        for fund in top_funds:
            mgr = fund_managers.get(fund["fund_code"])
            if mgr:
                fund["manager"] = mgr

        # 加载财务深度、北向资金、龙虎榜数据
        financial_depth = self._load_financial_depth(conn)
        northbound_trend = self._load_northbound_trend(conn)
        dragon_tiger = self._load_dragon_tiger_stocks(conn)

        # === Step 5: 认知验证 ===
        validation = validate_cognition(
            link_analysis, top_funds, judgment,
            fund_managers, financial_depth, northbound_trend, dragon_tiger,
        )

        # === Step 6: 组合构建 ===
        role = judgment["portfolio_role"]
        weight_range = judgment["role_weight_range"]

        # 信心强度决定认知仓位总量
        if conviction == "high":
            total_cognition_weight = float(weight_range[1])
        elif conviction == "medium":
            total_cognition_weight = (weight_range[0] + weight_range[1]) / 2
        else:
            total_cognition_weight = weight_range[0] * 0.5

        # 风险偏好决定防守仓位
        if risk_tolerance == "conservative":
            defense_weight_pct = 15.0
        elif risk_tolerance == "aggressive":
            defense_weight_pct = 5.0
        else:
            defense_weight_pct = 10.0

        # 保守策略：跳过减仓基金
        portfolio_candidates = list(fund_matches)
        if risk_tolerance == "conservative":
            portfolio_candidates = [
                f for f in portfolio_candidates if f["trend"]["trend"] != "decreasing"
            ]

        # 防守基金
        defense_fund: dict[str, Any] | None = None
        defense_chain = self._chains.get(chain.get("defense", ""))
        if defense_chain:
            defense_fund = self._find_defense_fund(conn, all_holdings, defense_chain, revenue_exposure)

        # 使用 portfolio_builder 构建组合（接入重叠度/相关性/估值约束）
        # 先尝试均值-方差优化，失败时回退到启发式分配
        optimized = optimize_portfolio(
            portfolio_candidates,
            conn,
            total_cognition_weight=total_cognition_weight,
        )
        if optimized:
            # 优化成功：用优化结果，补上防守基金和现金仓位
            portfolio = optimized
            if defense_fund:
                defense_fund["weight"] = defense_weight_pct
                portfolio["defense_position"] = defense_fund
                portfolio["defense_weight"] = defense_weight_pct
                total = portfolio["total_invested"] + defense_weight_pct
            else:
                portfolio["defense_position"] = None
                portfolio["defense_weight"] = 0.0
                total = portfolio["total_invested"]
            portfolio["cash_pct"] = round(max(0, 100 - total), 1)
            portfolio["optimization_method"] = "mean_variance"
        else:
            # 回退到原有启发式逻辑
            portfolio = build_portfolio(
                portfolio_candidates,
                defense_fund,
                corr_threshold=0.85,
                total_cognition_weight=total_cognition_weight,
                defense_weight_pct=defense_weight_pct,
            )
            portfolio["optimization_method"] = "heuristic"

        # 持仓重叠度分析
        overlap_pairs: list[dict[str, Any]] = []
        selected = portfolio.get("selected_funds", [])
        for i, fa in enumerate(selected):
            for fb in selected[i + 1:]:
                holdings_a = all_holdings.get(fa["fund_code"], [])
                holdings_b = all_holdings.get(fb["fund_code"], [])
                if holdings_a and holdings_b:
                    overlap = calculate_overlap(holdings_a, holdings_b)
                    overlap_pairs.append({
                        "fund_a": fa["fund_code"],
                        "fund_b": fb["fund_code"],
                        **overlap,
                    })

        max_overlap = max((p["overlap_a_pct"] for p in overlap_pairs), default=0)
        high_overlap_pairs = [
            [p["fund_a"], p["fund_b"]]
            for p in overlap_pairs
            if p["overlap_a_pct"] > 40
        ]
        overlap_summary = {
            "max_overlap_pct": round(max_overlap, 1),
            "high_overlap_pairs": high_overlap_pairs,
            "pairs": overlap_pairs,
        }

        # 组合级风险指标
        portfolio_metrics = calculate_portfolio_metrics(
            conn,
            selected,
            defense_fund,
            all_holdings,
        )

        portfolio["role"] = role
        portfolio["total_cognition_weight"] = round(total_cognition_weight, 1)
        portfolio["defense_weight_pct"] = defense_weight_pct
        portfolio["overlap_analysis"] = overlap_summary
        portfolio["metrics"] = portfolio_metrics
        portfolio["rationale"] = self._build_portfolio_rationale(
            judgment, positive_links, negative_links, validation
        )
        portfolio["gated_out"] = [
            {
                "fund_code": f["fund_code"],
                "fund_name": f["fund_name"],
                "match_pct": f["match_pct"],
                "violations": f["gate"]["violations"],
            }
            for f in gated_out[:5]
        ]
        # 前端兼容字段
        portfolio["top_funds"] = portfolio.get("selected_funds", [])
        portfolio["defense_fund"] = defense_fund

        # === 假设追踪闭环：Brier Score + 贝叶斯更新 ===
        tracker = create_tracker_from_cognition(
            thesis_id=f"{direction}_{date.today().isoformat()}",
            validation_result=validation,
            initial_probability=0.5,
        )

        return {
            "direction": direction,
            "available_links": [
                link["name"] for link in chain["chain"] if not link.get("exclude")
            ],
            "belief_link": belief_link,
            "conviction": conviction,
            "step1_judgment": step1,
            "step2_chain": link_analysis,
            "step3_expectation_gap": step3,
            "step4_fund_matches": top_funds,
            "step5_validation": validation,
            "step5_portfolio": portfolio,
            "thesis_tracker": tracker.to_dict(),
            "gated_out_funds": [
                {
                    "fund_code": f["fund_code"],
                    "fund_name": f["fund_name"],
                    "match_pct": f["match_pct"],
                    "violations": f["gate"]["violations"],
                }
                for f in gated_out[:5]
            ],
        }

    # ------------------------------------------------------------------
    # 完整候选证据构建（未截断）
    # ------------------------------------------------------------------
    def build_fund_candidate_evidence(
        self,
        *,
        direction: str,
        belief_link: str | None = None,
        conviction: str = "medium",
        time_horizon: str = "long",
        risk_tolerance: str = "moderate",
        data_snapshot_id: str,
        as_of_date: str,
        explicitly_named_fund_codes: Sequence[str] = (),
        max_valuation_percentile: float | None = None,
    ) -> FundCandidateEvidenceBatch:
        """构建完整基金候选证据（不截断），供治理链路使用。

        与 run() 的区别：
        - 不执行 top_n 截断，所有匹配到的基金都进入 all_candidates
        - 返回结构化的 FundCandidateEvidence 对象
        - 估值门禁拦下的基金同时在 all_candidates 和 valuation_gated_candidates 中
        """
        conn = self._get_conn()
        chain = self._chains.get(direction)
        if not chain:
            chain = self._build_dynamic_chain(conn, direction)

        # 用行业数据库增强产业链环节的股票列表（补充 extra_stocks）
        if self._industry_db and self._industry_db.is_loaded():
            chain = enrich_chain_with_industry_db(chain, self._industry_db)

        judgment = chain["judgment"]
        hard_limits = dict(judgment.get("hard_limits", {}))
        if max_valuation_percentile is not None:
            hard_limits["max_valuation_percentile"] = max_valuation_percentile

        # 加载所有基金持仓
        fund_codes = self._load_fund_codes(conn)
        all_holdings: dict[str, list[dict[str, Any]]] = {}
        for fc in fund_codes:
            h = get_holdings(conn, fc)
            if h:
                all_holdings[fc] = h

        revenue_exposure = self._load_revenue_exposure(conn)

        # 产业链拆解和预期差分析（复用 run() 的逻辑）
        link_analysis: list[dict[str, Any]] = []
        for link in chain["chain"]:
            if link.get("exclude"):
                continue
            if belief_link and link["name"] != belief_link:
                continue
            all_matched_holdings: list[dict[str, Any]] = []
            for fc, holdings in all_holdings.items():
                stock_kws = link.get("stocks", [])
                ind_kws = link.get("industry_keywords", [])
                for h in holdings:
                    name = h.get("stock_name", "") or ""
                    ind = h.get("industry_name", "") or ""
                    # 关键词子串匹配
                    if any(kw in name for kw in stock_kws) or any(kw in ind for kw in ind_kws):
                        all_matched_holdings.append(h)
                        continue
                    # 行业数据库补充匹配
                    if self._industry_db and self._industry_db.is_loaded():
                        code = h.get("stock_code", "") or ""
                        stock_industries = self._industry_db.get_industries_by_stock(code)
                        if any(kw in si for si in stock_industries for kw in ind_kws):
                            all_matched_holdings.append(h)
            gap = calculate_link_expectation_gap(link, all_matched_holdings, revenue_exposure)
            gap["benefit_logic"] = link.get("benefit_logic", "")
            link_analysis.append(gap)

        link_analysis.sort(key=lambda x: x["score"], reverse=True)

        # 构建匹配关键词（非负预期差的环节）
        good_keywords: list[str] = []
        good_industry_kws: list[str] = []
        for link in chain["chain"]:
            if link.get("exclude"):
                continue
            if belief_link and link["name"] != belief_link:
                continue
            for la in link_analysis:
                if la["link_name"] == link["name"] and la["expectation_gap"] != "negative":
                    good_keywords.extend(link.get("stocks", []))
                    good_industry_kws.extend(link.get("industry_keywords", []))

        # 横截面估值基准和基金经理
        industry_pe_medians = self._get_industry_pe_medians(conn)
        fund_managers = self._load_fund_managers(conn)

        # 持仓源适配器（用于获取报告期）
        try:
            holding_adapter = HoldingSourceAdapter(conn)
        except Exception:
            holding_adapter = None

        all_candidates: list[FundCandidateEvidence] = []
        valuation_gated: list[FundCandidateEvidence] = []
        mapped_count = 0
        unrelated_count = 0  # 有持仓但与主题方向不相关
        named_missing_count = 0  # 点名但无持仓数据

        for fc, holdings in all_holdings.items():
            match = self._match_fund_to_chain(
                holdings, good_keywords, good_industry_kws, revenue_exposure,
            )

            is_mapped = match["match_pct"] >= _MATCH_THRESHOLD
            is_named = fc in explicitly_named_fund_codes

            if is_mapped:
                mapped_count += 1
            elif not is_named:
                unrelated_count += 1

            # 未映射且未点名的基金不进入候选
            if not is_mapped and not is_named:
                continue

            # 权重计算（0..1 小数）
            # match_pct 是匹配持仓占总披露持仓的百分数，转为小数比例后乘以总披露权重，
            # 得到实际匹配持仓占基金净值的权重
            disclosed = sum(h["weight"] for h in holdings)
            matched = match["match_pct"] / 100.0 * disclosed
            normalized = matched / disclosed if disclosed > 0 else 0.0

            # 持仓报告期
            holding_report_date: str | None = None
            if holding_adapter:
                dates = holding_adapter.list_report_dates(fc, limit=1)
                holding_report_date = dates[0] if dates else None

            # 持仓年龄（使用 as_of_date，不使用系统今天日期）
            holding_age_days: int | None = None
            if holding_report_date:
                report_date = date.fromisoformat(holding_report_date)
                as_of = date.fromisoformat(as_of_date)
                holding_age_days = (as_of - report_date).days

            # 因子覆盖权重：有 pe 或 pb 因子的持仓权重 / 总披露权重
            factor_coverage = (
                sum(h["weight"] for h in holdings if self._has_required_factor(h)) / disclosed
                if disclosed > 0
                else 0.0
            )

            # 估值
            valuation = calculate_valuation(holdings)
            self._enrich_cross_sectional(holdings, valuation, industry_pe_medians)

            # 持仓趋势
            trend = calculate_holding_trend(
                conn,
                fc,
                {
                    "chain_links": {
                        "_": {
                            "stock_keywords": good_keywords,
                            "industry_keywords": good_industry_kws,
                        }
                    }
                },
            )

            # 估值门禁
            gate = check_hard_limits(valuation, hard_limits)

            # 基金经理
            manager = fund_managers.get(fc)

            # 证据类型来源记录
            evidence_types = self._build_evidence_types(
                holdings, valuation, trend, manager, holding_report_date, link_analysis,
            )

            evidence = FundCandidateEvidence(
                fund_code=fc,
                fund_name=self._get_fund_name(conn, fc),
                matched_holding_weight=matched,
                disclosed_holding_weight=disclosed,
                normalized_match_pct=normalized,
                holding_report_date=holding_report_date,
                holding_age_days=holding_age_days,
                factor_coverage_weight=factor_coverage,
                valuation=valuation,
                holding_trend=trend,
                manager_identity=manager,
                evidence_types=evidence_types,
                policy_conflicts=(),
                data_snapshot_id=data_snapshot_id,
            )

            all_candidates.append(evidence)
            if not gate["passed"]:
                valuation_gated.append(evidence)

        # 点名但无持仓的基金加入候选（评价为 data_insufficient）
        existing_codes = {c.fund_code for c in all_candidates}
        for code in explicitly_named_fund_codes:
            if code not in existing_codes:
                named_missing_count += 1
                fund_name = self._get_fund_name(conn, code)
                all_candidates.append(
                    FundCandidateEvidence(
                        fund_code=code,
                        fund_name=fund_name if fund_name != "?" else None,
                        matched_holding_weight=0.0,
                        disclosed_holding_weight=0.0,
                        normalized_match_pct=0.0,
                        holding_report_date=None,
                        holding_age_days=None,
                        factor_coverage_weight=0.0,
                        valuation={},
                        holding_trend={},
                        manager_identity=None,
                        evidence_types={},
                        policy_conflicts=(),
                        data_snapshot_id=data_snapshot_id,
                        asset_type="fund",
                    )
                )

        return FundCandidateEvidenceBatch(
            all_candidates=tuple(all_candidates),
            valuation_gated_candidates=tuple(valuation_gated),
            scanned_fund_count=len(fund_codes),
            mapped_candidate_count=mapped_count,
            unmapped_due_to_data_count=named_missing_count,
            unrelated_fund_count=unrelated_count,
        )

    @staticmethod
    def _has_required_factor(holding: dict[str, Any]) -> bool:
        """检查持仓是否有 pe 或 pb 因子（非 None）。"""
        return holding.get("pe") is not None or holding.get("pb") is not None

    @staticmethod
    def _build_evidence_types(
        holdings: list[dict[str, Any]],
        valuation: dict[str, Any],
        trend: dict[str, Any],
        manager: dict[str, Any] | None,
        holding_report_date: str | None,
        link_analysis: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """构建证据类型来源记录，关联原始数据来源。"""
        evidence_types: dict[str, list[dict[str, Any]]] = {}

        # business_logic: 来自产业链的受益逻辑
        benefit_logics = [
            la["benefit_logic"] for la in link_analysis if la.get("benefit_logic")
        ]
        if benefit_logics:
            evidence_types["business_logic"] = [
                {"source": "chain", "benefit_logic": bl} for bl in benefit_logics
            ]

        # earnings_or_cashflow: 来自持仓的因子数据
        stocks_with_factors = [
            h["stock_code"] for h in holdings if h.get("pe") or h.get("roe")
        ]
        if stocks_with_factors:
            evidence_types["earnings_or_cashflow"] = [
                {"source": "stock_factor_values", "stocks": stocks_with_factors}
            ]

        # valuation: 来自估值计算
        if valuation.get("weighted_pe") or valuation.get("weighted_pb"):
            evidence_types["valuation"] = [
                {
                    "source": "calculate_valuation",
                    "weighted_pe": valuation.get("weighted_pe"),
                    "weighted_pb": valuation.get("weighted_pb"),
                }
            ]

        # catalyst_or_expectation_gap: 来自预期差分析
        best_gap = link_analysis[0] if link_analysis else None
        if best_gap and best_gap.get("expectation_gap"):
            evidence_types["catalyst_or_expectation_gap"] = [
                {"source": "expectation_gap", "gap": best_gap["expectation_gap"]}
            ]

        # holding_truth: 来自持仓表
        if holdings:
            evidence_types["holding_truth"] = [
                {
                    "source": "stock_holdings",
                    "report_date": holding_report_date,
                    "count": len(holdings),
                }
            ]

        # holding_trend: 来自趋势计算
        if trend.get("periods"):
            evidence_types["holding_trend"] = [
                {"source": "calculate_holding_trend", "trend": trend.get("trend")}
            ]

        # manager_identity: 来自基金经理
        if manager:
            evidence_types["manager_identity"] = [
                {"source": "fund_managers", "name": manager.get("name")}
            ]

        return evidence_types

    # ------------------------------------------------------------------
    # 自定义方向：动态构建产业链
    # ------------------------------------------------------------------
    def _build_dynamic_chain(
        self, conn: sqlite3.Connection, direction: str
    ) -> dict[str, Any]:
        """对自定义方向，从数据库动态构建产业链。

        通过 stock_industry_map 搜索行业名包含方向关键词的股票，按行业分组
        形成产业链环节；judgment 使用自适应默认模板。
        """
        rows = conn.execute(
            """
            SELECT DISTINCT m.stock_code, m.industry_name, m.sector_group,
                   h.stock_name
            FROM stock_industry_map m
            LEFT JOIN stock_holdings h ON m.stock_code = h.stock_code
            WHERE m.industry_name LIKE ?
            """,
            (f"%{direction}%",),
        ).fetchall()

        # 按行业分组，形成产业链环节
        industry_groups: dict[str, dict[str, set[str]]] = {}
        for r in rows:
            ind = r["industry_name"]
            if not ind:
                continue
            if ind not in industry_groups:
                industry_groups[ind] = {"stocks": set(), "codes": set()}
            if r["stock_name"]:
                industry_groups[ind]["stocks"].add(r["stock_name"])
            industry_groups[ind]["codes"].add(r["stock_code"])

        links: list[dict[str, Any]] = []
        for ind, info in industry_groups.items():
            links.append(
                {
                    "name": ind,
                    "stocks": sorted(info["stocks"]),
                    "industry_keywords": [ind],
                    "certainty": "medium",
                    "elasticity": "medium",
                    "benefit_logic": f"{direction}相关",
                }
            )

        return {
            "judgment": {
                "level": "market",
                "belief": f"我相信{direction}方向",
                "time_horizon": "mid",
                "valuation_tolerance": "medium",
                "key_metric": "peg",
                "hard_limits": {
                    "max_valuation_percentile": 85,
                    "max_peg": 2.0,
                },
                "portfolio_role": "satellite",
                "role_weight_range": [5, 15],
            },
            "chain": links,
            "defense": "dividend_defense",
        }

    # ------------------------------------------------------------------
    # 子步骤
    # ------------------------------------------------------------------
    def _match_fund_to_chain(
        self,
        holdings: list[dict[str, Any]],
        stock_kws: list[str],
        ind_kws: list[str],
        revenue_data: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, Any]:
        """计算基金对目标资产的暴露度（收入暴露分析 + 关键词回退 + 行业数据库回退）。

        匹配优先级：
        1. 收入暴露：如果该股票有主营业务构成数据且某业务条目匹配关键词，
           按营收占比加权（例：中际旭创 光模块85% -> 暴露度0.85）
        2. 关键词回退：无主营构成数据时，按股票名/行业名关键词子串匹配（暴露度1.0）
        3. 行业数据库回退：关键词未命中时，用行业数据库反查股票所属行业（暴露度1.0）
        """
        total_weight = sum(h["weight"] for h in holdings)
        if total_weight == 0:
            return {"match_pct": 0, "chain_breakdown": {}}

        all_kws = stock_kws + ind_kws
        matched_weight = 0.0
        for h in holdings:
            name = h.get("stock_name", "") or ""
            ind = h.get("industry_name", "") or ""
            code = h.get("stock_code", "")

            # 1. 尝试收入暴露
            exposure: float | None = None
            if revenue_data and code in revenue_data:
                for segment, pct in revenue_data[code].items():
                    if any(kw in segment for kw in all_kws):
                        exposure = max(exposure or 0, pct / 100.0)

            if exposure is not None:
                matched_weight += h["weight"] * exposure
            elif any(kw in name for kw in stock_kws) or any(kw in ind for kw in ind_kws):
                # 2. 关键词回退（暴露度1.0）
                matched_weight += h["weight"]
            elif self._industry_db and self._industry_db.is_loaded() and ind_kws:
                # 3. 行业数据库回退：反查股票所属行业（暴露度1.0）
                stock_industries = self._industry_db.get_industries_by_stock(code)
                if any(kw in si for si in stock_industries for kw in ind_kws):
                    matched_weight += h["weight"]

        return {
            "match_pct": round(matched_weight / total_weight * 100, 1),
            "chain_breakdown": {},
        }

    def _build_gap_summary(
        self,
        positive: list[dict[str, Any]],
        negative: list[dict[str, Any]],
        judgment: dict[str, Any],
    ) -> str:
        """构建预期差摘要"""
        parts: list[str] = []
        if positive:
            names = "、".join(lk["link_name"] for lk in positive)
            parts.append(f"正预期差环节：{names}（值得配置）")
        if negative:
            names = "、".join(lk["link_name"] for lk in negative)
            parts.append(f"负预期差环节：{names}（暂不配置）")
        if not positive and not negative:
            parts.append("各环节预期差中性，按正常仓位配置")
        return "；".join(parts)

    def _build_portfolio_rationale(
        self,
        judgment: dict[str, Any],
        positive: list[dict[str, Any]],
        negative: list[dict[str, Any]],
        validation: dict[str, Any] | None = None,
    ) -> str:
        """构建仓位建议的理由"""
        role = judgment["portfolio_role"]
        belief = judgment["belief"]
        verdict = validation.get("verdict", "") if validation else ""

        if verdict == "认知有效":
            return f"基于'{belief}'，认知验证通过，建议{role}仓位配置"
        elif verdict == "认知存疑":
            return f"基于'{belief}'，但认知验证存疑，建议降低仓位或等待估值回落"
        elif positive:
            return f"基于'{belief}'，存在正预期差环节，建议{role}仓位配置"
        elif negative:
            return f"基于'{belief}'，但各环节估值偏高，建议降低仓位等待回调"
        else:
            return f"基于'{belief}'，估值合理，建议正常{role}仓位配置"

    def _find_defense_fund(
        self,
        conn: sqlite3.Connection,
        all_holdings: dict[str, list[dict[str, Any]]],
        defense_chain: dict[str, Any],
        revenue_data: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, Any] | None:
        """找防守基金"""
        stock_kws = get_all_stock_keywords(defense_chain)
        ind_kws = get_all_industry_keywords(defense_chain)

        best: dict[str, Any] | None = None
        best_pct = 0.0
        for fc, holdings in all_holdings.items():
            match = self._match_fund_to_chain(holdings, stock_kws, ind_kws, revenue_data)
            if match["match_pct"] > best_pct:
                best_pct = match["match_pct"]
                valuation = calculate_valuation(holdings)
                best = {
                    "fund_code": fc,
                    "fund_name": self._get_fund_name(conn, fc),
                    "match_pct": match["match_pct"],
                    "valuation": valuation,
                }
        return best
