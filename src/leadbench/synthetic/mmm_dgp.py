"""Aggregate marketing-mix data generating process with known causal truth.

Separate from the lead-level DGP on purpose (section 2): this answers "where
should the next $1,000 of media go?", not "who should we call?". Mixing the two
into one leaderboard would compare methods that solve different problems.

Truth we can score against:
  * per-channel adstock decay and saturation parameters
  * per-channel contribution in every period
  * true ROI and true *marginal* ROI at any spend level
  * the true optimal steady-state budget split
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MMMConfig:
    name: str = "mmm_base"
    seed: int = 0
    n_periods: int = 156  # weeks; 3 years is what MMM vendors ask for
    n_channels: int = 5
    channel_names: tuple[str, ...] = (
        "paid_search",
        "paid_social",
        "display",
        "video",
        "retargeting",
    )

    # -- media response --------------------------------------------------
    #: Geometric adstock retention per channel.
    adstock_alpha: tuple[float, ...] = (0.25, 0.45, 0.60, 0.55, 0.15)
    #: Saturation ceiling (max incremental revenue per period from a channel).
    sat_beta: tuple[float, ...] = (60_000.0, 45_000.0, 22_000.0, 30_000.0, 9_000.0)
    #: Saturation rate: revenue = beta * (1 - exp(-lam * adstocked_spend)).
    sat_lambda: tuple[float, ...] = (7e-5, 5e-5, 3e-5, 4e-5, 1.4e-4)

    # -- spend process -----------------------------------------------------
    base_spend: tuple[float, ...] = (40_000.0, 30_000.0, 18_000.0, 22_000.0, 6_000.0)
    spend_cv: float = 0.30
    #: Cross-channel spend correlation. High correlation is what makes real MMM
    #: identification hard; budgets move together.
    spend_correlation: float = 0.7

    # -- baseline ----------------------------------------------------------
    intercept: float = 120_000.0
    trend_per_period: float = 180.0
    seasonality_amplitude: float = 18_000.0
    seasonality_period: float = 52.0
    price_effect: float = -45_000.0
    promo_effect: float = 25_000.0
    noise_sd: float = 12_000.0

    # -- measurement -------------------------------------------------------
    #: Multiplicative bias in platform-reported (last-touch) revenue per channel.
    #: Retargeting claiming 3x its true contribution is the canonical case.
    attribution_bias: tuple[float, ...] = (1.15, 1.35, 0.85, 0.95, 3.20)
    attribution_noise_cv: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        import dataclasses

        return dataclasses.asdict(self)


@dataclass
class MMMDataset:
    data: pd.DataFrame
    truth: dict[str, Any]
    config: MMMConfig

    @property
    def channels(self) -> list[str]:
        return list(self.config.channel_names[: self.config.n_channels])


def geometric_adstock(x: np.ndarray, alpha: float, max_lag: int = 12) -> np.ndarray:
    """Standard geometric carry-over, normalised so total weight is 1."""
    w = alpha ** np.arange(max_lag + 1)
    w = w / w.sum()
    out = np.zeros_like(x, dtype=float)
    for lag, weight in enumerate(w):
        if lag == 0:
            out += weight * x
        else:
            out[lag:] += weight * x[:-lag]
    return out


def saturate(x: np.ndarray, beta: float, lam: float) -> np.ndarray:
    """Exponential saturation: concave, zero at zero, asymptote at beta."""
    return beta * (1.0 - np.exp(-lam * x))


def steady_state_response(
    spend: np.ndarray, alpha: np.ndarray, beta: np.ndarray, lam: np.ndarray
) -> np.ndarray:
    """Per-period contribution when a constant spend level has fully carried over.

    Geometric adstock with normalised weights converges to the spend level
    itself, so the steady-state adstocked spend equals the per-period spend.
    """
    return saturate(spend, beta, lam)


def generate_mmm(cfg: MMMConfig) -> MMMDataset:
    rng = np.random.default_rng(cfg.seed)
    T, C = cfg.n_periods, cfg.n_channels
    names = list(cfg.channel_names[:C])
    alpha = np.asarray(cfg.adstock_alpha[:C], dtype=float)
    beta = np.asarray(cfg.sat_beta[:C], dtype=float)
    lam = np.asarray(cfg.sat_lambda[:C], dtype=float)
    base = np.asarray(cfg.base_spend[:C], dtype=float)

    # Correlated multiplicative spend shocks.
    corr = np.full((C, C), cfg.spend_correlation)
    np.fill_diagonal(corr, 1.0)
    L = np.linalg.cholesky(corr + 1e-8 * np.eye(C))
    z = rng.standard_normal((T, C)) @ L.T
    sigma = np.sqrt(np.log1p(cfg.spend_cv**2))
    mult = np.exp(sigma * z - 0.5 * sigma**2)
    # A slow budget drift so spend is not stationary, as in real accounts.
    drift = np.linspace(0.8, 1.25, T)[:, None]
    spend = base[None, :] * mult * drift
    spend = np.clip(spend, 0.0, None)

    adstocked = np.column_stack(
        [geometric_adstock(spend[:, c], alpha[c]) for c in range(C)]
    )
    contribution = np.column_stack(
        [saturate(adstocked[:, c], beta[c], lam[c]) for c in range(C)]
    )

    t = np.arange(T)
    season = cfg.seasonality_amplitude * np.sin(2 * np.pi * t / cfg.seasonality_period)
    price = 1.0 + 0.08 * rng.standard_normal(T)
    promo = (rng.random(T) < 0.18).astype(float)
    baseline = (
        cfg.intercept
        + cfg.trend_per_period * t
        + season
        + cfg.price_effect * (price - 1.0)
        + cfg.promo_effect * promo
    )
    noise = cfg.noise_sd * rng.standard_normal(T)
    revenue = baseline + contribution.sum(axis=1) + noise

    # Platform-reported revenue: biased last-touch credit, which is what a
    # dashboard-driven ROAS policy would actually optimise against.
    bias = np.asarray(cfg.attribution_bias[:C], dtype=float)
    reported = contribution * bias[None, :]
    reported *= np.exp(
        cfg.attribution_noise_cv * rng.standard_normal((T, C))
        - 0.5 * cfg.attribution_noise_cv**2
    )

    df = pd.DataFrame({"period": t, "date": pd.date_range("2022-01-03", periods=T, freq="W-MON")})
    for c, nm in enumerate(names):
        df[f"spend_{nm}"] = spend[:, c]
        df[f"reported_revenue_{nm}"] = reported[:, c]
    df["price_index"] = price
    df["promo"] = promo
    df["revenue"] = revenue

    truth = {
        "channels": names,
        "alpha": alpha,
        "beta": beta,
        "lambda": lam,
        "contribution": contribution,
        "baseline": baseline,
        "spend": spend,
        "roi": contribution.sum(axis=0) / np.maximum(spend.sum(axis=0), 1e-9),
        "contribution_share": contribution.sum(axis=0) / contribution.sum(),
        "attribution_bias": bias,
        "reported_roas": reported.sum(axis=0) / np.maximum(spend.sum(axis=0), 1e-9),
        "mean_spend": spend.mean(axis=0),
    }
    return MMMDataset(data=df, truth=truth, config=cfg)


def true_response(dataset: MMMDataset, spend: np.ndarray) -> float:
    """True steady-state per-period revenue contribution at a spend vector."""
    t = dataset.truth
    return float(steady_state_response(np.asarray(spend, float), t["alpha"], t["beta"], t["lambda"]).sum())


def true_marginal_roi(dataset: MMMDataset, spend: np.ndarray) -> np.ndarray:
    """d(contribution)/d(spend) per channel at the given spend level."""
    t = dataset.truth
    s = np.asarray(spend, float)
    return t["beta"] * t["lambda"] * np.exp(-t["lambda"] * s)


MMM_REGIMES: dict[str, dict[str, Any]] = {
    "mmm_standard": dict(n_periods=156),
    # What an SMB actually has: one year of weekly data.
    "mmm_smb_short_history": dict(n_periods=52),
    "mmm_very_short_history": dict(n_periods=30),
    # Budgets that move together are the identification killer.
    "mmm_high_collinearity": dict(n_periods=156, spend_correlation=0.93, spend_cv=0.15),
    "mmm_low_signal": dict(n_periods=156, noise_sd=40_000.0),
    "mmm_long_history": dict(n_periods=260),
}


def make_mmm_config(regime: str, **overrides: Any) -> MMMConfig:
    if regime not in MMM_REGIMES:
        raise KeyError(f"unknown MMM regime {regime!r}; known: {sorted(MMM_REGIMES)}")
    return MMMConfig(name=regime, **{**MMM_REGIMES[regime], **overrides})
