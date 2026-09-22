#!/usr/bin/env python
"""Headline comparisons for the report, recomputed from the run artefacts.

Everything the executive summary claims is produced here, so the claims can be
re-derived rather than trusted:

  * the per-regime leaderboard in % of the Oracle's achievable gain,
  * paired bootstrap differences under the preregistered decision rule,
  * the regime-by-regime verdict that becomes the data-regime map,
  * whether uplift and predictive metrics rank candidates the way money does,
  * the compute-cost table.

    python scripts/headline_analysis.py --runs reports/runs/lead
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

METRIC = "net_value_per_1k_leads"
KEY = ["scenario", "seed"]
# Preregistered: a difference must clear 2% of the reference to count.
THRESHOLD_PCT = 2.0


def paired_diff(frame: pd.DataFrame, a: str, b: str, rng, n_boot: int = 4000):
    """Paired bootstrap of (a - b) over shared (scenario, seed) cells."""
    left = frame[frame.candidate == a].set_index(KEY)[METRIC]
    right = frame[frame.candidate == b].set_index(KEY)[METRIC]
    shared = left.index.intersection(right.index)
    if len(shared) < 4:
        return None
    diff = (left.loc[shared] - right.loc[shared]).to_numpy()
    base = abs(right.loc[shared].to_numpy().mean())
    draws = np.array([
        diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)
    ])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    scale = 100.0 / base if base else np.nan
    return dict(
        n=len(diff), diff=diff.mean(), lo=lo, hi=hi,
        pct=diff.mean() * scale, pct_lo=lo * scale, pct_hi=hi * scale,
    )


def verdict(res: dict) -> str:
    """The preregistered decision rule: interval excludes zero AND clears 2%."""
    if res is None:
        return "no data"
    if res["pct_lo"] > 0 and res["pct"] > THRESHOLD_PCT:
        return "WIN"
    if res["pct_hi"] < 0 and res["pct"] < -THRESHOLD_PCT:
        return "LOSS"
    return "no meaningful difference"


def leaderboard(d: pd.DataFrame) -> pd.DataFrame:
    piv = d[d.candidate != "oracle"].pivot_table(
        index="candidate", columns="regime",
        values="pct_of_oracle_incremental", aggfunc="mean")
    piv["MEAN"] = piv.mean(axis=1)
    return piv.sort_values("MEAN", ascending=False)


def metric_agreement(d: pd.DataFrame) -> pd.DataFrame:
    """Does each secondary metric rank candidates the way realised money does?"""
    rows = []
    for metric in ("uplift_qini_auc", "uplift_auuc", "pred_auroc", "pred_ece",
                   "pred_brier", "causal_pehe", "causal_cate_spearman"):
        rhos = []
        for _, cell in d.groupby(KEY):
            sub = cell.dropna(subset=[metric, "pct_of_oracle_incremental"])
            if len(sub) >= 6:
                rho = stats.spearmanr(sub[metric],
                                      sub.pct_of_oracle_incremental).correlation
                if np.isfinite(rho):
                    rhos.append(rho)
        rows.append(dict(metric=metric, mean_rho=np.mean(rhos), cells=len(rhos)))
    return pd.DataFrame(rows).sort_values("mean_rho", ascending=False)


def top_of_table_check(d: pd.DataFrame) -> pd.DataFrame:
    """A metric can correlate well overall and still misrank the top, which is
    the only part of the table a decision-maker reads."""
    agg = d[d.candidate != "oracle"].groupby("candidate")[
        ["uplift_qini_auc", "pred_auroc", "pct_of_oracle_incremental"]].mean()
    agg = agg.dropna()
    agg["qini_rank"] = agg.uplift_qini_auc.rank(ascending=False)
    agg["auroc_rank"] = agg.pred_auroc.rank(ascending=False)
    agg["money_rank"] = agg.pct_of_oracle_incremental.rank(ascending=False)
    return agg.sort_values("qini_rank")


def compute_cost(d: pd.DataFrame) -> pd.DataFrame:
    cost = d.groupby("candidate").agg(
        fit_s=("fit_seconds", "mean"),
        predict_s=("predict_seconds", "mean"),
        total_fit_s=("fit_seconds", "sum"),
        peak_rss_mb=("peak_rss_delta_mb", "max"),
    )
    cost["share_of_total_pct"] = 100 * cost.total_fit_s / cost.total_fit_s.sum()
    money = d.groupby("candidate")["pct_of_oracle_incremental"].mean()
    cost["pct_of_oracle"] = money
    return cost.sort_values("fit_s", ascending=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="reports/runs/lead")
    ap.add_argument("--reference", default="propensity_ev_logit",
                    help="the simple economic baseline everything must beat")
    ap.add_argument("--analytics", default="hist_conversion_rate",
                    help="the strongest analytics baseline; checked against the "
                         "whole hist_* family before it is used")
    ap.add_argument("--seed", type=int, default=20260922)
    args = ap.parse_args()

    raw = pd.read_csv(Path(args.runs) / "results.csv")
    rng = np.random.default_rng(args.seed)

    # Failed cells carry NaN in every metric. They must be dropped rather than
    # averaged: a single NaN poisons a paired difference into NaN, and a mean
    # that silently skips them compares candidates over different regime sets.
    d = raw[raw.get("status", "ok") == "ok"] if "status" in raw.columns else raw
    failures = raw[raw.status != "ok"] if "status" in raw.columns else raw.iloc[:0]
    regimes = sorted(d.regime.unique())
    print(f"{len(d)} rows, {len(regimes)} regimes, {d.seed.nunique()} seeds")
    if len(failures):
        print(f"\n!! {len(failures)} FAILED cells excluded — these are a result, not noise:")
        summary = (failures.groupby(["regime", "candidate", "status"])
                   .size().rename("cells").reset_index())
        print(summary.to_string(index=False))
        # A candidate missing a whole regime is not comparable on the mean.
        per_regime = d.groupby("candidate").regime.nunique()
        short = per_regime[per_regime < len(regimes)]
        if len(short):
            print("\n   candidates scored on fewer regimes than the full set "
                  f"({len(regimes)}), so their MEAN is not comparable:")
            print(short.to_string())
    print()

    print("=" * 78)
    print("LEADERBOARD — % of the Oracle's achievable gain")
    print("=" * 78)
    print(leaderboard(d).round(1).to_string())

    # Do not take the chosen analytics reference on trust: a falsification
    # study that quietly compares against a weak baseline proves nothing.
    analytics = d[d.candidate.str.startswith(("hist_", "last_click", "lowest_cpl"))]
    ranked = analytics.groupby("candidate").pct_of_oracle_incremental.mean()
    ranked = ranked.sort_values(ascending=False)
    print("\nAnalytics baselines, strongest first:")
    print(ranked.round(2).to_string())
    if ranked.index[0] != args.analytics:
        print(f"\n  !! {ranked.index[0]} outscores the chosen reference "
              f"{args.analytics}; rerun with --analytics {ranked.index[0]}")

    print("\n" + "=" * 78)
    print("PAIRED COMPARISONS — preregistered rule: CI excludes 0 AND |diff| > 2%")
    print("=" * 78)
    # `hist_conversion_rate` rather than the preregistered
    # `hist_profit_per_agent_hour`: on the data it is the *stronger* analytics
    # baseline, and a study built to falsify its own hypothesis compares
    # against the strongest available reference, not the nominated one. Both
    # are reported so the preregistered comparison stays visible.
    pairs = [
        ("s_learner", args.reference),
        ("x_learner", args.reference),
        ("dr_learner", args.reference),
        ("causal_forest", args.reference),
        ("propensity_ev_gbm", args.reference),
        (args.reference, "lead_score_gbm"),
        (args.reference, "lead_score_logit"),
        (args.reference, args.analytics),
        (args.reference, "hist_profit_per_agent_hour"),
        ("s_learner", args.analytics),
        (args.reference, "last_click_attribution"),
        ("lead_score_gbm", args.analytics),
        ("hist_profit_per_agent_hour", args.analytics),
    ]
    print(f"{'comparison':50s} {'$/1k':>9s} {'%ref':>7s} {'95% CI (%)':>18s}  verdict")
    for a, b in pairs:
        res = paired_diff(d, a, b, rng)
        if res is None:
            continue
        print(f"{a + ' - ' + b:50s} {res['diff']:9.0f} {res['pct']:+6.1f}% "
              f"[{res['pct_lo']:+7.1f},{res['pct_hi']:+7.1f}]  {verdict(res)}")

    print("\n" + "=" * 78)
    print(f"DATA-REGIME MAP — causal candidates vs {args.reference}, per regime")
    print("=" * 78)
    causal = ["s_learner", "x_learner", "t_learner", "dr_learner", "causal_forest"]
    header = f"{'regime':32s}" + "".join(f"{c[:13]:>15s}" for c in causal)
    print(header)
    for regime, sub in d.groupby("regime"):
        line = f"{regime:32s}"
        for cand in causal:
            res = paired_diff(sub, cand, args.reference, rng, n_boot=2500)
            if res is None:
                line += f"{'-':>15s}"
                continue
            mark = {"WIN": "*", "LOSS": "!", "no meaningful difference": " "}[verdict(res)]
            line += f"{res['pct']:+13.1f}{mark} "
        print(line)
    print("  * clears the +2% rule   ! loses by more than 2%   blank: no meaningful difference")

    print("\n" + "=" * 78)
    print("DO SECONDARY METRICS RANK CANDIDATES THE WAY MONEY DOES?")
    print("=" * 78)
    print(metric_agreement(d[d.candidate != "oracle"]).round(3).to_string(index=False))
    print("\nTop-of-table check (rank 1 on the metric vs rank on realised money):")
    print(top_of_table_check(d).round(3).to_string())

    print("\n" + "=" * 78)
    print("COMPUTE COST")
    print("=" * 78)
    print(compute_cost(d).round(2).to_string())


if __name__ == "__main__":
    main()
