"""治理核心 API Router:研究请求 / 候选集合 / 优先级评价。

路由:
    POST /v1/governance/research-inputs         创建研究请求
    GET  /v1/governance/research-inputs/{input_id}  查询研究请求
    GET  /v1/governance/candidate-sets/{candidate_set_id}  查询候选集合(含反查链路)
    POST /v1/governance/theses/{thesis_id}/candidate-sets  从投资假设生成 CandidateSet
    POST /v1/governance/theses/{thesis_id}/candidate-priority-runs  创建优先级评价
    GET  /v1/governance/candidate-priority-runs/{priority_run_id}  查询优先级结果
    GET  /v1/governance/theses/{thesis_id}/candidate-priority-runs  查询历史评价

领域异常 -> HTTP 状态码:
    PolicyNotFoundError / ResearchInputNotFoundError / SnapshotNotFoundError -> 404
    DuplicateResearchInputError -> 409
    InvalidStatusTransitionError -> 422
    GovernanceError(其他) -> 422

    ThesisNotFoundError / CandidateSetNotFoundError / SnapshotNotFoundError /
    PolicyNotFoundError(认知治理) -> 404
    DuplicateCandidateSetError / DuplicatePriorityRunError -> 409
    StructuredIntentIncompleteError / CandidatePriorityConfigurationError -> 422
    CandidateDataSourceUnavailableError -> 503
"""
from __future__ import annotations

from typing import Any

