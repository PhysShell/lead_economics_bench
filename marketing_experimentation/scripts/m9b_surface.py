#!/usr/bin/env python
"""M9-B: what is a longer test, or a bigger donor pool, worth?

The estimand
------------
    r_EVSI(T, G_c) = EVSI(T, G_c) / S_governed

the share of governed spend a signed-verdict experiment is worth, per
decision, as a function of test duration and donor pool size. M9-A priced
the information at one design point; this asks what the design axes buy.

Why this is a comparison and not four unrelated numbers
-------------------------------------------------------
Each of the 16 cells is a SLICE OF THE SAME maximal latent world: same
treated geo, same donor ordering, same panel seeds, same 25 replications.
So a paired difference between cells reflects the changed design factor and
not two independent Monte Carlo draws. Under the donor's own knobs it would
have carried a change of world as well -- see docs/m9-preregistration.md,
M9-B Addendum 1, and F20.

That is also why every difference here is computed PAIRED, cluster by
cluster, rather than as a difference of independently bootstrapped margins.
Throwing away the pairing would discard exactly the variance reduction the
world contract was built to create.

Rates, not dollars
------------------
Utility is exactly linear in spend (verified in m9a_break_even.py to 6.9e-18
over six decades), so a dollar figure is a statement about the budget it was
computed at. The transportable quantity is the rate.

Monotonicity is DESCRIPTIVE
---------------------------
m9b-freeze.json fixes this before any cell was run: no acceptance threshold
is attached to monotonicity in T or G_c, and none is invented after seeing
the surface. More data can improve the experiment while an estimator's own
calibration moves differently.

    python marketing_experimentation/scripts/m9b_surface.py
"""

from __future__ import annotations

import argparse
import json
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
from m9a_break_even import REFERENCE_SPEND  # noqa: E402

POST_DAYS = (15, 21, 28, 42)
N_CONTROL = (5, 9, 20, 40)
CELLS = [f"M9B_T{t:02d}_G{g:02d}" for t in POST_DAYS for g in N_CONTROL]
EXPECT_ITERATIONS = range(1, 26)
EXPECT_ROWS = 16 * 25 * 4   # truths x iterations x tools



def check_seal(base: Path) -> tuple[list[str], bool]:
    """Is the surface readable yet?

    NOT a file-existence test. All 16 cell files existed, with 800 rows and
    two dead tools, for the entire duration of the R-tool re-run -- so a
    presence check would have unsealed the surface on half-empty data. It
    asks the question the blinding rule actually asks: is every cell
    complete, with every tool having produced estimates?

    Reads `att_pct` for PRESENCE only. No value is compared, ordered or
    summarised, so this does not itself read the surface.
    """
    lines, bad = [], []
    for c in CELLS:
        f = base / f"{c}.jsonl"
        if not f.exists():
            bad.append(f"{c}: absent")
            continue
        n, usable = 0, {}
        with f.open() as fh:
            for line in fh:
                r = json.loads(line)
                n += 1
                t = r["tool"] + (f"[{r['posterior_type']}]"
                                 if r.get("posterior_type") else "")
                e = usable.setdefault(t, [0, 0])
                e[0] += 1
                if r.get("att_pct") is not None:
                    e[1] += 1
        dead = sorted(t for t, (_, u) in usable.items() if u == 0)
        if n != EXPECT_ROWS or dead:
            bad.append(f"{c}: {n:,} rows"
                       + (f", 0 estimates from {dead}" if dead else ""))
    lines.append(f"seal check : {len(CELLS) - len(bad)}/{len(CELLS)} cells "
                 f"complete ({EXPECT_ROWS:,} rows, every tool producing)")
    for b in bad[:20]:
        lines.append(f"             {b}")
    return lines, bool(bad)


def pct(x: float) -> str:
    return f"{100*x:.4f}%"


