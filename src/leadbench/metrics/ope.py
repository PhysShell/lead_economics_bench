"""Offline policy evaluation for logged bandit feedback.

Used on the real randomized datasets (Hillstrom, Criteo), where the
counterfactual is genuinely unobservable and the only honest way to score a
policy is an estimator with stated assumptions.

Every estimator here returns a :class:`OPEResult` carrying a bootstrap
interval **and** support diagnostics. A point estimate from an IPS with an
effective sample size of 40 is not a result, it is a rumour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class OPEResult:
    estimator: str
    value: float
    ci_low: float
    ci_high: float
    ess: float
    n: int
    diagnostics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, float]:
        return {
            f"{self.estimator}_value": self.value,
            f"{self.estimator}_ci_low": self.ci_low,
            f"{self.estimator}_ci_high": self.ci_high,
            f"{self.estimator}_ess": self.ess,
            **{f"{self.estimator}_{k}": v for k, v in self.diagnostics.items()},
        }


def _weights(
    logged_action: np.ndarray,
    target_action: np.ndarray,
    propensity: np.ndarray,
    clip: float | None = None,
) -> np.ndarray:
    match = (np.asarray(logged_action) == np.asarray(target_action)).astype(float)
    p = np.clip(np.asarray(propensity, float), 1e-12, 1.0)
    w = match / p
    if clip is not None:
        w = np.minimum(w, clip)
    return w


def effective_sample_size(w: np.ndarray) -> float:
    s1, s2 = w.sum(), (w**2).sum()
    if s2 <= 0:
        return 0.0
    return float(s1**2 / s2)


def _bootstrap_ci(
    fn, n: int, seed: int, n_boot: int, alpha: float = 0.05
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        vals[b] = fn(idx)
    lo, hi = np.quantile(vals[np.isfinite(vals)], [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def ips(
    reward: np.ndarray,
    logged_action: np.ndarray,
    target_action: np.ndarray,
    propensity: np.ndarray,
    clip: float | None = None,
    n_boot: int = 500,
    seed: int = 0,
) -> OPEResult:
    """Inverse propensity scoring. Unbiased under positivity; high variance."""
    r = np.asarray(reward, float)
    w = _weights(logged_action, target_action, propensity, clip)
    n = len(r)

    def est(idx):
        return float(np.mean(w[idx] * r[idx]))

    lo, hi = _bootstrap_ci(est, n, seed, n_boot)
    return OPEResult(
        "ips",
        est(np.arange(n)),
        lo,
        hi,
        effective_sample_size(w),
        n,
        {"max_weight": float(w.max()), "match_rate": float((w > 0).mean())},
    )


def snips(
    reward: np.ndarray,
    logged_action: np.ndarray,
    target_action: np.ndarray,
    propensity: np.ndarray,
    clip: float | None = None,
    n_boot: int = 500,
    seed: int = 0,
) -> OPEResult:
    """Self-normalised IPS. Biased but far better behaved than raw IPS."""
    r = np.asarray(reward, float)
    w = _weights(logged_action, target_action, propensity, clip)
    n = len(r)

    def est(idx):
        s = w[idx].sum()
        return float((w[idx] * r[idx]).sum() / s) if s > 0 else float("nan")

    lo, hi = _bootstrap_ci(est, n, seed, n_boot)
    return OPEResult(
        "snips",
        est(np.arange(n)),
        lo,
        hi,
        effective_sample_size(w),
        n,
        {"max_weight": float(w.max()), "match_rate": float((w > 0).mean())},
    )


def doubly_robust(
    reward: np.ndarray,
    logged_action: np.ndarray,
    target_action: np.ndarray,
    propensity: np.ndarray,
    q_hat: np.ndarray,
    clip: float | None = None,
    n_boot: int = 500,
    seed: int = 0,
) -> OPEResult:
    """Doubly robust estimator.

    ``q_hat`` has shape (n, A): the fitted reward model for every action.
    Consistent if *either* the propensity model or the reward model is right.
    """
    r = np.asarray(reward, float)
    q = np.asarray(q_hat, float)
    la = np.asarray(logged_action, int)
    ta = np.asarray(target_action, int)
    idx_all = np.arange(len(r))
    w = _weights(la, ta, propensity, clip)
    direct = q[idx_all, ta]
    correction = w * (r - q[idx_all, la])

    def est(idx):
        return float(np.mean(direct[idx] + correction[idx]))

    lo, hi = _bootstrap_ci(est, len(r), seed, n_boot)
    return OPEResult(
        "dr",
        est(idx_all),
        lo,
        hi,
        effective_sample_size(w),
        len(r),
        {"direct_part": float(direct.mean()), "max_weight": float(w.max())},
    )


def support_diagnostics(
    propensity_matrix: np.ndarray,
    target_action: np.ndarray,
    min_propensity: float = 0.01,
) -> dict[str, float]:
    """Positivity check. Report it; do not quietly clip it away.

    ``violation_rate`` is the share of leads whose chosen action had a logging
    probability below ``min_propensity``. Anything above a few percent means
    the OPE estimate is extrapolating, and the honest answer is INSUFFICIENT
    EVIDENCE rather than a number.
    """
    p = np.asarray(propensity_matrix, float)
    ta = np.asarray(target_action, int)
    chosen_p = p[np.arange(len(ta)), ta]
    return {
        "min_target_propensity": float(chosen_p.min()),
        "p05_target_propensity": float(np.quantile(chosen_p, 0.05)),
        "violation_rate": float((chosen_p < min_propensity).mean()),
        "mean_target_propensity": float(chosen_p.mean()),
    }


def evaluate_policy_ope(
    reward: np.ndarray,
    logged_action: np.ndarray,
    target_action: np.ndarray,
    propensity: np.ndarray,
    propensity_matrix: np.ndarray | None = None,
    q_hat: np.ndarray | None = None,
    clip: float | None = None,
    n_boot: int = 400,
    seed: int = 0,
) -> dict[str, float]:
    out: dict[str, float] = {}
    out.update(ips(reward, logged_action, target_action, propensity, clip, n_boot, seed).to_dict())
    out.update(snips(reward, logged_action, target_action, propensity, clip, n_boot, seed).to_dict())
    if q_hat is not None:
        out.update(
            doubly_robust(
                reward, logged_action, target_action, propensity, q_hat, clip, n_boot, seed
            ).to_dict()
        )
    if propensity_matrix is not None:
        out.update(support_diagnostics(propensity_matrix, target_action))
    return out
