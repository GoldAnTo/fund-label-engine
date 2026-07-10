from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.factors.equity_contributions import EquityStyleContribution
from app.factors.exposure_aggregator import FundFactorExposure
from app.label_engine.engine import DEFAULT_LABEL_DEFINITIONS, EngineResult, RuleConfig

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
    CREATE TABLE IF NOT EXISTS fund_percentile_rank (
        run_id TEXT NOT NULL,
        fund_code TEXT NOT NULL,
        label_code TEXT NOT NULL,
        metric_code TEXT NOT NULL,
        metric_value REAL,
        percentile REAL NOT NULL,
        rank_value INTEGER NOT NULL,
        peer_count INTEGER NOT NULL,
        direction TEXT NOT NULL DEFAULT 'higher_better',
        computed_at TEXT NOT NULL,
        PRIMARY KEY (run_id, fund_code, label_code, metric_code)
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
        data_snapshot_id: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        run_at = datetime.now(UTC).isoformat(timespec="seconds")
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
                "(run_id, run_at, data_as_of, rule_version, status, rule_snapshot_json, data_snapshot_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    run_at,
                    data_as_of,
                    self._rule_version,
                    "running",
                    snapshot_json,
                    data_snapshot_id,
                ),
            )
            conn.commit()
        return run_id

    def write_data_snapshot(
        self,
        snapshot_id: str,
        source_db_path: str,
        source_db_mtime: str | None = None,
        factor_db_path: str | None = None,
        factor_db_mtime: str | None = None,
        nav_date_min: str | None = None,
        nav_date_max: str | None = None,
        fund_count: int = 0,
        factor_count: int = 0,
        benchmark_returns_count: int = 0,
        holding_report_date: str | None = None,
        factor_as_of_date: str | None = None,
    ) -> None:
        """记录数据快照信息，用于审计追溯。"""
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO data_snapshots "
                "(snapshot_id, source_db_path, source_db_mtime, factor_db_path, "
                "factor_db_mtime, nav_date_min, nav_date_max, fund_count, "
                "factor_count, benchmark_returns_count, holding_report_date, "
                "factor_as_of_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    source_db_path,
                    source_db_mtime,
                    factor_db_path,
                    factor_db_mtime,
                    nav_date_min,
                    nav_date_max,
                    fund_count,
                    factor_count,
                    benchmark_returns_count,
                    holding_report_date,
                    factor_as_of_date,
                ),
            )
            conn.commit()

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
        reviewed_at = datetime.now(UTC).isoformat(timespec="seconds")
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

    def set_label_enabled(
        self,
        label_code: str,
        rule_version: str,
        enabled: bool,
        operator: str,
        reason: str | None = None,
        source_ip: str | None = None,
    ) -> dict[str, Any]:
        """启用/禁用某条 label 定义。

        持久化到 label_definitions.enabled，同时写入审计日志。
        返回变更详情（含 change_type: enable/disable/no_change）。
        """
        import json as _json
        import uuid

        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT enabled, label_name FROM label_definitions "
                "WHERE label_code = ? AND rule_version = ?",
                (label_code, rule_version),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"label definition not found: "
                    f"label_code={label_code!r} rule_version={rule_version!r}"
                )
            previous_enabled = bool(row["enabled"])
            new_value = 1 if enabled else 0
            if previous_enabled == enabled:
                return {
                    "label_code": label_code,
                    "label_name": row["label_name"],
                    "rule_version": rule_version,
                    "previous_enabled": previous_enabled,
                    "new_enabled": enabled,
                    "change_type": "no_change",
                    "operator": operator,
                }

            conn.execute(
                "UPDATE label_definitions SET enabled = ? "
                "WHERE label_code = ? AND rule_version = ?",
                (new_value, label_code, rule_version),
            )

            payload = {
                "label_code": label_code,
                "rule_version": rule_version,
                "previous_enabled": previous_enabled,
                "new_enabled": enabled,
                "reason": reason,
            }
            conn.execute(
                "INSERT INTO audit_log "
                "(audit_id, run_id, actor, action, target_type, target_id, "
                "payload_json, source_ip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"label-enable-{uuid.uuid4().hex[:12]}",
                    None,
                    operator,
                    "label_enable_change",
                    "label_definition",
                    f"{label_code}@{rule_version}",
                    _json.dumps(payload, ensure_ascii=False),
                    source_ip,
                ),
            )
            conn.commit()

        return {
            "label_code": label_code,
            "label_name": row["label_name"],
            "rule_version": rule_version,
            "previous_enabled": previous_enabled,
            "new_enabled": enabled,
            "change_type": "enable" if enabled else "disable",
            "operator": operator,
            "reason": reason,
        }

    def write_audit_log(
        self,
        audit_id: str,
        run_id: str | None,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        payload_json: str | None = None,
        source_ip: str | None = None,
    ) -> None:
        """写入一条审计日志。"""
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log "
                "(audit_id, run_id, actor, action, target_type, target_id, "
                "payload_json, source_ip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    audit_id,
                    run_id,
                    actor,
                    action,
                    target_type,
                    target_id,
                    payload_json,
                    source_ip,
                ),
            )
            conn.commit()

    def write_valuation_snapshot(
        self,
        run_id: str,
        fund_code: str,
        as_of_date: str,
        weighted_pe: float | None = None,
        weighted_pb: float | None = None,
        weighted_roe: float | None = None,
        weighted_dividend_yield: float | None = None,
        weighted_val_pct: float | None = None,
        weighted_peg: float | None = None,
        price_in_years: float | None = None,
        position_count: int | None = None,
        top_holding_weight: float | None = None,
    ) -> None:
        """为单只基金写入一行估值快照（监控面板 v1 数据源）。

        Args:
            run_id: 关联的 batch run
            fund_code: 基金代码
            as_of_date: 数据日期（YYYY-MM-DD）
            weighted_pe: 加权 PE
            weighted_pb: 加权 PB
            weighted_roe: 加权 ROE（小数 0.31 表示 31%）
            weighted_dividend_yield: 加权股息率（小数）
            weighted_val_pct: 估值分位（0-100）
            weighted_peg: PEG
            price_in_years: 估值隐含增长年限
            position_count: 持仓股票数
            top_holding_weight: 第一大重仓股权重（小数 0.10 表示 10%）
        """
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO fund_valuation_history "
                "(run_id, fund_code, as_of_date, weighted_pe, weighted_pb, "
                " weighted_roe, weighted_dividend_yield, weighted_val_pct, "
                " weighted_peg, price_in_years, position_count, top_holding_weight) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    fund_code,
                    as_of_date,
                    weighted_pe,
                    weighted_pb,
                    weighted_roe,
                    weighted_dividend_yield,
                    weighted_val_pct,
                    weighted_peg,
                    price_in_years,
                    position_count,
                    top_holding_weight,
                ),
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
        recorded_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO fund_run_failures "
                "(run_id, fund_code, stage, error_type, message, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, fund_code, stage, error_type, message, recorded_at),
            )
            conn.commit()

    def _seed_label_definitions(self, conn: sqlite3.Connection) -> None:
        """种子 label_definitions 行（仅在新行不存在时插入）。

        使用 INSERT OR IGNORE 避免覆盖用户对 enabled 字段的更改。
        如果用户修改了 enabled = 0，下次 ensure_schema() 不会再重置为 1。
        """
        for item in DEFAULT_LABEL_DEFINITIONS:
            thresholds = self._rule_config.thresholds_for(item["label_code"])
            conn.execute(
                "INSERT OR IGNORE INTO label_definitions "
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
