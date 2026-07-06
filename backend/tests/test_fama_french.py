"""Fama-French 3 因子 Alpha 测试。"""
from __future__ import annotations

from app.factors.fama_french import (
    compute_ff3_alpha,
    make_synthetic_size_value_factors,
)
from app.label_engine.engine import FundInput, LabelEngine, RuleConfig

# -----------------------------------------------------------------
# FamaFrench 基本回归测试
# -----------------------------------------------------------------


def test_ff3_falls_back_to_capm_when_smb_missing() -> None:
    """SMB 缺失时自动回退 CAPM。"""
    n = 200
    fund = [0.001 * (i % 7 - 3) * 0.01 for i in range(n)]
    market = [0.001 * ((i + 1) % 5 - 2) * 0.01 for i in range(n)]
    res = compute_ff3_alpha(fund, market, smb_returns=None, hml_returns=market)
    assert res.method == "capm_fallback"
    assert res.beta_smb == 0.0
    assert res.beta_hml == 0.0


def test_ff3_falls_back_to_capm_when_hml_too_short() -> None:
    """HML 长度不足时回退 CAPM。"""
    n = 200
    fund = [0.001 * (i % 7 - 3) * 0.01 for i in range(n)]
    market = [0.001 * ((i + 1) % 5 - 2) * 0.01 for i in range(n)]
    smb_short = [0.001] * 10  # 长度不够
    res = compute_ff3_alpha(fund, market, smb_returns=smb_short, hml_returns=market)
    assert res.method == "capm_fallback"


def test_ff3_runs_full_regression_with_valid_inputs() -> None:
    """三因子齐全时跑完整回归。"""
    n = 200
    fund = [0.001 * (i % 11 - 5) * 0.01 for i in range(n)]
    market = [0.001 * ((i + 1) % 7 - 3) * 0.01 for i in range(n)]
    smb, hml = make_synthetic_size_value_factors(market, seed=7)
    # 给 fund 加上一个 SMB-like alpha，观察 alpha 是否捕获
    fund_with_alpha = [f + 0.0005 for f in fund]
    res = compute_ff3_alpha(fund_with_alpha, market, smb, hml, risk_free_rate=0.0)
    assert res.method == "ff3"
    assert res.sample_count == n
    # alpha 应该是正数（我们故意加了一个 5bps 的常量收益）
    assert res.alpha_annualized > 0
    # 三因子回归后，market beta 应该不为 0
    assert res.beta_market != 0.0
    # R² 在合理范围内
    assert 0 <= res.r_squared <= 1


def test_ff3_insufficient_data_for_short_sample() -> None:
    """样本 < 30 时返回 insufficient_data。"""
    res = compute_ff3_alpha(
        fund_returns=[0.001] * 10,
        market_returns=[0.001] * 10,
        smb_returns=[0.001] * 10,
        hml_returns=[0.001] * 10,
    )
    assert res.method == "insufficient_data"


def test_synthetic_factors_length_matches_market() -> None:
    """合成 SMB/HML 的长度应等于 market。"""
    market = [0.001 * i for i in range(50)]
    smb, hml = make_synthetic_size_value_factors(market)
    assert len(smb) == 50
    assert len(hml) == 50


# -----------------------------------------------------------------
# engine.py 集成测试
# -----------------------------------------------------------------


def _make_fund(nav_returns: list[float], bench_returns: list[float], n: int) -> FundInput:
    assert len(nav_returns) == n
    assert len(bench_returns) == n
    return FundInput(
        fund_code="000001",
        fund_name="测试基金",
        fund_type="active",
        nav_returns=list(nav_returns),
        benchmark_returns=list(bench_returns),
    )


def test_engine_captures_ff3_features_when_enabled() -> None:
    """engine 在 enable_ff3_alpha=True 时输出 beta_smb/beta_hml/alpha_method。"""
    import random

    rng = random.Random(123)
    n = 200  # 满足 1y 窗口的 180 个 min_samples
    fund_returns = [rng.gauss(0, 0.01) for _ in range(n)]
    market_returns = [rng.gauss(0, 0.008) for _ in range(n)]
    smb_returns = [rng.gauss(0, 0.012) for _ in range(n)]
    hml_returns = [rng.gauss(0, 0.010) for _ in range(n)]

    config = RuleConfig(enable_ff3_alpha=True, ff3_min_samples=60)
    engine = LabelEngine(config)

    def loader():
        return smb_returns, hml_returns

    engine.set_ff3_factor_loader(loader)

    fund = _make_fund(fund_returns, market_returns, n)
    result = engine.evaluate(fund)

    # 至少应出现 beta_smb_1y 和 beta_hml_1y 特征
    feature_codes = {f.feature_code for f in result.features}
    assert "beta_smb_1y" in feature_codes
    assert "beta_hml_1y" in feature_codes
    # method 标记
    methods = [f.value for f in result.features if f.feature_code == "alpha_method_1y"]
    assert methods[0] == "ff3"


def test_engine_graceful_fallback_when_loader_returns_none() -> None:
    """loader 返回 None 时，应回退到 CAPM。"""
    config = RuleConfig(enable_ff3_alpha=True, ff3_min_samples=60)
    engine = LabelEngine(config)

    def loader():
        return None, None  # 故意返回 None

    engine.set_ff3_factor_loader(loader)

    n = 200
    fund = _make_fund([0.001] * n, [0.0008] * n, n)
    result = engine.evaluate(fund)
    methods = [f.value for f in result.features if f.feature_code == "alpha_method_1y"]
    assert methods[0] in {"capm", "capm_fallback", "capm_fallback_on_error"}


def test_engine_loader_exceptions_are_caught() -> None:
    """loader 抛异常时回退，不应让 batch 中断。"""
    config = RuleConfig(enable_ff3_alpha=True, ff3_min_samples=60)
    engine = LabelEngine(config)

    def bad_loader():
        raise RuntimeError("API down")

    engine.set_ff3_factor_loader(bad_loader)

    n = 200
    fund = _make_fund([0.001] * n, [0.0008] * n, n)
    # 即使 loader 抛异常，evaluate 也不应抛
    result = engine.evaluate(fund)
    methods = [f.value for f in result.features if f.feature_code == "alpha_method_1y"]
    assert methods[0] == "capm_fallback_on_error"


def test_ff3_disabled_by_default() -> None:
    """默认 enable_ff3_alpha=False 时不应输出 ff3 特征。"""
    engine = LabelEngine(RuleConfig())
    n = 100
    fund = _make_fund([0.001] * n, [0.0008] * n, n)
    result = engine.evaluate(fund)
    feature_codes = {f.feature_code for f in result.features}
    assert "beta_smb_1y" not in feature_codes
    assert "beta_hml_1y" not in feature_codes
