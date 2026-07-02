from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.label_engine.engine import DEFAULT_LABEL_DEFINITIONS, EngineResult, RuleConfig
from app.factors.exposure_aggregator import FundFactorExposure
from app.factors.equity_contributions import EquityStyleContribution


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS label_definitions (
        label_code TEXT NOT NULL,
        label_name TEXT NOT NULL,
        category TEXT NOT NULL,
        fund_types TEXT NOT NULL,
        rule_version TEXT NOT NULL,
        enabled INTEGER NOT NULL,
        description TEXT NOT NULL,
        thresholds_json TEXT,
        PRIMARY KEY (label_code, rule_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS label_runs (
        run_id TEXT PRIMARY KEY,
        run_at TEXT NOT NULL,
        data_as_of TEXT,
        rule_version TEXT NOT NULL,
        status TEXT NOT NULL,
        rule_snapshot_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_label_results (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        label_code TEXT NOT NULL,
        label_name TEXT NOT NULL,
        category TEXT NOT NULL,
        confidence REAL NOT NULL,
        status TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, label_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_label_evidence (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        label_code TEXT NOT NULL,
        metric TEXT NOT NULL,
        value TEXT NOT NULL,
        threshold TEXT NOT NULL,
        source TEXT NOT NULL,
        message TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_values (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        feature_code TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_run_coverage (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        field TEXT NOT NULL,
        present INTEGER NOT NULL,
        review_action TEXT NOT NULL,
        fund_type TEXT,
        PRIMARY KEY (run_id, fund_code, field)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS label_reviews (
        review_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        label_code TEXT NOT NULL,
        decision TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        comment TEXT NOT NULL,
        reviewed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_run_failures (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        stage TEXT NOT NULL,
        error_type TEXT NOT NULL,
        message TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, stage)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS label_calculation_states (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        label_code TEXT NOT NULL,
        label_name TEXT NOT NULL,
        category TEXT NOT NULL,
        state TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        observed TEXT NOT NULL,
        threshold TEXT NOT NULL,
        source TEXT NOT NULL,
        message TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, label_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_classification_results (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        dimension TEXT NOT NULL,
        classification_code TEXT NOT NULL,
        classification_name TEXT NOT NULL,
        confidence REAL NOT NULL,
        reason_code TEXT NOT NULL,
        evidence TEXT NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, dimension)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fund_group_results (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        group_code TEXT NOT NULL,
        group_name TEXT NOT NULL,
        group_type TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        evidence TEXT NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, group_code)
    )
    """,
)


class LabelRunWriter:
    """把一次批量计算的结果写入 SQLite。"""

    def __init__(
        self,
        db_path: str | Path,
        rule_version: str = "v1",
        rule_config: RuleConfig | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._rule_version = rule_version
        self._rule_config = rule_config or RuleConfig()

    def ensure_schema(self) -> None:
        # 1) 先建基线表（CREATE IF NOT EXISTS），保证 migration 中的 ALTER 有目标
        with self._connect() as conn:
            for stmt in SCHEMA_STATEMENTS:
                conn.execute(stmt)
            conn.commit()

        # 2) 跑 migration（已执行的不重复），用于历史 schema 升级 + 新功能预埋
        from app.persistence.migrations_runner import run_migrations

        run_migrations(self._db_path)

        # 3) 兼容兜底：极端老库可能 migration 也漏过，PRAGMA 检查并补列
        with self._connect() as conn:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(label_runs)").fetchall()
            }
            if "rule_snapshot_json" not in cols:
                conn.execute("ALTER TABLE label_runs ADD COLUMN rule_snapshot_json TEXT")
            def_cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(label_definitions)"
                ).fetchall()
            }
            if "thresholds_json" not in def_cols:
                conn.execute(
                    "ALTER TABLE label_definitions ADD COLUMN thresholds_json TEXT"
                )
            self._seed_label_definitions(conn)
            conn.commit()

    def start_run(
        self,
        data_as_of: str | None = None,
        rule_snapshot: Any | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snapshot_json: str | None
        if rule_snapshot is None:
            snapshot_json = None
        elif is_dataclass(rule_snapshot):
            snapshot = asdict(rule_snapshot)
            # frozenset 不可 JSON 序列化，转成 list
            if "disabled_rules" in snapshot and isinstance(
                snapshot["disabled_rules"], frozenset
            ):
                snapshot["disabled_rules"] = sorted(snapshot["disabled_rules"])
            snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        elif isinstance(rule_snapshot, dict):
            snapshot_json = json.dumps(rule_snapshot, ensure_ascii=False)
        else:
            snapshot_json = json.dumps(str(rule_snapshot), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO label_runs "
                "(run_id, run_at, data_as_of, rule_version, status, rule_snapshot_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    run_at,
                    data_as_of,
                    self._rule_version,
                    "running",
                    snapshot_json,
                ),
            )
            conn.commit()
        return run_id

    def write_result(self, run_id: str, result: EngineResult) -> None:
        with self._connect() as conn:
            for label in result.labels:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_label_results "
                    "(run_id, fund_code, label_code, label_name, category, confidence, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        label.label_code,
                        label.label_name,
                        label.category,
                        label.confidence,
                        label.status,
                    ),
                )
            for item in result.evidence:
                conn.execute(
                    "INSERT INTO fund_label_evidence "
                    "(run_id, fund_code, label_code, metric, value, threshold, source, message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        item.label_code,
                        item.metric,
                        str(item.value),
                        str(item.threshold),
                        item.source,
                        item.message,
                    ),
                )
            for field_name, present in result.coverage.items():
                conn.execute(
                    "INSERT OR REPLACE INTO fund_run_coverage "
                    "(run_id, fund_code, field, present, review_action, fund_type) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        field_name,
                        1 if present else 0,
                        result.review_action,
                        result.fund_type or None,
                    ),
                )
            for feature in result.features:
                conn.execute(
                    "INSERT INTO feature_values "
                    "(run_id, fund_code, feature_code, value, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        feature.feature_code,
                        str(feature.value),
                        feature.source,
                    ),
                )
            for item in result.calculations:
                conn.execute(
                    "INSERT OR REPLACE INTO label_calculation_states "
                    "(run_id, fund_code, label_code, label_name, category, state, "
                    " reason_code, observed, threshold, source, message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        item.label_code,
                        item.label_name,
                        item.category,
                        item.state,
                        item.reason_code,
                        str(item.observed),
                        str(item.threshold),
                        item.source,
                        item.message,
                    ),
                )
            for item in result.classifications:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_classification_results "
                    "(run_id, fund_code, dimension, classification_code, "
                    " classification_name, confidence, reason_code, evidence, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        item.dimension,
                        item.classification_code,
                        item.classification_name,
                        item.confidence,
                        item.reason_code,
                        item.evidence,
                        item.source,
                    ),
                )
            for item in result.groups:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_group_results "
                    "(run_id, fund_code, group_code, group_name, group_type, "
                    " reason_code, evidence, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        result.fund_code,
                        item.group_code,
                        item.group_name,
                        item.group_type,
                        item.reason_code,
                        item.evidence,
                        item.source,
                    ),
                )
            conn.commit()

    def write_factor_exposures(
        self,
        exposures: list[FundFactorExposure],
    ) -> None:
        if not exposures:
            return
        with self._connect() as conn:
            for item in exposures:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_factor_exposures "
                    "(fund_code, report_date, factor_code, exposure_value, "
                    " coverage_weight, holding_total_weight, stock_count, "
                    " covered_stock_count, source, as_of_date, computed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.fund_code,
                        item.report_date,
                        item.factor_code,
                        item.exposure_value,
                        item.coverage_weight,
                        item.holding_total_weight,
                        item.stock_count,
                        item.covered_stock_count,
                        item.source,
                        item.as_of_date,
                        item.computed_at,
                    ),
                )
            conn.commit()

    def write_equity_style_contributions(
        self,
        contributions: list[EquityStyleContribution],
    ) -> None:
        if not contributions:
            return
        with self._connect() as conn:
            for item in contributions:
                conn.execute(
                    "INSERT OR REPLACE INTO fund_equity_style_contributions "
                    "(fund_code, report_date, stock_code, stock_name, weight, "
                    " style_code, style_name, matched, contribution_weight, "
                    " factor_values_json, rule_snapshot_json, factor_as_of_date, "
                    " source, computed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.fund_code,
                        item.report_date,
                        item.stock_code,
                        item.stock_name,
                        item.weight,
                        item.style_code,
                        item.style_name,
                        item.matched,
                        item.contribution_weight,
                        item.factor_values_json,
                        item.rule_snapshot_json,
                        item.factor_as_of_date,
                        item.source,
                        item.computed_at,
                    ),
                )
            conn.commit()

    def write_feature(
        self,
        run_id: str,
        fund_code: str,
        feature_code: str,
        value: float | str,
        source: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO feature_values (run_id, fund_code, feature_code, value, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, fund_code, feature_code, str(value), source),
            )
            conn.commit()

    def write_review(
        self,
        run_id: str,
        fund_code: str,
        label_code: str,
        decision: str,
        reviewer: str,
        comment: str,
    ) -> str:
        self.ensure_schema()
        review_id = uuid.uuid4().hex
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO label_reviews "
                "(review_id, run_id, fund_code, label_code, decision, reviewer, comment, reviewed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    review_id,
                    run_id,
                    fund_code,
                    label_code,
                    decision,
                    reviewer,
                    comment,
                    reviewed_at,
                ),
            )
            conn.commit()
        return review_id

    def write_portfolio_role_review(
        self,
        *,
        run_id: str,
        fund_code: str,
        role_code: str,
        decision: str,
        target_bucket: str,
        max_weight_pct: float,
        rationale: str,
        reviewer: str,
    ) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_role_reviews (
                    run_id, fund_code, role_code, decision, target_bucket,
                    max_weight_pct, rationale, reviewer, reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    run_id,
                    fund_code,
                    role_code,
                    decision,
                    target_bucket,
                    max_weight_pct,
                    rationale,
                    reviewer,
                ),
            )
            conn.commit()

    def delete_portfolio_role_review(
        self,
        *,
        run_id: str,
        fund_code: str,
        role_code: str,
    ) -> bool:
        self.ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM portfolio_role_reviews "
                "WHERE run_id = ? AND fund_code = ? AND role_code = ?",
                (run_id, fund_code, role_code),
            )
            conn.commit()
            return cur.rowcount > 0

    def finish_run(self, run_id: str, status: str = "succeeded") -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE label_runs SET status = ? WHERE run_id = ?",
                (status, run_id),
            )
            conn.commit()

    def write_failure(
        self,
        run_id: str,
        fund_code: str,
        stage: str,
        error_type: str,
        message: str,
    ) -> None:
        recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO fund_run_failures "
                "(run_id, fund_code, stage, error_type, message, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, fund_code, stage, error_type, message, recorded_at),
            )
            conn.commit()

    def _seed_label_definitions(self, conn: sqlite3.Connection) -> None:
        for item in DEFAULT_LABEL_DEFINITIONS:
            thresholds = self._rule_config.thresholds_for(item["label_code"])
            conn.execute(
                "INSERT OR REPLACE INTO label_definitions "
                "(label_code, label_name, category, fund_types, rule_version, "
                " enabled, description, thresholds_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["label_code"],
                    item["label_name"],
                    item["category"],
                    item["fund_types"],
                    self._rule_version,
                    1,
                    item["description"],
                    json.dumps(thresholds, ensure_ascii=False) if thresholds else None,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
