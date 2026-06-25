# Fund Factor Exposure Aggregation Design

## Purpose

We will integrate useful ideas from projects such as FundSeeker, xalpha, cjquant,
and portfolio-optimization libraries by adding a narrow first module: a
fund-level factor exposure aggregation layer.

The goal is not to copy an external repository or build a broad FOF platform.
The goal is to turn existing fund holdings plus stock factor values into stable,
queryable fund-level exposures that the label engine can use as evidence.

This module should make the style-label path more durable:

```text
stock_holdings + stock_factor_values
  -> fund_factor_exposures
  -> FundInput.factor_exposures
  -> LabelEngine style labels and evidence
  -> SQLite results / API / frontend report
```

## External Ideas To Borrow

### FundSeeker

Borrow the idea of durable batch-friendly fund data preparation and scoring
inputs. We should not import its recommendation logic directly. Its useful
pattern is: collect raw fund/NAV/factor data first, normalize it, then let a
separate scoring or label layer consume the normalized data.

### xalpha

Borrow the idea of fund holding transparency and underlying-stock exposure.
For this project, the concrete adaptation is holdings-based aggregation:
stock-level factors such as PB, ROE, dividend yield, and revenue growth become
fund-level weighted exposures with explicit coverage weight.

### cjquant

Borrow the RBSA/HBSA framing, but implement only the HBSA slice in this phase.
HBSA means holdings-based style analysis: use actual disclosed holdings and
stock factors to explain a fund's style. RBSA, Brinson attribution, liquidity
simulation, and FOF rebalancing stay outside this spec.

### Portfolio Libraries

Riskfolio-Lib, skfolio, and PyPortfolioOpt are useful later for portfolio lab
experiments. They should not become dependencies of the label engine in this
phase. The label engine should remain a deterministic evidence engine, not a
portfolio optimizer.

## Scope

In scope:

- Add a canonical `fund_factor_exposures` table.
- Add a migration that creates the table and useful indexes.
- Add an aggregation service that computes fund-level exposures from holdings
  and stock factors.
- Persist exposure values with coverage, source, and as-of metadata.
- Extend data access so `FundInput` can carry precomputed fund exposures.
- Update style-label calculation to prefer fund-level exposures when present.
- Keep the existing stock-factor path as fallback for sample DBs and old runs.
- Add API/report/export visibility for the new exposure evidence.
- Add tests for aggregation, fallback behavior, and label outputs.

Out of scope:

- No direct code copying from external repositories.
- No new LLM agent workflow.
- No FOF optimization or portfolio construction.
- No RBSA regression, Brinson attribution, or liquidity backtesting.
- No automatic investment recommendation or admission decision.
- No frontend redesign beyond showing the new exposure evidence in existing
  report surfaces.

## Data Contract

### New Table: `fund_factor_exposures`

Each row represents one fund-level factor exposure for one report date.

| Column | Type | Meaning |
|---|---|---|
| `fund_code` | TEXT | Fund code |
| `report_date` | TEXT | Holding report date used for aggregation |
| `factor_code` | TEXT | Exposure code, such as `pb_weighted` |
| `exposure_value` | REAL | Numeric fund-level exposure |
| `coverage_weight` | REAL | Holding weight covered by usable stock factors |
| `holding_total_weight` | REAL | Total stock holding weight used as denominator reference |
| `stock_count` | INTEGER | Number of holdings inspected |
| `covered_stock_count` | INTEGER | Number of holdings with usable factor data |
| `source` | TEXT | Data source, for example `stock_holdings+stock_factor_values` |
| `as_of_date` | TEXT | Factor snapshot date used by the aggregation run |
| `computed_at` | TEXT | Timestamp when exposure was computed |

Primary key:

```text
(fund_code, report_date, factor_code, as_of_date)
```

Indexes:

- `(fund_code, report_date)`
- `(factor_code, as_of_date)`

### Initial Exposure Codes

The first implementation should compute:

- `pb_weighted`
- `roe_weighted`
- `revenue_growth_weighted`
- `profit_growth_weighted`
- `dividend_yield_weighted`
- `valuation_percentile_weighted`
- `deep_value_weight`
- `quality_growth_weight`
- `dividend_steady_weight`
- `factor_coverage_weight`

The three style weights are calculated with the same thresholds currently used
by `RuleConfig`:

- `deep_value_weight`: holdings where `pb <= deep_value_pb_max` and
  `valuation_percentile <= deep_value_valuation_pct_max`
- `quality_growth_weight`: holdings where `roe >= quality_growth_roe_min` and
  `revenue_growth >= quality_growth_revenue_growth_min`
- `dividend_steady_weight`: holdings where
  `dividend_yield >= dividend_steady_yield_min`

Weighted numeric exposures use the sum of `weight * factor_value` divided by
the weight with that factor present. Style weights use the original fund
holding weight sum, matching the current label-engine semantics.

If the factor loader can preserve per-factor `as_of_date`, the aggregation
should store the latest factor date used for that fund and also include the
per-factor date in debug/export rows where practical. If the loader only has a
single factor snapshot date, use that snapshot date for all exposure rows. This
keeps the table stable while leaving room for better provenance later.

## Architecture

### Aggregation Service

Add a small service module:

```text
backend/app/factors/exposure_aggregator.py
```

Responsibilities:

- Accept a fund code, holdings, stock factors, report date, as-of date, and
  rule config.
