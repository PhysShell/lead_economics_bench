#!/usr/bin/env python
"""M9-A: what is the information worth, as a rate? Not what does it cost.

The scoped question
-------------------
The DGP contains no spend, no budget and no intervention -- `generate_panels.R`
multiplies a treated geo's outcome by `(1 + effect_pct)` and nothing produces
that lift. So this simulation **can** identify

    r_EVSI = EVSI / S_governed          and      C*(S) = r_EVSI * S

and **cannot** identify `Delta_spend -> theta -> revenue`, which is what an
actual geo intervention costs. Rather than assume a cost model, invert the
question: the largest net economic cost at which an experiment still pays IS
its EVSI, and that needs no cost model at all.

This script therefore prices the information and stops. Whether real geo
experiments cost more than the threshold is an external-data question, to be
answered against vendor documentation rather than against this DGP.

Why a rate and not a dollar
---------------------------
`budget_problem`'s utility is `spend*d*k*(theta-b) - spend*c*d^2`, linear in
`spend`, so every value-of-information quantity is exactly proportional to
it. "$2,579" was a statement about a $1M budget, not about geo testing. The
invariant is the rate, and the linearity is verified here rather than
asserted from the algebra.

Horizon
-------
**L = 1, rho = 1.** One decision, no drift, no discounting. Stated rather
than inherited: an experiment informing twelve monthly budgets is worth more,
though not 12x if theta drifts, and no lifetime multiplier is applied until
one is preregistered.

    python marketing_experimentation/scripts/m9a_break_even.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.clusters import require_complete_clusters  # noqa: E402
from leadbench_mx.decision import budget_problem  # noqa: E402
from signed_verdict import (  # noqa: E402
    ALPHA, GARBLE, cluster_bootstrap_draws, load, verdict_index, verdict_matrix,
)
from continuous_finding_a import (  # noqa: E402
    build_prior, evsi_and_contributions, q_on_grid,
)

#: The reference scale everything is computed at. Only the ratio matters.
REFERENCE_SPEND = 1_000_000.0

#: Declared horizon. Not a default -- a choice.
HORIZON_L = 1
HORIZON_RHO = 1.0

#: Spend scales for the illustrative break-even table. Derived from the rate,
#: not independently computed.
ILLUSTRATIVE_SPEND = (250_000, 1_000_000, 5_000_000, 20_000_000, 100_000_000)


def pct(x: float) -> str:
    return f"{100*x:.4f}%"


def money(v: float) -> str:
    return f"${v:,.0f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_m8_full_merged.jsonl")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--alpha", type=float, default=ALPHA)
    args = ap.parse_args()

    print("=" * 72)
    print("M9-A: the price of information, as a rate")
    print("=" * 72)
    print("This prices the INFORMATION. It does not price the EXPERIMENT, and")
    print("cannot: the DGP has no spend variable, so Delta_spend -> theta ->")
    print("revenue is not identifiable here. See docs/m9-preregistration.md §1.")
    print(f"\nHorizon: L = {HORIZON_L} decision, rho = {HORIZON_RHO}, no "
          f"discounting. Declared, not inherited.")

    # -- 1. the linearity, verified rather than assumed -------------------
    print("\n== 1. is EVPI exactly proportional to spend? ==")
    th, pr, kind = build_prior()
    rates = []
    for s in (1e4, 1e5, 1e6, 1e7, 1e8, 1e9):
        rates.append(budget_problem(th, pr, spend=s).evpi() / s)
    spread = max(rates) - min(rates)
    print(f"   EVPI/spend over 1e4..1e9: {rates[0]:.12f}")
    print(f"   spread across six decades: {spread:.3e}   "
          f"{'EXACT' if spread < 1e-12 else 'NOT EXACT -- the rate framing fails'}")
    if spread >= 1e-12:
        raise SystemExit("utility is not linear in spend; M9-A's unit is wrong")
    print("   So the transportable quantity is a RATE. A dollar figure is a")
    print("   statement about the budget it was computed at.")

    # -- 2. the rates ------------------------------------------------------
    d = load(args.results)
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    d = d.assign(_verdict=verdict_index(d))
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    d = require_complete_clusters(d, thetas, expect_iterations=range(1, 26))
    tools = sorted(d.tool_label.unique())
    th16 = np.array(thetas)
    problem = budget_problem(th, pr, spend=REFERENCE_SPEND)
    evpi_rate = problem.evpi() / REFERENCE_SPEND

    print(f"\n== 2. the price of information, per decision ==")
    print(f"   as a share of the spend the decision governs. "
          f"{args.draws:,} cluster-bootstrap draws.\n")
    print(f"   {'tool':18s} {'VERDICT':>10s} {'BIT':>10s} {'V-B':>10s} "
          f"{'V-B 95% credible':>22s}")

    out = {}
    for tool in tools:
        V, _ = verdict_matrix(d[d.tool_label == tool], thetas)
        rng = np.random.default_rng(0)
        draws = cluster_bootstrap_draws(V, args.alpha, args.draws, rng)
        v, b = [], []
        for i in range(len(draws)):
            qg = q_on_grid(draws[i], th16, th)
            v.append(evsi_and_contributions(problem, qg)[0])
            b.append(evsi_and_contributions(problem, qg @ GARBLE.T)[0])
        v, b = np.array(v) / REFERENCE_SPEND, np.array(b) / REFERENCE_SPEND
        gap = v - b
        out[tool] = (float(np.median(v)), float(np.median(b)),
                     float(np.median(gap)),
                     float(np.quantile(gap, .025)),
                     float(np.quantile(gap, .975)))
        m = out[tool]
        print(f"   {tool:18s} {pct(m[0]):>10s} {pct(m[1]):>10s} "
              f"{pct(m[2]):>10s} {'[' + pct(m[3]) + ', ' + pct(m[4]) + ']':>22s}")
    print(f"   {'EVPI ceiling':18s} {pct(evpi_rate):>10s}")

    # -- 3. the break-even surface ----------------------------------------
    print(f"\n== 3. break-even: the largest NET ECONOMIC cost at which the ==")
    print(f"==    signed-verdict experiment still pays, at L = 1          ==")
    print("   This is EVSI restated, which is the point: no cost model is")
    print("   needed to state a threshold. Rows are derived from the rates")
    print("   above by multiplication, not computed independently.\n")
    print(f"   {'governed spend':>16s} " + " ".join(
        f"{t[:12]:>13s}" for t in tools))
    for s in ILLUSTRATIVE_SPEND:
        cells = " ".join(f"{money(out[t][0] * s):>13s}" for t in tools)
        print(f"   {money(s):>16s} " + cells)
    print("\n   (VERDICT, i.e. the whole signed-verdict experiment. The SIGN")
    print("    alone -- what an unsigned bit throws away -- is the V-B column.)")

    # -- 4. the inversion, which is the deliverable ------------------------
    print(f"\n== 4. the question this hands to the outside world ==")
    best = max(out.values(), key=lambda m: m[0])[0]
    worst = min(out.values(), key=lambda m: m[0])[0]
    print(f"   A signed-verdict experiment is worth {pct(worst)}-{pct(best)} "
          f"of the spend it\n   governs, per decision, in this simulation "
          f"world.")
    for c in (5_000, 20_000, 50_000):
        lo_s, hi_s = c / best, c / worst
        print(f"   An experiment costing {money(c):>8s} net breaks even at "
              f"{money(lo_s)}-{money(hi_s)}\n      of governed spend, for ONE "
              f"decision.")
    print("\n   Whether real geo experiments cost more or less than that is")
    print("   NOT answerable here. It is an external-data question, and the")
    print("   figure to compare against is the NET ECONOMIC cost -- not the")
    print("   ad spend perturbed, which differs in sign as well as magnitude.")

    print(f"\n== what this is not ==")
    print("   * not an ENBS: no cost model, deliberately")
    print("   * not a design frontier: T and G_control are M9-B")
    print(f"   * not a lifetime value: L = {HORIZON_L}, rho = {HORIZON_RHO}")
    print("   * not external validity: the DGP is synthetic and does not")
    print("     contain the economic object a real experiment perturbs")


if __name__ == "__main__":
    main()
