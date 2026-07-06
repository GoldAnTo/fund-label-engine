"""相对标签可用性的防回归守护。

这几轮反复用人工 SQL 才发现的 bug（如 audit ready 被误判、口径漂移）说明：
audit 的"relative_label_ready"判定与真实跑批 engine 是否产出相对标签，
必须是同一个不变量。本测试把两条代码路径焊死，任一侧漂移都会失败。

守护两层：
1. NAV_WINDOW_MIN_SAMPLES 必须等于 engine 1Y 窗口的 min_samples（同一不变量两处定义）。
2. 对一组 nav/benchmark 长度组合，audit 判 relative_label_ready
   当且仅当真实 LabelEngine 产出 1Y 相对基准特征（annualized_excess_return_1y）。
"""
from __future__ import annotations

import pytest
from app.label_engine.engine import (
    RETURN_WINDOWS,
    FundInput,
    LabelEngine,
)

from scripts.audit_relative_label_eligibility import (
    NAV_WINDOW_MIN_SAMPLES,
    classify_relative_eligibility,
)

_ONE_YEAR_MIN_SAMPLES = next(
    min_samples for name, _size, min_samples in RETURN_WINDOWS if name == "1y"
)


def test_audit_threshold_locked_to_engine_one_year_window():
    # audit 门槛与 engine 1Y 窗口的样本门槛是同一不变量；任一侧改了这里就告警。
    assert NAV_WINDOW_MIN_SAMPLES == _ONE_YEAR_MIN_SAMPLES


def _engine_emits_one_year_relative_feature(nav_len: int, bench_len: int) -> bool:
    fund = FundInput(
        fund_code="T",
        fund_name="t",
        fund_type="混合型",
        nav_returns=[0.001] * nav_len,
        benchmark_returns=[0.0008] * bench_len,
    )
    features = LabelEngine()._calculate_features(fund)
    return any(f.feature_code == "annualized_excess_return_1y" for f in features)


@pytest.mark.parametrize(
    "nav_len,bench_len",
    [
        (241, 241),   # 都够 -> ready
        (257, 194),   # aligned=194>=180 -> ready（补 NAV 后的 100039 形态）
        (20, 241),    # nav 不足 -> 不 ready（补 NAV 前的 100039 形态）
        (241, 120),   # benchmark 合成天数不足 -> 不 ready
        (179, 179),   # 恰好低于门槛 -> 不 ready
        (180, 180),   # 恰好达到门槛 -> ready
    ],
)
def test_audit_ready_iff_engine_emits_relative_feature(nav_len: int, bench_len: int):
    audit_ready = (
        classify_relative_eligibility(
            benchmark_source_status="ready",
            nav_sample_count=nav_len,
            benchmark_sample_count=bench_len,
        )["relative_label_status"]
        == "relative_label_ready"
    )
    engine_ready = _engine_emits_one_year_relative_feature(nav_len, bench_len)
    assert audit_ready == engine_ready


def test_non_ready_benchmark_source_never_relative_ready():
    # 基准源未就绪时，无论 NAV 多长都不能 relative_label_ready。
    for status in ("missing_source", "mapping_required", "unresolved", "benchmark_missing"):
        verdict = classify_relative_eligibility(
            benchmark_source_status=status,
            nav_sample_count=999,
            benchmark_sample_count=999,
        )
        assert verdict["relative_label_status"] != "relative_label_ready"
