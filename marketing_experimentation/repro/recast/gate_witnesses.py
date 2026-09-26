#!/usr/bin/env python
"""Adversarial gate witnesses: inputs that pass the proxy and violate the invariant.

C12, in executable form.

The pattern behind F20, F21 and the M9-B blinding seal is one defect: a gate
validates a **proxy** for the property it guards, because the proxy is the
thing that happens to be visible where the gate is written. The proxy is
always the shortcut a developer will reach for. So the test is not a generic
negative case — it is a **counterexample built specifically against that
shortcut**:

    an artifact that satisfies EVERY cheap proxy signal
    and still violates the invariant,
    which the gate must reject.

Three witnesses, one per gate that shipped broken or nearly so:

    nesting        pools genuinely nest, D5 subset D9 subset D20 subset D40,
                   every recorded field consistent -- but the donor order is
                   the sorted geo index rather than a draw from the dedicated
                   substream. Defeats F20's suite; caught only by W3d, which
                   re-derives sample.int() from perm_seed in a separate R
                   process.

    completeness   exactly 1,600 rows, every key present, every JSON line
                   well-formed, `significant` populated -- but one tool's
                   `att_pct` is null throughout. Defeats F21's row-count
                   gate; caught only by counting USABLE rows per tool.

    seal           all 16 cell files present with the right names and the
                   right row counts -- but a slice of estimates is missing.
                   Defeats the blinding seal's file-existence check; caught
                   only by requiring completeness per cell and per tool.

Each witness is generated deterministically, so it is a fixture rather than
a captured accident, and each is asserted to pass its proxy before the gate
is asked to reject it. A witness that fails the proxy proves nothing: it
would be rejected by the cheap check too, and the point is that the cheap
check waves it through.

    python marketing_experimentation/repro/recast/gate_witnesses.py
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EXPECT_ROWS = 1600
CELLS = [f"M9B_T{t:02d}_G{g:02d}" for t in (15, 21, 28, 42)
         for g in (5, 9, 20, 40)]

SEED_FIELDS = ["scenario", "effect_label", "iteration", "effect_pct",
               "panel_seed", "noise_seed", "perm_seed", "world_n_geos",
               "world_total_days", "requested_post_days",
               "requested_n_control", "treated_geo", "donor_order",
               "cell_donors"]
THETAS = [-0.15, -0.10, -0.05, -0.03125, -0.02, -0.01, 0.0, 0.01,
          0.0125, 0.02, 0.05, 0.051875, 0.075, 0.10, 0.104375, 0.15]
TOOLS = [("causalpy", "y_hat"), ("google_mm", ""), ("geolift", ""),
         ("causalimpact", "")]


# ── witness 1: nesting holds, randomness does not ──────────────────────

def witness_sorted_donor_order(out: Path) -> Path:
    """Pools nest perfectly; the order is sorted, not drawn.

    This is exactly mutation M-c, frozen as a fixture so the property is
    guarded even if nobody re-runs the mutation script.
    """
    d = out / "nesting"
    d.mkdir(parents=True, exist_ok=True)
    treated = 21
    controls = [i for i in range(1, 42) if i != treated]   # SORTED, not shuffled
    order = "|".join(f"City {i}" for i in controls)
    for cell in CELLS:
        g = int(cell.split("_G")[1])
        t = int(cell.split("_T")[1][:2])
        rows = []
        for it in range(1, 26):
            ps = 42000 + 10000 + it
            for th in THETAS:
                rows.append({
                    "scenario": cell, "effect_label": f"e{th}", "iteration": it,
                    "effect_pct": th, "panel_seed": ps,
                    "noise_seed": ps + 100000, "perm_seed": ps + 900000,
                    "world_n_geos": 41, "world_total_days": 132,
                    "requested_post_days": t, "requested_n_control": g,
                    "treated_geo": f"City {treated}", "donor_order": order,
                    "cell_donors": "|".join(f"City {i}" for i in controls[:g]),
                })
        with (d / f"{cell}.panel_seeds.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, SEED_FIELDS)
            w.writeheader()
            w.writerows(rows)
    return d


# ── witness 2: 1,600 rows, one tool empty ──────────────────────────────

def witness_dead_tool(out: Path, dead: str = "geolift") -> Path:
    d = out / "completeness"
    d.mkdir(parents=True, exist_ok=True)
    cell = CELLS[0]
    with (d / f"{cell}.jsonl").open("w") as f:
        for it in range(1, 26):
            for th in THETAS:
                for tool, pt in TOOLS:
                    alive = tool != dead
                    f.write(json.dumps({
                        "scenario": cell, "effect_label": f"e{th}",
                        "effect_pct": th, "iteration": it, "tool": tool,
                        "posterior_type": pt,
                        "att_pct": 0.01 if alive else None,
                        "att_level": 1.0 if alive else None,
                        "ci_lower": 0.0 if alive else None,
                        "ci_upper": 0.02 if alive else None,
                        # populated either way -- this is the fabricated value
                        # that made the dead rows look like real findings
                        "significant": False,
                        "runtime_seconds": 1.0 if alive else 0,
                    }) + "\n")
    return d


# ── witness 3: 16 files, right row counts, estimates missing ───────────

def witness_hollow_seal(out: Path) -> Path:
    d = out / "seal"
    d.mkdir(parents=True, exist_ok=True)
    for i, cell in enumerate(CELLS):
        # every file present, every row count exactly right; in half the
        # cells two of four tools carry no estimate
        hollow = {"geolift", "causalimpact"} if i % 2 else set()
        with (d / f"{cell}.jsonl").open("w") as f:
            for it in range(1, 26):
                for th in THETAS:
                    for tool, pt in TOOLS:
                        alive = tool not in hollow
                        f.write(json.dumps({
                            "scenario": cell, "effect_label": f"e{th}",
                            "effect_pct": th, "iteration": it, "tool": tool,
                            "posterior_type": pt,
                            "att_pct": 0.01 if alive else None,
                            "ci_lower": 0.0 if alive else None,
                            "ci_upper": 0.02 if alive else None,
                            "significant": False,
                        }) + "\n")
    return d


# ── the proxies each witness must satisfy ──────────────────────────────

def proxy_nesting(d: Path) -> tuple[bool, str]:
    """The cheap signal F20's suite counted: do the pools nest?"""
    for cell in CELLS:
        rows = list(csv.DictReader((d / f"{cell}.panel_seeds.csv").open()))
        g = int(cell.split("_G")[1])
        for r in rows:
            if r["cell_donors"].split("|") != r["donor_order"].split("|")[:g]:
                return False, f"{cell}: pool is not the order's prefix"
    sets = {}
    for cell in CELLS[:4]:
        rows = list(csv.DictReader((d / f"{cell}.panel_seeds.csv").open()))
        sets[int(cell.split("_G")[1])] = set(rows[0]["cell_donors"].split("|"))
    for a, b in zip((5, 9, 20), (9, 20, 40)):
        if not sets[a] < sets[b]:
            return False, f"D{a} not a strict subset of D{b}"
    return True, "pools nest, every recorded field self-consistent"


