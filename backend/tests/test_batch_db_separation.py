import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.batch import run_batch
from app.main import create_app
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
    }.issubset(output_tables)

    # API 走 output_db 能直接查到 run / fund / report
    client = TestClient(create_app(db_path=output_db))
    assert client.get(f"/v1/runs/{run_id}").status_code == 200
    report = client.get(f"/v1/runs/{run_id}/funds/000001/report").json()
    assert report["fund_code"] == "000001"
    assert report["summary"]["label_count"] >= 1


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
