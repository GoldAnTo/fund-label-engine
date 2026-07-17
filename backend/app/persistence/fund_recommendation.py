"""基金推荐 Repository:RecommendationRun/Result 的参数化 SQL、JSON round-trip、幂等查询和原子事务。

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
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"基金推荐数据 JSON 反序列化失败: {exc}") from exc


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ============================================================
# FundRecommendationTransaction(事务上下文)
# ============================================================
class FundRecommendationTransaction:
    """单连接事务上下文。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.row_factory = sqlite3.Row

    def __enter__(self) -> FundRecommendationTransaction:
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
        return False

    def insert_run(self, run: Mapping[str, Any]) -> str:
        """插入一条 RecommendationRun。返回 recommendation_run_id。"""
        run_id = run.get("recommendation_run_id") or _short_id("frr")
        self._conn.execute(
            """
            INSERT INTO fund_recommendation_runs (
                recommendation_run_id, candidate_set_id, thesis_id, user_input_id,
                strategy_policy_id, strategy_policy_version, data_snapshot_id,
                recommendation_method_version, result_status, result_type,
                evaluated_candidate_count, recommended_count, tier_counts_json,
                portfolio_json, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run["candidate_set_id"],
                run["thesis_id"],
                run["user_input_id"],
                run["strategy_policy_id"],
                run["strategy_policy_version"],
                run.get("data_snapshot_id"),
                run["recommendation_method_version"],
                run.get("result_status", "completed"),
                run["result_type"],
                run["evaluated_candidate_count"],
                run.get("recommended_count", 0),
                _dumps(run.get("tier_counts")),
                _dumps(run.get("portfolio")),
                run["created_by"],
                _now_iso(),
            ),
        )
        return run_id

    def insert_results(self, results: Sequence[Mapping[str, Any]]) -> None:
        """批量插入 RecommendationResult。"""
        for r in results:
            result_id = r.get("recommendation_result_id") or _short_id("frrr")
            self._conn.execute(
                """
                INSERT INTO fund_recommendation_results (
                    recommendation_result_id, recommendation_run_id, candidate_id,
                    fund_code, fund_name, product_category, recommendation_tier,
                    category_rank, theme_exposure_score, thesis_alignment_score,
                    risk_return_score, fund_quality_score, total_score,
                    recommendation_reasons_json, exclusion_reasons_json,
                    frozen_evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    r["recommendation_run_id"],
                    r["candidate_id"],
                    r["fund_code"],
                    r.get("fund_name"),
                    r["product_category"],
                    r["recommendation_tier"],
                    r.get("category_rank"),
                    r.get("theme_exposure_score"),
                    r.get("thesis_alignment_score"),
                    r.get("risk_return_score"),
                    r.get("fund_quality_score"),
                    r["total_score"],
                    _dumps(r.get("recommendation_reasons")),
                    _dumps(r.get("exclusion_reasons")),
                    _dumps(r.get("frozen_evidence")),
                    _now_iso(),
                ),
            )

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
        """在同一事务中写入审计日志。"""
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

    def get_existing_run_id(
        self,
        *,
        candidate_set_id: str,
        strategy_policy_id: str,
        strategy_policy_version: int,
        data_snapshot_id: str | None,
        recommendation_method_version: str,
    ) -> str | None:
        """按幂等键查询已存在的 recommendation_run_id。"""
        if data_snapshot_id is None:
            row = self._conn.execute(
                """
                SELECT recommendation_run_id FROM fund_recommendation_runs
                WHERE candidate_set_id = ?
                  AND strategy_policy_id = ?
                  AND strategy_policy_version = ?
                  AND data_snapshot_id IS NULL
                  AND recommendation_method_version = ?
                """,
                (
                    candidate_set_id,
                    strategy_policy_id,
                    strategy_policy_version,
                    recommendation_method_version,
                ),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT recommendation_run_id FROM fund_recommendation_runs
                WHERE candidate_set_id = ?
                  AND strategy_policy_id = ?
                  AND strategy_policy_version = ?
                  AND data_snapshot_id = ?
                  AND recommendation_method_version = ?
                """,
                (
                    candidate_set_id,
                    strategy_policy_id,
                    strategy_policy_version,
                    data_snapshot_id,
                    recommendation_method_version,
                ),
            ).fetchone()
        return row["recommendation_run_id"] if row else None


# ============================================================
# FundRecommendationRepository(连接工厂)
# ============================================================
class FundRecommendationRepository:
    """基金推荐 Repository:连接工厂 + 事务入口。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def transaction(self) -> FundRecommendationTransaction:
        return FundRecommendationTransaction(self._connect())

    def get_run(self, recommendation_run_id: str) -> dict[str, Any] | None:
        """读取一条 RecommendationRun。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM fund_recommendation_runs WHERE recommendation_run_id = ?",
                (recommendation_run_id,),
            ).fetchone()
            return _row_to_run(row) if row else None

    def get_results(self, recommendation_run_id: str) -> list[dict[str, Any]]:
        """读取 RecommendationRun 下的所有 RecommendationResult。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fund_recommendation_results "
                "WHERE recommendation_run_id = ? "
                "ORDER BY product_category, category_rank",
                (recommendation_run_id,),
            ).fetchall()
            return [_row_to_result(r) for r in rows]

    def list_runs_by_thesis(self, thesis_id: str) -> list[dict[str, Any]]:
        """按 thesis_id 查询所有 RecommendationRun。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fund_recommendation_runs "
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
        recommendation_method_version: str,
    ) -> str | None:
        """无事务查询:按幂等键查询已存在的 recommendation_run_id。"""
        with self._connect() as conn:
            if data_snapshot_id is None:
                row = conn.execute(
                    """
                    SELECT recommendation_run_id FROM fund_recommendation_runs
                    WHERE candidate_set_id = ?
                      AND strategy_policy_id = ?
                      AND strategy_policy_version = ?
                      AND data_snapshot_id IS NULL
                      AND recommendation_method_version = ?
                    """,
                    (
                        candidate_set_id,
                        strategy_policy_id,
                        strategy_policy_version,
                        recommendation_method_version,
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT recommendation_run_id FROM fund_recommendation_runs
                    WHERE candidate_set_id = ?
                      AND strategy_policy_id = ?
                      AND strategy_policy_version = ?
                      AND data_snapshot_id = ?
                      AND recommendation_method_version = ?
                    """,
                    (
                        candidate_set_id,
                        strategy_policy_id,
                        strategy_policy_version,
                        data_snapshot_id,
                        recommendation_method_version,
                    ),
                ).fetchone()
            return row["recommendation_run_id"] if row else None


# ============================================================
# row -> dict 转换
# ============================================================
def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tier_counts"] = _loads(d.pop("tier_counts_json", None))
    d["portfolio"] = _loads(d.pop("portfolio_json", None))
    return d


def _row_to_result(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["recommendation_reasons"] = _loads(d.pop("recommendation_reasons_json", None))
    d["exclusion_reasons"] = _loads(d.pop("exclusion_reasons_json", None))
    d["frozen_evidence"] = _loads(d.pop("frozen_evidence_json", None))
    return d
