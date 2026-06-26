# Equity Style Contributions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an equity-holding explanation layer that shows which stocks and factors contributed to `deep_value`, `quality_growth`, and `dividend_steady` fund labels.

**Architecture:** Keep existing fund-level labels as the decision layer, and add a stock-level contribution layer below them. Batch computes per-stock contribution rows from `stock_holdings + stock_factor_values`, persists them in the output DB, and API/export surfaces them alongside current `fund_factor_exposures`.

**Tech Stack:** Python, SQLite, existing `backend/app/batch.py`, `backend/app/factors/exposure_aggregator.py`, `backend/app/persistence`, FastAPI reader/export surfaces, pytest.

---

## File Structure

- Create `backend/app/factors/equity_contributions.py`
  - Owns stock-level style condition evaluation and contribution row generation.
  - Does not decide fund labels; it only explains stock contributions.
- Create migration `backend/app/persistence/migrations/0008_equity_style_contributions.sql`
  - Adds `fund_equity_style_contributions`.
- Modify `backend/app/persistence/writer.py`
  - Ensures schema and writes contribution rows during batch.
- Modify `backend/app/batch.py`
  - Computes contributions after factor exposure aggregation and before writing the engine result.
- Modify `backend/app/persistence/reader.py`
  - Adds contribution rows to single-fund report and run payload.
- Modify `backend/app/exporters.py`
  - Exports contribution rows.
- Modify `backend/app/main.py`
  - Adds an API surface if reader payload is not enough.
- Tests:
  - `backend/tests/test_equity_contributions.py`
  - `backend/tests/test_stock_factor_integration.py`
  - `backend/tests/test_exports_and_migrations.py`
  - `backend/tests/test_api_v1.py`

## Data Contract

New table:

```sql
CREATE TABLE IF NOT EXISTS fund_equity_style_contributions (
    fund_code TEXT NOT NULL,
    report_date TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    weight REAL NOT NULL,
    style_code TEXT NOT NULL,
    style_name TEXT NOT NULL,
    matched INTEGER NOT NULL,
    contribution_weight REAL NOT NULL,
    factor_values_json TEXT NOT NULL,
    rule_snapshot_json TEXT NOT NULL,
    factor_as_of_date TEXT NOT NULL,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (fund_code, report_date, stock_code, style_code, factor_as_of_date)
);
```

Style conditions:

- `deep_value`: `pb <= deep_value_pb_max` and `valuation_percentile <= deep_value_valuation_pct_max`
- `quality_growth`: `roe >= quality_growth_roe_min` and `revenue_growth >= quality_growth_revenue_growth_min`
- `dividend_steady`: `dividend_yield >= dividend_steady_yield_min`

Contribution semantics:

- One stock can match multiple style codes.
- `matched=1` rows explain positive style contribution.
- `matched=0` rows are optional and should only be emitted for top holdings when requested later; MVP writes only matched rows.
- `contribution_weight = holding weight` for matched rows.
- Fund-level `*_weight` remains the sum of matched contribution weights.

## Task 1: Contribution Aggregator

**Files:**
- Create: `backend/app/factors/equity_contributions.py`
- Test: `backend/tests/test_equity_contributions.py`

- [ ] **Step 1: Write failing tests for stock-level style matching**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_equity_contributions.py::test_build_equity_style_contributions_emits_matched_stock_rows -q
```

Expected: import failure for `app.factors.equity_contributions`.

- [ ] **Step 3: Implement minimal aggregator**

Create `EquityStyleContribution` dataclass with fields matching the new table. Implement `build_equity_style_contributions(...)` using the same thresholds as `aggregate_factor_exposures`.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_equity_contributions.py -q
```

Expected: all contribution tests pass.

## Task 2: Persistence Schema And Writer

**Files:**
- Create: `backend/app/persistence/migrations/0008_equity_style_contributions.sql`
- Modify: `backend/app/persistence/writer.py`
- Test: `backend/tests/test_exports_and_migrations.py`

- [ ] **Step 1: Write failing migration test**

Add an assertion that `fund_equity_style_contributions` exists after migrations run.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_migrations_create_expected_tables -q
```

Expected: missing table assertion fails.

- [ ] **Step 3: Add migration and writer method**

Add `write_equity_style_contributions(rows)` to `LabelRunWriter`. Use `INSERT OR REPLACE`, preserve JSON fields as strings, and keep contribution rows in the output DB, not source DB.

- [ ] **Step 4: Run persistence tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py backend/tests/test_batch_db_separation.py -q
```

Expected: migrations and separated DB tests pass.

## Task 3: Batch Integration

**Files:**
- Modify: `backend/app/batch.py`
- Test: `backend/tests/test_stock_factor_integration.py`

- [ ] **Step 1: Write failing batch test**

