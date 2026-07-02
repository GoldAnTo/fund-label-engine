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


def _max_weight(row: dict[str, Any], config: dict[str, Any]) -> float:
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


ACCEPTED_PORTFOLIO_BUCKETS = {"core", "satellite", "index_tool"}


def _exclude_reasons(
    row: dict[str, Any],
    config: dict[str, Any],
    manual_bucket: str | None = None,
    *,
    accepted_only: bool = False,
    has_accepted_review: bool = False,
) -> list[str]:
    if accepted_only and not has_accepted_review:
        return ["not_signed_off"]
    if accepted_only and manual_bucket not in ACCEPTED_PORTFOLIO_BUCKETS and manual_bucket != "exclude":
        return ["not_accepted_bucket"]
    if manual_bucket == "exclude":
        return ["manual_exclude"]
    blockers = set(config["hard_blockers"])
    reasons = sorted(blockers & set(row.get("watch_reasons", [])))
    if row.get("allocation_status") == "review_required":
        reasons.append("review_required")
    return sorted(set(reasons))


def _manual_bucket(review: Any) -> str | None:
    if isinstance(review, str):
        return review
    if not isinstance(review, dict):
        return None
    if review.get("decision") != "accept":
        return None
    target_bucket = review.get("target_bucket")
    return str(target_bucket) if target_bucket else None


def _manual_max_weight(review: Any) -> float | None:
    if not isinstance(review, dict):
        return None
    if review.get("decision") != "accept":
        return None
    value = review.get("max_weight_pct")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_portfolio_draft(
    matrix_rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    role_reviews: dict[str, Any] | None = None,
    *,
    mode: str = "research",
) -> dict[str, Any]:
    if mode not in {"research", "accepted"}:
        raise ValueError("mode must be 'research' or 'accepted'")
    accepted_only = mode == "accepted"
    cfg = config or load_portfolio_constraints()
    role_reviews = role_reviews or {}
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in matrix_rows:
        fund_code = row["fund_code"]
        review = role_reviews.get(fund_code)
        manual_bucket = _manual_bucket(review)
        manual_max_weight = _manual_max_weight(review)
        has_accepted_review = manual_bucket is not None
        reasons = _exclude_reasons(
            row,
            cfg,
            manual_bucket,
            accepted_only=accepted_only,
            has_accepted_review=has_accepted_review,
        )
        if reasons:
            excluded_row = {"fund_code": fund_code, "reasons": reasons}
            if manual_bucket:
                excluded_row["manual_role_review"] = manual_bucket
            excluded.append(excluded_row)
            continue
        if row.get("allocation_status") not in {"eligible", "observe"}:
            excluded.append({"fund_code": fund_code, "reasons": ["not_candidate_status"]})
            continue
        bucket = manual_bucket if manual_bucket in {"core", "satellite", "index_tool"} else _bucket(row)
        score = _score(row, cfg)
        max_weight = manual_max_weight if manual_max_weight is not None else _max_weight(row, cfg)
        draft_row = {
            "fund_code": fund_code,
            "bucket": bucket,
            "score": score,
            "max_weight_pct": max_weight,
            "portfolio_roles": row.get("portfolio_roles", []),
            "risk_tags": row.get("risk_tags", []),
        }
        if manual_bucket:
            draft_row["manual_role_review"] = manual_bucket
        included.append(draft_row)

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
        "mode": mode,
        "rows": sorted(capped, key=lambda item: (-item["draft_weight_pct"], item["fund_code"])),
        "excluded": excluded,
    }
