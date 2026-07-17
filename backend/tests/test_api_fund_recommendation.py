"""基金推荐 API 测试:POST/GET 路由、异常映射。

覆盖:
    1. POST fund-recommendation-runs 成功 -> 201
    2. POST fund-recommendation-runs thesis 不存在 -> 404
    3. POST fund-recommendation-runs candidate_set 不存在 -> 404
    4. POST fund-recommendation-runs 重复幂等 -> 409(detail 含已有 recommendation_run_id)
    5. GET fund-recommendation-runs/{id} 成功 -> 200
    6. GET fund-recommendation-runs/{id} 不存在 -> 404
    7. GET theses/{thesis_id}/fund-recommendation-runs 成功 -> 200

测试中用 Mock 注入 CognitionGovernanceService,避免依赖真实认知数据库。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from app.main import create_app
from app.persistence.migrations_runner import run_migrations
from app.services.cognition_governance_service import (
    CandidateSetNotFoundError,
    DuplicateRecommendationRunError,
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
    return client.app.state.cognition_governance_service


class TestCreateRecommendationRun:
    def test_create_success(self, client: TestClient):
        """POST fund-recommendation-runs 成功 -> 201。"""
        svc = _mock_service(client)
        svc.create_recommendation_run.return_value = {
            "recommendation_run_id": "frr_001",
            "result_type": "ranked_recommendations",
            "evaluated_candidate_count": 5,
            "recommended_count": 3,
            "tier_counts": {"candidate_pool": 3, "alternative": 2},
        }
        resp = client.post("/v1/governance/theses/th1/fund-recommendation-runs", json={
            "candidate_set_id": "cs_001",
            "data_snapshot_id": "snap1",
            "recommendation_method_version": "fund_recommendation_v1",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["recommendation_run_id"] == "frr_001"
        assert data["result_type"] == "ranked_recommendations"
        assert data["recommended_count"] == 3

    def test_thesis_not_found(self, client: TestClient):
        """POST fund-recommendation-runs thesis 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.create_recommendation_run.side_effect = ThesisNotFoundError("not found")
        resp = client.post("/v1/governance/theses/th1/fund-recommendation-runs", json={
            "candidate_set_id": "cs_001",
            "data_snapshot_id": "snap1",
            "recommendation_method_version": "fund_recommendation_v1",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 404

    def test_candidate_set_not_found(self, client: TestClient):
        """POST fund-recommendation-runs candidate_set 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.create_recommendation_run.side_effect = CandidateSetNotFoundError("not found")
        resp = client.post("/v1/governance/theses/th1/fund-recommendation-runs", json={
            "candidate_set_id": "cs_001",
            "data_snapshot_id": "snap1",
            "recommendation_method_version": "fund_recommendation_v1",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 404

    def test_duplicate_returns_409(self, client: TestClient):
        """POST fund-recommendation-runs 重复幂等 -> 409。"""
        svc = _mock_service(client)
        svc.create_recommendation_run.side_effect = DuplicateRecommendationRunError("frr_existing")
        resp = client.post("/v1/governance/theses/th1/fund-recommendation-runs", json={
            "candidate_set_id": "cs_001",
            "data_snapshot_id": "snap1",
            "recommendation_method_version": "fund_recommendation_v1",
            "actor_id": "researcher_001",
        })
        assert resp.status_code == 409


class TestGetRecommendationRun:
    def test_get_success(self, client: TestClient):
        """GET fund-recommendation-runs/{id} 成功 -> 200。"""
        svc = _mock_service(client)
        svc.get_recommendation_run.return_value = {
            "recommendation_run_id": "frr_001",
            "thesis_id": "th1",
            "candidate_set_id": "cs_001",
            "candidates_by_category": {
                "active_fund": [],
                "etf_or_index": [],
            },
            "recommended_universe": [],
        }
        resp = client.get("/v1/governance/fund-recommendation-runs/frr_001")
        assert resp.status_code == 200
        assert resp.json()["recommendation_run_id"] == "frr_001"

    def test_get_not_found(self, client: TestClient):
        """GET fund-recommendation-runs/{id} 不存在 -> 404。"""
        svc = _mock_service(client)
        svc.get_recommendation_run.return_value = None
        resp = client.get("/v1/governance/fund-recommendation-runs/frr_nonexistent")
        assert resp.status_code == 404


class TestListRecommendationRuns:
    def test_list_success(self, client: TestClient):
        """GET theses/{thesis_id}/fund-recommendation-runs 成功 -> 200。"""
        svc = _mock_service(client)
        svc.list_recommendation_runs.return_value = [
            {
                "recommendation_run_id": "frr_001",
                "thesis_id": "th1",
                "candidate_set_id": "cs_001",
                "result_type": "ranked_recommendations",
                "evaluated_candidate_count": 5,
                "recommended_count": 3,
            }
        ]
        resp = client.get("/v1/governance/theses/th1/fund-recommendation-runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["recommendation_run_id"] == "frr_001"
