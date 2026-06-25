# Label Calculation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the calculation layer explain every label outcome, including triggered labels, not-triggered labels, and labels that could not be computed because prerequisite data is missing.

**Architecture:** Keep the existing emitted-label tables unchanged for compatibility, and add a parallel calculation-state table. `LabelEngine` will return label calculation states; `LabelRunWriter` persists them; `LabelRunReader` exposes them in fund reports and run summaries.

**Tech Stack:** Python 3.13, SQLite, pytest, FastAPI reader endpoints.

---

### Task 1: Engine Calculation States

**Files:**
- Modify: `backend/app/label_engine/engine.py`
- Test: `backend/tests/test_label_engine.py`

- [x] **Step 1: Write failing tests**

Add tests that assert:
- a triggered label has `state="triggered"`;
- a label with enough data but missed threshold has `state="not_triggered"`;
- a label missing prerequisite data has `state="not_computed"` and a reason code.

- [x] **Step 2: Run targeted tests**

Run: `.venv/bin/python -m pytest backend/tests/test_label_engine.py -q`

- [x] **Step 3: Implement minimal engine support**

Add a `LabelCalculation` dataclass, add `calculations` to `EngineResult`, and derive per-label states from emitted labels, evidence, coverage, and known prerequisite rules.

- [x] **Step 4: Re-run targeted tests**

Run: `.venv/bin/python -m pytest backend/tests/test_label_engine.py -q`

### Task 2: Persistence And Reader Summary

**Files:**
- Modify: `backend/app/persistence/writer.py`
- Modify: `backend/app/persistence/reader.py`
- Create: `backend/app/persistence/migrations/0005_label_calculation_states.sql`
- Test: `backend/tests/test_exports_and_migrations.py`
- Test: `backend/tests/test_api_v1.py`

- [x] **Step 1: Write failing persistence/API tests**

Add tests that assert:
- the new table is created by migrations;
- a batch run persists calculation states;
- `get_fund_report` includes `calculations`;
- `get_summary` includes state distribution and not-computed reason distribution.

- [x] **Step 2: Run targeted tests**

Run: `.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py backend/tests/test_api_v1.py -q`

- [x] **Step 3: Implement persistence and reader support**

Create the migration, insert calculation states in `write_result`, and expose calculations through report/export/summary reader methods.

- [x] **Step 4: Re-run targeted tests**

Run: `.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py backend/tests/test_api_v1.py -q`

### Task 3: Export And Documentation

**Files:**
- Modify: `backend/app/exporters.py`
- Modify: `docs/requirements.md`
- Modify: `docs/label-taxonomy.md`
- Modify: `docs/todo.md`

- [x] **Step 1: Write failing export test**

Extend the run export test to require `calculations.csv` / `calculations` sheet.

- [x] **Step 2: Run export test**

Run: `.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_run_export_csv_returns_zip_with_expected_files backend/tests/test_exports_and_migrations.py::test_run_export_xlsx_has_all_sheets -q`

- [x] **Step 3: Implement export and docs**

Add calculation-state export and update docs to describe calculation-only v1, excluding review workflow from the current scope.

- [x] **Step 4: Re-run export test**

Run: `.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_run_export_csv_returns_zip_with_expected_files backend/tests/test_exports_and_migrations.py::test_run_export_xlsx_has_all_sheets -q`

### Task 4: Full Verification

**Files:**
- All changed files

- [x] **Step 1: Run backend tests**

Run: `.venv/bin/python -m pytest -q`

- [x] **Step 2: Inspect final diff**

Run: `git diff --stat` and `git diff -- backend/app backend/tests docs`

- [x] **Step 3: Report result**

Summarize changed files, test output, and remaining follow-up items.
