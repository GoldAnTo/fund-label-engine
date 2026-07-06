"""Fama-French 三因子 Alpha 计算。

经典 Fama-French (1993) 三因子模型：
    R_fund - R_f = α + β_mkt·(R_mkt - R_f) + β_smb·SMB + β_hml·HML + ε

输入：
- fund_returns: 基金日收益序列
- market_returns: 宽基日收益（市场因子，对应沪深300等）
- smb_returns: 规模因子日收益（小盘股 - 大盘股）
- hml_returns: 价值因子日收益（低估值股 - 高估值股）
- risk_free_rate: 年化无风险利率

输出：
- alpha_ff3: 年化三因子 Alpha
- betas: {market, smb, hml} 回归系数

降级策略：若 SMB / HML 缺失，自动回退到 CAPM（市场因子单因子）。
"""
from __future__ import annotations

from typing import NamedTuple

ANNUALIZATION_FACTOR = 252.0


class FamaFrenchResult(NamedTuple):
    alpha_annualized: float
    beta_market: float
    beta_smb: float
    beta_hml: float
    r_squared: float
    sample_count: int
    method: str  # "ff3" / "capm_fallback"


def _cumulative(returns: list[float]) -> float:
    """计算累计收益（复利）。"""
    cum = 1.0
    for r in returns:
        cum *= 1.0 + r
    return cum


def _annualized_return(returns: list[float]) -> float:
    """年化收益。"""
    n = len(returns)
    if n == 0:
        return 0.0
    cum = _cumulative(returns)
    if cum <= 0:
        return -1.0
    return cum ** (ANNUALIZATION_FACTOR / n) - 1.0


def _safe_var(samples: list[float]) -> float:
    """样本方差 (n-1 自由度)。"""
    if len(samples) < 2:
        return 0.0
    mean = sum(samples) / len(samples)
    return sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)


def _capm(
    fund_returns: list[float],
    market_returns: list[float],
    risk_free_rate: float,
) -> FamaFrenchResult:
    """CAPM 单因子：fund = rf + beta·(market - rf) + alpha。"""
    n = min(len(fund_returns), len(market_returns))
    if n == 0:
        return FamaFrenchResult(0.0, 0.0, 0.0, 0.0, 0.0, 0, "capm_fallback")
    fund = fund_returns[-n:]
    market = market_returns[-n:]
    rf_daily = (1 + risk_free_rate) ** (1 / ANNUALIZATION_FACTOR) - 1
    fund_excess = [f - rf_daily for f in fund]
    market_excess = [m - rf_daily for m in market]
    cov = sum((f - sum(fund_excess) / n) * (m - sum(market_excess) / n) for f, m in zip(fund_excess, market_excess, strict=False)) / (n - 1)
    var_m = _safe_var(market_excess)
    beta = cov / var_m if var_m > 0 else 0.0
    alpha_daily = (sum(fund_excess) / n) - beta * (sum(market_excess) / n)
    alpha_annualized = (1 + alpha_daily) ** ANNUALIZATION_FACTOR - 1
    r_squared = 0.0
    if var_m > 0 and _safe_var(fund_excess) > 0:
        r_squared = (cov ** 2) / (var_m * _safe_var(fund_excess))
    return FamaFrenchResult(
        alpha_annualized=alpha_annualized,
        beta_market=beta,
        beta_smb=0.0,
        beta_hml=0.0,
        r_squared=r_squared,
        sample_count=n,
        method="capm_fallback",
    )


