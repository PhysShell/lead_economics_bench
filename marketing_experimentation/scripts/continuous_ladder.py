#!/usr/bin/env python
"""The information ladder, with a real prior over effect size and five actions.

Everything published in this track so far lives in a two-point,
two-action world: theta in {0, +7.5%}, act or don't. Two limitations were
recorded there and both are load-bearing:

  * "the interval adds nothing on top of the point estimate" may be an
    artefact of two truths, where the point estimate nearly identifies the
    state on its own and leaves the interval nothing to contribute;
  * with two actions an experiment only has to say which side of a threshold
    theta falls on, so a significance bit is nearly a sufficient statistic
    and the measured compression tax is a lower bound.

This script removes both at once, which is the only way to find out whether
either mattered. It needs the atlas run (M7) -- several simulated truths,
including negative ones.

What changes, concretely
------------------------
    prior       a spike-and-slab over theta, 27% of its mass below zero,
                instead of a coin flip between two points
    actions     cut hard / cut / hold / increase / increase hard, with a
                quadratic adjustment cost, instead of hold / scale
    likelihood  p(y | theta) estimated at every simulated theta, either
                empirically per arm or as a smooth conditional model

Two likelihood modes, because the choice is not innocent
--------------------------------------------------------
    --mode discrete   one KDE per simulated theta. Makes no assumption about
                      how the estimator behaves between the simulated
                      truths, and restricts the decision to those truths.
    --mode smooth     y | theta ~ Normal(a + b*theta, s(theta)), fitted
                      across arms. Uses the whole grid, and assumes the
                      estimator is well behaved between the points we
                      simulated -- which the atlas (M7) is what tests.

Reported side by side. If they disagree, the disagreement is the finding,
and the smooth mode is the one to distrust.

    python marketing_experimentation/scripts/continuous_ladder.py \
        --results /tmp/results_atlas.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import (  # noqa: E402
    DEFAULT_ACTIONS, DEFAULT_MULTIPLIERS, DecisionProblem, budget_problem,
    spike_slab_prior, two_point_problem,
)

RUNGS: dict[str, list[str]] = {
    "S0_significance_bit": [],
    "S1_point_estimate": ["att_pct"],
    "S2_estimate_plus_ci": ["att_pct", "ci_width"],
}


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(l) for l in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    d["ci_width"] = pd.to_numeric(d.ci_upper, errors="coerce") - \
        pd.to_numeric(d.ci_lower, errors="coerce")
    d["att_pct"] = pd.to_numeric(d.att_pct, errors="coerce")
    return d


def guard_unique(d: pd.DataFrame) -> None:
    """D13 turns an appended results file into silently duplicated rows, and
    a duplicated row is a doubled likelihood weight. Refuse rather than
    quietly reweight."""
    keys = ["tool_label", "scenario", "effect_pct", "iteration"]
    dup = d.duplicated(subset=keys)
    if dup.any():
        raise SystemExit(
            f"{int(dup.sum())} duplicated run identities. A duplicate is a "
            f"doubled likelihood weight.\nRegenerate with `make clean` -- "
            f"see D13 in docs/donor-repro.md.")


def split_by_theta(g: pd.DataFrame, cols: list[str], seed: int,
                   frac_fit: float = 0.5):
    """Fit/evaluate split within each simulated theta, so no density scores
    its own points."""
    rng = np.random.default_rng(seed)
    fit, ev = {}, {}
    for th, sub in g.groupby("effect_pct"):
        X = sub[cols].to_numpy(dtype=float)
        X = X[np.isfinite(X).all(axis=1)]
        if len(X) < 8:
            continue
        idx = rng.permutation(len(X))
        cut = max(int(frac_fit * len(X)), 4)
        fit[float(th)], ev[float(th)] = X[idx[:cut]], X[idx[cut:]]
    return fit, ev


def discrete_problem(prior_grid: np.ndarray, prior_p: np.ndarray,
                     thetas: list[float]) -> DecisionProblem:
    """The budget problem restricted to the simulated truths, with the prior
    re-normalised onto them. Coarse, and assumption-free about what happens
    between them."""
    th = np.array(sorted(thetas))
    p = np.interp(th, prior_grid, prior_p)
    p = p / p.sum()
    return budget_problem(th, p)


def evsi_discrete(problem: DecisionProblem, fit: dict, ev: dict,
                  bw="scott") -> float:
    """EVSI with one KDE per simulated theta."""
    order = list(problem.theta)
    kdes = {}
    for th in order:
        X = fit.get(float(th))
        if X is None:
            return np.nan
        kdes[float(th)] = (gaussian_kde(X[:, 0], bw_method=bw) if X.shape[1] == 1
                           else gaussian_kde(X.T, bw_method=bw))
    total = 0.0
    for j, th in enumerate(order):
        X = ev.get(float(th))
        if X is None or not len(X):
            return np.nan
        pts = X[:, 0] if X.shape[1] == 1 else X.T
        like = np.vstack([np.clip(kdes[float(t)](pts), 1e-300, None)
                          for t in order]).T
        post = problem.prior * like
        post /= np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
        total += problem.prior[j] * float(
            (post @ problem.utility.T).max(axis=1).mean())
    return total - problem.value_no_experiment()


def fit_smooth(g: pd.DataFrame) -> tuple[float, float, float]:
    """y ~ Normal(a + b*theta, s). Returns (a, b, s) on the att_pct scale.

    `b` is the scale factor the atlas calls a scale error: b == 1 means the
    estimator tracks the truth, b < 1 that it attenuates.
    """
    ok = g[g.att_pct.notna()]
    x = ok.effect_pct.to_numpy(dtype=float)
    y = ok.att_pct.to_numpy(dtype=float)
    b, a = np.polyfit(x, y, 1)
    s = float(np.std(y - (a + b * x), ddof=2))
    return float(a), float(b), s


def evsi_smooth(problem: DecisionProblem, g: pd.DataFrame,
                seed: int) -> float:
    """EVSI on the full grid, assuming the estimator behaves between the
    simulated truths as the fitted line says it does."""
    rng = np.random.default_rng(seed)
    ok = g[g.att_pct.notna()]
    idx = rng.permutation(len(ok))
    cut = len(ok) // 2
    a, b, s = fit_smooth(ok.iloc[idx[:cut]])
    ev = ok.iloc[idx[cut:]]
    if s <= 0 or not np.isfinite(s):
        return np.nan

    th = problem.theta
    total = 0.0
    for j, t in enumerate(th):
        # Draws that WOULD be seen if the truth were t, under the fitted model.
        y = rng.normal(a + b * t, s, size=400)
        like = norm.pdf(y[:, None], loc=a + b * th[None, :], scale=s)
        post = problem.prior * like
        post /= np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
        total += problem.prior[j] * float(
            (post @ problem.utility.T).max(axis=1).mean())
    return total - problem.value_no_experiment()


def evsi_binary(problem: DecisionProblem, g: pd.DataFrame) -> float:
    """The significance bit, used optimally, against the same decision."""
    order = list(problem.theta)
    p_sig = []
    for t in order:
        sub = g[np.isclose(g.effect_pct.astype(float), t, atol=1e-9)]
        if sub.empty:
            return np.nan
        p_sig.append(float(sub.significant.astype(bool).mean()))
    p_sig = np.array(p_sig)
    like = np.vstack([1.0 - p_sig, p_sig])          # (2, n_theta)
    marg = like @ problem.prior
    total = 0.0
    for y in range(2):
        post = problem.prior * like[y]
        ssum = post.sum()
        post = post / ssum if ssum > 0 else problem.prior
        total += marg[y] * float((problem.utility @ post).max())
    return total - problem.value_no_experiment()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--scenario", default="A1")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--mode", choices=("discrete", "smooth", "both"),
                    default="both")
    args = ap.parse_args()

    d = load(args.results)
    guard_unique(d)
    d = d[d.scenario == args.scenario]
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    tools = sorted(d.tool_label.unique())

    print(f"scenario {args.scenario} | {len(d):,} rows | "
          f"{len(thetas)} simulated truths")
    print(f"theta: {[round(100*t, 1) for t in thetas]} (%)\n")
    if len(thetas) < 3:
        print("!! This script exists to escape the two-point world. With "
              f"{len(thetas)} truths\n   it cannot. Run the atlas first "
              "(M7).\n")

    grid = np.linspace(-0.15, 0.25, 81)
    pri = spike_slab_prior(grid)
    problem = discrete_problem(grid, pri, thetas)

    print("== the decision, now that it has more than two answers ==")
    print(f"   actions: {', '.join(DEFAULT_ACTIONS)}")
    print(f"   spend multipliers: {DEFAULT_MULTIPLIERS}")
    print(f"   prior-optimal action with no experiment: "
          f"{problem.best_action_no_experiment()!r}")
    print(f"   prior mass on theta < 0: "
          f"{problem.prior[problem.theta < 0].sum():.3f}")
    print(f"   EVPI ${problem.evpi():,.0f}")

    tp = two_point_problem(0.4, 500_000.0, 500_000.0)
    print(f"   (the two-point problem's EVPI was ${tp.evpi():,.0f} -- a "
          f"different\n    parameterisation, so the LEVELS are not "
          f"comparable. The ratios below are.)\n")

    rows = []
    for tool in tools:
        g = d[d.tool_label == tool]
        rec = {"tool": tool, "S0": evsi_binary(problem, g)}
        for rung, cols in RUNGS.items():
            if not cols:
                continue
            vals = []
            for s in range(args.seeds):
                fit, ev = split_by_theta(g, cols, s)
                if len(fit) == len(thetas):
                    vals.append(evsi_discrete(problem, fit, ev))
            rec[rung[:2]] = float(np.nanmean(vals)) if vals else np.nan
            rec[f"sd_{rung[:2]}"] = (float(np.nanstd(vals))
                                     if len(vals) > 1 else np.nan)
        if args.mode in ("smooth", "both"):
            sm = [evsi_smooth(problem, g, s) for s in range(args.seeds)]
            rec["S1_smooth"] = float(np.nanmean(sm))
            a, b, sd = fit_smooth(g)
            rec["slope_b"] = b
            rec["resid_sd"] = sd
        rows.append(rec)

    r = pd.DataFrame(rows).set_index("tool")

    print("== EVSI by rung, five actions, prior over effect size ==")
    cols = [c for c in ("S0", "S1", "S2", "S1_smooth") if c in r.columns]
    disp = r[cols].copy()
    for c in cols:
        disp[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in r[c]]
    print(disp.to_string())

    print("\n== the compression tax, now that the decision is richer ==")
    tax = pd.DataFrame(index=r.index)
    tax["S1-S0"] = r["S1"] - r["S0"]
    tax["S2-S1"] = r["S2"] - r["S1"]
    tax["S0 keeps %"] = 100 * r["S0"] / r["S1"]
    out = tax.copy()
    for c in ("S1-S0", "S2-S1"):
        out[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in tax[c]]
    out["S0 keeps %"] = tax["S0 keeps %"].round(1)
    print(out.to_string())

    print("\n== the two questions this script exists to answer ==")
    s21 = r["S2"] - r["S1"]
    sd = r.get("sd_S2", pd.Series(np.nan, index=r.index))
    print("\n1. Does the interval earn its keep once theta is continuous?")
    print("   (in the two-point world S2-S1 was -$1,475 to +$96, sign "
          "flipping)")
    for t in r.index:
        v, e = s21.get(t, np.nan), sd.get(t, np.nan)
        verdict = ("detectable" if np.isfinite(v) and np.isfinite(e)
                   and abs(v) > 2 * e else "still undetectable")
        print(f"     {t:18s} S2-S1 ${v:+9,.0f} (±{e:,.0f})  {verdict}")

    print("\n2. Does a richer action set widen the S0 gap?")
    print("   (two points / two actions kept 7.8%-79.9%)")
    for t in r.index:
        k = 100 * r.loc[t, "S0"] / r.loc[t, "S1"]
        print(f"     {t:18s} S0 keeps {k:5.1f}%")

    if "slope_b" in r.columns:
        print("\n== smooth-model diagnostics ==")
        print("   b is the scale factor: 1.0 means the estimator tracks the "
              "truth.\n")
        print(r[["slope_b", "resid_sd"]].round(4).to_string())

    Path("continuous_ladder_results.json").write_text(
        r.reset_index().to_json(orient="records", indent=2))
    print("\nwrote continuous_ladder_results.json")


if __name__ == "__main__":
    main()
