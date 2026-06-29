import csv
import sqlite3
from pathlib import Path

from scripts.audit_relative_label_eligibility import (
    NAV_WINDOW_MIN_SAMPLES,
    classify_relative_eligibility,
    build_eligibility_rows,
)


def test_ready_when_benchmark_ready_and_nav_sufficient():
    row = classify_relative_eligibility(
        benchmark_source_status="ready",
        nav_sample_count=241,
        benchmark_sample_count=241,
    )
    assert row["return_window_status"] == "ready"
    assert row["relative_label_status"] == "relative_label_ready"
    assert row["blocking_reason"] == ""


def test_benchmark_ready_but_nav_insufficient():
    # 100039 典型：基准源 ready，但 NAV 不足 180
    row = classify_relative_eligibility(
        benchmark_source_status="ready",
        nav_sample_count=20,
        benchmark_sample_count=241,
    )
    assert row["return_window_status"] == "nav_window_insufficient"
    assert row["relative_label_status"] == "nav_window_insufficient"
    assert row["blocking_reason"] == "nav_sample_count=20<180"


def test_missing_benchmark_source_attributed_to_source():
    row = classify_relative_eligibility(
        benchmark_source_status="missing_source",
        nav_sample_count=241,
        benchmark_sample_count=0,
    )
    assert row["relative_label_status"] == "benchmark_source_missing"


def test_mapping_required_attributed_to_mapping():
    row = classify_relative_eligibility(
        benchmark_source_status="mapping_required",
        nav_sample_count=241,
        benchmark_sample_count=0,
    )
    assert row["relative_label_status"] == "benchmark_mapping_required"


def test_benchmark_missing_attributed():
    row = classify_relative_eligibility(
        benchmark_source_status="benchmark_missing",
        nav_sample_count=241,
        benchmark_sample_count=0,
    )
    assert row["relative_label_status"] == "benchmark_missing"


def test_aligned_count_uses_min_of_nav_and_benchmark():
    # 基准源 ready 但合成收益本身天数不足（对齐后 < 180）也应判 nav_window_insufficient
    row = classify_relative_eligibility(
        benchmark_source_status="ready",
        nav_sample_count=241,
        benchmark_sample_count=120,
    )
    assert row["return_window_status"] == "nav_window_insufficient"
    assert row["relative_label_status"] == "nav_window_insufficient"
    assert "aligned" in row["blocking_reason"]


def test_nav_window_min_constant():
    assert NAV_WINDOW_MIN_SAMPLES == 180


def _seed_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE nav_history (fund_code TEXT, nav_date TEXT, daily_growth_rate REAL);
        CREATE TABLE benchmark_returns (fund_code TEXT, trade_date TEXT, daily_return REAL);
        """
    )
    # 基金 A: nav 200 天, benchmark 200 天 -> ready
    for i in range(200):
        conn.execute("INSERT INTO nav_history VALUES ('A', ?, 0.001)", (f"d{i}",))
        conn.execute("INSERT INTO benchmark_returns VALUES ('A', ?, 0.001)", (f"d{i}",))
    # 基金 B: nav 20 天, benchmark 200 天 -> nav 不足
    for i in range(20):
        conn.execute("INSERT INTO nav_history VALUES ('B', ?, 0.001)", (f"d{i}",))
    for i in range(200):
        conn.execute("INSERT INTO benchmark_returns VALUES ('B', ?, 0.001)", (f"d{i}",))
    conn.commit()
    conn.close()


def test_build_eligibility_rows_joins_benchmark_quality(tmp_path: Path):
    db = tmp_path / "src.sqlite"
    _seed_db(db)
    quality = {
        "A": {"quality_status": "ready", "blocking_components": ""},
        "B": {"quality_status": "ready", "blocking_components": ""},
    }
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = build_eligibility_rows(conn, ["A", "B"], quality)
    finally:
        conn.close()

    by_code = {r["fund_code"]: r for r in rows}
    assert by_code["A"]["relative_label_status"] == "relative_label_ready"
    assert by_code["B"]["relative_label_status"] == "nav_window_insufficient"
    assert by_code["A"]["nav_sample_count"] == 200
    assert by_code["B"]["nav_sample_count"] == 20
