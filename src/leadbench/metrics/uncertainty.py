"""Uncertainty calibration: does a stated 80% interval actually cover 80%?"""

from __future__ import annotations

import numpy as np


def interval_coverage(
    truth: np.ndarray, lo: np.ndarray, hi: np.ndarray
) -> float:
    truth, lo, hi = (np.asarray(a, float) for a in (truth, lo, hi))
    ok = np.isfinite(truth) & np.isfinite(lo) & np.isfinite(hi)
    if ok.sum() == 0:
        return float("nan")
    return float(((truth[ok] >= lo[ok]) & (truth[ok] <= hi[ok])).mean())


def interval_width(lo: np.ndarray, hi: np.ndarray) -> float:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    ok = np.isfinite(lo) & np.isfinite(hi)
    return float(np.mean(hi[ok] - lo[ok])) if ok.sum() else float("nan")


def uncertainty_summary(
    truth: np.ndarray,
    samples: np.ndarray | None,
    nominal: float = 0.80,
) -> dict[str, float]:
    """``samples`` has shape (S, n). ``truth`` is the quantity being estimated."""
    if samples is None:
        return {
            "coverage_80": float("nan"),
            "interval_width_80": float("nan"),
            "coverage_error_80": float("nan"),
        }
    alpha = (1 - nominal) / 2
    lo = np.quantile(samples, alpha, axis=0)
    hi = np.quantile(samples, 1 - alpha, axis=0)
    cov = interval_coverage(truth, lo, hi)
    return {
        "coverage_80": cov,
        "interval_width_80": interval_width(lo, hi),
        "coverage_error_80": float(cov - nominal) if np.isfinite(cov) else float("nan"),
    }


def crps_gaussian(truth: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> float:
    """Continuous ranked probability score under a Gaussian predictive law."""
    from scipy.stats import norm

    truth, mu, sigma = (np.asarray(a, float) for a in (truth, mu, sigma))
    sigma = np.maximum(sigma, 1e-9)
    z = (truth - mu) / sigma
    val = sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))
    return float(np.mean(val))
