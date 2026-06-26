from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

from app.factors.equity_contributions import build_equity_style_contributions
from app.label_engine.engine import RuleConfig


def test_build_equity_style_contributions_emits_matched_stock_rows():
    rows = build_equity_style_contributions(
        fund_code="000001",
        report_date="2025-12-31",
        holdings=[
            {"stock_code": "600001", "stock_name": "低估股票", "weight": 0.20},
            {"stock_code": "600002", "stock_name": "红利股票", "weight": 0.15},
            {"stock_code": "600003", "stock_name": "普通股票", "weight": 0.10},
        ],
        stock_factors=[
            {"stock_code": "600001", "pb": 1.1, "valuation_percentile": 0.2, "as_of_date": "2026-06-23"},
            {"stock_code": "600002", "dividend_yield": 0.04, "as_of_date": "2026-06-23"},
            {"stock_code": "600003", "pb": 4.0, "valuation_percentile": 0.8, "dividend_yield": 0.01, "as_of_date": "2026-06-23"},
        ],
        rule_config=RuleConfig(),
    )

    assert [(r.stock_code, r.style_code, r.contribution_weight) for r in rows] == [
        ("600001", "deep_value", 0.20),
        ("600002", "dividend_steady", 0.15),
    ]


def test_build_equity_style_contributions_emits_multiple_styles_for_one_stock():
    rows = build_equity_style_contributions(
        fund_code="000002",
        report_date="2025-12-31",
        holdings=[
            {"stock_code": "600010", "stock_name": "全能股票", "weight": 0.12},
        ],
        stock_factors=[
            {
                "stock_code": "600010",
                "pb": 1.0,
                "valuation_percentile": 0.1,
                "roe": 0.20,
                "revenue_growth": 0.18,
                "dividend_yield": 0.05,
                "as_of_date": "2026-06-23",
            },
        ],
        rule_config=RuleConfig(),
    )

    style_codes = {r.style_code for r in rows}
    assert style_codes == {"deep_value", "quality_growth", "dividend_steady"}
    for row in rows:
        assert row.matched == 1
        assert row.contribution_weight == 0.12
        assert row.factor_as_of_date == "2026-06-23"
        assert json.loads(row.factor_values_json)
        assert json.loads(row.rule_snapshot_json)


def test_build_equity_style_contributions_returns_empty_without_inputs():
    assert build_equity_style_contributions(
        fund_code="000003",
        report_date=None,
        holdings=[],
        stock_factors=[],
        rule_config=RuleConfig(),
    ) == []


def _load_report_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "generate_equity_style_contribution_report.py"
    )
    spec = importlib.util.spec_from_file_location("equity_style_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_equity_style_contribution_report_lists_top_stocks(tmp_path: Path) -> None:
    db = tmp_path / "out.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE fund_label_results (
            run_id TEXT, fund_code TEXT, label_code TEXT, label_name TEXT,
            category TEXT, confidence REAL, status TEXT
        );
        CREATE TABLE fund_equity_style_contributions (
            fund_code TEXT, report_date TEXT, stock_code TEXT, stock_name TEXT,
            weight REAL, style_code TEXT, style_name TEXT, matched INTEGER,
            contribution_weight REAL, factor_values_json TEXT,
            rule_snapshot_json TEXT, factor_as_of_date TEXT, source TEXT,
            computed_at TEXT
        );
        INSERT INTO fund_label_results VALUES
            ('run1','000001','dividend_steady','红利稳健','style',0.9,'active');
        INSERT INTO fund_equity_style_contributions VALUES
            ('000001','2025-12-31','600002','红利股票A',0.082,'dividend_steady',
             '红利稳健',1,0.082,'{}','{}','2026-06-23','test','now'),
            ('000001','2025-12-31','600003','红利股票B',0.065,'dividend_steady',
             '红利稳健',1,0.065,'{}','{}','2026-06-23','test','now');
        """
    )
    conn.commit()
    conn.close()

    module = _load_report_module()
    out_path = tmp_path / "report.md"
    module.generate_report(db_path=str(db), run_id="run1", out_path=str(out_path))

    text = out_path.read_text(encoding="utf-8")
    assert "dividend_steady" in text
    assert "红利股票A" in text
