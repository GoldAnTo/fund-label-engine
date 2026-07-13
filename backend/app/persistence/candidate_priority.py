"""候选优先级 Repository:PriorityRun/Result 的参数化 SQL、JSON round-trip、幂等查询和原子事务。

职责边界(严格遵守):
    - 只负责 SQL 执行、参数绑定、row->dict、JSON 序列化/反序列化
    - 不含业务校验(由 Service 层负责)
    - 不含 FastAPI 逻辑

事务设计:
    with repository.transaction() as tx:
        tx.insert_run(run)
        tx.insert_results(results)
        tx.insert_audit_log(...)
    # 正常退出 -> commit;异常 -> rollback + close

    审计写入与业务写入在**同一事务**中,审计失败时整体回滚。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
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

    坏 JSON 抛 ValueError,不静默返回 None(候选优先级数据不能丢失)。
    """
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"候选优先级数据 JSON 反序列化失败: {exc}") from exc


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ============================================================
# CandidatePriorityTransaction(事务上下文)
# ============================================================
class CandidatePriorityTransaction:
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

    def __enter__(self) -> CandidatePriorityTransaction:
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any
    ) -> bool:
        try:
            if exc_type is not None:
                self._conn.rollback()
            else:
                self._conn.commit()
        finally:
            self._conn.close()
        return False  # 不吞异常

    # ----------------------------------------------------------
    # candidate_priority_runs
    # ----------------------------------------------------------
    def insert_run(self, run: Mapping[str, Any]) -> str:
        """插入一条 PriorityRun。返回 priority_run_id。

        run 必填字段:
            candidate_set_id, thesis_id, user_input_id,
            strategy_policy_id, strategy_policy_version,
            ranking_method_version, result_type,
            evaluated_candidate_count, eligible_candidate_count, created_by
        可选字段:
            priority_run_id(默认自动生成),
            data_snapshot_id, result_status(默认 'completed'),
            scanned_fund_count, mapped_candidate_count, unmapped_due_to_data_count,
            tier_counts(dict -> tier_counts_json)
        """
        run_id = run.get("priority_run_id") or _short_id("cpr")
        self._conn.execute(
            """
            INSERT INTO candidate_priority_runs (
                priority_run_id, candidate_set_id, thesis_id, user_input_id,
                strategy_policy_id, strategy_policy_version, data_snapshot_id,
                ranking_method_version, result_status, result_type,
                scanned_fund_count, mapped_candidate_count, unmapped_due_to_data_count,
                evaluated_candidate_count, eligible_candidate_count, tier_counts_json,
                created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run["candidate_set_id"],
                run["thesis_id"],
                run["user_input_id"],
                run["strategy_policy_id"],
                run["strategy_policy_version"],
                run.get("data_snapshot_id"),
                run["ranking_method_version"],
                run.get("result_status", "completed"),
                run["result_type"],
                run.get("scanned_fund_count"),
                run.get("mapped_candidate_count"),
                run.get("unmapped_due_to_data_count"),
                run["evaluated_candidate_count"],
                run["eligible_candidate_count"],
                _dumps(run.get("tier_counts")),
                run["created_by"],
                _now_iso(),
            ),
        )
        return run_id

    # ----------------------------------------------------------
    # candidate_priority_results
    # ----------------------------------------------------------
    def insert_results(self, results: Sequence[Mapping[str, Any]]) -> None:
        """批量插入 PriorityResult。

        任一插入失败 -> 整个事务 rollback(由调用方在 with 块中处理)。

        每个 result 必填字段:
            priority_run_id, candidate_id, fund_code,
            eligibility_status, priority_tier
        可选字段:
            priority_result_id(默认自动生成),
            fund_name, priority_rank,
            matched_holding_weight, disclosed_holding_weight, normalized_match_pct,
            fit_score, evidence_score,
            holdings_truth_status, valuation_status, data_quality_status,
            holding_report_date,
            dimension_results(dict -> dimension_results_json),
            priority_reasons(list -> priority_reasons_json),
            exclusion_reasons(list -> exclusion_reasons_json)
        """
        for r in results:
            result_id = r.get("priority_result_id") or _short_id("cprr")
            self._conn.execute(
                """
                INSERT INTO candidate_priority_results (
                    priority_result_id, priority_run_id, candidate_id,
                    fund_code, fund_name, eligibility_status, priority_tier,
                    priority_rank, matched_holding_weight, disclosed_holding_weight,
                    normalized_match_pct, fit_score, evidence_score,
                    holdings_truth_status, valuation_status, data_quality_status,
                    holding_report_date, dimension_results_json,
                    priority_reasons_json, exclusion_reasons_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    r["priority_run_id"],
                    r["candidate_id"],
                    r["fund_code"],
                    r.get("fund_name"),
                    r["eligibility_status"],
                    r["priority_tier"],
                    r.get("priority_rank"),
                    r.get("matched_holding_weight"),
                    r.get("disclosed_holding_weight"),
                    r.get("normalized_match_pct"),
                    r.get("fit_score"),
                    r.get("evidence_score"),
                    r.get("holdings_truth_status"),
                    r.get("valuation_status"),
                    r.get("data_quality_status"),
                    r.get("holding_report_date"),
                    _dumps(r.get("dimension_results")),
                    _dumps(r.get("priority_reasons")),
                    _dumps(r.get("exclusion_reasons")),
                    _now_iso(),
                ),
            )

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
    # 幂等查询
    # ----------------------------------------------------------
    def get_existing_run_id(
        self,
        *,
        candidate_set_id: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        data_snapshot_id: str | None,
        ranking_method_version: str,
    ) -> str | None:
        """按幂等键查询已存在的 priority_run_id。

        幂等键:(candidate_set_id, strategy_policy_id, strategy_policy_version,
               data_snapshot_id, ranking_method_version)

        data_snapshot_id 可能为 None,SQL 需要处理 IS NULL。
        """
        if data_snapshot_id is None:
            row = self._conn.execute(
                """
                SELECT priority_run_id FROM candidate_priority_runs
                WHERE candidate_set_id = ?
                  AND strategy_policy_id = ?
                  AND strategy_policy_version = ?
                  AND data_snapshot_id IS NULL
                  AND ranking_method_version = ?
                """,
                (
                    candidate_set_id,
                    strategy_policy_id,
                    strategy_policy_version,
                    ranking_method_version,
                ),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT priority_run_id FROM candidate_priority_runs
                WHERE candidate_set_id = ?
                  AND strategy_policy_id = ?
                  AND strategy_policy_version = ?
                  AND data_snapshot_id = ?
                  AND ranking_method_version = ?
                """,
                (
                    candidate_set_id,
                    strategy_policy_id,
                    strategy_policy_version,
                    data_snapshot_id,
                    ranking_method_version,
                ),
            ).fetchone()
        return row["priority_run_id"] if row else None


# ============================================================
# CandidatePriorityRepository(连接工厂)
# ============================================================
class CandidatePriorityRepository:
    """候选优先级 Repository:连接工厂 + 事务入口。

    用法:
        repo = CandidatePriorityRepository(db_path)
        with repo.transaction() as tx:
            tx.insert_run(run)
            tx.insert_results(results)
            tx.insert_audit_log(...)

    查询(只读)也可以不开事务:
        run = repo.get_run("cpr_xxx")
        results = repo.get_results("cpr_xxx")
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def transaction(self) -> CandidatePriorityTransaction:
        """开启一个事务。返回 CandidatePriorityTransaction 上下文管理器。

        正常退出 -> commit;异常 -> rollback + close。
        """
        return CandidatePriorityTransaction(self._connect())

    def get_run(self, priority_run_id: str) -> dict[str, Any] | None:
        """无事务查询:读取一条 PriorityRun。JSON 字段被解析为 Python 对象。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_priority_runs WHERE priority_run_id = ?",
                (priority_run_id,),
            ).fetchone()
            return _row_to_run(row) if row else None

    def get_results(self, priority_run_id: str) -> list[dict[str, Any]]:
        """无事务查询:读取 PriorityRun 下的所有 PriorityResult。

        JSON 字段被解析:dimension_results_json -> dimension_results,
        priority_reasons_json -> priority_reasons,
        exclusion_reasons_json -> exclusion_reasons。
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_priority_results "
                "WHERE priority_run_id = ? ORDER BY priority_rank",
                (priority_run_id,),
            ).fetchall()
            return [_row_to_result(r) for r in rows]

    def list_runs_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]:
        """无事务查询:按 thesis_id 查询所有 PriorityRun,按 created_at DESC 排序。

        JSON 字段 tier_counts_json 被解析为 tier_counts。
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_priority_runs "
                "WHERE thesis_id = ? ORDER BY created_at DESC",
                (thesis_id,),
            ).fetchall()
            return [_row_to_run(r) for r in rows]

    def get_existing_run_id(
        self,
        *,
        candidate_set_id: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        data_snapshot_id: str | None,
        ranking_method_version: str,
    ) -> str | None:
        """无事务查询:按幂等键查询已存在的 priority_run_id。

        幂等键:(candidate_set_id, strategy_policy_id, strategy_policy_version,
               data_snapshot_id, ranking_method_version)

        data_snapshot_id 可能为 None,SQL 需要处理 IS NULL。
        """
        with self._connect() as conn:
            if data_snapshot_id is None:
                row = conn.execute(
                    """
                    SELECT priority_run_id FROM candidate_priority_runs
                    WHERE candidate_set_id = ?
                      AND strategy_policy_id = ?
                      AND strategy_policy_version = ?
                      AND data_snapshot_id IS NULL
                      AND ranking_method_version = ?
                    """,
                    (
                        candidate_set_id,
                        strategy_policy_id,
                        strategy_policy_version,
                        ranking_method_version,
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT priority_run_id FROM candidate_priority_runs
                    WHERE candidate_set_id = ?
                      AND strategy_policy_id = ?
                      AND strategy_policy_version = ?
                      AND data_snapshot_id = ?
                      AND ranking_method_version = ?
                    """,
                    (
                        candidate_set_id,
                        strategy_policy_id,
                        strategy_policy_version,
                        data_snapshot_id,
                        ranking_method_version,
                    ),
                ).fetchone()
            return row["priority_run_id"] if row else None


# ============================================================
# row -> dict 转换(反序列化 JSON 字段)
# ============================================================
def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tier_counts"] = _loads(d.pop("tier_counts_json", None))
    return d


def _row_to_result(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["dimension_results"] = _loads(d.pop("dimension_results_json", None))
    d["priority_reasons"] = _loads(d.pop("priority_reasons_json", None))
    d["exclusion_reasons"] = _loads(d.pop("exclusion_reasons_json", None))
    return d
