#!/usr/bin/env python
"""Finding A on the documented prior, with the spike kept as an atom.

What changed, and why it is the whole point
--------------------------------------------
Every Finding A number so far was computed on a prior bent to fit the
simulator. The continuous spike-and-slab was Voronoi-binned onto seven
simulated truths, which moved its negative mass from 0.267 to 0.071, and
every statement then carried an apology. The dependency ran

    available simulated theta -> invent a distribution fitting those points
                              -> apologise in the limitations section

The M8 boundary gate removed the reason for that. `q(theta)` survived
leave-one-out across every action boundary at n=25, so the likelihood can be
evaluated wherever the prior lives instead of the prior being dragged to
wherever the likelihood was measured::

    documented substantive prior
        -> its own support
        -> validated q(theta) interpolation
        -> utility / decision rule
        -> EVSI

The spike is an atom, not a narrow bump
----------------------------------------
`spike_slab_prior` represents the point mass at theta = 0 as a normal of
width 0.005 evaluated on a grid. That is a discretisation convenience and it
leaks: the atom's weight then depends on the grid spacing near zero, which is
exactly the class of defect F17 was. Here the prior keeps its declared form::

    p(theta) = pi_0 * delta_0(theta) + (1 - pi_0) * p_slab(theta)

so that

    E[f] = pi_0 * f(0) + (1 - pi_0) * integral f(theta) p_slab(theta) dtheta

and `pi_0` is exactly 0.45 however fine the grid gets.

Where the value comes from, not just how much
-----------------------------------------------
EVSI is not a sum over theta, but the **gain over the baseline action** is::

    EVSI = sum_theta p(theta) [ sum_y p(y|theta) U(a*(y), theta) - U(a0, theta) ]

with `a0` the prior-optimal action and `a*(y)` the signal-optimal one. That
decomposition is exact and additive, so each region of the prior can be asked
what it contributed. A headline EVSI that turns out to come almost entirely
from a sliver of prior mass near a decision boundary is a different finding
from the same number spread evenly, and the single dollar figure cannot tell
them apart. Individual contributions may be **negative** -- a signal can
mislead at a particular truth -- and those are reported rather than clipped.

The support is the validated one
---------------------------------
The gate validated interpolation, not extrapolation. Simulated truths span
[-15%, +15%], so the prior is restricted to that interval and renormalised;
the excluded mass is reported rather than absorbed.

    python marketing_experimentation/scripts/continuous_finding_a.py \
        --results /tmp/results_m8_full_merged.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.clusters import require_complete_clusters  # noqa: E402
from leadbench_mx.decision import (  # noqa: E402
    DEFAULT_ACTIONS, action_boundaries, budget_problem,
)
from signed_verdict import (  # noqa: E402
    ALPHA, GARBLE, cluster_bootstrap_draws, load, verdict_index, verdict_matrix,
)
from theta_interpolation import logit_interp  # noqa: E402

#: The documented spike-and-slab, in its declared form rather than its
#: gridded approximation. These are the defaults of `spike_slab_prior`.
PI_NULL = 0.45
SLAB_MU = 0.04
SLAB_SIGMA = 0.06

#: The interval over which q(theta) was validated. Outside it the gate says
#: nothing, so neither does this.
SUPPORT = (-0.15, 0.15)


def build_prior(n_slab: int = 241) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (theta, prior, kind) with the spike as its own support point.

    `kind` is 0 for the atom, -1 for slab mass below zero, +1 for slab mass
    at or above zero. The atom and the slab point at theta = 0 are the same
    state of the world and behave identically in the decision; they are kept
    apart only so the decomposition can attribute to them separately.
    """
    lo, hi = SUPPORT
    grid = np.linspace(lo, hi, n_slab)
    # Insert the four action boundaries exactly, so no boundary falls between
    # grid points and gets smoothed over by the quadrature.
    grid = np.unique(np.concatenate([grid, action_boundaries()]))

    dens = norm.pdf(grid, SLAB_MU, SLAB_SIGMA)
    w = np.zeros_like(grid)                       # trapezoid weights
    w[1:-1] = (grid[2:] - grid[:-2]) / 2.0
    w[0] = (grid[1] - grid[0]) / 2.0
    w[-1] = (grid[-1] - grid[-2]) / 2.0
    slab = dens * w
    inside = slab.sum()
    slab = slab / inside

    theta = np.concatenate([[0.0], grid])
    prior = np.concatenate([[PI_NULL], (1.0 - PI_NULL) * slab])
    kind = np.concatenate([[0], np.where(grid < 0, -1, 1)])
    return theta, prior, kind


