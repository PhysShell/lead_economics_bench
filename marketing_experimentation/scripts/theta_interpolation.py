#!/usr/bin/env python
"""Can the verdict channel be interpolated between simulated truths?

Why this has to be answered before M8, not after
-------------------------------------------------
Every Finding A number so far is computed on a prior that was *mutilated to
fit the grid*: the continuous spike-and-slab is Voronoi-binned onto seven
points, which moves its negative mass from 0.267 to 0.071. Every statement
then carries an apology.

The architectural fix is to stop moving the prior and start moving the
likelihood -- estimate the verdict channel `q(theta) = p(verdict | theta)` as
a function, evaluate it on the prior's own grid, and compute EVSI there::

    documented continuous prior  +  estimated q(theta)  +  utility  ->  EVSI

instead of

    documented prior -> mutilated seven-point prior -> sensitivity apology

But that is only legitimate if `q` is actually interpolable. If the verdict
channel does something between the simulated truths that the neighbours do
not predict, a continuous EVSI built on it is a fabrication with a smooth
curve through it. **So the interpolation is falsified first, on the data
already in hand, and it decides where M8 should spend simulator time.**

The test
--------
Leave one interior truth out. Rebuild `q` at that truth from its neighbours.
Compare to what was actually simulated there. Endpoints are excluded --
predicting them is extrapolation, a different and weaker claim.

Interpolation is in multinomial-logit space against the `inconclusive`
baseline, so predictions stay in the simplex by construction rather than by
renormalising something that left it.

Two metrics, because they answer different questions
-----------------------------------------------------
    TV        total variation distance between predicted and observed q.
              The statistical question: is the channel smooth?
    |dEVSI|   swap the interpolated row into the channel, recompute the sign
              loss, take the difference. The DECISION question: does the
              interpolation error change the answer we care about?

A channel can fail the first and pass the second. EVSI is what this project
reports, so the second is the one with authority -- but a large TV with a
small |dEVSI| is a warning that the decision happens to be insensitive here
and may not be at a different prior.

Both are read against the right yardstick: **the cluster bootstrap spread of
q itself.** If interpolating is no worse than resampling the runs, the
interpolation costs nothing that more simulation would fix. That comparison,
not an absolute threshold, is what makes the verdict non-arbitrary.

    python marketing_experimentation/scripts/theta_interpolation.py \
        --results /tmp/results_atlas.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.clusters import require_complete_clusters  # noqa: E402
from leadbench_mx.decision import (  # noqa: E402
    action_boundaries, budget_problem, spike_slab_prior,
)
from signed_verdict import (  # noqa: E402
    ALPHA, GARBLE, cluster_bootstrap_draws, evsi_batch, load, verdict_index,
    verdict_matrix,
)


def logit_interp(theta: np.ndarray, q: np.ndarray, at: float) -> np.ndarray:
    """Predict q at `at` from the rows of `q` at `theta`, in logit space.

    The baseline is `inconclusive` (index 1). Linear interpolation of
    log(q_k / q_1) keeps every prediction inside the simplex, which linear
    interpolation of the probabilities themselves does not guarantee once
    renormalisation is involved.
    """
    eta = np.log(q[:, [0, 2]] / q[:, [1]])
    pred = np.array([np.interp(at, theta, eta[:, i]) for i in range(2)])
    e = np.exp(np.concatenate([[pred[0]], [0.0], [pred[1]]]))
    return e / e.sum()


def tv(a: np.ndarray, b: np.ndarray) -> float:
    return 0.5 * float(np.abs(a - b).sum())


def counts_to_q(V: np.ndarray, alpha: float) -> np.ndarray:
    """(n_clusters, n_theta) verdict codes -> (n_theta, 3) probabilities."""
    n = len(V)
    c = np.stack([np.bincount(V[:, j], minlength=3) for j in range(V.shape[1])])
    return (c + alpha) / (n + 3 * alpha)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--expect-iterations", default=None,
                    help="preregister the complete-cluster set, e.g. '1-10'")
    args = ap.parse_args()

    d = load(args.results)
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    d = d.assign(_verdict=verdict_index(d))
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    # The gate matters MORE here than anywhere. If q(theta) rows rest on
    # different latent panels, the interpolation error this script measures
    # is mixed with a difference in Monte Carlo samples, and the boundary
    # falsification silently tests the wrong thing. See F16.
    exp = None
    if args.expect_iterations:
        lo, _, hi = args.expect_iterations.partition("-")
        exp = range(int(lo), int(hi or lo) + 1)
    before = len(d)
    d = require_complete_clusters(d, thetas, expect_iterations=exp)
    print(f"CRN gate: {len(d):,}/{before:,} rows in complete shared clusters")
    tools = sorted(d.tool_label.unique())
    th = np.array(thetas)

    grid = np.linspace(-0.15, 0.25, 81)
    pri = spike_slab_prior(grid)
    edges = np.concatenate(([-np.inf], (th[:-1] + th[1:]) / 2, [np.inf]))
    idx = np.digitize(grid, edges) - 1
    p7 = np.array([pri[idx == j].sum() for j in range(len(th))])
    problem = budget_problem(th, p7 / p7.sum())

    print(f"leave-one-theta-out on {len(thetas)} simulated truths, "
          f"alpha={args.alpha}")
    print(f"truths: {[round(100*t, 1) for t in thetas]} (%)")
    print(f"interior only ({len(thetas)-2} of them) -- the endpoints would be "
          f"extrapolation\n")
    print("decision boundaries of the budget problem, for reference:")
    print(f"   {['%+.4f%%' % (100*b) for b in action_boundaries()]}")
    print("   (the economic breakeven +3.00% is NOT one of them)\n")

    print(f"   {'tool':18s} {'held out':>9s} {'TV':>7s} {'TV pctile':>10s}"
          f" | {'V-B obs':>9s} {'V-B interp':>11s} {'|dEVSI|':>9s} "
          f"{'pctile':>7s}")
    rows = []
    for tool in tools:
        g = d[d.tool_label == tool]
        V, _ = verdict_matrix(g, thetas)
        q_obs = counts_to_q(V, args.alpha)
        rng = np.random.default_rng(0)
        boot = cluster_bootstrap_draws(V, args.alpha, args.draws, rng)
        gap_obs = float(evsi_batch(problem, q_obs[None])[0]
                        - evsi_batch(problem, (q_obs @ GARBLE.T)[None])[0])

        for j in range(1, len(thetas) - 1):
            keep = [k for k in range(len(thetas)) if k != j]
            q_hat = logit_interp(th[keep], q_obs[keep], th[j])

            # Yardstick 1: how far does resampling alone move this row?
            tv_boot = np.array([tv(boot[i, j], q_obs[j])
                                for i in range(len(boot))])
            tv_i = tv(q_hat, q_obs[j])
            pct = 100.0 * float((tv_boot < tv_i).mean())

            # Yardstick 2: the same, in the units this project reports.
            q_swap = q_obs.copy()
            q_swap[j] = q_hat
            gap_int = float(evsi_batch(problem, q_swap[None])[0]
                            - evsi_batch(problem, (q_swap @ GARBLE.T)[None])[0])
            gb = (evsi_batch(problem, boot)
                  - evsi_batch(problem, boot @ GARBLE.T))
            d_boot = np.abs(gb - gap_obs)
            d_i = abs(gap_int - gap_obs)
            pct_e = 100.0 * float((d_boot < d_i).mean())

            rows.append((tool, th[j], tv_i, pct, d_i, pct_e))
            print(f"   {tool:18s} {100*th[j]:+8.1f}% {tv_i:7.3f} "
                  f"{pct:9.1f}% | ${gap_obs:>8,.0f} ${gap_int:>10,.0f} "
                  f"${d_i:>8,.0f} {pct_e:6.1f}%")
        print()

    print("HOW TO READ THE PERCENTILES")
    print("   The percentile is the share of cluster-bootstrap resamples that")
    print("   move q (or the sign loss) LESS than the interpolation does. Low")
    print("   means interpolating is cheaper than the sampling noise already")
    print("   present -- nothing is lost by not simulating that truth. High")
    print("   means the interpolation error is real and a simulated point")
    print("   there is buying something a neighbour cannot supply.\n")

    worst = sorted(rows, key=lambda r: -r[5])[:5]
    print("   worst five cells by decision-relevant percentile:")
    for tool, t, tvv, p, de, pe in worst:
        print(f"     {tool:18s} {100*t:+6.1f}%  |dEVSI| ${de:,.0f} "
              f"at the {pe:.1f}th percentile of sampling noise")

    n_bad = sum(1 for r in rows if r[5] > 95.0)
    n_bad_tv = sum(1 for r in rows if r[3] > 95.0)
    print(f"\n   {n_bad_tv}/{len(rows)} cells above the 95th percentile on TV")
    print(f"   {n_bad}/{len(rows)} cells above the 95th percentile on |dEVSI|")
    if n_bad == 0:
        print("\n   VERDICT: on this grid, the decision-relevant interpolation")
        print("   error is inside sampling noise everywhere. A continuous-prior")
        print("   Finding A is defensible -- but note this is the seven-point")
        print("   grid testing ITSELF, with 5%-wide gaps. It says nothing about")
        print("   the boundaries at -3.1% and +1.25%, where no truth was ever")
        print("   simulated and where the optimal action actually changes.")
    else:
        print("\n   VERDICT: the interpolation is not free everywhere. The")
        print("   cells above are where M8 should place truths first -- they")
        print("   are the ones a neighbour demonstrably cannot predict.")


if __name__ == "__main__":
    main()
