"""Causal-error and uplift metrics.

Uplift metrics (Qini, AUUC) are **secondary** here, on purpose. They score a
ranking, and a ranking is not a decision: they are blind to deal value, to
agent minutes and to the cost of the action. A model can win Qini and lose
money. See ``docs/methodology.md``.
"""

from __future__ import annotations

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Known-truth causal error (synthetic / semi-synthetic only)
# ---------------------------------------------------------------------------


def pehe(true_cate: np.ndarray, est_cate: np.ndarray) -> float:
    """sqrt of the Precision in Estimating Heterogeneous Effects."""
    t, e = np.asarray(true_cate, float), np.asarray(est_cate, float)
    ok = np.isfinite(t) & np.isfinite(e)
    if ok.sum() == 0:
        return float("nan")
    return float(np.sqrt(np.mean((t[ok] - e[ok]) ** 2)))


def ate_error(true_cate: np.ndarray, est_cate: np.ndarray) -> float:
    t, e = np.asarray(true_cate, float), np.asarray(est_cate, float)
    ok = np.isfinite(t) & np.isfinite(e)
    if ok.sum() == 0:
        return float("nan")
    return float(np.mean(e[ok]) - np.mean(t[ok]))


def cate_rank_correlation(true_cate: np.ndarray, est_cate: np.ndarray) -> float:
    t, e = np.asarray(true_cate, float), np.asarray(est_cate, float)
    ok = np.isfinite(t) & np.isfinite(e)
    if ok.sum() < 10 or np.std(e[ok]) < 1e-12:
        return float("nan")
    return float(stats.spearmanr(t[ok], e[ok]).statistic)


def causal_summary(true_cate: np.ndarray, est_cate: np.ndarray) -> dict[str, float]:
    return {
        "pehe": pehe(true_cate, est_cate),
        "ate_error": ate_error(true_cate, est_cate),
        "cate_spearman": cate_rank_correlation(true_cate, est_cate),
    }


# ---------------------------------------------------------------------------
# Uplift ranking metrics (binary treatment)
# ---------------------------------------------------------------------------


def _uplift_curve(
    y: np.ndarray, t: np.ndarray, score: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative incremental conversions as the treated share grows."""
    order = np.argsort(-np.asarray(score, float), kind="stable")
    y, t = np.asarray(y, float)[order], np.asarray(t, int)[order]
    n = len(y)
    ct = np.cumsum(t)
    cc = np.cumsum(1 - t)
    yt = np.cumsum(y * t)
    yc = np.cumsum(y * (1 - t))
    with np.errstate(divide="ignore", invalid="ignore"):
        curve = np.where(ct > 0, yt, 0.0) - np.where(
            cc > 0, yc * np.divide(ct, np.maximum(cc, 1)), 0.0
        )
    return np.arange(1, n + 1), curve


def qini_auc(y: np.ndarray, t: np.ndarray, score: np.ndarray) -> float:
    """Normalised area between the Qini curve and the random line."""
    x, curve = _uplift_curve(y, t, score)
    n = len(x)
    if n == 0:
        return float("nan")
    area = np.trapezoid(curve, x)
    rand = np.trapezoid(curve[-1] * x / n, x)
    denom = abs(rand) if abs(rand) > 1e-12 else 1.0
    return float((area - rand) / denom)


def uplift_at_k(
    y: np.ndarray, t: np.ndarray, score: np.ndarray, k: float = 0.3
) -> float:
    """Difference in conversion rate between treated and control in the top k."""
    order = np.argsort(-np.asarray(score, float), kind="stable")
    m = int(np.ceil(k * len(order)))
    sel = order[:m]
    ys, ts = np.asarray(y, float)[sel], np.asarray(t, int)[sel]
    if ts.sum() == 0 or (1 - ts).sum() == 0:
        return float("nan")
    return float(ys[ts == 1].mean() - ys[ts == 0].mean())


def uplift_summary(
    y: np.ndarray, t: np.ndarray, score: np.ndarray
) -> dict[str, float]:
    """Library-backed where available, with a self-contained fallback."""
    out: dict[str, float] = {}
    try:
        from sklift.metrics import qini_auc_score, uplift_auc_score

        out["qini_auc"] = float(qini_auc_score(y, score, t))
        out["auuc"] = float(uplift_auc_score(y, score, t))
    except Exception:
        out["qini_auc"] = qini_auc(y, t, score)
        out["auuc"] = float("nan")
    out["uplift_at_10"] = uplift_at_k(y, t, score, 0.10)
    out["uplift_at_30"] = uplift_at_k(y, t, score, 0.30)
    return out
