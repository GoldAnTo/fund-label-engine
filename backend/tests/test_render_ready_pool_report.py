"""Phase1 v1 ready pool 验收报告的 smoke 单测。

锁定：
- 8 只样本列表与 2 只 mapping_reason 分类
- 数据集抽样必须满足 ready 池验收口径
- summary 表 8 行；每只基金都有 benchmark_data_missing=not_triggered
"""
import csv
import sqlite3
import subprocess
from pathlib import Path

from scripts.render_ready_pool_report import SAMPLE_CODES, _load_label_snapshot


def _summary_rows(md_path):
    return [line for line in Path(md_path).read_text(encoding="utf-8").splitlines() if line.startswith("| `")]


def test_load_label_snapshot_uses_latest_succeeded_run(tmp_path):
    db_path = tmp_path / "output.sqlite"
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE label_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            data_as_of TEXT,
            rule_version TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE fund_label_results (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            label_code TEXT NOT NULL,
            label_name TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE fund_label_evidence (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            label_code TEXT NOT NULL,
            metric TEXT NOT NULL,
            value TEXT NOT NULL,
            threshold TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE TABLE label_calculation_states (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            label_code TEXT NOT NULL,
            label_name TEXT NOT NULL,
            category TEXT NOT NULL,
            state TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            observed TEXT NOT NULL,
            threshold TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE TABLE fund_classification_results (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            dimension TEXT NOT NULL,
            classification_code TEXT NOT NULL,
            classification_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            reason_code TEXT NOT NULL,
            evidence TEXT NOT NULL,
            source TEXT NOT NULL
        );
        CREATE TABLE fund_group_results (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            group_code TEXT NOT NULL,
            group_name TEXT NOT NULL,
            group_type TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            evidence TEXT NOT NULL,
            source TEXT NOT NULL
        );
        CREATE TABLE feature_values (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            feature_code TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT NOT NULL
        );
        """
    )
    con.executemany(
        "INSERT INTO label_runs VALUES (?, ?, NULL, 'v1', ?)",
        [
            ("old_run", "2026-06-30T00:00:00+00:00", "succeeded"),
            ("latest_run", "2026-07-01T00:00:00+00:00", "succeeded"),
            ("failed_run", "2026-07-02T00:00:00+00:00", "completed_with_errors"),
        ],
    )
    con.executemany(
        "INSERT INTO fund_label_results VALUES (?, '000001', ?, ?, ?, 0.9, 'active')",
        [
            ("old_run", "old_label", "旧标签", "return_risk"),
            ("latest_run", "latest_label", "新标签", "return_risk"),
            ("failed_run", "failed_label", "失败批次标签", "return_risk"),
        ],
    )
    con.executemany(
        "INSERT INTO feature_values VALUES (?, '000001', 'alpha_1y', ?, 'unit-test')",
        [
            ("old_run", "0.1"),
            ("latest_run", "0.2"),
            ("failed_run", "0.3"),
        ],
    )
    con.commit()
    con.close()

    snap = _load_label_snapshot(db_path, "000001")

    assert snap["run_id"] == "latest_run"
    assert [row[0] for row in snap["results"]] == ["latest_label"]
    assert [row[1] for row in snap["features"]] == ["0.2"]


def test_sample_code_list_is_stable():
    assert SAMPLE_CODES == [
        "000006",
        "000020",
        "000039",
        "000199",
        "000354",
        "000511",
        "000656",
        "100038",
    ]
    assert len(SAMPLE_CODES) == 8


def test_eight_sample_funds_are_all_relative_label_ready():
    """锁定 v1 ready pool 抽样：8 只必须都是 relative_label_ready。

    这是 Phase1 v1 ready pool baseline 的最小不可动摇约束。
    """
    csv_path = Path("reports/phase1-real-run-2026-06-29/relative-label-eligibility.csv")
    if not csv_path.exists():
        # 报告尚未生成；不算硬性失败，但提醒跑验收流水线
        import pytest

        pytest.skip(f"{csv_path} not found; run make audit-relative-eligibility first")
    eligibility = {r["fund_code"]: r for r in csv.DictReader(open(csv_path, encoding="utf-8"))}
    for code in SAMPLE_CODES:
        row = eligibility.get(code)
        assert row is not None, f"{code} not in eligibility"
        assert row["relative_label_status"] == "relative_label_ready", (
            f"{code} expected relative_label_ready, got {row['relative_label_status']}"
        )
        assert int(row["nav_sample_count"]) >= 180
        assert int(row["benchmark_sample_count"]) >= 180


def test_eight_sample_funds_all_have_benchmark_data_missing_not_triggered():
    """每只样本的相对标签必须都解出，benchmark_data_missing 必须不触发。"""
    db_path = Path("/tmp/fle-run/output.sqlite")
    if not db_path.exists():
        import pytest

        pytest.skip(f"{db_path} not found; run make run-batch-v1-with-benchmark first")
    con = sqlite3.connect(db_path)
    for code in SAMPLE_CODES:
        row = con.execute(
            "SELECT state, reason_code FROM label_calculation_states "
            "WHERE fund_code=? AND label_code='benchmark_data_missing'",
            (code,),
        ).fetchone()
        assert row is not None, f"{code} missing benchmark_data_missing state"
        state, reason = row
        assert state == "not_triggered", f"{code} benchmark_data_missing state={state}"
        assert reason == "benchmark_window_available", f"{code} reason={reason}"
    con.close()


def test_eight_sample_funds_cover_two_mapping_reasons():
    """8 只样本必须覆盖 composite + tracking_target 两种 mapping_reason。"""
    csv_path = Path("reports/phase1-real-run-2026-06-29/benchmark-mapping.csv")
    rows = {r["fund_code"]: r for r in csv.DictReader(open(csv_path, encoding="utf-8"))}
    reasons = {rows[code]["mapping_reason"] for code in SAMPLE_CODES}
    assert "composite_benchmark_supported_components" in reasons
    assert "tracking_target_exact_supported_index" in reasons


def test_render_report_smoke(tmp_path):
    """端到端 smoke：脚本必须能生成报告，summary 表 8 行。"""
    csv_path = Path("reports/phase1-real-run-2026-06-29/relative-label-eligibility.csv")
    out_db = Path("/tmp/fle-run/output.sqlite")
    src_db = Path("/tmp/fle-run/source.sqlite")
    if not (csv_path.exists() and out_db.exists() and src_db.exists()):
        import pytest

        pytest.skip("source/output/audit files not ready; run the make pipeline first")
    out_md = tmp_path / "smoke.md"
    result = subprocess.run(
        [
            "python3",
            "scripts/render_ready_pool_report.py",
            "--source-db",
            str(src_db),
            "--output-db",
            str(out_db),
            "--out-md",
            str(out_md),
            "--codes",
            ",".join(SAMPLE_CODES),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "wrote" in result.stdout
    rows = _summary_rows(out_md)
    assert len(rows) == 8
    for code in SAMPLE_CODES:
        assert any(code in row for row in rows)