- Return a list of exposure records.
- Avoid database writes inside the pure calculation function.
- Keep all threshold-dependent style exposure calculations in one place.

Suggested public functions:

```python
aggregate_factor_exposures(fund: FundInput, rule_config: RuleConfig) -> list[FundFactorExposure]
```

or, if the implementation needs to avoid circular imports:

```python
aggregate_factor_exposures(
    fund_code: str,
    report_date: str,
    holdings: list[dict],
    stock_factors: list[dict],
    rule_config: RuleConfig,
    as_of_date: str | None,
) -> list[FundFactorExposure]
```

### Persistence

Add writer support to upsert exposure rows. This can live in a focused helper
or inside `LabelRunWriter` if the implementation stays small.

The aggregation should run before label evaluation in batch mode, after the
repository loads `FundInput`. The resulting exposures should be attached to
`FundInput` and also persisted to the output DB when using separated source and
output databases.

Important rule: source DBs remain read-only in separated mode. New exposure
rows must go to the output DB.

### Data Access

Extend `FundInput` with:

```python
factor_exposures: list[dict[str, Any]] = field(default_factory=list)
```

Repositories should load existing `fund_factor_exposures` if present. When no
precomputed exposures exist, the batch path can compute them from
`stock_holdings + stock_factors`.

This gives three supported modes:

1. Existing output DB with precomputed exposures: read and use them.
2. Batch source DB with holdings and factors: compute, persist, and use them.
3. Old sample DB without exposures: fallback to current stock-factor path.

### Label Engine

Change the style-label branch so it prefers `fund.factor_exposures`:

- If exposures include `deep_value_weight`, `quality_growth_weight`, or
  `dividend_steady_weight`, use those values directly.
- Evidence source should be `fund_factor_exposures`.
- Evidence message should mention both exposure value and coverage weight.
- If exposures are missing, keep the current stock-factor aggregation fallback.
- If both exposures and stock factors are missing, keep
  `style_unlabeled_stock_factors_missing`.

This keeps current behavior working while making the preferred path auditable
and reusable outside the engine.

## Batch Flow

The revised batch flow should be:

```text
repo.load_fund_input(fund_code)
  -> compute exposures when holdings and stock factors exist
  -> write fund_factor_exposures to output DB
  -> attach exposures to FundInput
  -> LabelEngine.evaluate(fund)
  -> write labels, evidence, features, calculations, classifications, groups
```

Failure behavior:

- If exposure aggregation fails for one fund, record a `fund_run_failures` row
  with stage `aggregate_exposures`.
- Continue evaluating the fund using the fallback stock-factor path when
  enough stock factors are still available.
- If neither exposure nor stock factors are available, emit the existing style
  boundary label.

## API And Frontend Visibility

The first frontend change should be minimal:

- Include factor exposures in the single-fund report payload.
- Show a compact table in `FundReportPage` under feature values or style
  evidence.
- Include exposure rows in run export and single-fund export.

The report should make coverage explicit:

```text
quality_growth_weight = 0.42
coverage_weight = 0.71
source = fund_factor_exposures
```

No new navigation page is required in this phase.

## Testing

Backend tests should cover:

- Aggregator computes weighted numeric exposures correctly.
- Aggregator computes the three style weights using `RuleConfig`.
- Missing factor values reduce coverage but do not crash aggregation.
- Batch persists `fund_factor_exposures` in output DB, not source DB.
- Label engine prefers precomputed exposures over ad hoc stock-factor
  aggregation.
- Label engine falls back to the current stock-factor path when exposures are
  absent.
- API report and export include exposure rows.

Frontend test/build coverage:

- `npm run build` must pass after the report UI adds exposure display.

Regression commands:

```bash
.venv/bin/python -m pytest -q
npm run build
```

## Rollout Plan

Phase A: schema and pure aggregation.

- Add migration for `fund_factor_exposures`.
- Add dataclass or typed dict for exposure rows.
- Add pure aggregation tests.

Phase B: batch persistence and engine consumption.

- Compute exposures during `run_batch`.
- Persist exposures to the output DB.
- Attach exposures to `FundInput`.
- Make style labels prefer exposure rows.

Phase C: API, export, and frontend visibility.

- Add reader methods.
- Add report/export fields.
- Add a compact table in `FundReportPage`.

Phase D: real-run validation.

- Run the Phase1 batch.
- Compare style label counts before and after.
- Sample-check 5 to 10 funds and write a short report under `reports/`.

## Acceptance Criteria

- The project has a canonical fund-level exposure table.
- Batch mode can generate and persist exposure rows for funds with holdings and
  stock factors.
- Style labels can be explained from `fund_factor_exposures`.
- Existing sample and old DB flows continue to work through fallback behavior.
- Source DB remains untouched in separated mode.
- Backend tests and frontend build pass.
- A real Phase1 run shows exposure coverage and style labels in reports.

## Risks And Decisions

- License risk is avoided by not copying external project code.
- Data drift risk is controlled by storing `source`, `as_of_date`, and
  `computed_at`.
- Coverage risk is made visible through `coverage_weight` and
  `covered_stock_count`.
- The first denominator for weighted numeric exposures is covered factor weight,
  while style weights remain raw holding weight. This is intentional: numeric
  exposures should describe the covered subset, while style labels should
  remain conservative about total fund exposure.
- Portfolio optimization remains a later module so the label engine stays
  deterministic and auditable.
