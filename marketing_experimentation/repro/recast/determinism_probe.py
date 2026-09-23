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


def residuals(d: pd.DataFrame, scenario: str,
              theta: float | None = None) -> pd.DataFrame:
    """Per-tool |att(theta) - att(null) - true_att| over shared iterations,
    for ONE non-null truth."""
    keys = ["tool", "posterior_type", "scenario", "iteration"]
    if "posterior_type" not in d.columns:
        d = d.assign(posterior_type="")
    d = d[d.scenario == scenario]

    # Non-null arm by effect size, not by the literal label "effect": that is
    # the name of one particular theta (D7, and our own version of it).
    #
    # But `effect_pct != 0` is only a correct selector when there is ONE
    # non-null truth. On the atlas dataset there are six, and pooling them
    # would compute a single residual over rows whose true effects differ by
    # 25 percentage points -- replacing a hard-coded 7.5% with a hard-coded
    # "anything but zero", which is the same defect wearing a hat. The caller
    # picks a theta; `main` loops over them.
    nonnull = sorted(t for t in d.effect_pct.astype(float).unique() if t != 0.0)
    if theta is None:
        if len(nonnull) != 1:
            raise SystemExit(
                f"{len(nonnull)} non-null truths present ({nonnull}); pass "
                f"--theta to pick one.\nPooling them would average residuals "
                f"across different true effects.")
        theta = nonnull[0]

    eff = d[np.isclose(d.effect_pct.astype(float), theta)].set_index(keys)
    nul = d[d.effect_pct.astype(float) == 0.0].set_index(keys)

    # A duplicated run identity would make `.loc[common]` align rows
    # positionally against rows that are not their counterparts, and the
    # function would return a number rather than an error. It happened: a run
    # that added a posterior type to the config without `make clean` first
    # left doubled y_hat rows, and this probe reported n=40 where n should
    # have been 20. `replay_check.py` already refuses on this; so does this.
    for name, frame in (("effect-arm", eff), ("null-arm", nul)):
        if frame.index.duplicated().any():
            dup = frame.index[frame.index.duplicated()][:3].tolist()
            raise SystemExit(
                f"duplicate run identities in the {name} "
                f"({int(frame.index.duplicated().sum())} rows, e.g. {dup}).\n"
                f"The identity is not unique, so any comparison on it would "
                f"pair arbitrary rows.\nMost likely cause: results.jsonl was "
                f"appended to rather than regenerated -- see D13.")

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
    ap.add_argument("--theta", type=float, default=None,
                    help="which non-null truth to test; required when the "
                         "dataset contains several")
    ap.add_argument("--all-thetas", action="store_true",
                    help="loop over every non-null truth in the dataset")
    args = ap.parse_args()

    d = load(args.results)
    sub = d[d.scenario == args.scenario]
    nonnull = sorted(t for t in sub.effect_pct.astype(float).unique() if t != 0.0)
    thetas = nonnull if args.all_thetas else [args.theta]

    print(f"scenario {args.scenario} | "
          f"identity: att(theta) - att(null) - true_att == 0 for a "
          f"deterministic estimator")
    if len(nonnull) > 1 and not args.all_thetas and args.theta is None:
        raise SystemExit(
            f"\n{len(nonnull)} non-null truths present "
            f"({[round(100*t,1) for t in nonnull]}%).\n"
            f"Pass --theta to pick one, or --all-thetas to loop. Pooling them "
            f"would average\nresiduals across different true effects.")

    for th in thetas:
        _one(d, args, th)


def _one(d, args, th) -> None:
    r = residuals(d, args.scenario, th)
    if r.empty:
        raise SystemExit(f"no paired rows for scenario {args.scenario}")
    if th is not None:
        print(f"\ntheta = {100 * th:+.1f}%")
    print()
    print(f"{'tool':14s} {'posterior':10s} {'n':>5s} {'median':>12s} "
          f"{'max':>12s} {'% of true':>10s}  class")

    for (tool, pt), g in r.groupby(["tool", "posterior_type"], sort=True):
        med = float(g.resid.median())
        # abs(): theta may be negative, and a signed denominator makes `rel`
        # negative, which sails past `rel < 1e-12` and labels a stochastic
        # tool "exact". Caught on the first negative-theta dataset, where
        # causalpy was reported as exact at -1.4704%.
        rel = med / abs(float(g.true_att_level.median()))
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
