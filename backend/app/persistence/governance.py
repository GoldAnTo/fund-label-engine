"""治理核心 Repository:策略政策 / 研究请求 / 投资假设 / 候选集合的数据库读写。

职责边界(严格遵守):
    - 只负责 SQL 执行、参数绑定、row->dict、JSON 序列化/反序列化
    - 不含状态机逻辑(由 GovernanceService 负责)
    - 不含业务校验(由 GovernanceService 负责)
    - 不含 CognitionEngine / FastAPI 逻辑

事务设计:
    with repository.transaction() as tx:
        tx.insert_research_input(...)
        tx.insert_thesis(...)
        tx.insert_candidates([...])
        tx.insert_audit_log(...)
    # 正常退出 -> commit;异常 -> rollback + close

    审计写入与业务写入在**同一事务**中,审计失败时整体回滚。
    这与 app.audit.audit_log(独立连接、失败不阻断)不同,是有意为之。

用法:
    repo = GovernanceRepository("/path/to/db.sqlite")
    with repo.transaction() as tx:
        tx.insert_research_input(...)
        tx.insert_thesis(...)
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ============================================================
# JSON 辅助
# ============================================================
def _dumps(value: Any) -> str | None:
    """把 Python 对象序列化为 JSON 字符串,None 保持 None。"""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None) -> Any:
    """把 JSON 字符串反序列化为 Python 对象,None 保持 None。

    坏 JSON 抛 ValueError,不静默返回 None(治理数据不能丢失)。
    """
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"治理数据 JSON 反序列化失败: {exc}") from exc


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ============================================================
# GovernanceTransaction(事务上下文)
# ============================================================
class GovernanceTransaction:
    """单连接事务上下文。

    所有 insert 方法共用同一个 connection,保证:
    1. 外键约束在同一事务中生效
    2. 任一 insert 失败 -> 整体 rollback
    3. 审计日志与业务数据原子写入
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        # 确保外键约束生效
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.row_factory = sqlite3.Row

    def __enter__(self) -> GovernanceTransaction:
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None,
                 exc_tb: Any) -> bool:
        try:
            if exc_type is not None:
                self._conn.rollback()
            else:
                self._conn.commit()
        finally:
            self._conn.close()
        return False  # 不吞异常

    # ----------------------------------------------------------
    # research_inputs
    # ----------------------------------------------------------
    def insert_research_input(
        self,
        *,
        user_input_id: str | None = None,
        input_type: str,
        business_mode: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        actor_role: str,
        actor_id: str | None = None,
        request_source: str,
        raw_text: str,
        structured_intent: dict | None = None,
        target_assets: list | None = None,
        implicit_intent: str | None = None,
        session_id: str | None = None,
        previous_user_input_id: str | None = None,
        as_of_date: str | None = None,
        data_snapshot_id: str | None = None,
        status: str = "received",
    ) -> str:
        """插入一条研究请求。返回 user_input_id。

        外键约束:(strategy_policy_id, strategy_policy_version) 必须已存在;
                  data_snapshot_id 必须已存在(若非 None)。
        """
        uid = user_input_id or _short_id("ri")
        self._conn.execute(
            """
            INSERT INTO research_inputs (
                user_input_id, input_type, business_mode,
                strategy_policy_id, strategy_policy_version,
                actor_role, actor_id, request_source,
                raw_text, structured_intent_json, target_assets_json,
                implicit_intent, session_id, previous_user_input_id,
                as_of_date, data_snapshot_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uid,
                input_type,
                business_mode,
                strategy_policy_id,
                strategy_policy_version,
                actor_role,
                actor_id,
                request_source,
                raw_text,
                _dumps(structured_intent),
                _dumps(target_assets),
                implicit_intent,
                session_id,
                previous_user_input_id,
                as_of_date,
                data_snapshot_id,
                status,
                _now_iso(),
            ),
        )
        return uid

    def update_research_input_status(
        self,
        user_input_id: str,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        """更新研究请求状态(不碰 raw_text,由 trigger 保证不可变)。"""
        if failure_reason:
            self._conn.execute(
                "UPDATE research_inputs SET status = ?, failure_reason = ? WHERE user_input_id = ?",
                (status, failure_reason, user_input_id),
            )
        else:
            self._conn.execute(
                "UPDATE research_inputs SET status = ? WHERE user_input_id = ?",
                (status, user_input_id),
            )

    def get_research_input(self, user_input_id: str) -> dict[str, Any] | None:
        """读取一条研究请求。返回 dict 或 None。"""
        row = self._conn.execute(
            "SELECT * FROM research_inputs WHERE user_input_id = ?",
            (user_input_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_research_input(row)

    # ----------------------------------------------------------
    # investment_theses
    # ----------------------------------------------------------
    def insert_thesis(
        self,
        *,
        thesis_id: str | None = None,
        user_input_id: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        title: str,
        belief_statement: str,
        time_horizon: str | None = None,
        supporting_evidence: list | None = None,
        opposing_evidence: list | None = None,
        key_metrics: dict | None = None,
        candidate_assets: list | None = None,
        valuation_view: dict | None = None,
        catalysts: list | None = None,
        invalidation_conditions: list | None = None,
        previous_thesis_id: str | None = None,
        owner: str = "system",
        as_of_date: str | None = None,
        data_snapshot_id: str | None = None,
        status: str = "draft",
    ) -> str:
        """插入一条投资假设。返回 thesis_id。

        外键约束:user_input_id 必须已存在;
                  (strategy_policy_id, strategy_policy_version) 必须已存在。
        """
        tid = thesis_id or _short_id("th")
        self._conn.execute(
            """
            INSERT INTO investment_theses (
                thesis_id, user_input_id,
                strategy_policy_id, strategy_policy_version,
                title, belief_statement, time_horizon,
                supporting_evidence_json, opposing_evidence_json,
                key_metrics_json, candidate_assets_json, valuation_view_json,
                catalysts_json, invalidation_conditions_json,
                previous_thesis_id, owner,
                as_of_date, data_snapshot_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                user_input_id,
                strategy_policy_id,
                strategy_policy_version,
                title,
                belief_statement,
                time_horizon,
                _dumps(supporting_evidence),
                _dumps(opposing_evidence),
                _dumps(key_metrics),
                _dumps(candidate_assets),
                _dumps(valuation_view),
                _dumps(catalysts),
                _dumps(invalidation_conditions),
                previous_thesis_id,
                owner,
                as_of_date,
                data_snapshot_id,
                status,
                _now_iso(),
            ),
        )
        return tid

    def update_thesis_status(
        self,
        thesis_id: str,
        status: str,
        invalidated_reason: str | None = None,
    ) -> None:
        """更新投资假设状态(核心字段由 trigger 保证不可变)。"""
        if invalidated_reason:
            self._conn.execute(
                "UPDATE investment_theses SET status = ?, invalidated_reason = ? WHERE thesis_id = ?",
                (status, invalidated_reason, thesis_id),
            )
        else:
            self._conn.execute(
                "UPDATE investment_theses SET status = ? WHERE thesis_id = ?",
                (status, thesis_id),
            )

    def get_thesis(self, thesis_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM investment_theses WHERE thesis_id = ?",
            (thesis_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_thesis(row)

    # ----------------------------------------------------------
    # candidate_set_headers(集合头)
    # ----------------------------------------------------------
    def insert_candidate_set_header(
        self,
        *,
        candidate_set_id: str,
        thesis_id: str,
        user_input_id: str,
        data_snapshot_id: str | None,
        source_method_version: str,
        scanned_fund_count: int,
        mapped_candidate_count: int,
        unmapped_due_to_data_count: int,
        unrelated_fund_count: int = 0,
        created_by: str,
    ) -> str:
        """插入 CandidateSet 集合头。返回 candidate_set_id。

        外键约束:thesis_id / user_input_id 必须已存在;
                  data_snapshot_id 必须已存在(若非 None)。
        """
        self._conn.execute(
            """
            INSERT INTO candidate_set_headers (
                candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
                source_method_version, scanned_fund_count, mapped_candidate_count,
                unmapped_due_to_data_count, unrelated_fund_count, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_set_id,
                thesis_id,
                user_input_id,
                data_snapshot_id,
                source_method_version,
                scanned_fund_count,
                mapped_candidate_count,
                unmapped_due_to_data_count,
                unrelated_fund_count,
                created_by,
                _now_iso(),
            ),
        )
        return candidate_set_id

    def get_candidate_set_header(self, candidate_set_id: str) -> dict[str, Any] | None:
        """查询 CandidateSet 集合头。返回 dict 或 None。"""
        row = self._conn.execute(
            "SELECT * FROM candidate_set_headers WHERE candidate_set_id = ?",
            (candidate_set_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_candidate_set_header_by_key(
        self,
        thesis_id: str,
        data_snapshot_id: str | None,
        source_method_version: str,
    ) -> dict[str, Any] | None:
        """按幂等键 (thesis_id, data_snapshot_id, source_method_version) 查询 header。"""
        if data_snapshot_id is None:
            row = self._conn.execute(
                "SELECT * FROM candidate_set_headers "
                "WHERE thesis_id = ? AND data_snapshot_id IS NULL "
                "AND source_method_version = ?",
                (thesis_id, source_method_version),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM candidate_set_headers "
                "WHERE thesis_id = ? AND data_snapshot_id = ? "
                "AND source_method_version = ?",
                (thesis_id, data_snapshot_id, source_method_version),
            ).fetchone()
        return dict(row) if row else None

    def get_strategy_policy(self, policy_id: str, version: int) -> dict[str, Any] | None:
        """查询策略政策,JSON 字段被解析为 Python 对象。"""
        row = self._conn.execute(
            "SELECT * FROM strategy_policies WHERE policy_id = ? AND version = ?",
            (policy_id, version),
        ).fetchone()
        return _row_to_strategy_policy(row) if row else None

    def get_data_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """查询数据快照。返回 dict 或 None。"""
        row = self._conn.execute(
            "SELECT * FROM data_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return dict(row) if row else None

    # ----------------------------------------------------------
    # candidate_sets
    # ----------------------------------------------------------
    def insert_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量插入候选集合。返回 {"candidate_ids": [...], "candidate_set_id": "..."}。

        所有候选共用同一 candidate_set_id(由调用方指定或自动生成)。
        任一插入失败 -> 整个事务 rollback(由调用方在 with 块中处理)。

        0016 后 candidate_sets 有外键引用 candidate_set_headers,
        本方法在写入候选行之前自动创建 legacy header(如果不存在)。

        每个候选 dict 必填字段:
            thesis_id, user_input_id, asset_type, asset_code
        可选字段:
            asset_name, fit_score, evidence_score, valuation_status,
            data_quality_status, conflict_reasons, exclusion_reasons,
            as_of_date, data_snapshot_id, candidate_set_id, candidate_id,
            candidate_evidence
        """
        if not candidates:
            return {"candidate_ids": [], "candidate_set_id": ""}

        # 确定唯一的 candidate_set_id:从第一个候选取或自动生成
        candidate_set_id = candidates[0].get("candidate_set_id") or _short_id("cs")

        # 校验:所有候选的 candidate_set_id 必须一致(或为空)
        for i, c in enumerate(candidates):
            csid = c.get("candidate_set_id")
            if csid is not None and csid != candidate_set_id:
                raise ValueError(
                    f"insert_candidates: 候选 {i} 的 candidate_set_id={csid!r}"
                    f" 与集合 {candidate_set_id!r} 不一致"
                )

        # 0016 后 candidate_sets 外键引用 candidate_set_headers,
        # 写入候选行之前确保 header 存在;不存在则自动创建 legacy header
        header_exists = self._conn.execute(
            "SELECT 1 FROM candidate_set_headers WHERE candidate_set_id = ?",
            (candidate_set_id,),
        ).fetchone()
        if header_exists is None:
            first = candidates[0]
            self._conn.execute(
                """
                INSERT INTO candidate_set_headers (
                    candidate_set_id, thesis_id, user_input_id, data_snapshot_id,
                    source_method_version, scanned_fund_count, mapped_candidate_count,
                    unmapped_due_to_data_count, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_set_id,
                    first["thesis_id"],
                    first["user_input_id"],
                    first.get("data_snapshot_id"),
                    "legacy_governance_v0",
                    len(candidates),
                    len(candidates),
                    0,
                    "system",
                    _now_iso(),
                ),
            )

        ids: list[str] = []
        for c in candidates:
            cid = c.get("candidate_id") or _short_id("can")
            self._conn.execute(
                """
                INSERT INTO candidate_sets (
                    candidate_id, candidate_set_id, thesis_id, user_input_id,
                    asset_type, asset_code, asset_name,
                    fit_score, evidence_score,
                    valuation_status, data_quality_status,
                    portfolio_contribution_json, conflict_reasons_json,
                    exclusion_reasons_json, as_of_date, data_snapshot_id,
                    candidate_status, created_at, candidate_evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    candidate_set_id,  # 强制使用统一的 candidate_set_id
                    c["thesis_id"],
                    c["user_input_id"],
                    c["asset_type"],
                    c["asset_code"],
                    c.get("asset_name"),
                    c.get("fit_score"),
                    c.get("evidence_score"),
                    c.get("valuation_status"),
                    c.get("data_quality_status"),
                    _dumps(c.get("portfolio_contribution")),
                    _dumps(c.get("conflict_reasons", [])),
                    _dumps(c.get("exclusion_reasons", [])),
                    c.get("as_of_date"),
                    c.get("data_snapshot_id"),
                    c.get("candidate_status", "proposed"),
                    _now_iso(),
                    _dumps(c.get("candidate_evidence")),
                ),
            )
            ids.append(cid)
        return {"candidate_ids": ids, "candidate_set_id": candidate_set_id}

    def get_candidates_by_set(self, candidate_set_id: str) -> list[dict[str, Any]]:
        """按 candidate_set_id 查询所有候选。"""
        rows = self._conn.execute(
            "SELECT * FROM candidate_sets WHERE candidate_set_id = ? ORDER BY created_at",
            (candidate_set_id,),
        ).fetchall()
        return [_row_to_candidate(r) for r in rows]

    def get_candidates_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]:
        """按 thesis_id 查询所有候选。"""
        rows = self._conn.execute(
            "SELECT * FROM candidate_sets WHERE thesis_id = ? ORDER BY created_at",
            (thesis_id,),
        ).fetchall()
        return [_row_to_candidate(r) for r in rows]

    # ----------------------------------------------------------
    # audit_log(与业务数据同事务)
    # ----------------------------------------------------------
    def insert_audit_log(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        payload: Any | None = None,
        actor: str = "system",
        run_id: str | None = None,
        source_ip: str | None = None,
    ) -> str:
        """在同一事务中写入审计日志。

        与 app.audit.audit_log 的区别:
        - 本方法不吞异常(失败则整个事务 rollback)
        - 不独立开连接(复用当前事务连接)
        - 支持 source_ip(API 接入后传入)
        """
        audit_id = _short_id("audit")
        self._conn.execute(
            """
            INSERT INTO audit_log (
                audit_id, run_id, actor, action,
                target_type, target_id, payload_json, source_ip, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                run_id,
                actor,
                action,
                target_type,
                target_id,
                _dumps(payload),
                source_ip,
                _now_iso(),
            ),
        )
        return audit_id

    # ----------------------------------------------------------
    # 策略 / 快照 存在性检查
    # ----------------------------------------------------------
    def policy_exists(self, policy_id: str, version: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM strategy_policies WHERE policy_id = ? AND version = ?",
            (policy_id, version),
        ).fetchone()
        return row is not None

    def snapshot_exists(self, snapshot_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM data_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return row is not None

    def research_input_exists(self, user_input_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM research_inputs WHERE user_input_id = ?",
            (user_input_id,),
        ).fetchone()
        return row is not None

    def thesis_exists(self, thesis_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM investment_theses WHERE thesis_id = ?",
            (thesis_id,),
        ).fetchone()
        return row is not None


# ============================================================
# GovernanceRepository(连接工厂)
# ============================================================
class GovernanceRepository:
    """治理核心 Repository:连接工厂 + 事务入口。

    用法:
        repo = GovernanceRepository(db_path)
        with repo.transaction() as tx:
            tx.insert_research_input(...)
            tx.insert_thesis(...)
            tx.insert_audit_log(...)

    查询(只读)也可以不开事务:
        with repo.transaction() as tx:
            ri = tx.get_research_input("ri_xxx")
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def transaction(self) -> GovernanceTransaction:
        """开启一个事务。返回 GovernanceTransaction 上下文管理器。

        正常退出 -> commit;异常 -> rollback + close。
        """
        return GovernanceTransaction(self._connect())

    def policy_exists(self, policy_id: str, version: int) -> bool:
        """无事务查询:策略是否存在。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM strategy_policies WHERE policy_id = ? AND version = ?",
                (policy_id, version),
            ).fetchone()
            return row is not None

    def snapshot_exists(self, snapshot_id: str) -> bool:
        """无事务查询:快照是否存在。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM data_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            return row is not None

    def get_research_input(self, user_input_id: str) -> dict[str, Any] | None:
        """无事务查询:读取一条研究请求。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_inputs WHERE user_input_id = ?",
                (user_input_id,),
            ).fetchone()
            return _row_to_research_input(row) if row else None

    def get_thesis(self, thesis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investment_theses WHERE thesis_id = ?",
                (thesis_id,),
            ).fetchone()
            return _row_to_thesis(row) if row else None

    def get_candidates_by_set(self, candidate_set_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_sets WHERE candidate_set_id = ? ORDER BY created_at",
                (candidate_set_id,),
            ).fetchall()
            return [_row_to_candidate(r) for r in rows]

    def get_candidates_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_sets WHERE thesis_id = ? ORDER BY created_at",
                (thesis_id,),
            ).fetchall()
            return [_row_to_candidate(r) for r in rows]

    def get_candidate_set_header(self, candidate_set_id: str) -> dict[str, Any] | None:
        """无事务查询:读取 CandidateSet 集合头。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_set_headers WHERE candidate_set_id = ?",
                (candidate_set_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_candidate_set_header_by_key(
        self,
        thesis_id: str,
        data_snapshot_id: str | None,
        source_method_version: str,
    ) -> dict[str, Any] | None:
        """无事务查询:按幂等键查询 CandidateSet header。"""
        with self._connect() as conn:
            if data_snapshot_id is None:
                row = conn.execute(
                    "SELECT * FROM candidate_set_headers "
                    "WHERE thesis_id = ? AND data_snapshot_id IS NULL "
                    "AND source_method_version = ?",
                    (thesis_id, source_method_version),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM candidate_set_headers "
                    "WHERE thesis_id = ? AND data_snapshot_id = ? "
                    "AND source_method_version = ?",
                    (thesis_id, data_snapshot_id, source_method_version),
                ).fetchone()
            return dict(row) if row else None

    def get_strategy_policy(self, policy_id: str, version: int) -> dict[str, Any] | None:
        """无事务查询:读取策略政策,JSON 字段被解析为 Python 对象。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_policies WHERE policy_id = ? AND version = ?",
                (policy_id, version),
            ).fetchone()
            return _row_to_strategy_policy(row) if row else None

    def get_data_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """无事务查询:读取数据快照。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM data_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            return dict(row) if row else None


# ============================================================
# row -> dict 转换(反序列化 JSON 字段)
# ============================================================
def _row_to_research_input(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["structured_intent"] = _loads(d.pop("structured_intent_json", None))
    d["target_assets"] = _loads(d.pop("target_assets_json", None))
    return d


def _row_to_thesis(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["supporting_evidence"] = _loads(d.pop("supporting_evidence_json", None))
    d["opposing_evidence"] = _loads(d.pop("opposing_evidence_json", None))
    d["key_metrics"] = _loads(d.pop("key_metrics_json", None))
    d["candidate_assets"] = _loads(d.pop("candidate_assets_json", None))
    d["valuation_view"] = _loads(d.pop("valuation_view_json", None))
    d["catalysts"] = _loads(d.pop("catalysts_json", None))
    d["invalidation_conditions"] = _loads(d.pop("invalidation_conditions_json", None))
    return d


def _row_to_candidate(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["portfolio_contribution"] = _loads(d.pop("portfolio_contribution_json", None))
    d["conflict_reasons"] = _loads(d.pop("conflict_reasons_json", None))
    d["exclusion_reasons"] = _loads(d.pop("exclusion_reasons_json", None))
    d["candidate_evidence"] = _loads(d.pop("candidate_evidence_json", None))
    return d


def _row_to_strategy_policy(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["market_scope"] = _loads(d.pop("market_scope_json", None))
    d["position_limit"] = _loads(d.pop("position_limit_json", None))
    d["allowed_universe"] = _loads(d.pop("allowed_universe_json", None))
    d["excluded_universe"] = _loads(d.pop("excluded_universe_json", None))
    d["valuation_policy"] = _loads(d.pop("valuation_policy_json", None))
    d["monitoring_policy"] = _loads(d.pop("monitoring_policy_json", None))
    d["investment_policy"] = _loads(d.pop("investment_policy_json", None))
    d["candidate_priority"] = _loads(d.pop("candidate_priority_json", None))
    d["fund_recommendation"] = _loads(d.pop("fund_recommendation_json", None))
    return d
