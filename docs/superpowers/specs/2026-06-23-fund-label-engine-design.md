# Fund Label Engine Design

## Goal

Create a new project under `/Users/xiongjiali/Desktop/code/fund-label-engine` that starts a rule-first, evidence-first fund label calculation engine for asset-management research workflows.

## Baseline

The primary baseline is `nai-he/fund-analysis-agent`, used only as an architectural reference for a FastAPI-backed fund analysis application with separated analysis modules. The project will not copy external source code. `xalpha` is a secondary reference for fund portfolio and holding penetration ideas. `FactorHub` is a secondary reference for future stock-factor lifecycle design.

## First Scope

The first version supports active-equity-heavy funds:

- 股票型
- 混合型-偏股
- 混合型-灵活
- 指数型-股票

The first version outputs data quality labels, basic return/risk labels, holding-structure labels, manager labels, fee/size labels, and boundary labels for missing stock factors.

## Boundaries

The project does not make trading decisions, place orders, produce buy/sell recommendations, or allow LLMs to make final admission decisions. Advanced style labels such as deep value, quality growth, and dividend stable require stock factors. Without stock factors, the engine must emit a boundary label instead of pretending style evidence exists.

## Architecture

The backend is a small Python package. It starts with pure calculation objects before connecting storage or a web API:

```text
FundInput
  -> CoverageEvaluator
  -> FeatureCalculator
  -> RuleEngine
  -> LabelResult + EvidenceItem
```

FastAPI is included as the expected service shell, but the first implementation keeps the calculation engine independent from HTTP.

## Verification

The first tests must prove:

- missing required data produces `data_insufficient` and `manual_review_required`
- concentrated holdings produce `holding_concentration_high` with evidence
- missing stock factors prevents formal style labels and emits `style_unlabeled_stock_factors_missing`

