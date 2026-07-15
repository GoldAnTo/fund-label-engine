"""组合级二次裁决测试。"""
from app.cognition.portfolio_builder import portfolio_risk_review


def _metrics(**overrides):
    base = {
        "portfolio_pe": 30.0,
        "portfolio_volatility": 20.0,
        "portfolio_max_drawdown": -15.0,
        "holdings_penetration": [
            {"stock_code": "001", "stock_name": "测试A", "weight": 5.0},
        ],
        "industry_exposure": [
            {"name": "信息技术", "weight": 25.0},
        ],
        "sector_exposure": [],
    }
    base.update(overrides)
    return base


def _overlap(**overrides):
    base = {"max_overlap_pct": 20.0, "high_overlap_pairs": [], "pairs": []}
    base.update(overrides)
    return base


def test_pass_when_all_within_limits():
    rr = portfolio_risk_review(
        _metrics(), _overlap(), [{"fund_code": "001"}], risk_tolerance="moderate"
    )
    assert rr["verdict"] == "pass"
    assert rr["violations"] == []
    assert rr["enforced_actions"] == []


def test_warn_on_high_industry_concentration():
    rr = portfolio_risk_review(
        _metrics(industry_exposure=[{"name": "半导体", "weight": 45.0}]),
        _overlap(),
        [{"fund_code": "001"}],
        risk_tolerance="moderate",
    )
    assert rr["verdict"] == "warn"
    assert any(v["type"] == "industry_concentration" for v in rr["violations"])
    assert len(rr["enforced_actions"]) == 1
    assert rr["enforced_actions"][0]["factor"] == 0.75


def test_fail_on_extreme_drawdown():
    rr = portfolio_risk_review(
        _metrics(portfolio_max_drawdown=-45.0),
        _overlap(),
        [{"fund_code": "001"}],
        risk_tolerance="moderate",
    )
    assert rr["verdict"] == "fail"
    assert any(v["type"] == "max_drawdown" and v["severity"] == "fail" for v in rr["violations"])
    assert rr["enforced_actions"][0]["factor"] == 0.5


def test_conservative_stricter_than_aggressive():
    metrics = _metrics(industry_exposure=[{"name": "半导体", "weight": 35.0}])
    conservative = portfolio_risk_review(metrics, _overlap(), [{}], "conservative")
    aggressive = portfolio_risk_review(metrics, _overlap(), [{}], "aggressive")
    assert conservative["verdict"] == "warn"
    assert aggressive["verdict"] == "pass"


def test_high_overlap_triggers_warn():
    rr = portfolio_risk_review(
        _metrics(),
        _overlap(max_overlap_pct=45.0, high_overlap_pairs=[["001", "002"]]),
        [{"fund_code": "001"}, {"fund_code": "002"}],
        risk_tolerance="moderate",
    )
    assert rr["verdict"] == "warn"
    assert any(v["type"] == "holdings_overlap" for v in rr["violations"])
