"""风格稳定性历史（style_stable / style_drift / style_recent_shift）测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.persistence import LabelRunReader, LabelRunWriter


def _seed_style_history(db: Path, fund_code: str = "000001") -> None:
    """写入 3 个 run + 3 个稳定性标签，构造演化时间线。"""
    writer = LabelRunWriter(db)
    writer.ensure_schema()
    with sqlite3.connect(db) as conn:
        # run1: stable
        conn.execute(
            "INSERT INTO label_runs (run_id, run_at, data_as_of, rule_version, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-1", "2026-01-01 00:00:00", "2025-12-31", "v1", "succeeded"),
        )
        conn.execute(
            "INSERT INTO label_runs (run_id, run_at, data_as_of, rule_version, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-2", "2026-02-01 00:00:00", "2026-01-31", "v1", "succeeded"),
        )
        conn.execute(
            "INSERT INTO label_runs (run_id, run_at, data_as_of, rule_version, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-3", "2026-03-01 00:00:00", "2026-02-28", "v1", "succeeded"),
        )
        # run-1 stable
        conn.execute(
            "INSERT INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, status, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-1", fund_code, "style_stable", "风格稳定", "stability", "active", 0.9),
        )
        # run-2 drift
        conn.execute(
            "INSERT INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, status, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-2", fund_code, "style_drift", "风格漂移", "stability", "active", 0.8),
        )
        # run-3 recent_shift
        conn.execute(
            "INSERT INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, status, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-3", fund_code, "style_recent_shift", "近期风格切换", "stability", "active", 0.7),
        )
        conn.commit()


def test_style_history_timeline_order_and_summary(tmp_path: Path) -> None:
    """timeline 应按时间正序，每条带 summary 收敛值。"""
    db = tmp_path / "style_history.sqlite"
    _seed_style_history(db)
    reader = LabelRunReader(db)
    history = reader.get_fund_style_history("000001")

    # 三次 run，timeline 应按时间正序（run-1 -> run-2 -> run-3）
    assert len(history["timeline"]) == 3
    runs = [t["run_id"] for t in history["timeline"]]
    assert runs == ["run-1", "run-2", "run-3"]
    # 每条 timeline 节点的 summary
    assert history["timeline"][0]["summary"] == "stable"
    assert history["timeline"][1]["summary"] == "drift"
    assert history["timeline"][2]["summary"] == "recent_shift"
    # current 应指向最新
    assert history["current"] is not None
    assert history["current"]["run_id"] == "run-3"
    # 计数
    assert history["stable_run_count"] == 1
    assert history["drift_run_count"] == 1
    assert history["shift_run_count"] == 1
    # 趋势：当前 recent_shift，趋势为 shifting
    assert history["trend"] == "shifting"


def test_style_history_trend_stable_when_current_stable(tmp_path: Path) -> None:
    """当前是 stable 且无后续恶化 → trend = stable。"""
    db = tmp_path / "stable.sqlite"
    writer = LabelRunWriter(db)
    writer.ensure_schema()
    with sqlite3.connect(db) as conn:
        for i in range(1, 5):
            conn.execute(
                "INSERT INTO label_runs (run_id, run_at, data_as_of, rule_version, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"run-{i}", f"2026-0{i} 00:00:00", f"2026-0{i - 1}", "v1", "succeeded"),
            )
            conn.execute(
                "INSERT INTO fund_label_results "
                "(run_id, fund_code, label_code, label_name, category, status, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"run-{i}", "000001", "style_stable", "风格稳定", "stability", "active", 0.9),
            )
        conn.commit()
    reader = LabelRunReader(db)
    history = reader.get_fund_style_history("000001")
    assert history["stable_run_count"] == 4
    assert history["trend"] == "stable"


def test_style_history_empty_fund(tmp_path: Path) -> None:
    """无任何标签记录时，timeline 为空、trend = insufficient_data。"""
    db = tmp_path / "empty.sqlite"
    writer = LabelRunWriter(db)
    writer.ensure_schema()
    reader = LabelRunReader(db)
    history = reader.get_fund_style_history("no-such-fund")
    assert history["timeline"] == []
    assert history["current"] is None
    assert history["trend"] == "insufficient_data"
    assert history["stable_run_count"] == 0


def test_style_history_embedded_in_fund_report(tmp_path: Path) -> None:
    """get_fund_report 应内嵌 style_history 字段。"""
    db = tmp_path / "report.sqlite"
    _seed_style_history(db)
    # 还需在 run-3 上加一个 active 普通标签，才能 get_fund_labels 返回非 None
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, status, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-3", "000001", "deep_value", "深度价值", "style", "active", 0.6),
        )
        conn.commit()

    reader = LabelRunReader(db)
    report = reader.get_fund_report("run-3", "000001")
    assert report is not None
    assert "style_history" in report
    sh = report["style_history"]
    assert sh["stable_run_count"] == 1
    assert sh["shift_run_count"] == 1
    # summary 内应有 style_* 计数
    assert "style_stable_run_count" in report["summary"]
    assert "style_drift_run_count" in report["summary"]
    assert "style_recent_shift_run_count" in report["summary"]


def test_style_history_limit(tmp_path: Path) -> None:
    """limit 参数应限制 timeline 长度。"""
    db = tmp_path / "limit.sqlite"
    writer = LabelRunWriter(db)
    writer.ensure_schema()
    with sqlite3.connect(db) as conn:
        for i in range(1, 6):
            conn.execute(
                "INSERT INTO label_runs (run_id, run_at, data_as_of, rule_version, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"run-{i}", f"2026-0{i} 00:00:00", f"2026-0{i - 1}", "v1", "succeeded"),
            )
            conn.execute(
                "INSERT INTO fund_label_results "
                "(run_id, fund_code, label_code, label_name, category, status, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"run-{i}", "000001", "style_stable", "风格稳定", "stability", "active", 0.9),
            )
        conn.commit()
    reader = LabelRunReader(db)
    history = reader.get_fund_style_history("000001", limit=3)
    assert len(history["timeline"]) == 3
    # timeline_asc 仅保留后 3 个：run-3, run-4, run-5
    assert [t["run_id"] for t in history["timeline"]] == ["run-3", "run-4", "run-5"]
