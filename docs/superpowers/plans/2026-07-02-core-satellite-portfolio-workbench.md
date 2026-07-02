# Core Satellite Portfolio Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current portfolio matrix into a usable core-satellite equity fund portfolio workbench: calibrated fund roles, clear data blockers, risk sizing constraints, draft portfolio output, and an operator UI.

**Architecture:** Keep the label engine as the evidence layer and keep portfolio construction as a separate derived layer. Portfolio roles come from `config/portfolio_roles.v1.json`; human calibration decisions and sizing constraints are added on top, then exposed through reports, API, exports, and frontend views. The system produces candidate pools and draft weights for research review, not buy/sell recommendations or trade execution.

**Tech Stack:** Python 3.13, SQLite, pytest, FastAPI, existing `LabelRunReader` / export patterns, React frontend, existing report scripts under `scripts/`.

---

## Current Baseline

Verified on the real run from `/tmp/fle-run/output.sqlite`:

- `run_id`: `349ee38559864bdd8b7968532452ba03`
- total matrix rows: 142
- `eligible`: 9
- `observe`: 133
- `review_required`: 0
- top watch reasons:
  - `style_pending_rule_definition`: 122
  - `benchmark_data_missing`: 28
  - `style_exposure_observe`: 6
  - `sector_mapping_insufficient`: 1
- current role quality gaps:
  - `eligible_with_allocation_risk_review`: 6
  - `core_candidate_with_core_risk_review`: 10
  - `active_equity_waiting_style_rule`: 66
  - `benchmark_data_missing`: 28

The first implementation target is not "more labels." The first target is to make the existing labels trustworthy for portfolio workflow decisions.

## Scope Boundaries

### In Scope

- Human role calibration for the 9 current `eligible` funds and high-value `observe` candidates.
- Clear separation between `allocation_status` and final portfolio admission.
- Risk sizing rules that turn high-risk tags into max-weight constraints.
- A dry-run portfolio draft engine for core-satellite candidate weights.
- Markdown and CSV reports that explain every inclusion, exclusion, cap, and warning.
- API and frontend surfaces for review workflow.

### Out Of Scope

- Trading execution.
- Real money recommendations.
- LLM-based final admission.
- Automatic purchase/sell signals.
- Optimizer-heavy mean-variance portfolios before role calibration is stable.

## File Structure

- Modify `config/portfolio_roles.v1.json`
  - Role and tag taxonomy remains the truth source for role derivation.
- Create `config/portfolio_constraints.v1.json`
  - Sizing caps, target role ranges, hard blockers, and score weights.
- Create `backend/app/portfolio/constraints.py`
  - Pure functions for applying caps and computing draft weights.
- Create `backend/app/portfolio/calibration.py`
  - Pure helpers for review decisions and role-quality checks.
- Modify `backend/app/portfolio/roles.py`
  - Add typed validation for role config and keep role derivation deterministic.
- Modify `backend/app/persistence/reader.py`
  - Add methods for calibration decisions and portfolio draft payloads.
- Modify `backend/app/persistence/writer.py`
  - Add write methods for portfolio role reviews.
- Create `backend/app/persistence/migrations/0010_portfolio_role_reviews.sql`
  - Persist human review decisions.
- Modify `backend/app/main.py`
  - Add API routes for role reviews and portfolio draft.
- Modify `backend/app/exporters.py`
  - Include role reviews and portfolio draft sheets in run export.
- Create `scripts/render_portfolio_calibration_report.py`
  - Human-readable calibration queue for eligible and high-value observe funds.
- Create `scripts/render_portfolio_draft_report.py`
  - Dry-run core-satellite portfolio report.
- Modify `scripts/render_portfolio_matrix_report.py`
  - Link matrix output to calibration and draft reports.
- Create `backend/tests/test_portfolio_constraints.py`
  - Unit tests for caps, scores, and draft weights.
- Create `backend/tests/test_portfolio_calibration.py`
  - Unit tests for role review state and quality checks.
- Modify `backend/tests/test_api_v1.py`
  - API tests for role review and draft endpoints.
- Modify `backend/tests/test_exports_and_migrations.py`
  - Migration/export coverage.
- Frontend:
  - Create `frontend/src/pages/PortfolioWorkbenchPage.tsx`
  - Modify `frontend/src/App.tsx`
  - Modify `frontend/src/styles.css`

---

### Task 1: Freeze Baseline And Add Portfolio Calibration Queue

**Purpose:** Before expanding labels, lock the current real-run matrix into an actionable review queue. The output must show exactly which funds need human role decisions and why.

**Files:**
- Create: `scripts/render_portfolio_calibration_report.py`
- Create: `backend/tests/test_portfolio_calibration_report.py`
- Modify: `scripts/render_portfolio_matrix_report.py`

- [ ] **Step 1: Write a failing smoke test for the calibration report**

Create `backend/tests/test_portfolio_calibration_report.py`:

```python
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch
from scripts.seed_sample_db import seed


def test_render_portfolio_calibration_report_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "DELETE FROM fund_label_results WHERE run_id = ? AND fund_code = '000001' "
            "AND label_code IN ('benchmark_data_missing', 'return_window_insufficient', "
            "'style_unlabeled_stock_factors_missing')",
            (run_id,),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO fund_label_results "
            "(run_id, fund_code, label_code, label_name, category, confidence, status) "
            "VALUES (?, '000001', ?, ?, ?, 0.8, 'active')",
            [
                (run_id, "alpha_positive", "Alpha 为正", "relative_benchmark"),
                (run_id, "information_ratio_high", "信息比率较高", "relative_benchmark"),
                (run_id, "manager_tenure_long", "经理任期较长", "manager"),
                (run_id, "quality_growth", "质量成长", "holding_style"),
                (run_id, "tracking_error_high", "跟踪误差较高", "relative_benchmark"),
            ],
        )
        conn.commit()

    out_md = tmp_path / "calibration.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_portfolio_calibration_report.py",
            "--output-db",
            str(db),
            "--out-md",
            str(out_md),
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    text = out_md.read_text(encoding="utf-8")
    assert "wrote" in result.stdout
    assert "# Portfolio Calibration Report" in text
    assert f"run_id: `{run_id}`" in text
    assert "`000001`" in text
    assert "eligible_with_allocation_risk_review" in text
    assert "human_decision_required" in text
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_portfolio_calibration_report.py::test_render_portfolio_calibration_report_smoke -q
```

Expected: FAIL because `scripts/render_portfolio_calibration_report.py` does not exist.

