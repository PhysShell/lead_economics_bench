#!/usr/bin/env python
"""Kill-gate: does a richer channel actually carry more DECISION value?

The question
------------
GeoLift's raw output tracks truth about as well as every other tool
(within-cell Spearman 0.71) while its VERDICT tracks it at 0.17. That is
strong evidence of a compression bottleneck — but rank correlation is not
decision value, and wide intervals могут be an honest report of uncertainty
rather than a lossy interface. Those are different stories and the cheap
test distinguishes them.

So: give the SAME downstream decision framework progressively richer
channels and measure `r_EVSI` for each.

    A  BIT              unsigned significance                    2 states
    B  VERDICT          signed neg / inconclusive / pos          3 states
    C  SIGN             sign of the point estimate alone         2 states
    D  POINT            signed point estimate, quantile-binned   K states
    E  POINT+CI         D crossed with a CI-width tercile        3K states

**Kill criterion, written before looking:** if D and E give only a small
increment over A/B, the "GeoLift is limited by its verdict representation"
hypothesis is dead — rho = 0.69 was an interesting correlation carrying no
decision-relevant information, and GeoLift is not investigated further.

If instead EVSI(rich) >> EVSI(verdict), the loss is localised between
estimator output and exposed verdict, and the step-by-step increments
decompose it:

    A -> B   the missing sign
    B -> C   the significance threshold discarding direction
    C -> D   magnitude beyond sign
    D -> E   uncertainty itself carrying decision-relevant information
    D ~= E   the CI buys nothing despite the ceremony around it

Three things this is careful about
----------------------------------
**1. No density estimation.** Continuous channels are DISCRETISED and fed
through the same count-based Dirichlet machinery as the verdict. Density
estimation has been the binding uncertainty twice in this project. The price
is that discretisation *loses* information, so EVSI(D) and EVSI(E) are
**lower bounds** on what those channels are worth. For a kill-gate that is
the safe direction: a lower bound that is already large settles it.

**2. The cluster is the WORLD, not (scenario, iteration).** Pooling cells is
what makes the counts dense enough for a 3K-state channel, but M9-B's cells
SHARE a latent world by replication — `(T15_G05, it=7)` and `(T42_G40, it=7)`
are the same world sliced twice. Treating them as independent clusters would
be F16 exactly. The bootstrap therefore resamples the 25 replications, each
carrying its whole (cell x theta) block.

**3. Bins are theta-independent.** Quantile edges come from the pooled
estimate distribution for that tool, never from the truth. A decision-maker
sees an estimate and applies a fixed rule.

    python marketing_experimentation/scripts/channel_ladder.py
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
from signed_verdict import ALPHA, load, verdict_index  # noqa: E402
from continuous_finding_a import (  # noqa: E402
    build_prior, evsi_and_contributions,
)
from m9a_break_even import REFERENCE_SPEND  # noqa: E402

CHANNELS = ("A_BIT", "B_VERDICT", "C_SIGN", "D_POINT", "E_POINT_CI")


def q_on_grid_k(q16: np.ndarray, th16: np.ndarray,
                grid: np.ndarray) -> np.ndarray:
    """K-state generalisation of `q_on_grid`.

    `continuous_finding_a.q_on_grid` interpolates the three-state verdict
    against its `inconclusive` baseline and is hardcoded to that shape. The
    scheme generalises unchanged: interpolate log(q_k / q_base) linearly in
    theta and softmax back, which keeps every prediction inside the simplex
    where interpolating probabilities directly would not.

    The baseline is the most populated state overall, chosen for numerical
    stability rather than meaning — the result is invariant to that choice
    up to floating point.
    """
    base = int(np.argmax(q16.sum(axis=0)))
    others = [k for k in range(q16.shape[1]) if k != base]
    eta = np.log(q16[:, others] / q16[:, [base]])
    out = np.empty((len(grid), q16.shape[1]))
    for i, t in enumerate(grid):
        pred = np.array([np.interp(t, th16, eta[:, j])
                         for j in range(len(others))])
        e = np.empty(q16.shape[1])
        e[base] = 1.0
        e[others] = np.exp(pred)
        out[i] = e / e.sum()
    return out


def encode(d: pd.DataFrame, k_bins: int) -> dict[str, tuple[np.ndarray, int]]:
    """Channel codes per row, plus each channel's state count."""
    v = verdict_index(d)
    att = d.att_pct.to_numpy(dtype=float)
    width = (d.ci_upper - d.ci_lower).to_numpy(dtype=float)

    # theta-independent quantile edges from the tool's own estimate spread
    qs = np.quantile(att, np.linspace(0, 1, k_bins + 1)[1:-1])
    point = np.searchsorted(qs, att)
    wq = np.quantile(width, [1 / 3, 2 / 3])
    wbin = np.searchsorted(wq, width)

    return {
        "A_BIT":       ((v != 1).astype(int), 2),
        "B_VERDICT":   (v, 3),
        "C_SIGN":      ((att > 0).astype(int), 2),
        "D_POINT":     (point, k_bins),
        "E_POINT_CI":  (point * 3 + wbin, k_bins * 3),
    }


