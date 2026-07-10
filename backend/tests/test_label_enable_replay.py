"""规则启停 + 规则回放测试。

覆盖：
- LabelRunWriter.set_label_enabled: 启用/禁用/不变三种状态
- LabelRunWriter.set_label_enabled: 不存在的 label_code 报错
- LabelRunReader.get_label_enable_changes: 按 rule_version 过滤 + rowid 倒序
- LabelRunReader.get_label_definition: 单条查询 + 启用位解析
- API 集成（通过 TestClient）: POST enable / bulk-enable / GET changes / 404
- API: POST /v1/runs/replay 404 源 run 不存在
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import LabelRunReader, LabelRunWriter


# ---------- helpers ----------

def _seed_label_definitions(db_path: Path) -> None:
    """构造最小 label_definitions + audit_log schema 与种子数据。"""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS label_definitions (
            label_code TEXT NOT NULL,
            label_name TEXT NOT NULL,
            category TEXT NOT NULL,
            fund_types TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            description TEXT NOT NULL,
            thresholds_json TEXT,
            PRIMARY KEY (label_code, rule_version)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id TEXT PRIMARY KEY,
            run_id TEXT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            payload_json TEXT,
            source_ip TEXT,
            occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS label_runs (
            run_id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            data_as_of TEXT,
            rule_version TEXT NOT NULL,
            status TEXT NOT NULL,
            rule_snapshot_json TEXT,
            data_snapshot_id TEXT
        );
        CREATE TABLE IF NOT EXISTS fund_run_failures (
            run_id TEXT NOT NULL,
            fund_code TEXT NOT NULL,
            stage TEXT,
            error TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO label_definitions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("deep_value", "深度价值", "style", "股票型", "v1", 1, "深度价值股", None),
            ("quality_growth", "质量成长", "style", "股票型", "v1", 1, "高质量成长", None),
            ("dividend_steady", "稳定分红", "style", "全类型", "v1", 1, "稳定分红股", None),
            ("nav_outlier", "净值异常", "risk", "全类型", "v1", 1, "净值离群", None),
            # 不同 rule_version
            ("deep_value", "深度价值", "style", "股票型", "v2", 1, "深度价值 v2", None),
        ],
    )
    # 一个示例 run（让 get_run 有返回值）
    conn.execute(
        "INSERT INTO label_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("run-test-001", "2025-12-31T00:00:00", "2025-12-30", "v1", "succeeded", None, None),
    )
    conn.commit()
    conn.close()


# ---------- 1. Writer: set_label_enabled ----------

def test_set_label_enabled_disable(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_label_definitions(db)
    writer = LabelRunWriter(str(db), rule_version="v1")
    result = writer.set_label_enabled(
        label_code="deep_value",
        rule_version="v1",
        enabled=False,
        operator="alice",
        reason="影响 ready pool",
    )
    assert result["change_type"] == "disable"
    assert result["previous_enabled"] is True
    assert result["new_enabled"] is False
    assert result["operator"] == "alice"

    # 验证持久化
    reader = LabelRunReader(str(db))
    defn = reader.get_label_definition("deep_value", "v1")
    assert defn["enabled"] is False

    # 验证审计日志
    changes = reader.get_label_enable_changes(rule_version="v1")
    assert len(changes) == 1
    assert changes[0]["operator"] == "alice"
    assert changes[0]["payload"]["previous_enabled"] is True
    assert changes[0]["payload"]["new_enabled"] is False
    assert changes[0]["payload"]["reason"] == "影响 ready pool"


def test_set_label_enabled_enable_back(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_label_definitions(db)
    writer = LabelRunWriter(str(db), rule_version="v1")
    writer.set_label_enabled("deep_value", "v1", False, operator="alice")
    result = writer.set_label_enabled(
        "deep_value", "v1", True, operator="bob", reason="恢复"
    )
    assert result["change_type"] == "enable"
    assert result["previous_enabled"] is False
    assert result["new_enabled"] is True

    changes = LabelRunReader(str(db)).get_label_enable_changes(rule_version="v1")
    # 两条审计日志（disable + enable）
    assert len(changes) == 2
    # 倒序：最新的是 enable
    assert changes[0]["operator"] == "bob"
    assert changes[1]["operator"] == "alice"


def test_set_label_enabled_no_change(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_label_definitions(db)
    writer = LabelRunWriter(str(db), rule_version="v1")
    result = writer.set_label_enabled(
        "deep_value", "v1", True, operator="alice"
    )  # 已经是 True
    assert result["change_type"] == "no_change"

    # 不应写入审计
    changes = LabelRunReader(str(db)).get_label_enable_changes(rule_version="v1")
    assert len(changes) == 0


def test_set_label_enabled_not_found(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_label_definitions(db)
    writer = LabelRunWriter(str(db), rule_version="v1")
    with pytest.raises(ValueError, match="label definition not found"):
        writer.set_label_enabled("nonexistent", "v1", False, operator="alice")


def test_set_label_enabled_isolated_by_rule_version(tmp_path: Path) -> None:
    """disable v1 不影响 v2。"""
    db = tmp_path / "test.sqlite"
    _seed_label_definitions(db)
    writer = LabelRunWriter(str(db), rule_version="v1")
    writer.set_label_enabled("deep_value", "v1", False, operator="alice")

    reader = LabelRunReader(str(db))
    v1 = reader.get_label_definition("deep_value", "v1")
    v2 = reader.get_label_definition("deep_value", "v2")
    assert v1["enabled"] is False
    assert v2["enabled"] is True

    # 审计按 rule_version 过滤
    v1_changes = reader.get_label_enable_changes(rule_version="v1")
    v2_changes = reader.get_label_enable_changes(rule_version="v2")
    assert len(v1_changes) == 1
    assert len(v2_changes) == 0


# ---------- 2. API 集成 ----------

def _make_client(tmp_path: Path) -> TestClient:
    db = tmp_path / "api.sqlite"
    _seed_label_definitions(db)
    app = create_app(
        db_path=str(db),
        source_db_path=str(db),
        frontend_dist=None,
    )
    return TestClient(app)


def test_api_enable_label(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.post(
        "/v1/label-definitions/deep_value/v1/enable",
        json={"enabled": False, "operator": "alice", "reason": "回测发现误报"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["change_type"] == "disable"
    assert data["operator"] == "alice"


def test_api_enable_label_not_found(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.post(
        "/v1/label-definitions/nonexistent/v1/enable",
        json={"enabled": False, "operator": "alice"},
    )
    assert resp.status_code == 404


def test_api_bulk_enable(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.post(
        "/v1/label-definitions/bulk-enable",
        json={
            "rule_version": "v1",
            "label_codes": ["deep_value", "quality_growth", "nonexistent"],
            "enabled": False,
            "operator": "alice",
            "reason": "批次回退",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 3
    assert data["changed_count"] == 2  # deep_value + quality_growth 实际变更
    assert len(data["errors"]) == 1
    assert data["errors"][0]["label_code"] == "nonexistent"


def test_api_get_changes(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    # 先 disable 一条
    client.post(
        "/v1/label-definitions/deep_value/v1/enable",
        json={"enabled": False, "operator": "alice"},
    )
    # 再 disable 另一条
    client.post(
        "/v1/label-definitions/quality_growth/v1/enable",
        json={"enabled": False, "operator": "bob"},
    )
    resp = client.get("/v1/label-definitions/changes?rule_version=v1&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rule_version"] == "v1"
    assert len(data["changes"]) == 2
    # 倒序
    assert data["changes"][0]["operator"] == "bob"
    assert data["changes"][1]["operator"] == "alice"


def test_api_get_label_definition(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.get("/v1/label-definitions/deep_value/v1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["label_name"] == "深度价值"
    assert data["enabled"] is True

    resp404 = client.get("/v1/label-definitions/nonexistent/v1")
    assert resp404.status_code == 404


# ---------- 3. 规则回放 ----------

def test_api_replay_run_not_found(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    resp = client.post(
        "/v1/runs/replay",
        json={"source_run_id": "nonexistent-run", "rule_version": "v2"},
    )
    assert resp.status_code == 404
    assert "source run not found" in resp.text


def test_api_replay_requires_db_config(tmp_path: Path, monkeypatch) -> None:
    """当 source/output DB 未配置时，返回 503。"""
    db = tmp_path / "api.sqlite"
    _seed_label_definitions(db)
    app = create_app(frontend_dist=None)  # 不传任何 db_path
    client = TestClient(app)
    resp = client.post(
        "/v1/runs/replay",
        json={"source_run_id": "run-test-001", "rule_version": "v2"},
    )
    # 没 source_db 时返回 503
    assert resp.status_code == 503