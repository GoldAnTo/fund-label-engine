from pathlib import Path

from app.batch import run_batch
from app.persistence.reader import LabelRunReader
from app.persistence.writer import LabelRunWriter
from scripts.seed_sample_db import seed


def test_portfolio_role_review_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "fund.sqlite"
    seed(db)
    run_id, _ = run_batch(db)

    writer = LabelRunWriter(db)
    writer.write_portfolio_role_review(
        run_id=run_id,
        fund_code="000001",
        role_code="satellite_alpha",
        decision="accept",
        target_bucket="satellite",
        max_weight_pct=8.0,
        rationale="Alpha role accepted, but cap because drawdown risk exists.",
        reviewer="researcher-a",
    )

    reader = LabelRunReader(db)
    reviews = reader.list_portfolio_role_reviews(run_id)

    assert reviews == [
        {
            "run_id": run_id,
            "fund_code": "000001",
            "role_code": "satellite_alpha",
            "decision": "accept",
            "target_bucket": "satellite",
            "max_weight_pct": 8.0,
            "rationale": "Alpha role accepted, but cap because drawdown risk exists.",
            "reviewer": "researcher-a",
            "reviewed_at": reviews[0]["reviewed_at"],
        }
    ]