def q_draws(code: np.ndarray, world: np.ndarray, theta_ix: np.ndarray,
            n_state: int, n_theta: int, alpha: float, n_draws: int,
            rng: np.random.Generator) -> np.ndarray:
    """(draws, theta, state) channel matrices, bootstrapping over WORLDS.

    One Dirichlet weight per replication, applied to that replication's
    entire block across every cell and truth — the CRN structure M9-B's
    world contract guarantees.
    """
    worlds = np.unique(world)
    oh = np.zeros((len(code), n_theta, n_state))
    oh[np.arange(len(code)), theta_ix, code] = 1.0
    per_world = np.stack([oh[world == w].sum(axis=0) for w in worlds])
    w = rng.dirichlet(np.ones(len(worlds)), size=n_draws)
    counts = np.einsum("dc,cjk->djk", w, per_world) * len(worlds)
    return (counts + alpha) / (counts.sum(axis=2, keepdims=True)
                               + n_state * alpha)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="/tmp/m9b_cells")
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--bins", type=int, nargs="*", default=[4, 8, 16])
    ap.add_argument("--alphas", type=float, nargs="*", default=[ALPHA])
    a = ap.parse_args()

    d = pd.concat([load(f) for f in sorted(glob.glob(f"{a.cells}/M9B_*.jsonl"))],
                  ignore_index=True)
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    th_ix = {t: i for i, t in enumerate(thetas)}
    d = d.assign(_ti=[th_ix[float(t)] for t in d.effect_pct])

    th, pr, _ = build_prior()
    problem = budget_problem(th, pr, spend=REFERENCE_SPEND)
    th16 = np.array(thetas)
    evpi = problem.evpi() / REFERENCE_SPEND

    print("=" * 78)
    print("CHANNEL LADDER — does a richer channel carry more DECISION value?")
    print("=" * 78)
    print(f"EVPI ceiling {100*evpi:.4f}% of governed spend")
    print(f"clusters: the {d.iteration.nunique()} REPLICATIONS (worlds), not "
          f"(scenario, iteration) — M9-B cells share a world by replication")
    print(f"rows: {len(d):,} pooled over {d.scenario.nunique()} cells; "
          f"{a.draws} bootstrap draws")
    print("D and E are DISCRETISED, so their EVSI is a LOWER BOUND\n")

    for k in a.bins:
        for alpha in a.alphas:
            print(f"--- K={k} bins, alpha={alpha} " + "-" * 44)
            print(f"   {'tool':18s} " +
                  " ".join(f"{c.split('_',1)[1][:9]:>10s}" for c in CHANNELS))
            res = {}
            for tool, g in d.groupby("tool_label"):
                enc = encode(g, k)
                world = g.iteration.to_numpy()
                ti = g._ti.to_numpy()
                row = []
                for ch in CHANNELS:
                    code, ns = enc[ch]
                    rng = np.random.default_rng(0)
                    Q = q_draws(code, world, ti, ns, len(thetas), alpha,
                                a.draws, rng)
                    ev = np.array([
                        evsi_and_contributions(problem, q_on_grid_k(Q[i], th16, th))[0]
                        for i in range(len(Q))]) / REFERENCE_SPEND
                    row.append(float(np.median(ev)))
                res[tool] = row
                print(f"   {tool:18s} " +
                      " ".join(f"{100*x:>9.4f}%" for x in row))

            print(f"\n   Blackwell self-test (a garbling cannot gain):")
            for tool, row in res.items():
                ab = row[1] >= row[0] - 1e-9        # BIT is a garbling of VERDICT
                dc = row[3] >= row[2] - 1e-9        # SIGN is a garbling of POINT
                ed = row[4] >= row[3] - 1e-9        # POINT is a garbling of POINT+CI
                print(f"   {tool:18s} VERDICT>=BIT {'ok' if ab else 'FAIL'}   "
                      f"POINT>=SIGN {'ok' if dc else 'FAIL'}   "
                      f"POINT+CI>=POINT {'ok' if ed else 'FAIL'}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
