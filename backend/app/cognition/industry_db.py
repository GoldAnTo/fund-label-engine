"""基于申万行业分类的产业链数据库。

支持从多种数据源加载行业-股票映射：
1. sw_industry_stocks 表（由 scripts/fetch_industry_data.py 抓取申万行业分类生成）
2. stock_industry_map 表（已有的人工/CSV 导入的行业映射）
3. fund_industry_allocations 表（基金行业配置，通过关联 stock_holdings 间接推导）

加载后提供正向查询（行业 -> 股票）和反向查询（股票 -> 行业），
供 CognitionEngine 在产业链匹配时作为关键词匹配的补充。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class IndustryDB:
    """行业-股票映射数据库，支持反向查询。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None
        # stock_code -> list[str]（行业名称列表）
        self._stock_to_industries: dict[str, list[str]] | None = None
        # industry_name -> list[str]（股票代码列表）
        self._industry_to_stocks: dict[str, list[str]] | None = None

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load_from_sqlite(self, conn: sqlite3.Connection) -> None:
        """从 SQLite 连接加载行业-股票映射。

        依次尝试以下表（命中第一个有数据的即返回）：
        1. sw_industry_stocks：申万行业成分股（fetch_industry_data.py 生成）
        2. stock_industry_map：已有行业映射表
        3. fund_industry_allocations：基金行业配置，关联 stock_holdings 间接推导
        """
        self._stock_to_industries = {}
        self._industry_to_stocks = {}

        # 1. 优先从 sw_industry_stocks 加载（最完整的申万分类数据）
        if self._table_exists(conn, "sw_industry_stocks"):
            rows = conn.execute(
                "SELECT stock_code, industry_name FROM sw_industry_stocks "
                "WHERE stock_code IS NOT NULL AND industry_name IS NOT NULL"
            ).fetchall()
            for row in rows:
                code, ind = row[0], row[1]
                if code and ind:
                    self._stock_to_industries.setdefault(code, [])
                    if ind not in self._stock_to_industries[code]:
                        self._stock_to_industries[code].append(ind)
                    self._industry_to_stocks.setdefault(ind, [])
                    if code not in self._industry_to_stocks[ind]:
                        self._industry_to_stocks[ind].append(code)
            if self._stock_to_industries:
                return

        # 2. 从 stock_industry_map 加载
        if self._table_exists(conn, "stock_industry_map"):
            rows = conn.execute(
                "SELECT stock_code, industry_name FROM stock_industry_map "
                "WHERE stock_code IS NOT NULL AND industry_name IS NOT NULL"
            ).fetchall()
            for row in rows:
                code, ind = row[0], row[1]
                if code and ind:
                    self._stock_to_industries.setdefault(code, [])
                    if ind not in self._stock_to_industries[code]:
                        self._stock_to_industries[code].append(ind)
                    self._industry_to_stocks.setdefault(ind, [])
                    if code not in self._industry_to_stocks[ind]:
                        self._industry_to_stocks[ind].append(code)
            if self._stock_to_industries:
                return

        # 3. 从 fund_industry_allocations 间接推导（关联 stock_holdings）
        if self._table_exists(conn, "fund_industry_allocations") and self._table_exists(
            conn, "stock_holdings"
        ):
            rows = conn.execute(
                "SELECT DISTINCT h.stock_code, f.industry "
                "FROM fund_industry_allocations f "
                "JOIN stock_holdings h ON f.fund_code = h.fund_code "
                "WHERE h.stock_code IS NOT NULL AND f.industry IS NOT NULL"
            ).fetchall()
            for row in rows:
                code, ind = row[0], row[1]
                if code and ind:
                    self._stock_to_industries.setdefault(code, [])
                    if ind not in self._stock_to_industries[code]:
                        self._stock_to_industries[code].append(ind)
                    self._industry_to_stocks.setdefault(ind, [])
                    if code not in self._industry_to_stocks[ind]:
                        self._industry_to_stocks[ind].append(code)

    def load(self) -> None:
        """从构造时指定的 SQLite 文件路径加载数据。"""
        if not self._db_path or not self._db_path.exists():
            self._stock_to_industries = {}
            self._industry_to_stocks = {}
            return
        conn = sqlite3.connect(str(self._db_path))
        try:
            self.load_from_sqlite(conn)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def is_loaded(self) -> bool:
        """是否已成功加载行业数据。"""
        return self._stock_to_industries is not None and len(self._stock_to_industries) > 0

    def get_stocks_by_industry(self, industry_keyword: str) -> list[str]:
        """根据行业关键词查找相关股票代码。

        对行业名称做子串匹配，返回所有匹配行业的成分股代码列表。
        """
        if not self._industry_to_stocks or not industry_keyword:
            return []
        result: list[str] = []
        for ind_name, stocks in self._industry_to_stocks.items():
            if industry_keyword in ind_name:
                result.extend(stocks)
        # 去重，保持顺序
        seen: set[str] = set()
        deduped: list[str] = []
        for s in result:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        return deduped

    def get_industries_by_stock(self, stock_code: str) -> list[str]:
        """根据股票代码查找所属行业列表。"""
        if not self._stock_to_industries or not stock_code:
            return []
        return self._stock_to_industries.get(stock_code, [])

    def match_fund_to_chain(
        self,
        holdings: list[dict[str, Any]],
        stock_keywords: list[str],
        industry_keywords: list[str],
    ) -> dict[str, Any]:
        """增强版基金-产业链匹配。

        匹配优先级：
        1. 关键词子串匹配：股票名含 stock_keywords 或行业名含 industry_keywords
        2. 行业数据库补充匹配：通过股票代码反查行业，与 industry_keywords 做子串匹配

        返回: {"matched_holdings": [...], "total_weight": float}
        """
        matched_holdings: list[dict[str, Any]] = []
        total_weight = 0.0

        for h in holdings:
            name = h.get("stock_name", "") or ""
            ind = h.get("industry_name", "") or ""
            code = h.get("stock_code", "") or ""
            weight = h.get("weight", 0) or 0

            # 1. 关键词子串匹配
            if any(kw in name for kw in stock_keywords) or any(kw in ind for kw in industry_keywords):
                matched_holdings.append(h)
                total_weight += weight
                continue

            # 2. 行业数据库补充匹配
            stock_industries = self.get_industries_by_stock(code)
            if any(kw in si for si in stock_industries for kw in industry_keywords):
                matched_holdings.append(h)
                total_weight += weight

        return {
            "matched_holdings": matched_holdings,
            "total_weight": round(total_weight, 4),
        }

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        """检查表是否存在。"""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None
