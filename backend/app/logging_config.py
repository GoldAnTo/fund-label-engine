"""结构化日志配置。

用法：
    from app.logging_config import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    logger.info("message", extra={"run_id": "xxx"})

日志格式：JSON 单行，便于 ELK/Loki 采集。
通知：设置环境变量 FLE_NOTIFY_WEBHOOK_URL 后，batch 失败时会发送通知。
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, datetime
from logging import Formatter, LogRecord, StreamHandler, getLogger
from typing import Any

_CONFIGURED = False


class JSONFormatter(Formatter):
    """将日志输出为 JSON 单行。"""

    def format(self, record: LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 合并 extra 字段
        for key in ("run_id", "fund_code", "snapshot_id", "stage", "event"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """配置全局日志，幂等。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str):
    """获取 logger。"""
    if not _CONFIGURED:
        configure_logging()
    return getLogger(name)


def notify_webhook(title: str, detail: str, level: str = "warning") -> bool:
    """发送通知到 webhook（如果配置了 FLE_NOTIFY_WEBHOOK_URL）。

    支持钉钉/飞书/Slack 等 webhook 格式。
    返回 True 表示已发送，False 表示未配置或发送失败。
    """
    webhook_url = os.environ.get("FLE_NOTIFY_WEBHOOK_URL")
    if not webhook_url:
        return False
    payload = json.dumps(
        {
            "title": title,
            "text": f"[{level.upper()}] {title}\n{detail}",
            "level": level,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        # 通知失败不应阻塞主流程
        get_logger(__name__).exception("webhook notify failed")
        return False