def excluded_slab_mass() -> tuple[float, float]:
    lo, hi = SUPPORT
    below = float(norm.cdf(lo, SLAB_MU, SLAB_SIGMA))
    above = float(1.0 - norm.cdf(hi, SLAB_MU, SLAB_SIGMA))
    return below, above


def q_on_grid(q16: np.ndarray, th16: np.ndarray,
              grid: np.ndarray) -> np.ndarray:
    """Interpolate the verdict channel onto the prior's own support."""
    return np.vstack([logit_interp(th16, q16, float(t)) for t in grid])


def evsi_and_contributions(problem, q: np.ndarray):
    """EVSI, and the exact per-theta decomposition of where it comes from.

    `q` is (n_theta, n_levels) = p(y | theta).
    """
    prior, U = problem.prior, problem.utility
    joint = prior[:, None] * q                       # (n_theta, n_levels)
    marg = joint.sum(axis=0)
    post = joint / np.clip(marg, 1e-300, None)[None, :]
    best = (U @ post).argmax(axis=0)                 # optimal action per y
    a0 = int((U @ prior).argmax())

    # contribution(theta) = p(theta) * [ E_y U(a*(y), theta) - U(a0, theta) ]
    gain = np.einsum("ty,yt->t", q, U[best, :]) - U[a0, :]
    contrib = prior * gain
    return float(contrib.sum()), contrib, a0, best


