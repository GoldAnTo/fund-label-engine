"""从中债登（ChinaBond）经 akshare 拉取债券指数财富点位，换算日收益后写入
``benchmark_component_returns`` 表，供 fetch_benchmark_returns.py 的本地优先通路消费。

解决相对基准 v3 的核心瓶颈：中债综合/中债国债总/中债国债1-3年等指数在东财/新浪/
腾讯/中证官网均无免费当前日收益，但中债登官方财富指数经 akshare 可获取且为当日数据。

财富指数（wealth index）已含票息再投资，其逐日变化率即总收益日收益率，可直接作为
基准组件日收益，无需再做代理。仅灌入 akshare 中债登指数列表内确实存在的指数；
中债总指数/中国债券总指数不在列表内，保留 local 占位符不强行代理。
"""
from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CbondSpec:
    component_code: str
    name: str
    fetch: Callable[[], pd.DataFrame]
    source_tag: str


def _specs() -> list[CbondSpec]:
    import akshare as ak

    return [
        CbondSpec(
            "LOCAL_CBOND_COMPOSITE",
            "中债综合财富指数",
            lambda: ak.bond_composite_index_cbond(indicator="财富", period="总值"),
            "akshare:bond_composite_index_cbond:财富:总值",
        ),
        CbondSpec(
            "LOCAL_CBOND_GOV_TOTAL",
            "中债国债总财富指数",
            lambda: ak.bond_index_general_cbond(
                index_category="国债总指数", indicator="财富", period="总值"
            ),
            "akshare:bond_index_general_cbond:国债总指数:财富:总值",
        ),
        CbondSpec(
            "LOCAL_CBOND_GOV_1_3Y",
            "中债国债1-3年财富指数",
            lambda: ak.bond_treasury_index_cbond(indicator="财富", period="1-3Y"),
            "akshare:bond_treasury_index_cbond:财富:1-3Y",
        ),
    ]


def _approx_specs() -> list[CbondSpec]:
    """显式近似组件（不是精确指数源）。

    中债总指数 / 中国债券总指数 / 标普中国债券指数在 akshare 中债登列表内没有
    对应精确接口。这里用真实的“中债综合财富指数（总值）”作为可审计的近似：
    - 三者都是全市场债券总收益口径，含票息再投资，走势高度接近；
    - 债券组件在这些基金基准里只占 15%~45%，近似误差对复合基准影响有限；
    - source 前缀统一为 ``approx:``，审计和报告可明确区分“近似”与“精确源”。

    默认不启用，必须显式 ``--include-approx`` 才灌，避免把近似误当精确源。
    """
    import akshare as ak

    def composite() -> object:
        return ak.bond_composite_index_cbond(indicator="财富", period="总值")
    return [
        CbondSpec(
            "LOCAL_CBOND_TOTAL",
            "中债总指数（用中债综合财富指数近似）",
            composite,
            "approx:cbond_composite_for_cbond_total",
        ),
        CbondSpec(
            "LOCAL_CHINA_BOND_TOTAL",
            "中国债券总指数（用中债综合财富指数近似）",
            composite,
            "approx:cbond_composite_for_china_bond_total",
        ),
        CbondSpec(
            "LOCAL_SP_CHINA_BOND",
            "标普中国债券指数（用中债综合财富指数近似）",
            composite,
            "approx:cbond_composite_for_sp_china_bond",
        ),
    ]


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_component_returns (
            component_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            daily_return REAL NOT NULL,
            source TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (component_code, trade_date)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_benchmark_component_returns_code "
        "ON benchmark_component_returns(component_code, trade_date)"
    )


def _to_daily_returns(df: pd.DataFrame, start_date: str, end_date: str) -> list[tuple[str, float]]:
    """财富点位 -> 日收益率；按日期升序，返回 (YYYY-MM-DD, daily_return)。"""
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values("date")
    work = work[(work["date"] >= start_date) & (work["date"] <= end_date)]
    values = work["value"].astype(float).to_numpy()
    dates = work["date"].dt.strftime("%Y-%m-%d").to_numpy()
    rows: list[tuple[str, float]] = []
    for i in range(1, len(values)):
        prev, cur = values[i - 1], values[i]
        if prev <= 0:
            continue
        rows.append((str(dates[i]), cur / prev - 1.0))
    return rows


def fetch_one(conn: sqlite3.Connection, spec: CbondSpec, start_date: str, end_date: str) -> int:
    df = spec.fetch()
    if "date" not in df.columns or "value" not in df.columns:
        raise RuntimeError(f"{spec.name}: 返回缺 date/value 列，实际 {list(df.columns)}")
    rows = _to_daily_returns(df, start_date, end_date)
    conn.execute(
        "DELETE FROM benchmark_component_returns WHERE component_code = ?",
        (spec.component_code,),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO benchmark_component_returns "
        "(component_code, trade_date, daily_return, source, fetched_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        [(spec.component_code, d, r, spec.source_tag) for d, r in rows],
    )
    conn.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="从中债登经 akshare 拉取债券指数日收益，写入 benchmark_component_returns。"
    )
    parser.add_argument("--db", required=True, help="fundData/source SQLite 路径")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--codes",
        help="可选，逗号分隔的 component_code 列表，仅灌这些指数；默认全部",
    )
    parser.add_argument(
        "--include-approx",
        action="store_true",
        help=(
            "额外灌入显式近似组件（中债总/中国债券总/标普中国债券，用中债综合财富指数近似，"
            "source 前缀 approx:）。默认关闭。"
        ),
    )
    args = parser.parse_args(argv)

    specs = _specs()
    if args.include_approx:
        specs = specs + _approx_specs()
    if args.codes:
        wanted = {c.strip() for c in args.codes.split(",") if c.strip()}
        specs = [s for s in specs if s.component_code in wanted]
    if not specs:
        print("no matching specs")
        return 1

    conn = sqlite3.connect(args.db)
    try:
        ensure_table(conn)
        for spec in specs:
            rows = fetch_one(conn, spec, args.start_date, args.end_date)
            print(f"{spec.component_code:24s} {spec.name}: {rows} rows -> {args.db}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