def proxy_row_count(d: Path) -> tuple[bool, str]:
    """The cheap signal F21's gate counted: are there 1,600 well-formed rows?"""
    f = next(d.glob("*.jsonl"))
    n = 0
    for line in f.open():
        json.loads(line)          # every line parses
        n += 1
    return n == EXPECT_ROWS, f"{n:,} well-formed rows, every key present"


def proxy_files_exist(d: Path) -> tuple[bool, str]:
    """The cheap signal the seal counted: do all 16 cell files exist?"""
    missing = [c for c in CELLS if not (d / f"{c}.jsonl").exists()]
    counts = {sum(1 for _ in (d / f"{c}.jsonl").open()) for c in CELLS}
    return (not missing and counts == {EXPECT_ROWS},
            f"16/16 files present, all at {EXPECT_ROWS:,} rows")


# ── the gates, asked to reject ─────────────────────────────────────────

def gate_nesting(d: Path) -> tuple[bool, str]:
    """W3d: re-derive the permutation from perm_seed, outside the generator."""
    rows = list(csv.DictReader((d / f"{CELLS[0]}.panel_seeds.csv").open()))
    r = rows[0]
    ti = int(r["treated_geo"].split()[1])
    p = subprocess.run(
        ["/opt/R/4.5.1/bin/Rscript", "-e",
         f'set.seed({int(r["perm_seed"])}); '
         f'ci <- setdiff(seq_len({int(r["world_n_geos"])}), {ti}); '
         f'cat(paste("City", ci[sample.int(length(ci))]), sep="|")'],
        capture_output=True, text=True)
    if p.returncode != 0:
        return False, f"could not re-derive: {p.stderr[-200:]}"
    rederived = p.stdout.strip()
    if rederived != r["donor_order"]:
        k = next(i for i, (x, y) in enumerate(
            zip(rederived.split("|"), r["donor_order"].split("|"))) if x != y)
        return True, (f"REJECTED: donor order differs from sample.int at "
                      f"position {k} (re-derived {rederived.split('|')[k]}, "
                      f"recorded {r['donor_order'].split('|')[k]})")
    return False, "gate accepted a sorted donor order"