- [ ] **Step 3: Implement the calibration report script**

Create `scripts/render_portfolio_calibration_report.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.persistence.reader import LabelRunReader

RISK_REVIEW_TAGS = {
    "beta_high",
    "drawdown_high",
    "holding_concentration_high",
    "industry_concentration_high",
    "volatility_high",
}


def _join(values: list[str] | None) -> str:
    return ", ".join(values or [])


def _decision_reason(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    if row["allocation_status"] == "eligible":
        reasons.append("eligible_candidate")
    if set(row.get("risk_tags") or []) & RISK_REVIEW_TAGS:
        reasons.append("eligible_with_allocation_risk_review")
    if "core_holding_candidate" in row.get("portfolio_roles", []) and set(row.get("risk_tags") or []) & {"beta_high", "drawdown_high", "volatility_high"}:
        reasons.append("core_candidate_with_core_risk_review")
    if "style_pending_rule_definition" in row.get("watch_reasons", []):
        reasons.append("active_equity_waiting_style_rule")
    if "benchmark_data_missing" in row.get("watch_reasons", []):
        reasons.append("benchmark_data_missing")
    return ", ".join(reasons or ["human_decision_required"])


def render_report(output_db: str, out_md: str, run_id: str | None = None) -> dict[str, Any]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    matrix = reader.get_portfolio_matrix(selected_run_id)
    if matrix is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    rows = [
        row
        for row in matrix["rows"]
        if row["allocation_status"] == "eligible"
        or "core_holding_candidate" in row.get("portfolio_roles", [])
        or "satellite_alpha" in row.get("portfolio_roles", [])
        or "benchmark_data_missing" in row.get("watch_reasons", [])
    ]
    rows = sorted(
        rows,
        key=lambda row: (
            row["allocation_status"] != "eligible",
            "benchmark_data_missing" in row.get("watch_reasons", []),
            row["fund_code"],
        ),
    )

    lines = [
        "# Portfolio Calibration Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"candidate_count: {len(rows)}",
        "",
        "| fund_code | status | roles | return_tags | risk_tags | watch | decision_reason | required_action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        decision_reason = _decision_reason(row)
        required_action = "human_decision_required"
        lines.append(
            f"| `{row['fund_code']}` | `{row['allocation_status']}` | "
            f"{_join(row.get('portfolio_roles'))} | {_join(row.get('return_tags'))} | "
            f"{_join(row.get('risk_tags'))} | {_join(row.get('watch_reasons'))} | "
            f"{decision_reason} | `{required_action}` |"
        )

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "candidate_count": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    summary = render_report(args.output_db, args.out_md, args.run_id)
    print(
        f"wrote {args.out_md} "
        f"(run_id={summary['run_id']}, candidates={summary['candidate_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the calibration report test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_portfolio_calibration_report.py::test_render_portfolio_calibration_report_smoke -q
```

Expected: PASS.

- [ ] **Step 5: Generate the real calibration report**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/render_portfolio_calibration_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/portfolio-calibration-v1-report.md
```

Expected:

```text
wrote reports/phase1-real-run-2026-06-29/portfolio-calibration-v1-report.md
```

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add scripts/render_portfolio_calibration_report.py backend/tests/test_portfolio_calibration_report.py reports/phase1-real-run-2026-06-29/portfolio-calibration-v1-report.md
git commit -m "feat(portfolio): add calibration queue report"
```

---

### Task 2: Persist Human Role Decisions

**Purpose:** The project needs a place to store "this fund is accepted as core," "this is only satellite," or "exclude until data is fixed." Without this, calibration lives in Markdown and cannot drive portfolio construction.

**Files:**
- Create: `backend/app/persistence/migrations/0010_portfolio_role_reviews.sql`
- Modify: `backend/app/persistence/reader.py`
- Modify: `backend/app/persistence/writer.py`
- Modify: `backend/tests/test_exports_and_migrations.py`
- Create: `backend/tests/test_portfolio_calibration.py`

- [ ] **Step 1: Write the migration test**

Add to `backend/tests/test_exports_and_migrations.py`:

```python
def test_migrations_create_portfolio_role_reviews_table(tmp_path: Path) -> None:
    db = tmp_path / "portfolio-role-reviews.sqlite"
    run_migrations(db)

    with sqlite3.connect(db) as conn:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(portfolio_role_reviews)").fetchall()
        }

    assert {
        "run_id",
        "fund_code",
        "role_code",
        "decision",
        "target_bucket",
        "max_weight_pct",
        "rationale",
        "reviewer",
        "reviewed_at",
    }.issubset(cols)
```

- [ ] **Step 2: Run the migration test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_migrations_create_portfolio_role_reviews_table -q
```

Expected: FAIL because `portfolio_role_reviews` does not exist.

- [ ] **Step 3: Add the migration**

Create `backend/app/persistence/migrations/0010_portfolio_role_reviews.sql`:

```sql
CREATE TABLE IF NOT EXISTS portfolio_role_reviews (
    run_id TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    role_code TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('accept', 'reject', 'needs_more_data')
    ),
    target_bucket TEXT NOT NULL CHECK (
        target_bucket IN ('core', 'satellite', 'index_tool', 'cash_buffer', 'exclude')
    ),
    max_weight_pct REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, fund_code, role_code)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_role_reviews_run_bucket
ON portfolio_role_reviews (run_id, target_bucket, decision);
```

- [ ] **Step 4: Run the migration test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_migrations_create_portfolio_role_reviews_table -q
```

Expected: PASS.

- [ ] **Step 5: Write reader/writer tests**

Create `backend/tests/test_portfolio_calibration.py`:

```python
from pathlib import Path

from app.batch import run_batch
from app.persistence.reader import LabelRunReader
from app.persistence.writer import LabelRunWriter
from scripts.seed_sample_db import seed


def test_portfolio_role_review_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)

    writer = LabelRunWriter(db)
    writer.write_portfolio_role_review(
        run_id=run_id,
        fund_code="000001",
        role_code="satellite_alpha",
        decision="accept",
        target_bucket="satellite",
        max_weight_pct=8.0,
        rationale="Alpha role accepted, but cap because drawdown risk exists.",
        reviewer="researcher-a",
    )

    reader = LabelRunReader(db)
    reviews = reader.list_portfolio_role_reviews(run_id)

    assert reviews == [
        {
            "run_id": run_id,
            "fund_code": "000001",
            "role_code": "satellite_alpha",
            "decision": "accept",
            "target_bucket": "satellite",
            "max_weight_pct": 8.0,
            "rationale": "Alpha role accepted, but cap because drawdown risk exists.",
            "reviewer": "researcher-a",
            "reviewed_at": reviews[0]["reviewed_at"],
        }
    ]
```

