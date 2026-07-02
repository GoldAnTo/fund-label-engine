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


def _exclude_reasons(
    row: dict[str, Any],
    config: dict[str, Any],
    manual_bucket: str | None = None,
) -> list[str]:
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


def build_portfolio_draft(
    matrix_rows: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    role_reviews: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or load_portfolio_constraints()
    role_reviews = role_reviews or {}
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in matrix_rows:
        fund_code = row["fund_code"]
        manual_bucket = _manual_bucket(role_reviews.get(fund_code))
        reasons = _exclude_reasons(row, cfg, manual_bucket)
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
        max_weight = _max_weight(row, cfg)
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
        "rows": sorted(capped, key=lambda item: (-item["draft_weight_pct"], item["fund_code"])),
        "excluded": excluded,
    }
