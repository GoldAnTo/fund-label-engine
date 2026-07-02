from scripts.apply_portfolio_v1_acceptance_reviews import build_review_seeds_from_payload


def _row(fund_code, status='eligible', roles=None, risks=None, alpha=0.1):
    return {
        'fund_code': fund_code,
        'allocation_status': status,
        'portfolio_roles': roles or ['core_holding_candidate'],
        'risk_tags': risks or [],
        'watch_reasons': [],
        'blocking_reasons': [],
        'alpha_1y': alpha,
        'annualized_volatility_1y': 0.15,
        'max_drawdown_1y': -0.1,
    }


def _draft(fund_code, bucket, cap):
    return {
        'fund_code': fund_code,
        'bucket': bucket,
        'max_weight_pct': cap,
        'optimized_weight_pct': 1.0,
        'draft_weight_pct': 1.0,
        'portfolio_roles': [],
    }


def test_build_review_seeds_classifies_core_satellite_index_and_exclude():
    matrix = {
        'rows': [
            _row('000279'),
            _row('000017', risks=['volatility_high']),
            _row('000368', roles=['index_tool', 'low_cost']),
            _row('100038', status='review_required'),
        ]
    }
    draft = {
        'rows': [
            _draft('000279', 'core', 8.0),
            _draft('000017', 'satellite', 5.0),
            _draft('000368', 'index_tool', 8.0),
        ]
    }

    seeds = build_review_seeds_from_payload(matrix, draft)
    by_code = {s.fund_code: s for s in seeds}

    assert by_code['000279'].target_bucket == 'core'
    assert by_code['000279'].max_weight_pct == 8.0
    assert by_code['000017'].target_bucket == 'satellite'
    assert by_code['000017'].max_weight_pct == 3.0
    assert by_code['000368'].target_bucket == 'index_tool'
    assert by_code['000368'].max_weight_pct == 3.0
    assert by_code['100038'].target_bucket == 'exclude'
    assert by_code['100038'].max_weight_pct == 0.0


def test_build_review_seeds_caps_negative_alpha_satellite_to_one_percent():
    matrix = {'rows': [_row('000083', roles=['active_equity_candidate'], alpha=-0.1)]}
    draft = {'rows': [_draft('000083', 'satellite', 3.0)]}

    [seed] = build_review_seeds_from_payload(matrix, draft)
    assert seed.target_bucket == 'satellite'
    assert seed.max_weight_pct == 1.0


def test_build_review_seeds_skips_observe_without_review_required():
    matrix = {'rows': [_row('000001', status='observe')]}
    draft = {'rows': []}
    assert build_review_seeds_from_payload(matrix, draft) == []
