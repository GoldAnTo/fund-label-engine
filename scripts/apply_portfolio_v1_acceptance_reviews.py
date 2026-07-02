"""Apply first-pass portfolio v1 acceptance reviews into portfolio_role_reviews.

This is the first manual-calibration bridge:
- 9 eligible core funds -> accept/core
- 11 eligible satellite funds -> accept/satellite (risk/negative-alpha names get tighter max cap)
- 8 index tools -> accept/index_tool with smaller 3% cap
- 4 review_required / benchmark-missing funds -> accept/exclude

The script writes only to a runtime output DB (default: /tmp/fle-run/output.sqlite).
It is deterministic and can be rerun safely because writer uses INSERT OR REPLACE
on (run_id, fund_code, role_code).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from app.persistence.reader import LabelRunReader
from app.persistence.writer import LabelRunWriter
from app.portfolio.acceptance import classify_eligible

DEFAULT_RUN_ID = "50f9b72de7104761869dc3e86e8a36d2"
DEFAULT_OUTPUT_DB = "/tmp/fle-run/output.sqlite"
DEFAULT_REVIEWER = "portfolio-v1-acceptance"

# 风险/负 alpha satellite 首轮人工校准：收窄上限，不直接 exclude。
SATELLITE_CAP_OVERRIDES = {
    "000017": 3.0,  # 高波动/高跟踪误差，但 alpha 极强：先卫星观察
    "000404": 3.0,  # 高波动/高跟踪误差
    "000531": 3.0,  # 高波动/行业集中
    "000522": 1.0,  # drawdown + volatility + concentration
    "000083": 1.0,  # negative alpha + drawdown
}

INDEX_TOOL_MAX_WEIGHT = 3.0


@dataclass(frozen=True)
class ReviewSeed:
    fund_code: str
    role_code: str
    target_bucket: str
    max_weight_pct: float
    rationale: str


def build_review_seeds_from_payload(
    matrix: dict,
    draft: dict,
) -> list[ReviewSeed]:
    draft_by_code = {row["fund_code"]: row for row in draft["rows"]}
    seeds: list[ReviewSeed] = []

    for row in matrix["rows"]:
        fund_code = row["fund_code"]
        draft_row = draft_by_code.get(fund_code)
        if draft_row:
            row = dict(row)
            row.update(
                {
                    "bucket": draft_row.get("bucket"),
                    "max_weight_pct": draft_row.get("max_weight_pct"),
                    "optimized_weight_pct": draft_row.get("optimized_weight_pct"),
                }
            )
        status = row.get("allocation_status")

        if status == "review_required":
            seeds.append(
                ReviewSeed(
                    fund_code=fund_code,
                    role_code="excluded",
                    target_bucket="exclude",
                    max_weight_pct=0.0,
                    rationale="portfolio v1 acceptance: data_insufficient / benchmark missing, exclude until source is fixed.",
                )
            )
            continue
        if status != "eligible" or draft_row is None:
            continue

        sub_class = classify_eligible(row)
        if sub_class == "core":
            seeds.append(
                ReviewSeed(
                    fund_code=fund_code,
                    role_code="core",
                    target_bucket="core",
                    max_weight_pct=float(draft_row.get("max_weight_pct") or 6.0),
                    rationale="portfolio v1 acceptance: eligible core pool; keep current max cap for first-pass validation.",
                )
            )
        elif sub_class == "index_tool":
            seeds.append(
                ReviewSeed(
                    fund_code=fund_code,
                    role_code="index_tool",
                    target_bucket="index_tool",
                    max_weight_pct=INDEX_TOOL_MAX_WEIGHT,
                    rationale="portfolio v1 acceptance: index tool only; cap at 3% until role confirmed.",
                )
            )
        else:
            cap = SATELLITE_CAP_OVERRIDES.get(
                fund_code,
                min(float(draft_row.get("max_weight_pct") or 5.0), 5.0),
            )
            seeds.append(
                ReviewSeed(
                    fund_code=fund_code,
                    role_code="satellite",
                    target_bucket="satellite",
                    max_weight_pct=cap,
                    rationale=(
                        "portfolio v1 acceptance: satellite bucket; "
                        "risk/negative-alpha names receive tighter first-pass cap."
                    ),
                )
            )
    seeds.sort(key=lambda item: (item.target_bucket, item.fund_code))
    return seeds


def build_review_seeds(output_db: str | Path, run_id: str) -> list[ReviewSeed]:
    reader = LabelRunReader(output_db)
    matrix = reader.get_portfolio_matrix(run_id)
    draft = reader.get_portfolio_draft(run_id)
    if matrix is None or draft is None:
        raise ValueError(f"run not found: {run_id}")
    return build_review_seeds_from_payload(matrix, draft)


def apply_review_seeds(
    output_db: str | Path,
    run_id: str,
    seeds: list[ReviewSeed],
    *,
    reviewer: str = DEFAULT_REVIEWER,
) -> None:
    writer = LabelRunWriter(output_db)
    for seed in seeds:
        writer.write_portfolio_role_review(
            run_id=run_id,
            fund_code=seed.fund_code,
            role_code=seed.role_code,
            decision="accept",
            target_bucket=seed.target_bucket,
            max_weight_pct=seed.max_weight_pct,
            rationale=seed.rationale,
            reviewer=reviewer,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--output-db", default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    seeds = build_review_seeds(args.output_db, args.run_id)
    if not args.dry_run:
        apply_review_seeds(args.output_db, args.run_id, seeds, reviewer=args.reviewer)
    print(
        f"{'would_apply' if args.dry_run else 'applied'} "
        f"{len(seeds)} portfolio role reviews to {args.output_db} (run_id={args.run_id})"
    )
    for seed in seeds:
        print(
            f"{seed.fund_code} {seed.target_bucket} {seed.role_code} "
            f"max={seed.max_weight_pct:.1f}%"
        )


if __name__ == "__main__":
    main()
