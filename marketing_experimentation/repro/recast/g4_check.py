#!/usr/bin/env python
"""Check the six G4 PASS criteria mechanically, for one theta mutation.

The mutation test asks whether the pipeline is parameterised in theta or
merely appears to be. The six criteria are fixed in `docs/donor-repro.md` §5
and are checked here by a program rather than by reading output, because
four of the twelve findings in that document exist precisely because
something looked right.

    1  the generator accepts an arbitrary theta
    2  the recorded true ATT reflects the requested theta, not 7.5
    3  all four adapters complete without error
    4  the output schema is unchanged
    5  downstream metrics do not assume `effect_label` means exactly 7.5%
    6  the decision layer can consume the new theta

Criterion 5 is the one to distrust: the static audit (§5a) found the metrics
layer clean and the figure layer hard-coded at 7.5%, and writing the patch
then found a *third* coupling the audit had missed. So this checks the
numbers the metrics layer produces, not just that it ran.

    python g4_check.py --results .../results.jsonl --theta 0.02 \
                       --metrics .../metrics.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

PUBLISHED = (
    "/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl"
)
EXPECTED_TOOLS = {"google_mm", "geolift", "causalpy", "causalimpact"}


def load(path: str) -> pd.DataFrame:
    return pd.DataFrame([json.loads(l) for l in Path(path).open()])


class Checks:
    def __init__(self) -> None:
        self.rows: list[tuple[int, str, bool, str]] = []

    def add(self, n: int, name: str, ok: bool, detail: str) -> None:
        self.rows.append((n, name, ok, detail))

    def report(self) -> bool:
        print(f"\n{'':2s} {'criterion':52s} {'':6s} detail")
        print("-" * 100)
        for n, name, ok, detail in self.rows:
            print(f"{n:2d} {name:52s} {'PASS' if ok else 'FAIL':6s} {detail}")
        allok = all(r[2] for r in self.rows)
        print("-" * 100)
        print(f"G4 verdict: {'PASS' if allok else 'FAIL'}"
              f"  ({sum(r[2] for r in self.rows)}/{len(self.rows)})")
        return allok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--theta", type=float, required=True,
                    help="requested effect as a proportion, e.g. 0.02 or -0.05")
    ap.add_argument("--metrics", default=None)
    ap.add_argument("--published", default=PUBLISHED)
    args = ap.parse_args()

    d = load(args.results)
    theta = args.theta
    c = Checks()

    print(f"requested theta = {theta:+.4f} ({100 * theta:+.2f}%)")
    print(f"rows {len(d):,} | arms {sorted(d.effect_label.unique())}")

    # --- 1: the generator accepted the theta we asked for.
    got = sorted(d.effect_pct.unique())
    ok1 = any(np.isclose(g, theta, atol=1e-9) for g in got)
    c.add(1, "generator accepts arbitrary theta", ok1,
          f"effect_pct present: {[round(g, 4) for g in got]}")

    # --- 2: the recorded true ATT reflects it. This is the check that a
    # hard-coded 0.075 anywhere in the generator would fail.
    arm = d[np.isclose(d.effect_pct, theta, atol=1e-9)]
    if arm.empty:
        c.add(2, "true ATT reflects theta, not 7.5", False, "no rows at theta")
    else:
        tap = pd.to_numeric(arm.true_att_pct, errors="coerce")
        med = float(tap.median())
        ok2 = bool(np.isclose(med, theta, rtol=1e-6, atol=1e-9))
        near_075 = bool(np.isclose(med, 0.075, atol=1e-6)) and theta != 0.075
        c.add(2, "true ATT reflects theta, not 7.5", ok2 and not near_075,
              f"median true_att_pct = {med:+.6f}, requested {theta:+.6f}"
              + ("  <-- STUCK AT 7.5%" if near_075 else ""))

    # --- 3: every adapter produced usable rows, not just rows.
    per = d.groupby("tool").apply(
        lambda x: pd.Series({
            "n": len(x),
            "usable": int(pd.to_numeric(x.att_pct, errors="coerce").notna().sum()),
        }), include_groups=False)
    missing = EXPECTED_TOOLS - set(per.index)
    dead = per[per.usable == 0]
    ok3 = not missing and dead.empty
    c.add(3, "all four adapters complete", ok3,
          (f"missing {sorted(missing)}; " if missing else "")
          + ", ".join(f"{t}:{int(r.usable)}/{int(r.n)}" for t, r in per.iterrows()))

    # --- 4: schema unchanged against the published artefact.
    pub_cols = set(load(args.published).columns)
    new_cols = set(d.columns)
    ok4 = pub_cols == new_cols
    c.add(4, "output schema unchanged", ok4,
          "identical" if ok4 else
          f"added {sorted(new_cols - pub_cols)} removed {sorted(pub_cols - new_cols)}")

    # --- 5: the metrics layer computes against the TRUE theta, not a constant.
    if args.metrics and Path(args.metrics).exists():
        m = pd.read_csv(args.metrics)
        mm = m[np.isclose(m.effect_pct, theta, atol=1e-9)]
        if mm.empty:
            c.add(5, "metrics do not assume effect_label == 7.5%", False,
                  "no metrics rows at this theta")
        else:
            tap = float(mm.true_att_pct.median())          # already in pp
            ok5a = bool(np.isclose(tap, 100 * theta, atol=1e-3))
            # bias must equal avg_att_pct - true_att_pct at THIS theta
            resid = (mm.avg_att_pct - mm.true_att_pct - mm.bias_pct_pts).abs()
            ok5b = bool((resid < 1e-2).all())
            c.add(5, "metrics do not assume effect_label == 7.5%", ok5a and ok5b,
                  f"metrics true_att_pct={tap:+.3f}pp (expect {100*theta:+.3f}); "
                  f"bias identity max resid {resid.max():.4f}pp")
    else:
        c.add(5, "metrics do not assume effect_label == 7.5%", False,
              "metrics.csv not supplied -- criterion untested, not passed")

    # --- 6: the decision layer accepts it.
    try:
        from leadbench_mx.decision import two_point_problem  # noqa: E402
        p = two_point_problem(0.4, 500_000.0, 500_000.0, effect=theta)
        evpi = p.evpi()
        ok6 = bool(np.isfinite(evpi) and evpi >= 0
                   and np.isclose(p.theta[1], theta))
        c.add(6, "decision layer consumes this theta", ok6,
              f"two_point_problem(effect={theta:+.4f}) -> theta={p.theta}, "
              f"EVPI ${evpi:,.0f}")
    except Exception as exc:
        c.add(6, "decision layer consumes this theta", False,
              f"{type(exc).__name__}: {exc}")

    # --- sign check, only meaningful for a negative theta (M6b).
    if theta < 0 and not arm.empty:
        est = pd.to_numeric(arm.att_pct, errors="coerce").dropna()
        frac_neg = float((est < 0).mean())
        print(f"\nsign mutation: {100 * frac_neg:.1f}% of estimates are "
              f"negative at theta = {100 * theta:+.1f}%")
        print("  (a pipeline that quietly assumes lift would show this near "
              "0%; a working\n   one should track the truth)")

    sys.exit(0 if c.report() else 1)


if __name__ == "__main__":
    main()
