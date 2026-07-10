"""治理 API 测试:POST/GET 路由、异常映射、反查链路。

覆盖:
    1. POST 创建研究请求 -> 201
    2. GET 查询研究请求 -> 200
    3. GET 不存在 -> 404
    4. POST policy 不存在 -> 404
    5. POST 重复 -> 409
    6. POST 参数错误 -> 422
    7. GET 候选集合反查链路(candidate_set_id -> thesis -> policy -> snapshot)
    8. source_ip 从请求头获取
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.migrations_runner import run_migrations


@pytest.fixture()
def gov_db(tmp_path: Path) -> Path:
    db = tmp_path / "gov.sqlite"
    run_migrations(str(db))
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """INSERT INTO strategy_policies
            (policy_id, version, business_mode, policy_status, strategy_name, strategy_type)
           VALUES ('p1', 1, 'private_strategy', 'active', '测试策略', 'equity_long_only')"""
    )
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path) VALUES ('snap1', '/tmp/x')"
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def client(gov_db: Path) -> TestClient:
    app = create_app(source_db_path=str(gov_db), db_path=str(gov_db))
    return TestClient(app)


# ============================================================
# 1. POST 创建研究请求
# ============================================================
class TestCreateResearchInput:
    def test_create_success(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "researcher_001",
            "request_source": "ad_hoc_research",
            "raw_text": "我看好消费白马",
            "data_snapshot_id": "snap1",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "received"
        assert data["user_input_id"].startswith("ri_")

    def test_create_with_stable_id(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_stable_001",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "researcher_001",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
            "data_snapshot_id": "snap1",
        })
        assert resp.status_code == 201
        assert resp.json()["user_input_id"] == "ri_stable_001"

    def test_create_actor_id_required(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
        })
        assert resp.status_code == 422

    def test_create_invalid_input_type(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "input_type": "invalid",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
        })
        assert resp.status_code == 422


# ============================================================
# 2. GET 查询研究请求
# ============================================================
class TestGetResearchInput:
    def test_get_success(self, client: TestClient):
        # 先创建
        create_resp = client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_get_001",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "测试查询",
            "data_snapshot_id": "snap1",
        })
        assert create_resp.status_code == 201

        # 再查询
        resp = client.get("/v1/governance/research-inputs/ri_get_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_input_id"] == "ri_get_001"
        assert data["raw_text"] == "测试查询"
        assert data["actor_id"] == "r1"

    def test_get_not_found(self, client: TestClient):
        resp = client.get("/v1/governance/research-inputs/nonexistent")
        assert resp.status_code == 404


# ============================================================
# 3. POST policy/snapshot 不存在 -> 404
# ============================================================
class TestPolicySnapshotNotFound:
    def test_policy_not_found(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "ghost",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
        })
        assert resp.status_code == 404
        assert "策略不存在" in resp.json()["detail"]

    def test_snapshot_not_found(self, client: TestClient):
        resp = client.post("/v1/governance/research-inputs", json={
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
            "data_snapshot_id": "ghost_snap",
        })
        assert resp.status_code == 404
        assert "快照不存在" in resp.json()["detail"]


# ============================================================
# 4. POST 重复 -> 409
# ============================================================
class TestDuplicateRequest:
    def test_duplicate_returns_409(self, client: TestClient):
        # 第一次
        resp1 = client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_dup_001",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "first",
            "data_snapshot_id": "snap1",
        })
        assert resp1.status_code == 201

        # 第二次相同 ID
        resp2 = client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_dup_001",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "second",
            "data_snapshot_id": "snap1",
        })
        assert resp2.status_code == 409


# ============================================================
# 5. GET 候选集合反查链路
# ============================================================
class TestCandidateSetReverseLookup:
    def test_full_reverse_lookup(self, client: TestClient, gov_db: Path):
        """候选集合能反查到 thesis / research_input / policy / snapshot。"""
        # 1. 创建 research_input
        ri_resp = client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_chain_001",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "researcher_001",
            "request_source": "ad_hoc_research",
            "raw_text": "我看好消费白马",
            "data_snapshot_id": "snap1",
        })
        assert ri_resp.status_code == 201

        # 2. 创建 thesis(通过 Service 直接写,API 暂不暴露 create_thesis)
        from app.persistence.governance import GovernanceRepository
        from app.services.governance_service import GovernanceService

        repo = GovernanceRepository(gov_db)
        service = GovernanceService(repo)
        th_result = service.create_thesis(
            user_input_id="ri_chain_001",
            strategy_policy_id="p1",
            strategy_policy_version=1,
            title="消费白马配置",
            belief_statement="消费白马是核心",
            actor_id="researcher_001",
            as_of_date="2026-03-31",
            data_snapshot_id="snap1",
        )
        tid = th_result["thesis_id"]

        # 3. 创建候选
        cs_result = service.create_candidates(
            thesis_id=tid,
            user_input_id="ri_chain_001",
            candidates=[
                {"asset_type": "fund", "asset_code": "000001", "asset_name": "A", "fit_score": 0.8},
                {"asset_type": "fund", "asset_code": "000002", "asset_name": "B", "fit_score": 0.6},
            ],
            actor_id="researcher_001",
        )
        cs_id = cs_result["candidate_set_id"]

        # 4. 通过 API 反查
        resp = client.get(f"/v1/governance/candidate-sets/{cs_id}")
        assert resp.status_code == 200
        data = resp.json()

        # 验证完整反查链路
        assert data["candidate_set_id"] == cs_id
        assert data["thesis_id"] == tid
        assert data["user_input_id"] == "ri_chain_001"
        assert data["strategy_policy_id"] == "p1"
        assert data["strategy_policy_version"] == 1
        assert data["data_snapshot_id"] == "snap1"
        assert len(data["candidates"]) == 2
        assert data["candidates"][0]["asset_code"] == "000001"

    def test_candidate_set_not_found(self, client: TestClient):
        resp = client.get("/v1/governance/candidate-sets/nonexistent")
        assert resp.status_code == 404


# ============================================================
# 6. source_ip 从请求头获取
# ============================================================
class TestSourceIp:
    def test_source_ip_default_uses_peer(self, client: TestClient, gov_db: Path):
        """默认不信任 X-Forwarded-For,用直连 IP。"""
        client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_ip_default",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
            "data_snapshot_id": "snap1",
        }, headers={"X-Forwarded-For": "10.0.0.1"})

        # 查审计表:source_ip 应该是 127.0.0.1(TestClient 的直连 IP),不是 10.0.0.1
        conn = sqlite3.connect(str(gov_db))
        row = conn.execute(
            "SELECT source_ip FROM audit_log WHERE target_id = 'ri_ip_default'"
        ).fetchone()
        conn.close()
        assert row is not None
        # TestClient 的 client.host 是 testclient 或 127.0.0.1
        assert row[0] != "10.0.0.1"

    def test_source_ip_trusted_proxy(self, client: TestClient, gov_db: Path, monkeypatch):
        """配置 FLE_TRUSTED_PROXY=1 时才信任 X-Forwarded-For。"""
        monkeypatch.setenv("FLE_TRUSTED_PROXY", "1")
        # 清除缓存的 service
        if hasattr(client.app.state, "governance_service"):
            del client.app.state.governance_service

        client.post("/v1/governance/research-inputs", json={
            "user_input_id": "ri_ip_trusted",
            "input_type": "philosophy",
            "business_mode": "private_strategy",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "actor_role": "researcher",
            "actor_id": "r1",
            "request_source": "ad_hoc_research",
            "raw_text": "test",
            "data_snapshot_id": "snap1",
        }, headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"})

        conn = sqlite3.connect(str(gov_db))
        row = conn.execute(
            "SELECT source_ip FROM audit_log WHERE target_id = 'ri_ip_trusted'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "10.0.0.1"
