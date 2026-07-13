"""候选优先级 API 测试:POST/GET 路由、异常映射。

覆盖:
    1. POST candidate-sets 成功 -> 201
    2. POST candidate-sets thesis 不存在 -> 404
    3. POST candidate-sets structured intent 缺失 -> 422
    4. POST candidate-sets snapshot 数据源不可用 -> 503
    5. POST candidate-sets 重复 -> 409(detail 含已有 candidate_set_id)
    6. POST candidate-priority-runs 成功 -> 201
    7. POST candidate-priority-runs thesis 不存在 -> 404
    8. POST candidate-priority-runs candidate_set 不存在 -> 404
    9. POST candidate-priority-runs 重复幂等 -> 409(detail 含已有 priority_run_id)
    10. POST candidate-priority-runs 配置错误 -> 422
    11. POST candidate-priority-runs no_eligible_candidate 返回 201
    12. GET candidate-priority-runs/{id} 成功 -> 200(含五档候选列表)
    13. GET candidate-priority-runs/{id} 不存在 -> 404
    14. GET theses/{thesis_id}/candidate-priority-runs 成功 -> 200

测试中用 Mock 注入 CognitionGovernanceService,避免依赖真实认知数据库。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from app.main import create_app
from app.persistence.migrations_runner import run_migrations
from app.services.candidate_priority import CandidatePriorityConfigurationError
from app.services.cognition_governance_service import (
    CandidateDataSourceUnavailableError,
    CandidateSetNotFoundError,
    DuplicateCandidateSetError,
    DuplicatePriorityRunError,
    StructuredIntentIncompleteError,
    ThesisNotFoundError,
)
from fastapi.testclient import TestClient


@pytest.fixture()
def gov_db(tmp_path: Path) -> Path:
    db = tmp_path / "gov.sqlite"
    run_migrations(str(db))
    return db


@pytest.fixture()
def client(gov_db: Path) -> TestClient:
    """创建带 Mock CognitionGovernanceService 的 TestClient。"""
    app = create_app(source_db_path=str(gov_db), db_path=str(gov_db))
    app.state.cognition_governance_service = Mock()
    return TestClient(app)


def _mock_service(client: TestClient) -> Mock:
    """从 client.app.state 获取 Mock 服务。"""
    return client.app.state.cognition_governance_service


# ============================================================
# 1. POST candidate-sets
# ============================================================
class TestCreateCandidateSet:
    def test_create_success(self, client: TestClient):
        """POST candidate-sets 成功 -> 201。"""
        svc = _mock_service(client)
        svc.create_candidate_set.return_value = {
            "candidate_set_id": "cs_001",
            "thesis_id": "th1",
            "mapped_candidate_count": 3,
            "scanned_fund_count": 10,
            "unmapped_due_to_data_count": 7,
            "data_snapshot_id": "snap1",
        }
        resp = client.post("/v1/governance/theses/th1/candidate-sets", json={
            "data_snapshot_id": "snap1",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["candidate_set_id"] == "cs_001"
        assert data["thesis_id"] == "th1"
        assert data["mapped_candidate_count"] == 3
        assert data["scanned_fund_count"] == 10
        assert data["unmapped_due_to_data_count"] == 7
        assert data["data_snapshot_id"] == "snap1"
        # 验证 service 被正确调用
        svc.create_candidate_set.assert_called_once_with(
            thesis_id="th1",
            data_snapshot_id="snap1",
            actor_id="researcher_001",
            source_ip="testclient",
        )

    def test_thesis_not_found(self, client: TestClient):
        """POST candidate-sets thesis 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.create_candidate_set.side_effect = ThesisNotFoundError("投资假设不存在: ghost")
        resp = client.post("/v1/governance/theses/ghost/candidate-sets", json={
            "data_snapshot_id": "snap1",
            "actor_id": "r1",
        })
        assert resp.status_code == 404

    def test_structured_intent_incomplete(self, client: TestClient):
        """POST candidate-sets structured intent 缺失 -> 422。"""
        svc = _mock_service(client)
        svc.create_candidate_set.side_effect = StructuredIntentIncompleteError(
            "structured_intent 缺少必填字段: ['direction']"
        )
        resp = client.post("/v1/governance/theses/th1/candidate-sets", json={
            "data_snapshot_id": "snap1",
            "actor_id": "r1",
        })
        assert resp.status_code == 422

    def test_data_source_unavailable(self, client: TestClient):
        """POST candidate-sets snapshot 数据源不可用 -> 503。"""
        svc = _mock_service(client)
        svc.create_candidate_set.side_effect = CandidateDataSourceUnavailableError(
            "候选数据源文件不存在: snap2"
        )
        resp = client.post("/v1/governance/theses/th1/candidate-sets", json={
            "data_snapshot_id": "snap2",
            "actor_id": "r1",
        })
        assert resp.status_code == 503

    def test_duplicate_returns_409(self, client: TestClient):
        """POST candidate-sets 重复 -> 409,detail 含已有 candidate_set_id。"""
        svc = _mock_service(client)
        svc.create_candidate_set.side_effect = DuplicateCandidateSetError("cs_existing_001")
        resp = client.post("/v1/governance/theses/th1/candidate-sets", json={
            "data_snapshot_id": "snap1",
            "actor_id": "r1",
        })
        assert resp.status_code == 409
        assert "cs_existing_001" in resp.json()["detail"]


