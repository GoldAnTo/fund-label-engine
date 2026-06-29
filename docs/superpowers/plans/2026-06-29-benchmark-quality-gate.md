# Benchmark Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make benchmark data safe for relative-return labels by preventing wrong benchmark mappings, producing an auditable gap report, and only allowing Alpha/Beta/excess-return labels when the benchmark source is correct enough.

**Architecture:** Keep benchmark work in `scripts/fetch_benchmark_returns.py` as the source preparation layer, because label calculation should consume already-trusted benchmark returns. Add a small audit/report layer that classifies every Phase1 fund as `ready`, `missing_source`, `mapping_required`, or `high_risk_mapping`, then wire the workflow so `run-batch-v1` is never treated as relative-benchmark-ready unless benchmark preparation has run. The first milestone prioritizes correctness over coverage: a fund with an ambiguous benchmark must remain `benchmark_data_missing` instead of silently falling back to a broad index.

**Tech Stack:** Python 3.13, SQLite, pytest, existing Makefile workflow, existing `scripts/fetch_benchmark_returns.py`, existing `app.batch`.

---

## Current Evidence

- Official v1 list: `data/phase1_fund_codes_v1_official.txt`, 142 funds.
- Prepared benchmark source: `/tmp/fle-run/source-v5.sqlite`.
- Current benchmark coverage from source-v5: 68/142 funds have `benchmark_returns`; 74/142 still become `benchmark_data_missing`.
- Current parsing audit has 132 funds with resolved index components, but "resolved component" does not always mean "safe to compute".
- Confirmed wrong mapping:
  - `000251 工银金融地产混合A`: source text `80%×沪深300金融地产行业指数收益率` currently maps to ordinary `000300 沪深300`.
  - `000368 汇添富沪深300安中指数A`: source text `沪深300安中动态策略指数收益率*95%` currently maps to ordinary `000300 沪深300`.

## Scope Boundary

### In Scope

- Fix broad keyword false positives in benchmark component parsing.
- Add tests that reproduce the confirmed false positives.
- Add an audit report that explains each benchmark gap by fund and component.
- Add Makefile workflow targets for benchmark preparation and benchmark-aware v1 batch.
- Update docs so operators know which result set is safe for relative-benchmark labels.

### Out of Scope

- Do not proxy missing bond indexes with unrelated free indexes.
- Do not mark `中证全债`, `中证综合债`, `中债总`, or `中国债券总` as ready without a real daily-return source.
- Do not use LLM judgment to "guess" benchmark components.
- Do not expand beyond the v1 official list until the v1 benchmark audit is clean enough.

## Files To Touch

- Modify: `scripts/fetch_benchmark_returns.py`
  - Add high-risk prefix guard for broad index aliases.
  - Add precise unresolved reasons for ambiguous benchmark terms.
  - Keep existing fetch and compose behavior intact.
- Modify: `backend/tests/test_fetch_benchmark_returns.py`
  - Add regression tests for false positive prevention and existing plain-index behavior.
- Create: `scripts/audit_benchmark_quality.py`
  - Read source DB plus code list and output Markdown/CSV benchmark quality reports.
- Create: `backend/tests/test_audit_benchmark_quality.py`
  - Unit-test quality bucketing without network.
- Modify: `Makefile`
  - Add `refresh-benchmark`, `audit-benchmark`, and `run-batch-v1-with-benchmark` targets.
- Modify: `docs/runbook-batch-workflow.md`
  - Document the new benchmark-safe workflow and relative-label acceptance gate.
- Create: `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md`
  - Generated report after implementation.

---

## Acceptance Rules

1. `000251` and `000368` must no longer produce ordinary `000300` benchmark returns unless exact supported mappings are added with verified source IDs.
2. Plain `沪深300指数收益率*80%+上证国债指数收益率*20%` must still resolve to `000300:0.80+000012:0.20`.
3. `benchmark_components` must distinguish:
   - `resolved` with usable source,
   - `resolved` but missing source,
   - `unresolved` because exact mapping is required,
   - `unresolved` because benchmark text is missing.
