# Fund Label Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable fund label calculation engine with documentation, tests, and a minimal FastAPI shell.

**Architecture:** The engine is rule-first and evidence-first. Data enters as a `FundInput`, coverage and features are calculated in pure Python, labels are emitted with evidence, and API/storage layers remain thin wrappers.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, setuptools.

---

### Task 1: Project Documentation

**Files:**
- Create: `README.md`
- Create: `docs/requirements.md`
- Create: `docs/scope-boundary.md`
- Create: `docs/baseline-research.md`
- Create: `docs/data-contract.md`
- Create: `docs/label-taxonomy.md`
- Create: `docs/mvp-roadmap.md`

- [x] **Step 1: Write the project overview**

Document the project goal, first scope, non-goals, and baseline repositories.

- [x] **Step 2: Write requirements and boundaries**

Define users, inputs, outputs, MVP acceptance, in-scope work, and out-of-scope work.

- [x] **Step 3: Write data and label contracts**

Define expected input tables, output tables, first label set, and advanced label boundary.

### Task 2: Define Expected Engine Behavior With Tests

**Files:**
- Create: `backend/tests/test_label_engine.py`

- [x] **Step 1: Write tests before production code**

Tests define missing-data handling, holding concentration labels, manager/fee labels, and missing stock-factor boundaries.

- [x] **Step 2: Run tests to verify red state**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 -m pytest backend/tests/test_label_engine.py -q
```

Expected: fail because `app.label_engine.engine` is not implemented yet.

### Task 3: Implement Minimal Engine

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/label_engine/__init__.py`
- Create: `backend/app/label_engine/engine.py`

- [x] **Step 1: Implement dataclasses**

Create `FundInput`, `EvidenceItem`, `LabelResult`, and `EngineResult`.

- [x] **Step 2: Implement coverage checks**

Emit `data_insufficient` and `manual_review_required` when required evidence is missing.

- [x] **Step 3: Implement basic labels**

Emit `holding_concentration_high`, `manager_tenure_long`, `fee_low`, and `style_unlabeled_stock_factors_missing` with evidence.

- [x] **Step 4: Run tests to verify green state**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 -m pytest backend/tests/test_label_engine.py -q
```

Expected: pass.

### Task 4: Add API Shell

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

- [x] **Step 1: Write health test**

Test `GET /health` returns `{"status": "ok"}`.

- [x] **Step 2: Implement FastAPI app**

Add `create_app()` and `app`.

- [x] **Step 3: Run API tests**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 -m pytest backend/tests/test_api.py -q
```

Expected: pass.

### Task 5: Repository Initialization

**Files:**
- Create: `.gitignore`

- [x] **Step 1: Add ignore rules**

Ignore `.venv`, caches, local DB files, and large data exports.

- [x] **Step 2: Run full tests**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 -m pytest -q
```

Expected: all tests pass.

- [x] **Step 3: Commit project start**

Run:

```bash
git init
git add .
git commit -m "chore: start fund label engine project"
```
