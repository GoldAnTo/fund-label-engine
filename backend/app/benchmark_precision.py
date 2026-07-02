"""基金基准精度标注：区分精确源与显式近似源。

上一步用真实中债综合财富指数(akshare)对中债总/中国债券总/标普中国债券做了
可审计的近似，source 前缀统一为 ``approx:``。为了不让“近似基准”算出来的
Alpha/超额收益被当成“精确基准”结论使用，这里提供一个共享判定：

- ``approx``：该基金的复合基准里至少有一个组件用的是 ``approx:`` 源。
- ``exact``：该基金已合成出 benchmark_returns，且没有用到任何 approx 组件。
- ``none``：该基金没有可用基准收益（benchmark_data_missing）。

所有报告层与 API 层复用这一个判定，避免各处口径不一致。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def benchmark_precision_by_fund(source_db_path: str | Path) -> dict[str, str]:
    """返回 {fund_code: 'exact'|'approx'|'none'}。

    只读 source DB 的 benchmark 表，不写任何数据。source DB 不存在或缺表时返回空 dict。
    """
    path = str(source_db_path)
    if not Path(path).exists():
        return {}
    conn = sqlite3.connect(path)
    try:
        if not _table_exists(conn, "benchmark_components"):
            return {}

        approx_codes: set[str] = set()
        if _table_exists(conn, "benchmark_component_returns"):
            approx_codes = {
                str(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT component_code FROM benchmark_component_returns "
                    "WHERE source LIKE 'approx:%'"
                ).fetchall()
            }

        funds_with_returns: set[str] = set()
        if _table_exists(conn, "benchmark_returns"):
            funds_with_returns = {
                str(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT fund_code FROM benchmark_returns"
                ).fetchall()
            }

        approx_funds: set[str] = set()
        if approx_codes:
            placeholders = ",".join("?" for _ in approx_codes)
            approx_funds = {
                str(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT fund_code FROM benchmark_components "
                    f"WHERE component_code IN ({placeholders})",
                    tuple(approx_codes),
                ).fetchall()
            }

        result: dict[str, str] = {}
        for fund_code in funds_with_returns:
            result[fund_code] = "approx" if fund_code in approx_funds else "exact"
        return result
    finally:
        conn.close()
