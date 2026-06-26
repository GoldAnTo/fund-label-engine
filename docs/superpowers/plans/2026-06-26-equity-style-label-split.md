# Equity Style Label Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stock-industry-backed dividend style splitting so high-dividend financials, consumer-quality blue chips, and broad dividend funds are separated with explicit evidence.

**Architecture:** Keep the existing stock-factor and contribution layers as the truth source for dividend candidates. Add `stock_industry_map` in the factor DB, aggregate dividend contribution sector mix into `fund_factor_exposures`, and let `LabelEngine` split `dividend_steady` into `high_dividend_financial`, `consumer_quality`, or retained `dividend_steady` using configurable thresholds.

**Tech Stack:** Python 3.13, SQLite migrations, pytest, existing `app.batch`, `app.factors`, `app.data_access`, `app.label_engine`, and report scripts.

---

## File Structure

- Create `backend/app/persistence/migrations/0009_stock_industry_map.sql`
  Defines `stock_industry_map` in migrated DBs.
- Modify `config/rules.v1.json`
  Adds `high_dividend_sector_ratio_min`, `consumer_dominant_ratio_min`, and `sector_coverage_min`.
- Modify `backend/app/label_engine/engine.py`
  Adds config fields, label definitions, style groups, sector-aware dividend split, and evidence.
- Create `backend/app/data_access/stock_industries.py`
  Loads latest stock industry rows from `stock_industry_map`.
- Modify `backend/app/data_access/repository.py`
  Adds `load_stock_industry_map(stock_codes, as_of=None)`.
- Modify `backend/app/data_access/funddata_repository.py`
  Exposes attached factor DB `stock_industry_map` and adds `load_stock_industry_map`.
- Create `backend/app/factors/dividend_sector_mix.py`
  Pure aggregation from dividend contribution rows + industry map to sector mix exposures.
- Modify `backend/app/batch.py`
  Computes sector mix after equity contributions and writes it to `fund_factor_exposures` before `LabelEngine.evaluate`.
- Modify `scripts/fetch_stock_factors.py` or create `scripts/fetch_stock_industries.py`
  Creates/fills `stock_industry_map` in `data/stock_factors.sqlite`.
- Modify `scripts/generate_equity_style_contribution_report.py`
  Reports split counts and sector mix.
- Tests:
  `backend/tests/test_exports_and_migrations.py`,
  `backend/tests/test_stock_industries.py`,
  `backend/tests/test_dividend_sector_mix.py`,
  `backend/tests/test_label_engine.py`,
  `backend/tests/test_stock_factor_integration.py`.

## Factor Exposure Contract

Write these factor exposure rows for the latest dividend contribution period:

| factor_code | exposure_value | coverage_weight |
| --- | ---: | ---: |
| `dividend_sector_financial_ratio` | financial contribution / mapped dividend contribution | sector coverage |
| `dividend_sector_energy_utility_ratio` | energy_utility contribution / mapped dividend contribution | sector coverage |
| `dividend_sector_consumer_ratio` | consumer contribution / mapped dividend contribution | sector coverage |
| `dividend_sector_coverage` | mapped dividend contribution / total dividend contribution | sector coverage |

Use `source="fund_equity_style_contributions+stock_industry_map"` and `as_of_date` equal to the latest stock industry map date used for mapped dividend contribution rows.

---

### Task 1: Schema, RuleConfig, And Label Definitions

**Files:**
- Create: `backend/app/persistence/migrations/0009_stock_industry_map.sql`
- Modify: `backend/app/label_engine/engine.py`
- Modify: `config/rules.v1.json`
- Test: `backend/tests/test_exports_and_migrations.py`
- Test: `backend/tests/test_label_engine.py`

- [ ] **Step 1: Write the migration test**

Add this test to `backend/tests/test_exports_and_migrations.py`:

```python
def test_migrations_create_stock_industry_map_table(tmp_path: Path) -> None:
    db = tmp_path / "industry-map.sqlite"
    run_migrations(db)

    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(stock_industry_map)").fetchall()
        }

    assert "stock_industry_map" in tables
    assert {
        "stock_code",
        "industry_code",
        "industry_name",
        "sector_group",
        "source",
        "as_of_date",
    }.issubset(cols)
```