def gate_usable_rows(d: Path) -> tuple[bool, str]:
    f = next(d.glob("*.jsonl"))
    usable: dict = {}
    for line in f.open():
        r = json.loads(line)
        t = r["tool"] + (f"[{r['posterior_type']}]" if r.get("posterior_type") else "")
        e = usable.setdefault(t, [0, 0])
        e[0] += 1
        if r.get("att_pct") is not None:
            e[1] += 1
    dead = sorted(t for t, (_, u) in usable.items() if u == 0)
    return (bool(dead),
            f"REJECTED: {dead} produced 0 estimates in {EXPECT_ROWS:,} rows"
            if dead else "gate accepted a cell with a dead tool")


def gate_seal(d: Path) -> tuple[bool, str]:
    sys.path.insert(0, str(REPO / "marketing_experimentation/scripts"))
    from m9b_surface import check_seal          # the real seal, not a copy
    _lines, sealed = check_seal(d)
    return sealed, ("REJECTED: seal refused despite 16/16 files at the right "
                    "row count" if sealed else "seal accepted hollow cells")


WITNESSES = [
    ("nesting gate / F20", witness_sorted_donor_order, proxy_nesting,
     gate_nesting,
     "pools nest perfectly; donor order is the sorted geo index, not a draw"),
    ("completeness gate / F21", witness_dead_tool, proxy_row_count,
     gate_usable_rows,
     "1,600 well-formed rows; one tool's att_pct is null throughout"),
    ("blinding seal / F22c", witness_hollow_seal, proxy_files_exist,
     gate_seal,
     "16/16 files at the right row count; half have two tools with no estimates"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", default=None,
                    help="write the witnesses here instead of a temp dir")
    a = ap.parse_args()
    root = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="witness_"))
    root.mkdir(parents=True, exist_ok=True)

    print("=" * 76)
    print("ADVERSARIAL GATE WITNESSES (C12)")
    print("=" * 76)
    print("Each witness satisfies the cheap proxy the gate was tempted to")
    print("count, and violates the invariant the gate exists to protect.")
    print("Both halves are asserted: a witness that fails its own proxy")
    print("proves nothing, because the cheap check would have caught it.\n")

    ok = True
    for name, make, proxy, gate, what in WITNESSES:
        d = make(root)
        p_ok, p_msg = proxy(d)
        g_ok, g_msg = gate(d)
        ok &= p_ok and g_ok
        print(f"[{name}]")
        print(f"   witness      {what}")
        print(f"   proxy PASSES {'yes' if p_ok else 'NO -- witness is invalid'}"
              f"  ({p_msg})")
        print(f"   gate REJECTS {'yes' if g_ok else 'NO -- GATE IS BROKEN'}"
              f"  ({g_msg})")
        print()

    print("=" * 76)
    print("ALL GATES REJECT THEIR WITNESS" if ok
          else "A GATE ACCEPTED ITS WITNESS -- the invariant is unguarded")
    print("=" * 76)
    if a.keep:
        print(f"\nwitnesses kept under {root}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