from app.persistence.candidate_priority import CandidatePriorityRepository
from app.persistence.governance import GovernanceRepository
from app.services import cognition_governance_service as _cgs
from app.services.candidate_priority import CandidatePriorityConfigurationError
from app.services.cognition_governance_service import CognitionGovernanceService
from app.services.governance_service import (
    DuplicateResearchInputError,
    GovernanceError,
    GovernanceService,
    InvalidStatusTransitionError,
    PolicyNotFoundError,
    ResearchInputNotFoundError,
    SnapshotNotFoundError,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field


# ============================================================
# Pydantic 模型
# ============================================================
class CreateResearchInputRequest(BaseModel):
    """创建研究请求。客户端应传入稳定的 user_input_id 以支持幂等重试。"""
    user_input_id: str | None = Field(None, description="客户端生成的稳定 ID,支持幂等重试")
    input_type: str = Field(..., description="philosophy / industry / target / manager / strategy")
    business_mode: str = Field("private_strategy", description="private_strategy / fof")
    strategy_policy_id: str
    strategy_policy_version: int
    actor_role: str = Field(..., description="researcher / portfolio_manager / risk / product")
    actor_id: str = Field(..., description="机构内部身份标识(必填)")
    request_source: str = Field("ad_hoc_research", description="研究会议/临时研究等")
    raw_text: str = Field(..., description="原始研究观点(不可变)")
    structured_intent: dict | None = None
    target_assets: list | None = None
    implicit_intent: str | None = None
    session_id: str | None = None
    previous_user_input_id: str | None = None
    as_of_date: str | None = None
    data_snapshot_id: str | None = None


class ResearchInputResponse(BaseModel):
    user_input_id: str
    status: str


class CandidateSetResponse(BaseModel):
    """候选集合查询响应,包含从候选反查研究请求、投资假设、策略版本和数据快照的完整链路。"""
    candidate_set_id: str
    thesis_id: str | None = None
    user_input_id: str | None = None
    strategy_policy_id: str | None = None
    strategy_policy_version: int | None = None
    data_snapshot_id: str | None = None
    candidates: list[dict[str, Any]] = []


class CreateCandidateSetRequest(BaseModel):
    """从投资假设生成 CandidateSet 的请求。"""
    data_snapshot_id: str
    actor_id: str


class CreatePriorityRunRequest(BaseModel):
    """创建优先级评价的请求。"""
    candidate_set_id: str
    data_snapshot_id: str
    ranking_method_version: str
    actor_id: str


class CreateCandidateSetResponse(BaseModel):
    """CandidateSet 创建响应。"""
    candidate_set_id: str
    thesis_id: str
    mapped_candidate_count: int
    scanned_fund_count: int
    unmapped_due_to_data_count: int
    data_snapshot_id: str


class CreatePriorityRunResponse(BaseModel):
    """PriorityRun 创建响应。"""
    priority_run_id: str
    result_type: str
    evaluated_candidate_count: int
    eligible_candidate_count: int
    tier_counts: dict[str, Any] = Field(default_factory=dict)
    approved_for_production: bool


# ============================================================
# 依赖
# ============================================================
def get_governance_service(request: Request) -> GovernanceService:
    """从 app.state 获取 GovernanceService(延迟初始化)。

    数据库选择优先级:
        1. output_db_path(双库模式的输出库,治理数据应写入这里)
        2. db_path(单库模式)
        3. source_db_path(最后兜底,不推荐把治理数据写入源数据库)
    """
    if not hasattr(request.app.state, "governance_service"):
        db_path = (
            getattr(request.app.state, "output_db_path", None)
            or getattr(request.app.state, "db_path", None)
            or getattr(request.app.state, "source_db_path", None)
        )
        if not db_path:
            raise HTTPException(
                status_code=503,
                detail="数据库未配置。设置 FLE_OUTPUT_DB / FLE_DB_PATH / FLE_SOURCE_DB。",
            )
        repo = GovernanceRepository(db_path)
        request.app.state.governance_service = GovernanceService(repo)
    return request.app.state.governance_service


def get_cognition_governance_service(request: Request) -> CognitionGovernanceService:
    """从 app.state 获取 CognitionGovernanceService(延迟初始化)。

    复用 governance DB 路径选择逻辑:
        1. output_db_path(双库模式的输出库,治理数据应写入这里)
        2. db_path(单库模式)
        3. source_db_path(最后兜底)
    """
    if not hasattr(request.app.state, "cognition_governance_service"):
        db_path = (
            getattr(request.app.state, "output_db_path", None)
            or getattr(request.app.state, "db_path", None)
            or getattr(request.app.state, "source_db_path", None)
        )
        if not db_path:
            raise HTTPException(status_code=503, detail="数据库未配置")
        gov_repo = GovernanceRepository(db_path)
        priority_repo = CandidatePriorityRepository(db_path)
        request.app.state.cognition_governance_service = CognitionGovernanceService(
            governance_repo=gov_repo,
            priority_repo=priority_repo,
        )
    return request.app.state.cognition_governance_service


def _get_source_ip(request: Request) -> str | None:
    """从请求上下文获取 source_ip。

    信任边界:
    - 默认只记录 request.client.host(直连 IP,不可伪造)
    - 只有配置了可信反向代理(FLE_TRUSTED_PROXY=1)时才读 X-Forwarded-For
    - 同时保存 peer IP 和 forwarded IP,审计可追溯
    """
    import os

    peer_ip = request.client.host if request.client else None
    trusted_proxy = os.environ.get("FLE_TRUSTED_PROXY", "") == "1"

    if trusted_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer_ip


# ============================================================
# 异常映射
# ============================================================
def _map_governance_error(exc: GovernanceError) -> HTTPException:
    """把领域异常映射到 HTTP 状态码。"""
    if isinstance(exc, (PolicyNotFoundError, ResearchInputNotFoundError, SnapshotNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, DuplicateResearchInputError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, InvalidStatusTransitionError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _map_cognition_error(exc: Exception) -> HTTPException:
    """把认知治理领域异常映射到 HTTP 状态码。

    ThesisNotFoundError / CandidateSetNotFoundError / SnapshotNotFoundError /
    PolicyNotFoundError -> 404
    DuplicateCandidateSetError / DuplicatePriorityRunError -> 409
    StructuredIntentIncompleteError / CandidatePriorityConfigurationError -> 422
    CandidateDataSourceUnavailableError -> 503
    其他 GovernanceError -> 422
    """
    if isinstance(exc, (
        _cgs.ThesisNotFoundError,
        _cgs.CandidateSetNotFoundError,
        _cgs.SnapshotNotFoundError,
        _cgs.PolicyNotFoundError,
    )):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, _cgs.DuplicateCandidateSetError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, _cgs.DuplicatePriorityRunError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, _cgs.StructuredIntentIncompleteError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, CandidatePriorityConfigurationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, _cgs.CandidateDataSourceUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


# ============================================================
# Router
# ============================================================
router = APIRouter(prefix="/v1/governance", tags=["governance"])


@router.post(
    "/research-inputs",
    response_model=ResearchInputResponse,
    status_code=201,
    summary="创建研究请求",
)
def create_research_input(
    request_body: CreateResearchInputRequest,
    request: Request,
    service: GovernanceService = Depends(get_governance_service),
) -> ResearchInputResponse:
    """创建一条研究请求。

    - 客户端应传入稳定的 `user_input_id` 以支持网络重试幂等
    - `source_ip` 从请求上下文自动获取,不从 body 传入
    - `raw_text` 一旦写入即不可变;修订需通过 `previous_user_input_id` 新增
    """
    try:
        result = service.create_research_input(
            user_input_id=request_body.user_input_id,
            input_type=request_body.input_type,
            business_mode=request_body.business_mode,
            strategy_policy_id=request_body.strategy_policy_id,
            strategy_policy_version=request_body.strategy_policy_version,
            actor_role=request_body.actor_role,
            actor_id=request_body.actor_id,
            request_source=request_body.request_source,
            raw_text=request_body.raw_text,
            structured_intent=request_body.structured_intent,
            target_assets=request_body.target_assets,
            implicit_intent=request_body.implicit_intent,
            session_id=request_body.session_id,
            previous_user_input_id=request_body.previous_user_input_id,
            as_of_date=request_body.as_of_date,
            data_snapshot_id=request_body.data_snapshot_id,
            source_ip=_get_source_ip(request),
        )
        return ResearchInputResponse(**result)
    except GovernanceError as exc:
        raise _map_governance_error(exc) from exc


@router.get(
    "/research-inputs/{input_id}",
    summary="查询研究请求",
)
def get_research_input(
    input_id: str,
    service: GovernanceService = Depends(get_governance_service),
) -> dict[str, Any]:
    """查询一条研究请求。不存在返回 404。"""
    ri = service.get_research_input(input_id)
    if ri is None:
        raise HTTPException(status_code=404, detail=f"研究请求不存在: {input_id}")
    return ri


@router.get(
    "/candidate-sets/{candidate_set_id}",
    response_model=CandidateSetResponse,
    summary="查询候选集合(含反查链路)",
)
def get_candidate_set(
    candidate_set_id: str,
    service: GovernanceService = Depends(get_governance_service),
) -> CandidateSetResponse:
    """查询候选集合。

    返回的不仅是候选行,还包含:
    - candidate_set_id
    - thesis_id(从集合头获取)
    - user_input_id(从集合头获取)
    - strategy_policy_id + version(从 thesis 获取)
    - data_snapshot_id(从集合头获取,不是 thesis)
    - candidates(完整候选列表)

    这样机构投研可以从候选直接反查到研究请求、投资假设、策略版本和数据快照。
    """
    # 优先从集合头获取元信息（正确的快照来源）
    header = service.get_candidate_set_header(candidate_set_id)

    candidates = service.get_candidates_by_set(candidate_set_id)

    # 集合头和候选行都不存在时才是 404
    if not header and not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"候选集合不存在: {candidate_set_id}",
        )

    # 从集合头获取 thesis_id、user_input_id、data_snapshot_id
    if header:
        thesis_id = header.get("thesis_id")
        user_input_id = header.get("user_input_id")
        data_snapshot_id = header.get("data_snapshot_id")
    else:
        # 回退：从第一个候选获取（旧数据兼容）
        first = candidates[0]
        thesis_id = first.get("thesis_id")
        user_input_id = first.get("user_input_id")
        data_snapshot_id = None

    # 从 thesis 获取策略版本
    # 旧数据兼容：如果 header 没有 data_snapshot_id，从 thesis 回退
    strategy_policy_id = None
    strategy_policy_version = None
    if thesis_id:
        thesis = service.get_thesis(thesis_id)
        if thesis:
            strategy_policy_id = thesis.get("strategy_policy_id")
            strategy_policy_version = thesis.get("strategy_policy_version")
            if not data_snapshot_id:
                data_snapshot_id = thesis.get("data_snapshot_id")

    return CandidateSetResponse(
        candidate_set_id=candidate_set_id,
        thesis_id=thesis_id,
        user_input_id=user_input_id,
        strategy_policy_id=strategy_policy_id,
        strategy_policy_version=strategy_policy_version,
        data_snapshot_id=data_snapshot_id,
        candidates=candidates,
    )


# ============================================================
# 认知治理 API: CandidateSet 生成 + PriorityRun 编排
# ============================================================
@router.post(
    "/theses/{thesis_id}/candidate-sets",
    response_model=CreateCandidateSetResponse,
    status_code=201,
    summary="从投资假设生成 CandidateSet",
)
def create_candidate_set(
    thesis_id: str,
    request_body: CreateCandidateSetRequest,
    request: Request,
    service: CognitionGovernanceService = Depends(get_cognition_governance_service),
) -> CreateCandidateSetResponse:
    """从投资假设生成 CandidateSet。

    - 根据 thesis_id 读取投资假设和结构化意图
    - 用 data_snapshot_id 对应的数据快照构建 CognitionEngine
    - 调用认知引擎生成基金候选证据并写入候选集合
    - source_ip 从请求上下文自动获取,不从 body 传入
    """
    try:
        result = service.create_candidate_set(
            thesis_id=thesis_id,
            data_snapshot_id=request_body.data_snapshot_id,
            actor_id=request_body.actor_id,
            source_ip=_get_source_ip(request),
        )
        return CreateCandidateSetResponse(**result)
    except (_cgs.GovernanceError, CandidatePriorityConfigurationError) as exc:
        raise _map_cognition_error(exc) from exc


@router.post(
    "/theses/{thesis_id}/candidate-priority-runs",
    response_model=CreatePriorityRunResponse,
    status_code=201,
    summary="创建优先级评价",
)
def create_priority_run(
    thesis_id: str,
    request_body: CreatePriorityRunRequest,
    request: Request,
    service: CognitionGovernanceService = Depends(get_cognition_governance_service),
) -> CreatePriorityRunResponse:
    """创建优先级评价运行。

    - 校验 thesis / candidate_set / snapshot / policy 对齐
    - 读取候选证据并在内存中完成评价和档内排序
    - 原子写入 run + results + audit
    - no_eligible_candidate 也是成功状态(201),不是错误
    - source_ip 从请求上下文自动获取,不从 body 传入
    """
    try:
        result = service.create_priority_run(
            thesis_id=thesis_id,
            candidate_set_id=request_body.candidate_set_id,
            data_snapshot_id=request_body.data_snapshot_id,
            ranking_method_version=request_body.ranking_method_version,
            actor_id=request_body.actor_id,
            source_ip=_get_source_ip(request),
        )
        return CreatePriorityRunResponse(**result)
    except (_cgs.GovernanceError, CandidatePriorityConfigurationError) as exc:
        raise _map_cognition_error(exc) from exc


@router.get(
    "/candidate-priority-runs/{priority_run_id}",
    summary="查询优先级结果",
)
def get_priority_run(
    priority_run_id: str,
    service: CognitionGovernanceService = Depends(get_cognition_governance_service),
) -> dict[str, Any]:
    """查询优先级评价详情,按固定五档分组返回候选列表。不存在返回 404。"""
    result = service.get_priority_run(priority_run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"优先级评价不存在: {priority_run_id}",
        )
    return result


@router.get(
    "/theses/{thesis_id}/candidate-priority-runs",
    summary="查询投资假设的历史评价",
)
def list_priority_runs(
    thesis_id: str,
    service: CognitionGovernanceService = Depends(get_cognition_governance_service),
) -> list[dict[str, Any]]:
    """按投资假设查询历史 PriorityRun 列表。"""
    return service.list_priority_runs(thesis_id)


# ============================================================
# 策略宪法 API: 从策略政策编译宪法
# ============================================================
@router.get(
    "/constitutions/{policy_id}",
    summary="获取策略宪法版本",
)
def get_constitution(
    policy_id: str,
    version: int | None = None,
    service: GovernanceService = Depends(get_governance_service),
) -> dict[str, Any]:
    """获取宪法版本(默认返回最新版本)。

    - 如果指定 version,编译该版本策略政策对应的宪法
    - 如果不指定 version,优先找 active 状态的版本,其次找最大版本号
    """
    from app.governance.constitution import create_constitution_from_policy

    # 确定要查询的版本
    target_version = version
    if target_version is None:
        # 查找该 policy_id 的所有版本,优先取 active,其次取最大 version
        import sqlite3

        db_path = (
            getattr(service, "_repo", None)
            and getattr(service._repo, "_db_path", None)
        )
        if not db_path:
            raise HTTPException(status_code=503, detail="数据库路径未配置")
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            # 优先找 active 版本
            row = conn.execute(
                "SELECT version FROM strategy_policies "
                "WHERE policy_id = ? AND policy_status = 'active' "
                "ORDER BY version DESC LIMIT 1",
                (policy_id,),
            ).fetchone()
            if row is not None:
                target_version = row["version"]
            else:
                # 回退:找最大 version
                row = conn.execute(
                    "SELECT MAX(version) AS max_version FROM strategy_policies WHERE policy_id = ?",
                    (policy_id,),
                ).fetchone()
                if row is not None and row["max_version"] is not None:
                    target_version = row["max_version"]

        if target_version is None:
            raise HTTPException(
                status_code=404,
                detail=f"策略政策不存在: {policy_id}",
            )

    # 读取策略政策
    policy = service._repo.get_strategy_policy(policy_id, target_version)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"策略政策不存在: {policy_id} v{target_version}",
        )

    # 编译宪法
    constitution = create_constitution_from_policy(policy, policy_id, target_version)
    return constitution.to_dict()


@router.post(
    "/constitutions/{policy_id}/compile",
    summary="从策略政策编译宪法",
    status_code=201,
)
def compile_constitution(
    policy_id: str,
    version: int,
    service: GovernanceService = Depends(get_governance_service),
) -> dict[str, Any]:
    """从策略政策编译宪法。

    - 从数据库读取指定版本的策略政策
    - 调用 create_constitution_from_policy 生成宪法版本
    - 返回编译后的宪法(含准则列表、校验结果、编译输出)
    """
    from app.governance.constitution import create_constitution_from_policy

    # 读取策略政策
    policy = service._repo.get_strategy_policy(policy_id, version)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"策略政策不存在: {policy_id} v{version}",
        )

    # 编译宪法
    constitution = create_constitution_from_policy(policy, policy_id, version)
    return constitution.to_dict()


# ============================================================
# Pipeline 工作流编排 API
# ============================================================
@router.post(
    "/pipeline/run",
    summary="执行认知研究 pipeline",
)
async def run_pipeline(direction: str):
    """执行认知研究 pipeline。

    - 按阶段顺序执行：screener -> cognition -> ic_review -> memo -> portfolio -> monitoring
    - 漏斗阶段失败则 pipeline 立即 fail
    - 非漏斗阶段失败不 fail pipeline，标记为 partial
    """
    from app.governance.pipeline import execute_cognition_pipeline

    result = execute_cognition_pipeline(direction)
    return result.to_dict()


@router.get(
    "/pipeline/runs",
    summary="列出 pipeline runs",
)
async def list_runs(direction: str | None = None):
    """列出 pipeline runs，可按 direction 过滤。"""
    from app.governance.pipeline import get_run_store

    store = get_run_store()
    runs = store.list_runs(direction)
    return [r.to_dict() for r in runs]


@router.get(
    "/pipeline/runs/{run_id}",
    summary="获取 pipeline run 详情",
)
async def get_run(run_id: str):
    """获取 pipeline run 详情。不存在返回 404。"""
    from app.governance.pipeline import get_run_store

    store = get_run_store()
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run.to_dict()
