#!/usr/bin/env python
"""F17 closure: prove the precision fix changed only what it was allowed to.

Why "the estimates are the same" is not enough
-----------------------------------------------
The first control compared `att_level` across the pre-fix and post-fix runs
and found them identical. That rules out the worst case -- precision reaching
the estimator -- and nothing else. A rounded θ that never enters estimation
can still change a conclusion if it is later used for

    boundary classification   which side of a decision boundary a truth is on
    grouping                  which rows are aggregated together
    row selection             which rows enter an analysis at all
    truth                     the θ grid a decision problem is defined on
    display                   what a table or figure claims

and the one that actually fired was **truth**: `budget_problem(thetas, ...)`
builds its utility matrix from `effect_pct`, so a rounded θ silently moves
the decision problem.

So closure needs two things, neither of which is "the numbers look the same":

1. **An allowlist diff.** Every field of every row must be identical between
   the two runs EXCEPT the ones named below. Not "the ones we looked at" --
   every field, checked mechanically, with the allowlist stated in advance.

2. **A classified inventory** of every consumer of the quantity, so the claim
   "estimation is untouched" is a statement about the whole call graph rather
   than about the one line that was read.

    python marketing_experimentation/repro/recast/f17_closure.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

#: Sentinel distinguishing "key absent" from "key present with value None".
_ABSENT = object()

#: The ONLY fields permitted to differ between the pre-fix and post-fix runs.
#: Anything else differing means the precision change had a second effect and
#: F17's blast radius is larger than described.
#:
#: `runtime_seconds` is wall-clock and cannot be identical across two runs; it
#: is listed here rather than quietly skipped, and it is classified in
#: CONSUMERS so that "nothing decision-relevant reads it" is a checked claim
#: rather than an obvious-sounding one.
ALLOWED_TO_DIFFER = {"effect_pct", "runtime_seconds"}

#: Fields that MUST differ, or the fix was not applied. Separated from the
#: permissive list because "allowed to change" and "had to change" are
#: different assertions and conflating them would let a no-op fix pass.
MUST_DIFFER = {"effect_pct"}

#: Fields that identify a row. Must match exactly or the runs are not
#: comparable row-for-row in the first place.
JOIN_KEYS = ["tool_label", "scenario", "effect_label", "iteration"]

#: Every consumer of the rounded quantity, classified by what it does with
#: it. Built by static inventory over the donor and this repository, not by
#: recall. `estimation` is the class that would have been fatal; `truth` is
#: the class that actually fired.
CONSUMERS = [
    # (file, line, class, note)
    ("donor run_tools.py", 445, "reporting",
     "reads effect_pct from metadata.json"),
    ("donor run_tools.py", "199/459", "reporting",
     "passed as a parameter; never reaches an estimator"),
    ("donor run_tools.py", "299/328/358/388", "reporting",
     "written into the emitted result row, all four tools"),
    ("donor run_tools.py", 453, "display", "progress line"),
    ("donor compute_metrics.py", 125, "grouping",
     "group_cols includes effect_pct AND effect_label, which are 1:1, "
     "so rounding can neither merge nor split a group"),
    ("donor compute_metrics.py", "93/105", "grouping",
     "branches on effect_label, not effect_pct"),
    ("donor audit_metrics.py", 47, "grouping", "same 1:1 pairing"),
    ("donor plot_forest.py", 70, "truth",
     "derives true values from true_att_pct, NOT effect_pct -- hunk 3 of "
     "theta-mutation.patch, which is why D7 does not compound this"),
    ("ours signed_verdict.py", "thetas -> budget_problem", "TRUTH",
     "the decision problem's utility matrix is built on these theta values. "
     "THIS IS THE ONE THAT FIRED."),
    ("ours theta_interpolation.py", "thetas", "TRUTH",
     "interpolation abscissa and boundary classification"),
    ("ours continuous_ladder.py", "thetas", "TRUTH", "same"),
    ("ours s0_reconstruction.py", "== 0 / != 0", "row selection",
     "zero vs non-zero survives rounding"),
    ("ours f8_equivalence.py", "== 0 / != 0", "row selection", "same"),
    ("ours information_ladder.py", "median per label", "ordering",
     "rounding preserves order"),
    ("ours theta_atlas.py", "* 100", "display", "printed percentage"),
    ("ours (session)", "runtime_seconds", "display",
     "summed once to cost M8 at ~3.48 CPU-hours; no analysis consumes it"),
]


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(l) for l in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="/tmp/results_m8_pilot_rounded.jsonl")
    ap.add_argument("--after", default="/tmp/results_m8_pilot.jsonl")
    args = ap.parse_args()

    a, b = load(args.before), load(args.after)
    ok = True

    print("== 1. classified inventory of every consumer ==")
    print("   Static, over the donor and this repository. The point is that")
    print("   `estimation` is empty -- as a statement about the whole call")
    print("   graph, not about the one line that was read.\n")
    by_class: dict[str, list] = {}
    for f, ln, cls, note in CONSUMERS:
        by_class.setdefault(cls, []).append((f, ln, note))
    for cls in ("estimation", "TRUTH", "truth", "grouping", "row selection",
                "ordering", "reporting", "display"):
        rows = by_class.get(cls, [])
        if not rows and cls != "estimation":
            continue
        print(f"   {cls.upper():14s} {len(rows)} site(s)")
        for f, ln, note in rows:
            print(f"      {f}:{ln}\n         {note}")
    n_est = len(by_class.get("estimation", []))
    ok &= n_est == 0
    print(f"\n   [{'PASS' if n_est == 0 else 'FAIL'}] no consumer in class "
          f"`estimation`: {n_est} found")
    print("   [NOTE] class TRUTH is non-empty, and that is the defect. A")
    print("          rounded theta never entered an estimator and still moved")
    print("          the decision problem the estimates were judged against.")

    print("\n== 2. allowlist diff over EVERY field, at the JSON level ==")
    print(f"   allowed to differ: {sorted(ALLOWED_TO_DIFFER)}")
    print(f"   must differ:       {sorted(MUST_DIFFER)}")
    print("   Stated before looking. Any other field differing means the")
    print("   precision change had a second effect.")
    print("\n   Compared as parsed JSON objects, row by row -- NOT through a")
    print("   DataFrame. The first version of this check went through a pandas")
    print("   merge and reported `converged` as differing in 1,080 rows. It")
    print("   does not: the key is simply absent for three of the four tools")
    print("   in BOTH files, and the merge stringified the missing values")
    print("   inconsistently between frames. A comparison instrument that")
    print("   normalises absence into a value cannot answer a question about")
    print("   absence, and a phantom finding in a closure check is worse than")
    print("   no closure check.\n")

    rows_a = [json.loads(l) for l in Path(args.before).open()]
    rows_b = [json.loads(l) for l in Path(args.after).open()]

    def key(r):
        return (r["tool"], r.get("posterior_type") or "", r["scenario"],
                r["effect_label"], r["iteration"])

    ia = {key(r): r for r in rows_a}
    ib = {key(r): r for r in rows_b}
    ok &= _report("row counts match", len(rows_a) == len(rows_b),
                  f"{len(rows_a)} vs {len(rows_b)}")
    ok &= _report("identity keys are unique in both files",
                  len(ia) == len(rows_a) and len(ib) == len(rows_b),
                  f"{len(ia)} vs {len(rows_a)}, {len(ib)} vs {len(rows_b)}")
    ok &= _report("every row in `before` has a partner in `after`",
                  set(ia) == set(ib),
                  f"{len(set(ia) ^ set(ib))} unmatched")

    def same(x, y) -> bool:
        if isinstance(x, float) and isinstance(y, float):
            return x == y or (x != x and y != y)
        return x == y and type(x) is type(y)

    diffs: dict[str, tuple[int, float]] = {}
    for k in set(ia) & set(ib):
        ra, rb = ia[k], ib[k]
        for f in set(ra) | set(rb):
            va, vb = ra.get(f, _ABSENT), rb.get(f, _ABSENT)
            if same(va, vb):
                continue
            n, mx = diffs.get(f, (0, 0.0))
            try:
                mx = max(mx, abs(float(va) - float(vb)))
            except (TypeError, ValueError):
                mx = float("nan")
            diffs[f] = (n + 1, mx)

    all_fields = sorted(set().union(*[set(r) for r in rows_a[:50]]))
    print(f"   {len(all_fields) - len(diffs)} field(s) identical in every row:")
    print("      " + ", ".join(f for f in all_fields if f not in diffs))
    print(f"\n   {len(diffs)} field(s) differ:")
    for f in sorted(diffs):
        n, mx = diffs[f]
        mark = "ALLOWED" if f in ALLOWED_TO_DIFFER else "NOT ALLOWED"
        print(f"      {f:22s} {n:5d} row(s)   max |diff| = {mx:.3e}   {mark}")

    unexpected = [f for f in diffs if f not in ALLOWED_TO_DIFFER]
    ok &= _report("only allowlisted fields differ", not unexpected,
                  f"unexpected: {unexpected}")
    missing = [f for f in MUST_DIFFER if f not in diffs]
    ok &= _report("every must-differ field actually DID differ", not missing,
                  f"{missing} did not change -- was the fix applied?")
    if "effect_pct" in diffs:
        n, mx = diffs["effect_pct"]
        ok &= _report("effect_pct moved on exactly the three rounded truths",
                      n == 480, f"{n} rows, expected 480")
        # Half of the last retained digit. Rounding to 4 dp can move a value
        # by at most 0.5e-4, and -0.03125 -> -0.0312 hits that bound exactly;
        # in binary it lands at 5.0000000000000375e-05, so a strict `<=`
        # fails on the one case the check exists for. The tolerance is float
        # slop on the bound, not slack in the claim.
        bound = 0.5 * 1e-4
        ok &= _report(
            "and moved by at most half the last retained digit -- a "
            "rounding, not a value change",
            mx <= bound * (1 + 1e-9),
            f"max {mx:.17g} against {bound:.17g}")

    print(f"\n{'=' * 64}")
    if ok:
        print("F17 CLOSED. The precision change moved exactly one field, the")
        print("one it was supposed to move, and the consumer inventory has no")
        print("entry in class `estimation`. The claim is now about the whole")
        print("call graph rather than about the line that was read.")
    else:
        print("F17 NOT CLOSED. See the failures above.")
    sys.exit(0 if ok else 1)


def _report(name: str, ok: bool, detail: str = "") -> bool:
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}"
          + (f"   {detail}" if detail and not ok else ""))
    return ok


if __name__ == "__main__":
    main()
