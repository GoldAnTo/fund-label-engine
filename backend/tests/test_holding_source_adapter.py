"""HoldingSourceAdapter 只读适配器测试。

验证适配器能统一读取 stock_holdings 和 fund_stock_holdings 两种持仓表结构，
输出统一的持仓 dict，且不创建或修改任何表（只读）。
"""
from __future__ import annotations

import sqlite3

import pytest
from app.cognition.holding_source import (
    HoldingSourceAdapter,
    HoldingSourceUnavailableError,
)

# 两种表结构下都期望得到的统一持仓 dict
_EXPECTED_ROW = {
    "fund_code": "000001",
    "holding_report_date": "2025-12-31",
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "weight": 0.12,
    "market": None,
}


# ============================================================
# 辅助函数：构建测试数据库
# ============================================================

def _make_stock_holdings_conn() -> sqlite3.Connection:
    """创建仅含 stock_holdings 表的内存连接（单条数据）。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE stock_holdings ("
        "fund_code TEXT, stock_code TEXT, stock_name TEXT, "
        "report_period TEXT, net_value_ratio REAL)"
    )
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
        ("000001", "600519", "贵州茅台", "2025-12-31", 0.12),
    )
    conn.commit()
    return conn


def _make_fund_stock_holdings_conn() -> sqlite3.Connection:
    """创建仅含 fund_stock_holdings 表的内存连接（单条数据）。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE fund_stock_holdings ("
        "fund_code TEXT, stock_code TEXT, stock_name TEXT, "
        "report_date TEXT, weight REAL, market TEXT)"
    )
    conn.execute(
        "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
        ("000001", "600519", "贵州茅台", "2025-12-31", 0.12, None),
    )
    conn.commit()
    return conn


