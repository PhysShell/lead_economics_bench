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

and `pi_0` is exactly 0.45 however fine the grid gets. **After conditioning
on the validated support it is 0.45861, not 0.45** -- see `build_prior`. The
atom survives as an atom; its weight does not survive unchanged.

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
[-15%, +15%], so the prior is CONDITIONED on that interval -- not truncated
without renormalisation, which would leave a measure of mass 0.981219 rather
than a probability distribution. The excluded mass is reported by tail.

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
    """The declared prior CONDITIONED on the validated support.

    Three different objects are available here and an earlier version of this
    function silently built the third one. Naming them, because "the prior"
    stopped being unambiguous the moment the support was restricted::

        0) DECLARED, untruncated        spike 0.45000   P(theta<0) 0.13887
        A) CONDITIONED on the support   spike 0.45861   P(theta<0) 0.14110
        B) slab renormalised, mixture
           weight left at 0.45          spike 0.45000   P(theta<0) 0.14334
        C) sub-probability measure,
           no renormalisation           spike 0.45000   total mass 0.981219

    This returns **A**: `p_V(theta) = p(theta | -0.15 <= theta <= 0.15)`. It
    is the standard object -- EVSI is defined as an expectation under a
    probability distribution, and C is a measure of mass 0.9812, which would
    put every dollar figure ~1.88% low for a reason that is bookkeeping
    rather than decision theory.

    (An earlier draft of this table gave A's negative mass as 0.14153, which
    forgets to exclude the 0.042% of slab mass below -15%. Conditioning drops
    the left tail as well as the right: 0.14110.)

    **The atom stays an atom, but its weight is no longer 0.45.** Under
    conditioning it is `0.45 / 0.981219 = 0.45861`. Saying "pi_0 is exactly
    0.45 at any resolution" is true of the declared prior and false of the
    one the EVSI is computed on; both sentences were in an earlier draft.

    `kind` is 0 for the atom, -1 for slab mass below zero, +1 for slab mass
    at or above zero.
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
    shape = dens * w
    shape = shape / shape.sum()                   # shape only; mass set below

    # Analytic, not quadrature: the slab's share of itself that lies inside.
    s_in = float(norm.cdf(hi, SLAB_MU, SLAB_SIGMA)
                 - norm.cdf(lo, SLAB_MU, SLAB_SIGMA))
    inside = PI_NULL + (1.0 - PI_NULL) * s_in     # total declared mass inside

    theta = np.concatenate([[0.0], grid])
    prior = np.concatenate([[PI_NULL / inside],
                            (1.0 - PI_NULL) * s_in / inside * shape])
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
    lo_t, hi_t = SUPPORT
    s_in = float(norm.cdf(hi_t, SLAB_MU, SLAB_SIGMA)
                 - norm.cdf(lo_t, SLAB_MU, SLAB_SIGMA))
    inside = PI_NULL + (1.0 - PI_NULL) * s_in
    print(f"\n   support: [{100*lo_t:+.0f}%, {100*hi_t:+.0f}%], "
          f"{len(theta)} points (1 atom + {len(theta)-1} slab)")
    print(f"   mass outside, as a share of TOTAL prior mass:")
    print(f"      below {100*lo_t:+.0f}%: {100*(1-PI_NULL)*below:.4f}%"
          f"      above {100*hi_t:+.0f}%: {100*(1-PI_NULL)*above:.4f}%")
    print(f"      total {100*(1-inside):.4f}% -- almost all of it the RIGHT "
          f"tail; the left tail is\n      0.04%, and quoting the total as "
          f"though it were the upper tail was wrong.")
    print(f"\n   EVSI is computed on the prior CONDITIONED on that support:")
    print(f"      p_V(theta) = p(theta | {100*lo_t:+.0f}% <= theta <= "
          f"{100*hi_t:+.0f}%)")
    print(f"   so the atom stays an atom but its weight is NOT 0.45:")
    print(f"      declared   pi_0 = {PI_NULL:.5f}")
    print(f"      condition  pi_0 = {PI_NULL:.2f}/{inside:.6f} = "
          f"{PI_NULL/inside:.5f}   <- what the EVSI uses")
    print(f"   The alternative -- integrating over the validated region "
          f"without\n   renormalising -- is a measure of mass "
          f"{inside:.6f}, not a probability\n   distribution, and would put "
          f"every figure {100*(1-inside):.2f}% low for a reason that\n   is "
          f"bookkeeping rather than decision theory.")
    neg = float(prior[theta < 0].sum())
    # ANALYTIC on both columns. An earlier version printed the declared
    # masses analytically and the conditioned ones by quadrature, which is
    # the same apples-to-oranges move as F19 one level down: the grid cell
    # AT theta = 0 straddles the sign boundary, so its whole trapezoid
    # weight lands in the >= 0 bucket and negative mass reads ~0.0023 low.
    # Both columns are closed form; the quadrature realisation is printed
    # underneath with its error, rather than presented as the exact value.
    nd = (1 - PI_NULL) * float(norm.cdf(0, SLAB_MU, SLAB_SIGMA))
    nd_below = (1 - PI_NULL) * float(norm.cdf(SUPPORT[0], SLAB_MU, SLAB_SIGMA))
    c_spike = PI_NULL / inside
    c_neg = (nd - nd_below) / inside
    c_pos = 1.0 - c_spike - c_neg
    print(f"\n   exact prior masses (closed form, both columns):")
    print(f"      {'':22s} {'declared':>10s} {'conditioned':>12s}")
    print(f"      {'spike (theta = 0)':22s} {PI_NULL:10.5f} {c_spike:12.5f}")
    print(f"      {'slab < 0':22s} {nd:10.5f} {c_neg:12.5f}")
    print(f"      {'slab > 0':22s} {1-PI_NULL-nd:10.5f} {c_pos:12.5f}")
    print(f"\n   quadrature realisation on the {len(theta)}-point grid:")
    print(f"      slab < 0 reads {neg:.5f} against the exact {c_neg:.5f} "
          f"({neg-c_neg:+.5f})")
    print(f"      because the cell AT theta = 0 straddles the sign boundary "
          f"and its\n      whole weight is assigned above it. Reported, not "
          f"absorbed: the\n      decomposition below inherits this, and it "
          f"is smaller than the\n      credible intervals by two orders of "
          f"magnitude.")
    print(f"\n   NOT 0.267. That was the n=81 value of a discretisation")
    print(f"   artefact (F19), and it grows with resolution -- 0.267, 0.344,")
    print(f"   0.359 at n=81, 401, 1601 -- because the gridded spike is")
    print(f"   centred AT zero and half of p_null leaks below it. The")
    print(f"   'sensitivity prior matched on negative mass' retires, and its")
    print(f"   label was describing a property the prior never had.")
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

    print(f"\n   TWO denominators, because with a negative region they answer")
    print("   different questions. NET divides by the sum of the signed parts;")
    print("   GROSS divides by the sum of their absolute values. A region can")
    print("   be 90% of the net and 67% of the gross, and `% of the value` is")
    print("   ambiguous between them.")
    print("\n   NOTE: medians are not additive --")
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
        gross = sum(abs(x) for x in parts)
        gh = [100 * abs(x) / gross for x in parts]
        print(f"   {tool:18s} NET   spike {sh[0]:6.1f}%   neg {sh[1]:6.1f}%   "
              f"pos {sh[2]:6.1f}%   (of the summed signed parts)")
        print(f"   {'':18s} GROSS spike {gh[0]:6.1f}%   neg {gh[1]:6.1f}%   "
              f"pos {gh[2]:6.1f}%   (of summed |parts|)")
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
