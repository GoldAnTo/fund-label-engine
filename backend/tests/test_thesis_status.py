"""Thesis 状态流转 + 证伪检查测试。"""
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.seed_sample_db import seed


def _get_thesis_id(client: TestClient) -> str:
    """提交认知请求，返回持久化 thesis_id。"""
    resp = client.post("/v1/cognition", json={
        "theme_key": "AI",
        "conviction": "high",
        "belief_note": "AI是生产力变革",
    })
    assert resp.status_code == 200
    return resp.json()["step0_thesis"]["thesis_id"]


def test_thesis_status_transition_manual(tmp_path: Path) -> None:
    """手动状态迁移：draft -> researching -> validated。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    app = create_app(db_path=db)
    client = TestClient(app)

    thesis_id = _get_thesis_id(client)

    # draft -> researching
    resp = client.patch(f"/v1/governance/theses/{thesis_id}/status", json={
        "to_status": "researching",
        "actor_id": "researcher_001",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "researching"

    # researching -> validated
    resp = client.patch(f"/v1/governance/theses/{thesis_id}/status", json={
        "to_status": "validated",
        "actor_id": "researcher_001",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "validated"


def test_thesis_invalid_transition_rejected(tmp_path: Path) -> None:
    """非法迁移应返回 422：draft -> approved（跳过 researching/validated）。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    app = create_app(db_path=db)
    client = TestClient(app)

    thesis_id = _get_thesis_id(client)

    resp = client.patch(f"/v1/governance/theses/{thesis_id}/status", json={
        "to_status": "approved",
        "actor_id": "researcher_001",
    })
    assert resp.status_code == 422


def test_thesis_review_returns_health(tmp_path: Path) -> None:
    """证伪检查应返回健康状态。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    app = create_app(db_path=db)
    client = TestClient(app)

    thesis_id = _get_thesis_id(client)

    resp = client.post(f"/v1/governance/theses/{thesis_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert data["thesis_id"] == thesis_id
    assert "health_label" in data
    assert isinstance(data["intact"], int)
    assert isinstance(data["broken"], int)


def test_thesis_auto_invalidation_on_broken(tmp_path: Path) -> None:
    """当 health 有 immediate_kill broken 时，应自动迁移到 invalidated。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    app = create_app(db_path=db)
    client = TestClient(app)

    thesis_id = _get_thesis_id(client)

    # 先迁移到 approved（需要经过 researching -> validated -> approved）
    for status in ("researching", "validated", "approved"):
        resp = client.patch(f"/v1/governance/theses/{thesis_id}/status", json={
            "to_status": status,
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 200

    # 手动在数据库中更新 key_metrics.health，模拟 broken + immediate_kill
    conn = sqlite3.connect(str(db))
    import json
    thesis = conn.execute(
        "SELECT key_metrics_json FROM investment_theses WHERE thesis_id = ?",
        (thesis_id,),
    ).fetchone()
    metrics = json.loads(thesis[0]) if thesis else {}
    metrics["health"] = {
        "health_label": "Broken",
        "intact": 3,
        "watch": 0,
        "broken": 1,
        "data_gap": 0,
        "items": [
            {"title": "估值分位", "metric": "val_pct", "status": "broken", "immediate_kill": True},
        ],
    }
    conn.execute(
        "UPDATE investment_theses SET key_metrics_json = ? WHERE thesis_id = ?",
        (json.dumps(metrics), thesis_id),
    )
    conn.commit()
    conn.close()

    # 调用 review，应自动迁移到 invalidated
    resp = client.post(f"/v1/governance/theses/{thesis_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_transition"] == "invalidated"
    assert data["invalidated_reason"] is not None
    assert "估值分位" in data["invalidated_reason"]

    # 验证数据库中状态已更新
    conn = sqlite3.connect(str(db))
    status = conn.execute(
        "SELECT status FROM investment_theses WHERE thesis_id = ?",
        (thesis_id,),
    ).fetchone()[0]
    conn.close()
    assert status == "invalidated"


def test_thesis_auto_watching_on_watch(tmp_path: Path) -> None:
    """当 health=Watching 且当前 approved 时，应自动迁移到 watching。"""
    db = tmp_path / "fund.sqlite"
    seed(db)
    app = create_app(db_path=db)
    client = TestClient(app)

    thesis_id = _get_thesis_id(client)

    # 迁移到 approved
    for status in ("researching", "validated", "approved"):
        resp = client.patch(f"/v1/governance/theses/{thesis_id}/status", json={
            "to_status": status,
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 200

    # 模拟 Watching 状态
    conn = sqlite3.connect(str(db))
    import json
    thesis = conn.execute(
        "SELECT key_metrics_json FROM investment_theses WHERE thesis_id = ?",
        (thesis_id,),
    ).fetchone()
    metrics = json.loads(thesis[0]) if thesis else {}
    metrics["health"] = {
        "health_label": "Watching",
        "intact": 3,
        "watch": 1,
        "broken": 0,
        "data_gap": 0,
        "items": [
            {"title": "匹配度", "metric": "match_pct", "status": "watch", "immediate_kill": False},
        ],
    }
    conn.execute(
        "UPDATE investment_theses SET key_metrics_json = ? WHERE thesis_id = ?",
        (json.dumps(metrics), thesis_id),
    )
    conn.commit()
    conn.close()

    resp = client.post(f"/v1/governance/theses/{thesis_id}/review")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_transition"] == "watching"