def _make_multi_period_conn() -> sqlite3.Connection:
    """创建含多基金多报告期的 stock_holdings 连接。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE stock_holdings ("
        "fund_code TEXT, stock_code TEXT, stock_name TEXT, "
        "report_period TEXT, net_value_ratio REAL)"
    )
    conn.executemany(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
        [
            # 基金 000001：两期数据
            ("000001", "600519", "贵州茅台", "2025-12-31", 0.12),
            ("000001", "000858", "五粮液", "2025-12-31", 0.10),
            ("000001", "600519", "贵州茅台", "2025-06-30", 0.08),
            ("000001", "000858", "五粮液", "2025-06-30", 0.06),
            ("000001", "600519", "贵州茅台", "2025-03-31", 0.05),
            ("000001", "600519", "贵州茅台", "2024-12-31", 0.04),
            ("000001", "600519", "贵州茅台", "2024-09-30", 0.03),
            ("000001", "600519", "贵州茅台", "2024-06-30", 0.02),
            # 基金 000002：一期数据
            ("000002", "300750", "宁德时代", "2025-12-31", 0.08),
        ],
    )
    conn.commit()
    return conn


# ============================================================
# 测试 1：stock_holdings 表适配
# ============================================================

def test_stock_holdings_adapter() -> None:
    """stock_holdings 表适配：字段映射 report_period -> holding_report_date, net_value_ratio -> weight, market -> None。"""
    conn = _make_stock_holdings_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        result = adapter.load_holdings("000001", "2025-12-31")
        assert result == [_EXPECTED_ROW]
    finally:
        conn.close()


# ============================================================
# 测试 2：fund_stock_holdings 表适配
# ============================================================

def test_fund_stock_holdings_adapter() -> None:
    """fund_stock_holdings 表适配：字段映射 report_date -> holding_report_date, weight -> weight, market -> market。"""
    conn = _make_fund_stock_holdings_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        result = adapter.load_holdings("000001", "2025-12-31")
        assert result == [_EXPECTED_ROW]
    finally:
        conn.close()


# ============================================================
# 测试 3：两表并存优先 stock_holdings
# ============================================================

def test_both_tables_prefers_stock_holdings() -> None:
    """两表并存时适配器选择 stock_holdings。"""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE stock_holdings ("
            "fund_code TEXT, stock_code TEXT, stock_name TEXT, "
            "report_period TEXT, net_value_ratio REAL)"
        )
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?)",
            ("000001", "600519", "贵州茅台", "2025-12-31", 0.12),
        )
        conn.execute(
            "CREATE TABLE fund_stock_holdings ("
            "fund_code TEXT, stock_code TEXT, stock_name TEXT, "
            "report_date TEXT, weight REAL, market TEXT)"
        )
        conn.execute(
            "INSERT INTO fund_stock_holdings VALUES (?, ?, ?, ?, ?, ?)",
            ("000099", "999999", "其他股票", "2025-12-31", 0.50, "SH"),
        )
        conn.commit()

        adapter = HoldingSourceAdapter(conn)
        assert adapter.schema_name() == "stock_holdings"
        # 读到的是 stock_holdings 的数据，而非 fund_stock_holdings
        result = adapter.load_holdings("000001", "2025-12-31")
        assert len(result) == 1
        assert result[0]["stock_code"] == "600519"
    finally:
        conn.close()


# ============================================================
# 测试 4：两表都不存在抛 HoldingSourceUnavailableError
# ============================================================

def test_no_table_raises_error() -> None:
    """两表都不存在时构造函数抛 HoldingSourceUnavailableError。"""
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(HoldingSourceUnavailableError):
            HoldingSourceAdapter(conn)
    finally:
        conn.close()


# ============================================================
# 测试 5：适配器运行后 sqlite_master 没有新增表（只读不写）
# ============================================================

def test_no_new_tables_created() -> None:
    """适配器运行后 sqlite_master 没有新增表。"""
    conn = _make_multi_period_conn()
    try:
        before = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        adapter = HoldingSourceAdapter(conn)
        adapter.schema_name()
        adapter.list_fund_codes()
        adapter.list_report_dates("000001")
        adapter.load_holdings("000001")

        after = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert before == after
    finally:
        conn.close()


# ============================================================
# 测试 6：factor DB 未 attach 时基础持仓仍可读取
# ============================================================

def test_load_holdings_without_factordb() -> None:
    """没有 factordb schema 时，load_holdings 不崩溃。"""
    conn = _make_stock_holdings_conn()
    try:
        # 确认没有 factordb schema
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "stock_factor_values" not in tables

        adapter = HoldingSourceAdapter(conn)
        result = adapter.load_holdings("000001", "2025-12-31")
        assert len(result) == 1
        assert result[0]["stock_code"] == "600519"
    finally:
        conn.close()


# ============================================================
# 测试 7：list_fund_codes() 返回所有基金代码列表
# ============================================================

def test_list_fund_codes() -> None:
    """list_fund_codes 返回所有基金代码列表（升序）。"""
    conn = _make_multi_period_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        codes = adapter.list_fund_codes()
        assert codes == ["000001", "000002"]
    finally:
        conn.close()


# ============================================================
# 测试 8：list_report_dates() 返回指定基金的报告期列表（倒序，默认 limit=4）
# ============================================================

def test_list_report_dates() -> None:
    """list_report_dates 返回报告期列表（倒序，默认 limit=4）。"""
    conn = _make_multi_period_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        dates = adapter.list_report_dates("000001")
        # 000001 有 6 个报告期，limit=4 只返回最近 4 个
        assert len(dates) == 4
        # 倒序排列
        assert dates == [
            "2025-12-31",
            "2025-06-30",
            "2025-03-31",
            "2024-12-31",
        ]
    finally:
        conn.close()


# ============================================================
# 测试 9：load_holdings 指定 report_date 时返回该期持仓
# ============================================================

def test_load_holdings_with_specific_date() -> None:
    """load_holdings 指定 report_date 时返回该期持仓。"""
    conn = _make_multi_period_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        result = adapter.load_holdings("000001", "2025-06-30")
        assert len(result) == 2
        assert all(r["holding_report_date"] == "2025-06-30" for r in result)
        # 按权重降序排列
        assert result[0]["weight"] >= result[1]["weight"]
    finally:
        conn.close()


# ============================================================
# 测试 10：load_holdings 不指定 report_date 时返回最新一期持仓
# ============================================================

def test_load_holdings_latest_period() -> None:
    """load_holdings 不指定 report_date 时返回最新一期持仓。"""
    conn = _make_multi_period_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        result = adapter.load_holdings("000001")
        assert len(result) == 2
        assert all(r["holding_report_date"] == "2025-12-31" for r in result)
    finally:
        conn.close()


# ============================================================
# 测试 11：schema_name() 返回当前使用的表名
# ============================================================

def test_schema_name_stock_holdings() -> None:
    """schema_name 返回 stock_holdings。"""
    conn = _make_stock_holdings_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        assert adapter.schema_name() == "stock_holdings"
    finally:
        conn.close()


def test_schema_name_fund_stock_holdings() -> None:
    """schema_name 返回 fund_stock_holdings。"""
    conn = _make_fund_stock_holdings_conn()
    try:
        adapter = HoldingSourceAdapter(conn)
        assert adapter.schema_name() == "fund_stock_holdings"
    finally:
        conn.close()
