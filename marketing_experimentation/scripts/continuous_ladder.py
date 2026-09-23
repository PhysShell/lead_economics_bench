#!/usr/bin/env python
"""The information ladder, with a real prior over effect size and five actions.

Everything published in this track so far lives in a two-point,
two-action world: theta in {0, +7.5%}, act or don't. Two limitations were
recorded there and both are load-bearing:

  * with two truths the point estimate nearly identifies the state on its
    own, which may be why the interval looked as though it added little --
    see Addendum 0 of layer3-first-result.md, where that claim was already
    narrowed once for a different reason;
  * with two actions an experiment only has to say which side of a threshold
    theta falls on, so the significance bit is close to a sufficient summary
    of the decision and the measured thresholding cost is a LOWER bound.

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
                      across arms and evaluated on the full 81-point grid.
                      s(theta) is genuinely a function -- residual SD per
                      simulated truth, interpolated -- and the constant-sigma
                      variant runs alongside so the cost of that assumption
                      is visible. Assumes the estimator is well behaved
                      between the simulated points, which is what the atlas
                      (M7, Q3a) tests.

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

#: Same representation graph as `information_ladder.py`, and for the same
#: reason: `significant` is "the interval excludes zero", so BIT is a
#: deterministic garbling of INTERVAL (Blackwell applies) while POINT is a
#: side branch comparable to neither. INTERVAL carries both bounds, not the
#: width -- the intervals are asymmetric, so (att, width) recovers
#: significance only 94-97% of the time and would break the nesting.
RUNGS: dict[str, list[str]] = {
    "BIT": [],
    "POINT": ["att_pct"],
    "INTERVAL": ["att_pct", "ci_lower", "ci_upper"],
}


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(l) for l in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    for c in ("att_pct", "ci_lower", "ci_upper"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["ci_width"] = d.ci_upper - d.ci_lower  # reporting only
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
    """The budget problem restricted to the simulated truths.

    The prior is carried across by **integrating probability mass over
    Voronoi bins**, not by sampling the density at the seven points.

    An earlier version did `np.interp(th, grid, p); p /= p.sum()`, which
    takes the *density value* at each theta and renormalises. For a
    spike-and-slab that is badly wrong: the spike is a narrow bump of width
    0.005, so its density value is enormous while the mass it actually
    represents is `p_null`. Sampling the density there and normalising can
    hand the null point far more or far less weight than the prior says,
    and the documented properties -- 45% null mass, 27% below zero -- would
    not survive the transfer.

    Binning by midpoints assigns every region of the continuous prior to its
    nearest simulated truth, so the mass is conserved by construction.
    """
    th = np.array(sorted(thetas), dtype=float)
    edges = np.concatenate(([-np.inf], (th[:-1] + th[1:]) / 2.0, [np.inf]))
    idx = np.digitize(prior_grid, edges) - 1
    p = np.array([prior_p[idx == j].sum() for j in range(len(th))])
    if p.sum() <= 0:
        raise SystemExit("no prior mass landed on the simulated truths")
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


def fit_smooth(g: pd.DataFrame, hetero: bool = True):
    """y ~ Normal(a + b*theta, s(theta)) on the att_pct scale.

    `b` is the scale factor the atlas calls a scale error: b == 1 means the
    estimator tracks the truth, b < 1 that it attenuates.

    `s` is a FUNCTION of theta, not a constant. An earlier version of this
    file documented `s(theta)` and then computed `np.std(all residuals)` --
    which is amusing next to `theta_atlas.py` Q3a, whose whole job is to ask
    whether the variance moves. The residual SD is now fitted per simulated
    truth and interpolated, and the constant-sigma model is available via
    `hetero=False` so the two can be compared rather than assumed.

    Returns (a, b, sigma_fn) where sigma_fn(theta) -> scale.
    """
    ok = g[g.att_pct.notna()]
    x = ok.effect_pct.to_numpy(dtype=float)
    y = ok.att_pct.to_numpy(dtype=float)
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)

    if not hetero:
        s = float(np.std(resid, ddof=2))
        return float(a), float(b), (lambda t: np.full_like(np.asarray(t, float), s))

    # Residual SD per simulated truth, then linear interpolation between
    # them and flat extrapolation outside -- enough to carry a moving
    # variance without inventing a functional form the data cannot support.
    tab = (pd.DataFrame({"t": x, "r": resid})
           .groupby("t").r.std(ddof=1).dropna())
    if len(tab) < 2:
        s = float(np.std(resid, ddof=2))
        return float(a), float(b), (lambda t: np.full_like(np.asarray(t, float), s))
    ts, ss = tab.index.to_numpy(float), tab.to_numpy(float)

    def sigma_fn(t):
        return np.interp(np.asarray(t, dtype=float), ts, ss,
                         left=ss[0], right=ss[-1])

    return float(a), float(b), sigma_fn


def evsi_smooth(problem: DecisionProblem, g: pd.DataFrame, seed: int,
                hetero: bool = True) -> float:
    """EVSI over the decision problem's own theta grid, assuming the
    estimator behaves between the simulated truths as the fitted model says.

    The problem passed in decides the grid. Pass the discrete problem for a
    seven-point evaluation; pass a `budget_problem` on the full 81-point grid
    for a genuinely continuous one. An earlier docstring claimed this "uses
    the whole grid" while the caller only ever handed it the seven points.
    """
    rng = np.random.default_rng(seed)
    ok = g[g.att_pct.notna()]
    idx = rng.permutation(len(ok))
    cut = len(ok) // 2
    a, b, sigma_fn = fit_smooth(ok.iloc[idx[:cut]], hetero=hetero)

    th = problem.theta
    s_th = np.asarray(sigma_fn(th), dtype=float)
    if not np.all(np.isfinite(s_th)) or np.any(s_th <= 0):
        return np.nan

    total = 0.0
    for j, t in enumerate(th):
        # Draws that WOULD be seen if the truth were t, under the fitted model.
        y = rng.normal(a + b * t, s_th[j], size=400)
        like = norm.pdf(y[:, None], loc=a + b * th[None, :],
                        scale=s_th[None, :])
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
    # The genuinely continuous problem: 81 points, the prior untouched.
    # `smooth` mode is evaluated on this, which is what its docstring
    # always claimed and what the code did not do.
    problem_full = budget_problem(grid, pri)

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
        rec = {"tool": tool, "BIT": evsi_binary(problem, g)}
        for rung, cols in RUNGS.items():
            if not cols:
                continue
            vals = []
            for s in range(args.seeds):
                fit, ev = split_by_theta(g, cols, s)
                if len(fit) == len(thetas):
                    vals.append(evsi_discrete(problem, fit, ev))
            rec[rung] = float(np.nanmean(vals)) if vals else np.nan
            rec[f"sd_{rung}"] = (float(np.nanstd(vals))
                                 if len(vals) > 1 else np.nan)
        if args.mode in ("smooth", "both"):
            sm = [evsi_smooth(problem_full, g, s, hetero=True)
                  for s in range(args.seeds)]
            rec["POINT_smooth"] = float(np.nanmean(sm))
            # Same model with a constant sigma, so the cost of that
            # assumption is visible instead of assumed away.
            sc = [evsi_smooth(problem_full, g, s, hetero=False)
                  for s in range(args.seeds)]
            rec["POINT_smooth_const_sigma"] = float(np.nanmean(sc))
            a, b, sigma_fn = fit_smooth(g)
            rec["slope_b"] = b
            sig = np.asarray(sigma_fn(np.array(thetas)), dtype=float)
            rec["sigma_min"] = float(sig.min())
            rec["sigma_max"] = float(sig.max())
        rows.append(rec)

    r = pd.DataFrame(rows).set_index("tool")

    print("== EVSI by rung, five actions, prior over effect size ==")
    print(f"   BIT/POINT/INTERVAL on the {len(thetas)} simulated truths "
          f"(EVPI ${problem.evpi():,.0f});")
    print(f"   POINT_smooth on the full {len(grid)}-point grid "
          f"(EVPI ${problem_full.evpi():,.0f}).")
    print("   DIFFERENT CEILINGS -- compare within a column, not across.\n")
    cols = [c for c in ("BIT", "POINT", "INTERVAL", "POINT_smooth",
                        "POINT_smooth_const_sigma") if c in r.columns]
    disp = r[cols].copy()
    for c in cols:
        disp[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in r[c]]
    print(disp.to_string())

    print("\n== the compression tax, now that the decision is richer ==")
    tax = pd.DataFrame(index=r.index)
    tax["POINT-BIT"] = r["POINT"] - r["BIT"]
    tax["INTERVAL-POINT"] = r["INTERVAL"] - r["POINT"]
    # BIT / INTERVAL, not BIT / POINT. The bit is a garbling of the interval,
    # so that ratio is a compression measurement. BIT / POINT compares two
    # signals Blackwell does not order and is not a "share kept" of anything.
    # A leftover from the mechanical S0/S1/S2 rename; caught because the two
    # places that printed it disagreed (21.7% here against 11.2% below) and
    # the runs are deterministic, so one of them had to be wrong.
    tax["BIT keeps %"] = 100 * r["BIT"] / r["INTERVAL"]
    out = tax.copy()
    for c in ("POINT-BIT", "INTERVAL-POINT"):
        out[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in tax[c]]
    out["BIT keeps %"] = tax["BIT keeps %"].round(1)
    print(out.to_string())

    print("\n== the two questions this script exists to answer ==")
    s21 = r["INTERVAL"] - r["POINT"]
    sd = r.get("sd_INTERVAL", pd.Series(np.nan, index=r.index))
    print("\n1. Does the interval earn its keep once theta is continuous?")
    print("   Blackwell guarantees INTERVAL >= BIT. It does NOT order")
    print("   INTERVAL against POINT, so this gap can legitimately go either")
    print("   way and is an empirical property of this decision problem.")
    for t in r.index:
        v, e = s21.get(t, np.nan), sd.get(t, np.nan)
        verdict = ("detectable" if np.isfinite(v) and np.isfinite(e)
                   and abs(v) > 2 * e else "still undetectable")
        print(f"     {t:18s} INTERVAL-POINT ${v:+9,.0f} (±{e:,.0f})  {verdict}")

    print("\n2. Does a richer action set widen the thresholding gap?")
    print("   BIT as a share of INTERVAL -- the guaranteed chain, so this is")
    print("   a compression measurement. Two points / two actions kept")
    print("   7.2%-34.1% of INTERVAL.")
    for t in r.index:
        k = 100 * r.loc[t, "BIT"] / r.loc[t, "INTERVAL"]
        print(f"     {t:18s} BIT keeps {k:5.1f}% of INTERVAL")

    if "slope_b" in r.columns:
        print("\n== smooth-model diagnostics ==")
        print("   b is the scale factor: 1.0 means the estimator tracks the")
        print("   truth, b < 1 that it attenuates. sigma_min/max show whether")
        print("   the variance moves -- if it does, the constant-sigma column")
        print("   above is the wrong model and the difference is its cost.\n")
        print(r[["slope_b", "sigma_min", "sigma_max"]].round(5).to_string())
        if "POINT_smooth_const_sigma" in r.columns:
            d_ = r["POINT_smooth"] - r["POINT_smooth_const_sigma"]
            print("\n   cost of assuming constant sigma:")
            for tool in r.index:
                print(f"     {tool:18s} ${d_.get(tool, float('nan')):+,.0f}")

    Path("continuous_ladder_results.json").write_text(
        r.reset_index().to_json(orient="records", indent=2))
    print("\nwrote continuous_ladder_results.json")


if __name__ == "__main__":
    main()