# ============================================================
# 2. POST candidate-priority-runs
# ============================================================
class TestCreatePriorityRun:
    def test_create_success(self, client: TestClient):
        """POST candidate-priority-runs 成功 -> 201。"""
        svc = _mock_service(client)
        svc.create_priority_run.return_value = {
            "priority_run_id": "cpr_001",
            "result_type": "ranked_candidates",
            "evaluated_candidate_count": 3,
            "eligible_candidate_count": 2,
            "tier_counts": {
                "research_now": 1,
                "research_next": 1,
                "valuation_watch": 0,
                "data_insufficient": 0,
                "excluded": 1,
            },
            "approved_for_production": False,
        }
        resp = client.post("/v1/governance/theses/th1/candidate-priority-runs", json={
            "candidate_set_id": "cs1",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority_run_id"] == "cpr_001"
        assert data["result_type"] == "ranked_candidates"
        assert data["evaluated_candidate_count"] == 3
        assert data["eligible_candidate_count"] == 2
        assert data["tier_counts"]["research_now"] == 1
        assert data["approved_for_production"] is False
        svc.create_priority_run.assert_called_once_with(
            thesis_id="th1",
            candidate_set_id="cs1",
            data_snapshot_id="snap1",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
            source_ip="testclient",
        )

    def test_thesis_not_found(self, client: TestClient):
        """POST candidate-priority-runs thesis 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.create_priority_run.side_effect = ThesisNotFoundError("投资假设不存在: ghost")
        resp = client.post("/v1/governance/theses/ghost/candidate-priority-runs", json={
            "candidate_set_id": "cs1",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "r1",
        })
        assert resp.status_code == 404

    def test_candidate_set_not_found(self, client: TestClient):
        """POST candidate-priority-runs candidate_set 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.create_priority_run.side_effect = CandidateSetNotFoundError("候选集合不存在: ghost")
        resp = client.post("/v1/governance/theses/th1/candidate-priority-runs", json={
            "candidate_set_id": "ghost",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "r1",
        })
        assert resp.status_code == 404

    def test_duplicate_returns_409(self, client: TestClient):
        """POST candidate-priority-runs 重复幂等 -> 409,detail 含已有 priority_run_id。"""
        svc = _mock_service(client)
        svc.create_priority_run.side_effect = DuplicatePriorityRunError("cpr_existing_001")
        resp = client.post("/v1/governance/theses/th1/candidate-priority-runs", json={
            "candidate_set_id": "cs1",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "r1",
        })
        assert resp.status_code == 409
        assert "cpr_existing_001" in resp.json()["detail"]

    def test_configuration_error_returns_422(self, client: TestClient):
        """POST candidate-priority-runs 配置错误 -> 422。"""
        svc = _mock_service(client)
        svc.create_priority_run.side_effect = CandidatePriorityConfigurationError(
            "candidate_priority 配置缺失"
        )
        resp = client.post("/v1/governance/theses/th1/candidate-priority-runs", json={
            "candidate_set_id": "cs1",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "r1",
        })
        assert resp.status_code == 422

    def test_no_eligible_candidate_returns_201(self, client: TestClient):
        """POST candidate-priority-runs no_eligible_candidate 返回 201(不是错误)。"""
        svc = _mock_service(client)
        svc.create_priority_run.return_value = {
            "priority_run_id": "cpr_002",
            "result_type": "no_eligible_candidate",
            "evaluated_candidate_count": 1,
            "eligible_candidate_count": 0,
            "tier_counts": {
                "research_now": 0,
                "research_next": 0,
                "valuation_watch": 0,
                "data_insufficient": 0,
                "excluded": 1,
            },
            "approved_for_production": False,
        }
        resp = client.post("/v1/governance/theses/th1/candidate-priority-runs", json={
            "candidate_set_id": "cs1",
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "actor_id": "r1",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["result_type"] == "no_eligible_candidate"
        assert data["eligible_candidate_count"] == 0


# ============================================================
# 3. GET candidate-priority-runs/{id}
# ============================================================
class TestGetPriorityRun:
    def test_get_success(self, client: TestClient):
        """GET candidate-priority-runs/{id} 成功 -> 200,返回五档候选列表。"""
        svc = _mock_service(client)
        svc.get_priority_run.return_value = {
            "priority_run_id": "cpr_001",
            "thesis_id": "th1",
            "candidate_set_id": "cs1",
            "strategy_policy_id": "p1",
            "strategy_policy_version": 1,
            "data_snapshot_id": "snap1",
            "ranking_method_version": "fund_priority_v0",
            "result_type": "ranked_candidates",
            "result_status": "completed",
            "evaluated_candidate_count": 3,
            "eligible_candidate_count": 2,
            "tier_counts": {
                "research_now": 1,
                "research_next": 1,
                "valuation_watch": 0,
                "data_insufficient": 0,
                "excluded": 1,
            },
            "approved_for_production": False,
            "created_by": "researcher_001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "candidates_by_tier": {
                "research_now": [
                    {"fund_code": "001001", "fund_name": "基金A", "priority_rank": 1},
                ],
                "research_next": [
                    {"fund_code": "001002", "fund_name": "基金B", "priority_rank": 1},
                ],
                "valuation_watch": [],
                "data_insufficient": [],
                "excluded": [
                    {"fund_code": "001003", "fund_name": "基金C"},
                ],
            },
        }
        resp = client.get("/v1/governance/candidate-priority-runs/cpr_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority_run_id"] == "cpr_001"
        assert data["thesis_id"] == "th1"
        tiers = data["candidates_by_tier"]
        for tier_name in ("research_now", "research_next", "valuation_watch",
                          "data_insufficient", "excluded"):
            assert tier_name in tiers
        assert len(tiers["research_now"]) == 1
        assert tiers["research_now"][0]["fund_code"] == "001001"
        assert len(tiers["excluded"]) == 1

    def test_get_not_found(self, client: TestClient):
        """GET candidate-priority-runs/{id} 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.get_priority_run.return_value = None
        resp = client.get("/v1/governance/candidate-priority-runs/nonexistent")
        assert resp.status_code == 404


# ============================================================
# 4. GET theses/{thesis_id}/candidate-priority-runs
# ============================================================
class TestListPriorityRuns:
    def test_list_success(self, client: TestClient):
        """GET theses/{thesis_id}/candidate-priority-runs 成功 -> 200。"""
        svc = _mock_service(client)
        svc.list_priority_runs.return_value = [
            {
                "priority_run_id": "cpr_001",
                "thesis_id": "th1",
                "candidate_set_id": "cs1",
                "strategy_policy_id": "p1",
                "strategy_policy_version": 1,
                "data_snapshot_id": "snap1",
                "ranking_method_version": "fund_priority_v0",
                "result_type": "ranked_candidates",
                "result_status": "completed",
                "evaluated_candidate_count": 3,
                "eligible_candidate_count": 2,
                "tier_counts": {"research_now": 1, "excluded": 1},
                "created_by": "r1",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "priority_run_id": "cpr_002",
                "thesis_id": "th1",
                "candidate_set_id": "cs2",
                "strategy_policy_id": "p1",
                "strategy_policy_version": 1,
                "data_snapshot_id": "snap1",
                "ranking_method_version": "fund_priority_v0",
                "result_type": "no_eligible_candidate",
                "result_status": "completed",
                "evaluated_candidate_count": 1,
                "eligible_candidate_count": 0,
                "tier_counts": {"excluded": 1},
                "created_by": "r1",
                "created_at": "2026-02-01T00:00:00+00:00",
            },
        ]
        resp = client.get("/v1/governance/theses/th1/candidate-priority-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["priority_run_id"] == "cpr_001"
        assert data[1]["priority_run_id"] == "cpr_002"
        assert all(r["thesis_id"] == "th1" for r in data)

    def test_list_empty(self, client: TestClient):
        """GET theses/{thesis_id}/candidate-priority-runs 空列表 -> 200。"""
        svc = _mock_service(client)
        svc.list_priority_runs.return_value = []
        resp = client.get("/v1/governance/theses/th1/candidate-priority-runs")
        assert resp.status_code == 200
        assert resp.json() == []
