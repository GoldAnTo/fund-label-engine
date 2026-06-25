"""Run Diff API 和 reader 行为测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.batch import run_batch
from app.label_engine.engine import RuleConfig
from app.main import create_app
from app.persistence import LabelRunReader


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    from scripts.seed_sample_db import seed

    db = tmp_path / "fund.sqlite"
    seed(db)
    return db


def _force_extra_label_in_run(db: Path, run_id: str, fund_code: str) -> None:
    """对某个 run 注入一条"伪造"标签，便于差异测试。"""
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, confidence, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                fund_code,
                "test_only_in_base",
                "测试-仅基线",
                "test",
                1.0,
                "active",
            ),
        )
        conn.commit()


def test_diff_same_run_yields_no_changes(seeded_db: Path) -> None:
    run_id, _ = run_batch(seeded_db)
    payload = LabelRunReader(seeded_db).diff_runs(run_id, run_id)
    assert payload is not None
    assert payload["totals"]["added_pair_count"] == 0
    assert payload["totals"]["removed_pair_count"] == 0
    assert payload["totals"]["changed_fund_count"] == 0
    assert payload["summary_by_label"] == []
    assert payload["details_by_fund"] == []


def test_diff_detects_added_and_removed_labels(seeded_db: Path) -> None:
    base_run, _ = run_batch(seeded_db)
    # 给 base 多加一条标签，让其相对 target 是 "removed"
    _force_extra_label_in_run(seeded_db, base_run, "000001")

    # 用更严格规则跑第二个 run，让某些标签消失
    target_run, _ = run_batch(
        seeded_db,
        rule_config=RuleConfig(holding_concentration_threshold=0.99),
    )

    payload = LabelRunReader(seeded_db).diff_runs(base_run, target_run)
    assert payload is not None
    # 至少有一个 removed（test_only_in_base）
    removed_labels = {row["label_code"] for row in payload["summary_by_label"] if row["removed_funds"]}
    assert "test_only_in_base" in removed_labels
    # holding_concentration_high 被更严的阈值弹掉了，应该出现在 removed
    assert "holding_concentration_high" in removed_labels
    # 按 fund 视角：000001 在 details 中
    fund_codes = {row["fund_code"] for row in payload["details_by_fund"]}
    assert "000001" in fund_codes


def test_diff_runs_returns_none_when_run_missing(seeded_db: Path) -> None:
    run_id, _ = run_batch(seeded_db)
    payload = LabelRunReader(seeded_db).diff_runs(run_id, "does-not-exist")
    assert payload is None


def test_diff_api_404_when_run_missing(seeded_db: Path) -> None:
    run_id, _ = run_batch(seeded_db)
    client = TestClient(create_app(db_path=seeded_db))
    resp = client.get(
        "/v1/runs/diff", params={"base": run_id, "target": "no-such-run"}
    )
    assert resp.status_code == 404


def test_diff_api_400_when_params_missing(seeded_db: Path) -> None:
    client = TestClient(create_app(db_path=seeded_db))
    # 缺 target 参数 → FastAPI 自动 422
    resp = client.get("/v1/runs/diff", params={"base": "x"})
    assert resp.status_code in (400, 422)


def test_diff_api_returns_well_formed_payload(seeded_db: Path) -> None:
    base_run, _ = run_batch(seeded_db)
    target_run, _ = run_batch(seeded_db)
    client = TestClient(create_app(db_path=seeded_db))

    resp = client.get(
        "/v1/runs/diff", params={"base": base_run, "target": target_run}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["base_run_id"] == base_run
    assert body["target_run_id"] == target_run
    for key in (
        "totals",
        "summary_by_label",
        "details_by_fund",
        "only_in_base",
        "only_in_target",
    ):
        assert key in body
    # 两次相同输入应该 0 变动
    assert body["totals"]["added_pair_count"] == 0
    assert body["totals"]["removed_pair_count"] == 0


def test_diff_treats_funds_only_in_one_run_as_only_in_lists(seeded_db: Path) -> None:
    base_run, _ = run_batch(seeded_db)
    # 把第二个 run 的某只基金的标签删干净，让它从 target 消失
    target_run, _ = run_batch(seeded_db)
    with sqlite3.connect(seeded_db) as conn:
        conn.execute(
            "DELETE FROM fund_label_results WHERE run_id = ? AND fund_code = ?",
            (target_run, "000002"),
        )
        conn.commit()

    payload = LabelRunReader(seeded_db).diff_runs(base_run, target_run)
    assert payload is not None
    assert "000002" in payload["only_in_base"]
    assert payload["totals"]["only_in_base_count"] >= 1
    # 该基金不应进入 added/removed 统计
    fund_codes_in_details = {row["fund_code"] for row in payload["details_by_fund"]}
    assert "000002" not in fund_codes_in_details
