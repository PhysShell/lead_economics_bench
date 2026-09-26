#!/usr/bin/env python
"""The nested-channel gate: a real Blackwell family, not two sibling coarsenings.

Why this exists
---------------
`channel_ladder.py` compared VERDICT against SIGN and I described the gap as
"the loss is localised at B -> C". That overstates what Blackwell licenses.
VERDICT and SIGN are **two different coarsenings of the same raw output**,
neither a garbling of the other: from `inconclusive` you cannot recover the
sign, and from `positive` you cannot recover whether it was significant.
Comparing them is legitimate and informative; calling one a step in a chain
is not.

The fix is the common refinement. `VERDICT+SIGN` has four natural states —

    significant-negative | inconclusive-negative
    inconclusive-positive | significant-positive

— and every other channel in the family is an aggregation of it:

                      VERDICT+SIGN  (4)
                       /          \\
              VERDICT (3)          SIGN (2)
                  |
                BIT (2)

    VERDICT   collapse the two inconclusive states into one
    SIGN      collapse significance within each sign
    BIT       collapse VERDICT's neg and pos into `significant`

So Blackwell now supplies **required** inequalities rather than empirical
hopes:

    EVSI(VERDICT+SIGN) >= EVSI(VERDICT) >= EVSI(BIT)
    EVSI(VERDICT+SIGN) >= EVSI(SIGN)

and the answer is interpretable either way:

    V+S ~= SIGN >> VERDICT   almost all the loss is `inconclusive` erasing
                             direction
    V+S >  SIGN >> VERDICT   the sign is lost AND the significance flag
                             still carries something of its own
    V+S <  VERDICT           not a result. The measurement code is wrong,
                             and that is F24.

Projectively consistent smoothing (F23, strengthened)
-----------------------------------------------------
F23 found that a fixed per-state Dirichlet alpha penalises the richer
channel, because `n_state * alpha` of pseudo-mass gets added. The repair
`alpha / n_state` is right only for uniform refinements. The general
property, which follows from the Dirichlet aggregation rule, is:

> **The smoothing prior must commute with the refinement map: aggregating
> the fine channel's prior must reproduce the coarse channel's prior
> exactly.**

Here that is enforced structurally rather than checked. One prior is placed
on the finest channel in the family and every coarser prior is *derived* by
summing over the aggregation map — so the priors cannot disagree, whether or
not the refinement is uniform. `--audit-prior` prints the derivation.

    python marketing_experimentation/scripts/nested_channel_gate.py
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import budget_problem  # noqa: E402
from signed_verdict import load, verdict_index  # noqa: E402
from continuous_finding_a import build_prior, evsi_and_contributions  # noqa: E402
from m9a_break_even import REFERENCE_SPEND  # noqa: E402
from channel_ladder import q_on_grid_k  # noqa: E402

#: The finest channel. Index = 2*sign + significant, so:
FINE = ["inconclusive-negative", "significant-negative",
        "inconclusive-positive", "significant-positive"]

#: Every coarser channel as a map from fine state -> coarse state.
#: These ARE the refinement maps; the priors are derived through them.
MAPS = {
    "VERDICT+SIGN": [0, 1, 2, 3],          # identity
    "VERDICT":      [1, 0, 1, 2],          # inc-neg,inc-pos -> inconclusive
    "SIGN":         [0, 0, 1, 1],          # drop significance
    "BIT":          [0, 1, 0, 1],          # drop sign
}
#: Blackwell requirements: (finer, coarser) -- finer must not be worth less.
REQUIRED = [("VERDICT+SIGN", "VERDICT"), ("VERDICT+SIGN", "SIGN"),
            ("VERDICT+SIGN", "BIT"), ("VERDICT", "BIT")]


def derive_prior(alpha_total: float) -> dict[str, np.ndarray]:
    """One prior on the finest channel; the rest by aggregation.

    Uniform on the four fine states, then summed through each map. This is
    projective consistency by construction: no coarse prior is chosen, so
    none can disagree with the fine one.
    """
    fine = np.full(4, alpha_total / 4)
    out = {}
    for name, m in MAPS.items():
        a = np.zeros(max(m) + 1)
        for f, c in enumerate(m):
            a[c] += fine[f]
        out[name] = a
    return out


def q_draws(code: np.ndarray, world: np.ndarray, theta_ix: np.ndarray,
            alpha: np.ndarray, n_theta: int, n_draws: int,
            rng: np.random.Generator) -> np.ndarray:
    """Bootstrap over WORLDS (replications), not (scenario, iteration).

    M9-B cells share a latent world by replication, so cells are not
    independent clusters. Same discipline as channel_ladder.py.
    """
    ns = len(alpha)
    worlds = np.unique(world)
    oh = np.zeros((len(code), n_theta, ns))
    oh[np.arange(len(code)), theta_ix, code] = 1.0
    per_world = np.stack([oh[world == w].sum(axis=0) for w in worlds])
    w = rng.dirichlet(np.ones(len(worlds)), size=n_draws)
    counts = np.einsum("dc,cjk->djk", w, per_world) * len(worlds)
    return (counts + alpha) / (counts.sum(axis=2, keepdims=True) + alpha.sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="/tmp/m9b_cells")
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--alpha-total", type=float, nargs="*",
                    default=[0.5, 2.0, 8.0],
                    help="TOTAL pseudo-mass, held constant across the family")
    ap.add_argument("--audit-prior", action="store_true")
    a = ap.parse_args()

    if a.audit_prior:
        for at in a.alpha_total:
            pri = derive_prior(at)
            print(f"alpha_total = {at}")
            for name, v in pri.items():
                print(f"   {name:14s} {np.round(v,4)}  sum={v.sum():.4f}")
            print()
        return 0

    d = pd.concat([load(f) for f in sorted(glob.glob(f"{a.cells}/M9B_*.jsonl"))],
                  ignore_index=True)
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    tix = {t: i for i, t in enumerate(thetas)}
    d = d.assign(_ti=[tix[float(t)] for t in d.effect_pct],
                 _v=verdict_index(d))
    # fine code = 2*positive + significant
    d = d.assign(_fine=2 * (d.att_pct > 0).astype(int)
                 + (d._v != 1).astype(int))

    th, pr, _ = build_prior()
    problem = budget_problem(th, pr, spend=REFERENCE_SPEND)
    th16 = np.array(thetas)

    print("=" * 78)
    print("NESTED-CHANNEL GATE — a real Blackwell family")
    print("=" * 78)
    print(f"EVPI ceiling {100*problem.evpi()/REFERENCE_SPEND:.4f}%")
    print(f"clusters: {d.iteration.nunique()} replications (worlds); "
          f"{len(d):,} rows over {d.scenario.nunique()} cells")
    print("priors DERIVED from one prior on the 4-state finest channel, so "
          "they\ncommute with the refinement map by construction (F23)\n")

    order = ["BIT", "VERDICT", "SIGN", "VERDICT+SIGN"]
    for at in a.alpha_total:
        pri = derive_prior(at)
        print(f"--- total pseudo-mass {at} " + "-" * 46)
        print(f"   {'tool':18s} " + " ".join(f"{c:>15s}" for c in order))
        res = {}
        for tool, g in d.groupby("tool_label"):
            world = g.iteration.to_numpy(); ti = g._ti.to_numpy()
            row = {}
            for name in order:
                code = np.array(MAPS[name])[g._fine.to_numpy()]
                rng = np.random.default_rng(0)
                Q = q_draws(code, world, ti, pri[name], len(thetas),
                            a.draws, rng)
                ev = np.array([evsi_and_contributions(
                    problem, q_on_grid_k(Q[i], th16, th))[0]
                    for i in range(len(Q))]) / REFERENCE_SPEND
                row[name] = float(np.median(ev))
            res[tool] = row
            print(f"   {tool:18s} " +
                  " ".join(f"{100*row[c]:>14.4f}%" for c in order))

        print(f"\n   Blackwell (REQUIRED, not hoped for):")
        allok = True
        for tool, row in res.items():
            marks = []
            for fine, coarse in REQUIRED:
                ok = row[fine] >= row[coarse] - 1e-12
                allok &= ok
                marks.append(f"{fine[:3]}>={coarse[:3]} {'ok' if ok else 'FAIL'}")
            print(f"   {tool:18s} " + "  ".join(marks))
        print(f"   -> {'all hold' if allok else 'VIOLATION: this is F24, not a finding'}\n")

        print(f"   Interpretation, per tool:")
        for tool, row in res.items():
            v, s, vs = row["VERDICT"], row["SIGN"], row["VERDICT+SIGN"]
            gain_over_sign = vs - s
            if s > 3 * max(v, 1e-9):
                lead = "SIGN >> VERDICT"
            elif abs(s - v) < 0.1 * max(s, 1e-9):
                lead = "SIGN ~= VERDICT"
            else:
                lead = "SIGN > VERDICT"
            extra = ("significance adds little beyond sign"
                     if gain_over_sign < 0.1 * max(s, 1e-9)
                     else "significance adds materially beyond sign")
            print(f"   {tool:18s} {lead:16s}  V+S-SIGN = "
                  f"{100*gain_over_sign:+.4f}pp  ({extra})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