def cell_draws(path: Path, tool: str, problem, th_prior, n_draws: int,
               alpha: float, seed: int = 0):
    """Bootstrap draws of r_EVSI for VERDICT and BIT, for one (cell, tool).

    The RNG seed is shared across cells on purpose: the same Dirichlet
    weights fall on the same replication index everywhere, so a paired
    difference between two cells is a difference between two designs
    evaluated on the same resampled worlds.
    """
    d = load(str(path))
    d = d[np.isfinite(d[["att_pct", "ci_lower", "ci_upper"]]
                      .to_numpy(dtype=float)).all(axis=1) & d.significant.notna()]
    if d.empty:
        raise SystemExit(f"{path.name}: no finite rows. If a whole tool is "
                         f"missing this is F21 again -- check the usable-row "
                         f"gate before trusting anything downstream.")
    d = d.assign(_verdict=verdict_index(d))
    thetas = sorted(float(t) for t in d.effect_pct.unique())
    d = require_complete_clusters(d, thetas, expect_iterations=EXPECT_ITERATIONS)
    g = d[d.tool_label == tool]
    if g.empty:
        return None, None, thetas
    V, _ = verdict_matrix(g, thetas)
    rng = np.random.default_rng(seed)
    draws = cluster_bootstrap_draws(V, alpha, n_draws, rng)
    th16 = np.array(thetas)
    v = np.empty(len(draws))
    b = np.empty(len(draws))
    for i in range(len(draws)):
        qg = q_on_grid(draws[i], th16, th_prior)
        v[i] = evsi_and_contributions(problem, qg)[0]
        b[i] = evsi_and_contributions(problem, qg @ GARBLE.T)[0]
    return v / REFERENCE_SPEND, b / REFERENCE_SPEND, thetas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="/tmp/m9b_cells")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--out", default=None, help="optional JSON dump")
    a = ap.parse_args()

    base = Path(a.cells)
    seal_report, sealed = check_seal(base)
    for line in seal_report:
        print(line)
    if sealed:
        raise SystemExit(
            "\nSEALED. The surface is not readable until all 16 cells are "
            "COMPLETE.\nA cell file existing is not a cell being finished: "
            "every one of the 16\nexisted with 800 rows through the whole "
            "R-tool re-run. Checking presence\ninstead of completeness is "
            "the defect F21 is about, and this seal had it.")
    print()

    th, pr, _kind = build_prior()
    problem = budget_problem(th, pr, spend=REFERENCE_SPEND)
    evpi_rate = problem.evpi() / REFERENCE_SPEND

    print("=" * 78)
    print("M9-B: the value of more information, as a rate")
    print("=" * 78)
    print(f"prior      : the conditioned documented spike-and-slab, atom kept")
    print(f"EVPI       : {pct(evpi_rate)} of governed spend (the ceiling)")
    print(f"draws      : {a.draws:,} cluster bootstrap, alpha={a.alpha}, "
          f"shared RNG seed across cells so differences stay PAIRED")
    print(f"unit       : share of governed spend, per decision, L=1\n")

    # discover tools from the first cell rather than hard-coding them
    d0 = load(str(base / f"{CELLS[0]}.jsonl"))
    tools = sorted(d0.tool_label.unique())
    print(f"tools      : {', '.join(tools)}\n")

    surf: dict = {t: {} for t in tools}
    for c in CELLS:
        for t in tools:
            v, b, _ = cell_draws(base / f"{c}.jsonl", t, problem, th,
                                 a.draws, a.alpha)
            if v is None:
                continue
            surf[t][c] = {"verdict": v, "bit": b, "gap": v - b}

    # -- 1. the surface, per tool ----------------------------------------
    for t in tools:
        print("=" * 78)
        print(f"{t}   r_EVSI(VERDICT), median of {a.draws:,} draws")
        hdr = "T \\ G_c"
        print(f"{hdr:>10s} " + " ".join(f"{g:>12d}" for g in N_CONTROL))
        for T in POST_DAYS:
            row = []
            for G in N_CONTROL:
                m = surf[t].get(f"M9B_T{T:02d}_G{G:02d}")
                row.append(pct(float(np.median(m["verdict"]))) if m else "--")
            print(f"{T:>10d} " + " ".join(f"{x:>12s}" for x in row))

    # -- 2. the marginal value of each axis, PAIRED ----------------------
    print("\n" + "=" * 78)
    print("marginal value of the axes, paired across the shared world")
    print("(a paired difference of bootstrap draws, not a difference of")
    print(" independently drawn margins -- the cells share replications)")
    for t in tools:
        print(f"\n{t}")
        print(f"   {'step':28s} {'delta r_EVSI':>14s} {'95% credible':>26s}")
        for T in POST_DAYS:
            for G0, G1 in zip(N_CONTROL, N_CONTROL[1:]):
                a0 = surf[t].get(f"M9B_T{T:02d}_G{G0:02d}")
                a1 = surf[t].get(f"M9B_T{T:02d}_G{G1:02d}")
                if not (a0 and a1):
                    continue
                dd = a1["verdict"] - a0["verdict"]
                lo, hi = np.quantile(dd, [.025, .975])
                est = "" if lo <= 0 <= hi else "  *"
                print(f"   T={T:<3} G_c {G0:>2d} -> {G1:<2d}{'':11s} "
                      f"{pct(float(np.median(dd))):>14s} "
                      f"{'[' + pct(lo) + ', ' + pct(hi) + ']':>26s}{est}")
        for G in N_CONTROL:
            for T0, T1 in zip(POST_DAYS, POST_DAYS[1:]):
                a0 = surf[t].get(f"M9B_T{T0:02d}_G{G:02d}")
                a1 = surf[t].get(f"M9B_T{T1:02d}_G{G:02d}")
                if not (a0 and a1):
                    continue
                dd = a1["verdict"] - a0["verdict"]
                lo, hi = np.quantile(dd, [.025, .975])
                est = "" if lo <= 0 <= hi else "  *"
                print(f"   G_c={G:<3} T {T0:>2d} -> {T1:<2d}{'':12s} "
                      f"{pct(float(np.median(dd))):>14s} "
                      f"{'[' + pct(lo) + ', ' + pct(hi) + ']':>26s}{est}")
        print("   * = the paired 95% interval excludes zero. NOT a "
              "significance test:\n     no alpha was preregistered for "
              "these steps and none is claimed.")

    # -- 3. monotonicity, descriptive ------------------------------------
    print("\n" + "=" * 78)
    print("monotonicity [DESCRIPTIVE -- no threshold, per m9b-freeze.json]")
    for t in tools:
        upG = dnG = upT = dnT = 0
        for T in POST_DAYS:
            for G0, G1 in zip(N_CONTROL, N_CONTROL[1:]):
                a0, a1 = surf[t].get(f"M9B_T{T:02d}_G{G0:02d}"), surf[t].get(f"M9B_T{T:02d}_G{G1:02d}")
                if a0 and a1:
                    m = float(np.median(a1["verdict"] - a0["verdict"]))
                    upG += m > 0; dnG += m < 0
        for G in N_CONTROL:
            for T0, T1 in zip(POST_DAYS, POST_DAYS[1:]):
                a0, a1 = surf[t].get(f"M9B_T{T0:02d}_G{G:02d}"), surf[t].get(f"M9B_T{T1:02d}_G{G:02d}")
                if a0 and a1:
                    m = float(np.median(a1["verdict"] - a0["verdict"]))
                    upT += m > 0; dnT += m < 0
        print(f"   {t:18s} G_c steps {upG:2d} up / {dnG:2d} down   "
              f"T steps {upT:2d} up / {dnT:2d} down")

    # -- 4. the sign loss across the surface -----------------------------
    print("\n" + "=" * 78)
    print("V - B: what the UNSIGNED bit throws away, at each corner")
    print(f"   {'tool':18s} {'cheapest cell':>16s} {'richest cell':>16s}")
    lo_c, hi_c = CELLS[0], CELLS[-1]
    for t in tools:
        a0, a1 = surf[t].get(lo_c), surf[t].get(hi_c)
        f = lambda m: pct(float(np.median(m["gap"]))) if m else "--"
        print(f"   {t:18s} {f(a0):>16s} {f(a1):>16s}")
    print(f"   ({lo_c} vs {hi_c})")

    if a.out:
        dump = {t: {c: {k: float(np.median(v)) for k, v in m.items()}
                    for c, m in surf[t].items()} for t in tools}
        Path(a.out).write_text(json.dumps(
            {"evpi_rate": evpi_rate, "reference_spend": REFERENCE_SPEND,
             "draws": a.draws, "alpha": a.alpha, "surface": dump},
            indent=2) + "\n")
        print(f"\nwrote {a.out}")

    print("\n" + "=" * 78)
    print("what this is NOT")
    print("  * not an ENBS: no cost model, deliberately (M9-A section 1)")
    print("  * not external validity: the DGP is synthetic and contains no")
    print("    spend, no budget and no intervention")
    print("  * not a claim that a cell equals the donor's A1 or A3: those")
    print("    draw 21 geos as 21, these draw 41 and slice")
    print("  * not a monotonicity finding: that column is descriptive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