Extend an existing stock-factor integration fixture so one holding matches `deep_value` and one matches `dividend_steady`. Assert output DB contains matching rows in `fund_equity_style_contributions`.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_factor_integration.py::test_run_batch_persists_equity_style_contributions -q
```

Expected: table missing or zero contribution rows.

- [ ] **Step 3: Wire aggregator into batch**

In `run_batch`, after `_compute_exposures(...)` and before `engine.evaluate(fund)`, call `build_equity_style_contributions(...)` when `fund.stock_holdings` and `fund.stock_factors` exist. Write rows to output DB through `LabelRunWriter`.

- [ ] **Step 4: Run batch tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_factor_integration.py backend/tests/test_batch_db_separation.py -q
```

Expected: contribution rows persist only in output DB.

## Task 4: Reader, API, And Export Visibility

**Files:**
- Modify: `backend/app/persistence/reader.py`
- Modify: `backend/app/exporters.py`
- Optionally modify: `backend/app/main.py`
- Test: `backend/tests/test_api_v1.py`
- Test: `backend/tests/test_exports_and_migrations.py`

- [ ] **Step 1: Write failing reader/API test**

For a seeded run with contribution rows, assert `/v1/runs/{run_id}/funds/{fund_code}/report` includes `equity_style_contributions`.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py::test_fund_report_includes_equity_style_contributions -q
```

Expected: key missing from response.

- [ ] **Step 3: Add reader and export payload**

Add `LabelRunReader.list_equity_style_contributions(fund_code=None, style_code=None)` and include rows in single-fund report. Add an export sheet/file named `equity_style_contributions`.

- [ ] **Step 4: Run API/export tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_api_v1.py backend/tests/test_exports_and_migrations.py -q
```

Expected: report and export include contribution rows.

## Task 5: Data Quality And Calibration Report

**Files:**
- Create: `scripts/generate_equity_style_contribution_report.py`
- Output: `reports/equity_style_contributions_<run_id>.md`
- Test: `backend/tests/test_equity_contributions.py`

- [ ] **Step 1: Write failing report smoke test**

Create a tiny output DB with contribution rows and assert the report contains top contributing stocks by style.

- [ ] **Step 2: Implement report script**

Report sections:

- summary counts by style
- top 20 funds per style by total contribution weight
- top contributing stocks for one fund
- factor coverage buckets
- warning list for funds with style label but no contribution rows

- [ ] **Step 3: Run report on current real output DB**

Run:

```bash
PYTHONPATH=backend .venv/bin/python scripts/generate_equity_style_contribution_report.py \
  --db /tmp/fle-run/output-after-equity-factor-correct.sqlite \
  --run-id 3a4b30458a0347e0a207d9d40ec27851 \
  --out reports/equity_style_contributions_3a4b3045.md
```

Expected: report file exists and shows `deep_value`, `quality_growth`, and `dividend_steady` contribution breakdowns.

## Task 6: Verification Gate

**Files:**
- Modify: `backend/app/batch.py`
- Test: `backend/tests/test_batch_db_separation.py`

- [ ] **Step 1: Extend equity-factor output validation**

When style labels are triggered, validate that contribution rows exist for the same fund/style. Keep this as a warning first if needed, but fail for the controlled test fixture.

- [ ] **Step 2: Run targeted validation tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_batch_db_separation.py backend/tests/test_stock_factor_integration.py -q
```

Expected: validation proves labels and explanation rows stay in sync.

## Final Verification

Run:

```bash
.venv/bin/python -m pytest -q
npm run build --prefix frontend
git diff --check
```

Expected:

- backend tests pass
- frontend build passes
- no whitespace errors

Run one real batch smoke:

```bash
printf '000001\n' > /tmp/fle-run/equity-check-codes.txt
rm -f /tmp/fle-run/output-equity-contribution-check.sqlite
FLE_PHASE1_CODES_FILE=/tmp/fle-run/equity-check-codes.txt \
PYTHONPATH=backend .venv/bin/python -m app.batch \
  --source-db /tmp/fle-run/source-v5.sqlite \
  --output-db /tmp/fle-run/output-equity-contribution-check.sqlite \
  --source funddata \
  --rule-config config/rules.v1.json \
  --factor-db data/stock_factors.sqlite \
  --style-history-periods 2
```

Then verify:

```bash
sqlite3 /tmp/fle-run/output-equity-contribution-check.sqlite \
  "select style_code, count(*) from fund_equity_style_contributions group by style_code;"
```

Expected: rows exist for any matched styles in the chosen fund. If the chosen fund has no matched styles, choose one fund from the latest output that already has `deep_value`, `quality_growth`, or `dividend_steady`.

## Commit Strategy

Commit after each task:

```bash
git add <task files>
git commit -m "feat: add equity style contribution <task summary>"
```

Keep contribution logic, persistence, API/export, and report script in separate commits so regressions are easy to isolate.
