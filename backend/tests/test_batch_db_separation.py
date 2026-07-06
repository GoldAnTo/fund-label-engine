import json
import sqlite3
from pathlib import Path

import pytest
from app.batch import (
    run_batch,
    validate_equity_factor_inputs,
    validate_equity_factor_outputs,
)
from app.main import create_app
from fastapi.testclient import TestClient

from scripts.seed_sample_db import seed


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    db = tmp_path / "fundData.sqlite"
    seed(db)
    return db


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def test_separated_dbs_keep_source_untouched_and_results_in_output(
    source_db: Path, tmp_path: Path
) -> None:
    output_db = tmp_path / "label_results.sqlite"
    source_tables_before = _table_names(source_db)

    run_id, processed = run_batch(source_db=source_db, output_db=output_db)

    assert processed >= 1
    # 源库不应该多出任何结果表
    assert _table_names(source_db) == source_tables_before
    # 结果表都落在 output_db
    output_tables = _table_names(output_db)
    assert {
        "label_runs",
        "fund_label_results",
        "fund_label_evidence",
        "feature_values",
        "fund_run_coverage",
        "label_definitions",
        "fund_factor_exposures",
    }.issubset(output_tables)

    # API 走 output_db 能直接查到 run / fund / report
    client = TestClient(create_app(db_path=output_db))
    assert client.get(f"/v1/runs/{run_id}").status_code == 200
    report = client.get(f"/v1/runs/{run_id}/funds/000001/report").json()
    assert report["fund_code"] == "000001"
    assert report["summary"]["label_count"] >= 1
    assert "factor_exposures" in report