- [ ] **Step 2: Run the migration test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_migrations_create_stock_industry_map_table -q
```

Expected: FAIL because `stock_industry_map` does not exist.

- [ ] **Step 3: Add the migration**

Create `backend/app/persistence/migrations/0009_stock_industry_map.sql`:

```sql
CREATE TABLE IF NOT EXISTS stock_industry_map (
    stock_code TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    sector_group TEXT NOT NULL CHECK (
        sector_group IN ('financial', 'energy_utility', 'consumer', 'other')
    ),
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    PRIMARY KEY (stock_code, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_industry_map_sector
ON stock_industry_map (sector_group, as_of_date);
```

- [ ] **Step 4: Run the migration test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_exports_and_migrations.py::test_migrations_create_stock_industry_map_table -q
```

Expected: PASS.

- [ ] **Step 5: Write the RuleConfig test**

Extend `test_rule_config_loads_from_json_file` in `backend/tests/test_label_engine.py`:

```python
def test_rule_config_loads_from_json_file(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            {
                "fee_low_threshold": 0.01,
                "style_drift_delta_threshold": 0.3,
                "high_dividend_sector_ratio_min": 0.65,
                "consumer_dominant_ratio_min": 0.55,
                "sector_coverage_min": 0.8,
            }
        ),
        encoding="utf-8",
    )

    cfg = RuleConfig.from_file(path)

    assert cfg.fee_low_threshold == 0.01
    assert cfg.style_drift_delta_threshold == 0.3
    assert cfg.high_dividend_sector_ratio_min == 0.65
    assert cfg.consumer_dominant_ratio_min == 0.55
    assert cfg.sector_coverage_min == 0.8
```

- [ ] **Step 6: Run the RuleConfig test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_label_engine.py::test_rule_config_loads_from_json_file -q
```

Expected: FAIL with unknown or missing RuleConfig fields.

- [ ] **Step 7: Add config fields and label definitions**

In `backend/app/label_engine/engine.py`, add fields after `dividend_steady_weight_min`:

```python
    high_dividend_sector_ratio_min: float = 0.6
    consumer_dominant_ratio_min: float = 0.6
    sector_coverage_min: float = 0.7
```

Add label definitions near the existing style labels:

```python
    {
        "label_code": "high_dividend_financial",
        "label_name": "金融高股息",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利贡献主要来自金融、能源、公用事业、交通运输等传统高股息行业。",
    },
    {
        "label_code": "consumer_quality",
        "label_name": "消费质量",
        "category": "holding_style",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利底层命中但消费行业贡献主导，归为消费质量而非红利稳健。",
    },
    {
        "label_code": "sector_mapping_insufficient",
        "label_name": "行业映射覆盖不足",
        "category": "style_boundary",
        "fund_types": ",".join(sorted(SUPPORTED_ACTIVE_EQUITY_TYPES)),
        "description": "红利贡献股票行业映射覆盖率不足，暂不做金融/消费/红利分流。",
    },
```

Update style group constants:

```python
_STYLE_LABELS = {
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
}
_STYLE_GROUP_BY_LABEL = {
    "deep_value": ("deep_value_group", "深度价值组"),
    "quality_growth": ("quality_growth_group", "质量成长组"),
    "dividend_steady": ("dividend_steady_group", "红利稳健组"),
    "high_dividend_financial": ("high_dividend_financial_group", "金融高股息组"),
    "consumer_quality": ("consumer_quality_group", "消费质量组"),
}
```

Update `thresholds_for` so the three new labels expose their rule thresholds:

```python
            "high_dividend_financial": {
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
                "high_dividend_sector_ratio_min": self.high_dividend_sector_ratio_min,
                "sector_coverage_min": self.sector_coverage_min,
            },
            "consumer_quality": {
                "dividend_steady_weight_min": self.dividend_steady_weight_min,
                "consumer_dominant_ratio_min": self.consumer_dominant_ratio_min,
                "sector_coverage_min": self.sector_coverage_min,
            },
            "sector_mapping_insufficient": {
                "sector_coverage_min": self.sector_coverage_min,
            },
```

- [ ] **Step 8: Update `config/rules.v1.json`**

Add these keys after `dividend_steady_weight_min`:

```json
  "high_dividend_sector_ratio_min": 0.6,
  "consumer_dominant_ratio_min": 0.6,
  "sector_coverage_min": 0.7,
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_exports_and_migrations.py::test_migrations_create_stock_industry_map_table \
  backend/tests/test_label_engine.py::test_rule_config_loads_from_json_file \
  -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/persistence/migrations/0009_stock_industry_map.sql \
  backend/app/label_engine/engine.py \
  config/rules.v1.json \
  backend/tests/test_exports_and_migrations.py \
  backend/tests/test_label_engine.py
git commit -m "feat(equity): add dividend sector split config"
```

---

### Task 2: Stock Industry Map Loader And Data Access

**Files:**
- Create: `backend/app/data_access/stock_industries.py`
- Modify: `backend/app/data_access/repository.py`
- Modify: `backend/app/data_access/funddata_repository.py`
- Test: `backend/tests/test_stock_industries.py`
- Test: `backend/tests/test_stock_factor_integration.py`

- [ ] **Step 1: Write loader tests**

Create `backend/tests/test_stock_industries.py`:

```python
import sqlite3
from pathlib import Path

from app.data_access.stock_industries import load_stock_industry_map


def test_load_stock_industry_map_returns_latest_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "industries.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600000", "801780", "银行", "financial", "fixture", "2025-12-31"),
                ("600000", "801780", "银行", "financial", "fixture", "2026-06-30"),
                ("600519", "801120", "食品饮料", "consumer", "fixture", "2026-06-30"),
            ],
        )
        rows = load_stock_industry_map(conn, ["600000", "600519", "000001"], None)

    assert rows["600000"]["industry_name"] == "银行"
    assert rows["600000"]["as_of_date"] == "2026-06-30"
    assert rows["600519"]["sector_group"] == "consumer"
    assert "000001" not in rows


