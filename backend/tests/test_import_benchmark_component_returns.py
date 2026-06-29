import sqlite3
from pathlib import Path

import pytest

from scripts.import_benchmark_component_returns import (
    ALLOWED_COMPONENT_CODES,
    RowError,
    import_csv,
    validate_row,
)


def _valid_row():
    return {
        "component_code": "H11001",
        "trade_date": "2025-06-25",
        "daily_return": "0.0012",
        "source": "csindex_official",
    }


def test_validate_row_accepts_valid_decimal_return():
    parsed = validate_row(_valid_row())
    assert parsed == ("H11001", "2025-06-25", 0.0012, "csindex_official")


def test_validate_row_rejects_component_not_in_whitelist():
    row = _valid_row() | {"component_code": "000300"}
    with pytest.raises(RowError, match="not in whitelist"):
        validate_row(row)


def test_validate_row_rejects_percentage_like_return():
    # 1.2 看起来像把 0.012 误填成百分数，单日收益不可能 120%
    row = _valid_row() | {"daily_return": "1.2"}
    with pytest.raises(RowError, match="out of plausible daily range"):
        validate_row(row)


def test_validate_row_rejects_missing_or_unknown_source():
    with pytest.raises(RowError, match="source is required"):
        validate_row(_valid_row() | {"source": ""})
    with pytest.raises(RowError, match="source is required"):
        validate_row(_valid_row() | {"source": "unknown"})


def test_validate_row_rejects_bad_date():
    with pytest.raises(RowError, match="invalid trade_date"):
        validate_row(_valid_row() | {"trade_date": "2025/06/25"})


def test_import_csv_is_idempotent_on_component_date(tmp_path: Path):
    db = tmp_path / "src.sqlite"
    csv_path = tmp_path / "bond.csv"
    csv_path.write_text(
        "component_code,trade_date,daily_return,source\n"
        "H11001,2025-06-25,0.0012,csindex\n"
        "H11001,2025-06-25,0.0034,csindex\n",
        encoding="utf-8",
    )
    with sqlite3.connect(db) as conn:
        stats = import_csv(conn, csv_path, min_rows=1)
        rows = conn.execute(
            "SELECT daily_return FROM benchmark_component_returns "
            "WHERE component_code='H11001' AND trade_date='2025-06-25'"
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == 0.0034
    assert stats["imported"] == 2
    assert stats["components"]["H11001"] == 1


def test_import_csv_rejects_when_rows_below_min(tmp_path: Path):
    db = tmp_path / "src.sqlite"
    csv_path = tmp_path / "bond.csv"
    csv_path.write_text(
        "component_code,trade_date,daily_return,source\n"
        "H11001,2025-06-25,0.0012,csindex\n",
        encoding="utf-8",
    )
    with sqlite3.connect(db) as conn:
        with pytest.raises(RowError, match="below min_rows"):
            import_csv(conn, csv_path, min_rows=180)
        # 校验失败时不得写入任何行
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='benchmark_component_returns'"
        ).fetchone()
        if table:
            count = conn.execute(
                "SELECT count(*) FROM benchmark_component_returns"
            ).fetchone()[0]
            assert count == 0


def test_allowed_whitelist_contents():
    assert {
        "H11001",
        "H11006",
        "H11008",
        "H11009",
        "000998",
        "000964",
        "000942",
        "931027",
        "399102",
        "399101",
        "LOCAL_CBOND_COMPOSITE",
        "LOCAL_CBOND_TOTAL",
    }.issubset(ALLOWED_COMPONENT_CODES)
    assert "LOCAL_CHINA_BOND_TOTAL" in ALLOWED_COMPONENT_CODES