def test_batch_persists_factor_exposures_in_output_not_source(
    source_db: Path, tmp_path: Path
) -> None:
    with sqlite3.connect(source_db) as conn:
        conn.executemany(
            "INSERT INTO stock_factors "
            "(stock_code, factor_date, pb, roe, dividend_yield, revenue_growth, "
            " profit_growth, market_cap_bucket, valuation_percentile, style) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("600519", "2026-03-01", 1.0, 0.20, 0.04, 0.18, 0.12, "large", 0.20, "value"),
                ("000858", "2026-03-01", 1.2, 0.18, 0.035, 0.17, 0.10, "large", 0.25, "value"),
            ],
        )
        conn.commit()
    output_db = tmp_path / "label_results.sqlite"

    run_batch(source_db=source_db, output_db=output_db)

    assert "fund_factor_exposures" not in _table_names(source_db)
    with sqlite3.connect(output_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM fund_factor_exposures").fetchone()[0]
    assert count >= 1


def test_separated_mode_opens_source_read_only(
    source_db: Path, tmp_path: Path
) -> None:
    output_db = tmp_path / "label_results.sqlite"

    # 把源库设为只读权限，确认双库模式仍能跑（验证它没有去写源库）
    source_db.chmod(0o400)
    try:
        run_id, processed = run_batch(source_db=source_db, output_db=output_db)
    finally:
        source_db.chmod(0o600)

    assert processed >= 1
    assert run_id


def test_single_db_mode_still_works(source_db: Path) -> None:
    # 老用法 run_batch(db_path) 必须保持不变
    run_id, processed = run_batch(source_db)

    assert processed >= 1
    assert "label_runs" in _table_names(source_db)


def test_run_batch_rejects_ambiguous_arguments(tmp_path: Path) -> None:
    db = tmp_path / "a.sqlite"
    seed(db)

    with pytest.raises(ValueError):
        run_batch(db_path=db, source_db=db)

    with pytest.raises(ValueError):
        run_batch()


def test_cli_requires_output_when_source_is_given(
    source_db: Path, capsys: pytest.CaptureFixture
) -> None:
    from app.batch import main

    with pytest.raises(SystemExit):
        main(["--source-db", str(source_db)])


def test_cli_accepts_rule_config_file(source_db: Path, tmp_path: Path) -> None:
    from app.batch import main

    config = tmp_path / "rules.json"
    config.write_text('{"fee_low_threshold": 0.01}', encoding="utf-8")

    exit_code = main(["--db", str(source_db), "--rule-config", str(config)])

    assert exit_code == 0
    with sqlite3.connect(source_db) as conn:
        snapshot_raw = conn.execute(
            "SELECT rule_snapshot_json FROM label_runs ORDER BY run_at DESC LIMIT 1"
        ).fetchone()[0]
    snapshot = json.loads(snapshot_raw)
    assert snapshot["fee_low_threshold"] == 0.01


def test_equity_factor_preflight_rejects_empty_factor_db(
    source_db: Path,
    tmp_path: Path,
) -> None:
    factor_db = tmp_path / "empty_factors.sqlite"
    with sqlite3.connect(factor_db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_factor_values (
                stock_code TEXT,
                factor_code TEXT,
                factor_value REAL,
                as_of_date TEXT,
                source TEXT
            )
            """
        )

    with pytest.raises(ValueError, match="stock factor rows"):
        validate_equity_factor_inputs(source_db=source_db, factor_db=factor_db)


def test_equity_factor_output_validation_requires_exposures_and_ready_pool(
    tmp_path: Path,
) -> None:
    output_db = tmp_path / "label_results.sqlite"
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_factor_exposures (
                fund_code TEXT,
                report_date TEXT,
                factor_code TEXT,
                exposure_value REAL,
                coverage_weight REAL,
                holding_total_weight REAL,
                stock_count INTEGER,
                covered_stock_count INTEGER,
                source TEXT,
                as_of_date TEXT,
                computed_at TEXT
            );
            CREATE TABLE fund_group_results (
                run_id TEXT,
                fund_code TEXT,
                group_code TEXT,
                group_name TEXT,
                group_type TEXT,
                reason_code TEXT,
                evidence TEXT,
                source TEXT
            );
            CREATE TABLE label_calculation_states (
                run_id TEXT,
                fund_code TEXT,
                label_code TEXT,
                label_name TEXT,
                category TEXT,
                state TEXT,
                reason_code TEXT,
                observed TEXT,
                threshold TEXT,
                source TEXT,
                message TEXT
            );
            """
        )

    with pytest.raises(ValueError, match="fund_factor_exposures"):
        validate_equity_factor_outputs(output_db, run_id="r1")

    with sqlite3.connect(output_db) as conn:
        conn.execute(
            "INSERT INTO fund_factor_exposures VALUES "
            "('000001', '2025-12-31', 'factor_coverage_weight', 0.8, 0.8, 0.8, "
            "10, 10, 'test', '2026-06-23', 'now')"
        )
        conn.execute(
            "INSERT INTO label_calculation_states VALUES "
            "('r1', '000001', 'deep_value', '深度价值', 'holding_style', "
            "'not_triggered', 'threshold_not_met', '0.1', '0.6', 'test', '')"
        )

    with pytest.raises(ValueError, match="style_factor_ready_pool"):
        validate_equity_factor_outputs(output_db, run_id="r1")

    with sqlite3.connect(output_db) as conn:
        conn.execute(
            "INSERT INTO fund_group_results VALUES "
            "('r1', '000001', 'style_factor_ready_pool', '风格因子可用池', "
            "'style', 'stock_factors_available', '{}', 'stock_factors')"
        )

    validate_equity_factor_outputs(output_db, run_id="r1")


def test_equity_factor_validation_requires_contributions_for_triggered_styles(
    tmp_path: Path,
) -> None:
    """触发了风格标签的基金，必须有对应的股票级贡献明细，否则校验失败。"""
    output_db = tmp_path / "label_results.sqlite"
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_factor_exposures (
                fund_code TEXT, report_date TEXT, factor_code TEXT,
                exposure_value REAL, coverage_weight REAL, holding_total_weight REAL,
                stock_count INTEGER, covered_stock_count INTEGER, source TEXT,
                as_of_date TEXT, computed_at TEXT
            );
            CREATE TABLE fund_group_results (
                run_id TEXT, fund_code TEXT, group_code TEXT, group_name TEXT,
                group_type TEXT, reason_code TEXT, evidence TEXT, source TEXT
            );
            CREATE TABLE label_calculation_states (
                run_id TEXT, fund_code TEXT, label_code TEXT, label_name TEXT,
                category TEXT, state TEXT, reason_code TEXT, observed TEXT,
                threshold TEXT, source TEXT, message TEXT
            );
            CREATE TABLE fund_label_results (
                run_id TEXT, fund_code TEXT, label_code TEXT, label_name TEXT,
                category TEXT, confidence REAL, status TEXT
            );
            CREATE TABLE fund_equity_style_contributions (
                fund_code TEXT, report_date TEXT, stock_code TEXT, stock_name TEXT,
                weight REAL, style_code TEXT, style_name TEXT, matched INTEGER,
                contribution_weight REAL, factor_values_json TEXT,
                rule_snapshot_json TEXT, factor_as_of_date TEXT, source TEXT,
                computed_at TEXT
            );
            INSERT INTO fund_factor_exposures VALUES
                ('000001','2025-12-31','factor_coverage_weight',0.8,0.8,0.8,
                 10,10,'test','2026-06-23','now');
            INSERT INTO label_calculation_states VALUES
                ('r1','000001','dividend_steady','红利稳健','holding_style',
                 'triggered','threshold_met','0.6','0.5','test','');
            INSERT INTO fund_group_results VALUES
                ('r1','000001','style_factor_ready_pool','风格因子可用池',
                 'style','stock_factors_available','{}','stock_factors');
            INSERT INTO fund_label_results VALUES
                ('r1','000001','dividend_steady','红利稳健','style',0.9,'active');
            """
        )

    with pytest.raises(ValueError, match="equity style contributions"):
        validate_equity_factor_outputs(output_db, run_id="r1")

    with sqlite3.connect(output_db) as conn:
        conn.execute(
            "INSERT INTO fund_equity_style_contributions VALUES "
            "('000001','2025-12-31','600002','红利股票',0.082,'dividend_steady',"
            "'红利稳健',1,0.082,'{}','{}','2026-06-23','test','now')"
        )

    validate_equity_factor_outputs(output_db, run_id="r1")