def test_load_stock_industry_map_returns_empty_when_table_missing(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    with sqlite3.connect(db) as conn:
        rows = load_stock_industry_map(conn, ["600000"], None)

    assert rows == {}
```

- [ ] **Step 2: Run loader tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_industries.py -q
```

Expected: FAIL because `app.data_access.stock_industries` does not exist.

- [ ] **Step 3: Implement the loader**

Create `backend/app/data_access/stock_industries.py`:

```python
from __future__ import annotations

import sqlite3
from typing import Any


def load_stock_industry_map(
    conn: sqlite3.Connection,
    stock_codes: list[str],
    as_of: str | None = None,
) -> dict[str, dict[str, Any]]:
    codes = sorted({str(code) for code in stock_codes if code})
    if not codes or not _table_or_view_exists(conn, "stock_industry_map"):
        return {}

    placeholders = ",".join("?" for _ in codes)
    params: list[Any] = list(codes)
    date_filter = ""
    if as_of is not None:
        date_filter = "AND sim.as_of_date <= ?"
        params.append(as_of)

    sql = f"""
        SELECT sim.stock_code, sim.industry_code, sim.industry_name,
               sim.sector_group, sim.source, sim.as_of_date
        FROM stock_industry_map sim
        JOIN (
            SELECT stock_code, MAX(as_of_date) AS max_date
            FROM stock_industry_map
            WHERE stock_code IN ({placeholders}) {date_filter}
            GROUP BY stock_code
        ) latest
          ON latest.stock_code = sim.stock_code
         AND latest.max_date = sim.as_of_date
        ORDER BY sim.stock_code
    """
    return {
        row["stock_code"]: dict(row)
        for row in conn.execute(sql, params).fetchall()
    }


def _table_or_view_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    if row is not None:
        return True
    row = conn.execute(
        "SELECT name FROM sqlite_temp_master WHERE type='view' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
```

- [ ] **Step 4: Run loader tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_industries.py -q
```

Expected: PASS.

- [ ] **Step 5: Add repository methods**

In `backend/app/data_access/repository.py`, add:

```python
    def load_stock_industry_map(
        self,
        stock_codes: list[str],
        as_of: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            from app.data_access.stock_industries import load_stock_industry_map

            return load_stock_industry_map(conn, stock_codes, as_of)
```

In `backend/app/data_access/funddata_repository.py`, update `_connect` after the `stock_factor_values` temp view block:

```python
            industry_row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='stock_industry_map'"
            ).fetchone()
            if industry_row is None:
                attached_row = conn.execute(
                    "SELECT name FROM factordb.sqlite_master "
                    "WHERE type='table' AND name='stock_industry_map'"
                ).fetchone()
                if attached_row is not None:
                    conn.execute(
                        "CREATE TEMP VIEW stock_industry_map AS "
                        "SELECT * FROM factordb.stock_industry_map"
                    )
```

Add the same `load_stock_industry_map` method to `FundDataRepository`.

- [ ] **Step 6: Add an attached factor DB test**

Add this test to `backend/tests/test_stock_factor_integration.py`:

```python
def test_funddata_repository_loads_attached_stock_industry_map(tmp_path: Path) -> None:
    source_db = tmp_path / "source.sqlite"
    factor_db = tmp_path / "factor.sqlite"
    sqlite3.connect(source_db).close()
    with sqlite3.connect(factor_db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.execute(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            ("601398", "801780", "银行", "financial", "fixture", "2026-06-30"),
        )

    repo = FundDataRepository(source_db, factor_db_path=factor_db)
    rows = repo.load_stock_industry_map(["601398"], None)

    assert rows["601398"]["sector_group"] == "financial"
```

- [ ] **Step 7: Run tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_stock_industries.py \
  backend/tests/test_stock_factor_integration.py::test_funddata_repository_loads_attached_stock_industry_map \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/data_access/stock_industries.py \
  backend/app/data_access/repository.py \
  backend/app/data_access/funddata_repository.py \
  backend/tests/test_stock_industries.py \
  backend/tests/test_stock_factor_integration.py
git commit -m "feat(data): load stock industry map"
```

---

### Task 3: Dividend Sector Mix Aggregator

**Files:**
- Create: `backend/app/factors/dividend_sector_mix.py`
- Test: `backend/tests/test_dividend_sector_mix.py`

- [ ] **Step 1: Write pure aggregation tests**

Create `backend/tests/test_dividend_sector_mix.py`:

```python
from app.factors.dividend_sector_mix import aggregate_dividend_sector_mix


def test_aggregate_dividend_sector_mix_uses_only_matched_dividend_rows() -> None:
    contributions = [
        {"stock_code": "601398", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
        {"stock_code": "600900", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.20, "report_date": "2026-06-30"},
        {"stock_code": "600519", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.10, "report_date": "2026-06-30"},
        {"stock_code": "000001", "style_code": "deep_value", "matched": 1, "contribution_weight": 0.40, "report_date": "2026-06-30"},
    ]
    industry_map = {
        "601398": {"sector_group": "financial", "as_of_date": "2026-06-30"},
        "600900": {"sector_group": "energy_utility", "as_of_date": "2026-06-30"},
        "600519": {"sector_group": "consumer", "as_of_date": "2026-06-30"},
    }

    result = aggregate_dividend_sector_mix("000001", "2026-06-30", contributions, industry_map)

    assert result is not None
    by_code = {item.factor_code: item for item in result}
    assert by_code["dividend_sector_coverage"].exposure_value == 1.0
    assert by_code["dividend_sector_financial_ratio"].exposure_value == 0.5
    assert by_code["dividend_sector_energy_utility_ratio"].exposure_value == 0.333333
    assert by_code["dividend_sector_consumer_ratio"].exposure_value == 0.166667


def test_aggregate_dividend_sector_mix_tracks_missing_industry_coverage() -> None:
    contributions = [
        {"stock_code": "601398", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
        {"stock_code": "600519", "style_code": "dividend_steady", "matched": 1, "contribution_weight": 0.30, "report_date": "2026-06-30"},
    ]
    industry_map = {
        "601398": {"sector_group": "financial", "as_of_date": "2026-06-30"},
    }

    result = aggregate_dividend_sector_mix("000001", "2026-06-30", contributions, industry_map)

    assert result is not None
    by_code = {item.factor_code: item for item in result}
    assert by_code["dividend_sector_coverage"].exposure_value == 0.5
    assert by_code["dividend_sector_financial_ratio"].coverage_weight == 0.5
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_dividend_sector_mix.py -q
```

Expected: FAIL because `app.factors.dividend_sector_mix` does not exist.

- [ ] **Step 3: Implement the aggregator**

Create `backend/app/factors/dividend_sector_mix.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.factors.exposure_aggregator import FundFactorExposure

_SOURCE = "fund_equity_style_contributions+stock_industry_map"
_SECTOR_CODES = (
    ("dividend_sector_financial_ratio", "financial"),
    ("dividend_sector_energy_utility_ratio", "energy_utility"),
    ("dividend_sector_consumer_ratio", "consumer"),
)


def aggregate_dividend_sector_mix(
    fund_code: str,
    report_date: str | None,
    contributions: list[dict[str, Any]],
    industry_map: dict[str, dict[str, Any]],
) -> list[FundFactorExposure]:
    if not report_date:
        return []
    rows = [
        row for row in contributions
        if str(row.get("style_code") or "") == "dividend_steady"
        and int(row.get("matched") or 0) == 1
        and _as_float(row.get("contribution_weight")) > 0
    ]
    if not rows:
        return []

    total = sum(_as_float(row.get("contribution_weight")) for row in rows)
    mapped_total = 0.0
    sector_weight = {"financial": 0.0, "energy_utility": 0.0, "consumer": 0.0}
    industry_dates: list[str] = []
    for row in rows:
        stock_code = str(row.get("stock_code") or "")
        weight = _as_float(row.get("contribution_weight"))
        industry = industry_map.get(stock_code)
        if not industry:
            continue
        sector = str(industry.get("sector_group") or "other")
        mapped_total += weight
        if sector in sector_weight:
            sector_weight[sector] += weight
        if industry.get("as_of_date"):
            industry_dates.append(str(industry["as_of_date"]))

    coverage = mapped_total / total if total > 0 else 0.0
    as_of_date = max(industry_dates) if industry_dates else report_date
    computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = [
        _record(
            fund_code,
            report_date,
            "dividend_sector_coverage",
            coverage,
            coverage,
            total,
            len(rows),
            int(round(len(rows) * coverage)),
            as_of_date,
            computed_at,
        )
    ]
    for factor_code, sector in _SECTOR_CODES:
        ratio = sector_weight[sector] / mapped_total if mapped_total > 0 else 0.0
        result.append(
            _record(
                fund_code,
                report_date,
                factor_code,
                ratio,
                coverage,
                total,
                len(rows),
                int(round(len(rows) * coverage)),
                as_of_date,
                computed_at,
            )
        )
    return result


def _record(
    fund_code: str,
    report_date: str,
    factor_code: str,
    exposure_value: float,
    coverage_weight: float,
    holding_total_weight: float,
    stock_count: int,
    covered_stock_count: int,
    as_of_date: str,
    computed_at: str,
) -> FundFactorExposure:
    return FundFactorExposure(
        fund_code=fund_code,
        report_date=report_date,
        factor_code=factor_code,
        exposure_value=round(exposure_value, 6),
        coverage_weight=round(coverage_weight, 6),
        holding_total_weight=round(holding_total_weight, 6),
        stock_count=stock_count,
        covered_stock_count=covered_stock_count,
        source=_SOURCE,
        as_of_date=as_of_date,
        computed_at=computed_at,
    )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 4: Run aggregator tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_dividend_sector_mix.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/factors/dividend_sector_mix.py backend/tests/test_dividend_sector_mix.py
git commit -m "feat(equity): aggregate dividend sector mix"
```

---

### Task 4: Batch Wiring For Sector Mix Exposures

**Files:**
- Modify: `backend/app/batch.py`
- Test: `backend/tests/test_stock_factor_integration.py`

- [ ] **Step 1: Write integration test**

Add this test to `backend/tests/test_stock_factor_integration.py` using the existing fixture style:

```python
def test_run_batch_persists_dividend_sector_mix_exposures(tmp_path: Path) -> None:
    db = _make_stock_factor_db(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("600001", "801780", "银行", "financial", "fixture", "2026-06-30"),
                ("600002", "801120", "食品饮料", "consumer", "fixture", "2026-06-30"),
            ],
        )

    run_id, processed = run_batch(db, source="funddata")
    assert processed == 1

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT factor_code, exposure_value, coverage_weight "
            "FROM fund_factor_exposures "
            "WHERE factor_code LIKE 'dividend_sector_%' "
            "ORDER BY factor_code"
        ).fetchall()

    assert run_id
    assert {row[0] for row in rows} == {
        "dividend_sector_consumer_ratio",
        "dividend_sector_coverage",
        "dividend_sector_energy_utility_ratio",
        "dividend_sector_financial_ratio",
    }
```

- [ ] **Step 2: Run the integration test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_factor_integration.py::test_run_batch_persists_dividend_sector_mix_exposures -q
```

Expected: FAIL because sector mix exposures are not written.

- [ ] **Step 3: Implement batch wiring**

In `backend/app/batch.py`, import:

```python
from app.factors.dividend_sector_mix import aggregate_dividend_sector_mix
```

Add a helper near `_compute_equity_contributions`:

```python
def _compute_dividend_sector_exposures(
    repo: Any,
    fund: FundInput,
    contributions: list[Any],
) -> list[Any]:
    if not contributions or not hasattr(repo, "load_stock_industry_map"):
        return []
    latest_report_date = max(str(row.report_date) for row in contributions)
    latest_rows = [
        asdict(row)
        for row in contributions
        if str(row.report_date) == latest_report_date
    ]
    stock_codes = sorted({row["stock_code"] for row in latest_rows if row.get("stock_code")})
    industry_map = repo.load_stock_industry_map(stock_codes, None)
    return aggregate_dividend_sector_mix(
        fund_code=fund.fund_code,
        report_date=latest_report_date,
        contributions=latest_rows,
        industry_map=industry_map,
    )
```

Update the run loop after `writer.write_equity_style_contributions(contributions)`:

```python
                    sector_exposures = _compute_dividend_sector_exposures(
                        repo=repo,
                        fund=fund,
                        contributions=contributions,
                    )
                    if sector_exposures:
                        writer.write_factor_exposures(sector_exposures)
                        merged_exposures = [asdict(item) for item in exposures]
                        merged_exposures.extend(asdict(item) for item in sector_exposures)
                        fund = replace(fund, factor_exposures=merged_exposures)
```

- [ ] **Step 4: Run integration test**

Run:

```bash
.venv/bin/python -m pytest backend/tests/test_stock_factor_integration.py::test_run_batch_persists_dividend_sector_mix_exposures -q
```

Expected: PASS.

- [ ] **Step 5: Run existing equity contribution tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_equity_contributions.py \
  backend/tests/test_stock_factor_integration.py::test_run_batch_persists_equity_style_contributions \
  backend/tests/test_stock_factor_integration.py::test_run_batch_contributions_cover_historical_period_when_latest_uncovered \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/batch.py backend/tests/test_stock_factor_integration.py
git commit -m "feat(equity): persist dividend sector mix exposures"
```

---

### Task 5: LabelEngine Dividend Split

**Files:**
- Modify: `backend/app/label_engine/engine.py`
- Test: `backend/tests/test_label_engine.py`

- [ ] **Step 1: Add engine tests for the three branches**

Add helper:

```python
def _fund_with_dividend_sector_exposures(
    financial: float,
    energy: float,
    consumer: float,
    coverage: float = 1.0,
) -> FundInput:
    return FundInput(
        fund_code="110022",
        fund_name="红利分流测试基金",
        fund_type="股票型",
        nav_returns=[0.001] * 30,
        stock_holdings=[
            {"stock_code": "600519", "weight": 0.40},
            {"stock_code": "601398", "weight": 0.30},
        ],
        industry_allocations=[{"industry": "食品饮料", "weight": 0.20}],
        stock_factors=[],
        factor_exposures=[
            {"report_date": "2026-06-30", "factor_code": "factor_coverage_weight", "exposure_value": 0.90, "coverage_weight": 0.90, "holding_total_weight": 0.90},
            {"report_date": "2026-06-30", "factor_code": "dividend_steady_weight", "exposure_value": 0.70, "coverage_weight": 0.90, "holding_total_weight": 0.90},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_financial_ratio", "exposure_value": financial, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_energy_utility_ratio", "exposure_value": energy, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_consumer_ratio", "exposure_value": consumer, "coverage_weight": coverage, "holding_total_weight": 0.70},
            {"report_date": "2026-06-30", "factor_code": "dividend_sector_coverage", "exposure_value": coverage, "coverage_weight": coverage, "holding_total_weight": 0.70},
        ],
        manager_tenure_years=6.2,
        management_fee=0.010,
        custody_fee=0.002,
        fund_size=180.0,
        equity_position=0.89,
    )
```

Add tests:

```python
def test_dividend_sector_split_emits_high_dividend_financial() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.50, energy=0.15, consumer=0.10)
    )

    codes = label_codes(result)
    assert "high_dividend_financial" in codes
    assert "dividend_steady" not in codes


def test_dividend_sector_split_emits_consumer_quality() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.05, energy=0.05, consumer=0.72)
    )

    codes = label_codes(result)
    assert "consumer_quality" in codes
    assert "dividend_steady" not in codes


def test_dividend_sector_split_keeps_broad_dividend_steady() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.25, energy=0.15, consumer=0.20)
    )

    codes = label_codes(result)
    assert "dividend_steady" in codes
    assert "high_dividend_financial" not in codes
    assert "consumer_quality" not in codes


def test_dividend_sector_split_observes_low_sector_coverage() -> None:
    result = LabelEngine().evaluate(
        _fund_with_dividend_sector_exposures(financial=0.80, energy=0.00, consumer=0.00, coverage=0.50)
    )

    codes = label_codes(result)
    assert "sector_mapping_insufficient" in codes
    assert "dividend_steady" in codes
    assert "high_dividend_financial" not in codes
```

- [ ] **Step 2: Run engine tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_label_engine.py::test_dividend_sector_split_emits_high_dividend_financial \
  backend/tests/test_label_engine.py::test_dividend_sector_split_emits_consumer_quality \
  backend/tests/test_label_engine.py::test_dividend_sector_split_keeps_broad_dividend_steady \
  backend/tests/test_label_engine.py::test_dividend_sector_split_observes_low_sector_coverage \
  -q
```

Expected: FAIL because the engine still emits only `dividend_steady`.

- [ ] **Step 3: Implement split helpers**

In `LabelEngine`, add helpers near `_add_style_labels_from_exposures`:

```python
    def _dividend_sector_values(
        self,
        exposure_by_code: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        def value(code: str) -> float:
            row = exposure_by_code.get(code) or {}
            return float(row.get("exposure_value") or 0.0)

        return {
            "financial": value("dividend_sector_financial_ratio"),
            "energy_utility": value("dividend_sector_energy_utility_ratio"),
            "consumer": value("dividend_sector_consumer_ratio"),
            "coverage": value("dividend_sector_coverage"),
        }

    def _dividend_split_label(
        self,
        sector_values: dict[str, float],
    ) -> tuple[str, str, str]:
        cfg = self._rule_config
        high_dividend_ratio = (
            sector_values["financial"] + sector_values["energy_utility"]
        )
        if sector_values["coverage"] < cfg.sector_coverage_min:
            return (
                "dividend_steady",
                "红利稳健",
                "行业映射覆盖不足，保留红利稳健并追加观察标签。",
            )
        if high_dividend_ratio >= cfg.high_dividend_sector_ratio_min:
            return (
                "high_dividend_financial",
                "金融高股息",
                f"金融/能源/公用事业红利贡献占比 {high_dividend_ratio:.0%}。",
            )
        if sector_values["consumer"] >= cfg.consumer_dominant_ratio_min:
            return (
                "consumer_quality",
                "消费质量",
                f"消费红利贡献占比 {sector_values['consumer']:.0%}。",
            )
        return (
            "dividend_steady",
            "红利稳健",
            "红利贡献未被单一金融/能源或消费行业主导。",
        )
```

- [ ] **Step 4: Use the split in `_add_style_labels_from_exposures`**

Replace the `dividend_steady` `_emit(...)` block with:

```python
        if dividend_weight >= cfg.dividend_steady_weight_min:
            sector_values = self._dividend_sector_values(exposure_by_code)
            split_code, split_name, split_message = self._dividend_split_label(sector_values)
            _emit(
                split_code,
                split_name,
                "dividend_steady_weight",
                cfg.dividend_steady_weight_min,
                (
                    f"预聚合红利持仓权重 {dividend_weight:.0%}，"
                    f"达到 {cfg.dividend_steady_weight_min:.0%} 阈值；"
                    f"行业映射覆盖率 {sector_values['coverage']:.0%}；"
                    f"financial={sector_values['financial']:.0%}, "
                    f"energy_utility={sector_values['energy_utility']:.0%}, "
                    f"consumer={sector_values['consumer']:.0%}。{split_message}"
                ),
            )
            if sector_values["coverage"] < cfg.sector_coverage_min:
                labels.append(
                    LabelResult(
                        label_code="sector_mapping_insufficient",
                        label_name="行业映射覆盖不足",
                        category="style_boundary",
                        confidence=1.0,
                        status="observe",
                    )
                )
                evidence.append(
                    EvidenceItem(
                        label_code="sector_mapping_insufficient",
                        metric="dividend_sector_coverage",
                        value=round(sector_values["coverage"], 4),
                        threshold=cfg.sector_coverage_min,
                        source="fund_factor_exposures",
                        message="红利贡献股票行业映射覆盖不足，暂不进行金融/消费/红利分流。",
                    )
                )
```

Apply the same split logic to the fallback `_add_style_labels` path only when sector mix exposures are present. If no sector mix exists, keep current `dividend_steady` behavior for backward compatibility.

- [ ] **Step 5: Run engine tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_label_engine.py::test_dividend_sector_split_emits_high_dividend_financial \
  backend/tests/test_label_engine.py::test_dividend_sector_split_emits_consumer_quality \
  backend/tests/test_label_engine.py::test_dividend_sector_split_keeps_broad_dividend_steady \
  backend/tests/test_label_engine.py::test_dividend_sector_split_observes_low_sector_coverage \
  backend/tests/test_label_engine.py::test_style_labels_emit_style_groups \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/label_engine/engine.py backend/tests/test_label_engine.py
git commit -m "feat(equity): split dividend style labels by sector mix"
```

---

### Task 6: Reports And Validation Gate

**Files:**
- Modify: `backend/app/batch.py`
- Modify: `scripts/generate_equity_style_contribution_report.py`
- Test: `backend/tests/test_stock_factor_integration.py`

- [ ] **Step 1: Add gate test for split labels**

Add a regression test:

```python
def test_equity_factor_gate_accepts_split_dividend_labels_with_contributions(tmp_path: Path) -> None:
    db = _make_stock_factor_db(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE stock_industry_map (
                stock_code TEXT NOT NULL,
                industry_code TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sector_group TEXT NOT NULL,
                source TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                PRIMARY KEY (stock_code, as_of_date)
            )
            """
        )
        conn.execute(
            "INSERT INTO stock_industry_map VALUES (?, ?, ?, ?, ?, ?)",
            ("600001", "801780", "银行", "financial", "fixture", "2026-06-30"),
        )

    run_id, _processed = run_batch(db, source="funddata")

    with sqlite3.connect(db) as conn:
        missing = conn.execute(
            """
            WITH style_labels AS (
              SELECT fund_code, label_code FROM fund_label_results
              WHERE run_id = ?
                AND label_code IN ('dividend_steady', 'high_dividend_financial', 'consumer_quality')
            ),
            contribs AS (
              SELECT fund_code, COUNT(*) AS n FROM fund_equity_style_contributions
              WHERE matched=1 AND style_code='dividend_steady'
              GROUP BY fund_code
            )
            SELECT COUNT(*) FROM style_labels l
            LEFT JOIN contribs c ON c.fund_code=l.fund_code
            WHERE COALESCE(c.n, 0)=0
            """,
            (run_id,),
        ).fetchone()[0]

    assert missing == 0
```

- [ ] **Step 2: Extend validation gate**

In `backend/app/batch.py`, update `STYLE_LABEL_CODES`:

```python
STYLE_LABEL_CODES = (
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
)
```

When checking contribution style code for split labels, map both split labels back to `dividend_steady` contribution rows:

```python
STYLE_CONTRIBUTION_CODE = {
    "deep_value": "deep_value",
    "quality_growth": "quality_growth",
    "dividend_steady": "dividend_steady",
    "high_dividend_financial": "dividend_steady",
    "consumer_quality": "dividend_steady",
}
```

- [ ] **Step 3: Update report constants**

In `scripts/generate_equity_style_contribution_report.py`, update:

```python
STYLE_CODES = (
    "deep_value",
    "quality_growth",
    "dividend_steady",
    "high_dividend_financial",
    "consumer_quality",
)
STYLE_NAMES = {
    "deep_value": "深度价值",
    "quality_growth": "质量成长",
    "dividend_steady": "红利稳健",
    "high_dividend_financial": "金融高股息",
    "consumer_quality": "消费质量",
}
STYLE_WEIGHT_THRESHOLDS = {
    "deep_value": 0.60,
    "quality_growth": 0.50,
    "dividend_steady": 0.50,
    "high_dividend_financial": 0.50,
    "consumer_quality": 0.50,
}
CONTRIBUTION_STYLE_CODE = {
    "deep_value": "deep_value",
    "quality_growth": "quality_growth",
    "dividend_steady": "dividend_steady",
    "high_dividend_financial": "dividend_steady",
    "consumer_quality": "dividend_steady",
}
```

Use `CONTRIBUTION_STYLE_CODE` wherever the report looks up contribution rows for a label.

- [ ] **Step 4: Run focused tests and report smoke**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_stock_factor_integration.py::test_equity_factor_gate_accepts_split_dividend_labels_with_contributions \
  backend/tests/test_stock_factor_integration.py::test_run_batch_persists_dividend_sector_mix_exposures \
  -q
```

Expected: PASS.

Report smoke is covered by Task 7 full replay. This task verifies only split-label gate correctness and report code compatibility through tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/batch.py scripts/generate_equity_style_contribution_report.py backend/tests/test_stock_factor_integration.py
git commit -m "feat(report): include split dividend style labels"
```

---

### Task 7: Industry Map Fill, Full Replay, And Acceptance Report

**Files:**
- Create or modify: `scripts/fetch_stock_industries.py`
- Create: `reports/equity-style-label-split-replay-<run_id>.md`
- Test: full relevant pytest suite

- [ ] **Step 1: Add deterministic CSV import mode for industry map**

Create `scripts/fetch_stock_industries.py` with a CSV import path as the MVP entrypoint. Live Eastmoney endpoint validation is outside this plan; the CSV path makes the first replay deterministic:

```python
def import_csv(conn: sqlite3.Connection, csv_path: Path, as_of_date: str, source: str) -> int:
    rows = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for item in reader:
            stock_code = (item.get("stock_code") or "").strip()
            industry_code = (item.get("industry_code") or "").strip() or "manual"
            industry_name = (item.get("industry_name") or "").strip()
            sector_group = (item.get("sector_group") or "").strip()
            if not stock_code or not industry_name or sector_group not in {
                "financial", "energy_utility", "consumer", "other",
            }:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO stock_industry_map "
                "(stock_code, industry_code, industry_name, sector_group, source, as_of_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (stock_code, industry_code, industry_name, sector_group, source, as_of_date),
            )
            rows += 1
    conn.commit()
    return rows
```

The script should create the same `stock_industry_map` schema as migration `0009`.

- [ ] **Step 2: Seed MVP coverage**

Build a CSV from the top dividend contribution stocks in the latest full report. Include at least these acceptance stocks:

```csv
stock_code,industry_code,industry_name,sector_group
601398,801780,银行,financial
600036,801780,银行,financial
601318,801790,保险,financial
601601,801790,保险,financial
600519,801120,食品饮料,consumer
000858,801120,食品饮料,consumer
600900,801160,电力及公用事业,energy_utility
601857,801960,石油石化,energy_utility
```

Use source `manual.mvp_dividend_sector_seed` for manually curated seed rows.

- [ ] **Step 3: Import seed into factor DB**

Run:

```bash
.venv/bin/python scripts/fetch_stock_industries.py \
  --db data/stock_factors.sqlite \
  --from-csv data/stock_industry_seed.mvp.csv \
  --as-of-date 2026-06-26 \
  --source manual.mvp_dividend_sector_seed
```

Expected: script prints inserted row count greater than 0.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  backend/tests/test_stock_industries.py \
  backend/tests/test_dividend_sector_mix.py \
  backend/tests/test_label_engine.py \
  backend/tests/test_stock_factor_integration.py \
  backend/tests/test_exports_and_migrations.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run full batch replay**

Use the same source DB, factor DB, and `--style-history-periods 2` path as the A/B replay. Keep the output DB separate:

```bash
.venv/bin/python -m app.batch \
  --source-db /tmp/fle-run/source-v5.sqlite \
  --output-db /tmp/fle-run/output-dividend-sector-split.sqlite \
  --source funddata \
  --factor-db data/stock_factors.sqlite \
  --rule-config config/rules.v1.json \
  --style-history-periods 2
```

Expected: processed count equals the baseline full replay count, and the batch exits without gate errors.

- [ ] **Step 6: Verify acceptance samples directly**

Run:

```bash
sqlite3 /tmp/fle-run/output-dividend-sector-split.sqlite "
SELECT fund_code, label_code, status
FROM fund_label_results
WHERE fund_code IN ('159843','001382','512700','159887','000916')
  AND label_code IN ('dividend_steady','high_dividend_financial','consumer_quality','sector_mapping_insufficient')
ORDER BY fund_code, label_code;"
```

Expected:

```text
001382|consumer_quality|active
159843|consumer_quality|observe
159887|high_dividend_financial|observe
512700|high_dividend_financial|observe
```

For `000916`, expected result is one of the red-dividend family labels and not `sector_mapping_insufficient` if the seed covers its main contributors. If `000916` is missing coverage, add its top dividend contributors to the seed CSV and rerun Step 3 and Step 5.

- [ ] **Step 7: Generate report**

Run:

```bash
.venv/bin/python scripts/generate_equity_style_contribution_report.py \
  --db /tmp/fle-run/output-dividend-sector-split.sqlite \
  --run-id <RUN_ID_FROM_BATCH> \
  --out reports/equity-style-label-split-replay-<RUN_ID_PREFIX>.md
```

Expected report includes counts for `high_dividend_financial`, `consumer_quality`, and `dividend_steady`.

- [ ] **Step 8: Compare against baseline**

Run:

```bash
.venv/bin/python scripts/compare_runs.py \
  --before /tmp/fle-run/output-equity-contribution-full.sqlite \
  --after /tmp/fle-run/output-dividend-sector-split.sqlite \
  --label dividend_steady \
  --label high_dividend_financial \
  --label consumer_quality \
  --report reports/compare_dividend_sector_split.md
```

Expected:
- `dividend_steady` count decreases.
- `high_dividend_financial` and `consumer_quality` appear.
- No active/observe labels exist without matching dividend contribution rows.

- [ ] **Step 9: Commit replay evidence**

```bash
git add scripts/fetch_stock_industries.py \
  data/stock_industry_seed.mvp.csv \
  reports/equity-style-label-split-replay-*.md \
  reports/compare_dividend_sector_split.md
git commit -m "test(equity): add dividend sector split replay evidence"
```

---

## Final Verification

Run before declaring the implementation complete:

```bash
.venv/bin/python -m pytest -q
git diff --check
```

Expected:
- All tests pass.
- `git diff --check` has no output.
- Full replay output DB has zero labels in `dividend_steady`, `high_dividend_financial`, or `consumer_quality` without matched `dividend_steady` contribution rows.

Use this SQL for the final gate check:

```sql
WITH red_labels AS (
  SELECT fund_code, label_code FROM fund_label_results
  WHERE label_code IN ('dividend_steady', 'high_dividend_financial', 'consumer_quality')
),
contribs AS (
  SELECT fund_code, COUNT(*) AS n
  FROM fund_equity_style_contributions
  WHERE matched=1 AND style_code='dividend_steady'
  GROUP BY fund_code
)
SELECT COUNT(*)
FROM red_labels l
LEFT JOIN contribs c ON c.fund_code=l.fund_code
WHERE COALESCE(c.n, 0)=0;
```

Expected result: `0`.
