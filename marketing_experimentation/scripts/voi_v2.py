#!/usr/bin/env python
"""Layer 3 v2: value the experiment, then subtract its price.

v1 (`business_phase_diagram.py`) measured a *significance gate* and reported
that a free experiment was not worth running over 70% of the plane. That
violates `EVSI >= 0` and the violation was the point: the gate is forced to
obey its own verdict, so it can lose to acting on the prior. v1 is kept,
relabelled, because the gate is what practice actually runs.

This computes three quantities on the identical Recast data:

  EVPI   ceiling: what being told the truth would be worth
  EVSI   what the experiment is worth when its result is used optimally
  ENBS   EVSI - experiment cost, i.e. the honest RUN / DO-NOT-RUN rule

and separately the **gate information loss**: how much of a worthwhile
experiment conventional practice discards at the final step.

Two signal representations, because the difference between them is a result:

  binary      only the significant/not flag -- one bit
  continuous  the point estimate, via p(att_pct | theta) fitted per method

    python marketing_experimentation/scripts/voi_v2.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import (  # noqa: E402
    check_invariants,
    evsi,
    gate_information_loss,
    two_point_problem,
    value_of_significance_gate,
)

ABBREV = {"causalimpact": "CI", "causalpy": "CP", "geolift": "GL",
          "google_mm": "MM"}


def load_runs(path: Path) -> pd.DataFrame:
    return pd.DataFrame([json.loads(l) for l in path.open()])


def binary_signal(d: pd.DataFrame, tool: str, scenario: str):
    """p(y | theta) for the one-bit significance flag."""
    g = d[(d.tool == tool) & (d.scenario == scenario)]
    fpr = float(g[g.effect_label == "null"].significant.mean())
    tpr = float(g[g.effect_label != "null"].significant.mean())
    p_sig = np.array([fpr, tpr])
    return np.vstack([1.0 - p_sig, p_sig]), p_sig


def continuous_signal(d: pd.DataFrame, tool: str, scenario: str, seed: int = 0):
    """p(y | theta) for the point estimate, by KDE, with a train/eval split.

    The split matters: fitting the density and evaluating the expectation on
    the same runs flatters the experiment, because the density has already
    seen the points it is scoring. Half the runs fit, half evaluate.
    """
    from scipy.stats import gaussian_kde

    rng = np.random.default_rng(seed)
    g = d[(d.tool == tool) & (d.scenario == scenario)]
    fit, ev = {}, {}
    for j, label in enumerate(("null", "effect")):
        vals = g[g.effect_label == label].att_pct.to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        idx = rng.permutation(len(vals))
        half = len(vals) // 2
        fit[j] = vals[idx[:half]]
        ev[j] = vals[idx[half:]]
    kdes = {j: gaussian_kde(fit[j]) for j in fit}

    # Evaluation points: the held-out draws, pooled, with their source theta.
    ys = np.concatenate([ev[0], ev[1]])
    source = np.concatenate([np.zeros(len(ev[0]), int), np.ones(len(ev[1]), int)])
    like = np.vstack([kdes[0](ys), kdes[1](ys)]).T   # (n_y, n_theta)
    like = np.clip(like, 1e-300, None)
    return like, source, {0: len(ev[0]), 1: len(ev[1])}


def evsi_continuous(problem, like, source, counts) -> float:
    """Monte Carlo EVSI: average max-posterior-value over draws from p(y)."""
    total = 0.0
    for j in (0, 1):
        sel = source == j
        if not sel.any():
            continue
        post = problem.prior * like[sel]
        post = post / np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
        vals = (post @ problem.utility.T).max(axis=1)
        total += problem.prior[j] * float(vals.mean())
    return total - problem.value_no_experiment()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results",
        default="/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl")
    ap.add_argument("--scenario", default="A1")
    ap.add_argument("--c-fn", type=float, default=500_000.0)
    ap.add_argument("--c-test", type=float, default=40_000.0)
    args = ap.parse_args()

    d = load_runs(Path(args.results))
    tools = sorted(d.tool.unique())
    ratios = np.round(np.logspace(np.log10(0.1), np.log10(10.0), 25), 4)
    priors = np.round(np.linspace(0.05, 0.90, 18), 4)

    print(f"scenario {args.scenario} | C_FN=${args.c_fn:,.0f} | "
          f"C_test=${args.c_test:,.0f}\n")

    binaries = {t: binary_signal(d, t, args.scenario) for t in tools}

    # -- invariant check on every cell, before reporting anything -----------
    violations = 0
    for t in tools:
        like, _ = binaries[t]
        for pi in priors:
            for r in ratios:
                p = two_point_problem(pi, r * args.c_fn, args.c_fn)
                if not check_invariants(p, like, like @ p.prior)["ok"]:
                    violations += 1
    print(f"invariant check (0 <= EVSI <= EVPI) over "
          f"{len(tools) * len(priors) * len(ratios):,} cells: "
          f"{'PASS' if violations == 0 else f'{violations} VIOLATIONS'}\n")
    if violations:
        raise SystemExit("refusing to report numbers that violate the invariants")

    # -- who wins, using the signal optimally -------------------------------
    rows = []
    for pi in priors:
        for r in ratios:
            p = two_point_problem(pi, r * args.c_fn, args.c_fn)
            vals = {}
            for t in tools:
                like, p_sig = binaries[t]
                v = evsi(p, like, like @ p.prior)
                vals[t] = dict(
                    evsi=v,
                    enbs=v - args.c_test,
                    gate_loss=gate_information_loss(
                        p, like, like @ p.prior, p_sig, "scale", "hold"),
                    gate_value=value_of_significance_gate(
                        p, p_sig, "scale", "hold"),
                )
            best = max(vals, key=lambda t: vals[t]["enbs"])
            rows.append(dict(
                prior=pi, ratio=r, evpi=p.evpi(),
                best_tool=best,
                best_evsi=vals[best]["evsi"],
                best_enbs=vals[best]["enbs"],
                run=vals[best]["enbs"] > 0,
                gate_loss=vals[best]["gate_loss"],
                gate_beats_prior=vals[best]["gate_value"] >= p.value_no_experiment(),
                **{f"evsi_{t}": vals[t]["evsi"] for t in tools},
            ))
    g = pd.DataFrame(rows)

    print("== RUN / DO-NOT-RUN, decided by ENBS = EVSI - cost ==")
    print(f"  experiment worth running in {100 * g.run.mean():.0f}% of the plane")
    print(f"  (v1's significance-gate model said 12%)")
    print(f"  median EVSI where positive: ${g[g.best_evsi > 0].best_evsi.median():,.0f}")
    print(f"  median EVPI (the ceiling):  ${g.evpi.median():,.0f}")

    print("\n== does a free experiment ever hurt? ==")
    # Monte Carlo and floating point leave tiny negatives; anything within a
    # rounding error of zero is zero. A real violation would be material.
    tol = 1e-6 * max(g.evpi.max(), 1.0)
    material = (g.best_evsi < -tol).sum()
    print(f"  cells with materially negative EVSI: {material} of {len(g):,}")
    print(f"  most negative value seen: ${g.best_evsi.min():,.2f} "
          f"(tolerance ${tol:,.2f})")
    print(f"  v1's significance-gate model reported negative value over 70% "
          f"of this plane")

    print("\n== which tool is preferred, where ENBS > 0 ==")
    won = g[g.run]
    if len(won):
        print((100 * won.best_tool.value_counts(normalize=True)).round(1).to_string())
    print("\nphase map of the preferred tool (blank = DO NOT RUN):")
    piv = g.assign(cell=np.where(g.run, g.best_tool.map(ABBREV), "--")) \
           .pivot(index="prior", columns="ratio", values="cell")
    cols = [c for i, c in enumerate(piv.columns) if i % 3 == 0]
    compact = piv[cols]
    compact.columns = [f"{c:g}" for c in compact.columns]
    print(compact.to_string())

    print("\n== how much the significance gate throws away ==")
    print(f"  mean gate loss where the experiment is worth running: "
          f"${won.gate_loss.mean():,.0f}" if len(won) else "  n/a")
    print(f"  cells where the gate is worse than acting on the prior: "
          f"{100 * (~g.gate_beats_prior).mean():.0f}%")
    # Only meaningful where the experiment has material value to discard.
    worth = g[g.best_evsi > tol]
    if len(worth):
        share = 100 * worth.gate_loss / worth.best_evsi
        print(f"  median share of a valuable experiment discarded by the "
              f"gate: {share.median():.0f}%  (over {len(worth)} cells with "
              f"EVSI > ${tol:,.0f})")

    print("\n== EVSI by tool, averaged over the plane (binary signal) ==")
    means = {t: g[f"evsi_{t}"].mean() for t in tools}
    for t, v in sorted(means.items(), key=lambda kv: -kv[1]):
        print(f"  {t:14s} ${v:>10,.0f}")

    # -- does the continuous signal recover more? ---------------------------
    print("\n== binary flag vs the point estimate, at prior=0.4, ratio=1 ==")
    p = two_point_problem(0.4, 1.0 * args.c_fn, args.c_fn)
    print(f"  EVPI ceiling: ${p.evpi():,.0f}")
    print(f"  {'tool':14s} {'EVSI binary':>13s} {'EVSI continuous':>17s} {'uplift':>9s}")
    for t in tools:
        like, _ = binaries[t]
        v_bin = evsi(p, like, like @ p.prior)
        cl, src, cnt = continuous_signal(d, t, args.scenario)
        v_con = evsi_continuous(p, cl, src, cnt)
        print(f"  {t:14s} ${v_bin:>12,.0f} ${v_con:>16,.0f} "
              f"{100 * (v_con / v_bin - 1) if v_bin else float('nan'):>8.0f}%")


if __name__ == "__main__":
    main()
