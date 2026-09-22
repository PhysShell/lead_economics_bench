#!/usr/bin/env python
"""v1, SUPERSEDED as a value-of-information model; kept as a policy model.

**What this measures is a significance gate, not the value of an experiment.**

    significant     -> take the action
    not significant -> do not take the action

The policy is forced to obey the gate, which is why it can score worse than
acting on the prior, and why this script reported that a *free* experiment was
not worth running over 70% of the plane. That finding violates `EVSI >= 0` --
free information cannot hurt, because you can always ignore it -- so it is not
a statement about experiments. It is a statement about the gate.

`voi_v2.py` computes the value of the experiment properly (EVPI / EVSI / ENBS,
with the invariants enforced). This file stays because the gate is what
conventional experimentation practice actually runs, so the difference between
the two is a research finding rather than a bug to be deleted.

**Do not quote the numbers below as evidence about experiments.** They are
evidence about `p < .05` as a decision rule.
"""Layer 3 on Layer 1's published numbers: which method wins once errors cost money.

Recast's study (June 2026) establishes the statistical behaviour of four
geo-experiment tools and stops, correctly, at the observation that choosing
between them is a business tradeoff between false positives and false
negatives. This script takes that one step further and asks the question a
buyer actually has:

    given how much a false positive costs me, how much a false negative
    costs me, how likely the effect is a priori, and what the experiment
    itself costs -- which tool minimises my expected loss, and is running
    the experiment worth it at all?

Nothing here re-estimates anything. It consumes Recast's published per-run
results and adds a loss function, which is why it can be written in an
afternoon and why its conclusions are only as good as their DGP.

    python marketing_experimentation/scripts/business_phase_diagram.py \
        --results /home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl

Decision model
--------------
A method is a decision rule that returns "significant" or not. Given a prior
`pi` that the channel really works:

    loss(method) = (1-pi) * FPR * C_FP     # scaled a dud channel
                 + pi     * FNR * C_FN     # killed a good channel
                 + C_test                  # cost of running at all

`DO_NOT_RUN` is a first-class competitor, not a fallback. Without an
experiment you act on the prior alone, so you take whichever mistake the
prior makes cheaper, and you pay no experiment cost:

    loss(no test) = min((1-pi) * C_FP, pi * C_FN)

That comparison is the value of information. If no method beats DO_NOT_RUN,
the honest recommendation is to keep the money.

Caveats that limit what this can prove, stated up front:

* FPR/FNR come from Recast's synthetic panels at one effect size (+7.5%).
  A business whose real effects are smaller faces worse FNRs than these.
* A binary significant/not decision throws away the point estimate. A real
  decision would use the magnitude; this is deliberately the crude version,
  because if even the crude version shows the ranking flipping with costs,
  the refined one will too.
* Recast's tools are configured as their study configured them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DO_NOT_RUN = "DO_NOT_RUN"


def load_rates(path: Path) -> pd.DataFrame:
    """Per (tool, scenario) false-positive and false-negative rates."""
    rows = [json.loads(line) for line in path.open()]
    d = pd.DataFrame(rows)
    out = []
    for (tool, scenario), g in d.groupby(["tool", "scenario"]):
        null = g[g.effect_label == "null"]
        eff = g[g.effect_label != "null"]
        if not len(null) or not len(eff):
            continue
        out.append(
            dict(
                tool=tool,
                scenario=scenario,
                fpr=float(null.significant.mean()),
                fnr=float(1.0 - eff.significant.mean()),
                n_null=len(null),
                n_eff=len(eff),
                effect_pct=float(eff.effect_pct.iloc[0]),
            )
        )
    return pd.DataFrame(out)


def expected_loss(fpr: float, fnr: float, pi: float,
                  c_fp: float, c_fn: float, c_test: float) -> float:
    return (1.0 - pi) * fpr * c_fp + pi * fnr * c_fn + c_test


def no_test_loss(pi: float, c_fp: float, c_fn: float) -> float:
    """Act on the prior: take the cheaper of the two mistakes, pay nothing."""
    return min((1.0 - pi) * c_fp, pi * c_fn)


def phase_diagram(rates: pd.DataFrame, scenario: str, c_fn: float,
                  ratios: np.ndarray, priors: np.ndarray,
                  c_test: float) -> pd.DataFrame:
    """Winning decision rule over the (cost ratio, prior) plane."""
    sub = rates[rates.scenario == scenario]
    cells = []
    for pi in priors:
        for ratio in ratios:
            c_fp = ratio * c_fn
            losses = {
                r.tool: expected_loss(r.fpr, r.fnr, pi, c_fp, c_fn, c_test)
                for r in sub.itertuples()
            }
            losses[DO_NOT_RUN] = no_test_loss(pi, c_fp, c_fn)
            winner = min(losses, key=losses.get)
            ordered = sorted(losses.values())
            cells.append(
                dict(
                    prior=pi,
                    cost_ratio=ratio,
                    winner=winner,
                    best_loss=ordered[0],
                    runner_up_gap=ordered[1] - ordered[0],
                    loss_no_test=losses[DO_NOT_RUN],
                    voi=losses[DO_NOT_RUN] - ordered[0],
                )
            )
    return pd.DataFrame(cells)


