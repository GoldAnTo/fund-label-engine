from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_portfolio_role_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "portfolio_roles.v1.json"


def load_portfolio_role_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else default_portfolio_role_config_path()
    return json.loads(config_path.read_text(encoding="utf-8"))


def portfolio_feature_columns(config: dict[str, Any]) -> set[str]:
    return set(config.get("feature_columns", []))


def _sorted_intersection(values: set[str], candidates: list[str]) -> list[str]:
    return sorted(values & set(candidates))


def _matches_condition(
    condition: dict[str, Any],
    *,
    allocation_status: str,
    label_codes: set[str],
    active_label_codes: set[str],
    group_codes: set[str],
    classifications: dict[str, str],
) -> bool:
    any_of = condition.get("any_of", [])
    if any_of and not any(
        _matches_condition(
            item,
            allocation_status=allocation_status,
            label_codes=label_codes,
            active_label_codes=active_label_codes,
            group_codes=group_codes,
            classifications=classifications,
        )
        for item in any_of
    ):
        return False

    all_of = condition.get("all_of", [])
    if all_of and not all(
        _matches_condition(
            item,
            allocation_status=allocation_status,
            label_codes=label_codes,
            active_label_codes=active_label_codes,
            group_codes=group_codes,
            classifications=classifications,
        )
        for item in all_of
    ):
        return False

    allowed_status = set(condition.get("allocation_status", []))
    if allowed_status and allocation_status not in allowed_status:
        return False

    all_labels = set(condition.get("all_labels", []))
    if all_labels and not all_labels <= label_codes:
        return False

    any_labels = set(condition.get("any_labels", []))
    if any_labels and not (any_labels & label_codes):
        return False

    none_labels = set(condition.get("none_labels", []))
    if none_labels and (none_labels & label_codes):
        return False

    active_labels = set(condition.get("active_labels", []))
    if active_labels and not active_labels <= active_label_codes:
        return False

    any_group = set(condition.get("any_group", []))
    if any_group and not (any_group & group_codes):
        return False

    classification_rules = condition.get("classification", {})
    for dimension, allowed_values in classification_rules.items():
        if classifications.get(dimension) not in set(allowed_values):
            return False

    return True


def derive_portfolio_profile(
    *,
    label_codes: set[str],
    active_label_codes: set[str],
    group_codes: set[str],
    classifications: dict[str, str],
    review_action: str | None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or load_portfolio_role_config()
    tag_groups = cfg.get("tag_groups", {})

    blocking_reasons = _sorted_intersection(
        label_codes,
        tag_groups.get("review_required_labels", []),
    )
    if review_action == "manual_review":
        blocking_reasons.append("manual_review_action")
    blocking_reasons = sorted(set(blocking_reasons))

    watch_reasons = _sorted_intersection(label_codes, tag_groups.get("watch_labels", []))
    if blocking_reasons:
        allocation_status = "review_required"
    elif watch_reasons:
        allocation_status = "observe"
    else:
        allocation_status = "eligible"

    roles: list[str] = []
    for role in cfg.get("roles", []):
        if _matches_condition(
            role.get("when", {}),
            allocation_status=allocation_status,
            label_codes=label_codes,
            active_label_codes=active_label_codes,
            group_codes=group_codes,
            classifications=classifications,
        ):
            roles.append(role["role_code"])

    return {
        "allocation_status": allocation_status,
        "portfolio_roles": sorted(set(roles)),
        "style_tags": _sorted_intersection(
            active_label_codes,
            tag_groups.get("style_tags", []),
        ),
        "return_tags": _sorted_intersection(
            label_codes,
            tag_groups.get("return_tags", []),
        ),
        "risk_tags": _sorted_intersection(
            label_codes,
            tag_groups.get("risk_tags", []),
        ),
        "data_tags": _sorted_intersection(
            label_codes,
            tag_groups.get("data_tags", []),
        ),
        "blocking_reasons": blocking_reasons,
        "watch_reasons": watch_reasons,
    }