def money(v: float) -> str:
    return f"${v:,.0f}" if np.isfinite(v) else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_m8_full_merged.jsonl")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--expect-iterations", default="1-25")
    args = ap.parse_args()

    d = load(args.results)
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    d = d.assign(_verdict=verdict_index(d))
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    lo, _, hi = args.expect_iterations.partition("-")
    d = require_complete_clusters(d, thetas,
                                  expect_iterations=range(int(lo), int(hi) + 1))
    tools = sorted(d.tool_label.unique())
    th16 = np.array(thetas)

    theta, prior, kind = build_prior()
    problem = budget_problem(theta, prior)
    below, above = excluded_slab_mass()

    print("== the prior, in its declared form ==")
    print(f"   p(theta) = {PI_NULL} * delta_0  +  {1-PI_NULL:.2f} * "
          f"N({SLAB_MU}, {SLAB_SIGMA}^2)")
    print(f"   the spike is an ATOM, not a normal of width 0.005 evaluated on")
    print(f"   a grid -- so its weight is exactly {PI_NULL} however fine the")
    print(f"   grid gets, instead of depending on the spacing near zero.")
    print(f"\n   support: [{100*SUPPORT[0]:+.0f}%, {100*SUPPORT[1]:+.0f}%], "
          f"{len(theta)} points (1 atom + {len(theta)-1} slab)")
    print(f"   slab mass excluded by that restriction: "
          f"{100*below:.2f}% below, {100*above:.2f}% above")
    print(f"   = {100*(1-PI_NULL)*(below+above):.2f}% of total prior mass, "
          f"dropped because the gate validated")
    print(f"     INTERPOLATION and says nothing about extrapolation.")
    neg = float(prior[theta < 0].sum())
    print(f"\n   prior mass below zero: {neg:.3f}")
    print(f"   (the seven-point surrogate carried 0.071; the 'sensitivity "
          f"prior\n    matched on negative mass' can now retire)")
    print(f"\n   actions: {', '.join(DEFAULT_ACTIONS)}")
    print(f"   boundaries: {['%+.4f%%' % (100*b) for b in action_boundaries()]}")
    print(f"   prior-optimal action: {problem.best_action_no_experiment()!r}")
    print(f"   EVPI: {money(problem.evpi())}")

    print(f"\n== Finding A on the documented prior ==")
    print(f"   q(theta) interpolated from the {len(th16)} simulated truths, "
          f"cluster\n   bootstrap over (scenario, iteration), "
          f"{args.draws:,} draws, alpha={args.alpha}.\n")
    print(f"   {'tool':18s} {'VERDICT':>10s} {'BIT':>10s} {'V-B median':>11s} "
          f"{'95% credible':>22s}")

    results = {}
    for tool in tools:
        V, _ = verdict_matrix(d[d.tool_label == tool], thetas)
        rng = np.random.default_rng(0)
        draws = cluster_bootstrap_draws(V, args.alpha, args.draws, rng)
        v_list, b_list, contribs = [], [], []
        for i in range(len(draws)):
            qg = q_on_grid(draws[i], th16, theta)
            ev, cv, _, _ = evsi_and_contributions(problem, qg)
            eb, cb, _, _ = evsi_and_contributions(problem, qg @ GARBLE.T)
            v_list.append(ev)
            b_list.append(eb)
            contribs.append(cv - cb)
        v = np.array(v_list)
        b = np.array(b_list)
        gap = v - b
        C = np.vstack(contribs)
        results[tool] = (v, b, gap, C)
        print(f"   {tool:18s} {money(np.median(v)):>10s} "
              f"{money(np.median(b)):>10s} {money(np.median(gap)):>11s} "
              f"{'[' + money(np.quantile(gap, .025)) + ', ' + money(np.quantile(gap, .975)) + ']':>22s}")

    worst = min(float((r[0] - r[1]).min()) for r in results.values())
    print(f"\n   self-test: min(V - B) over all draws = {worst:+.3e}  "
          f"{'PASS' if worst >= -1e-6 else 'FAIL -- STOP'}")

    print(f"\n== where the sign's value comes from ==")
    print("   A NEGATIVE regional contribution is not an error. Blackwell")
    print("   guarantees V >= B in TOTAL, not at every truth: extra")
    print("   resolution can move the policy to an action that happens to be")
    print("   worse at one theta while paying for itself on average. Those")
    print("   are reported, not clipped.")
    print("   EVSI is not a sum over theta, but the gain over the baseline")
    print("   action is: contribution(theta) = p(theta) * [E_y U(a*(y),theta)")
    print("   - U(a0,theta)]. Exact, additive, and it can be negative where a")
    print("   signal misleads. Reported as medians of the V-B contribution.\n")
    print(f"   {'tool':18s} {'spike (0)':>12s} {'slab < 0':>12s} "
          f"{'slab > 0':>12s} {'total':>12s}")
    for tool in tools:
        C = results[tool][3]
        parts = [float(np.median(C[:, kind == k].sum(axis=1)))
                 for k in (0, -1, 1)]
        tot = float(np.median(C.sum(axis=1)))
        print(f"   {tool:18s} {money(parts[0]):>12s} {money(parts[1]):>12s} "
              f"{money(parts[2]):>12s} {money(tot):>12s}")

    print(f"\n   as a share of the total. NOTE: medians are not additive --")
    print("   the three regional medians need not sum to the median total, so")
    print("   the shares are taken against the sum of the parts and the")
    print("   residual is printed rather than hidden by normalising it away.")
    print()
    for tool in tools:
        C = results[tool][3]
        parts = [float(np.median(C[:, kind == k].sum(axis=1)))
                 for k in (0, -1, 1)]
        med_total = float(np.median(C.sum(axis=1)))
        ssum = sum(parts)
        if abs(ssum) < 1e-9:
            print(f"   {tool:18s} parts sum to ~$0; shares undefined")
            continue
        sh = [100 * x / ssum for x in parts]
        print(f"   {tool:18s} spike {sh[0]:6.1f}%   neg slab {sh[1]:6.1f}%   "
              f"pos slab {sh[2]:6.1f}%")
        print(f"   {'':18s} sum of medians {money(ssum)} vs median total "
              f"{money(med_total)}  "
              f"(non-additivity: {money(ssum - med_total)})")

    print(f"\n== concentration: is the value spread, or is it a sliver? ==")
    print("   The share of |contribution| carried by the smallest set of grid")
    print("   points reaching 50% and 90% of the total. A headline that comes")
    print("   almost entirely from a narrow band near a boundary is a")
    print("   different finding from the same number spread evenly, and one")
    print("   dollar figure cannot distinguish them.\n")
    for tool in tools:
        C = np.median(results[tool][3], axis=0)
        mass = np.abs(C)
        if mass.sum() <= 0:
            continue
        order = np.argsort(-mass)
        cum = np.cumsum(mass[order]) / mass.sum()
        n50 = int(np.searchsorted(cum, 0.50) + 1)
        n90 = int(np.searchsorted(cum, 0.90) + 1)
        span = theta[order[:n90]]
        print(f"   {tool:18s} 50% of |contribution| in {n50:3d}/{len(theta)} "
              f"points, 90% in {n90:3d}")
        print(f"   {'':18s} those 90% span "
              f"[{100*span.min():+.2f}%, {100*span.max():+.2f}%]")


if __name__ == "__main__":
    main()
