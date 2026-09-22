"""Secondary predictive metrics. Calibration is the one that matters.

An expected-value policy multiplies a probability by a dollar amount. If the
probability is miscalibrated by 30%, the dollars are wrong by 30%, and no
amount of ranking skill (AUROC) repairs that.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


def predictive_summary(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    out: dict[str, float] = {}
    if len(y) == 0 or len(np.unique(y)) < 2:
        return {"log_loss": float("nan"), "brier": float("nan"), "auroc": float("nan")}
    out["log_loss"] = float(log_loss(y, p, labels=[0, 1]))
    out["brier"] = float(brier_score_loss(y, p))
    out["auroc"] = float(roc_auc_score(y, p))
    out["auprc"] = float(average_precision_score(y, p))
    out["ece"] = expected_calibration_error(y, p)
    out["calibration_slope"] = calibration_slope(y, p)
    out["mean_predicted"] = float(p.mean())
    out["mean_observed"] = float(y.mean())
    return out


def expected_calibration_error(
    y: np.ndarray, p: np.ndarray, n_bins: int = 20
) -> float:
    """Quantile-binned |observed - predicted|, weighted by bin size."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    if len(y) == 0:
        return float("nan")
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        return float(abs(y.mean() - p.mean()))
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, len(edges) - 2)
    total = 0.0
    for b in range(len(edges) - 1):
        m = idx == b
        if m.sum() == 0:
            continue
        total += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(total)


def calibration_slope(y: np.ndarray, p: np.ndarray) -> float:
    """Slope of a logistic recalibration. 1.0 is perfect; <1 means overconfident."""
    from sklearn.linear_model import LogisticRegression

    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    lo = np.log(p / (1 - p)).reshape(-1, 1)
    try:
        m = LogisticRegression(max_iter=1000).fit(lo, y)
        return float(m.coef_[0][0])
    except Exception:
        return float("nan")


def calibration_curve_points(
    y: np.ndarray, p: np.ndarray, n_bins: int = 10
) -> dict[str, list[float]]:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        return {"predicted": [], "observed": [], "count": []}
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, len(edges) - 2)
    pred, obs, cnt = [], [], []
    for b in range(len(edges) - 1):
        m = idx == b
        if m.sum() == 0:
            continue
        pred.append(float(p[m].mean()))
        obs.append(float(y[m].mean()))
        cnt.append(float(m.sum()))
    return {"predicted": pred, "observed": obs, "count": cnt}