4. Relative-benchmark labels are allowed only for funds with composed `benchmark_returns`.
5. After rerun, coverage may drop below 68/142 if false positives are removed. That is acceptable and expected; correctness wins.

---

### Task 1: Add Regression Tests For Broad-Index False Positives

**Files:**
- Modify: `backend/tests/test_fetch_benchmark_returns.py`

- [ ] **Step 1: Add failing tests for confirmed wrong mappings**

Append these tests to `backend/tests/test_fetch_benchmark_returns.py`:

```python
def test_parse_rejects_hs300_financial_real_estate_as_plain_hs300():
    components, audits = parse_benchmark_components(
        "80%×沪深300金融地产行业指数收益率+20%×上证国债指数收益率"
    )

    assert components is None
    assert any(
        audit.status == "unresolved"
        and audit.reason == "exact_component_mapping_required"
        and audit.component_name == "沪深300金融地产行业指数"
        for audit in audits
    )
    assert not any(
        audit.status == "resolved"
        and audit.component_code == "000300"
        and audit.source_text == "80%×沪深300金融地产行业指数收益率"
        for audit in audits
    )


def test_parse_rejects_hs300_anzhong_strategy_as_plain_hs300():
    components, audits = parse_benchmark_components(
        "沪深300安中动态策略指数收益率*95%+金融机构人民币活期存款基准利率(税后)*5%"
    )

    assert components is None
    assert any(
        audit.status == "unresolved"
        and audit.reason == "exact_component_mapping_required"
        and audit.component_name == "沪深300安中动态策略指数"
        for audit in audits
    )
    assert not any(
        audit.status == "resolved"
        and audit.component_code == "000300"
        for audit in audits
    )


def test_parse_keeps_plain_hs300_supported():
    components, audits = parse_benchmark_components(
        "沪深300指数收益率*80%+上证国债指数收益率*20%"
    )

    assert components is not None
    assert [component.benchmark_code for component in components] == ["000300", "000012"]
    assert [component.weight for component in components] == [0.8, 0.2]
    assert all(audit.status == "resolved" for audit in audits)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
../fund-label-engine/.venv/bin/python -m pytest backend/tests/test_fetch_benchmark_returns.py \
  -k "hs300_financial_real_estate or hs300_anzhong_strategy or plain_hs300" -q
```

Expected:

```text
2 failed, 1 passed
```

The two failing tests should show that the current parser incorrectly returns component code `000300`.

---

### Task 2: Block Ambiguous Broad-Index Prefix Matches

**Files:**
- Modify: `scripts/fetch_benchmark_returns.py`
- Test: `backend/tests/test_fetch_benchmark_returns.py`

- [ ] **Step 1: Add exact-mapping guard data**

In `scripts/fetch_benchmark_returns.py`, add this constant after `INDEX_MAP`:

```python
EXACT_COMPONENT_REQUIRED_PREFIXES = {
    "沪深300": (
        "沪深300金融地产",
        "沪深300安中",
        "沪深300非周期",
    ),
}
```

- [ ] **Step 2: Add helper that identifies high-risk component names**

Add this helper below `_clean_component_name`:

```python
def _requires_exact_component_mapping(cleaned_name: str) -> bool:
    for _broad_alias, exact_required_prefixes in EXACT_COMPONENT_REQUIRED_PREFIXES.items():
        if any(cleaned_name.startswith(prefix) for prefix in exact_required_prefixes):
            return True
    return False
```

- [ ] **Step 3: Change component matching to return unresolved audit reason**

Replace `_match_index_component` with this version:

```python
def _match_index_component(name: str, weight: float, source_text: str) -> BenchmarkComponent | None:
    cleaned = _clean_component_name(name)
    if _requires_exact_component_mapping(cleaned):
        return None
    for key in sorted(INDEX_MAP, key=len, reverse=True):
        if key in cleaned:
            code, secid, index_name = INDEX_MAP[key]
            return BenchmarkComponent(code, secid, index_name, weight, "index", source_text)
    return None
```

