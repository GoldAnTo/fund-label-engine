from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Literal

# 把项目根目录加入 sys.path，使 scripts 模块可被 import
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.batch import run_batch
from app.benchmark_precision import benchmark_precision_by_fund
from app.exporters import (
    export_fund_report,
    export_review_queue,
    export_run_results,
)
from app.persistence import LabelRunReader, LabelRunWriter

OBSERVE_TASK_LABEL_CODES = {
    "industry_concentration_high",
    "industry_concentration_observe",
    "industry_diversified",
    "holding_concentration_high",
    "equity_position_high",
    "style_stable",
    "style_drift",
    "style_recent_shift",
    "style_exposure_observe",
    "style_exposure_low_coverage",
}

CALIBRATION_TASK_LABEL_CODES = {
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
    "style_pending_rule_definition",
    "style_unlabeled_stock_factors_missing",
    "sector_mapping_insufficient",
}


def _resolve_db_path(db_path: str | Path | None) -> str | None:
    if db_path is not None:
        return str(db_path)
    env_path = os.environ.get("FLE_DB_PATH")
    return env_path or None


def _resolve_source_db(db_path: str | Path | None) -> str | None:
    explicit = os.environ.get("FLE_SOURCE_DB")
    if explicit:
        return explicit
    return _resolve_db_path(db_path)


def _resolve_output_db(db_path: str | Path | None) -> str | None:
    explicit = os.environ.get("FLE_OUTPUT_DB")
    if explicit:
        return explicit
    return _resolve_db_path(db_path)


def _resolve_frontend_dist(frontend_dist: str | Path | None) -> Path | None:
    explicit = frontend_dist or os.environ.get("FLE_FRONTEND_DIST")
    if explicit:
        candidate = Path(explicit)
    else:
        # backend/app/main.py -> 仓库根 -> frontend/dist
        candidate = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return candidate if candidate.is_dir() else None


class ReviewRequest(BaseModel):
    decision: Literal["confirm", "reject", "observe"]
    reviewer: str
    comment: str = ""


class RunRequest(BaseModel):
    source: Literal["auto", "engine", "funddata"] = "auto"
    rule_version: str = "v1"


class PortfolioRoleReviewRequest(BaseModel):
    fund_code: str
    role_code: str
    decision: Literal["accept", "reject", "needs_more_data"]
    target_bucket: Literal["core", "satellite", "index_tool", "cash_buffer", "exclude", "observe"]
    max_weight_pct: float = 0
    rationale: str = ""
    reviewer: str = ""


class PortfolioRoleReviewItem(BaseModel):
    fund_code: str
    role_code: str
    decision: Literal["accept", "reject", "needs_more_data"]
    target_bucket: Literal["core", "satellite", "index_tool", "cash_buffer", "exclude"]
    max_weight_pct: float = 0
    rationale: str = ""


class PortfolioRoleReviewApplyRequest(BaseModel):
    reviewer: str
    items: list[PortfolioRoleReviewItem]


