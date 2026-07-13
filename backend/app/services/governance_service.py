"""治理核心 Service:业务校验、状态机、审计编排。

职责边界(严格遵守):
    - 状态机和合法状态迁移
    - policy / snapshot / 上游实体存在性校验
    - actor_id、角色和业务模式校验
    - 幂等键和重复请求处理
    - 修订关系 previous_user_input_id / previous_thesis_id
    - 审计事件名称和审计载荷
    - 事务提交、回滚和领域异常转换

    **不**包含:
    - SQL 执行(由 GovernanceRepository 负责)
    - CognitionEngine / FastAPI 逻辑
    - 前端 / API 路由

用法:
    service = GovernanceService(repository)
    result = service.create_research_input(
        input_type="philosophy",
        raw_text="我看好消费白马",
        actor_role="researcher",
        actor_id=" researcher_001",
        ...
    )
"""
from __future__ import annotations

from typing import Any

from app.persistence.governance import GovernanceRepository


# ============================================================
# 领域异常
# ============================================================
class GovernanceError(Exception):
    """治理业务错误基类。"""


class PolicyNotFoundError(GovernanceError):
    """策略政策不存在。"""


class SnapshotNotFoundError(GovernanceError):
    """数据快照不存在。"""


class ResearchInputNotFoundError(GovernanceError):
    """研究请求不存在。"""


class InvalidStatusTransitionError(GovernanceError):
    """非法状态迁移。"""


class DuplicateResearchInputError(GovernanceError):
    """重复研究请求(幂等键冲突)。"""


class InvalidActorError(GovernanceError):
    """角色或身份不合法。"""


# ============================================================
# 合法状态迁移表
# ============================================================
_RESEARCH_INPUT_TRANSITIONS: dict[str, set[str]] = {
    "received": {"parsed", "failed"},
    "parsed": {"expanded", "failed"},
    "expanded": {"closed"},
    "closed": set(),  # 终态
    "failed": {"received"},  # 允许重试(重新输入)
}

_THESIS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"researching", "closed"},
    "researching": {"validated", "closed"},
    "validated": {"approved", "closed"},
    "approved": {"watching", "invalidated", "closed"},
    "watching": {"approved", "invalidated", "closed"},
    "invalidated": {"closed"},
    "closed": set(),  # 终态
}

_CANDIDATE_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"screening", "rejected"},
    "screening": {"reviewed", "rejected"},
    "reviewed": {"approved", "rejected"},
    "approved": set(),  # 终态
    "rejected": set(),  # 终态
}

_VALID_ACTOR_ROLES = {"researcher", "portfolio_manager", "risk", "product"}
_VALID_BUSINESS_MODES = {"private_strategy", "fof"}
_VALID_INPUT_TYPES = {"philosophy", "industry", "target", "manager", "strategy"}
_VALID_REQUEST_SOURCES = {
    "research_meeting", "ad_hoc_research", "portfolio_review", "risk_review",
}


