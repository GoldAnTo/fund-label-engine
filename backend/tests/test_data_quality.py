"""数据质量巡检（异常值/报告期错配/覆盖率/概览）测试。

覆盖：
- inspect_nav_return_outliers：离群值检测
- inspect_holding_weight_outliers：权重超 30% 或负
- inspect_holding_count_outliers：单期持仓数 > 阈值
- inspect_holding_report_period_coverage：最近一期覆盖率
- collect_overview：综合概览字段
- 集成：render_data_quality_report 端到端
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from scripts.data_quality_inspection import (
    InspectionFinding,
    collect_overview,
    inspect_holding_count_outliers,
    inspect_holding_report_period_coverage,
    inspect_holding_weight_outliers,
    inspect_nav_return_outliers,
)


def _seed_minimal_db(path: Path) -> None:
    """构造一个最小可用的 source DB schema。"""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE fund_profiles (
            fund_code TEXT PRIMARY KEY,
            fund_name TEXT NOT NULL,
            fund_type TEXT NOT NULL
        );
        CREATE TABLE nav_history (
            fund_code TEXT NOT NULL,
            nav_date TEXT NOT NULL,
            nav REAL,
            adjusted_nav REAL,
            daily_return REAL,
            PRIMARY KEY (fund_code, nav_date)
        );
        CREATE TABLE stock_holdings (
            fund_code TEXT,
            report_period TEXT,
            stock_code TEXT,
            stock_name TEXT,
            net_value_ratio REAL,
            weight REAL,
            market TEXT,
            rank
        );
        CREATE INDEX idx_sh_fund ON stock_holdings(fund_code);
        """
    )
    conn.commit()
    conn.close()


def test_nav_return_outliers_basic(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    today = date.today()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO fund_profiles VALUES (?, ?, ?)",
        ("000001", "基金A", "股票型"),
    )
    # 正常收益
    for i in range(5):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000001", (today - timedelta(days=i)).isoformat(), 1.0, 1.0, 0.01),
        )
    # 离群：-50% 一次
    conn.execute(
        "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
        ("000001", (today - timedelta(days=10)).isoformat(), 1.0, 1.0, -0.5),
    )
    # 离群：+80% 一次
    conn.execute(
        "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
        ("000001", (today - timedelta(days=11)).isoformat(), 1.0, 1.0, 0.8),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_nav_return_outliers(conn, threshold=0.20)
    conn.close()
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "warning"
    assert "2 条" in f.title
    assert any("-50" in s for s in f.samples)
    assert any("80" in s for s in f.samples)


def test_nav_return_outliers_no_issue(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    today = date.today()
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO fund_profiles VALUES (?, ?, ?)", ("000001", "基金A", "股票型"))
    for i in range(3):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000001", (today - timedelta(days=i)).isoformat(), 1.0, 1.0, 0.005),
        )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_nav_return_outliers(conn, threshold=0.20)
    conn.close()
    assert findings == []


def test_holding_weight_outliers(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    conn = sqlite3.connect(db)
    # 正常 5%
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "2025-12-31", "600000", "A", None, 0.05, "上海", 1),
    )
    # 异常 50%
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "2025-12-31", "600001", "B", None, 0.5, "上海", 2),
    )
    # 异常 负值
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "2025-12-31", "600002", "C", None, -0.1, "上海", 3),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_holding_weight_outliers(conn, threshold=0.30)
    conn.close()
    assert len(findings) == 1
    f = findings[0]
    assert "2 条" in f.title  # 0.5 和 -0.1
    assert f.severity == "warning"


def test_holding_count_outliers(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    conn = sqlite3.connect(db)
    # 150 只持仓
    for i in range(150):
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("000001", "2025-12-31", f"60{i:04d}", f"X{i}", None, 0.001, "上海", i),
        )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_holding_count_outliers(conn, threshold=100)
    conn.close()
    assert len(findings) == 1
    f = findings[0]
    assert "1 个" in f.title
    assert "150只" in "".join(f.samples)


def test_report_period_coverage_healthy(tmp_path: Path) -> None:
    """最近一期覆盖率 ≥ 阈值，无 finding。"""
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    conn = sqlite3.connect(db)
    for period in ("2025-06-30", "2025-09-30", "2025-12-31"):
        for fc in ("000001", "000002", "000003"):
            conn.execute(
                "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (fc, period, "600000", "A", None, 0.1, "上海", 1),
            )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_holding_report_period_coverage(conn, min_coverage_ratio=0.6)
    conn.close()
    assert findings == []


