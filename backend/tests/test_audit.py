"""审计日志测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.audit import audit_log
from app.main import create_app
from app.persistence import LabelRunReader, LabelRunWriter
from fastapi.testclient import TestClient


def test_audit_log_writes_record(tmp_path: Path) -> None:
    """audit_log() 应正确写入一条审计记录。"""
    db = tmp_path / "audit_test.sqlite"
    writer = LabelRunWriter(db)
    writer.ensure_schema()

    audit_log(
        writer,
        action="test_action",
        target_type="fund",
        target_id="000001",
        payload={"key": "value", "n": 42},
        actor="tester",
        run_id="run-abc",
    )

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT actor, action, target_type, target_id, payload_json, run_id "
            "FROM audit_log ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    assert row[0] == "tester"
    assert row[1] == "test_action"
    assert row[2] == "fund"
    assert row[3] == "000001"
    assert "key" in row[4]
    assert row[5] == "run-abc"


def test_audit_log_failure_does_not_break(tmp_path: Path) -> None:
    """audit_log 失败不应抛出异常（fail-safe）。"""
    db = tmp_path / "audit_test2.sqlite"
    writer = LabelRunWriter(db)
    # 不 ensure_schema - 尝试写入时若表不存在也不应崩溃（但其实 ensure_schema 内部会建）
    # 这里测的是一个不存在的字段——payload 为不可序列化对象时会 fallback 到 str
    audit_log(
        writer,
        action="x",
        target_type="y",
        target_id="z",
        payload={"d": {"nested": object()}},  # 不可 JSON 化
        actor="tester",
    )


def test_reader_list_audit_log_filters(tmp_path: Path) -> None:
    """reader 应能按 run_id/actor/action 过滤。"""
    db = tmp_path / "audit_test3.sqlite"
    writer = LabelRunWriter(db)
    writer.ensure_schema()

    for i in range(3):
        audit_log(
            writer,
            action="write_role_review",
            target_type="role",
            target_id=f"fund{i}/role",
            payload={"decision": "accept"},
            actor=f"tester{i % 2}",
            run_id=f"run{i // 2}",
        )

    reader = LabelRunReader(db)

    all_rows = reader.list_audit_log()
    assert len(all_rows) == 3

    only_run_0 = reader.list_audit_log(run_id="run0")
    assert len(only_run_0) == 2
    assert all(r["run_id"] == "run0" for r in only_run_0)

    only_tester0 = reader.list_audit_log(actor="tester0")
    assert len(only_tester0) == 2
    assert all(r["actor"] == "tester0" for r in only_tester0)


def test_write_role_review_creates_audit_log(seeded_run) -> None:
    """调用 write_role_review 后应有一条 write_role_review 审计。"""
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))
    resp = client.post(
        f"/v1/runs/{run_id}/portfolio-role-reviews",
        json={
            "fund_code": "000001",
            "role_code": "manual_portfolio_role",
            "decision": "accept",
            "target_bucket": "core",
            "max_weight_pct": 8.0,
            "rationale": "audit test",
            "reviewer": "audit_tester",
        },
    )
    assert resp.status_code == 200

    audit_resp = client.get(
        "/v1/audit-log",
        params={"run_id": run_id, "action": "write_role_review"},
    )
    assert audit_resp.status_code == 200
    payload = audit_resp.json()
    assert payload["count"] >= 1
    by_code = {row["target_id"]: row for row in payload["rows"]}
    assert "000001/manual_portfolio_role" in by_code
    row = by_code["000001/manual_portfolio_role"]
    assert row["actor"] == "audit_tester"

    assert "core" in (row["payload_json"] or "")


def test_apply_suggestions_creates_audit_log_per_item(seeded_run) -> None:
    """一键 apply 应为每条 suggestion 写一条审计。"""
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))
    resp = client.post(
        f"/v1/runs/{run_id}/portfolio-role-reviews/apply-suggestions",
        json={
            "reviewer": "batch_tester",
            "items": [
                {
                    "fund_code": "000001",
                    "role_code": "core_holding_candidate",
                    "decision": "accept",
                    "target_bucket": "core",
                    "max_weight_pct": 10.0,
                    "rationale": "test",
                },
                {
                    "fund_code": "000002",
                    "role_code": "core_holding_candidate",
                    "decision": "accept",
                    "target_bucket": "core",
                    "max_weight_pct": 12.0,
                    "rationale": "test",
                },
            ],
        },
    )
    assert resp.status_code == 200

    audit_resp = client.get(
        "/v1/audit-log",
        params={"run_id": run_id, "action": "apply_role_suggestion"},
    )
    assert audit_resp.status_code == 200
    payload = audit_resp.json()
    assert payload["count"] == 2
    assert all(r["actor"] == "batch_tester" for r in payload["rows"])
