#!/usr/bin/env python
"""Paired, cluster-robust comparisons on the real randomized-experiment track.

Why this is not just a table of DR intervals.

Each candidate's doubly-robust interval is *marginal*: it covers the sampling
variation of that candidate's own value estimate. Every candidate is scored on
the same test fold from the same randomized experiment, so those intervals
overlap heavily even when one policy is reliably better than another. Reading
overlap as "no difference" is the classic error and it understates what the
data can show.

The right comparison is paired: difference against `random` within a
(seed, budget) cell. But budgets *within a seed share one test fold*, so the
(seed, budget) pairs are not independent and a t-test over all of them is
anti-conservative. So the difference is averaged within a seed first and the
test runs across seeds only — a cluster-robust comparison with df = seeds - 1.
With 3 seeds that is a very conservative test, which is the correct direction
to err in.

    python scripts/real_track_analysis.py --runs reports/runs/real
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

METRIC = "net_value_per_1k_dr"
REFERENCE = "random"
THRESHOLD_PCT = 2.0


def clustered_paired(sub: pd.DataFrame, cand: str, metric: str):
    """Paired difference vs the reference, clustered on seed.

    The percentage is scaled by ``abs(reference)``, and is reported as NaN when
    the reference is too close to zero to divide by. Criteo's conversion
    scenario has a *negative* random baseline -- at a 0.28% outcome rate the
    preregistered cost per treatment exceeds the value it buys, so treating
    anybody loses money -- and dividing by a signed near-zero denominator
    flips the sign of every comparison and inverts the ordering. An earlier
    version of this script did exactly that and reported a candidate that was
    worse than random in raw dollars as "+34.9%, BEATS RANDOM".
    """
    key = ["seed", "budget"]
    ref = sub[sub.candidate == REFERENCE].set_index(key)[metric]
    cur = sub[sub.candidate == cand].set_index(key)[metric]
    shared = cur.index.intersection(ref.index)
    if len(shared) == 0:
        return None
    per_seed = (cur.loc[shared] - ref.loc[shared]).groupby(level="seed").mean().to_numpy()
    if len(per_seed) < 2:
        return None
    mean = per_seed.mean()
    se = per_seed.std(ddof=1) / np.sqrt(len(per_seed))
    crit = stats.t.ppf(0.975, len(per_seed) - 1)
    lo, hi = mean - crit * se, mean + crit * se
    base = float(ref.loc[shared].to_numpy().mean())
    spread = float(np.abs(ref.loc[shared].to_numpy()).mean())
    # A reference whose mean is a small fraction of its own scale cannot
    # anchor a percentage.
    usable = abs(base) > 0.10 * spread and abs(base) > 1e-9
    scale = 100.0 / abs(base) if usable else np.nan
    return dict(seeds=len(per_seed), diff=mean, lo=lo, hi=hi, base=base,
                pct=mean * scale, pct_lo=lo * scale, pct_hi=hi * scale,
                pct_usable=usable)


def verdict(res: dict) -> str:
    """Decided on the raw difference, never on the percentage.

    The interval has to exclude zero in raw units, and the effect has to clear
    the practical threshold -- which can only be expressed as a percentage when
    the reference is a usable denominator. Where it is not, the interval test
    alone decides and the verdict says so.
    """
    if res["lo"] > 0:
        if not res["pct_usable"]:
            return "beats random (raw; % not defined)"
        return "BEATS RANDOM" if res["pct"] > THRESHOLD_PCT else ""
    if res["hi"] < 0:
        if not res["pct_usable"]:
            return "worse than random (raw; % not defined)"
        return "WORSE THAN RANDOM" if res["pct"] < -THRESHOLD_PCT else ""
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="reports/runs/real")
    ap.add_argument("--metric", default=METRIC)
    args = ap.parse_args()

    d = pd.read_csv(Path(args.runs) / "results.csv")
    print(f"{len(d)} rows | {d.scenario.nunique()} scenarios | "
          f"seeds {sorted(d.seed.unique())} | budgets {sorted(d.budget.unique())}")
    print("Paired vs `random`, clustered on seed. Preregistered rule: interval "
          f"excludes zero AND |diff| > {THRESHOLD_PCT}% of the reference.\n")

    for scen, sub in d.groupby("scenario"):
        base = sub[sub.candidate == REFERENCE][args.metric].mean()
        events = sub.pred_mean_observed.mean() * sub.n_test.mean()
        print(f"=== {scen} ===")
        print(f"    random baseline {base:.2f}/1k | outcome rate "
              f"{sub.pred_mean_observed.mean():.4f} | ~{events:,.0f} events in the test fold")
        if base <= 0:
            print("    NOTE: the random policy's own value is <= 0 here, so "
                  "percent-of-reference is meaningless; raw differences only.")
        rows = []
        for cand in sorted(sub.candidate.unique()):
            if cand == REFERENCE:
                continue
            res = clustered_paired(sub, cand, args.metric)
            if res:
                rows.append((cand, res))
        # Sorted by the raw difference. Sorting by percentage inverts the
        # ordering whenever the reference is negative.
        for cand, res in sorted(rows, key=lambda r: -r[1]["diff"]):
            if res["pct_usable"]:
                pct = (f"{res['pct']:+6.1f}%  95% CI "
                       f"[{res['pct_lo']:+7.1f},{res['pct_hi']:+7.1f}]")
            else:
                pct = f"    n/a  95% CI [{res['lo']:+7.3f},{res['hi']:+7.3f}] raw"
            print(f"  {cand:22s} {res['diff']:+8.3f}  {pct}  {verdict(res)}")
        print()

    print("Causal family vs the plain propensity ranking (`response_score`) —")
    print("the real-data version of kill criterion K2:\n")
    for scen, sub in d.groupby("scenario"):
        if "response_score" not in set(sub.candidate):
            continue
        key = ["seed", "budget"]
        ref = sub[sub.candidate == "response_score"].set_index(key)[args.metric]
        line = f"  {scen:34s}"
        for cand in ("s_learner", "t_learner", "x_learner", "dr_learner"):
            cur = sub[sub.candidate == cand].set_index(key)[args.metric]
            shared = cur.index.intersection(ref.index)
            if len(shared) == 0:
                line += f"{'-':>14s}"
                continue
            per_seed = (cur.loc[shared] - ref.loc[shared]).groupby(level="seed").mean().to_numpy()
            ref_vals = ref.loc[shared].to_numpy()
            base = abs(float(ref_vals.mean()))
            spread = float(np.abs(ref_vals).mean())
            mean = per_seed.mean()
            se = per_seed.std(ddof=1) / np.sqrt(len(per_seed))
            crit = stats.t.ppf(0.975, len(per_seed) - 1)
            sig = "*" if (mean - crit * se > 0 or mean + crit * se < 0) else " "
            # Same guard as clustered_paired: a reference sitting near zero
            # cannot anchor a percentage, and printing one invents an effect
            # size out of a small denominator.
            if base > 0.10 * spread and base > 1e-9:
                line += f"{100 * mean / base:+12.1f}%{sig}"
            else:
                line += f"{'n/a':>12s} {sig}"
        print(line)
    print(f"  columns: {'s_learner':>13s}{'t_learner':>13s}{'x_learner':>13s}{'dr_learner':>13s}")
    print("  * interval excludes zero")


if __name__ == "__main__":
    main()