def fixed_default_regret(rates: pd.DataFrame, scenario: str, c_fn: float,
                         ratios: np.ndarray, priors: np.ndarray,
                         c_test: float) -> pd.DataFrame:
    """What each always-pick-this-one policy costs against the oracle choice.

    This is the kill criterion for the whole layer. If some fixed default has
    near-zero regret everywhere, business-cost-aware selection is decoration.
    """
    grid = phase_diagram(rates, scenario, c_fn, ratios, priors, c_test)
    sub = rates[rates.scenario == scenario]
    policies = list(sub.tool) + [DO_NOT_RUN]
    rows = []
    for policy in policies:
        regrets = []
        for cell in grid.itertuples():
            c_fp = cell.cost_ratio * c_fn
            if policy == DO_NOT_RUN:
                loss = no_test_loss(cell.prior, c_fp, c_fn)
            else:
                r = sub[sub.tool == policy].iloc[0]
                loss = expected_loss(r.fpr, r.fnr, cell.prior, c_fp, c_fn, c_test)
            regrets.append(loss - cell.best_loss)
        regrets = np.array(regrets)
        rows.append(
            dict(
                policy=policy,
                mean_regret=regrets.mean(),
                median_regret=float(np.median(regrets)),
                p90_regret=float(np.percentile(regrets, 90)),
                max_regret=regrets.max(),
                pct_cells_optimal=100.0 * float((regrets <= 1e-9).mean()),
            )
        )
    return pd.DataFrame(rows).sort_values("mean_regret")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results",
        default="/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl",
    )
    ap.add_argument("--c-fn", type=float, default=500_000.0,
                    help="cost of killing a channel that actually works")
    ap.add_argument("--c-test", type=float, default=40_000.0,
                    help="cost of running the experiment (holdout + ops)")
    ap.add_argument("--scenario", default="A1")
    args = ap.parse_args()

    rates = load_rates(Path(args.results))
    print("Rates recomputed from the published per-run results "
          f"({int(rates.n_null.sum() + rates.n_eff.sum()):,} runs).\n")
    show = rates[rates.scenario == args.scenario].copy()
    show["fpr_%"] = (100 * show.fpr).round(1)
    show["fnr_%"] = (100 * show.fnr).round(1)
    print(f"== scenario {args.scenario}, effect = "
          f"{100 * show.effect_pct.iloc[0]:.1f}% ==")
    print(show[["tool", "fpr_%", "fnr_%"]].to_string(index=False))

    ratios = np.round(np.logspace(np.log10(0.1), np.log10(10.0), 25), 4)
    priors = np.round(np.linspace(0.05, 0.90, 18), 4)

    grid = phase_diagram(rates, args.scenario, args.c_fn, ratios, priors,
                         args.c_test)

    print(f"\n== who wins, over cost ratio C_FP/C_FN x prior P(effect) ==")
    print(f"   C_FN = ${args.c_fn:,.0f}   C_test = ${args.c_test:,.0f}\n")
    share = (100 * grid.winner.value_counts(normalize=True)).round(1)
    print("share of the plane won by each rule (%):")
    print(share.to_string())

    print("\nphase map (rows: prior; cols: C_FP/C_FN):")
    pivot = grid.pivot(index="prior", columns="cost_ratio", values="winner")
    abbrev = {"causalimpact": "CI", "causalpy": "CP", "geolift": "GL",
              "google_mm": "MM", DO_NOT_RUN: "--"}
    cols = [c for i, c in enumerate(pivot.columns) if i % 3 == 0]
    compact = pivot[cols].map(lambda v: abbrev.get(v, v[:2]))
    compact.columns = [f"{c:g}" for c in compact.columns]
    print(compact.to_string())
    print("\n  GL=geolift  MM=google_mm  CP=causalpy  CI=causalimpact  "
          "--=DO_NOT_RUN")

    print("\n== the kill test: regret of always picking one rule ==")
    reg = fixed_default_regret(rates, args.scenario, args.c_fn, ratios,
                               priors, args.c_test)
    reg_fmt = reg.copy()
    for c in ("mean_regret", "median_regret", "p90_regret", "max_regret"):
        reg_fmt[c] = reg_fmt[c].map(lambda v: f"${v:,.0f}")
    reg_fmt["pct_cells_optimal"] = reg_fmt.pct_cells_optimal.round(1)
    print(reg_fmt.to_string(index=False))

    best_fixed = reg.iloc[0]
    print(f"\n  best fixed default: {best_fixed.policy}, mean regret "
          f"${best_fixed.mean_regret:,.0f}, optimal in "
          f"{best_fixed.pct_cells_optimal:.0f}% of the plane")

    print("\n== value of information ==")
    run = grid[grid.winner != DO_NOT_RUN]
    print(f"  experiment is worth running in {100 * len(run) / len(grid):.0f}% "
          f"of the plane")
    if len(run):
        print(f"  median VOI where it is worth running: ${run.voi.median():,.0f}")
    dont = grid[grid.winner == DO_NOT_RUN]
    if len(dont):
        print(f"  DO_NOT_RUN wins at prior in "
              f"[{dont.prior.min():.2f}, {dont.prior.max():.2f}] and cost ratio in "
              f"[{dont.cost_ratio.min():g}, {dont.cost_ratio.max():g}]")


if __name__ == "__main__":
    main()
