import os
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch

from scripts.seed_sample_db import seed


def test_render_portfolio_draft_report_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    out_md = tmp_path / "draft.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_portfolio_draft_report.py",
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
    assert "# Portfolio Draft Report" in text
    assert f"run_id: `{run_id}`" in text
    assert "Draft Weights" in text