Then update the unresolved branch inside `parse_benchmark_components` from:

```python
reason="unsupported_component_or_missing_source",
```

to:

```python
reason=(
    "exact_component_mapping_required"
    if _requires_exact_component_mapping(component_name)
    else "unsupported_component_or_missing_source"
),
```

- [ ] **Step 4: Run focused parser tests**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
.venv/bin/python -m pytest backend/tests/test_fetch_benchmark_returns.py \
  -k "hs300_financial_real_estate or hs300_anzhong_strategy or plain_hs300" -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run all benchmark parser tests**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
.venv/bin/python -m pytest backend/tests/test_fetch_benchmark_returns.py -q
```

Expected:

```text
12 passed
```

The exact number may be higher if more tests already exist; there must be zero failures.

---

### Task 3: Add Benchmark Quality Audit Script

**Files:**
- Create: `scripts/audit_benchmark_quality.py`
- Create: `backend/tests/test_audit_benchmark_quality.py`

- [ ] **Step 1: Create unit tests for quality bucketing**

Create `backend/tests/test_audit_benchmark_quality.py`:

```python
from scripts.audit_benchmark_quality import classify_component, summarize_fund_quality


def test_classify_component_ready_when_resolved_and_has_returns():
    component = {
        "status": "resolved",
        "reason": "index",
        "component_code": "000300",
        "component_name": "沪深300",
    }

    assert classify_component(component, {"000300"}) == "ready"


def test_classify_component_missing_source_when_resolved_without_returns():
    component = {
        "status": "resolved",
        "reason": "index",
        "component_code": "H11001",
        "component_name": "中证全债",
    }

    assert classify_component(component, {"000300"}) == "missing_source"


def test_classify_component_mapping_required_for_exact_required_reason():
    component = {
        "status": "unresolved",
        "reason": "exact_component_mapping_required",
        "component_code": None,
        "component_name": "沪深300金融地产行业指数",
    }

    assert classify_component(component, {"000300"}) == "mapping_required"


def test_summarize_fund_quality_uses_worst_component_status():
    components = [
        {
            "status": "resolved",
            "reason": "index",
            "component_code": "000300",
            "component_name": "沪深300",
        },
        {
            "status": "resolved",
            "reason": "index",
            "component_code": "H11001",
            "component_name": "中证全债",
        },
    ]

    summary = summarize_fund_quality(components, {"000300"})

    assert summary["quality_status"] == "missing_source"
    assert summary["blocking_components"] == "H11001:中证全债"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
.venv/bin/python -m pytest backend/tests/test_audit_benchmark_quality.py -q
```

Expected:

```text
ERROR backend/tests/test_audit_benchmark_quality.py
ModuleNotFoundError: No module named 'scripts.audit_benchmark_quality'
```

- [ ] **Step 3: Create the audit script implementation**

Create `scripts/audit_benchmark_quality.py`:

```python
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Any


QUALITY_ORDER = {
    "ready": 0,
    "missing_source": 1,
    "mapping_required": 2,
    "unresolved": 3,
    "benchmark_missing": 4,
}


