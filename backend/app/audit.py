"""审计日志：记录所有影响数据库状态的写操作。

用法：
    from app.audit import audit_log
    audit_log(writer, action="review", target_type="label",
              target_id=f"{fund_code}/{label_code}", payload=...,
              actor=reviewer, run_id=run_id, source_ip=request.client.host)
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.persistence import LabelRunWriter


def audit_log(
    writer: LabelRunWriter,
    action: str,
    target_type: str,
    target_id: str,
    payload: Any | None = None,
    actor: str = "system",
    run_id: str | None = None,
    source_ip: str | None = None,
) -> None:
    """记录一条审计日志。失败不会影响主流程。"""
    try:
        audit_id = uuid.uuid4().hex
        payload_json: str | None = None
        if payload is not None:
            try:
                payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                payload_json = json.dumps(str(payload), ensure_ascii=False)
        with writer._connect() as conn:
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
    except Exception:
        # 审计失败不应阻塞主流程；记录器可在外部 capture
        from app.logging_config import get_logger

        get_logger(__name__).exception("audit_log failed for action %s", action)
