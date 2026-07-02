"""optimize_draft 单元测试。"""
from app.portfolio.optimize import optimize_draft, summarize_optimization


def _row(fund_code, draft_w, cap):
    return {
        "fund_code": fund_code,
        "draft_weight_pct": draft_w,
        "max_weight_pct": cap,
        "bucket": "core",
    }


def test_optimize_redistributes_to_total_100():
    rows = [_row("A", 60, 50), _row("B", 40, 50)]
    out = optimize_draft(rows)
    total = sum(r["optimized_weight_pct"] for r in out)
    assert abs(total - 100.0) < 1e-6
    # A cap 50, B 应承担 50
    a = next(r for r in out if r["fund_code"] == "A")
    b = next(r for r in out if r["fund_code"] == "B")
    assert a["optimized_weight_pct"] == 50.0
    assert b["optimized_weight_pct"] == 50.0
    assert a["optimized_status"] == "capped"


def test_optimize_does_not_break_when_no_caps_triggered():
    rows = [_row("A", 30, 100), _row("B", 70, 100)]
    out = optimize_draft(rows)
    a = next(r for r in out if r["fund_code"] == "A")
    b = next(r for r in out if r["fund_code"] == "B")
    assert a["optimized_weight_pct"] == 30.0
    assert b["optimized_weight_pct"] == 70.0
    assert a["optimized_status"] == "ok"
    assert b["optimized_status"] == "ok"


def test_optimize_handles_caps_sum_exceeding_total():
    # caps 已经超出 100：剩下按 0
    rows = [_row("A", 60, 80), _row("B", 40, 80)]
    out = optimize_draft(rows)
    total = sum(r["optimized_weight_pct"] for r in out)
    assert total <= 100.0 + 1e-6
    # A、B 都应 ≤ 80
    for r in out:
        assert r["optimized_weight_pct"] <= 80.0


def test_optimize_handles_zero_caps():
    rows = [_row("A", 0, 0), _row("B", 0, 0)]
    out = optimize_draft(rows)
    # cap 全 0：按 total/n 等分
    for r in out:
        assert r["optimized_weight_pct"] == 50.0


def test_optimize_iterates_multiple_redistribution_rounds():
    # 需要多轮 redistribute：3 只基金 cap 较低
    rows = [
        _row("A", 80, 30),  # 超 cap
        _row("B", 10, 30),
        _row("C", 10, 60),
    ]
    out = optimize_draft(rows)
    total = sum(r["optimized_weight_pct"] for r in out)
    assert abs(total - 100.0) < 1e-6
    a = next(r for r in out if r["fund_code"] == "A")
    assert a["optimized_weight_pct"] == 30.0
    assert a["optimized_status"] == "capped"


def test_summarize_returns_counters():
    rows = [_row("A", 60, 50), _row("B", 40, 50)]
    out = optimize_draft(rows)
    s = summarize_optimization(out)
    assert s["total_weight_pct"] == 100.0
    assert s["optimized_funds"] == 2
    # A draft=60 超 cap=50 → capped; B draft=40 不超 cap=50 → ok
    assert s["capped_count"] == 1
    assert s["method"] == "cap_redistribute_v1"


def test_optimize_handles_empty_rows():
    assert optimize_draft([]) == []
    assert summarize_optimization([])["optimized_funds"] == 0
