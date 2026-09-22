#!/usr/bin/env python
"""Which of the donor's four estimators are deterministic? Ask the donor's data.

This runs against the *published* `results.jsonl` alone. No replay, no donor
execution, no environment required beyond pandas/numpy -- which is the point:
it settles a question that the G3 tolerance table had to answer before any
compute was spent, and it settles it from artefacts that already exist.

The identity it exploits
------------------------
The donor generates the null and effect panels of an iteration from the same
seed, so they share their entire pre-treatment data, and applies the effect as
a multiplicative shift on the treated geo's post-period only
(`generate_panels.R:265`). For an estimator that is a deterministic function
of the panel and linear in the outcome,

    att_level(effect) - att_level(null) - true_att_level(effect) == 0

per iteration, exactly. The residual is therefore a direct measure of how much
non-determinism each tool injects into its own point estimate -- without
needing to run anything twice.

What it found
-------------
Three of the four are deterministic, including CausalImpact, which the G3
table had classified as platform-sensitive MCMC. It is seeded
(`run_tools.py:173` -> `run_causalimpact.R:98`), and R's Mersenne-Twister
does not vary by platform. Only CausalPy carries genuine Monte Carlo noise in
its published point estimate -- 1.3% of the effect on A1-A3, 3.2% on A4,
the short panel.

The 3e-5 floor for GeoLift and CausalImpact is *not* a solver tolerance,
which an earlier version of this file claimed. Both R adapters round every
level and interval to 4 decimal places on output; a half-ULP of that is 5e-5,
and a residual combining three such values has exactly the observed median of
3e-5 and maximum of 9.8e-5. Those two tools are as deterministic as
`google_mm`; the donor simply did not publish enough digits to see it. The
giveaway was that the residual is a *constant absolute* value across two
tools and four scenarios of very different magnitudes.

Two caveats this cannot escape. It measures determinism *on one machine*,
from one set of runs -- cross-platform determinism is a stronger claim and
only the replay tests it. And for the two 4-dp tools it cannot see below the
published precision, so "exact" here means "exact as far as the artefact
allows".

    python marketing_experimentation/repro/recast/determinism_probe.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_RESULTS = (
    "/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl"
)


def load(path: str) -> pd.DataFrame:
    return pd.DataFrame([json.loads(line) for line in Path(path).open()])


def residuals(d: pd.DataFrame, scenario: str) -> pd.DataFrame:
    """Per-tool |att(effect) - att(null) - true_att| over shared iterations."""
    keys = ["tool", "posterior_type", "scenario", "iteration"]
    if "posterior_type" not in d.columns:
        d = d.assign(posterior_type="")
    d = d[d.scenario == scenario]

    eff = d[d.effect_label == "effect"].set_index(keys)
    nul = d[d.effect_label == "null"].set_index(keys)
    common = eff.index.intersection(nul.index)
    eff, nul = eff.loc[common], nul.loc[common]

    resid = (eff.att_level - nul.att_level) - eff.true_att_level
    out = pd.DataFrame({
        "resid": resid.abs(),
        "true_att_level": eff.true_att_level,
    }).reset_index()
    return out[np.isfinite(out.resid)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=DEFAULT_RESULTS)
    ap.add_argument("--scenario", default="A1")
    args = ap.parse_args()

    d = load(args.results)
    r = residuals(d, args.scenario)
    if r.empty:
        raise SystemExit(f"no paired rows for scenario {args.scenario}")

    print(f"scenario {args.scenario} | "
          f"identity: att(effect) - att(null) - true_att == 0 for a "
          f"deterministic estimator\n")
    print(f"{'tool':14s} {'posterior':10s} {'n':>5s} {'median':>12s} "
          f"{'max':>12s} {'% of true':>10s}  class")

    for (tool, pt), g in r.groupby(["tool", "posterior_type"], sort=True):
        med = float(g.resid.median())
        rel = med / float(g.true_att_level.median())
        cls = ("exact" if rel < 1e-12 else
               "exact (4dp-censored)" if med < 1e-4 else
               "stochastic")
        print(f"{tool:14s} {str(pt):10s} {len(g):5d} {med:12.6g} "
              f"{g.resid.max():12.6g} {100 * rel:10.4f}  {cls}")

    print("\nA residual at machine epsilon means linear algebra. A residual "
          "pinned at a\nconstant ~3e-5 regardless of magnitude means output "
          "rounded to 4 decimal\nplaces, not randomness -- see `precision` "
          "below. A residual at a percent of\nthe effect means the published "
          "point estimate carries Monte Carlo noise of\nthat size.\n")

    print("published decimal places (the ceiling on any comparison):")
    fields = ["att_level", "ci_lower", "ci_upper"]
    for tool in sorted(d.tool.unique()):
        g = d[(d.tool == tool) & (d.scenario == args.scenario)]
        dp = {f: int(g[f].dropna().map(_decimals).max()) for f in fields
              if f in g.columns}
        print(f"  {tool:14s} " + "  ".join(f"{f}={v}" for f, v in dp.items()))


def _decimals(x: float) -> int:
    """Decimal places in the shortest round-tripping repr of a float."""
    s = repr(float(x))
    if "e" in s or "E" in s:
        return 17
    return len(s.partition(".")[2])


if __name__ == "__main__":
    main()
