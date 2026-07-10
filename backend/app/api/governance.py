"""治理核心 API Router:研究请求 / 候选集合。

路由:
    POST /v1/governance/research-inputs         创建研究请求
    GET  /v1/governance/research-inputs/{input_id}  查询研究请求
    GET  /v1/governance/candidate-sets/{candidate_set_id}  查询候选集合(含反查链路)

领域异常 -> HTTP 状态码:
    PolicyNotFoundError / ResearchInputNotFoundError / SnapshotNotFoundError -> 404
    DuplicateResearchInputError -> 409
    InvalidStatusTransitionError -> 422
    GovernanceError(其他) -> 422
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.persistence.governance import GovernanceRepository
from app.services.governance_service import (
    DuplicateResearchInputError,
    GovernanceError,
    GovernanceService,
    InvalidStatusTransitionError,
    PolicyNotFoundError,
    ResearchInputNotFoundError,
    SnapshotNotFoundError,
)


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
    - thesis_id(从候选行获取)
    - user_input_id(从候选行获取)
    - strategy_policy_id + version(从 thesis 获取)
    - data_snapshot_id(从 thesis 获取)
    - candidates(完整候选列表)

    这样机构投研可以从候选直接反查到研究请求、投资假设、策略版本和数据快照。
    """
    candidates = service.get_candidates_by_set(candidate_set_id)
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"候选集合不存在: {candidate_set_id}",
        )

    # 从第一个候选获取 thesis_id 和 user_input_id
    first = candidates[0]
    thesis_id = first.get("thesis_id")
    user_input_id = first.get("user_input_id")

    # 从 thesis 获取策略和快照信息
    strategy_policy_id = None
    strategy_policy_version = None
    data_snapshot_id = None
    if thesis_id:
        thesis = service.get_thesis(thesis_id)
        if thesis:
            strategy_policy_id = thesis.get("strategy_policy_id")
            strategy_policy_version = thesis.get("strategy_policy_version")
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