def create_app(
    db_path: str | Path | None = None,
    source_db_path: str | Path | None = None,
    output_db_path: str | Path | None = None,
    frontend_dist: str | Path | None = None,
) -> FastAPI:
    from app.logging_config import configure_logging

    configure_logging()

    app = FastAPI(
        title="Fund Label Engine",
        description="Explainable fund label calculation engine.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 兼容旧用法：db_path 同时承担读和写；双库模式下查询/复核读写 output DB。
    app.state.db_path = _resolve_output_db(output_db_path or db_path)
    # 新增：批量执行需要明确的输入/输出数据库
    app.state.source_db_path = _resolve_source_db(source_db_path or db_path)
    app.state.output_db_path = _resolve_output_db(output_db_path or db_path)

    def get_reader() -> LabelRunReader:
        path = app.state.output_db_path or app.state.db_path
        if not path:
            raise HTTPException(
                status_code=503,
                detail="Database path is not configured. Set FLE_OUTPUT_DB/FLE_DB_PATH or pass db_path to create_app().",
            )
        return LabelRunReader(path, app.state.source_db_path)

    def get_writer() -> LabelRunWriter:
        path = app.state.output_db_path or app.state.db_path
        if not path:
            raise HTTPException(
                status_code=503,
                detail="Database path is not configured. Set FLE_OUTPUT_DB/FLE_DB_PATH or pass db_path to create_app().",
            )
        return LabelRunWriter(path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/runs")
    def list_runs(
        limit: int = 50,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, list[dict]]:
        return {"runs": reader.list_runs(limit=limit)}

    @app.post("/v1/runs", status_code=201)
    def trigger_run(request: RunRequest | None = None) -> dict[str, Any]:
        source = (request or RunRequest()).source
        rule_version = (request or RunRequest()).rule_version
        source_db = app.state.source_db_path
        output_db = app.state.output_db_path
        if not source_db or not output_db:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Batch endpoint requires FLE_SOURCE_DB and FLE_OUTPUT_DB "
                    "(or FLE_DB_PATH for both)."
                ),
            )
        try:
            if source_db == output_db:
                run_id, processed = run_batch(
                    db_path=source_db,
                    rule_version=rule_version,
                    source=source,
                )
            else:
                run_id, processed = run_batch(
                    source_db=source_db,
                    output_db=output_db,
                    rule_version=rule_version,
                    source=source,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - 仅在底层异常时触发
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "run_id": run_id,
            "processed": processed,
            "status": "succeeded",
            "source": source,
            "rule_version": rule_version,
        }

    @app.get("/v1/runs/diff")
    def get_runs_diff(
        base: str,
        target: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        if not base or not target:
            raise HTTPException(
                status_code=400,
                detail="both base and target run_id are required",
            )
        payload = reader.diff_runs(base, target)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"one of the runs not found: base={base} target={target}",
            )
        return payload

    @app.get("/v1/runs/{run_id}")
    def get_run(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict:
        run = reader.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        run["fund_codes"] = reader.list_run_funds(run_id)
        run["failures"] = reader.list_failures(run_id)
        run["data_snapshot"] = reader.get_data_snapshot(
            run.get("data_snapshot_id")
        )
        return run

    @app.get("/v1/runs/{run_id}/failures")
    def get_run_failures(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        failures = reader.list_failures(run_id)
        return {"run_id": run_id, "failures": failures, "failure_count": len(failures)}

    @app.get("/v1/runs/{run_id}/rules")
    def get_run_rules(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        run = reader.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return {
            "run_id": run_id,
            "rule_version": run["rule_version"],
            "rule_snapshot": run.get("rule_snapshot"),
        }

    @app.get("/v1/runs/{run_id}/summary")
    def get_run_summary(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        summary = reader.get_summary(run_id)
        if not summary:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        # 附带标签变化汇总，让前端一次拿全
        summary["label_change_summary"] = reader.get_label_change_summary(run_id)
        return summary

    @app.get("/v1/audit-log")
    def get_audit_log(
        run_id: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int = 200,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """查询审计日志，可按多个维度过滤。"""
        rows = reader.list_audit_log(
            run_id=run_id,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            limit=limit,
        )
        return {"count": len(rows), "rows": rows}

    @app.get("/v1/runs/{run_id}/label-changes")
    def get_run_label_changes(
        run_id: str,
        fund_code: str | None = None,
        risk_warnings_only: bool = False,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """列出本次 run 的标签变化，含新增/消失/状态变更、风险预警标记。"""
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        changes = reader.list_label_changes(
            run_id,
            fund_code=fund_code,
            risk_warnings_only=risk_warnings_only,
        )
        summary = reader.get_label_change_summary(run_id)
        return {
            "run_id": run_id,
            "summary": summary,
            "count": len(changes),
            "changes": changes,
        }

    def _annotate_benchmark_precision(payload: dict[str, Any]) -> None:
        """给 matrix 每行补 benchmark_precision(exact/approx/none)。

        approx 表示该基金的相对基准用了显式近似源（中债综合近似中债总等），
        Alpha/超额收益等相对结论需按“近似基准”解读，不能与精确基准同等看待。
        """
        source_db = app.state.source_db_path or app.state.db_path
        precision: dict[str, str] = {}
        if source_db:
            try:
                precision = benchmark_precision_by_fund(source_db)
            except Exception:  # noqa: BLE001 - 标注失败不应影响 matrix 主体
                precision = {}
        for row in payload.get("rows", []):
            row["benchmark_precision"] = precision.get(row["fund_code"], "none")

    @app.get("/v1/runs/{run_id}/portfolio-matrix")
    def get_run_portfolio_matrix(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        payload = reader.get_portfolio_matrix(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        _annotate_benchmark_precision(payload)
        return payload

    @app.get("/v1/runs/{run_id}/portfolio-draft")
    def get_run_portfolio_draft(
        run_id: str,
        mode: Literal["research", "accepted"] = "research",
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        payload = reader.get_portfolio_draft(run_id, mode=mode)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return payload

    @app.get("/v1/runs/{run_id}/portfolio-role-reviews")
    def list_portfolio_role_reviews(
        run_id: str,
        fund_code: str | None = None,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        reviews = reader.list_portfolio_role_reviews(run_id, fund_code=fund_code)
        return {"run_id": run_id, "reviews": reviews}

    @app.get("/v1/runs/{run_id}/portfolio-role-reviews/suggest")
    def suggest_portfolio_role_reviews(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """对所有 allocation_status=review_required 的基金给出 role review 建议。

        不写库；返回结构给前端展示，研究员可以一键 apply 或逐只改。
        """
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        from app.portfolio.role_review_suggest import suggest_role_reviews

        payload = reader.get_portfolio_matrix(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"matrix not found: {run_id}")
        suggestions = suggest_role_reviews(payload.get("rows", []))
        return {"run_id": run_id, "suggestions": suggestions}

    @app.post("/v1/runs/{run_id}/portfolio-role-reviews/apply-suggestions")
    def apply_portfolio_role_review_suggestions(
        run_id: str,
        request: PortfolioRoleReviewApplyRequest,
        reader: LabelRunReader = Depends(get_reader),
        writer: LabelRunWriter = Depends(get_writer),
    ) -> dict[str, Any]:
        """一键 apply 建议（不修改的内容可省略 reviewer 字段会被拒绝）。"""
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        if not request.reviewer.strip():
            raise HTTPException(
                status_code=400,
                detail="reviewer is required to apply suggestions",
            )
        applied: list[str] = []
        from app.audit import audit_log

        for item in request.items:
            writer.write_portfolio_role_review(
                run_id=run_id,
                fund_code=item.fund_code,
                role_code=item.role_code,
                decision=item.decision,
                target_bucket=item.target_bucket,
                max_weight_pct=item.max_weight_pct,
                rationale=item.rationale,
                reviewer=request.reviewer,
            )
            applied.append(item.fund_code)
            audit_log(
                writer,
                action="apply_role_suggestion",
                target_type="role",
                target_id=f"{item.fund_code}/{item.role_code}",
                payload={
                    "decision": item.decision,
                    "target_bucket": item.target_bucket,
                    "max_weight_pct": item.max_weight_pct,
                    "rationale": item.rationale,
                },
                actor=request.reviewer,
                run_id=run_id,
            )
        return {
            "run_id": run_id,
            "reviewer": request.reviewer,
            "applied_fund_codes": applied,
        }

    @app.post("/v1/runs/{run_id}/portfolio-role-reviews")
    def create_portfolio_role_review(
        run_id: str,
        request: PortfolioRoleReviewRequest,
        reader: LabelRunReader = Depends(get_reader),
        writer: LabelRunWriter = Depends(get_writer),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        writer.write_portfolio_role_review(
            run_id=run_id,
            fund_code=request.fund_code,
            role_code=request.role_code,
            decision=request.decision,
            target_bucket=request.target_bucket,
            max_weight_pct=request.max_weight_pct,
            rationale=request.rationale,
            reviewer=request.reviewer,
        )
        from app.audit import audit_log
        audit_log(
            writer,
            action="write_role_review",
            target_type="role",
            target_id=f"{request.fund_code}/{request.role_code}",
            payload={
                "decision": request.decision,
                "target_bucket": request.target_bucket,
                "max_weight_pct": request.max_weight_pct,
                "rationale": request.rationale,
            },
            actor=request.reviewer or "unknown",
            run_id=run_id,
        )
        reviews = reader.list_portfolio_role_reviews(run_id, fund_code=request.fund_code)
        for review in reviews:
            if review["role_code"] == request.role_code:
                return review
        raise HTTPException(status_code=500, detail="portfolio role review was not persisted")

    @app.delete("/v1/runs/{run_id}/portfolio-role-reviews/{fund_code}/{role_code}")
    def delete_portfolio_role_review(
        run_id: str,
        fund_code: str,
        role_code: str,
        reader: LabelRunReader = Depends(get_reader),
        writer: LabelRunWriter = Depends(get_writer),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        deleted = writer.delete_portfolio_role_review(
            run_id=run_id,
            fund_code=fund_code,
            role_code=role_code,
        )
        return {"run_id": run_id, "fund_code": fund_code, "role_code": role_code, "deleted": deleted}

    @app.get("/v1/runs/{run_id}/coverage")
    def get_run_coverage(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """P0：数据覆盖率报告（按基金类型聚合 + 拒绝原因 top）。"""
        payload = reader.get_coverage_report(run_id)
        if not payload:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return payload

    @app.get("/v1/runs/{run_id}/style")
    def get_run_style(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        payload = reader.get_run_style_summary(run_id)
        if not payload:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return payload

    @app.get("/v1/label-definitions")
    def list_label_definitions(
        rule_version: str | None = None,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        return {
            "rule_version": rule_version,
            "definitions": reader.list_label_definitions(rule_version),
        }

    @app.get("/v1/rule-versions")
    def list_rule_versions(
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        return {"rule_versions": reader.list_rule_versions()}

    @app.get("/v1/runs/{run_id}/funds/{fund_code}")
    def get_run_fund(
        run_id: str,
        fund_code: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict:
        payload = reader.get_fund_labels(run_id, fund_code)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"fund {fund_code} not found in run {run_id}",
            )
        return payload

    @app.get("/v1/runs/{run_id}/funds/{fund_code}/report")
    def get_run_fund_report(
        run_id: str,
        fund_code: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict:
        payload = reader.get_fund_report(run_id, fund_code)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"fund {fund_code} not found in run {run_id}",
            )
        return payload

    @app.get("/v1/runs/{run_id}/funds/{fund_code}/percentile")
    def get_run_fund_percentile(
        run_id: str,
        fund_code: str,
        label_code: str | None = None,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """返回某只基金在指定分组下的指标百分位排名。

        - ``label_code`` 可选；不传则返回该基金所有分组（全市场+所有命中的风格标签）。
        - 返回值: ``{fund_code, run_id, ranks: [{label_code, metric_code, ...}]}``
        """
        ranks = reader.list_percentile_ranks(run_id, fund_code, label_code)
        return {
            "run_id": run_id,
            "fund_code": fund_code,
            "label_code": label_code,
            "ranks": ranks,
        }

    @app.get("/v1/runs/{run_id}/top-funds")
    def get_run_top_funds(
        run_id: str,
        label_code: str,
        metric_code: str = "annualized_return_1y",
        limit: int = 5,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """返回某风格标签分组下某指标排名前 N 的基金。"""
        rows = reader.get_top_funds_in_group(run_id, label_code, metric_code, limit)
        return {
            "run_id": run_id,
            "label_code": label_code,
            "metric_code": metric_code,
            "results": rows,
        }

    @app.get("/v1/runs/{run_id}/compare")
    def get_run_compare(
        run_id: str,
        funds: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """竞品横评：多只基金的标签、因子、指标、分位数并排对比。

        - ``funds``: 逗号分隔的基金代码，最多 6 只。
        """
        fund_codes = [c.strip() for c in funds.split(",") if c.strip()]
        if not fund_codes:
            raise HTTPException(status_code=400, detail="funds 参数不能为空")
        if len(fund_codes) > 6:
            raise HTTPException(status_code=400, detail="最多支持 6 只基金对比")
        return reader.get_compare_overview(run_id, fund_codes)

    @app.get("/v1/holdings-overlap")
    def get_holdings_overlap(
        funds: str,
        top_n: int = 10,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """持仓重叠度：多只基金最新一期前 N 持仓的重叠情况。"""
        fund_codes = [c.strip() for c in funds.split(",") if c.strip()]
        if len(fund_codes) < 2:
            raise HTTPException(status_code=400, detail="至少需要 2 只基金")
        if len(fund_codes) > 6:
            raise HTTPException(status_code=400, detail="最多支持 6 只基金")
        return reader.get_holdings_overlap(fund_codes, top_n)

    @app.get("/v1/correlation")
    def get_correlation(
        funds: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """基金相关性矩阵：基于日收益率计算两两 Pearson 相关系数。"""
        fund_codes = [c.strip() for c in funds.split(",") if c.strip()]
        if len(fund_codes) < 2:
            raise HTTPException(status_code=400, detail="至少需要 2 只基金")
        if len(fund_codes) > 6:
            raise HTTPException(status_code=400, detail="最多支持 6 只基金")
        return reader.get_correlation_matrix(fund_codes)

    @app.get("/v1/portfolio-risk")
    def get_portfolio_risk(
        funds: str,
        weights: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        """组合风险预估：给定基金和权重，计算组合波动率、分散化比率。"""
        fund_codes = [c.strip() for c in funds.split(",") if c.strip()]
        weight_list = [float(w.strip()) for w in weights.split(",") if w.strip()]
        if len(fund_codes) < 2:
            raise HTTPException(status_code=400, detail="至少需要 2 只基金")
        if len(fund_codes) > 6:
            raise HTTPException(status_code=400, detail="最多支持 6 只基金")
        if len(fund_codes) != len(weight_list):
            raise HTTPException(status_code=400, detail="基金数和权重数不一致")
        return reader.get_portfolio_risk(fund_codes, weight_list)

    @app.get("/v1/runs/{run_id}/funds/{fund_code}/benchmark-components")
    def get_run_fund_benchmark_components(
        run_id: str,
        fund_code: str,
    ) -> dict[str, Any]:
        """返回该基金基准组件解析与收益缺口（从 source 库读取）。

        用于单基金报告页醒目展示基准覆盖缺口：哪些组件未解析、哪些已解析但
        无日收益源、合成基准收益是否成功。
        """
        import sqlite3

        source_db = app.state.source_db_path or app.state.db_path
        if not source_db:
            raise HTTPException(
                status_code=503,
                detail="Source database is not configured.",
            )
        conn = sqlite3.connect(source_db)
        conn.row_factory = sqlite3.Row
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            components: list[dict[str, Any]] = []
            if "benchmark_components" in tables:
                rows = conn.execute(
                    "SELECT component_order, component_code, component_name, "
                    "weight, source_text, status, reason "
                    "FROM benchmark_components WHERE fund_code = ? "
                    "ORDER BY component_order",
                    (fund_code,),
                ).fetchall()
                # 哪些 component_code 有本地日收益
                have_returns: set[str] = set()
                if "benchmark_component_returns" in tables and rows:
                    codes = [r["component_code"] for r in rows if r["component_code"]]
                    if codes:
                        placeholders = ",".join("?" for _ in codes)
                        have_returns = {
                            r[0]
                            for r in conn.execute(
                                f"SELECT DISTINCT component_code FROM "
                                f"benchmark_component_returns "
                                f"WHERE component_code IN ({placeholders})",
                                codes,
                            ).fetchall()
                        }
                for r in rows:
                    code = r["component_code"]
                    reason = r["reason"]
                    # 收益源判定：
                    # - synthetic 组件恒有收益（合成利率）
                    # - 在 benchmark_component_returns 表里有行的组件有收益
                    # - 基金已成功合成 benchmark_returns 时，所有 resolved 组件必然都有收益
                    #   （股指等直取组件不入 component_returns 表，但合成成功即证明可取）
                    has_returns = (
                        reason == "synthetic"
                        or (bool(code) and code in have_returns)
                    )
                    components.append(
                        {
                            "component_order": r["component_order"],
                            "component_code": code,
                            "component_name": r["component_name"],
                            "weight": r["weight"],
                            "source_text": r["source_text"],
                            "status": r["status"],
                            "reason": reason,
                            "has_returns": has_returns,
                        }
                    )
            benchmark_returns_count = 0
            if "benchmark_returns" in tables:
                benchmark_returns_count = (
                    conn.execute(
                        "SELECT COUNT(*) FROM benchmark_returns WHERE fund_code = ?",
                        (fund_code,),
                    ).fetchone()[0]
                )
        finally:
            conn.close()

        # 基金已合成基准收益 → 所有 resolved 组件都有收益（直取组件不入 component_returns）
        if benchmark_returns_count > 0:
            for c in components:
                if c["status"] == "resolved" and not c["has_returns"]:
                    c["has_returns"] = True

        unresolved = [
            c for c in components if c["status"] != "resolved" or not c["has_returns"]
        ]
        return {
            "run_id": run_id,
            "fund_code": fund_code,
            "components": components,
            "benchmark_returns_count": benchmark_returns_count,
            "has_benchmark_returns": benchmark_returns_count > 0,
            "unresolved_count": len(unresolved),
        }

    @app.get("/v1/runs/{run_id}/search")
    def search_run_funds(
        run_id: str,
        fund_code: str | None = None,
        label_code: str | None = None,
        review_action: Literal["observe", "manual_review"] | None = None,
        group_code: str | None = None,
        group_type: str | None = None,
        classification_code: str | None = None,
        limit: int = 200,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return {
            "run_id": run_id,
            "filters": {
                "fund_code": fund_code,
                "label_code": label_code,
                "review_action": review_action,
                "group_code": group_code,
                "group_type": group_type,
                "classification_code": classification_code,
            },
            "available_labels": reader.list_distinct_label_codes(run_id),
            "available_groups": reader.list_distinct_group_codes(run_id),
            "available_group_types": reader.list_distinct_group_types(run_id),
            "available_classifications": reader.list_distinct_classification_codes(run_id),
            "results": reader.search_run_funds(
                run_id,
                fund_code=fund_code,
                label_code=label_code,
                review_action=review_action,
                group_code=group_code,
                group_type=group_type,
                classification_code=classification_code,
                limit=limit,
            ),
        }

    @app.get("/v1/runs/{run_id}/review-queue")
    def get_review_queue(
        run_id: str,
        limit: int = 200,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return {
            "run_id": run_id,
            "results": reader.search_run_funds(
                run_id,
                review_action="manual_review",
                limit=limit,
            ),
        }

    def _export_response(payload: tuple[bytes, str, str]) -> Response:
        data, media_type, filename = payload
        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/v1/runs/{run_id}/export")
    def export_run(
        run_id: str,
        format: Literal["csv", "xlsx"] = "xlsx",
        reader: LabelRunReader = Depends(get_reader),
    ) -> Response:
        payload = reader.get_run_export(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return _export_response(export_run_results(payload, format))

    @app.get("/v1/runs/{run_id}/funds/{fund_code}/export")
    def export_fund(
        run_id: str,
        fund_code: str,
        format: Literal["csv", "xlsx"] = "xlsx",
        reader: LabelRunReader = Depends(get_reader),
    ) -> Response:
        report = reader.get_fund_report(run_id, fund_code)
        if report is None:
            raise HTTPException(
                status_code=404,
                detail=f"fund report not found: run={run_id} fund={fund_code}",
            )
        return _export_response(export_fund_report(report, format))

    @app.get("/v1/runs/{run_id}/review-queue/export")
    def export_review_queue_endpoint(
        run_id: str,
        format: Literal["csv", "xlsx"] = "csv",
        limit: int = 1000,
        reader: LabelRunReader = Depends(get_reader),
    ) -> Response:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        rows = reader.search_run_funds(
            run_id, review_action="manual_review", limit=limit
        )
        return _export_response(export_review_queue(rows, run_id, format))

    @app.post("/v1/runs/{run_id}/funds/{fund_code}/labels/{label_code}/reviews")
    def post_label_review(
        run_id: str,
        fund_code: str,
        label_code: str,
        request: ReviewRequest,
        reader: LabelRunReader = Depends(get_reader),
        writer: LabelRunWriter = Depends(get_writer),
    ) -> dict:
        payload = reader.get_fund_labels(run_id, fund_code)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"fund {fund_code} not found in run {run_id}",
            )
        label_codes = {item["label_code"] for item in payload["labels"]}
        if label_code not in label_codes:
            raise HTTPException(
                status_code=404,
                detail=f"label {label_code} not found for fund {fund_code} in run {run_id}",
            )
        review_id = writer.write_review(
            run_id=run_id,
            fund_code=fund_code,
            label_code=label_code,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
        return {
            "review_id": review_id,
            "run_id": run_id,
            "fund_code": fund_code,
            "label_code": label_code,
            "decision": request.decision,
            "reviewer": request.reviewer,
            "comment": request.comment,
        }

    def _relative_eligibility_payload(
        run_id: str,
        status: Literal["all", "ready", "blocked"],
        limit: int,
        reader: LabelRunReader,
        fund_code: str | None = None,
    ) -> dict[str, Any]:
        """返回相对基准标签 ready/blocked 池，用于工作台展示。

        当 fund_code 不为空时，只返回该基金的 eligibility，避免前端拉全量。
        """
        import sqlite3

        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        source_db = app.state.source_db_path or app.state.db_path
        if not source_db:
            raise HTTPException(
                status_code=503,
                detail="Source database is not configured.",
            )

        from scripts.audit_benchmark_quality import build_quality_rows
        from scripts.audit_relative_label_eligibility import build_eligibility_rows

        codes = reader.list_run_funds(run_id)
        if fund_code:
            codes = [c for c in codes if c == fund_code]
            if not codes:
                raise HTTPException(
                    status_code=404,
                    detail=f"fund not found in run: {fund_code}",
                )
        precision_by_code = benchmark_precision_by_fund(source_db)
        try:
            with sqlite3.connect(source_db) as conn:
                conn.row_factory = sqlite3.Row
                quality_rows = build_quality_rows(conn, codes)
                quality_by_code = {row["fund_code"]: row for row in quality_rows}
                rows = build_eligibility_rows(
                    conn, codes, quality_by_code, precision_by_code
                )
        except sqlite3.OperationalError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Relative eligibility source tables are not ready: {exc}",
            ) from exc

        status_counts = Counter(row["relative_label_status"] for row in rows)
        source_counts = Counter(row["benchmark_source_status"] for row in rows)
        # approx 是“可用但按近似口径解读”的就绪档，不算被阻塞。
        ready_statuses = {"relative_label_ready", "relative_label_ready_approx"}
        blocker_groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row["relative_label_status"] in ready_statuses:
                continue
            components = [
                item.strip()
                for item in str(row.get("blocking_components") or "").split(";")
                if item.strip()
            ] or [str(row.get("blocking_reason") or row["relative_label_status"])]
            for component in components:
                key = f"{row['relative_label_status']}|{component}"
                group = blocker_groups.setdefault(
                    key,
                    {
                        "key": key,
                        "status": row["relative_label_status"],
                        "component": component,
                        "count": 0,
                        "sample_fund_codes": [],
                    },
                )
                group["count"] += 1
                if len(group["sample_fund_codes"]) < 5:
                    group["sample_fund_codes"].append(row["fund_code"])
        blocker_group_rows = sorted(
            blocker_groups.values(),
            key=lambda item: (-item["count"], item["status"], item["component"]),
        )
        if status == "ready":
            display_rows = [
                row for row in rows
                if row["relative_label_status"] in ready_statuses
            ]
        elif status == "blocked":
            display_rows = [
                row for row in rows
                if row["relative_label_status"] not in ready_statuses
            ]
        else:
            display_rows = rows
        display_rows = sorted(
            display_rows,
            key=lambda row: (row["relative_label_status"] not in ready_statuses, row["fund_code"]),
        )[:limit]

        ready_count = sum(
            status_counts.get(s, 0) for s in ready_statuses
        )
        return {
            "run_id": run_id,
            "total_funds": len(rows),
            "ready_count": ready_count,
            "ready_exact_count": status_counts.get("relative_label_ready", 0),
            "ready_approx_count": status_counts.get("relative_label_ready_approx", 0),
            "blocked_count": len(rows) - ready_count,
            "status_counts": dict(status_counts),
            "benchmark_source_counts": dict(source_counts),
            "blocker_groups": blocker_group_rows,
            "filters": {"status": status, "limit": limit},
            "results": display_rows,
        }

    def _clean_blocking_component(value: str) -> str:
        return value.split(":", 1)[1] if ":" in value else value

    def _workbench_task_action(task_type: str, reason: str) -> str:
        if task_type == "benchmark_gap":
            if reason == "benchmark_source_missing":
                return "补齐基准收益源"
            if reason == "benchmark_mapping_required":
                return "确认基准精确映射"
            if reason == "benchmark_unresolved":
                return "补解析规则或明确不支持"
            if reason == "benchmark_missing":
                return "补充基金业绩基准配置"
            return "补齐相对基准展示条件"
        if task_type == "manual_review":
            return "进入单基金报告复核结论"
        if task_type == "observe_signal":
            return "观察业务解释，不进入正式结论"
        if task_type == "calibration_signal":
            return "补样本或校准阈值后再升级"
        return "查看单基金报告"

    def _workbench_tasks_payload(
        run_id: str,
        limit: int,
        reader: LabelRunReader,
    ) -> dict[str, Any]:
        if reader.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        tasks: list[dict[str, Any]] = []

        eligibility = _relative_eligibility_payload(run_id, "blocked", 1000, reader)
        for row in eligibility["results"]:
            tasks.append({
                "task_id": f"benchmark_gap:{row['fund_code']}",
                "task_type": "benchmark_gap",
                "priority": "high",
                "fund_code": row["fund_code"],
                "fund_name": row.get("fund_name") or "",
                "label_code": None,
                "label_name": None,
                "reason_code": row["relative_label_status"],
                "reason_text": _clean_blocking_component(
                    row.get("blocking_components") or row.get("blocking_reason") or ""
                ),
                "suggested_action": _workbench_task_action(
                    "benchmark_gap", row["relative_label_status"]
                ),
            })

        for row in reader.search_run_funds(
            run_id,
            review_action="manual_review",
            limit=1000,
        ):
            tasks.append({
                "task_id": f"manual_review:{row['fund_code']}",
                "task_type": "manual_review",
                "priority": "high",
                "fund_code": row["fund_code"],
                "fund_name": "",
                "label_code": None,
                "label_name": None,
                "reason_code": "manual_review",
                "reason_text": f"缺失字段数 {row['missing_field_count']}",
                "suggested_action": _workbench_task_action("manual_review", "manual_review"),
            })

        summary = reader.get_summary(run_id)
        labels_by_code = {
            row["label_code"]: row
            for row in summary.get("label_distribution", [])
        }
        for label_code in sorted(OBSERVE_TASK_LABEL_CODES & labels_by_code.keys()):
            row = labels_by_code[label_code]
            tasks.append({
                "task_id": f"observe_signal:{label_code}",
                "task_type": "observe_signal",
                "priority": "medium",
                "fund_code": None,
                "fund_name": None,
                "label_code": label_code,
                "label_name": row["label_name"],
                "reason_code": "observe_signal",
                "reason_text": f"{row['fund_count']} 只基金命中",
                "suggested_action": _workbench_task_action("observe_signal", "observe_signal"),
            })
        for label_code in sorted(CALIBRATION_TASK_LABEL_CODES & labels_by_code.keys()):
            row = labels_by_code[label_code]
            tasks.append({
                "task_id": f"calibration_signal:{label_code}",
                "task_type": "calibration_signal",
                "priority": "medium",
                "fund_code": None,
                "fund_name": None,
                "label_code": label_code,
                "label_name": row["label_name"],
                "reason_code": "calibration_signal",
                "reason_text": f"{row['fund_count']} 只基金命中",
                "suggested_action": _workbench_task_action("calibration_signal", "calibration_signal"),
            })

        order = {"high": 0, "medium": 1, "low": 2}
        tasks = sorted(
            tasks,
            key=lambda task: (
                order.get(task["priority"], 9),
                task["task_type"],
                task.get("fund_code") or task.get("label_code") or "",
            ),
        )
        total_count = len(tasks)
        tasks = tasks[:limit]
        counts = Counter(task["task_type"] for task in tasks)
        return {
            "run_id": run_id,
            "total_count": total_count,
            "task_type_counts": dict(counts),
            "results": tasks,
        }

    @app.get("/v1/runs/{run_id}/workbench-summary")
    def get_run_workbench_summary(
        run_id: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        summary = reader.get_summary(run_id)
        if not summary:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        eligibility = _relative_eligibility_payload(run_id, "all", 300, reader)
        tasks = _workbench_tasks_payload(run_id, 1000, reader)
        return {
            "run_id": run_id,
            "run_at": summary["run_at"],
            "rule_version": summary["rule_version"],
            "status": summary["status"],
            "total_funds": eligibility["total_funds"],
            "ready_count": eligibility["ready_count"],
            "blocked_count": eligibility["blocked_count"],
            "manual_review_count": summary["counts"].get("manual_review", 0),
            "task_type_counts": tasks["task_type_counts"],
            "blocker_groups": eligibility["blocker_groups"][:10],
            "group_distribution": summary.get("group_distribution", []),
            "classification_distribution": summary.get("classification_distribution", []),
        }

    @app.get("/v1/runs/{run_id}/workbench-tasks")
    def get_run_workbench_tasks(
        run_id: str,
        limit: int = 300,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        return _workbench_tasks_payload(run_id, limit, reader)

    @app.get("/v1/runs/{run_id}/relative-label-eligibility")
    def get_run_relative_label_eligibility(
        run_id: str,
        status: Literal["all", "ready", "blocked"] = "all",
        limit: int = 200,
        fund_code: str | None = None,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict[str, Any]:
        return _relative_eligibility_payload(run_id, status, limit, reader, fund_code)

    @app.get("/v1/funds/{fund_code}/labels")
    def get_latest_fund_labels(
        fund_code: str,
        reader: LabelRunReader = Depends(get_reader),
    ) -> dict:
        run_id = reader.latest_succeeded_run_id()
        if run_id is None:
            raise HTTPException(status_code=404, detail="no succeeded run available")
        payload = reader.get_fund_labels(run_id, fund_code)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"fund {fund_code} not found in latest run {run_id}",
            )
        return payload

    # 在 API 路由之后 mount 前端静态文件
    dist_dir = _resolve_frontend_dist(frontend_dist)
    if dist_dir is not None:
        def _frontend_index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/ready-pool", include_in_schema=False)
        def serve_ready_pool() -> FileResponse:
            return _frontend_index()

        @app.get("/portfolio", include_in_schema=False)
        def serve_portfolio_route() -> FileResponse:
            return _frontend_index()

        @app.get("/runs/{full_path:path}", include_in_schema=False)
        def serve_run_route(full_path: str) -> FileResponse:
            return _frontend_index()

        @app.get("/diff", include_in_schema=False)
        def serve_diff_route() -> FileResponse:
            return _frontend_index()

        @app.get("/search", include_in_schema=False)
        def serve_search_route() -> FileResponse:
            return _frontend_index()

        @app.get("/review-queue", include_in_schema=False)
        def serve_review_queue_route() -> FileResponse:
            return _frontend_index()

        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


app = create_app()
