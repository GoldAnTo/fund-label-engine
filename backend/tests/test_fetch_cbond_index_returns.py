"""scripts/fetch_cbond_index_returns.py 测试：财富点位换算日收益 + 落库。

不依赖网络/akshare：用假 CbondSpec 注入 DataFrame 验证换算与写入逻辑。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from scripts.fetch_cbond_index_returns import (
    CbondSpec,
    _to_daily_returns,
    ensure_table,
    fetch_one,
)


def test_to_daily_returns_computes_period_over_period() -> None:
    df = pd.DataFrame(
        {
            "date": ["2026-06-23", "2026-06-24", "2026-06-25"],
            "value": [100.0, 101.0, 100.5],
        }
    )
    rows = _to_daily_returns(df, "2026-06-01", "2026-06-30")
    assert [r[0] for r in rows] == ["2026-06-24", "2026-06-25"]
    assert rows[0][1] == pytest.approx(0.01)
    assert rows[1][1] == pytest.approx(100.5 / 101.0 - 1.0)


def test_to_daily_returns_filters_outside_range() -> None:
    df = pd.DataFrame(
        {
            "date": ["2026-06-20", "2026-06-24", "2026-06-30"],
            "value": [100.0, 101.0, 102.0],
        }
    )
    rows = _to_daily_returns(df, "2026-06-23", "2026-06-25")
    # 06-20 被范围外过滤；06-24 的前值 06-20 也被丢，故 06-24 无前值；只剩 06-30 越界
    assert rows == []


def test_fetch_one_writes_component_returns(tmp_path: Path) -> None:
    db = tmp_path / "cb.sqlite"
    conn = sqlite3.connect(db)
    ensure_table(conn)

    fake_df = pd.DataFrame(
        {"date": ["2026-06-23", "2026-06-24", "2026-06-25"], "value": [100.0, 101.0, 100.5]}
    )
    spec = CbondSpec(
        component_code="LOCAL_CBOND_COMPOSITE",
        name="测试中债综合",
        fetch=lambda: fake_df.copy(),
        source_tag="test:fake",
    )
    n = fetch_one(conn, spec, "2026-06-01", "2026-06-30")
    assert n == 2
    rows = conn.execute(
        "SELECT trade_date, daily_return, source FROM benchmark_component_returns "
        "WHERE component_code=? ORDER BY trade_date",
        ("LOCAL_CBOND_COMPOSITE",),
    ).fetchall()
    assert [r[0] for r in rows] == ["2026-06-24", "2026-06-25"]
    assert rows[0][1] == pytest.approx(0.01)
    assert all(r[2] == "test:fake" for r in rows)
    conn.close()


def test_fetch_one_replaces_existing_rows(tmp_path: Path) -> None:
    db = tmp_path / "cb.sqlite"
    conn = sqlite3.connect(db)
    ensure_table(conn)
    spec = CbondSpec(
        component_code="LOCAL_CBOND_GOV_TOTAL",
        name="测试国债总",
        fetch=lambda: pd.DataFrame(
            {"date": ["2026-06-24", "2026-06-25"], "value": [200.0, 202.0]}
        ),
        source_tag="test",
    )
    fetch_one(conn, spec, "2026-06-01", "2026-06-30")
    # 再灌一次不同数据，应替换而非累加
    spec2 = CbondSpec(
        component_code="LOCAL_CBOND_GOV_TOTAL",
        name="测试国债总",
        fetch=lambda: pd.DataFrame(
            {"date": ["2026-06-24", "2026-06-25"], "value": [200.0, 204.0]}
        ),
        source_tag="test2",
    )
    fetch_one(conn, spec2, "2026-06-01", "2026-06-30")
    rows = conn.execute(
        "SELECT daily_return FROM benchmark_component_returns WHERE component_code=?",
        ("LOCAL_CBOND_GOV_TOTAL",),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == pytest.approx(204.0 / 200.0 - 1.0)
    conn.close()
