import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch
from scripts.seed_sample_db import seed


def test_render_portfolio_calibration_report_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "DELETE FROM fund_label_results WHERE run_id = ? AND fund_code = '000001' "
            "AND label_code IN ('benchmark_data_missing', 'return_window_insufficient', "
            "'style_unlabeled_stock_factors_missing')",
            (run_id,),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, confidence, status) "
            "VALUES (?, '000001', ?, ?, ?, 0.8, 'active')",
            [
                (run_id, "alpha_positive", "Alpha 为正", "relative_benchmark"),
                (run_id, "information_ratio_high", "信息比率较高", "relative_benchmark"),
                (run_id, "manager_tenure_long", "经理任期较长", "manager"),
                (run_id, "quality_growth", "质量成长", "holding_style"),
                (run_id, "tracking_error_high", "跟踪误差较高", "relative_benchmark"),
            ],
        )
        conn.commit()

    out_md = tmp_path / "calibration.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_portfolio_calibration_report.py",
            "--output-db",
            str(db),
            "--out-md",
            str(out_md),
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    text = out_md.read_text(encoding="utf-8")
    assert "wrote" in result.stdout
    assert "# Portfolio Calibration Report" in text
    assert f"run_id: `{run_id}`" in text
    assert "`000001`" in text
    assert "eligible_with_allocation_risk_review" in text
    assert "human_decision_required" in text
