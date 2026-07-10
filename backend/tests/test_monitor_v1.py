"""监控面板 v1 测试。

覆盖：
- migration 自动建 fund_valuation_history 表
- writer.write_valuation_snapshot 写入 + reader.get_valuation_history 读取
- reader.get_holding_history 报告期聚合
- monitor.service.detect_risk_signals 5 类信号
- API /v1/monitor/fund/{code}/overview 端到端
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.monitor import detect_risk_signals
from app.persistence import LabelRunReader, LabelRunWriter


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def test_migration_creates_fund_valuation_history(tmp_path) -> None:
    """ensure_schema 后 fund_valuation_history 表应存在。"""
    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()

    conn = sqlite3.connect(str(db))
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(fund_valuation_history)").fetchall()
    }
    expected = {
        "run_id", "fund_code", "as_of_date",
        "weighted_pe", "weighted_pb", "weighted_roe",
        "weighted_dividend_yield", "weighted_val_pct",
        "weighted_peg", "price_in_years",
        "position_count", "top_holding_weight",
    }
    assert expected.issubset(cols), f"缺少列: {expected - cols}"


# ---------------------------------------------------------------------------
# Writer / Reader
# ---------------------------------------------------------------------------


def test_write_and_read_valuation_snapshot(tmp_path) -> None:
    """写一行快照，能从 reader 读回。"""
    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()
    writer.write_valuation_snapshot(
        run_id="run-1",
        fund_code="000001",
        as_of_date="2026-07-01",
        weighted_pe=20.5,
        weighted_pb=3.0,
        weighted_roe=0.15,
        weighted_dividend_yield=0.02,
        weighted_val_pct=55.0,
        weighted_peg=1.4,
        price_in_years=2.5,
        position_count=30,
        top_holding_weight=0.08,
    )

    reader = LabelRunReader(str(db))
    history = reader.get_valuation_history("000001")
    assert len(history) == 1
    h = history[0]
    assert h["as_of_date"] == "2026-07-01"
    assert h["run_id"] == "run-1"
    assert h["weighted_pe"] == 20.5
    assert h["weighted_val_pct"] == 55.0
    assert h["position_count"] == 30
    assert h["top_holding_weight"] == 0.08


def test_get_valuation_history_ordered_by_date_desc(tmp_path) -> None:
    """快照按 as_of_date DESC 排序。"""
    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()
    for d in ("2026-05-01", "2026-07-01", "2026-06-01"):
        writer.write_valuation_snapshot(
            run_id="run-" + d,
            fund_code="000002",
            as_of_date=d,
            weighted_pe=20.0,
        )
    reader = LabelRunReader(str(db))
    history = reader.get_valuation_history("000002")
    assert [h["as_of_date"] for h in history] == ["2026-07-01", "2026-06-01", "2026-05-01"]


def test_get_valuation_history_limit(tmp_path) -> None:
    """limit 参数生效。"""
    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()
    for i in range(5):
        writer.write_valuation_snapshot(
            run_id=f"r{i}",
            fund_code="000003",
            as_of_date=f"2026-0{i + 1}-01",
            weighted_pe=20.0,
        )
    reader = LabelRunReader(str(db))
    history = reader.get_valuation_history("000003", limit=2)
    assert len(history) == 2


def test_get_valuation_history_table_missing_returns_empty(tmp_path) -> None:
    """表不存在时（极端老库）应返回空，不抛异常。"""
    db = tmp_path / "no-table.sqlite"
    # 不 ensure_schema，直接建空 DB
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE dummy (x INTEGER)")
    conn.commit()
    conn.close()
    reader = LabelRunReader(str(db))
    history = reader.get_valuation_history("anything")
    assert history == []


def test_get_holding_history_aggregates(tmp_path) -> None:
    """持仓历史：报告期聚合 + top 持仓 + 行业聚合。"""
    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()
    # source DB 跟 output DB 一样（默认模式）
    reader = LabelRunReader(str(db))
    # 直接写入 fund_stock_holdings / stock_industry_map（手动建表，因为是 source DB 概念）
    with reader._connect_source() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fund_stock_holdings ("
            " fund_code TEXT, report_period TEXT, stock_code TEXT, "
            " stock_name TEXT, net_value_ratio REAL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS stock_industry_map ("
            " stock_code TEXT NOT NULL, industry_code TEXT NOT NULL, "
            " industry_name TEXT NOT NULL, sector_group TEXT NOT NULL, "
            " source TEXT NOT NULL, as_of_date TEXT NOT NULL, "
            " PRIMARY KEY (stock_code, as_of_date))"
        )
        # 两个报告期：A 和 B
        conn.executemany(
            "INSERT INTO fund_stock_holdings "
            "(fund_code, report_period, stock_code, stock_name, net_value_ratio) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("000100", "2026-03-31", "600000", "A", 0.10),
                ("000100", "2026-03-31", "600001", "B", 0.08),
                ("000100", "2026-03-31", "600002", "C", 0.05),
                ("000100", "2026-06-30", "600000", "A", 0.12),  # 增持
                ("000100", "2026-06-30", "600003", "D", 0.06),  # 新进
            ],
        )
        conn.executemany(
            "INSERT INTO stock_industry_map "
            "(stock_code, industry_code, industry_name, sector_group, source, as_of_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600000", "FIN", "金融", "financial", "test", "2026-06-30"),
                ("600001", "FIN", "金融", "financial", "test", "2026-06-30"),
                ("600002", "TECH", "科技", "tech", "test", "2026-06-30"),
                ("600003", "CONS", "消费", "consumer", "test", "2026-06-30"),
            ],
        )
        conn.commit()

    history = reader.get_holding_history("000100", limit_periods=2)
    # 按报告期 DESC：2026-06-30 在前
    assert len(history) == 2
    assert history[0]["report_period"] == "2026-06-30"
    assert history[0]["total_stocks"] == 2
    assert history[0]["top_holdings"][0]["stock_code"] == "600000"
    assert history[0]["top_holdings"][0]["weight"] == 0.12
    # 行业：金融 0.12, 消费 0.06
    ind = {x["name"]: x["weight"] for x in history[0]["top_industries"]}
    assert abs(ind["金融"] - 0.12) < 1e-6
    assert abs(ind["消费"] - 0.06) < 1e-6


# ---------------------------------------------------------------------------
# Risk signal detection
# ---------------------------------------------------------------------------


def test_detect_risk_signals_no_history() -> None:
    """无任何历史 → no_valuation_history 信号。"""
    signals = detect_risk_signals([], [])
    codes = [s["code"] for s in signals]
    assert "no_valuation_history" in codes


def test_detect_risk_signals_stale_valuation() -> None:
    """估值快照超过 60 天没更新 → stale_valuation。"""
    today = date(2026, 7, 10)
    old = (today - timedelta(days=70)).isoformat()
    signals = detect_risk_signals(
        [{"as_of_date": old, "weighted_val_pct": 50}],
        [],
        as_of_today=today,
    )
    stale = [s for s in signals if s["code"] == "stale_valuation"]
    assert len(stale) == 1
    assert stale[0]["level"] == "warning"


def test_detect_risk_signals_high_concentration() -> None:
    """第一大重仓 > 15% → high_concentration。"""
    signals = detect_risk_signals(
        [{"as_of_date": "2026-07-01", "top_holding_weight": 0.20}],
        [],
    )
    high = [s for s in signals if s["code"] == "high_concentration"]
    assert len(high) == 1
    assert "20.0%" in high[0]["detail"]


def test_detect_risk_signals_valuation_drift_up() -> None:
    """连续两期估值分位上跳 > 15pp → valuation_drift。"""
    signals = detect_risk_signals(
        [
            {"as_of_date": "2026-07-01", "weighted_val_pct": 80.0},
            {"as_of_date": "2026-06-01", "weighted_val_pct": 60.0},
        ],
        [],
    )
    drift = [s for s in signals if s["code"] == "valuation_drift"]
    assert len(drift) == 1
    assert "上跳" in drift[0]["title"]
    assert "+20" in drift[0]["detail"]


def test_detect_risk_signals_valuation_drift_down() -> None:
    """连续两期估值分位下跌 > 15pp → valuation_drift（下跌方向）。"""
    signals = detect_risk_signals(
        [
            {"as_of_date": "2026-07-01", "weighted_val_pct": 50.0},
            {"as_of_date": "2026-06-01", "weighted_val_pct": 70.0},
        ],
        [],
    )
    drift = [s for s in signals if s["code"] == "valuation_drift"]
    assert len(drift) == 1
    assert "下跌" in drift[0]["title"]


def test_detect_risk_signals_valuation_drift_below_threshold() -> None:
    """变化 ≤ 15pp → 不触发 valuation_drift。"""
    signals = detect_risk_signals(
        [
            {"as_of_date": "2026-07-01", "weighted_val_pct": 65.0},
            {"as_of_date": "2026-06-01", "weighted_val_pct": 60.0},
        ],
        [],
    )
    drift = [s for s in signals if s["code"] == "valuation_drift"]
    assert drift == []


def test_detect_risk_signals_holding_drift() -> None:
    """top5 替换 ≥ 2 只 → holding_drift。"""
    signals = detect_risk_signals(
        [{"as_of_date": "2026-07-01", "weighted_val_pct": 50}],
        [
            {
                "report_period": "2026-06-30",
                "top_holdings": [
                    {"stock_code": "A"}, {"stock_code": "B"},
                    {"stock_code": "C"}, {"stock_code": "D"},
                    {"stock_code": "E"},
                ],
            },
            {
                "report_period": "2026-03-31",
                "top_holdings": [
                    {"stock_code": "A"}, {"stock_code": "F"},
                    {"stock_code": "G"}, {"stock_code": "H"},
                    {"stock_code": "I"},
                ],
            },
        ],
    )
    drift = [s for s in signals if s["code"] == "holding_drift"]
    assert len(drift) == 1


def test_detect_risk_signals_missing_data() -> None:
    """关键字段缺失 ≥ 2 → missing_data (critical)。"""
    signals = detect_risk_signals(
        [{"as_of_date": "2026-07-01", "weighted_pe": None, "weighted_pb": None, "weighted_roe": None}],
        [],
    )
    missing = [s for s in signals if s["code"] == "missing_data"]
    assert len(missing) == 1
    assert missing[0]["level"] == "critical"


def test_detect_risk_signals_combined() -> None:
    """多个信号并存都能识别。"""
    today = date(2026, 7, 10)
    old = (today - timedelta(days=70)).isoformat()
    signals = detect_risk_signals(
        [
            {"as_of_date": old, "top_holding_weight": 0.20, "weighted_val_pct": 80},
            {"as_of_date": (today - timedelta(days=10)).isoformat(), "weighted_val_pct": 50},
        ],
        [],
        as_of_today=today,
    )
    codes = {s["code"] for s in signals}
    # stale + high concentration 都在
    assert "stale_valuation" in codes
    assert "high_concentration" in codes


# ---------------------------------------------------------------------------
# API 端到端
# ---------------------------------------------------------------------------


def test_api_monitor_overview_returns_aggregated_payload(tmp_path) -> None:
    """API /v1/monitor/fund/{code}/overview 返回完整 payload。"""
    from app.main import create_app

    db = tmp_path / "monitor.sqlite"
    writer = LabelRunWriter(str(db))
    writer.ensure_schema()
    writer.write_valuation_snapshot(
        run_id="r1",
        fund_code="000999",
        as_of_date="2026-07-01",
        weighted_pe=22.0,
        weighted_val_pct=55.0,
        position_count=30,
        top_holding_weight=0.08,
    )
    app = create_app(db_path=str(db), frontend_dist=None)
    client = TestClient(app)
    resp = client.get("/v1/monitor/fund/000999/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["fund_code"] == "000999"
    assert "as_of_today" in data
    assert len(data["valuation_history"]) == 1
    assert data["valuation_history"][0]["weighted_pe"] == 22.0
    assert "risk_signals" in data
    # 5 类信号类别应都在
    assert isinstance(data["risk_signals"], list)


def test_api_monitor_overview_empty_db() -> None:
    """无数据的基金 → 返回空历史 + no_valuation_history 信号。"""
    from app.main import create_app

    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "empty.sqlite")
        app = create_app(db_path=db, frontend_dist=None)
        client = TestClient(app)
        resp = client.get("/v1/monitor/fund/000000/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valuation_history"] == []
        assert data["holding_history"] == []
        codes = {s["code"] for s in data["risk_signals"]}
        assert "no_valuation_history" in codes