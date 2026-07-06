"""标签变化检测：对比相邻两次 batch 的标签状态，记录变化和风险预警。

用法：
    from app.label_change_detection import detect_and_write_label_changes

    detect_and_write_label_changes(writer, reader, run_id)
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

# 风险类标签：从非 active 变为 active 时触发风险预警
RISK_LABEL_CODES = frozenset({
    "drawdown_high",
    "volatility_high",
    "beta_high",
    "industry_concentration_high",
    "holding_concentration_high",
    "tracking_error_high",
    "style_drift",
})


def _get_label_set(conn: sqlite3.Connection, run_id: str) -> dict[tuple[str, str], str]:
    """返回 {(fund_code, label_code): status} for a given run."""
    rows = conn.execute(
        "SELECT fund_code, label_code, status FROM fund_label_results WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def detect_label_changes(
    conn: sqlite3.Connection,
    current_run_id: str,
    previous_run_id: str,
) -> list[dict[str, Any]]:
    """对比两次 run 的标签，返回变化列表。"""
    current = _get_label_set(conn, current_run_id)
    previous = _get_label_set(conn, previous_run_id)
    now = datetime.now(UTC).isoformat(timespec="seconds")

    changes: list[dict[str, Any]] = []
    all_keys = set(current.keys()) | set(previous.keys())

    for fund_code, label_code in all_keys:
        curr_status = current.get((fund_code, label_code))
        prev_status = previous.get((fund_code, label_code))

        if curr_status is not None and prev_status is None:
            change_type = "added"
        elif curr_status is None and prev_status is not None:
            change_type = "removed"
        elif curr_status != prev_status:
            change_type = "status_changed"
        else:
            continue

        # 风险预警：风险标签从非 active 变为 active
        is_risk = 0
        if (
            label_code in RISK_LABEL_CODES
            and curr_status == "active"
            and prev_status != "active"
        ):
            is_risk = 1

        changes.append({
            "run_id": current_run_id,
            "previous_run_id": previous_run_id,
            "fund_code": fund_code,
            "label_code": label_code,
            "change_type": change_type,
            "previous_status": prev_status,
            "current_status": curr_status,
            "is_risk_warning": is_risk,
            "detected_at": now,
        })

    return changes


def write_label_changes(
    conn: sqlite3.Connection,
    changes: list[dict[str, Any]],
) -> int:
    """将变化写入 label_changes 表，返回写入条数。"""
    if not changes:
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO label_changes "
        "(run_id, previous_run_id, fund_code, label_code, change_type, "
        "previous_status, current_status, is_risk_warning, detected_at) "
        "VALUES (:run_id, :previous_run_id, :fund_code, :label_code, :change_type, "
        ":previous_status, :current_status, :is_risk_warning, :detected_at)",
        changes,
    )
    return len(changes)


def detect_and_write_label_changes(
    output_db_path: str,
    current_run_id: str,
    previous_run_id: str | None,
) -> tuple[int, int]:
    """检测并写入标签变化，返回 (总变化数, 风险预警数)。

    如果没有上一次成功的 run，返回 (0, 0)。
    """
    if not previous_run_id:
        return 0, 0

    with sqlite3.connect(output_db_path) as conn:
        # 确保 label_changes 表存在（迁移可能在后台跑）
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS label_changes (
                run_id TEXT NOT NULL,
                previous_run_id TEXT NOT NULL,
                fund_code TEXT NOT NULL,
                label_code TEXT NOT NULL,
                change_type TEXT NOT NULL,
                previous_status TEXT,
                current_status TEXT,
                is_risk_warning INTEGER DEFAULT 0,
                detected_at TEXT NOT NULL,
                PRIMARY KEY (run_id, fund_code, label_code)
            );
            """
        )
        try:
            changes = detect_label_changes(conn, current_run_id, previous_run_id)
        except sqlite3.OperationalError:
            return 0, 0
        write_label_changes(conn, changes)
        conn.commit()

    risk_count = sum(1 for c in changes if c["is_risk_warning"])
    return len(changes), risk_count