def read_codes(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def classify_component(component: dict[str, Any], component_codes_with_returns: set[str]) -> str:
    status = str(component.get("status") or "")
    reason = str(component.get("reason") or "")
    code = component.get("component_code")
    if reason == "benchmark_missing":
        return "benchmark_missing"
    if reason == "exact_component_mapping_required":
        return "mapping_required"
    if status != "resolved":
        return "unresolved"
    if code and str(code) in component_codes_with_returns:
        return "ready"
    return "missing_source"


def summarize_fund_quality(
    components: list[dict[str, Any]],
    component_codes_with_returns: set[str],
) -> dict[str, str]:
    if not components:
        return {
            "quality_status": "benchmark_missing",
            "blocking_components": "",
        }
    classified = [
        (classify_component(component, component_codes_with_returns), component)
        for component in components
    ]
    worst_status = max(classified, key=lambda item: QUALITY_ORDER[item[0]])[0]
    blockers = [
        f"{component.get('component_code') or ''}:{component.get('component_name') or ''}".strip(":")
        for status, component in classified
        if status != "ready"
    ]
    return {
        "quality_status": worst_status,
        "blocking_components": ";".join(blockers),
    }


def load_component_codes_with_returns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT benchmark_code AS component_code
        FROM benchmark_returns
        WHERE benchmark_code IS NOT NULL
        UNION
        SELECT DISTINCT component_code
        FROM benchmark_component_returns
        WHERE component_code IS NOT NULL
        """
    ).fetchall()
    return {str(row["component_code"]) for row in rows if row["component_code"]}


def build_quality_rows(conn: sqlite3.Connection, codes: list[str]) -> list[dict[str, str]]:
    component_codes_with_returns = load_component_codes_with_returns(conn)
    placeholders = ",".join("?" for _ in codes)
    profile_rows = conn.execute(
        f"""
        SELECT fund_code, fund_name, fund_type, benchmark, tracking_target
        FROM fund_profiles
        WHERE fund_code IN ({placeholders})
        ORDER BY fund_code
        """,
        codes,
    ).fetchall()
    rows: list[dict[str, str]] = []
    for profile in profile_rows:
        components = [
            dict(row)
            for row in conn.execute(
                """
                SELECT component_code, component_name, weight, source_text, status, reason, secid
                FROM benchmark_components
                WHERE fund_code = ?
                ORDER BY component_order
                """,
                (profile["fund_code"],),
            ).fetchall()
        ]
        summary = summarize_fund_quality(components, component_codes_with_returns)
        has_returns = conn.execute(
            "SELECT 1 FROM benchmark_returns WHERE fund_code = ? LIMIT 1",
            (profile["fund_code"],),
        ).fetchone()
        rows.append(
            {
                "fund_code": profile["fund_code"],
                "fund_name": profile["fund_name"] or "",
                "fund_type": profile["fund_type"] or "",
                "quality_status": summary["quality_status"],
                "has_benchmark_returns": "yes" if has_returns else "no",
                "blocking_components": summary["blocking_components"],
                "benchmark": profile["benchmark"] or "",
                "tracking_target": profile["tracking_target"] or "",
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    fieldnames = [
        "fund_code",
        "fund_name",
        "fund_type",
        "quality_status",
        "has_benchmark_returns",
        "blocking_components",
        "benchmark",
        "tracking_target",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], path: str | Path) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["quality_status"]] = counts.get(row["quality_status"], 0) + 1
    lines = [
        "# Benchmark Quality Gate Report",
        "",
        "## Status Counts",
        "",
        "| status | funds |",
        "|---|---:|",
    ]
    for status, count in sorted(counts.items(), key=lambda item: item[0]):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Blocked Funds",
            "",
            "| fund_code | fund_name | status | blocking_components | benchmark |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        if row["quality_status"] == "ready":
            continue
        benchmark = row["benchmark"].replace("|", "/")
        blockers = row["blocking_components"].replace("|", "/")
        lines.append(
            f"| `{row['fund_code']}` | {row['fund_name']} | `{row['quality_status']}` | "
            f"{blockers} | {benchmark} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit benchmark mapping and source quality.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--codes-file", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args(argv)

    codes = read_codes(args.codes_file)
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        rows = build_quality_rows(conn, codes)
    write_csv(rows, args.csv)
    write_markdown(rows, args.markdown)
    print(f"benchmark_quality_rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the audit unit tests**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
.venv/bin/python -m pytest backend/tests/test_audit_benchmark_quality.py -q
```

Expected:

```text
4 passed
```

---

### Task 4: Add Benchmark Workflow Targets

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add benchmark variables**

In `Makefile`, add these variables after `NAV_END`:

```make
BENCHMARK_START ?= 2025-06-25
BENCHMARK_END   ?= 2026-06-24
BENCHMARK_REPORT_DIR ?= reports/phase1-real-run-2026-06-29
BENCHMARK_MAPPING_CSV ?= $(BENCHMARK_REPORT_DIR)/benchmark-mapping.csv
BENCHMARK_QUALITY_CSV ?= $(BENCHMARK_REPORT_DIR)/benchmark-quality.csv
BENCHMARK_QUALITY_MD  ?= $(BENCHMARK_REPORT_DIR)/benchmark-quality-gate.md
```

- [ ] **Step 2: Add help text**

Add these lines to the `help` target:

```make
	@echo "  make refresh-benchmark  解析/拉取 phase1 v1 基准收益到 $(SOURCE_DB)"
	@echo "  make audit-benchmark    输出 benchmark 质量审计到 $(BENCHMARK_REPORT_DIR)"
	@echo "  make run-batch-v1-with-benchmark  先补 benchmark，再跑 v1 标签"
```

- [ ] **Step 3: Add workflow targets**

Add these Makefile targets before `test`:

```make
refresh-benchmark: copy-source
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/fetch_benchmark_returns.py \
	  --db $(SOURCE_DB) \
	  --codes-file $(PHASE1_OFFICIAL_FILE) \
	  --start-date $(BENCHMARK_START) \
	  --end-date $(BENCHMARK_END) \
	  --mapping-csv $(BENCHMARK_MAPPING_CSV)

audit-benchmark:
	@mkdir -p $(BENCHMARK_REPORT_DIR)
	$(PYTHON) scripts/audit_benchmark_quality.py \
	  --db $(SOURCE_DB) \
	  --codes-file $(PHASE1_OFFICIAL_FILE) \
	  --csv $(BENCHMARK_QUALITY_CSV) \
	  --markdown $(BENCHMARK_QUALITY_MD)

run-batch-v1-with-benchmark: refresh-benchmark audit-benchmark
	@rm -f $(OUTPUT_DB)
	cd backend && FLE_PHASE1_CODES_FILE=$(PWD)/$(PHASE1_OFFICIAL_FILE) \
	  $(PYTHON) -m app.batch \
	    --source-db $(SOURCE_DB) \
	    --output-db $(OUTPUT_DB) \
	    --source funddata \
	    --rule-config $(PWD)/$(RULE_CONFIG) \
	    --factor-db $(PWD)/$(FACTOR_DB) \
	    --min-nav-samples 180 \
	    --min-holding-total-weight 0.5 \
	    --deep-value-weight-min 0.4 \
	    --quality-growth-weight-min 0.4
```

- [ ] **Step 4: Verify Makefile target listing**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
make help
```

Expected output includes:

```text
make refresh-benchmark
make audit-benchmark
make run-batch-v1-with-benchmark
```

---

### Task 5: Rerun Benchmark Preparation And Capture The New Truth

**Files:**
- Generated: `reports/phase1-real-run-2026-06-29/benchmark-mapping.csv`
- Generated: `reports/phase1-real-run-2026-06-29/benchmark-quality.csv`
- Generated: `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md`
- Generated output DB outside repo: `/tmp/fle-run/benchmark-quality-output.sqlite`

- [ ] **Step 1: Run benchmark-aware v1 batch**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
make run-batch-v1-with-benchmark \
  PYTHON=.venv/bin/python \
  OUTPUT_DB=/tmp/fle-run/benchmark-quality-output.sqlite
```

Expected:

```text
processed=142
```

The `run_id=` value is generated at runtime; the command must exit 0 and include `processed=142`.

- [ ] **Step 2: Verify the confirmed false-positive funds no longer have benchmark returns**

Run:

```bash
sqlite3 /tmp/fle-run/source.sqlite "
select fund_code, count(*) rows
from benchmark_returns
where fund_code in ('000251','000368')
group by fund_code;"
```

Expected:

```text
-- no rows --
```

- [ ] **Step 3: Verify benchmark gap labels for those funds**

Run:

```bash
sqlite3 /tmp/fle-run/benchmark-quality-output.sqlite "
select fund_code, label_code, status
from fund_label_results
where fund_code in ('000251','000368')
  and label_code='benchmark_data_missing'
order by fund_code;"
```

Expected:

```text
000251|benchmark_data_missing|observe
000368|benchmark_data_missing|observe
```

- [ ] **Step 4: Record headline counts**

Run:

```bash
sqlite3 /tmp/fle-run/benchmark-quality-output.sqlite "
select label_code, count(distinct fund_code)
from fund_label_results
where label_code in (
  'benchmark_data_missing',
  'alpha_positive',
  'beta_low',
  'beta_high',
  'excess_return_strong',
  'information_ratio_high',
  'tracking_error_high'
)
group by label_code
order by label_code;"
```

Expected: the command exits 0, prints one `label_code|count` row per triggered relative-benchmark label, and includes a `benchmark_data_missing|...` row. Every count must be a decimal integer.

Write the observed counts into `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md` under `## Relative Label Counts After Quality Gate`.

---

### Task 6: Decide Coverage Expansion From The Audit Report

**Files:**
- Modify only after source proof exists: `scripts/fetch_benchmark_returns.py`
- Modify tests if mappings are added: `backend/tests/test_fetch_benchmark_returns.py`
- Modify report: `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md`

- [ ] **Step 1: Sort the gap report by highest fund impact**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
python3 - <<'PY'
import csv
from collections import Counter

path = "reports/phase1-real-run-2026-06-29/benchmark-quality.csv"
counter = Counter()
with open(path, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["quality_status"] == "ready":
            continue
        for item in row["blocking_components"].split(";"):
            if item:
                counter[item] += 1
for component, count in counter.most_common(30):
    print(count, component)
PY
```

Expected top blockers are likely:

```text
H11001:中证全债
H11008:中证综合债
LOCAL_CBOND_TOTAL:中债总
LOCAL_CHINA_BOND_TOTAL:中国债券总
沪深300金融地产行业指数
沪深300安中动态策略指数
恒生指数
```

- [ ] **Step 2: Apply the source rule**

For each blocker, choose exactly one status:

```text
ready_to_add_mapping: exact index identity and daily-return source are verified
source_required: exact index identity is known but no daily-return source exists
mapping_required: benchmark text names an index that is not yet identified
keep_unresolved: benchmark text is ambiguous or missing
```

Write these decisions into the Markdown report under a section named:

```markdown
## Coverage Expansion Decisions
```

- [ ] **Step 3: Keep unverified mappings unresolved**

For this plan, do not add new `INDEX_MAP` rows for `沪深300金融地产行业指数`, `沪深300安中动态策略指数`, `恒生指数`, MSCI, or debt indexes. The implementation deliverable is a correctness gate, not a new vendor data integration. Leave these blockers in the report until a later source-specific plan verifies exact index identity and daily-return availability.

- [ ] **Step 4: Preserve a ready-to-use test pattern for a future verified mapping**

When a later source-specific plan verifies a new mapping, add a concrete test with that verified code and secid. For example, if `沪深300金融地产行业指数` is verified in a later task, replace the current rejection test with a concrete acceptance test in this shape:

```python
def test_parse_verified_hs300_financial_real_estate_index():
    components, audits = parse_benchmark_components(
        "80%×沪深300金融地产行业指数收益率+20%×上证国债指数收益率"
    )

    assert components is not None
    assert components[0].benchmark_name == "沪深300金融地产"
    assert components[0].weight == 0.8
    assert components[1].benchmark_code == "000012"
    assert all(audit.status == "resolved" for audit in audits)
```

Do not add this acceptance test in the current plan; the current plan must keep the confirmed false-positive examples unresolved.

---

### Task 7: Update Runbook And Label Usage Boundary

**Files:**
- Modify: `docs/runbook-batch-workflow.md`

- [ ] **Step 1: Add benchmark quality section**

Add this section after the existing benchmark component source section:

```markdown
## Benchmark Quality Gate

相对基准标签只允许在 benchmark quality 为 `ready` 的基金上解释和展示。

运行顺序：

```bash
make run-batch-v1-with-benchmark \
  PYTHON=.venv/bin/python \
  OUTPUT_DB=/tmp/fle-run/output-v1-with-benchmark.sqlite
```

输出文件：

- `reports/phase1-real-run-2026-06-29/benchmark-mapping.csv`
- `reports/phase1-real-run-2026-06-29/benchmark-quality.csv`
- `reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md`

状态含义：

| status | 含义 | 是否允许相对基准标签 |
|---|---|---|
| `ready` | 组件映射明确，且有可用日收益序列 | 是 |
| `missing_source` | 组件映射明确，但缺少可靠日收益源 | 否 |
| `mapping_required` | 文本命中高风险宽指数，必须补精确映射 | 否 |
| `unresolved` | 暂不支持或解析失败 | 否 |
| `benchmark_missing` | 基金未披露基准 | 否 |

原则：宁可缺失，也不使用宽指数代理。比如 `沪深300金融地产行业指数` 不得自动退化为普通 `沪深300`。
```

- [ ] **Step 2: Run docs grep check**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
rg -n "Benchmark Quality Gate|run-batch-v1-with-benchmark|宁可缺失" docs/runbook-batch-workflow.md
```

Expected:

```text
docs/runbook-batch-workflow.md:## Benchmark Quality Gate
docs/runbook-batch-workflow.md:make run-batch-v1-with-benchmark
docs/runbook-batch-workflow.md:宁可缺失，也不使用宽指数代理。
```

The actual output also includes line numbers.

---

### Task 8: Full Verification

**Files:**
- All modified files from previous tasks.

- [ ] **Step 1: Run backend test suite**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
make test PYTHON=../.venv/bin/python
```

Expected:

```text
passed
```

There must be zero failures.

- [ ] **Step 2: Run benchmark-aware smoke**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
make run-batch-v1-with-benchmark \
  PYTHON=.venv/bin/python \
  OUTPUT_DB=/tmp/fle-run/benchmark-quality-output.sqlite
```

Expected:

```text
processed=142
```

The `run_id=` value is generated at runtime; the command must exit 0 and include `processed=142`.

- [ ] **Step 3: Verify false-positive prevention**

Run:

```bash
sqlite3 /tmp/fle-run/benchmark-quality-output.sqlite "
select fund_code, label_code
from fund_label_results
where fund_code in ('000251','000368')
  and label_code in ('benchmark_data_missing','alpha_positive','beta_low','excess_return_strong')
order by fund_code, label_code;"
```

Expected:

```text
000251|benchmark_data_missing
000368|benchmark_data_missing
```

No relative-performance labels should appear for those two funds until exact benchmark mappings are verified.

- [ ] **Step 4: Commit**

Run:

```bash
cd /Users/xiongjiali/Desktop/code/fund-label-engine
git add \
  scripts/fetch_benchmark_returns.py \
  scripts/audit_benchmark_quality.py \
  backend/tests/test_fetch_benchmark_returns.py \
  backend/tests/test_audit_benchmark_quality.py \
  Makefile \
  docs/runbook-batch-workflow.md \
  docs/superpowers/plans/2026-06-29-benchmark-quality-gate.md \
  reports/phase1-real-run-2026-06-29/benchmark-quality-gate.md \
  reports/phase1-real-run-2026-06-29/benchmark-quality.csv \
  reports/phase1-real-run-2026-06-29/benchmark-mapping.csv
git commit -m "fix: add benchmark quality gate"
```

---

## Recommended Execution Order

1. Task 1-2 first: stop wrong mappings.
2. Task 3-5 second: generate the new benchmark truth.
3. Task 6 third: decide which missing components can be safely expanded.
4. Task 7-8 last: document, verify, and commit.

## Final Acceptance Checklist

- [ ] `000251` no longer maps `沪深300金融地产行业指数` to ordinary `沪深300`.
- [ ] `000368` no longer maps `沪深300安中动态策略指数` to ordinary `沪深300`.
- [ ] Plain `沪深300` composite benchmarks still resolve.
- [ ] Benchmark audit report exists and explains all 142 funds.
- [ ] Relative-benchmark labels are only interpreted for funds with real `benchmark_returns`.
- [ ] Full backend tests pass.
- [ ] Benchmark-aware batch processes 142 funds.