- [ ] **Step 6: Run the reader/writer test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_portfolio_calibration.py::test_portfolio_role_review_round_trip -q
```

Expected: FAIL because the reader and writer methods do not exist.

- [ ] **Step 7: Add writer method**

In `backend/app/persistence/writer.py`, add:

```python
    def write_portfolio_role_review(
        self,
        *,
        run_id: str,
        fund_code: str,
        role_code: str,
        decision: str,
        target_bucket: str,
        max_weight_pct: float,
        rationale: str,
        reviewer: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO portfolio_role_reviews (
                    run_id, fund_code, role_code, decision, target_bucket,
                    max_weight_pct, rationale, reviewer, reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    run_id,
                    fund_code,
                    role_code,
                    decision,
                    target_bucket,
                    max_weight_pct,
                    rationale,
                    reviewer,
                ),
            )
            conn.commit()
```

- [ ] **Step 8: Add reader method**

In `backend/app/persistence/reader.py`, add:

```python
    def list_portfolio_role_reviews(
        self,
        run_id: str,
        fund_code: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT run_id, fund_code, role_code, decision, target_bucket, "
            "max_weight_pct, rationale, reviewer, reviewed_at "
            "FROM portfolio_role_reviews WHERE run_id = ?"
        )
        params: list[Any] = [run_id]
        if fund_code:
            sql += " AND fund_code = ?"
            params.append(fund_code)
        sql += " ORDER BY fund_code, role_code"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 9: Run reader/writer tests and migration tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_portfolio_calibration.py::test_portfolio_role_review_round_trip \
  backend/tests/test_exports_and_migrations.py::test_migrations_create_portfolio_role_reviews_table \
  -q
```

Expected: PASS.

- [ ] **Step 10: Commit Task 2**

Run:

```bash
git add backend/app/persistence/migrations/0010_portfolio_role_reviews.sql backend/app/persistence/reader.py backend/app/persistence/writer.py backend/tests/test_exports_and_migrations.py backend/tests/test_portfolio_calibration.py
git commit -m "feat(portfolio): persist role calibration decisions"
```

---

### Task 3: Add Role Review API

**Purpose:** Let the frontend and future operators read and write calibration decisions without editing SQLite or Markdown manually.

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api_v1.py`

- [ ] **Step 1: Write API tests**

Add to `backend/tests/test_api_v1.py`:

```python
def test_portfolio_role_reviews_api_round_trip(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    created = client.post(
        f"/v1/runs/{run_id}/portfolio-role-reviews",
        json={
            "fund_code": "000001",
            "role_code": "satellite_alpha",
            "decision": "accept",
            "target_bucket": "satellite",
            "max_weight_pct": 8.0,
            "rationale": "Accept as satellite only.",
            "reviewer": "researcher-a",
        },
    )

    assert created.status_code == 200
    assert created.json()["fund_code"] == "000001"
    assert created.json()["target_bucket"] == "satellite"

    listed = client.get(f"/v1/runs/{run_id}/portfolio-role-reviews")
    assert listed.status_code == 200
    reviews = listed.json()["reviews"]
    assert len(reviews) == 1
    assert reviews[0]["role_code"] == "satellite_alpha"
    assert reviews[0]["max_weight_pct"] == 8.0
```

- [ ] **Step 2: Run API test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_portfolio_role_reviews_api_round_trip -q
```

Expected: FAIL with 404 for the new route.

- [ ] **Step 3: Add request model and routes**

In `backend/app/main.py`, add a Pydantic model near existing request models:

```python
class PortfolioRoleReviewRequest(BaseModel):
    fund_code: str
    role_code: str
    decision: str
    target_bucket: str
    max_weight_pct: float = 0
    rationale: str = ""
    reviewer: str = ""
```

Add routes inside `create_app`:

```python
    @app.get("/v1/runs/{run_id}/portfolio-role-reviews")
    def list_portfolio_role_reviews(run_id: str) -> dict[str, Any]:
        reader = LabelRunReader(db_path)
        run = reader.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "run_id": run_id,
            "reviews": reader.list_portfolio_role_reviews(run_id),
        }

    @app.post("/v1/runs/{run_id}/portfolio-role-reviews")
    def create_portfolio_role_review(
        run_id: str,
        payload: PortfolioRoleReviewRequest,
    ) -> dict[str, Any]:
        reader = LabelRunReader(db_path)
        run = reader.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        writer = LabelRunWriter(db_path)
        writer.write_portfolio_role_review(
            run_id=run_id,
            fund_code=payload.fund_code,
            role_code=payload.role_code,
            decision=payload.decision,
            target_bucket=payload.target_bucket,
            max_weight_pct=payload.max_weight_pct,
            rationale=payload.rationale,
            reviewer=payload.reviewer,
        )
        created = reader.list_portfolio_role_reviews(
            run_id,
            fund_code=payload.fund_code,
        )
        for item in created:
            if item["role_code"] == payload.role_code:
                return item
        raise HTTPException(status_code=500, detail="Review was not persisted")
```

- [ ] **Step 4: Run API test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_portfolio_role_reviews_api_round_trip -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add backend/app/main.py backend/tests/test_api_v1.py
git commit -m "feat(api): add portfolio role review endpoints"
```

---

### Task 4: Add Portfolio Constraints And Draft Engine

**Purpose:** Convert roles and risk tags into draft core-satellite weights. This is a dry-run allocator for research review, not an investment recommendation.

**Files:**
- Create: `config/portfolio_constraints.v1.json`
- Create: `backend/app/portfolio/constraints.py`
- Create: `backend/tests/test_portfolio_constraints.py`

- [ ] **Step 1: Write constraint config**

Create `config/portfolio_constraints.v1.json`:

