#!/usr/bin/env python
"""Verify the world contract on the RUN THAT HAPPENED, not on a test of it.

Why this is separate from m9b_world_check.py
---------------------------------------------
`m9b_world_check.py` runs BEFORE the freeze. It generates its own small
cells and proves that the *generator* obeys the world contract. It says
nothing about the 25-replication, 16-cell run that was actually executed
days later across three worker trees, two rebalances and three container
restarts.

This script closes that gap. It reads the seed logs the run itself emitted
and checks the same invariants on them at full scale. A generator that
obeys the contract and a run that obeys it are two different claims, and
this project's whole method is refusing to let the first stand in for the
second (F11: two-lane isolation asserted, not verified).

Blinding
--------
It reads SEED LOGS only -- panel seeds, donor orderings, treated geo, world
shape. It never opens a results file, so it can be run at any point during
a run without touching the EVSI surface.

    python marketing_experimentation/repro/recast/m9b_run_invariants.py
"""

from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

EXPECT_WORLD = ("41", "132")     # geos, total days
EXPECT_REPLICATIONS = 25
EXPECT_ARMS = 16


def load(base: Path) -> dict[str, list[dict]]:
    cells = {}
    for p in sorted(base.glob("*.panel_seeds.csv")):
        with p.open() as f:
            cells[p.name.split(".")[0]] = list(csv.DictReader(f))
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="/tmp/m9b_cells")
    ap.add_argument("--expect-cells", type=int, default=16)
    a = ap.parse_args()

    cells = load(Path(a.cells))
    if not cells:
        raise SystemExit(f"no seed logs under {a.cells}")

    print("=" * 74)
    print("M9-B world contract, verified on the executed run")
    print("=" * 74)
    print(f"{len(cells)} cells: {', '.join(sorted(cells))}\n")

    ok = True

    # W7 -- one world per replication, across every cell
    worlds: dict = {}
    for c, rows in cells.items():
        for r in rows:
            worlds.setdefault(r["iteration"], {}).setdefault(
                (r["panel_seed"], r["donor_order"], r["treated_geo"]),
                set()).add(c)
    bad = [it for it, vs in worlds.items() if len(vs) != 1]
    ok &= not bad
    print(f"W7   one world per replication across all {len(cells)} cells "
          f"({len(worlds)*len(cells)*EXPECT_ARMS:,} panels): "
          f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

    # W3 -- pools are prefixes of the recorded permutation
    order = {it: next(iter(vs))[1].split("|") for it, vs in worlds.items()}
    bad = [f"it{it} {c}" for it in order for c in cells
           if next(r["cell_donors"] for r in cells[c]
                   if r["iteration"] == it).split("|")
           != order[it][:int(c.split("_G")[1])]]
    ok &= not bad
    print(f"W3   every pool is donor_order[:G_c]: "
          f"{'PASS' if not bad else 'FAIL ' + str(bad[:3])}")

    # W7b / W7c -- the world survives each axis independently
    key = lambda c: {(r["panel_seed"], r["donor_order"]) for r in cells[c]}
    for tag, sel in (
        ("W7b  matched G_c share a world across durations",
         lambda x, y: x.split("_G")[1] == y.split("_G")[1]),
        ("W7c  matched T share a world across pool sizes",
         lambda x, y: x.split("_T")[1][:2] == y.split("_T")[1][:2]),
    ):
        pr = [(x, y) for x, y in itertools.combinations(sorted(cells), 2)
              if sel(x, y)]
        bd = [(x, y) for x, y in pr if key(x) != key(y)]
        ok &= not bd
        print(f"{tag} ({len(pr)} pairs): "
              f"{'PASS' if not bd else 'FAIL ' + str(bd)}")

    # W7d -- the strongest form: one world set, full stop
    one = len({frozenset(key(c)) for c in cells}) == 1
    ok &= one
    print(f"W7d  all {len(cells)} cells share ONE identical world set: "
          f"{'PASS' if one else 'FAIL'}")

    # shape and completeness
    shapes = {(r["world_n_geos"], r["world_total_days"])
              for rr in cells.values() for r in rr}
    shape_ok = shapes == {EXPECT_WORLD}
    ok &= shape_ok
    print(f"W9   world shape is {EXPECT_WORLD[0]} geos x {EXPECT_WORLD[1]} "
          f"days everywhere: {'PASS' if shape_ok else 'FAIL ' + str(shapes)}")

    reps_ok = len(worlds) == EXPECT_REPLICATIONS
    cells_ok = len(cells) == a.expect_cells
    ok &= reps_ok and cells_ok
    print(f"W10  {len(worlds)} replications (expect {EXPECT_REPLICATIONS}) "
          f"and {len(cells)} cells (expect {a.expect_cells}): "
          f"{'PASS' if reps_ok and cells_ok else 'FAIL'}")

    tg = sorted({r["treated_geo"] for rr in cells.values() for r in rr})
    perms = len({"|".join(order[i]) for i in order})
    print(f"\n[desc] treated geo everywhere: {tg}")
    print(f"[desc] distinct donor permutations: {perms} over {len(worlds)} "
          f"replications -- the pool composition moves ACROSS replications "
          f"while nesting WITHIN one, which is the declared design")

    print("\n" + "=" * 74)
    print("ALL WORLD-CONTRACT INVARIANTS HOLD ON THE EXECUTED RUN" if ok
          else "CONTRACT VIOLATED ON THE EXECUTED RUN -- do not analyse")
    print("=" * 74)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
