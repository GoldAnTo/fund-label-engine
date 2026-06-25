from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class LabelRunReader:
    """从 SQLite 读取已经落库的标签批次结果。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, run_at, data_as_of, rule_version, status "
                "FROM label_runs ORDER BY run_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id, run_at, data_as_of, rule_version, status, rule_snapshot_json "
                "FROM label_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            run = dict(row)
            failure_count = conn.execute(
                "SELECT COUNT(*) AS c FROM fund_run_failures WHERE run_id = ?",
                (run_id,),
            ).fetchone()["c"]
        run["failure_count"] = failure_count
        snapshot_raw = run.pop("rule_snapshot_json", None)
        run["rule_snapshot"] = json.loads(snapshot_raw) if snapshot_raw else None
        return run

    def latest_succeeded_run_id(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id FROM label_runs "
                "WHERE status = 'succeeded' "
                "ORDER BY run_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return row["run_id"] if row else None

    def get_fund_labels(self, run_id: str, fund_code: str) -> dict[str, Any] | None:
        """返回单只基金在一次 run 内的全部标签、证据、coverage。找不到记录返回 None。"""
        with self._connect() as conn:
            label_rows = conn.execute(
                "SELECT label_code, label_name, category, confidence, status "
                "FROM fund_label_results "
                "WHERE run_id = ? AND fund_code = ? "
                "ORDER BY label_code",
                (run_id, fund_code),
            ).fetchall()
            if not label_rows:
                return None

            evidence_rows = conn.execute(
                "SELECT label_code, metric, value, threshold, source, message "
                "FROM fund_label_evidence "
                "WHERE run_id = ? AND fund_code = ? "
                "ORDER BY label_code",
                (run_id, fund_code),
            ).fetchall()

            coverage_rows = conn.execute(
                "SELECT field, present, review_action "
                "FROM fund_run_coverage "
                "WHERE run_id = ? AND fund_code = ?",
                (run_id, fund_code),
            ).fetchall()

        review_action = (
            coverage_rows[0]["review_action"] if coverage_rows else "observe"
        )
        coverage = {row["field"]: bool(row["present"]) for row in coverage_rows}

        return {
            "run_id": run_id,
            "fund_code": fund_code,
            "review_action": review_action,
            "coverage": coverage,
            "labels": [dict(row) for row in label_rows],
            "evidence": [dict(row) for row in evidence_rows],
            "features": self.list_features(run_id, fund_code),
            "calculations": self.list_calculations(run_id, fund_code),
            "reviews": self.list_reviews(run_id, fund_code),
        }

    def list_run_funds(self, run_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT fund_code FROM fund_label_results "
                "WHERE run_id = ? ORDER BY fund_code",
                (run_id,),
            ).fetchall()
        return [row["fund_code"] for row in rows]

    def list_features(self, run_id: str, fund_code: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT feature_code, value, source "
                    "FROM feature_values "
                    "WHERE run_id = ? AND fund_code = ? "
                    "ORDER BY feature_code",
                    (run_id, fund_code),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def list_calculations(self, run_id: str, fund_code: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT label_code, label_name, category, state, reason_code, "
                    "observed, threshold, source, message "
                    "FROM label_calculation_states "
                    "WHERE run_id = ? AND fund_code = ? "
                    "ORDER BY label_code",
                    (run_id, fund_code),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def list_reviews(self, run_id: str, fund_code: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT review_id, run_id, fund_code, label_code, decision, reviewer, comment "
                    "FROM label_reviews "
                    "WHERE run_id = ? AND fund_code = ? "
                    "ORDER BY reviewed_at, rowid",
                    (run_id, fund_code),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def get_fund_report(self, run_id: str, fund_code: str) -> dict[str, Any] | None:
        payload = self.get_fund_labels(run_id, fund_code)
        if payload is None:
            return None

        missing_fields = [
            field for field, present in payload["coverage"].items() if not present
        ]
        payload["missing_fields"] = missing_fields
        payload["summary"] = {
            "label_count": len(payload["labels"]),
            "feature_count": len(payload["features"]),
            "evidence_count": len(payload["evidence"]),
            "calculation_count": len(payload["calculations"]),
            "missing_field_count": len(missing_fields),
            "review_count": len(payload["reviews"]),
            "review_action": payload["review_action"],
        }
        return payload

    def search_run_funds(
        self,
        run_id: str,
        fund_code: str | None = None,
        label_code: str | None = None,
        review_action: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """按 fund_code/label_code/review_action 在一次 run 内做基金检索。

        返回每只基金的代码、命中标签数、review_action、缺失字段数。
        """
        clauses = ["r.run_id = ?"]
        params: list[Any] = [run_id]
        if fund_code:
            clauses.append("r.fund_code LIKE ?")
            params.append(f"%{fund_code}%")
        if label_code:
            clauses.append(
                "EXISTS (SELECT 1 FROM fund_label_results lr "
                "WHERE lr.run_id = r.run_id AND lr.fund_code = r.fund_code "
                "AND lr.label_code = ?)"
            )
            params.append(label_code)
        if review_action:
            clauses.append(
                "EXISTS (SELECT 1 FROM fund_run_coverage cov "
                "WHERE cov.run_id = r.run_id AND cov.fund_code = r.fund_code "
                "AND cov.review_action = ?)"
            )
            params.append(review_action)

        where = " AND ".join(clauses)
        sql = (
            "SELECT r.fund_code AS fund_code, "
            "COUNT(DISTINCT r.label_code) AS label_count, "
            "(SELECT cov.review_action FROM fund_run_coverage cov "
            " WHERE cov.run_id = r.run_id AND cov.fund_code = r.fund_code LIMIT 1) AS review_action, "
            "(SELECT COUNT(*) FROM fund_run_coverage cov "
            " WHERE cov.run_id = r.run_id AND cov.fund_code = r.fund_code AND cov.present = 0) AS missing_field_count "
            f"FROM fund_label_results r WHERE {where} "
            "GROUP BY r.fund_code "
            "ORDER BY r.fund_code LIMIT ?"
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def list_distinct_label_codes(self, run_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT label_code FROM fund_label_results "
                "WHERE run_id = ? ORDER BY label_code",
                (run_id,),
            ).fetchall()
        return [row["label_code"] for row in rows]

    def list_failures(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT fund_code, stage, error_type, message, recorded_at "
                    "FROM fund_run_failures WHERE run_id = ? "
                    "ORDER BY recorded_at, fund_code",
                    (run_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def get_summary(self, run_id: str) -> dict[str, Any]:
        """聚合一次 run 的批次摘要。"""
        with self._connect() as conn:
            run_row = conn.execute(
                "SELECT run_id, run_at, rule_version, status FROM label_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return {}

            processed_count = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c FROM fund_label_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()["c"]
            failed_count = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c FROM fund_run_failures WHERE run_id = ?",
                (run_id,),
            ).fetchone()["c"]
            insufficient_count = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c FROM fund_label_results "
                "WHERE run_id = ? AND label_code = 'data_insufficient'",
                (run_id,),
            ).fetchone()["c"]
            manual_review_count = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c FROM fund_run_coverage "
                "WHERE run_id = ? AND review_action = 'manual_review'",
                (run_id,),
            ).fetchone()["c"]
            return_window_insufficient_count = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c FROM fund_label_results "
                "WHERE run_id = ? AND label_code = 'return_window_insufficient'",
                (run_id,),
            ).fetchone()["c"]

            label_rows = conn.execute(
                "SELECT label_code, label_name, category, "
                "COUNT(DISTINCT fund_code) AS fund_count "
                "FROM fund_label_results WHERE run_id = ? "
                "GROUP BY label_code, label_name, category "
                "ORDER BY fund_count DESC, label_code",
                (run_id,),
            ).fetchall()

            review_rows = conn.execute(
                "SELECT review_action, COUNT(DISTINCT fund_code) AS fund_count "
                "FROM fund_run_coverage WHERE run_id = ? "
                "GROUP BY review_action "
                "ORDER BY fund_count DESC",
                (run_id,),
            ).fetchall()

            category_rows = conn.execute(
                "SELECT category, COUNT(*) AS label_count "
                "FROM fund_label_results WHERE run_id = ? "
                "GROUP BY category ORDER BY label_count DESC",
                (run_id,),
            ).fetchall()
            try:
                calculation_rows = conn.execute(
                    "SELECT state, COUNT(*) AS calculation_count, "
                    "COUNT(DISTINCT fund_code) AS fund_count "
                    "FROM label_calculation_states WHERE run_id = ? "
                    "GROUP BY state ORDER BY calculation_count DESC, state",
                    (run_id,),
                ).fetchall()
                not_computed_reason_rows = conn.execute(
                    "SELECT reason_code, COUNT(*) AS calculation_count, "
                    "COUNT(DISTINCT fund_code) AS fund_count "
                    "FROM label_calculation_states "
                    "WHERE run_id = ? AND state = 'not_computed' "
                    "GROUP BY reason_code ORDER BY calculation_count DESC, reason_code",
                    (run_id,),
                ).fetchall()
                not_computed_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM label_calculation_states "
                    "WHERE run_id = ? AND state = 'not_computed'",
                    (run_id,),
                ).fetchone()["c"]
            except sqlite3.OperationalError:
                calculation_rows = []
                not_computed_reason_rows = []
                not_computed_count = 0

        return {
            "run_id": run_id,
            "run_at": run_row["run_at"],
            "rule_version": run_row["rule_version"],
            "status": run_row["status"],
            "counts": {
                "processed": processed_count,
                "failed": failed_count,
                "data_insufficient": insufficient_count,
                "manual_review": manual_review_count,
                "return_window_insufficient": return_window_insufficient_count,
                "not_computed_calculations": not_computed_count,
            },
            "label_distribution": [dict(row) for row in label_rows],
            "review_action_distribution": [dict(row) for row in review_rows],
            "category_distribution": [dict(row) for row in category_rows],
            "calculation_state_distribution": [
                dict(row) for row in calculation_rows
            ],
            "not_computed_reason_distribution": [
                dict(row) for row in not_computed_reason_rows
            ],
        }

    def get_coverage_report(self, run_id: str) -> dict[str, Any]:
        """P0：按 fund_type 聚合本次 run 的数据覆盖率 + 拒绝原因 top。

        - by_fund_type: 每个类型下，每个 coverage 字段的通过/未通过基金数
        - rejection_reasons_top: data_insufficient 子原因码 top 列表
        - manual_review_fund_types: manual_review 基金按 fund_type 的分布
        """
        with self._connect() as conn:
            run = conn.execute(
                "SELECT run_id, run_at, rule_version, status FROM label_runs "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                return {}

            # 先看 fund_run_coverage 有没有 fund_type 列（migration 0004 之前的库可能没有）
            cov_cols = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(fund_run_coverage)"
                ).fetchall()
            }
            type_col = "fund_type" if "fund_type" in cov_cols else "NULL AS fund_type"

            coverage_rows = conn.execute(
                f"SELECT {type_col} AS fund_type, field, "
                "SUM(present) AS pass_count, "
                "SUM(1 - present) AS fail_count, "
                "COUNT(*) AS total "
                "FROM fund_run_coverage WHERE run_id = ? "
                "GROUP BY fund_type, field "
                "ORDER BY fund_type, field",
                (run_id,),
            ).fetchall()

            review_rows = conn.execute(
                f"SELECT {type_col} AS fund_type, review_action, "
                "COUNT(DISTINCT fund_code) AS fund_count "
                "FROM fund_run_coverage WHERE run_id = ? "
                "GROUP BY fund_type, review_action",
                (run_id,),
            ).fetchall()

            total_funds = conn.execute(
                "SELECT COUNT(DISTINCT fund_code) AS c "
                "FROM fund_label_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()["c"]

            # 子原因码 top：来自 data_insufficient 的 evidence，metric 形如 "<field>:<reason>"
            reason_rows = conn.execute(
                "SELECT metric, COUNT(DISTINCT fund_code) AS fund_count "
                "FROM fund_label_evidence "
                "WHERE run_id = ? AND label_code = 'data_insufficient' "
                "  AND source = 'coverage_gate' "
                "GROUP BY metric ORDER BY fund_count DESC, metric",
                (run_id,),
            ).fetchall()

        # 重组 by_fund_type
        by_type: dict[str, dict[str, Any]] = {}
        for row in coverage_rows:
            ft = row["fund_type"] or "unknown"
            bucket = by_type.setdefault(
                ft, {"fund_type": ft, "fields": [], "review_action_counts": {}}
            )
            bucket["fields"].append(
                {
                    "field": row["field"],
                    "pass_count": int(row["pass_count"] or 0),
                    "fail_count": int(row["fail_count"] or 0),
                    "total": int(row["total"] or 0),
                    "pass_rate": (
                        round(float(row["pass_count"] or 0) / float(row["total"]), 4)
                        if row["total"]
                        else 0.0
                    ),
                }
            )
        for row in review_rows:
            ft = row["fund_type"] or "unknown"
            bucket = by_type.setdefault(
                ft, {"fund_type": ft, "fields": [], "review_action_counts": {}}
            )
            bucket["review_action_counts"][row["review_action"]] = int(
                row["fund_count"] or 0
            )

        rejection_reasons_top = []
        for row in reason_rows:
            metric = row["metric"]
            if ":" in metric:
                field, reason = metric.split(":", 1)
            else:
                field, reason = metric, ""
            rejection_reasons_top.append(
                {
                    "field": field,
                    "reason": reason,
                    "fund_count": int(row["fund_count"] or 0),
                }
            )

        return {
            "run_id": run_id,
            "run_at": run["run_at"],
            "rule_version": run["rule_version"],
            "status": run["status"],
            "total_funds": int(total_funds or 0),
            "by_fund_type": sorted(by_type.values(), key=lambda x: x["fund_type"]),
            "rejection_reasons_top": rejection_reasons_top,
        }

    def list_label_definitions(
        self, rule_version: str | None = None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            try:
                if rule_version:
                    rows = conn.execute(
                        "SELECT label_code, label_name, category, fund_types, "
                        "rule_version, enabled, description, thresholds_json "
                        "FROM label_definitions WHERE rule_version = ? "
                        "ORDER BY label_code",
                        (rule_version,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT label_code, label_name, category, fund_types, "
                        "rule_version, enabled, description, thresholds_json "
                        "FROM label_definitions ORDER BY rule_version, label_code"
                    ).fetchall()
            except sqlite3.OperationalError:
                return []
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            thresholds_raw = item.pop("thresholds_json", None)
            item["thresholds"] = (
                json.loads(thresholds_raw) if thresholds_raw else None
            )
            results.append(item)
        return results

    def list_rule_versions(self) -> list[dict[str, Any]]:
        """列出已有的规则版本和每个版本对应的 run 数量。"""
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT rule_version, COUNT(*) AS run_count, "
                    "MAX(run_at) AS last_run_at "
                    "FROM label_runs GROUP BY rule_version "
                    "ORDER BY last_run_at DESC"
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def get_run_export(self, run_id: str) -> dict[str, Any] | None:
        """整批结果导出所需的全部数据，单次连接覆盖 5 张表。"""
        with self._connect() as conn:
            try:
                run = conn.execute(
                    "SELECT run_id, run_at, rule_version, status FROM label_runs "
                    "WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return None
            if run is None:
                return None
            labels = conn.execute(
                "SELECT fund_code, label_code, label_name, category, "
                "status, confidence FROM fund_label_results "
                "WHERE run_id = ? ORDER BY fund_code, label_code",
                (run_id,),
            ).fetchall()
            evidence = conn.execute(
                "SELECT fund_code, label_code, metric, value, threshold, "
                "source, message FROM fund_label_evidence "
                "WHERE run_id = ? ORDER BY fund_code, label_code",
                (run_id,),
            ).fetchall()
            try:
                features = conn.execute(
                    "SELECT fund_code, feature_code, value, source "
                    "FROM feature_values WHERE run_id = ? "
                    "ORDER BY fund_code, feature_code",
                    (run_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                features = []
            try:
                calculations = conn.execute(
                    "SELECT fund_code, label_code, label_name, category, state, "
                    "reason_code, observed, threshold, source, message "
                    "FROM label_calculation_states WHERE run_id = ? "
                    "ORDER BY fund_code, label_code",
                    (run_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                calculations = []
            try:
                coverage = conn.execute(
                    "SELECT fund_code, "
                    "GROUP_CONCAT(CASE WHEN present = 0 THEN field END) AS missing_fields, "
                    "MAX(review_action) AS review_action "
                    "FROM fund_run_coverage WHERE run_id = ? "
                    "GROUP BY fund_code ORDER BY fund_code",
                    (run_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                coverage = []
            try:
                failures = conn.execute(
                    "SELECT fund_code, stage, error_type, message, recorded_at "
                    "FROM fund_run_failures WHERE run_id = ? "
                    "ORDER BY recorded_at, fund_code",
                    (run_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                failures = []
        return {
            "run_id": run_id,
            "run_at": run["run_at"],
            "rule_version": run["rule_version"],
            "status": run["status"],
            "labels": [dict(r) for r in labels],
            "evidence": [dict(r) for r in evidence],
            "features": [dict(r) for r in features],
            "calculations": [dict(r) for r in calculations],
            "coverage": [dict(r) for r in coverage],
            "failures": [dict(r) for r in failures],
        }

    # ---------- Phase 5: 股票因子/股票级标签占位查询 ----------
    # 表已经在 migration 中预留，下列方法允许引擎以后无缝接入；
    # 当前如果表为空或不存在，返回空列表。

    def list_stock_factors(
        self, stock_code: str | None = None, as_of_date: str | None = None
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT stock_code, factor_code, factor_value, as_of_date, source "
            "FROM stock_factor_values WHERE 1=1"
        )
        params: list[Any] = []
        if stock_code:
            sql += " AND stock_code = ?"
            params.append(stock_code)
        if as_of_date:
            sql += " AND as_of_date = ?"
            params.append(as_of_date)
        sql += " ORDER BY as_of_date, stock_code, factor_code"
        with self._connect() as conn:
            try:
                rows = conn.execute(sql, tuple(params)).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(r) for r in rows]

    def list_stock_labels(
        self,
        stock_code: str | None = None,
        rule_version: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT stock_code, label_code, confidence, as_of_date, rule_version "
            "FROM stock_labels WHERE 1=1"
        )
        params: list[Any] = []
        if stock_code:
            sql += " AND stock_code = ?"
            params.append(stock_code)
        if rule_version:
            sql += " AND rule_version = ?"
            params.append(rule_version)
        sql += " ORDER BY as_of_date, stock_code, label_code"
        with self._connect() as conn:
            try:
                rows = conn.execute(sql, tuple(params)).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(r) for r in rows]

    def get_run_style_summary(self, run_id: str) -> dict[str, Any]:
        """汇总本次 run 在「持仓风格」上的产出。"""
        STYLE_LABELS = ("deep_value", "quality_growth", "dividend_steady")
        BOUNDARY_LABELS = (
            "style_unlabeled_stock_factors_missing",
            "style_pending_rule_definition",
        )
        with self._connect() as conn:
            run = conn.execute(
                "SELECT run_id, run_at, rule_version, status FROM label_runs "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                return {}

            placeholders = ",".join("?" * (len(STYLE_LABELS) + len(BOUNDARY_LABELS)))
            label_rows = conn.execute(
                f"SELECT label_code, COUNT(DISTINCT fund_code) AS fund_count "
                f"FROM fund_label_results WHERE run_id = ? "
                f"AND label_code IN ({placeholders}) GROUP BY label_code",
                (run_id, *STYLE_LABELS, *BOUNDARY_LABELS),
            ).fetchall()
            counts = {row["label_code"]: row["fund_count"] for row in label_rows}

            style_funds = conn.execute(
                f"SELECT fund_code, label_code FROM fund_label_results "
                f"WHERE run_id = ? AND label_code IN ({','.join('?' * len(STYLE_LABELS))}) "
                f"ORDER BY label_code, fund_code",
                (run_id, *STYLE_LABELS),
            ).fetchall()

        styles = {
            label: {"count": counts.get(label, 0), "funds": []}
            for label in STYLE_LABELS
        }
        for row in style_funds:
            styles[row["label_code"]]["funds"].append(row["fund_code"])
        return {
            "run_id": run_id,
            "run_at": run["run_at"],
            "rule_version": run["rule_version"],
            "styles": styles,
            "boundary_counts": {
                "stock_factors_missing": counts.get(
                    "style_unlabeled_stock_factors_missing", 0
                ),
                "style_pending_rule_definition": counts.get(
                    "style_pending_rule_definition", 0
                ),
            },
        }

    def diff_runs(
        self, base_run_id: str, target_run_id: str
    ) -> dict[str, Any] | None:
        """对比两个 run 的标签集合。

        - 基金交集上算 (fund_code, label_code) 的 added/removed
        - 同时返回按 label 聚合 和 按 fund 聚合 两种视角
        - only_in_base / only_in_target 是只在某一边出现过的基金代码（不进
          added/removed 统计，避免"换批数据"被误判成标签变动）
        """
        with self._connect() as conn:
            for rid in (base_run_id, target_run_id):
                exists = conn.execute(
                    "SELECT 1 FROM label_runs WHERE run_id = ?", (rid,)
                ).fetchone()
                if exists is None:
                    return None
            base_rows = conn.execute(
                "SELECT fund_code, label_code, label_name, category "
                "FROM fund_label_results WHERE run_id = ?",
                (base_run_id,),
            ).fetchall()
            target_rows = conn.execute(
                "SELECT fund_code, label_code, label_name, category "
                "FROM fund_label_results WHERE run_id = ?",
                (target_run_id,),
            ).fetchall()

        base_pairs = {(r["fund_code"], r["label_code"]) for r in base_rows}
        target_pairs = {(r["fund_code"], r["label_code"]) for r in target_rows}
        base_funds = {r["fund_code"] for r in base_rows}
        target_funds = {r["fund_code"] for r in target_rows}
        common_funds = base_funds & target_funds

        # 标签元信息：优先用 target 的（更新规则版本），fallback base
        label_meta: dict[str, dict[str, str]] = {}
        for r in target_rows:
            label_meta.setdefault(
                r["label_code"],
                {"label_name": r["label_name"], "category": r["category"]},
            )
        for r in base_rows:
            label_meta.setdefault(
                r["label_code"],
                {"label_name": r["label_name"], "category": r["category"]},
            )

        added = sorted(
            (pair for pair in target_pairs - base_pairs if pair[0] in common_funds)
        )
        removed = sorted(
            (pair for pair in base_pairs - target_pairs if pair[0] in common_funds)
        )

        def _by_label(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
            grouped: dict[str, list[str]] = {}
            for fund_code, label_code in pairs:
                grouped.setdefault(label_code, []).append(fund_code)
            return grouped

        added_by_label = _by_label(added)
        removed_by_label = _by_label(removed)
        all_changed_labels = sorted(set(added_by_label) | set(removed_by_label))
        summary_by_label = [
            {
                "label_code": label,
                "label_name": label_meta.get(label, {}).get("label_name", label),
                "category": label_meta.get(label, {}).get("category", ""),
                "added_funds": added_by_label.get(label, []),
                "removed_funds": removed_by_label.get(label, []),
                "delta": len(added_by_label.get(label, []))
                - len(removed_by_label.get(label, [])),
            }
            for label in all_changed_labels
        ]

        fund_changes: dict[str, dict[str, list[str]]] = {}
        for fund_code, label_code in added:
            fund_changes.setdefault(
                fund_code, {"added": [], "removed": []}
            )["added"].append(label_code)
        for fund_code, label_code in removed:
            fund_changes.setdefault(
                fund_code, {"added": [], "removed": []}
            )["removed"].append(label_code)
        details_by_fund = [
            {
                "fund_code": fund_code,
                "added_labels": sorted(changes["added"]),
                "removed_labels": sorted(changes["removed"]),
            }
            for fund_code, changes in sorted(fund_changes.items())
        ]

        return {
            "base_run_id": base_run_id,
            "target_run_id": target_run_id,
            "totals": {
                "base_fund_count": len(base_funds),
                "target_fund_count": len(target_funds),
                "common_fund_count": len(common_funds),
                "only_in_base_count": len(base_funds - target_funds),
                "only_in_target_count": len(target_funds - base_funds),
                "added_pair_count": len(added),
                "removed_pair_count": len(removed),
                "changed_fund_count": len(fund_changes),
            },
            "summary_by_label": summary_by_label,
            "details_by_fund": details_by_fund,
            "only_in_base": sorted(base_funds - target_funds),
            "only_in_target": sorted(target_funds - base_funds),
        }
