"""基金候选优先级 v0 端到端 smoke 测试。

验证完整链路:
    ResearchInput -> Thesis -> Cognition evidence -> CandidateSet
    -> CandidatePriorityRun -> CandidatePriorityResult -> API reverse lookup

使用真实的认知数据库(_make_cognition_db),不使用 Mock。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from app.main import create_app
from app.persistence.candidate_priority import CandidatePriorityRepository
from app.persistence.governance import GovernanceRepository
from app.persistence.migrations_runner import run_migrations
from app.services.cognition_governance_service import (
    CognitionGovernanceService,
    DuplicateCandidateSetError,
    DuplicatePriorityRunError,
)
from app.services.governance_service import GovernanceService
from fastapi.testclient import TestClient

# 从 test_cognition_engine 导入认知数据库构建辅助函数
from test_cognition_engine import _make_cognition_db


# ============================================================
# 策略配置辅助
# ============================================================
def _candidate_priority_config() -> dict:
    """候选优先级策略配置(写入 candidate_priority_json 列)。"""
    return {
        "method_version": "fund_priority_v0",
        "source_method_version": "fund_candidate_evidence_v0",
        "asset_type": "fund",
        "minimum_target_holding_weight": 0.01,
        "minimum_disclosed_holding_weight": 0.05,
        "minimum_factor_coverage_weight": 0.30,
        "maximum_holding_age_days": 365,
        "valuation_breach_mode": "watch",
        "require_manager_identity": False,
        "require_holding_report_date": True,
        "required_evidence": [
            "business_logic",
            "earnings_or_cashflow",
            "valuation",
            "catalyst_or_expectation_gap",
        ],
        "allowed_asset_types": ["fund"],
        "excluded_asset_codes": [],
        "valuation_policy": {
            "max_pe": 60,
            "max_pb": 10,
            "max_peg": 2.0,
            "max_valuation_percentile": 85,
        },
        "approved_for_production": False,
    }


def _valuation_policy_config() -> dict:
    """估值策略配置(写入 valuation_policy_json 列)。"""
    return {
        "status": "example",
        "method": "relative_and_absolute",
        "max_pe": 60,
        "max_pb": 10,
        "max_peg": 2.0,
        "max_valuation_percentile": 85,
    }


# ============================================================
# 测试 1: 完整链路首次运行
# ============================================================
def test_first_run_complete_chain(tmp_path: Path) -> dict:
    """完整链路首次运行。

    本函数既是一个独立测试,也被后续测试复用以构建基础数据。
    """
    # 1. 创建认知数据库(source + factor)
    source_db, factor_db = _make_cognition_db(tmp_path)

    # 2. 创建治理数据库
    gov_db = tmp_path / "gov.sqlite"
    run_migrations(str(gov_db))

    # 3. 插入基础数据
    conn = sqlite3.connect(str(gov_db))
    conn.execute("PRAGMA foreign_keys = ON")
    # 策略(含 candidate_priority_json 和 valuation_policy_json)
    conn.execute(
        """INSERT INTO strategy_policies
        (policy_id, version, business_mode, policy_status, approved_for_production,
         strategy_name, strategy_type, candidate_priority_json, valuation_policy_json)
        VALUES ('private_equity_growth', 2, 'private_strategy', 'example', 0,
        '私募成长', 'equity_long_only', ?, ?)""",
        (
            json.dumps(_candidate_priority_config(), ensure_ascii=False),
            json.dumps(_valuation_policy_config(), ensure_ascii=False),
        ),
    )
    # 快照(指向认知数据库路径)
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path, factor_db_path) "
        "VALUES (?, ?, ?)",
        ("snap_smoke", str(source_db), str(factor_db)),
    )
    conn.commit()
    conn.close()

    # 4. 创建 GovernanceService 和 ResearchInput
    gov_repo = GovernanceRepository(gov_db)
    gov_service = GovernanceService(gov_repo)
    ri_result = gov_service.create_research_input(
        input_type="philosophy",
        business_mode="private_strategy",
        strategy_policy_id="private_equity_growth",
        strategy_policy_version=2,
        actor_role="researcher",
        actor_id="researcher_001",
        request_source="ad_hoc_research",
        raw_text="我看好消费方向",
        structured_intent={
            "direction": "consumer",
            "conviction": "medium",
            "time_horizon": "long",
            "risk_tolerance": "moderate",
        },
        data_snapshot_id="snap_smoke",
    )
    user_input_id = ri_result["user_input_id"]

    # 5. 创建 Thesis
    th_result = gov_service.create_thesis(
        user_input_id=user_input_id,
        strategy_policy_id="private_equity_growth",
        strategy_policy_version=2,
        title="消费方向研究",
        belief_statement="我相信消费白马",
        actor_id="researcher_001",
        as_of_date="2026-01-15",
        data_snapshot_id="snap_smoke",
    )
    thesis_id = th_result["thesis_id"]

    # 6. 创建 CognitionGovernanceService
    priority_repo = CandidatePriorityRepository(gov_db)
    cog_gov_service = CognitionGovernanceService(
        governance_repo=gov_repo,
        priority_repo=priority_repo,
    )

    # 7. 创建 CandidateSet
    cs_result = cog_gov_service.create_candidate_set(
        thesis_id=thesis_id,
        data_snapshot_id="snap_smoke",
        actor_id="researcher_001",
    )
    candidate_set_id = cs_result["candidate_set_id"]

    # 8. 创建 PriorityRun
    pr_result = cog_gov_service.create_priority_run(
        thesis_id=thesis_id,
        candidate_set_id=candidate_set_id,
        data_snapshot_id="snap_smoke",
        ranking_method_version="fund_priority_v0",
        actor_id="researcher_001",
    )
    priority_run_id = pr_result["priority_run_id"]

    # 9. 验证结果
    assert pr_result["result_type"] in ("ranked_candidates", "no_eligible_candidate")
    assert pr_result["evaluated_candidate_count"] > 0
    assert "tier_counts" in pr_result
    assert pr_result["approved_for_production"] is False

    # 10. 反查
    run_detail = cog_gov_service.get_priority_run(priority_run_id)
    assert run_detail is not None
    assert run_detail["priority_run_id"] == priority_run_id
    assert run_detail["thesis_id"] == thesis_id
    assert run_detail["candidate_set_id"] == candidate_set_id

    # 11. 验证五档分组存在(实际字段名为 candidates_by_tier)
    for tier in (
        "research_now",
        "research_next",
        "valuation_watch",
        "data_insufficient",
        "excluded",
    ):
        assert tier in run_detail.get("candidates_by_tier", {})

    return {
        "user_input_id": user_input_id,
        "thesis_id": thesis_id,
        "candidate_set_id": candidate_set_id,
        "priority_run_id": priority_run_id,
        "gov_db": str(gov_db),
    }


# ============================================================
# 测试 2: 重复运行不重复
# ============================================================
def test_repeat_run_does_not_duplicate(tmp_path: Path) -> None:
    """同参数重复运行不创建新记录。"""
    ids = test_first_run_complete_chain(tmp_path)

    # 重新创建 service
    gov_db = Path(ids["gov_db"])
    gov_repo = GovernanceRepository(gov_db)
    priority_repo = CandidatePriorityRepository(gov_db)
    cog_gov_service = CognitionGovernanceService(gov_repo, priority_repo)

    # 重复创建 CandidateSet 应抛 DuplicateCandidateSetError
    with pytest.raises(DuplicateCandidateSetError) as exc_info:
        cog_gov_service.create_candidate_set(
            thesis_id=ids["thesis_id"],
            data_snapshot_id="snap_smoke",
            actor_id="researcher_001",
        )
    assert exc_info.value.candidate_set_id == ids["candidate_set_id"]

    # 重复创建 PriorityRun 应抛 DuplicatePriorityRunError
    with pytest.raises(DuplicatePriorityRunError) as exc_info:
        cog_gov_service.create_priority_run(
            thesis_id=ids["thesis_id"],
            candidate_set_id=ids["candidate_set_id"],
            data_snapshot_id="snap_smoke",
            ranking_method_version="fund_priority_v0",
            actor_id="researcher_001",
        )
    assert exc_info.value.priority_run_id == ids["priority_run_id"]


# ============================================================
# 测试 3: 新快照生成新 PriorityRun
# ============================================================
def test_new_snapshot_generates_new_run(tmp_path: Path) -> None:
    """新 snapshot 生成新 CandidateSet/PriorityRun,旧结果保留。"""
    ids = test_first_run_complete_chain(tmp_path)

    # 创建第二个快照(指向另一个认知数据库,但 snapshot_id 不同)
    gov_db = Path(ids["gov_db"])
    cog2_dir = tmp_path / "cog2"
    cog2_dir.mkdir(exist_ok=True)
    source_db, factor_db = _make_cognition_db(cog2_dir)

    conn = sqlite3.connect(str(gov_db))
    conn.execute(
        "INSERT INTO data_snapshots (snapshot_id, source_db_path, factor_db_path) "
        "VALUES (?, ?, ?)",
        ("snap_smoke_v2", str(source_db), str(factor_db)),
    )
    conn.commit()
    conn.close()

    # 需要新建 ResearchInput 关联新快照
    gov_repo = GovernanceRepository(gov_db)
    gov_service = GovernanceService(gov_repo)
    ri2 = gov_service.create_research_input(
        input_type="philosophy",
        business_mode="private_strategy",
        strategy_policy_id="private_equity_growth",
        strategy_policy_version=2,
        actor_role="researcher",
        actor_id="researcher_001",
        request_source="ad_hoc_research",
        raw_text="我看好消费方向 v2",
        structured_intent={
            "direction": "consumer",
            "conviction": "medium",
            "time_horizon": "long",
            "risk_tolerance": "moderate",
        },
        data_snapshot_id="snap_smoke_v2",
    )
    th2 = gov_service.create_thesis(
        user_input_id=ri2["user_input_id"],
        strategy_policy_id="private_equity_growth",
        strategy_policy_version=2,
        title="消费方向研究 v2",
        belief_statement="我相信消费白马 v2",
        actor_id="researcher_001",
        as_of_date="2026-02-15",
        data_snapshot_id="snap_smoke_v2",
    )

    priority_repo = CandidatePriorityRepository(gov_db)
    cog_gov_service = CognitionGovernanceService(gov_repo, priority_repo)

    cs2 = cog_gov_service.create_candidate_set(
        thesis_id=th2["thesis_id"],
        data_snapshot_id="snap_smoke_v2",
        actor_id="researcher_001",
    )
    pr2 = cog_gov_service.create_priority_run(
        thesis_id=th2["thesis_id"],
        candidate_set_id=cs2["candidate_set_id"],
        data_snapshot_id="snap_smoke_v2",
        ranking_method_version="fund_priority_v0",
        actor_id="researcher_001",
    )

    # 新 run ID 不同
    assert pr2["priority_run_id"] != ids["priority_run_id"]

    # 旧 run 仍可查询
    old_run = cog_gov_service.get_priority_run(ids["priority_run_id"])
    assert old_run is not None
    assert old_run["priority_run_id"] == ids["priority_run_id"]


# ============================================================
# 测试 4: API 反查
# ============================================================
def test_api_reverse_lookup(tmp_path: Path) -> None:
    """通过 API 反查全链 ID。"""
    ids = test_first_run_complete_chain(tmp_path)
    gov_db = ids["gov_db"]

    # 创建 app 和 client
    app = create_app(source_db_path=str(gov_db), db_path=str(gov_db))

    # 注入 CognitionGovernanceService
    gov_repo = GovernanceRepository(gov_db)
    priority_repo = CandidatePriorityRepository(gov_db)
    app.state.cognition_governance_service = CognitionGovernanceService(gov_repo, priority_repo)

    client = TestClient(app)

    # GET PriorityRun 详情
    resp = client.get(f"/v1/governance/candidate-priority-runs/{ids['priority_run_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["priority_run_id"] == ids["priority_run_id"]
    assert data["thesis_id"] == ids["thesis_id"]
    assert data["candidate_set_id"] == ids["candidate_set_id"]

    # GET Thesis 历史评价
    resp = client.get(f"/v1/governance/theses/{ids['thesis_id']}/candidate-priority-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 1
    assert any(r["priority_run_id"] == ids["priority_run_id"] for r in runs)
