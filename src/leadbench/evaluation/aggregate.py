"""Leaderboards with uncertainty.

The house rule (section 32): no ranking is reported without an interval, and a
"win" requires the paired difference interval to exclude zero *and* the point
estimate to clear the preregistered practical threshold. Anything else is
reported as "no meaningful evidence of difference", which is a result, not a
failure.

Comparisons are paired by seed: both candidates saw the identical generated
population, the identical split and the identical capacity, so the paired
difference removes the between-seed variance that otherwise drowns everything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


def ok_rows(results: pd.DataFrame) -> pd.DataFrame:
    """The rows whose candidate ran successfully.

    Not ``results[results.get("status", "ok") == "ok"]``: ``DataFrame.get``
    returns the *default scalar* when the column is absent, so that expression
    collapses to ``results[True]`` and raises ``KeyError: True``. Suites that
    never record a failure (the online track) have no ``status`` column at all,
    so the missing-column path is the normal one, not an edge case.
    """
    if "status" not in results.columns:
        return results
    return results[results["status"] == "ok"]


def oracle_share(
    results: pd.DataFrame,
    group_cols: Iterable[str] = ("regime",),
    value_col: str = "incremental_net_value_per_1k",
    oracle: str = "oracle",
) -> pd.DataFrame:
    """Share of the Oracle's achievable gain, as a **ratio of means**.

    Deliberately not the mean of the per-row ``pct_of_oracle_incremental``.
    That column divides by the Oracle's incremental gain *on that seed*, which
    is only a safe denominator while the prize is comfortably large. It is not
    always: under ``concept_drift`` the Oracle's gain over doing nothing is
    about $3.0k per 1,000 leads against $109k-$208k in other regimes, because
    drift leaves almost nothing on the table for anybody. Averaging the ratios
    there reported 1,454% of Oracle for ``fifo``, whose raw incremental value
    is *negative*, and 1,344% for ``dr_learner`` -- and those figures then
    dominated the leaderboard mean and inverted it.

    Summing numerator and denominator across seeds before dividing is stable
    however small the prize, and ranks that same regime sensibly (76.5% for
    ``propensity_ev_logit``, -1.2% for ``fifo``).
    """
    ok = ok_rows(results)
    keys = [c for c in group_cols if c in ok.columns]
    ref = ok[ok["candidate"] == oracle].groupby(keys)[value_col].sum()
    num = ok[ok["candidate"] != oracle].groupby(["candidate", *keys])[value_col].sum()
    if num.empty or ref.empty:
        return pd.DataFrame()
    den = num.index.droplevel("candidate").map(ref)
    share = 100.0 * num.to_numpy() / np.asarray(den, dtype=float)
    out = pd.Series(share, index=num.index, name="share").reset_index()
    return out.pivot(index="candidate", columns=keys[0] if len(keys) == 1 else keys,
                     values="share")


@dataclass
class Comparison:
    scenario: str
    candidate: str
    reference: str
    metric: str
    mean_diff: float
    ci_low: float
    ci_high: float
    relative_pct: float
    n_seeds: int
    verdict: str

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _paired_bootstrap(
    diffs: np.ndarray, n_boot: int = 20_000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float]:
    diffs = np.asarray(diffs, dtype=float)
    diffs = diffs[np.isfinite(diffs)]
    if len(diffs) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diffs), (n_boot, len(diffs)))
    means = diffs[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def leaderboard(
    results: pd.DataFrame,
    metric: str = "net_value_per_1k_leads",
    group_cols: Iterable[str] = ("scenario", "regime", "capacity_ratio", "candidate"),
    seed_col: str = "seed",
) -> pd.DataFrame:
    """Mean of ``metric`` per candidate with a bootstrap interval over seeds."""
    ok = ok_rows(results).copy()
    group_cols = [c for c in group_cols if c in ok.columns]
    rows = []
    for key, g in ok.groupby(list(group_cols), dropna=False):
        vals = g[metric].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            continue
        lo, hi = _paired_bootstrap(vals)
        row = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        row.update(
            {
                "metric": metric,
                "mean": float(vals.mean()),
                "sd": float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
                "ci_low": lo,
                "ci_high": hi,
                "n_seeds": int(len(vals)),
            }
        )
        for extra in (
            "family",
            "pct_of_oracle_incremental",
            "fit_seconds",
            "predict_seconds",
            "share_treated",
        ):
            if extra in g.columns:
                v = g[extra]
                row[extra] = v.iloc[0] if v.dtype == object else float(
                    pd.to_numeric(v, errors="coerce").mean()
                )
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        sort_cols = [c for c in group_cols if c != "candidate"]
        out = out.sort_values(sort_cols + ["mean"], ascending=[True] * len(sort_cols) + [False])
    return out.reset_index(drop=True)


def paired_comparisons(
    results: pd.DataFrame,
    reference: str,
    metric: str = "net_value_per_1k_leads",
    practical_threshold_pct: float = 2.0,
    scenario_cols: Iterable[str] = ("scenario", "regime", "capacity_ratio"),
    seed_col: str = "seed",
    n_boot: int = 20_000,
) -> pd.DataFrame:
    """Every candidate versus a reference, paired by seed.

    ``practical_threshold_pct`` is expressed relative to the *reference's*
    absolute level of the metric, and must be preregistered.
    """
    ok = ok_rows(results)
    scenario_cols = [c for c in scenario_cols if c in ok.columns]
    # A cell must hold at most one row per (scenario, candidate, seed). If a
    # suite ever writes two -- a candidate registered by two registry groups,
    # or two run artefacts concatenated -- then `.loc[common]` below returns
    # more rows than the reference has and the paired difference is computed
    # against misaligned seeds, or raises. Collapse them here so the aggregation
    # cannot be corrupted by an upstream duplicate.
    ok = ok.drop_duplicates(subset=[*scenario_cols, "candidate", seed_col],
                            keep="first")
    out: list[Comparison] = []
    for key, g in ok.groupby(list(scenario_cols), dropna=False):
        ref = g[g["candidate"] == reference]
        if ref.empty:
            continue
        ref_by_seed = ref.set_index(seed_col)[metric]
        ref_level = float(np.nanmean(ref_by_seed.to_numpy(dtype=float)))
        scen = "|".join(str(v) for v in (key if isinstance(key, tuple) else (key,)))
        for cand, gc in g.groupby("candidate"):
            if cand == reference:
                continue
            cand_by_seed = gc.set_index(seed_col)[metric]
            common = ref_by_seed.index.intersection(cand_by_seed.index)
            if len(common) < 2:
                continue
            d = (
                cand_by_seed.loc[common].to_numpy(dtype=float)
                - ref_by_seed.loc[common].to_numpy(dtype=float)
            )
            lo, hi = _paired_bootstrap(d, n_boot=n_boot)
            mean_d = float(np.nanmean(d))
            rel = 100.0 * mean_d / abs(ref_level) if abs(ref_level) > 1e-9 else float("nan")
            out.append(
                Comparison(
                    scenario=scen,
                    candidate=cand,
                    reference=reference,
                    metric=metric,
                    mean_diff=mean_d,
                    ci_low=lo,
                    ci_high=hi,
                    relative_pct=rel,
                    n_seeds=len(common),
                    verdict=_verdict(mean_d, lo, hi, rel, practical_threshold_pct),
                )
            )
    return pd.DataFrame([c.to_dict() for c in out])


def _verdict(
    mean_d: float, lo: float, hi: float, rel_pct: float, threshold_pct: float
) -> str:
    if not np.isfinite(lo) or not np.isfinite(hi):
        return "insufficient data"
    if lo <= 0 <= hi:
        return "no meaningful evidence of difference"
    if mean_d > 0:
        if abs(rel_pct) < threshold_pct:
            return "statistically better but below practical threshold"
        return "better"
    if abs(rel_pct) < threshold_pct:
        return "statistically worse but below practical threshold"
    return "worse"


def pareto_frontier(
    board: pd.DataFrame,
    value_col: str = "mean",
    cost_col: str = "fit_seconds",
) -> pd.DataFrame:
    """Candidates not dominated on (higher value, lower cost)."""
    df = board.dropna(subset=[value_col, cost_col]).copy()
    keep = []
    for i, r in df.iterrows():
        dominated = (
            (df[value_col] >= r[value_col])
            & (df[cost_col] <= r[cost_col])
            & ((df[value_col] > r[value_col]) | (df[cost_col] < r[cost_col]))
        ).any()
        if not dominated:
            keep.append(i)
    return df.loc[keep].sort_values(cost_col).reset_index(drop=True)


def summarise_failures(results: pd.DataFrame) -> pd.DataFrame:
    """Every candidate that errored, with the reason. Failures are results."""
    bad = (results[results["status"] != "ok"]
           if "status" in results.columns else results.iloc[:0])
    if bad.empty:
        return pd.DataFrame(columns=["candidate", "scenario", "status", "count"])
    cols = [c for c in ("candidate", "scenario", "regime", "status") if c in bad.columns]
    return (
        bad.groupby(cols, dropna=False).size().reset_index(name="count")
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )
