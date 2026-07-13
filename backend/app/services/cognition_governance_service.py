"""认知治理 Service: 从投资假设生成 CandidateSet，编排 PriorityRun。

职责边界(严格遵守):
    - 业务校验(thesis / snapshot / candidate_set / policy 对齐)
    - structured_intent 必填字段校验
    - CognitionEngine 生命周期管理(finally 关闭)
    - CandidateSet 幂等键检查
    - PriorityRun 内存计算 + 原子写入
    - 失败审计(独立短事务，不写敏感数据)

    不包含:
    - SQL 执行(由 Repository 负责)
    - 纯规则计算(由 CandidatePriorityEngine 负责)
    - FastAPI / 前端逻辑
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.cognition.engine import CognitionEngine, FundCandidateEvidenceBatch
from app.persistence.candidate_priority import CandidatePriorityRepository
from app.persistence.governance import GovernanceRepository
from app.services.candidate_priority import (
    PRIORITY_TIERS,
    CandidatePriorityEngine,
    CandidatePriorityResult,
    FundCandidateEvidence,
    parse_candidate_priority_policy,
)


# ============================================================
# 领域异常
# ============================================================
class GovernanceError(Exception):
    """治理业务错误基类。"""


class ThesisNotFoundError(GovernanceError):
    """投资假设不存在。"""


class CandidateSetNotFoundError(GovernanceError):
    """候选集合不存在。"""


class StructuredIntentIncompleteError(GovernanceError):
    """结构化意图缺少必填字段。"""


class CandidateDataSourceUnavailableError(GovernanceError):
    """候选数据源不可用(文件路径不存在等)。"""


class SnapshotNotFoundError(GovernanceError):
    """数据快照不存在。"""


class PolicyNotFoundError(GovernanceError):
    """策略政策不存在。"""


class DuplicateCandidateSetError(GovernanceError):
    """重复候选集合(幂等键冲突)。"""

    def __init__(self, candidate_set_id: str) -> None:
        self.candidate_set_id = candidate_set_id
        super().__init__(f"CandidateSet already exists: {candidate_set_id}")


class DuplicatePriorityRunError(GovernanceError):
    """重复优先级运行(幂等键冲突)。"""

    def __init__(self, priority_run_id: str) -> None:
        self.priority_run_id = priority_run_id
        super().__init__(f"PriorityRun already exists: {priority_run_id}")


# ============================================================
# 辅助函数
# ============================================================
def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


_SOURCE_METHOD_VERSION = "fund_candidate_evidence_v0"


def _evidence_to_dict(ev: FundCandidateEvidence) -> dict[str, Any]:
    """把 FundCandidateEvidence 序列化为可存储的 dict。"""
    return {
        "fund_code": ev.fund_code,
        "fund_name": ev.fund_name,
        "matched_holding_weight": ev.matched_holding_weight,
        "disclosed_holding_weight": ev.disclosed_holding_weight,
        "normalized_match_pct": ev.normalized_match_pct,
        "holding_report_date": ev.holding_report_date,
        "holding_age_days": ev.holding_age_days,
        "factor_coverage_weight": ev.factor_coverage_weight,
        "valuation": ev.valuation,
        "holding_trend": ev.holding_trend,
        "manager_identity": ev.manager_identity,
        "evidence_types": ev.evidence_types,
        "policy_conflicts": list(ev.policy_conflicts),
        "data_snapshot_id": ev.data_snapshot_id,
        "asset_type": ev.asset_type,
    }


def _dict_to_evidence(d: dict[str, Any]) -> FundCandidateEvidence:
    """从 dict 反序列化为 FundCandidateEvidence。"""
    return FundCandidateEvidence(
        fund_code=d["fund_code"],
        fund_name=d["fund_name"],
        matched_holding_weight=d["matched_holding_weight"],
        disclosed_holding_weight=d["disclosed_holding_weight"],
        normalized_match_pct=d["normalized_match_pct"],
        holding_report_date=d["holding_report_date"],
        holding_age_days=d["holding_age_days"],
        factor_coverage_weight=d["factor_coverage_weight"],
        valuation=d["valuation"],
        holding_trend=d["holding_trend"],
        manager_identity=d["manager_identity"],
        evidence_types=d["evidence_types"],
        policy_conflicts=tuple(d.get("policy_conflicts", ())),
        data_snapshot_id=d["data_snapshot_id"],
        asset_type=d.get("asset_type", "fund"),
    )


def _default_engine_factory(source_db: str, factor_db: str | None) -> CognitionEngine:
    """默认 CognitionEngine 工厂。"""
    return CognitionEngine(source_db, factor_db)  # type: ignore[arg-type]


# ============================================================
# CognitionGovernanceService
# ============================================================
class CognitionGovernanceService:
    """认知治理 Service。

    负责:
    1. 从投资假设生成 CandidateSet(调用 CognitionEngine)
    2. 编排 PriorityRun(调用 CandidatePriorityEngine)
    3. 查询 PriorityRun 详情和历史
    """

    def __init__(
        self,
        governance_repo: GovernanceRepository,
        priority_repo: CandidatePriorityRepository,
        engine_factory: Callable[[str, str | None], CognitionEngine] | None = None,
    ) -> None:
        self._governance_repo = governance_repo
        self._priority_repo = priority_repo
        self._engine_factory = engine_factory or _default_engine_factory
        self._priority_engine = CandidatePriorityEngine()

    # ----------------------------------------------------------
    # Task 7: CandidateSet 创建
    # ----------------------------------------------------------
    def create_candidate_set(
        self,
        *,
        thesis_id: str,
        data_snapshot_id: str,
        actor_id: str,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """从投资假设生成 CandidateSet。

        流程:
        1. 读 Thesis -> 读 ResearchInput -> 校验 structured_intent
        2. 读 data_snapshot，获取 source_db_path 和 factor_db_path
        3. 用 snapshot 路径构建 CognitionEngine
        4. 调用 build_fund_candidate_evidence()
        5. 在单事务写 header、候选和 audit
        """
        # 1. 读 Thesis
        thesis = self._governance_repo.get_thesis(thesis_id)
        if thesis is None:
            raise ThesisNotFoundError(f"投资假设不存在: {thesis_id}")

        # 2. 读 ResearchInput
        user_input_id = thesis["user_input_id"]
        research_input = self._governance_repo.get_research_input(user_input_id)
        if research_input is None:
            raise GovernanceError(f"研究请求不存在: {user_input_id}")

        # 3. 校验 structured_intent
        intent = research_input.get("structured_intent") or {}
        required_fields = ("direction", "conviction", "time_horizon", "risk_tolerance")
        missing = [f for f in required_fields if not intent.get(f)]
        if missing:
            raise StructuredIntentIncompleteError(
                f"structured_intent 缺少必填字段: {missing}"
            )

        # 4. 读 data_snapshot
        snapshot = self._governance_repo.get_data_snapshot(data_snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(f"数据快照不存在: {data_snapshot_id}")

        # 5. 从 snapshot 获取路径
        source_db_path = snapshot.get("source_db_path")
        factor_db_path = snapshot.get("factor_db_path")

        # 6. 检查 source_db_path 文件存在
        if not source_db_path or not Path(source_db_path).exists():
            raise CandidateDataSourceUnavailableError(
                f"候选数据源文件不存在: {data_snapshot_id}"
            )

        # 7. 创建 CognitionEngine
        engine = self._engine_factory(source_db_path, factor_db_path)

        try:
            # 8. 调用 build_fund_candidate_evidence
            # 优先用 thesis / research_input 的 as_of_date，否则用 snapshot 的 created_at
            as_of_date = (
                thesis.get("as_of_date")
                or research_input.get("as_of_date")
            )
            if not as_of_date:
                snapshot_created = snapshot.get("created_at") or ""
                as_of_date = snapshot_created[:10] if snapshot_created else None
            if not as_of_date:
                raise GovernanceError(
                    "缺少 as_of_date: thesis、research_input 和 snapshot 都没有有效日期"
                )

            # 从 target_assets 提取点名基金代码
            target_assets = research_input.get("target_assets") or []
            explicitly_named: list[str] = []
            for asset in target_assets:
                if isinstance(asset, dict) and asset.get("asset_type") == "fund":
                    code = asset.get("asset_code") or asset.get("code")
                    if code:
                        explicitly_named.append(code)
                elif isinstance(asset, str):
                    explicitly_named.append(asset)

            batch: FundCandidateEvidenceBatch = engine.build_fund_candidate_evidence(
                direction=intent["direction"],
                belief_link=intent.get("belief_link"),
                conviction=intent["conviction"],
                time_horizon=intent["time_horizon"],
                risk_tolerance=intent["risk_tolerance"],
                data_snapshot_id=data_snapshot_id,
                as_of_date=as_of_date,
                explicitly_named_fund_codes=explicitly_named,
            )

            # 9. 在事务中写入
            candidate_set_id = _short_id("cs")

            with self._governance_repo.transaction() as tx:
                # 检查幂等键
                existing = tx.get_candidate_set_header_by_key(
                    thesis_id, data_snapshot_id, _SOURCE_METHOD_VERSION
                )
                if existing:
                    raise DuplicateCandidateSetError(existing["candidate_set_id"])

                # 写 header
                tx.insert_candidate_set_header(
                    candidate_set_id=candidate_set_id,
                    thesis_id=thesis_id,
                    user_input_id=user_input_id,
                    data_snapshot_id=data_snapshot_id,
                    source_method_version=_SOURCE_METHOD_VERSION,
                    scanned_fund_count=batch.scanned_fund_count,
                    mapped_candidate_count=batch.mapped_candidate_count,
                    unmapped_due_to_data_count=batch.unmapped_due_to_data_count,
                    created_by=actor_id,
                )

                # 写候选
                candidates: list[dict[str, Any]] = []
                for ev in batch.all_candidates:
                    candidates.append(
                        {
                            "candidate_set_id": candidate_set_id,
                            "thesis_id": thesis_id,
                            "user_input_id": user_input_id,
                            "asset_type": ev.asset_type,
                            "asset_code": ev.fund_code,
                            "asset_name": ev.fund_name,
                            "fit_score": ev.matched_holding_weight,
                            "data_snapshot_id": data_snapshot_id,
                            "candidate_evidence": _evidence_to_dict(ev),
                        }
                    )

                if candidates:
                    tx.insert_candidates(candidates)

                # 写 audit
                tx.insert_audit_log(
                    action="create_candidate_set",
                    target_type="candidate_set",
                    target_id=candidate_set_id,
                    payload={
                        "thesis_id": thesis_id,
                        "data_snapshot_id": data_snapshot_id,
                        "candidate_count": len(candidates),
                        "scanned_fund_count": batch.scanned_fund_count,
                        "mapped_candidate_count": batch.mapped_candidate_count,
                    },
                    actor=actor_id,
                    source_ip=source_ip,
                )
        finally:
            # 10. 关闭 CognitionEngine
            engine.close()

        # 11. 返回
        return {
            "candidate_set_id": candidate_set_id,
            "thesis_id": thesis_id,
            "mapped_candidate_count": batch.mapped_candidate_count,
            "scanned_fund_count": batch.scanned_fund_count,
            "unmapped_due_to_data_count": batch.unmapped_due_to_data_count,
            "data_snapshot_id": data_snapshot_id,
        }

    # ----------------------------------------------------------
    # Task 8: PriorityRun 编排
    # ----------------------------------------------------------
    def create_priority_run(
        self,
        *,
        thesis_id: str,
        candidate_set_id: str,
        data_snapshot_id: str,
        ranking_method_version: str,
        actor_id: str,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """创建优先级评价运行。

        流程:
        1. 校验 thesis / candidate_set / snapshot / policy 对齐
        2. 读取候选证据
        3. 解析策略配置
        4. 在内存完成所有评价和档内排序
        5. 开启写事务，原子写入 run + results + audit
        """
        # 1. 读 Thesis
        thesis = self._governance_repo.get_thesis(thesis_id)
        if thesis is None:
            raise ThesisNotFoundError(f"投资假设不存在: {thesis_id}")

        # 2. 读 CandidateSet header
        header = self._governance_repo.get_candidate_set_header(candidate_set_id)
        if header is None:
            raise CandidateSetNotFoundError(f"候选集合不存在: {candidate_set_id}")

        # 3. 校验 header.thesis_id == thesis_id
        if header["thesis_id"] != thesis_id:
            raise GovernanceError(
                f"候选集合 {candidate_set_id} 属于 thesis {header['thesis_id']!r},"
                f"与请求的 {thesis_id!r} 不一致"
            )

        # 4. 校验 header.data_snapshot_id == data_snapshot_id
        header_snapshot_id = header.get("data_snapshot_id")
        if header_snapshot_id != data_snapshot_id:
            raise GovernanceError(
                f"候选集合 {candidate_set_id} 的 data_snapshot_id="
                f"{header_snapshot_id!r} 与请求的 {data_snapshot_id!r} 不一致"
            )

        # 5. 读候选列表
        candidates = self._governance_repo.get_candidates_by_set(candidate_set_id)

        # 6. 检查 candidate_evidence 非空
        for c in candidates:
            if not c.get("candidate_evidence"):
                raise GovernanceError(
                    f"候选 {c.get('candidate_id')} 的 candidate_evidence 缺失"
                )

        # 7. 从 Thesis 获取 strategy_policy_id 和 version
        policy_id = thesis["strategy_policy_id"]
        policy_version = thesis["strategy_policy_version"]

        # 8. 读策略
        policy_row = self._governance_repo.get_strategy_policy(policy_id, policy_version)
        if policy_row is None:
            raise PolicyNotFoundError(
                f"策略不存在: {policy_id} v{policy_version}"
            )

        # 9. 解析 candidate_priority 配置
        policy = parse_candidate_priority_policy(policy_row)

        # 10. 校验 ranking_method_version == policy.method_version
        if ranking_method_version != policy.method_version:
            raise GovernanceError(
                f"ranking_method_version {ranking_method_version!r} 与策略 "
                f"method_version {policy.method_version!r} 不一致"
            )

        # 10b. 校验策略 source_method_version 与 CandidateSet header 的 source_method_version 一致
        if (
            policy.source_method_version
            and header.get("source_method_version")
            and policy.source_method_version != header.get("source_method_version")
        ):
            raise GovernanceError(
                f"策略 source_method_version {policy.source_method_version!r} "
                f"与 CandidateSet source_method_version "
                f"{header.get('source_method_version')!r} 不一致"
            )

        # 11. 检查幂等键
        existing_run_id = self._priority_repo.get_existing_run_id(
            candidate_set_id=candidate_set_id,
            strategy_policy_id=policy_id,
            strategy_policy_version=policy_version,
            data_snapshot_id=data_snapshot_id,
            ranking_method_version=ranking_method_version,
        )
        if existing_run_id:
            raise DuplicatePriorityRunError(existing_run_id)

        # 12. 在内存中评价
        try:
            evidences = [
                _dict_to_evidence(c["candidate_evidence"]) for c in candidates
            ]
            results: list[CandidatePriorityResult] = (
                self._priority_engine.evaluate_all(evidences, policy)
            )

            eligible_count = sum(
                1 for r in results if r.eligibility_status == "eligible"
            )
            result_type = (
                "ranked_candidates" if eligible_count > 0 else "no_eligible_candidate"
            )

            tier_counts: dict[str, int] = dict.fromkeys(PRIORITY_TIERS, 0)
            for r in results:
                if r.priority_tier in tier_counts:
                    tier_counts[r.priority_tier] += 1
        except Exception as exc:
            # 写失败 audit(独立短事务，不写敏感数据)
            self._write_failure_audit(
                thesis_id=thesis_id,
                candidate_set_id=candidate_set_id,
                policy_id=policy_id,
                policy_version=policy_version,
                data_snapshot_id=data_snapshot_id,
                ranking_method_version=ranking_method_version,
                actor_id=actor_id,
                source_ip=source_ip,
                error=exc,
            )
            raise

        # 13. 开启写事务
        run_id = _short_id("cpr")
        candidate_map = {c["asset_code"]: c["candidate_id"] for c in candidates}

        result_dicts: list[dict[str, Any]] = []
        for r in results:
            result_dicts.append(self._result_to_dict(r, run_id, candidate_map))

        with self._priority_repo.transaction() as tx:
            tx.insert_run(
                {
                    "priority_run_id": run_id,
                    "candidate_set_id": candidate_set_id,
                    "thesis_id": thesis_id,
                    "user_input_id": thesis["user_input_id"],
                    "strategy_policy_id": policy_id,
                    "strategy_policy_version": policy_version,
                    "data_snapshot_id": data_snapshot_id,
                    "ranking_method_version": ranking_method_version,
                    "result_type": result_type,
                    "evaluated_candidate_count": len(results),
                    "eligible_candidate_count": eligible_count,
                    "scanned_fund_count": header.get("scanned_fund_count"),
                    "mapped_candidate_count": header.get("mapped_candidate_count"),
                    "unmapped_due_to_data_count": header.get("unmapped_due_to_data_count"),
                    "tier_counts": tier_counts,
                    "created_by": actor_id,
                }
            )

            if result_dicts:
                tx.insert_results(result_dicts)

            tx.insert_audit_log(
                action="create_priority_run",
                target_type="priority_run",
                target_id=run_id,
                payload={
                    "thesis_id": thesis_id,
                    "candidate_set_id": candidate_set_id,
                    "result_type": result_type,
                    "evaluated_candidate_count": len(results),
                    "eligible_candidate_count": eligible_count,
                    "tier_counts": tier_counts,
                },
                actor=actor_id,
                run_id=run_id,
                source_ip=source_ip,
            )

        # 14. 返回
        return {
            "priority_run_id": run_id,
            "result_type": result_type,
            "evaluated_candidate_count": len(results),
            "eligible_candidate_count": eligible_count,
            "tier_counts": tier_counts,
            "approved_for_production": policy.approved_for_production,
        }

    @staticmethod
    def _result_to_dict(
        result: CandidatePriorityResult,
        run_id: str,
        candidate_map: dict[str, str],
    ) -> dict[str, Any]:
        """把 CandidatePriorityResult 转换为可写入的 result dict。"""
        candidate_id = candidate_map.get(result.fund_code, "")
        return {
            "priority_result_id": _short_id("cprr"),
            "priority_run_id": run_id,
            "candidate_id": candidate_id,
            "fund_code": result.fund_code,
            "fund_name": result.fund_name,
            "eligibility_status": result.eligibility_status,
            "priority_tier": result.priority_tier,
            "priority_rank": result.priority_rank,
            "matched_holding_weight": result.evidence.matched_holding_weight,
            "disclosed_holding_weight": result.evidence.disclosed_holding_weight,
            "normalized_match_pct": result.evidence.normalized_match_pct,
            "fit_score": result.fit_score,
            "evidence_score": result.evidence_score,
            "holdings_truth_status": result.dimension_results.get("holding_truth_status"),
            "valuation_status": result.dimension_results.get("valuation_status"),
            "data_quality_status": result.dimension_results.get("data_quality_status"),
            "holding_report_date": result.evidence.holding_report_date,
            "dimension_results": result.dimension_results,
            "priority_reasons": [
                {"code": r.code, "message": r.message} for r in result.reasons
            ],
            "exclusion_reasons": [
                {"code": r.code, "message": r.message} for r in result.exclusion_reasons
            ],
        }

    def _write_failure_audit(
        self,
        *,
        thesis_id: str,
        candidate_set_id: str,
        policy_id: str,
        policy_version: int,
        data_snapshot_id: str,
        ranking_method_version: str,
        actor_id: str,
        source_ip: str | None,
        error: BaseException,
    ) -> None:
        """写失败审计(独立短事务，不写敏感数据)。"""
        with self._priority_repo.transaction() as tx:
            tx.insert_audit_log(
                action="create_priority_run_failed",
                target_type="priority_run",
                target_id=candidate_set_id,
                payload={
                    "thesis_id": thesis_id,
                    "candidate_set_id": candidate_set_id,
                    "strategy_policy_id": policy_id,
                    "strategy_policy_version": policy_version,
                    "data_snapshot_id": data_snapshot_id,
                    "ranking_method_version": ranking_method_version,
                    "error_type": type(error).__name__,
                    "error_code": "evaluation_failed",
                },
                actor=actor_id,
                source_ip=source_ip,
            )

    # ----------------------------------------------------------
    # 查询服务
    # ----------------------------------------------------------
    def get_priority_run(self, priority_run_id: str) -> dict[str, Any] | None:
        """查询 PriorityRun 详情，按固定五档分组返回候选列表。"""
        run = self._priority_repo.get_run(priority_run_id)
        if run is None:
            return None

        results = self._priority_repo.get_results(priority_run_id)

        # 按五档分组
        tiers: dict[str, list[dict[str, Any]]] = {tier: [] for tier in PRIORITY_TIERS}
        for r in results:
            tier = r.get("priority_tier", "excluded")
            if tier not in tiers:
                tier = "excluded"
            tiers[tier].append(r)

        # 查询策略获取 approved_for_production
        approved = False
        policy_row = self._governance_repo.get_strategy_policy(
            run["strategy_policy_id"], run["strategy_policy_version"]
        )
        if policy_row:
            try:
                policy = parse_candidate_priority_policy(policy_row)
                approved = policy.approved_for_production
            except Exception:
                pass

        return {
            "priority_run_id": run["priority_run_id"],
            "thesis_id": run["thesis_id"],
            "candidate_set_id": run["candidate_set_id"],
            "strategy_policy_id": run["strategy_policy_id"],
            "strategy_policy_version": run["strategy_policy_version"],
            "data_snapshot_id": run.get("data_snapshot_id"),
            "ranking_method_version": run["ranking_method_version"],
            "result_type": run["result_type"],
            "result_status": run.get("result_status"),
            "evaluated_candidate_count": run["evaluated_candidate_count"],
            "eligible_candidate_count": run["eligible_candidate_count"],
            "tier_counts": run.get("tier_counts") or {},
            "approved_for_production": approved,
            "created_by": run["created_by"],
            "created_at": run["created_at"],
            "candidates_by_tier": tiers,
        }

    def list_priority_runs(self, thesis_id: str) -> list[dict[str, Any]]:
        """按 Thesis 查询历史 PriorityRun。"""
        runs = self._priority_repo.list_runs_by_thesis(thesis_id)
        return [
            {
                "priority_run_id": run["priority_run_id"],
                "thesis_id": run["thesis_id"],
                "candidate_set_id": run["candidate_set_id"],
                "strategy_policy_id": run["strategy_policy_id"],
                "strategy_policy_version": run["strategy_policy_version"],
                "data_snapshot_id": run.get("data_snapshot_id"),
                "ranking_method_version": run["ranking_method_version"],
                "result_type": run["result_type"],
                "result_status": run.get("result_status"),
                "evaluated_candidate_count": run["evaluated_candidate_count"],
                "eligible_candidate_count": run["eligible_candidate_count"],
                "tier_counts": run.get("tier_counts") or {},
                "created_by": run["created_by"],
                "created_at": run["created_at"],
            }
            for run in runs
        ]
