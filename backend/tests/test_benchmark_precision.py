import sqlite3
from pathlib import Path

from app.benchmark_precision import benchmark_precision_by_fund


def _make_source(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE benchmark_components (
            fund_code TEXT, component_order INTEGER, component_code TEXT
        );
        CREATE TABLE benchmark_component_returns (
            component_code TEXT, trade_date TEXT, daily_return REAL, source TEXT
        );
        CREATE TABLE benchmark_returns (
            fund_code TEXT, trade_date TEXT, daily_return REAL
        );
        """
    )
    # 基金 A：精确基准（沪深300 + 中债国债总，皆非 approx）
    conn.executemany(
        "INSERT INTO benchmark_components(fund_code, component_order, component_code) VALUES (?,?,?)",
        [("A", 0, "000300"), ("A", 1, "LOCAL_CBOND_GOV_TOTAL")],
    )
    # 基金 B：含 approx 债券组件
    conn.executemany(
        "INSERT INTO benchmark_components(fund_code, component_order, component_code) VALUES (?,?,?)",
        [("B", 0, "000300"), ("B", 1, "LOCAL_CBOND_TOTAL")],
    )
    conn.executemany(
        "INSERT INTO benchmark_component_returns(component_code, trade_date, daily_return, source) VALUES (?,?,?,?)",
        [
            ("LOCAL_CBOND_GOV_TOTAL", "2026-01-02", 0.0001, "akshare:bond_index_general_cbond"),
            ("LOCAL_CBOND_TOTAL", "2026-01-02", 0.0001, "approx:cbond_composite_for_cbond_total"),
        ],
    )
    conn.executemany(
        "INSERT INTO benchmark_returns(fund_code, trade_date, daily_return) VALUES (?,?,?)",
        [("A", "2026-01-02", 0.001), ("B", "2026-01-02", 0.001)],
    )
    conn.commit()
    conn.close()


def test_precision_distinguishes_exact_and_approx(tmp_path: Path) -> None:
    db = tmp_path / "source.sqlite"
    _make_source(db)

    precision = benchmark_precision_by_fund(db)

    assert precision["A"] == "exact"
    assert precision["B"] == "approx"


def test_precision_omits_funds_without_returns(tmp_path: Path) -> None:
    db = tmp_path / "source.sqlite"
    _make_source(db)
    # 基金 C 有 approx 组件映射但没有合成 benchmark_returns，不应算作 approx-ready
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO benchmark_components(fund_code, component_order, component_code) VALUES ('C', 0, 'LOCAL_CBOND_TOTAL')"
    )
    conn.commit()
    conn.close()

    precision = benchmark_precision_by_fund(db)

    assert "C" not in precision


def test_precision_missing_db_returns_empty(tmp_path: Path) -> None:
    assert benchmark_precision_by_fund(tmp_path / "nope.sqlite") == {}
