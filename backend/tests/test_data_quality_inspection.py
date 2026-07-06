"""数据质量巡检测试。"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.data_quality_inspection import (
    inspect_benchmark_gaps,
    inspect_data_snapshots,
    inspect_factor_freshness,
    inspect_holdings_staleness,
    inspect_nav_history,
)


def _make_fund_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE fund_profiles (fund_code TEXT PRIMARY KEY, fund_type TEXT);
        CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL);
        CREATE TABLE stock_holdings (fund_code TEXT, stock_code TEXT, report_period TEXT, net_value_ratio REAL);
        CREATE TABLE benchmark_components (
            fund_code TEXT, component_code TEXT, status TEXT,
            resolved INTEGER, source_text TEXT
        );
        CREATE TABLE benchmark_returns (fund_code TEXT, trade_date TEXT, daily_return REAL);
        CREATE TABLE stock_factor_values (
            stock_code TEXT, factor_code TEXT, factor_value REAL, as_of_date TEXT
        );
        """
    )


def test_inspect_nav_history_flags_stale(tmp_path: Path) -> None:
    db = tmp_path / "q.sqlite"
    today = datetime.now(UTC).date().isoformat()
    stale_date = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
    with sqlite3.connect(db) as conn:
        _make_fund_table(conn)
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, 0.001)", ("000001", today)
        )
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, 0.001)", ("000002", stale_date)
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_nav_history(conn, lookback_days=7)

    assert any(f.category == "nav_history" for f in findings)
    stale = [f for f in findings if f.category == "nav_history"][0]
    assert "000002" in " ".join(stale.samples)


def test_inspect_holdings_staleness(tmp_path: Path) -> None:
    db = tmp_path / "q.sqlite"
    today = datetime.now(UTC).date().isoformat()
    with sqlite3.connect(db) as conn:
        _make_fund_table(conn)
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?)",
            ("000001", "600000", today, 0.05),
        )
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?)",
            ("000002", "600000", "2024-01-01", 0.05),
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_holdings_staleness(conn, max_age_days=120)
    assert any(f.category == "stock_holdings" for f in findings)


def test_inspect_factor_freshness_warns_when_old(tmp_path: Path) -> None:
    db = tmp_path / "q.sqlite"
    old = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
    with sqlite3.connect(db) as conn:
        _make_fund_table(conn)
        conn.execute(
            "INSERT INTO stock_factor_values VALUES (?, ?, ?, ?)",
            ("600000", "pb", 1.5, old),
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_factor_freshness(conn, max_age_days=7)
    assert any(f.severity == "warning" and f.category == "stock_factors" for f in findings)


def test_inspect_factor_freshness_critical_when_empty(tmp_path: Path) -> None:
    db = tmp_path / "q.sqlite"
    with sqlite3.connect(db) as conn:
        _make_fund_table(conn)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_factor_freshness(conn, max_age_days=7)
    assert any(f.severity == "critical" for f in findings)


def test_inspect_benchmark_gaps(tmp_path: Path) -> None:
    db = tmp_path / "q.sqlite"
    with sqlite3.connect(db) as conn:
        _make_fund_table(conn)
        conn.execute(
            "INSERT INTO benchmark_components VALUES (?, ?, ?, ?, ?)",
            ("000001", "X1", "unresolved", 0, "x"),
        )
        conn.execute(
            "INSERT INTO benchmark_components VALUES (?, ?, ?, ?, ?)",
            ("000002", "X1", "resolved", 1, "x"),
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_benchmark_gaps(conn)
    assert any(f.category == "benchmark_components" for f in findings)


def test_inspect_data_snapshots_empty(tmp_path: Path) -> None:
    db = tmp_path / "out.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE data_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                created_at TEXT
            )
            """
        )

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_data_snapshots(conn)
    assert any(f.category == "data_snapshots" and f.severity == "info" for f in findings)


def test_inspect_data_snapshots_recent_no_warning(tmp_path: Path) -> None:
    db = tmp_path / "out.sqlite"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE data_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                created_at TEXT
            )
            """
        )
        conn.execute("INSERT INTO data_snapshots VALUES (?, ?)", ("snap1", now))
        conn.commit()

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        findings = inspect_data_snapshots(conn)
    assert findings == []  # 最近的快照不应报警
