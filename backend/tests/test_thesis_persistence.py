"""Thesis 持久化测试：验证 step0_thesis 落库到 investment_theses 表。"""
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.seed_sample_db import seed


def test_thesis_persisted_to_investment_theses(tmp_path: Path) -> None:
    """认知请求后，investment_theses 表应有一条 draft 状态的记录。"""
    db = tmp_path / "fund.sqlite"
    seed(db)

    app = create_app(db_path=db)
    client = TestClient(app)

    response = client.post("/v1/cognition", json={
        "theme_key": "AI",
        "conviction": "high",
        "belief_note": "AI是生产力变革",
        "reasoning_chain": ["AI是生产力变革", "算力是核心"],
    })
    assert response.status_code == 200
    result = response.json()

    thesis = result.get("step0_thesis", {})
    assert thesis.get("persisted") is True
    thesis_id = thesis["thesis_id"]

    # 验证数据库中有对应记录
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT thesis_id, title, belief_statement, status, data_snapshot_id, "
        "strategy_policy_id FROM investment_theses WHERE thesis_id = ?",
        (thesis_id,),
    ).fetchone()
    conn.close()

    assert row is not None, "investment_theses 表中应有对应记录"
    assert row[0] == thesis_id
    assert row[1] == "AI 认知假设"  # title
    assert row[2] == "AI是生产力变革"  # belief_statement
    assert row[3] == "draft"  # status
    assert row[4] is not None  # data_snapshot_id
    assert row[5] == "cognition_default"  # strategy_policy_id


def test_thesis_research_input_created(tmp_path: Path) -> None:
    """持久化 Thesis 时应同时创建 research_inputs 记录。"""
    db = tmp_path / "fund.sqlite"
    seed(db)

    app = create_app(db_path=db)
    client = TestClient(app)

    response = client.post("/v1/cognition", json={
        "theme_key": "AI",
        "conviction": "medium",
        "belief_note": "国产替代加速",
    })
    assert response.status_code == 200

    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        "SELECT input_type, raw_text, request_source FROM research_inputs "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "philosophy"
    assert rows[0][1] == "国产替代加速"
    assert rows[0][2] == "ad_hoc_research"


def test_thesis_persistence_failure_graceful(tmp_path: Path) -> None:
    """持久化失败时不应阻断认知结果，应保留运行时 thesis_id。"""
    db = tmp_path / "fund.sqlite"
    seed(db)

    app = create_app(db_path=db)
    client = TestClient(app)

    # 正常请求应成功
    response = client.post("/v1/cognition", json={
        "theme_key": "AI",
        "conviction": "low",
    })
    assert response.status_code == 200
    result = response.json()
    thesis = result.get("step0_thesis", {})
    assert "thesis_id" in thesis
