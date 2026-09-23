#!/usr/bin/env python
"""Refuse to extend the run unless exactly one thing changed since the freeze.

Why this exists rather than a note in a document
-------------------------------------------------
The premature 25-iteration launch in this session did not happen because the
protocol was unclear. It happened because the protocol lived in a
conversation and the runner did not read it. A rule that only a human
enforces is a rule that fails on the day the human is confident.

So the extension is gated by code. Before a single panel is generated, this
compares the current state against the frozen manifest and requires

    changed_fields == {"iterations"}

plus the fields explicitly classified below as non-semantic. Anything else --
a touched patch, an edited generator, a different donor commit, a modified
theta grid, a changed boundary definition, a moved gate threshold -- and it
refuses.

What counts as non-semantic, stated in advance
-----------------------------------------------
Output paths and run identifiers change by construction on every run and
carry no scientific content. They are listed here, once, rather than waved
past at the point of comparison -- which is where "just this one field" gets
decided badly.

    python marketing_experimentation/repro/recast/extend_from_freeze.py \\
        --freeze marketing_experimentation/docs/m8-pilot-freeze.json \\
        --iterations 25
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from leadbench_mx.canonical import (  # noqa: E402
    CANONICAL_THETA_M8, canon_str,
)
from leadbench_mx.decision import action_boundaries  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
DONOR = Path("/home/user/donor-smoke")
PATCHES = ["theta-mutation.patch", "m8-seed-log.patch"]

#: Fields that change on every run by construction and carry no scientific
#: content. Named in advance so the decision is not made at the moment of
#: temptation.
NON_SEMANTIC = {
    "frozen_at", "runtime_seconds", "output_path", "run_id",
    "tree_clean_at_generation", "analysis_commit", "analysis_commit_subject",
}

#: The single permitted semantic change.
PERMITTED = {"iterations"}


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str, cwd: Path = REPO) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"<unavailable: {e}>"


def current_state(iterations: int) -> dict:
    return {
        "donor.base_commit": git("rev-parse", "HEAD", cwd=DONOR),
        **{f"donor.patch.{p}": sha256(Path(__file__).resolve().parent / p)
           for p in PATCHES},
        "donor.file.generate_panels.R":
            sha256(DONOR / "src/R/generate_panels.R"),
        "donor.file.run_tools.py": sha256(DONOR / "src/python/run_tools.py"),
        "design.theta_grid_new": [canon_str(t) for t in CANONICAL_THETA_M8],
        "design.action_boundaries": [canon_str(x) for x in action_boundaries()],
        "design.cluster_definition": ["scenario", "iteration"],
        "design.gate_threshold_percentile": 95,
        "iterations": iterations,
    }


def frozen_state(fz: dict) -> dict:
    d = fz["donor"]
    g = fz["design"]
    return {
        "donor.base_commit": d["base_commit"],
        **{f"donor.patch.{k}": v for k, v in d["patches"].items()},
        "donor.file.generate_panels.R":
            d["patched_files_sha256"]["src/R/generate_panels.R"],
        "donor.file.run_tools.py":
            d["patched_files_sha256"]["src/python/run_tools.py"],
        "design.theta_grid_new": [canon_str(t) for t in g["theta_grid_new"]],
        "design.action_boundaries":
            [canon_str(x) for x in g["action_boundaries"]],
        "design.cluster_definition": g["cluster_definition"],
        "design.gate_threshold_percentile": g["gate_threshold_percentile"],
        "iterations": 10,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", default=str(
        REPO / "marketing_experimentation/docs/m8-pilot-freeze.json"))
    ap.add_argument("--iterations", type=int, required=True)
    args = ap.parse_args()

    fz = json.loads(Path(args.freeze).read_text())

    # The pointer and the artifact must name the same analysis commit. They
    # drifted once already: freeze_pilot.py regenerates on every invocation,
    # and running it inside an unrelated commit moved the artifact while the
    # pointer stayed behind. A freeze that moves is not a freeze, and a
    # pointer that disagrees with what it points at is worse than no pointer.
    ptr_path = Path(args.freeze).with_suffix(".commit")
    if ptr_path.exists():
        ptr = json.loads(ptr_path.read_text())
        if ptr.get("analysis_commit") != fz["code"]["analysis_commit"]:
            print("   REFUSE_EXTENSION_FROM_FREEZE")
            print(f"   pointer names analysis_commit "
                  f"{ptr.get('analysis_commit', '?')[:12]}")
            print(f"   artifact names analysis_commit "
                  f"{fz['code']['analysis_commit'][:12]}")
            print("   The freeze moved after the pointer was written. "
                  "Regenerate\n   the freeze and rewrite the pointer, in that "
                  "order, before\n   extending anything.")
            sys.exit(1)

    was, now = frozen_state(fz), current_state(args.iterations)

    print("== extension gate: what changed since the freeze? ==")
    print(f"   freeze: {args.freeze}")
    print(f"   analysis commit frozen: {fz['code']['analysis_commit'][:12]}")
    print(f"   permitted semantic change: {sorted(PERMITTED)}")
    print(f"   declared non-semantic:     {sorted(NON_SEMANTIC)}\n")

    changed = sorted(k for k in set(was) | set(now)
                     if was.get(k, "<absent>") != now.get(k, "<absent>"))
    for k in sorted(set(was) | set(now)):
        mark = "CHANGED" if k in changed else "same"
        if k in changed:
            print(f"   {mark:8s} {k}")
            print(f"            was: {was.get(k, '<absent>')}")
            print(f"            now: {now.get(k, '<absent>')}")
        else:
            print(f"   {mark:8s} {k}")

    semantic = [k for k in changed
                if k not in PERMITTED and k not in NON_SEMANTIC]
    print()
    if semantic:
        print("   REFUSE_EXTENSION_FROM_FREEZE")
        print(f"   {len(semantic)} unpermitted change(s): {semantic}")
        print("\n   This is not a refinement to wave through. Either revert")
        print("   to the frozen state, or take a NEW freeze and say in it")
        print("   what changed and why -- which makes the change visible to")
        print("   whoever reproduces this, instead of leaving them to")
        print("   discover it from a number that will not reconcile.")
        sys.exit(1)

    if "iterations" not in changed:
        print("   REFUSE_EXTENSION_FROM_FREEZE")
        print(f"   iterations is still {now['iterations']}; nothing to extend.")
        sys.exit(1)

    print("   EXTENSION PERMITTED")
    print(f"   iterations {was['iterations']} -> {now['iterations']}, and")
    print("   nothing else semantic moved. Every design field, every patch")
    print("   hash and both patched-file hashes match the freeze.")
    print("\n   Reminder carried from the freeze: the boundary gate's")
    print("   yardstick is sampling noise, which shrinks with cluster count.")
    print("   The n=10 PASS does not transfer. Re-run the gate at the new n")
    print("   before any continuous-prior EVSI is built.")
    sys.exit(0)


if __name__ == "__main__":
    main()