# ============================================================
# GovernanceService
# ============================================================
class GovernanceService:
    """治理核心 Service。

    所有写操作通过 Repository 的 transaction() 保证原子性。
    Service 负责:
    1. 校验入参(角色、模式、状态迁移)
    2. 校验上游存在性(policy / snapshot / research_input)
    3. 幂等处理(重复 user_input_id 检测)
    4. 修订关系(previous_user_input_id)
    5. 审计写入(与业务数据同事务)
    6. 领域异常转换(把 sqlite3.IntegrityError 转成有语义的 GovernanceError)
    """

    def __init__(self, repository: GovernanceRepository) -> None:
        self._repo = repository

    # ----------------------------------------------------------
    # ResearchInput
    # ----------------------------------------------------------
    def create_research_input(
        self,
        *,
        input_type: str,
        business_mode: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        actor_role: str,
        actor_id: str,
        request_source: str,
        raw_text: str,
        user_input_id: str | None = None,
        structured_intent: dict | None = None,
        target_assets: list | None = None,
        implicit_intent: str | None = None,
        session_id: str | None = None,
        previous_user_input_id: str | None = None,
        as_of_date: str | None = None,
        data_snapshot_id: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """创建研究请求。

        校验:
        1. input_type / business_mode / actor_role / request_source 合法
        2. actor_id 非空(机构内部必须保留身份)
        3. (strategy_policy_id, version) 存在
        4. data_snapshot_id 存在(若非 None)
        5. previous_user_input_id 存在(若非 None,修订关系)
        6. raw_text 非空

        审计:
        - action: create_research_input
        - target: research_input / {user_input_id}

        返回:
            {"user_input_id": ..., "status": "received"}
        """
        # 1. 入参校验
        self._validate_input_type(input_type)
        self._validate_business_mode(business_mode)
        self._validate_actor_role(actor_role)
        self._validate_request_source(request_source)
        if not actor_id or not actor_id.strip():
            raise InvalidActorError("actor_id 不能为空(机构内部必须保留身份)")
        if not raw_text or not raw_text.strip():
            raise GovernanceError("raw_text 不能为空")

        # 2. 上游存在性校验
        with self._repo.transaction() as tx:
            if not tx.policy_exists(strategy_policy_id, strategy_policy_version):
                raise PolicyNotFoundError(
                    f"策略不存在: {strategy_policy_id} v{strategy_policy_version}"
                )
            if data_snapshot_id and not tx.snapshot_exists(data_snapshot_id):
                raise SnapshotNotFoundError(f"快照不存在: {data_snapshot_id}")
            if previous_user_input_id and not tx.research_input_exists(previous_user_input_id):
                raise ResearchInputNotFoundError(
                    f"修订目标不存在: {previous_user_input_id}"
                )

            # 3. 写入(Repository 处理 SQL + 外键)
            import sqlite3

            try:
                uid = tx.insert_research_input(
                    user_input_id=user_input_id,
                    input_type=input_type,
                    business_mode=business_mode,
                    strategy_policy_id=strategy_policy_id,
                    strategy_policy_version=strategy_policy_version,
                    actor_role=actor_role,
                    actor_id=actor_id,
                    request_source=request_source,
                    raw_text=raw_text,
                    structured_intent=structured_intent,
                    target_assets=target_assets,
                    implicit_intent=implicit_intent,
                    session_id=session_id,
                    previous_user_input_id=previous_user_input_id,
                    as_of_date=as_of_date,
                    data_snapshot_id=data_snapshot_id,
                    status="received",
                )
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc):
                    raise DuplicateResearchInputError(
                        f"研究请求已存在: {uid if 'uid' in dir() else 'unknown'}"
                    ) from exc
                raise GovernanceError(f"数据库约束失败: {exc}") from exc

            # 4. 审计(同事务)
            tx.insert_audit_log(
                action="create_research_input",
                target_type="research_input",
                target_id=uid,
                payload={
                    "input_type": input_type,
                    "business_mode": business_mode,
                    "actor_role": actor_role,
                    "actor_id": actor_id,
                    "raw_text_preview": raw_text[:100],
                },
                actor=actor_id,
                source_ip=source_ip,
            )

        return {"user_input_id": uid, "status": "received"}

    def transition_research_input(
        self,
        *,
        user_input_id: str,
        to_status: str,
        actor_id: str,
        failure_reason: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """迁移研究请求状态。

        校验:
        1. research_input 存在
        2. 当前状态 -> to_status 是合法迁移
        3. raw_text 不可变(trigger 保证;Service 不碰 raw_text)
        """
        ri = self._repo.get_research_input(user_input_id)
        if ri is None:
            raise ResearchInputNotFoundError(f"研究请求不存在: {user_input_id}")

        self._validate_actor_id(actor_id)
        current = ri["status"]
        self._validate_transition(
            _RESEARCH_INPUT_TRANSITIONS, current, to_status, "research_input"
        )

        import sqlite3

        with self._repo.transaction() as tx:
            try:
                tx.update_research_input_status(
                    user_input_id, to_status, failure_reason
                )
            except sqlite3.IntegrityError as exc:
                raise GovernanceError(f"状态迁移失败: {exc}") from exc

            tx.insert_audit_log(
                action="transition_research_input",
                target_type="research_input",
                target_id=user_input_id,
                payload={"from": current, "to": to_status, "failure_reason": failure_reason},
                actor=actor_id,
                source_ip=source_ip,
            )

        return {"user_input_id": user_input_id, "status": to_status}

    # ----------------------------------------------------------
    # InvestmentThesis
    # ----------------------------------------------------------
    def create_thesis(
        self,
        *,
        user_input_id: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        title: str,
        belief_statement: str,
        actor_id: str,
        time_horizon: str | None = None,
        supporting_evidence: list | None = None,
        opposing_evidence: list | None = None,
        key_metrics: dict | None = None,
        candidate_assets: list | None = None,
        valuation_view: dict | None = None,
        catalysts: list | None = None,
        invalidation_conditions: list | None = None,
        previous_thesis_id: str | None = None,
        owner: str | None = None,
        as_of_date: str | None = None,
        data_snapshot_id: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """创建投资假设。

        校验:
        1. user_input_id 存在
        2. (strategy_policy_id, version) 存在
        3. data_snapshot_id 存在(若非 None)
        4. previous_thesis_id 存在(若非 None,修订关系)
        5. title / belief_statement 非空
        6. actor_id 非空
        """
        if not title or not title.strip():
            raise GovernanceError("title 不能为空")
        if not belief_statement or not belief_statement.strip():
            raise GovernanceError("belief_statement 不能为空")
        self._validate_actor_id(actor_id)

        with self._repo.transaction() as tx:
            if not tx.research_input_exists(user_input_id):
                raise ResearchInputNotFoundError(f"研究请求不存在: {user_input_id}")
            if not tx.policy_exists(strategy_policy_id, strategy_policy_version):
                raise PolicyNotFoundError(
                    f"策略不存在: {strategy_policy_id} v{strategy_policy_version}"
                )
            if data_snapshot_id and not tx.snapshot_exists(data_snapshot_id):
                raise SnapshotNotFoundError(f"快照不存在: {data_snapshot_id}")
            if previous_thesis_id and not tx.thesis_exists(previous_thesis_id):
                raise GovernanceError(f"修订目标 thesis 不存在: {previous_thesis_id}")

            import sqlite3

            try:
                tid = tx.insert_thesis(
                    user_input_id=user_input_id,
                    strategy_policy_id=strategy_policy_id,
                    strategy_policy_version=strategy_policy_version,
                    title=title,
                    belief_statement=belief_statement,
                    time_horizon=time_horizon,
                    supporting_evidence=supporting_evidence,
                    opposing_evidence=opposing_evidence,
                    key_metrics=key_metrics,
                    candidate_assets=candidate_assets,
                    valuation_view=valuation_view,
                    catalysts=catalysts,
                    invalidation_conditions=invalidation_conditions,
                    previous_thesis_id=previous_thesis_id,
                    owner=owner or actor_id,
                    as_of_date=as_of_date,
                    data_snapshot_id=data_snapshot_id,
                    status="draft",
                )
            except sqlite3.IntegrityError as exc:
                raise GovernanceError(f"数据库约束失败: {exc}") from exc

            tx.insert_audit_log(
                action="create_thesis",
                target_type="thesis",
                target_id=tid,
                payload={
                    "user_input_id": user_input_id,
                    "title": title,
                    "belief_preview": belief_statement[:100],
                },
                actor=actor_id,
                source_ip=source_ip,
            )

        return {"thesis_id": tid, "status": "draft"}

    def transition_thesis(
        self,
        *,
        thesis_id: str,
        to_status: str,
        actor_id: str,
        invalidated_reason: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """迁移投资假设状态。

        校验:
        1. thesis 存在
        2. 当前状态 -> to_status 是合法迁移
        3. 核心 belief_statement / as_of_date / data_snapshot_id 不可变
           (trigger 保证;Service 不碰这些字段)
        """
        th = self._repo.get_thesis(thesis_id)
        if th is None:
            raise GovernanceError(f"投资假设不存在: {thesis_id}")

        self._validate_actor_id(actor_id)
        current = th["status"]
        self._validate_transition(
            _THESIS_TRANSITIONS, current, to_status, "thesis"
        )

        import sqlite3

        with self._repo.transaction() as tx:
            try:
                tx.update_thesis_status(
                    thesis_id, to_status, invalidated_reason
                )
            except sqlite3.IntegrityError as exc:
                if "immutable" in str(exc):
                    raise GovernanceError(
                        f"不可变字段被修改(应由 trigger 拦截): {exc}"
                    ) from exc
                raise GovernanceError(f"状态迁移失败: {exc}") from exc

            tx.insert_audit_log(
                action="transition_thesis",
                target_type="thesis",
                target_id=thesis_id,
                payload={"from": current, "to": to_status, "invalidated_reason": invalidated_reason},
                actor=actor_id,
                source_ip=source_ip,
            )

        return {"thesis_id": thesis_id, "status": to_status}

    # ----------------------------------------------------------
    # CandidateSet
    # ----------------------------------------------------------
    def create_candidates(
        self,
        *,
        thesis_id: str,
        user_input_id: str,
        candidates: list[dict[str, Any]],
        actor_id: str,
        candidate_set_id: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """创建候选集合。

        校验:
        1. thesis 存在
        2. user_input_id 存在
        3. 每个候选有 thesis_id / user_input_id / asset_type / asset_code
        4. 所有候选共用同一 candidate_set_id(Repository 强制)
        5. actor_id 非空
        """
        th = self._repo.get_thesis(thesis_id)
        if th is None:
            raise GovernanceError(f"投资假设不存在: {thesis_id}")

        if not candidates:
            raise GovernanceError("候选列表不能为空")

        self._validate_actor_id(actor_id)

        # 强制校验:每个候选的 thesis_id 和 user_input_id 必须与参数一致
        for i, c in enumerate(candidates):
            c_thesis = c.get("thesis_id")
            if c_thesis is not None and c_thesis != thesis_id:
                raise GovernanceError(
                    f"候选 {i} 的 thesis_id={c_thesis!r} 与参数 {thesis_id!r} 不一致"
                )
            c_uid = c.get("user_input_id")
            if c_uid is not None and c_uid != user_input_id:
                raise GovernanceError(
                    f"候选 {i} 的 user_input_id={c_uid!r} 与参数 {user_input_id!r} 不一致"
                )
            # 强制设为参数值(不允许调用方传错)
            c["thesis_id"] = thesis_id
            c["user_input_id"] = user_input_id
            if candidate_set_id:
                c["candidate_set_id"] = candidate_set_id
            # 必填字段检查
            for field in ("asset_type", "asset_code"):
                if not c.get(field):
                    raise GovernanceError(f"候选 {i} 缺少必填字段: {field}")

        with self._repo.transaction() as tx:
            if not tx.thesis_exists(thesis_id):
                raise GovernanceError(f"投资假设不存在: {thesis_id}")
            if not tx.research_input_exists(user_input_id):
                raise ResearchInputNotFoundError(f"研究请求不存在: {user_input_id}")

            import sqlite3

            try:
                result = tx.insert_candidates(candidates)
            except sqlite3.IntegrityError as exc:
                raise GovernanceError(f"候选写入失败: {exc}") from exc
            except ValueError as exc:
                raise GovernanceError(f"候选集合 ID 不一致: {exc}") from exc

            cs_id = result["candidate_set_id"]
            tx.insert_audit_log(
                action="create_candidates",
                target_type="candidate_set",
                target_id=cs_id,
                payload={
                    "thesis_id": thesis_id,
                    "candidate_count": len(result["candidate_ids"]),
                },
                actor=actor_id,
                source_ip=source_ip,
            )

        return {
            "candidate_ids": result["candidate_ids"],
            "candidate_set_id": cs_id,
            "count": len(result["candidate_ids"]),
        }

    # ----------------------------------------------------------
    # 查询代理(委托 Repository)
    # ----------------------------------------------------------
    def get_research_input(self, user_input_id: str) -> dict[str, Any] | None:
        return self._repo.get_research_input(user_input_id)

    def get_thesis(self, thesis_id: str) -> dict[str, Any] | None:
        return self._repo.get_thesis(thesis_id)

    def get_candidates_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]:
        return self._repo.get_candidates_by_thesis(thesis_id)

    def get_candidates_by_set(self, candidate_set_id: str) -> list[dict[str, Any]]:
        return self._repo.get_candidates_by_set(candidate_set_id)

    def get_candidate_set_header(self, candidate_set_id: str) -> dict[str, Any] | None:
        return self._repo.get_candidate_set_header(candidate_set_id)

    # ----------------------------------------------------------
    # 校验辅助
    # ----------------------------------------------------------
    @staticmethod
    def _validate_actor_id(actor_id: str) -> None:
        """校验 actor_id 非空(机构内部必须保留身份)。"""
        if not actor_id or not actor_id.strip():
            raise InvalidActorError("actor_id 不能为空(机构内部必须保留身份)")

    @staticmethod
    def _validate_input_type(input_type: str) -> None:
        if input_type not in _VALID_INPUT_TYPES:
            raise GovernanceError(
                f"input_type 不合法: {input_type}, 合法值: {_VALID_INPUT_TYPES}"
            )

    @staticmethod
    def _validate_business_mode(business_mode: str) -> None:
        if business_mode not in _VALID_BUSINESS_MODES:
            raise GovernanceError(
                f"business_mode 不合法: {business_mode}, 合法值: {_VALID_BUSINESS_MODES}"
            )

    @staticmethod
    def _validate_actor_role(actor_role: str) -> None:
        if actor_role not in _VALID_ACTOR_ROLES:
            raise GovernanceError(
                f"actor_role 不合法: {actor_role}, 合法值: {_VALID_ACTOR_ROLES}"
            )

    @staticmethod
    def _validate_request_source(request_source: str) -> None:
        if request_source not in _VALID_REQUEST_SOURCES:
            raise GovernanceError(
                f"request_source 不合法: {request_source}, 合法值: {_VALID_REQUEST_SOURCES}"
            )

    @staticmethod
    def _validate_transition(
        table: dict[str, set[str]],
        current: str,
        to_status: str,
        entity_name: str,
    ) -> None:
        if current not in table:
            raise InvalidStatusTransitionError(
                f"{entity_name} 当前状态 {current!r} 不在状态表中"
            )
        allowed = table[current]
        if to_status not in allowed:
            raise InvalidStatusTransitionError(
                f"{entity_name} 不允许从 {current!r} 迁移到 {to_status!r},"
                f"合法目标: {allowed or '(终态,不可迁移)'}"
            )