```json
{
  "version": "v1",
  "objective": "core_satellite_equity_pool",
  "target_buckets": {
    "core": {
      "target_weight_pct": 60,
      "min_weight_pct": 45,
      "max_weight_pct": 70
    },
    "satellite": {
      "target_weight_pct": 30,
      "min_weight_pct": 20,
      "max_weight_pct": 45
    },
    "index_tool": {
      "target_weight_pct": 10,
      "min_weight_pct": 0,
      "max_weight_pct": 25
    }
  },
  "single_fund_caps": {
    "default_pct": 10,
    "core_holding_candidate_pct": 15,
    "satellite_alpha_pct": 8,
    "index_tool_pct": 20
  },
  "risk_caps": {
    "drawdown_high": 3,
    "volatility_high": 5,
    "beta_high": 4,
    "holding_concentration_high": 6,
    "industry_concentration_high": 6,
    "tracking_error_high": 8
  },
  "hard_blockers": [
    "benchmark_data_missing",
    "data_insufficient",
    "manual_review_required"
  ],
  "score_weights": {
    "core_holding_candidate": 20,
    "satellite_alpha": 15,
    "defensive_anchor": 10,
    "low_cost": 5,
    "style_quality_growth": 6,
    "style_deep_value": 5,
    "style_dividend_steady": 5,
    "style_high_dividend_financial": 4,
    "alpha_positive": 6,
    "information_ratio_high": 6,
    "excess_return_strong": 4,
    "drawdown_high": -12,
    "volatility_high": -8,
    "beta_high": -8,
    "holding_concentration_high": -5,
    "industry_concentration_high": -5
  }
}
```

- [ ] **Step 2: Write draft engine tests**

Create `backend/tests/test_portfolio_constraints.py`:

```python
from app.portfolio.constraints import build_portfolio_draft


def test_build_portfolio_draft_caps_high_risk_satellite() -> None:
    rows = [
        {
            "fund_code": "000001",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate", "satellite_alpha"],
            "return_tags": ["alpha_positive", "information_ratio_high"],
            "risk_tags": ["volatility_high"],
            "watch_reasons": [],
        },
        {
            "fund_code": "000002",
            "allocation_status": "eligible",
            "portfolio_roles": ["core_holding_candidate", "defensive_anchor"],
            "return_tags": ["alpha_positive"],
            "risk_tags": [],
            "watch_reasons": [],
        },
        {
            "fund_code": "000003",
            "allocation_status": "observe",
            "portfolio_roles": ["satellite_alpha"],
            "return_tags": ["alpha_positive", "information_ratio_high"],
            "risk_tags": [],
            "watch_reasons": ["benchmark_data_missing"],
        },
    ]

    draft = build_portfolio_draft(rows)

    weights = {row["fund_code"]: row for row in draft["rows"]}
    assert "000003" not in weights
    assert weights["000001"]["max_weight_pct"] == 5
    assert weights["000001"]["bucket"] == "satellite"
    assert weights["000002"]["bucket"] == "core"
    assert round(sum(row["draft_weight_pct"] for row in draft["rows"]), 6) == 100
    assert draft["excluded"][0]["fund_code"] == "000003"
    assert "benchmark_data_missing" in draft["excluded"][0]["reasons"]
```

- [ ] **Step 3: Run the test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_portfolio_constraints.py::test_build_portfolio_draft_caps_high_risk_satellite -q
```

Expected: FAIL because `app.portfolio.constraints` does not exist.

- [ ] **Step 4: Implement the draft engine**

Create `backend/app/portfolio/constraints.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_constraints_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "portfolio_constraints.v1.json"