def compute_ff3_alpha(
    fund_returns: list[float],
    market_returns: list[float],
    smb_returns: list[float] | None = None,
    hml_returns: list[float] | None = None,
    risk_free_rate: float = 0.015,
) -> FamaFrenchResult:
    """Fama-French 三因子回归。

    如果 SMB 或 HML 缺失或长度不足，自动回退到 CAPM 单因子。
    """
    n = min(len(fund_returns), len(market_returns))
    if n < 30:
        # 样本太少也无法做稳健回归
        return FamaFrenchResult(0.0, 0.0, 0.0, 0.0, 0.0, n, "insufficient_data")

    smb_ok = smb_returns is not None and len(smb_returns) >= n
    hml_ok = hml_returns is not None and len(hml_returns) >= n

    if not smb_ok or not hml_ok:
        return _capm(fund_returns, market_returns, risk_free_rate)

    rf_daily = (1 + risk_free_rate) ** (1 / ANNUALIZATION_FACTOR) - 1
    fund_window = fund_returns[-n:]
    market_window = market_returns[-n:]
    smb_window = smb_returns[-n:]
    hml_window = hml_returns[-n:]

    fund_excess = [f - rf_daily for f in fund_window]
    market_excess = [m - rf_daily for m in market_window]
    smb_excess = list(smb_window)
    hml_excess = list(hml_window)

    # OLS 回归 y = X β + ε
    # X 第一列 = market_excess, 第二列 = smb, 第三列 = hml
    y_mean = sum(fund_excess) / n
    x1_mean = sum(market_excess) / n
    x2_mean = sum(smb_excess) / n
    x3_mean = sum(hml_excess) / n

    def mean_centered(x: list[float]) -> list[float]:
        return [v - (sum(x) / len(x)) for v in x]

    y_c = mean_centered(fund_excess)
    x1_c = mean_centered(market_excess)
    x2_c = mean_centered(smb_excess)
    x3_c = mean_centered(hml_excess)

    # 计算 X'X 矩阵 (3x3) 和 X'y 向量 (3)
    # X'X[i][j] = Σ x_i·x_j (centered)
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0, 0.0, 0.0]
    x_cols = [x1_c, x2_c, x3_c]
    for i in range(3):
        for j in range(3):
            xtx[i][j] = sum(x_cols[i][k] * x_cols[j][k] for k in range(n))
        xty[i] = sum(x_cols[i][k] * y_c[k] for k in range(n))

    # 求解 3x3 线性方程组（高斯-约旦消元）
    betas = _solve_3x3(xtx, xty)
    if betas is None:
        return _capm(fund_returns, market_returns, risk_free_rate)
    beta_market, beta_smb, beta_hml = betas

    # Alpha = mean(y) - β'·mean(X)
    alpha_daily = y_mean - (
        beta_market * x1_mean
        + beta_smb * x2_mean
        + beta_hml * x3_mean
    )
    alpha_annualized = (1 + alpha_daily) ** ANNUALIZATION_FACTOR - 1

    # R²
    y_var = sum((y - y_mean) ** 2 for y in fund_excess)
    ss_reg = sum(
        betas[i] * sum(x_cols[i][k] * y_c[k] for k in range(n)) for i in range(3)
    )
    r_squared = ss_reg / y_var if y_var > 0 else 0.0

    return FamaFrenchResult(
        alpha_annualized=alpha_annualized,
        beta_market=beta_market,
        beta_smb=beta_smb,
        beta_hml=beta_hml,
        r_squared=r_squared,
        sample_count=n,
        method="ff3",
    )


def _solve_3x3(xtx: list[list[float]], xty: list[float]) -> list[float] | None:
    """解 3x3 线性方程组 X'X · β = X'y。"""
    n = 3
    # 增广矩阵
    aug = [xtx[i] + [xty[i]] for i in range(n)]

    # 高斯消元
    for i in range(n):
        # 选主元
        pivot = i
        for j in range(i + 1, n):
            if abs(aug[j][i]) > abs(aug[pivot][i]):
                pivot = j
        if abs(aug[pivot][i]) < 1e-12:
            return None
        if pivot != i:
            aug[i], aug[pivot] = aug[pivot], aug[i]

        pivot_val = aug[i][i]
        for j in range(i, n + 1):
            aug[i][j] /= pivot_val

        for j in range(n):
            if j == i:
                continue
            factor = aug[j][i]
            for k in range(i, n + 1):
                aug[j][k] -= factor * aug[i][k]

    return [aug[i][n] for i in range(n)]


def make_synthetic_size_value_factors(
    market_returns: list[float],
    seed: int = 42,
) -> tuple[list[float], list[float]]:
    """生成 SMB / HML 代理序列（当真实数据源缺失时使用）。

    用近似的因子相关性构造代理：
    - SMB ≈ 0.3 * market + 噪声（小盘股波动比大盘大、beta 略高）
    - HML ≈ -0.4 * market - 0.2 * 波动率代理 + 噪声（价值股与成长股周期差）

    这是基于经验的代理，绝非真实因子，仅用于在没有正式 SMB/HML 数据时让
    FF3 模型能跑通——结果不能用于实际投资决策，仅作占位。
    """
    import random

    rng = random.Random(seed)
    smb: list[float] = []
    hml: list[float] = []
    for i, m in enumerate(market_returns):
        # 用前 5 天的市场波动率作为波动率代理
        if i < 5:
            recent_vol = abs(m) * 0.5
        else:
            recent_vol = sum(abs(market_returns[i - 5 + j]) for j in range(5)) / 5
        noise_s = rng.gauss(0, 0.01)
        noise_h = rng.gauss(0, 0.008)
        smb.append(0.3 * m + 0.5 * recent_vol + noise_s)
        hml.append(-0.4 * m - 0.6 * recent_vol + noise_h)
    return smb, hml
