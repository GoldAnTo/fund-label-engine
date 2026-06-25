# Fund Classification And Grouping V1

## Goal

Add a deterministic classification/grouping layer on top of the existing label engine so a batch run can answer:

- What kind of fund is this?
- Which comparison or business pool should it enter?
- Which pool did it miss, and why?
- What evidence supports the grouping?

## Scope

- Reuse current labels, coverage, features, and calculation states.
- Persist fund-level classifications and groups in SQLite.
- Return classifications/groups through reader payloads and exports.
- Keep this as an explainable rules layer, not a review workflow or recommendation engine.

## Rule Shape

- Classifications: stable dimensions such as `asset_class`, `management_style`, `calculation_eligibility`, and `style_clarity`.
- Groups: operational pools such as `phase1_active_equity_scope`, `active_equity_candidate_pool`, `passive_tool_pool`, `data_gap_pool`, `style_factor_missing_pool`, and style-specific groups.
- Evidence: each row must carry `reason_code`, `evidence`, and `source`.

## Out Of Scope

- No fixed-income classification.
- No final investment selection.
- No human review workflow expansion.
- No subjective or LLM-only grouping.