def load_portfolio_constraints(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else default_constraints_path()
    return json.loads(config_path.read_text(encoding="utf-8"))


def _score(row: dict[str, Any], config: dict[str, Any]) -> float:
    weights = config["score_weights"]
    score = 0.0
    for key in row.get("portfolio_roles", []):
        score += float(weights.get(key, 0))
    for key in row.get("return_tags", []):
        score += float(weights.get(key, 0))
    for key in row.get("risk_tags", []):
        score += float(weights.get(key, 0))
    return max(score, 1.0)


def _bucket(row: dict[str, Any]) -> str:
    roles = set(row.get("portfolio_roles", []))
    risks = set(row.get("risk_tags", []))
    if "index_tool" in roles:
        return "index_tool"
    if "satellite_alpha" in roles and risks & {"drawdown_high", "volatility_high", "beta_high"}:
        return "satellite"
    if "core_holding_candidate" in roles and "drawdown_high" not in risks:
        return "core"
    if "satellite_alpha" in roles:
        return "satellite"
    return "satellite"


def _max_weight(row: dict[str, Any], bucket: str, config: dict[str, Any]) -> float:
    caps = config["single_fund_caps"]
    risk_caps = config["risk_caps"]
    values = [float(caps["default_pct"])]
    roles = set(row.get("portfolio_roles", []))
    if "core_holding_candidate" in roles:
        values.append(float(caps["core_holding_candidate_pct"]))
    if "satellite_alpha" in roles:
        values.append(float(caps["satellite_alpha_pct"]))
    if "index_tool" in roles:
        values.append(float(caps["index_tool_pct"]))
    for risk in row.get("risk_tags", []):
        if risk in risk_caps:
            values.append(float(risk_caps[risk]))
    return min(values)


def _exclude_reasons(row: dict[str, Any], config: dict[str, Any]) -> list[str]:
    blockers = set(config["hard_blockers"])
    reasons = sorted(blockers & set(row.get("watch_reasons", [])))
    if row.get("allocation_status") == "review_required":
        reasons.append("review_required")
    return sorted(set(reasons))


def build_portfolio_draft(
    matrix_rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or load_portfolio_constraints()
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in matrix_rows:
        reasons = _exclude_reasons(row, cfg)
        if reasons:
            excluded.append({"fund_code": row["fund_code"], "reasons": reasons})
            continue
        if row.get("allocation_status") not in {"eligible", "observe"}:
            excluded.append({"fund_code": row["fund_code"], "reasons": ["not_candidate_status"]})
            continue
        bucket = _bucket(row)
        score = _score(row, cfg)
        max_weight = _max_weight(row, bucket, cfg)
        included.append(
            {
                "fund_code": row["fund_code"],
                "bucket": bucket,
                "score": score,
                "max_weight_pct": max_weight,
                "portfolio_roles": row.get("portfolio_roles", []),
                "risk_tags": row.get("risk_tags", []),
            }
        )

    total_score = sum(row["score"] for row in included) or 1.0
    capped = []
    for row in included:
        raw_weight = row["score"] / total_score * 100
        row = dict(row)
        row["draft_weight_pct"] = min(raw_weight, row["max_weight_pct"])
        capped.append(row)
    capped_total = sum(row["draft_weight_pct"] for row in capped) or 1.0
    for row in capped:
        row["draft_weight_pct"] = row["draft_weight_pct"] / capped_total * 100

    return {
        "config_version": cfg["version"],
        "objective": cfg["objective"],
        "rows": sorted(capped, key=lambda item: (-item["draft_weight_pct"], item["fund_code"])),
        "excluded": excluded,
    }
```

- [ ] **Step 5: Run constraint tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_portfolio_constraints.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add config/portfolio_constraints.v1.json backend/app/portfolio/constraints.py backend/tests/test_portfolio_constraints.py
git commit -m "feat(portfolio): add draft constraint engine"
```

---

### Task 5: Expose Portfolio Draft Through Reader, API, Export, And Report

**Purpose:** Make the draft engine usable from API, CSV/XLSX export, and Markdown reports.

**Files:**
- Modify: `backend/app/persistence/reader.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/exporters.py`
- Create: `scripts/render_portfolio_draft_report.py`
- Modify: `backend/tests/test_api_v1.py`
- Modify: `backend/tests/test_exports_and_migrations.py`
- Create: `backend/tests/test_render_portfolio_draft_report.py`

- [ ] **Step 1: Add reader method test through API**

Add to `backend/tests/test_api_v1.py`:

```python
def test_get_portfolio_draft_returns_weights(seeded_run) -> None:
    db, run_id = seeded_run
    client = TestClient(create_app(db_path=db))

    response = client.get(f"/v1/runs/{run_id}/portfolio-draft")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert "rows" in payload
    assert "excluded" in payload
    assert "config_version" in payload
```

- [ ] **Step 2: Run API test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_get_portfolio_draft_returns_weights -q
```

Expected: FAIL with 404.

- [ ] **Step 3: Add reader method**

In `backend/app/persistence/reader.py`, import:

```python
from app.portfolio.constraints import build_portfolio_draft
```

Add method:

```python
    def get_portfolio_draft(self, run_id: str) -> dict[str, Any] | None:
        matrix = self.get_portfolio_matrix(run_id)
        if matrix is None:
            return None
        draft = build_portfolio_draft(matrix["rows"])
        return {
            "run_id": run_id,
            "run_at": matrix["run_at"],
            "rule_version": matrix["rule_version"],
            **draft,
        }
```

- [ ] **Step 4: Add API route**

In `backend/app/main.py`, add:

```python
    @app.get("/v1/runs/{run_id}/portfolio-draft")
    def get_portfolio_draft(run_id: str) -> dict[str, Any]:
        reader = LabelRunReader(db_path)
        draft = reader.get_portfolio_draft(run_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return draft
```

- [ ] **Step 5: Run API test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_get_portfolio_draft_returns_weights -q
```

Expected: PASS.

- [ ] **Step 6: Add draft export**

In `backend/app/persistence/reader.py`, extend `get_run_export`:

```python
        portfolio_draft = self.get_portfolio_draft(run_id) or {"rows": []}
        payload["portfolio_draft"] = portfolio_draft["rows"]
```

In `backend/app/exporters.py`, add sheet definition:

```python
        (
            "portfolio_draft",
            run_payload.get("portfolio_draft", []),
            [
                "fund_code",
                "bucket",
                "draft_weight_pct",
                "max_weight_pct",
                "score",
                "portfolio_roles",
                "risk_tags",
            ],
        ),
```

- [ ] **Step 7: Add export test assertion**

In `backend/tests/test_exports_and_migrations.py`, update the XLSX sheet test:

```python
    assert "portfolio_draft" in wb.sheetnames
```

- [ ] **Step 8: Add draft report test and script**

Create `backend/tests/test_render_portfolio_draft_report.py`:

```python
import os
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch
from scripts.seed_sample_db import seed


def test_render_portfolio_draft_report_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    out_md = tmp_path / "draft.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_portfolio_draft_report.py",
            "--output-db",
            str(db),
            "--out-md",
            str(out_md),
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    text = out_md.read_text(encoding="utf-8")
    assert "wrote" in result.stdout
    assert "# Portfolio Draft Report" in text
    assert f"run_id: `{run_id}`" in text
    assert "Draft Weights" in text
```

Create `scripts/render_portfolio_draft_report.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from app.persistence.reader import LabelRunReader


def render_report(output_db: str, out_md: str, run_id: str | None = None) -> dict[str, object]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    draft = reader.get_portfolio_draft(selected_run_id)
    if draft is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    lines = [
        "# Portfolio Draft Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"objective: `{draft['objective']}`",
        f"config_version: `{draft['config_version']}`",
        "",
        "## Draft Weights",
        "",
        "| fund_code | bucket | draft_weight_pct | max_weight_pct | score | roles | risk_tags |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in draft["rows"]:
        lines.append(
            f"| `{row['fund_code']}` | `{row['bucket']}` | "
            f"{row['draft_weight_pct']:.2f} | {row['max_weight_pct']:.2f} | "
            f"{row['score']:.2f} | {', '.join(row.get('portfolio_roles', []))} | "
            f"{', '.join(row.get('risk_tags', []))} |"
        )
    lines += [
        "",
        "## Excluded",
        "",
        "| fund_code | reasons |",
        "| --- | --- |",
    ]
    for row in draft["excluded"]:
        lines.append(f"| `{row['fund_code']}` | {', '.join(row['reasons'])} |")

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "row_count": len(draft["rows"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    summary = render_report(args.output_db, args.out_md, args.run_id)
    print(f"wrote {args.out_md} (run_id={summary['run_id']}, rows={summary['row_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_api_v1.py::test_get_portfolio_draft_returns_weights \
  backend/tests/test_exports_and_migrations.py::test_run_export_xlsx_has_all_sheets \
  backend/tests/test_render_portfolio_draft_report.py \
  -q
```

Expected: PASS.

- [ ] **Step 10: Generate real draft report**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/render_portfolio_draft_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/portfolio-draft-v1-report.md
```

Expected: report exists and contains draft weights plus exclusions.

- [ ] **Step 11: Commit Task 5**

Run:

```bash
git add backend/app/persistence/reader.py backend/app/main.py backend/app/exporters.py scripts/render_portfolio_draft_report.py backend/tests/test_api_v1.py backend/tests/test_exports_and_migrations.py backend/tests/test_render_portfolio_draft_report.py reports/phase1-real-run-2026-06-29/portfolio-draft-v1-report.md
git commit -m "feat(portfolio): expose draft portfolio output"
```

---

### Task 6: Reduce `style_pending_rule_definition`

**Purpose:** The biggest current blocker is 122 funds waiting on style rules. This task turns the vague blocker into actionable sub-reasons and starts removing the blocker where contribution evidence is sufficient.

**Files:**
- Modify: `backend/app/label_engine/engine.py`
- Modify: `scripts/render_portfolio_matrix_report.py`
- Create: `scripts/audit_style_pending_reasons.py`
- Create: `backend/tests/test_style_pending_reasons.py`

- [ ] **Step 1: Write reason audit test**

Create `backend/tests/test_style_pending_reasons.py`:

```python
import os
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch
from scripts.seed_sample_db import seed


def test_audit_style_pending_reasons_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    out_md = tmp_path / "style-pending.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/audit_style_pending_reasons.py",
            "--output-db",
            str(db),
            "--out-md",
            str(out_md),
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    text = out_md.read_text(encoding="utf-8")
    assert "wrote" in result.stdout
    assert "# Style Pending Reason Audit" in text
    assert "style_pending_rule_definition" in text
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_style_pending_reasons.py::test_audit_style_pending_reasons_smoke -q
```

Expected: FAIL because the audit script does not exist.

- [ ] **Step 3: Add audit script**

Create `scripts/audit_style_pending_reasons.py`:

```python
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from app.persistence.reader import LabelRunReader


def render_report(output_db: str, out_md: str, run_id: str | None = None) -> dict[str, object]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    matrix = reader.get_portfolio_matrix(selected_run_id)
    if matrix is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    rows = [
        row
        for row in matrix["rows"]
        if "style_pending_rule_definition" in row.get("watch_reasons", [])
    ]
    reason_counts = Counter()
    for row in rows:
        features = row.get("features", {})
        if not any(features.get(key) is not None for key in ("quality_growth_weight", "deep_value_weight", "dividend_steady_weight")):
            reason_counts["style_weight_missing"] += 1
        elif not row.get("style_tags"):
            reason_counts["style_weight_below_formal_threshold"] += 1
        else:
            reason_counts["style_label_present_but_watch_not_cleared"] += 1

    lines = [
        "# Style Pending Reason Audit",
        "",
        f"run_id: `{selected_run_id}`",
        f"style_pending_count: {len(rows)}",
        "",
        "| reason | count |",
        "| --- | ---: |",
    ]
    for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{reason}` | {count} |")
    lines += [
        "",
        "## Examples",
        "",
        "| fund_code | roles | style_tags | watch_reasons |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows[:50]:
        lines.append(
            f"| `{row['fund_code']}` | {', '.join(row.get('portfolio_roles', []))} | "
            f"{', '.join(row.get('style_tags', []))} | {', '.join(row.get('watch_reasons', []))} |"
        )

    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "style_pending_count": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    summary = render_report(args.output_db, args.out_md, args.run_id)
    print(f"wrote {args.out_md} (run_id={summary['run_id']}, pending={summary['style_pending_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run audit test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_style_pending_reasons.py::test_audit_style_pending_reasons_smoke -q
```

Expected: PASS.

- [ ] **Step 5: Generate real style pending audit**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/audit_style_pending_reasons.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/style-pending-reasons-v1.md
```

Expected: report identifies which part of the 122 pending funds is missing weights versus below threshold.

- [ ] **Step 6: Decide reduction rule from audit evidence**

Apply this rule in `backend/app/label_engine/engine.py` after reading the generated report:

```python
# Clear style_pending_rule_definition when formal style tags exist and
# contribution-backed style weights are present for the same fund.
```

The exact implementation must preserve these boundaries:

- If no contribution-backed style weights exist, keep `style_pending_rule_definition`.
- If style weights exist but are below formal thresholds, keep observe status.
- If formal style tag exists and style weights exist, do not emit `style_pending_rule_definition`.

- [ ] **Step 7: Add regression test for clearing pending style**

Add to `backend/tests/test_label_engine.py`:

```python
def test_formal_style_label_does_not_emit_pending_rule_boundary() -> None:
    engine = LabelEngine()
    fund = FundInput(
        fund_code="000001",
        fund_name="风格测试基金",
        fund_type="偏股混合型",
        inception_date="2019-01-01",
        manager_start_date="2019-01-01",
        stock_holdings=[],
        total_annual_fee=0.01,
        nav_history=[],
        benchmark_history=[],
        factor_exposures=[
            FactorExposure(
                factor_code="quality_growth_weight",
                exposure_value=0.65,
                coverage_weight=0.9,
                source="unit-test",
                as_of_date="2026-06-30",
            )
        ],
    )

    result = engine.evaluate(fund)
    codes = {label.label_code for label in result.labels}

    assert "quality_growth" in codes
    assert "style_pending_rule_definition" not in codes
```

- [ ] **Step 8: Run style tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_label_engine.py::test_formal_style_label_does_not_emit_pending_rule_boundary -q
```

Expected: PASS after implementation.

- [ ] **Step 9: Commit Task 6**

Run:

```bash
git add backend/app/label_engine/engine.py scripts/audit_style_pending_reasons.py backend/tests/test_style_pending_reasons.py backend/tests/test_label_engine.py reports/phase1-real-run-2026-06-29/style-pending-reasons-v1.md
git commit -m "fix(portfolio): reduce style pending blockers with evidence"
```

---

### Task 7: Close Benchmark Data Gaps For Relative Labels

**Purpose:** 28 funds currently have `benchmark_data_missing`; their alpha and relative labels should not drive portfolio decisions until benchmark data is mapped and sampled.

**Files:**
- Modify: existing benchmark data fetch/audit scripts identified by `rg -n "benchmark_data_missing|benchmark_components|relative_label" scripts backend/app`
- Create: `scripts/render_benchmark_gap_portfolio_report.py`
- Create: `backend/tests/test_benchmark_gap_portfolio_report.py`

- [ ] **Step 1: Locate existing benchmark code**

Run:

```bash
rg -n "benchmark_data_missing|benchmark_components|relative_label|benchmark_quality" scripts backend/app backend/tests
```

Expected: output includes the existing benchmark quality and relative-label eligibility code paths.

- [ ] **Step 2: Write benchmark gap report test**

Create `backend/tests/test_benchmark_gap_portfolio_report.py`:

```python
import os
import subprocess
import sys
from pathlib import Path

from app.batch import run_batch
from scripts.seed_sample_db import seed


def test_render_benchmark_gap_portfolio_report_smoke(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)
    out_md = tmp_path / "benchmark-gap.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd() / 'backend'}:{Path.cwd()}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_benchmark_gap_portfolio_report.py",
            "--output-db",
            str(db),
            "--out-md",
            str(out_md),
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    text = out_md.read_text(encoding="utf-8")
    assert "wrote" in result.stdout
    assert "# Benchmark Gap Portfolio Report" in text
    assert "benchmark_data_missing" in text
```

- [ ] **Step 3: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_benchmark_gap_portfolio_report.py::test_render_benchmark_gap_portfolio_report_smoke -q
```

Expected: FAIL because report script does not exist.

- [ ] **Step 4: Add benchmark gap report script**

Create `scripts/render_benchmark_gap_portfolio_report.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from app.persistence.reader import LabelRunReader


def render_report(output_db: str, out_md: str, run_id: str | None = None) -> dict[str, object]:
    reader = LabelRunReader(output_db)
    selected_run_id = run_id or reader.latest_succeeded_run_id()
    if not selected_run_id:
        raise ValueError("No succeeded run found")
    matrix = reader.get_portfolio_matrix(selected_run_id)
    if matrix is None:
        raise ValueError(f"Run not found: {selected_run_id}")

    rows = [
        row
        for row in matrix["rows"]
        if "benchmark_data_missing" in row.get("watch_reasons", [])
    ]
    lines = [
        "# Benchmark Gap Portfolio Report",
        "",
        f"run_id: `{selected_run_id}`",
        f"benchmark_data_missing_count: {len(rows)}",
        "",
        "| fund_code | roles | return_tags | risk_tags | required_fix |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['fund_code']}` | {', '.join(row.get('portfolio_roles', []))} | "
            f"{', '.join(row.get('return_tags', []))} | {', '.join(row.get('risk_tags', []))} | "
            "`complete_benchmark_mapping_and_quote_window` |"
        )
    Path(out_md).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"run_id": selected_run_id, "gap_count": len(rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    summary = render_report(args.output_db, args.out_md, args.run_id)
    print(f"wrote {args.out_md} (run_id={summary['run_id']}, gaps={summary['gap_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Generate real benchmark gap report**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/render_benchmark_gap_portfolio_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/benchmark-gap-portfolio-v1.md
```

Expected: report lists the 28 benchmark-gap funds and their portfolio impact.

- [ ] **Step 6: Fix benchmark sources in priority order**

Use the report order. For each fund, only remove `benchmark_data_missing` when all three conditions pass:

- benchmark mapping is explicit, not guessed from broad aliases.
- benchmark quote window has at least 180 samples for the selected return window.
- `label_calculation_states` shows `benchmark_data_missing` as `not_triggered`.

Run after each benchmark-source batch:

```bash
PYTHONPATH=backend .venv/bin/python scripts/render_benchmark_gap_portfolio_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/benchmark-gap-portfolio-v1.md
```

Expected: `benchmark_data_missing_count` decreases and no manually proxied broad benchmark is introduced.

- [ ] **Step 7: Commit Task 7**

Run:

```bash
git add scripts/render_benchmark_gap_portfolio_report.py backend/tests/test_benchmark_gap_portfolio_report.py reports/phase1-real-run-2026-06-29/benchmark-gap-portfolio-v1.md
git commit -m "feat(portfolio): surface benchmark gaps for allocation workflow"
```

---

### Task 8: Build Portfolio Workbench UI

**Purpose:** Give the user a usable screen for portfolio construction: matrix filters, calibration actions, draft weights, and blockers.

**Files:**
- Create: `frontend/src/pages/PortfolioWorkbenchPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `backend/tests/test_api_v1.py`

- [ ] **Step 1: Add API health test for frontend route support**

If frontend route tests already exist, extend the same pattern. Add to `backend/tests/test_api_v1.py`:

```python
def test_create_app_serves_portfolio_workbench_route(tmp_path: Path, seeded_run) -> None:
    db, _ = seeded_run
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<main id=\"root\"></main>", encoding="utf-8")
    client = TestClient(create_app(db_path=db, frontend_dist=dist))

    response = client.get("/portfolio")

    assert response.status_code == 200
    assert b"id=\"root\"" in response.content
```

- [ ] **Step 2: Run test and verify current route behavior**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_create_app_serves_portfolio_workbench_route -q
```

Expected: PASS if SPA fallback already covers `/portfolio`; otherwise FAIL and add `/portfolio` to the fallback route list.

- [ ] **Step 3: Create frontend page**

Create `frontend/src/pages/PortfolioWorkbenchPage.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";

type MatrixRow = {
  fund_code: string;
  allocation_status: string;
  portfolio_roles: string[];
  style_tags: string[];
  return_tags: string[];
  risk_tags: string[];
  watch_reasons: string[];
};

type DraftRow = {
  fund_code: string;
  bucket: string;
  draft_weight_pct: number;
  max_weight_pct: number;
  score: number;
  portfolio_roles: string[];
  risk_tags: string[];
};

export function PortfolioWorkbenchPage() {
  const [runId, setRunId] = useState("");
  const [matrix, setMatrix] = useState<MatrixRow[]>([]);
  const [draft, setDraft] = useState<DraftRow[]>([]);
  const [status, setStatus] = useState("eligible");

  useEffect(() => {
    fetch("/v1/runs")
      .then((res) => res.json())
      .then((data) => {
        const latest = data.runs?.[0]?.run_id ?? "";
        setRunId(latest);
      });
  }, []);

  useEffect(() => {
    if (!runId) return;
    fetch(`/v1/runs/${runId}/portfolio-matrix`)
      .then((res) => res.json())
      .then((data) => setMatrix(data.rows ?? []));
    fetch(`/v1/runs/${runId}/portfolio-draft`)
      .then((res) => res.json())
      .then((data) => setDraft(data.rows ?? []));
  }, [runId]);

  const filtered = useMemo(
    () => matrix.filter((row) => row.allocation_status === status),
    [matrix, status],
  );

  return (
    <main className="portfolio-workbench">
      <header className="portfolio-toolbar">
        <h1>组合池</h1>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="eligible">可筛选</option>
          <option value="observe">观察</option>
          <option value="review_required">需复核</option>
        </select>
      </header>
      <section className="portfolio-grid">
        <div className="portfolio-panel">
          <h2>基金矩阵</h2>
          <table>
            <thead>
              <tr>
                <th>基金</th>
                <th>角色</th>
                <th>风格</th>
                <th>收益</th>
                <th>风险</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.fund_code}>
                  <td>{row.fund_code}</td>
                  <td>{row.portfolio_roles.join(", ")}</td>
                  <td>{row.style_tags.join(", ")}</td>
                  <td>{row.return_tags.join(", ")}</td>
                  <td>{row.risk_tags.join(", ")}</td>
                  <td>{row.watch_reasons.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="portfolio-panel">
          <h2>草案权重</h2>
          <table>
            <thead>
              <tr>
                <th>基金</th>
                <th>桶</th>
                <th>权重</th>
                <th>上限</th>
              </tr>
            </thead>
            <tbody>
              {draft.map((row) => (
                <tr key={row.fund_code}>
                  <td>{row.fund_code}</td>
                  <td>{row.bucket}</td>
                  <td>{row.draft_weight_pct.toFixed(2)}%</td>
                  <td>{row.max_weight_pct.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Wire route in `frontend/src/App.tsx`**

Add import:

```tsx
import { PortfolioWorkbenchPage } from "./pages/PortfolioWorkbenchPage";
```

In the sidebar `<nav>`, add this link after `可展示池`:

```tsx
<NavLink to="/portfolio">组合池</NavLink>
```

In the `<Routes>` block, add this route after `/ready-pool`:

```tsx
<Route path="/portfolio" element={<PortfolioWorkbenchPage />} />
```

- [ ] **Step 5: Add compact styles**

In `frontend/src/styles.css`, add:

```css
.portfolio-workbench {
  min-height: 100vh;
  background: #f7f8fa;
  color: #1f2937;
}

.portfolio-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid #d9dee7;
  background: #ffffff;
}

.portfolio-toolbar h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}

.portfolio-toolbar select {
  height: 34px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #ffffff;
  padding: 0 10px;
}

.portfolio-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(360px, 0.8fr);
  gap: 16px;
  padding: 16px;
}

.portfolio-panel {
  min-width: 0;
  background: #ffffff;
  border: 1px solid #d9dee7;
  border-radius: 8px;
  overflow: auto;
}

.portfolio-panel h2 {
  margin: 0;
  padding: 14px 16px;
  font-size: 15px;
  border-bottom: 1px solid #e5e7eb;
}

.portfolio-panel table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.portfolio-panel th,
.portfolio-panel td {
  padding: 10px 12px;
  border-bottom: 1px solid #edf0f5;
  text-align: left;
  vertical-align: top;
}

@media (max-width: 900px) {
  .portfolio-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 7: Run API route test**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_create_app_serves_portfolio_workbench_route -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 8**

Run:

```bash
git add frontend/src/pages/PortfolioWorkbenchPage.tsx frontend/src/App.tsx frontend/src/styles.css backend/tests/test_api_v1.py
git commit -m "feat(frontend): add portfolio workbench"
```

---

### Task 9: Final Acceptance And Regression

**Purpose:** Prove the end-to-end workflow works: labels -> matrix -> calibration -> constraints -> draft -> report -> UI/export.

**Files:**
- Modify: `docs/todo.md` or `docs/superpowers/specs/2026-06-30-phase1-v1-workbench-design.md`
- Reports under `reports/phase1-real-run-2026-06-29/`

- [ ] **Step 1: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected:

```text
passed
```

The exact test count may increase as tasks are added.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits with code 0.

- [ ] **Step 3: Regenerate all portfolio reports**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/render_portfolio_matrix_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/portfolio-matrix-v1-report.md

PYTHONPATH=backend .venv/bin/python scripts/render_portfolio_calibration_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/portfolio-calibration-v1-report.md

PYTHONPATH=backend .venv/bin/python scripts/render_portfolio_draft_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/portfolio-draft-v1-report.md

PYTHONPATH=backend .venv/bin/python scripts/render_benchmark_gap_portfolio_report.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/benchmark-gap-portfolio-v1.md

PYTHONPATH=backend .venv/bin/python scripts/audit_style_pending_reasons.py \
  --output-db /tmp/fle-run/output.sqlite \
  --out-md reports/phase1-real-run-2026-06-29/style-pending-reasons-v1.md
```

Expected: every command prints `wrote ...`.

- [ ] **Step 4: Check acceptance metrics**

Run:

```bash
PYTHONPATH=backend .venv/bin/python - <<'PY'
from collections import Counter
from app.persistence.reader import LabelRunReader

reader = LabelRunReader('/tmp/fle-run/output.sqlite')
run_id = reader.latest_succeeded_run_id()
matrix = reader.get_portfolio_matrix(run_id)
rows = matrix['rows']
status = Counter(row['allocation_status'] for row in rows)
watch = Counter()
roles = Counter()
for row in rows:
    watch.update(row['watch_reasons'])
    roles.update(row['portfolio_roles'])
print('run_id', run_id)
print('status', dict(status))
print('roles', roles.most_common(10))
print('watch', watch.most_common(10))
PY
```

Acceptance target for this plan:

- `portfolio-draft-v1-report.md` exists.
- `/v1/runs/{run_id}/portfolio-draft` returns rows and exclusions.
- role reviews can be persisted and listed.
- `style_pending_rule_definition` is decomposed into actionable audit reasons.
- `benchmark_data_missing` funds are excluded from draft weights.
- full pytest passes.
- frontend build passes.

- [ ] **Step 5: Commit final documentation update**

Run:

```bash
git add docs/todo.md docs/superpowers/specs/2026-06-30-phase1-v1-workbench-design.md reports/phase1-real-run-2026-06-29
git commit -m "docs(portfolio): record portfolio workbench acceptance baseline"
```

---

## Recommended Execution Order

1. Task 1: Calibration queue report.
2. Task 2: Persist human role decisions.
3. Task 3: Role review API.
4. Task 4: Portfolio constraints and draft engine.
5. Task 5: Draft API/export/report.
6. Task 6: Reduce style pending blockers.
7. Task 7: Benchmark gap closure report and fixes.
8. Task 8: Portfolio workbench UI.
9. Task 9: Full acceptance.

Do not start Task 8 before Task 5 is complete. The frontend should consume stable API payloads, not invent its own portfolio logic.

## Product Acceptance Definition

The project is strong enough for first practical portfolio workflow when all of these are true:

- A researcher can open the portfolio matrix and see fund role, style, return, risk, and blocker reasons.
- A researcher can record whether a role is accepted, rejected, or needs more data.
- Benchmark-missing funds are excluded from draft weights.
- High-risk funds are capped by explicit config, not hidden judgment.
- Draft portfolio output shows every weight, cap, bucket, score, and exclusion reason.
- Reports are reproducible from `/tmp/fle-run/output.sqlite`.
- Backend tests and frontend build pass.

## Self-Review

- Spec coverage: The plan covers calibration, data blockers, risk sizing constraints, reports, API, export, and frontend.
- Vague-pattern scan: No task relies on unfinished work labels; every new file has concrete code or commands.
- Type consistency: `portfolio_roles`, `risk_tags`, `watch_reasons`, `allocation_status`, `draft_weight_pct`, and `max_weight_pct` match current matrix payload naming.