def test_report_period_coverage_warning(tmp_path: Path) -> None:
    """最近一期覆盖 5 只中的 2 只（40%），在 40%-60% 区间 → warning。"""
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    conn = sqlite3.connect(db)
    # 旧期覆盖 5 只
    for fc in ("000001", "000002", "000003", "000004", "000005"):
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fc, "2025-09-30", "600000", "A", None, 0.1, "上海", 1),
        )
    # 新期只有 2 只 = 40%
    for fc in ("000001", "000002"):
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fc, "2025-12-31", "600000", "A", None, 0.1, "上海", 1),
        )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_holding_report_period_coverage(conn, min_coverage_ratio=0.6)
    conn.close()
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "warning"
    assert "2025-12-31" in f.title
    assert "40%" in f.title


def test_report_period_coverage_critical(tmp_path: Path) -> None:
    """最近一期 < 40% → critical。"""
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    conn = sqlite3.connect(db)
    for fc in ("000001", "000002", "000003", "000004", "000005"):
        conn.execute(
            "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fc, "2025-09-30", "600000", "A", None, 0.1, "上海", 1),
        )
    # 新期只有 1 只（20% < 40%）
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "2025-12-31", "600000", "A", None, 0.1, "上海", 1),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    findings = inspect_holding_report_period_coverage(conn, min_coverage_ratio=0.6)
    conn.close()
    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_collect_overview_basic(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    _seed_minimal_db(db)
    today = date.today()
    conn = sqlite3.connect(db)
    # 3 只基金，只有 2 只 NAV，1 只持仓
    for fc in ("000001", "000002", "000003"):
        conn.execute("INSERT INTO fund_profiles VALUES (?, ?, ?)", (fc, f"基金{fc}", "股票型"))
    for i in range(3):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000001", (today - timedelta(days=i)).isoformat(), 1.0, 1.0, 0.01),
        )
    for i in range(3):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000002", (today - timedelta(days=i)).isoformat(), 1.0, 1.0, 0.01),
        )
    conn.execute(
        "INSERT INTO stock_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("000001", "2025-12-31", "600000", "A", None, 0.1, "上海", 1),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    overview = collect_overview(conn)
    conn.close()

    assert overview["total_funds"] == 3
    assert overview["nav_covered_funds"] == 2
    assert overview["nav_missing_funds"] == 1
    assert overview["holding_covered_funds"] == 1
    assert overview["latest_nav_date"] == today.isoformat()
    assert overview["latest_holding_period"] == "2025-12-31"


def test_render_data_quality_report_e2e(tmp_path: Path) -> None:
    """端到端：CLI 渲染 Markdown + JSON。"""
    db = tmp_path / "e2e.sqlite"
    _seed_minimal_db(db)
    today = date.today()
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO fund_profiles VALUES (?, ?, ?)", ("000001", "基金A", "股票型"))
    # NAV 正常
    for i in range(3):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000001", (today - timedelta(days=i)).isoformat(), 1.0, 1.0, 0.005),
        )
    conn.commit()
    conn.close()

    report_path = tmp_path / "dq.md"
    json_path = tmp_path / "dq.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_data_quality_report.py",
            "--db", str(db),
            "--report", str(report_path),
            "--json", str(json_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert report_path.exists()
    assert json_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "# 数据质量综合报告" in content
    assert "## 概览" in content
    assert "## 检查发现" in content
    assert "## 修复优先级建议" in content
    assert "## 复现命令" in content
    assert "基金池 | 1 只" in content
    import json as _json

    payload = _json.loads(json_path.read_text(encoding="utf-8"))
    assert "overview" in payload
    assert "summary" in payload
    assert "findings" in payload
    assert payload["overview"]["total_funds"] == 1


def test_render_data_quality_report_exit_code_2_on_critical(tmp_path: Path) -> None:
    """有 critical finding 时 exit 2。"""
    db = tmp_path / "crit.sqlite"
    _seed_minimal_db(db)
    today = date.today()
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO fund_profiles VALUES (?, ?, ?)", ("000001", "基金A", "股票型"))
    # 大量离群收益（>50 条会触发 critical）
    for i in range(60):
        conn.execute(
            "INSERT INTO nav_history VALUES (?, ?, ?, ?, ?)",
            ("000001", (today - timedelta(days=i + 1)).isoformat(), 1.0, 1.0, 0.5 if i % 2 == 0 else -0.5),
        )
    conn.commit()
    conn.close()

    report_path = tmp_path / "crit.md"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_data_quality_report.py",
            "--db", str(db),
            "--report", str(report_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert result.returncode == 2
    assert "critical=1" in result.stdout
