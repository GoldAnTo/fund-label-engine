"""共享 pytest fixtures。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.batch import run_batch

from scripts.seed_sample_db import seed

# 确保工作目录是项目根目录（subprocess 测试依赖 scripts/ 路径）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if Path.cwd() != _PROJECT_ROOT:
    os.chdir(_PROJECT_ROOT)


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    """仅 seed 样例库，不跑 batch。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    return db


@pytest.fixture()
def seeded_run(tmp_path: Path) -> tuple[Path, str]:
    """seed 样例库后跑一次 batch，返回 (db_path, run_id)。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    return db, run_id
