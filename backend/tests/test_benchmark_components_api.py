"""GET /v1/runs/{run_id}/funds/{fund_code}/benchmark-components 单测。

覆盖：组件列表 / 状态细分 / 权重覆盖率。
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def _seed_source_db(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE funds_master (
            fund_code TEXT PRIMARY KEY,
            fund_name TEXT NOT NULL,
            fund_type TEXT,
            benchmark_text TEXT
        );
        CREATE TABLE benchmark_components (
            fund_code TEXT,
            component_order INTEGER,
            component_code TEXT,
            component_name TEXT,
            weight REAL,
            source_text TEXT,
            status TEXT,
            reason TEXT,
            PRIMARY KEY (fund_code, component_order)
        );
        CREATE TABLE benchmark_component_returns (
            component_code TEXT,
            trade_date TEXT,
            daily_return REAL,
            PRIMARY KEY (component_code, trade_date)
        );
        CREATE TABLE benchmark_returns (
            fund_code TEXT,
            trade_date TEXT,
            benchmark_return REAL,
            PRIMARY KEY (fund_code, trade_date)
        );
        """
    )
    conn.executemany(
        "INSERT INTO benchmark_components VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("000001", 1, "HS300", "沪深300", 0.6, "沪深300指数收益率×60%", "resolved", "index"),
            ("000001", 2, "HBI", "中证港股通", 0.2, "中证港股通综合指数×20%", "resolved", "index"),
            ("000001", 3, "DEBT", "中债-国债", 0.2, "中债-国债总财富指数×20%", "resolved", "synthetic"),
            ("000001", 4, "GOLD", "黄金", 0.0, "黄金×0%", "unresolved", "missing_index"),
        ],
    )
    # 收益：HS300、HBI、DEBT 有
    conn.executemany(
        "INSERT INTO benchmark_component_returns VALUES (?, ?, ?)",
        [
            ("HS300", "2026-01-02", 0.01),
            ("HBI", "2026-01-02", 0.005),
            ("DEBT", "2026-01-02", 0.0),
        ],
    )
    # 基金总收益已合成
    conn.execute(
        "INSERT INTO benchmark_returns VALUES (?, ?, ?)",
        ("000001", "2026-01-02", 0.006),
    )
    conn.commit()
    conn.close()


def _build_app_with_source_db(source_db: Path) -> TestClient:
    from app.main import create_app

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        result_db = Path(tmp.name)
    app = create_app(db_path=result_db, source_db_path=source_db, frontend_dist=None)
    return TestClient(app)


def test_benchmark_components_basic(tmp_path: Path) -> None:
    source_db = tmp_path / "source.sqlite"
    _seed_source_db(source_db)
    client = _build_app_with_source_db(source_db)
    # 用任意 run_id（接口不校验 run 存在，仅当未发现 fund 时）
    resp = client.get("/v1/runs/run-x/funds/000001/benchmark-components")
    assert resp.status_code == 200
    data = resp.json()
    assert data["fund_code"] == "000001"
    assert data["has_benchmark_returns"] is True
    assert data["benchmark_returns_count"] == 1
    components = data["components"]
    assert len(components) == 4
    # GOLD 未解析
    unresolved = [c for c in components if c["status"] != "resolved"]
    assert len(unresolved) == 1
    assert unresolved[0]["component_code"] == "GOLD"
    # 全部组件都有收益（HS300/HBI/DEBT 直接有；GOLD 权重为 0 且 resolved 故不算）
    # unresolved_count 包含 status != resolved 或 has_returns=False
    assert data["unresolved_count"] == 1
    assert data["unresolved_unresolved_count"] == 1
    assert data["unresolved_missing_returns_count"] == 0
    # 权重覆盖率 = (0.6+0.2+0.2) / 1.0 = 100%
    assert data["coverage_pct"] == 100.0
    assert data["coverage_basis"] == "weight"


def test_benchmark_components_missing_fund(tmp_path: Path) -> None:
    source_db = tmp_path / "source.sqlite"
    _seed_source_db(source_db)
    client = _build_app_with_source_db(source_db)
    resp = client.get("/v1/runs/run-x/funds/999999/benchmark-components")
    assert resp.status_code == 200
    data = resp.json()
    assert data["components"] == []
    assert data["has_benchmark_returns"] is False
    assert data["benchmark_returns_count"] == 0
    assert data["unresolved_count"] == 0
    assert data["coverage_pct"] == 0.0


def test_benchmark_components_partial_returns(tmp_path: Path) -> None:
    """组件 resolved 但 has_returns=False（缺收益源）→ coverage 下降。"""
    source_db = tmp_path / "source.sqlite"
    _seed_source_db(source_db)
    # 删除 HBI 的收益，制造"解析成功但缺收益源"
    conn = sqlite3.connect(source_db)
    conn.execute("DELETE FROM benchmark_component_returns WHERE component_code = 'HBI'")
    conn.execute("DELETE FROM benchmark_returns")  # 整体未合成
    conn.commit()
    conn.close()

    client = _build_app_with_source_db(source_db)
    resp = client.get("/v1/runs/run-x/funds/000001/benchmark-components")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_benchmark_returns"] is False
    # HBI 状态 resolved 但 has_returns=False；GOLD status=unresolved
    # unresolved_count 包含两者
    assert data["unresolved_count"] == 2
    assert data["unresolved_unresolved_count"] == 1
    assert data["unresolved_missing_returns_count"] == 1
    # coverage: (0.6 + 0.2) / 1.0 = 80% （HS300+DEBT）
    assert data["coverage_pct"] == 80.0
