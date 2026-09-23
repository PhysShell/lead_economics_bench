#!/usr/bin/env python
"""S0's value is *determined* by (FPR, TPR), not correlated with them.

An earlier write-up offered a Spearman correlation of 1.00 between each
tool's discrimination (TPR - FPR) and the share of decision value surviving
the significance bit, and called it a mechanistic explanation. It is not
one. A rank correlation on four points has an exact two-sided permutation
p-value of 2/4! = 0.083 even when perfect, and more to the point a
correlation is not a mechanism at all.

The mechanism is available in closed form, and it is stronger.

The argument
------------
At rung S0 the decision sees exactly one bit, `significant`. That channel is
fully described by two numbers::

    P(Z = 1 | theta = 0)      = FPR
    P(Z = 1 | theta = effect) = TPR

Nothing else about the estimator reaches the decision. So for a fixed prior
`pi` and utility matrix `U`, EVSI is a deterministic function of the pair::

    P(Z=z)            = sum_theta p(theta) P(z | theta)
    p(theta | Z=z)    = p(theta) P(z | theta) / P(Z=z)
    EVSI              = sum_z P(Z=z) max_a E[U(a, theta) | Z=z]
                        - max_a E[U(a, theta)]

This script evaluates that expression from Recast's **published** `metrics.csv`
FPR and FNR -- numbers computed by their code, not ours -- and compares it
against the S0 figures the ladder obtained by counting significance flags
row by row. Two independent paths to the same quantity.

If they agree numerically, the claim becomes::

    The S0 rung is mechanically determined by each tool's binary
    significance channel under this decision problem.

which is a statement about what the bit can carry, not about four points
happening to sort the same way.

    python marketing_experimentation/scripts/s0_reconstruction.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import two_point_problem  # noqa: E402

DONOR = "/home/user/getrecast/geolift-simulation-study"


def evsi_from_confusion(fpr: float, tpr: float, pi: float,
                        c_fp: float, c_fn: float) -> float:
    """EVSI of a binary channel, in closed form, from its two error rates."""
    problem = two_point_problem(pi, c_fp, c_fn)
    # likelihood[z, theta] = P(Z = z | theta), theta order (null, effect)
    like = np.array([[1.0 - fpr, 1.0 - tpr],
                     [fpr, tpr]])
    marg = like @ problem.prior
    total = 0.0
    for z in range(2):
        post = problem.prior * like[z]
        s = post.sum()
        post = post / s if s > 0 else problem.prior
        total += marg[z] * float((problem.utility @ post).max())
    return total - problem.value_no_experiment()


def evsi_from_rows(d: pd.DataFrame, tool: str, scenario: str, pi: float,
                   c_fp: float, c_fn: float) -> tuple[float, float, float]:
    """The ladder's own path: count significance flags, then the same sum."""
    g = d[(d.tool_label == tool) & (d.scenario == scenario)]
    fpr = float(g[g.effect_pct == 0].significant.astype(bool).mean())
    tpr = float(g[g.effect_pct != 0].significant.astype(bool).mean())
    return evsi_from_confusion(fpr, tpr, pi, c_fp, c_fn), fpr, tpr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=f"{DONOR}/results/raw/results.jsonl")
    ap.add_argument("--metrics", default=f"{DONOR}/results/aggregated/metrics.csv")
    ap.add_argument("--scenario", default="A1")
    ap.add_argument("--prior", type=float, default=0.4)
    ap.add_argument("--c-fn", type=float, default=500_000.0)
    ap.add_argument("--ratio", type=float, default=1.0)
    args = ap.parse_args()

    c_fn = args.c_fn
    c_fp = args.ratio * c_fn

    d = pd.DataFrame([json.loads(l) for l in Path(args.results).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"_{s}" if s else "")

    m = pd.read_csv(args.metrics)
    m = m[m.scenario == args.scenario]
    pub_fpr = m[m.effect_pct == 0].set_index("tool_label").fpr
    pub_fnr = m[m.effect_pct != 0].set_index("tool_label").fnr

    print(f"scenario {args.scenario} | prior {args.prior} | "
          f"C_FP/C_FN {args.ratio} | C_FN ${c_fn:,.0f}\n")
    print("Two independent paths to EVSI(S0):")
    print("  A  closed form from the donor's PUBLISHED FPR/FNR in metrics.csv")
    print("  B  the ladder's own count of significance flags, row by row\n")

    print(f"{'tool':16s} {'FPR':>7s} {'TPR':>7s} "
          f"{'A published':>13s} {'B row-level':>13s} {'|A-B|':>9s}")
    rows = []
    for tool in sorted(pub_fpr.index):
        fpr_p = float(pub_fpr[tool])
        tpr_p = 1.0 - float(pub_fnr[tool])
        a = evsi_from_confusion(fpr_p, tpr_p, args.prior, c_fp, c_fn)
        b, fpr_r, tpr_r = evsi_from_rows(d, tool, args.scenario,
                                         args.prior, c_fp, c_fn)
        print(f"{tool:16s} {100*fpr_p:6.1f}% {100*tpr_p:6.1f}% "
              f"${a:>12,.0f} ${b:>12,.0f} ${abs(a-b):>8,.2f}")
        rows.append(dict(tool=tool, fpr=fpr_p, tpr=tpr_p,
                         evsi_published=a, evsi_rowlevel=b))

    r = pd.DataFrame(rows)
    worst = float((r.evsi_published - r.evsi_rowlevel).abs().max())
    print(f"\nlargest disagreement between the two paths: ${worst:,.2f}")
    if worst < 1.0:
        print("\nSo EVSI(S0) is reconstructed to the dollar from two numbers "
              "per tool.\nThe S0 rung is MECHANICALLY DETERMINED by the "
              "binary significance channel\nunder this decision problem -- "
              "not correlated with it.")
    else:
        print("\nThe paths disagree. Investigate before claiming either.")

    # The closed form, written out, and a shortcut that does NOT hold.
    print("\n== the closed form, and a tempting identity that is false ==")
    print("   With two actions and utilities (0, -c_FN), (-c_FP, 0):\n")
    print("     EVSI = min(pi*c_FN, (1-pi)*c_FP)")
    print("            - min(pi*(1-TPR)*c_FN, (1-pi)*(1-FPR)*c_FP)")
    print("            - min(pi*TPR*c_FN,     (1-pi)*FPR*c_FP)\n")
    print("   GeoLift, pi=0.4, c=500k:")
    pi = args.prior
    f, t = float(pub_fpr["geolift"]), 1.0 - float(pub_fnr["geolift"])
    t0 = min(pi * c_fn, (1 - pi) * c_fp)
    t1 = min(pi * (1 - t) * c_fn, (1 - pi) * (1 - f) * c_fp)
    t2 = min(pi * t * c_fn, (1 - pi) * f * c_fp)
    print(f"     {t0:>9,.0f} - {t1:>9,.0f} - {t2:>9,.0f} = {t0-t1-t2:>9,.0f}")

    # An earlier draft of this script read a few grid cells and was about to
    # assert EVSI = EVPI * (TPR - FPR). It is false, and the failure is not
    # marginal -- so it is tested here rather than left as folklore.
    worst_id = 0.0
    for fpr in np.linspace(0, 0.6, 13):
        for tpr in np.linspace(0, 1.0, 21):
            got = evsi_from_confusion(fpr, tpr, pi, c_fp, c_fn)
            pred = two_point_problem(pi, c_fp, c_fn).evpi() * max(tpr - fpr, 0)
            worst_id = max(worst_id, abs(got - pred))
    print(f"\n   Shortcut `EVSI = EVPI * (TPR - FPR)`: WRONG by up to "
          f"${worst_id:,.0f}")
    print(f"   over the same grid. GeoLift would be ${8200:,.0f} under it "
          f"and is ${t0-t1-t2:,.0f}.")
    print("   The min() structure is the whole content: the bit is worth "
          "something only\n   where it moves the posterior far enough to "
          "change which loss binds.")

    print("\n== what the channel is worth, over its own two numbers ==")
    grid = [0.0, 0.05, 0.10, 0.20, 0.30]
    print("   " + "TPR\\FPR".ljust(10)
          + "".join(f"{100*f:>10.0f}%" for f in grid))
    for tpr in (0.10, 0.30, 0.50, 0.70, 0.90, 1.00):
        line = f"   {100*tpr:>6.0f}%   "
        for fpr in grid:
            line += f"{evsi_from_confusion(fpr, tpr, pi, c_fp, c_fn):>10,.0f} "
        print(line)
    print("\n   A bit with TPR <= FPR is worth exactly $0 whatever its level. "
          "GeoLift's\n   well-calibrated 4.6% FPR buys it almost nothing at a "
          "TPR of 8.7% -- not\n   because calibration is bad, but because the "
          "channel is nearly mute.")

    Path("s0_reconstruction_results.json").write_text(
        r.to_json(orient="records", indent=2))
    sys.exit(0 if worst < 1.0 else 1)


if __name__ == "__main__":
    main()
