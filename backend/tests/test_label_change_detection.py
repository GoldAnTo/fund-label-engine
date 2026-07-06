"""标签变化检测测试。"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from app.label_change_detection import (
    RISK_LABEL_CODES,
    detect_and_write_label_changes,
    detect_label_changes,
)


def test_detect_added_removed_changed(tmp_path: Path) -> None:
    """检测新增、消失、状态变更三类变化。"""
    db = tmp_path / "fund.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_label_results (
                run_id TEXT, fund_code TEXT, label_code TEXT,
                label_name TEXT, status TEXT,
                PRIMARY KEY (run_id, fund_code, label_code)
            );
            """
        )
        # 上一次 run
        prev = "prev123"
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '001', 'drawdown_high', '回撤高', 'inactive')",
            (prev,),
        )
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '002', 'volatility_high', '波动高', 'active')",
            (prev,),
        )
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '003', 'sharpe_high', '夏普高', 'observe')",
            (prev,),
        )
        # 本次 run
        curr = "curr456"
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '001', 'drawdown_high', '回撤高', 'active')",
            (curr,),
        )
        # 002 消失
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '003', 'sharpe_high', '夏普高', 'active')",
            (curr,),
        )
        # 新增 004
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '004', 'small_cap', '小盘', 'active')",
            (curr,),
        )
        conn.commit()

    with sqlite3.connect(db) as conn:
        changes = detect_label_changes(conn, curr, prev)

    changes_by = {(c["fund_code"], c["label_code"]): c for c in changes}

    # 001 drawdown_high: status_changed (inactive -> active) + 风险标签触发
    chg = changes_by[("001", "drawdown_high")]
    assert chg["change_type"] == "status_changed"
    assert chg["is_risk_warning"] == 1
    assert chg["previous_status"] == "inactive"
    assert chg["current_status"] == "active"

    # 002 volatility_high: removed
    chg = changes_by[("002", "volatility_high")]
    assert chg["change_type"] == "removed"
    assert chg["is_risk_warning"] == 0

    # 003 sharpe_high: status_changed (observe -> active) 不是风险标签
    chg = changes_by[("003", "sharpe_high")]
    assert chg["change_type"] == "status_changed"
    assert chg["is_risk_warning"] == 0

    # 004 small_cap: added
    chg = changes_by[("004", "small_cap")]
    assert chg["change_type"] == "added"


def test_detect_no_previous_run_returns_no_changes(tmp_path: Path) -> None:
    """没有上一次 run 时返回空。"""
    db = tmp_path / "fund.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_label_results (
                run_id TEXT, fund_code TEXT, label_code TEXT,
                label_name TEXT, status TEXT,
                PRIMARY KEY (run_id, fund_code, label_code)
            );
            """
        )

    change_count, risk_count = detect_and_write_label_changes(
        str(db), "any_run", None
    )
    assert change_count == 0
    assert risk_count == 0


def test_write_label_changes_creates_records(tmp_path: Path) -> None:
    """写完变化后表里就有记录。"""
    db = tmp_path / "fund.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE fund_label_results (
                run_id TEXT, fund_code TEXT, label_code TEXT,
                label_name TEXT, status TEXT,
                PRIMARY KEY (run_id, fund_code, label_code)
            );
            CREATE TABLE label_changes (
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

    prev = uuid.uuid4().hex
    curr = uuid.uuid4().hex
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '001', 'drawdown_high', '回撤高', 'inactive')",
            (prev,),
        )
        conn.execute(
            "INSERT INTO fund_label_results VALUES (?, '001', 'drawdown_high', '回撤高', 'active')",
            (curr,),
        )
        conn.commit()

    change_count, risk_count = detect_and_write_label_changes(str(db), curr, prev)
    assert change_count == 1
    assert risk_count == 1

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT fund_code, label_code, change_type, is_risk_warning FROM label_changes"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "001"
    assert rows[0][1] == "drawdown_high"
    assert rows[0][2] == "status_changed"
    assert rows[0][3] == 1


def test_risk_label_codes_set_is_sensible() -> None:
    """风险标签集合应至少包含核心风险标签。"""
    assert "drawdown_high" in RISK_LABEL_CODES
    assert "volatility_high" in RISK_LABEL_CODES
    assert "industry_concentration_high" in RISK_LABEL_CODES
    # sharpe_high 不是风险标签，是收益类标签
    assert "sharpe_high" not in RISK_LABEL_CODES
