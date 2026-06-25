from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.batch import run_batch
from app.exporters import (
    export_fund_report,
    export_review_queue,
    export_run_results,
)
from app.persistence import LabelRunReader, LabelRunWriter


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


def create_app(
    db_path: str | Path | None = None,
    source_db_path: str | Path | None = None,
    output_db_path: str | Path | None = None,
    frontend_dist: str | Path | None = None,
) -> FastAPI:
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
        return LabelRunReader(path)

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
        return summary

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

    @app.get("/v1/runs/{run_id}/search")
    def search_run_funds(
        run_id: str,
        fund_code: str | None = None,
        label_code: str | None = None,
        review_action: Literal["observe", "manual_review"] | None = None,
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
            },
            "available_labels": reader.list_distinct_label_codes(run_id),
            "results": reader.search_run_funds(
                run_id,
                fund_code=fund_code,
                label_code=label_code,
                review_action=review_action,
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
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


app = create_app()
