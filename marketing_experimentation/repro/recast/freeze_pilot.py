#!/usr/bin/env python
"""Freeze the accepted pilot state before the iteration count is changed.

Why a freeze artifact rather than a sentence
---------------------------------------------
"We only increased N" has a reliable habit of meaning, six months later, "we
increased N and also fixed three small things". The defence is not discipline;
it is a manifest written before the change, against which the next run can be
diffed mechanically.

This project has the specific version of that problem already: a `baseline`
that is one commit older than the safeguard it is supposed to contain would
reproduce a pilot with no CRN gate, and nobody would notice until the numbers
disagreed for a reason nobody could name.

What is recorded
----------------
    code        this repository's HEAD, and whether the tree is clean
    donor       the disposable clone's base commit plus the SHA-256 of every
                patch applied to it, since the clone is deliberately dirty
    generator   SHA-256 of the two donor files the patches touch, so a later
                edit cannot hide behind "the patch is the same"
    data        SHA-256 of the results file and the seed manifest
    tools       the resolved tool versions the run actually used
    design      the theta grid, the four action boundaries, the gate
                threshold, and the cluster definition
    result      the pilot acceptance verdict and the boundary gate verdict

and, explicitly, **the single change permitted after this point**.

    python marketing_experimentation/repro/recast/freeze_pilot.py \
        --out marketing_experimentation/docs/m8-pilot-freeze.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from leadbench_mx.decision import (  # noqa: E402
    DEFAULT_ACTIONS, DEFAULT_MULTIPLIERS, action_boundaries,
)

REPO = Path(__file__).resolve().parents[3]
DONOR = Path("/home/user/donor-smoke")
PATCHES = ["theta-mutation.patch", "m8-seed-log.patch"]

#: The one thing allowed to change between this freeze and the next run.
#: Anything else differing is a protocol violation, not a refinement.
PERMITTED_CHANGE = "n_iterations: 10 -> 25, for the nine new truths only"


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_m8_pilot.jsonl")
    ap.add_argument("--seeds", default="/tmp/panel_seeds_m8_pilot.csv")
    ap.add_argument("--baseline", default="/tmp/results_m8_pilot_rounded.jsonl")
    ap.add_argument("--atlas", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--out", default=str(
        REPO / "marketing_experimentation/docs/m8-pilot-freeze.json"))
    args = ap.parse_args()

    rec = Path(__file__).resolve().parent
    art = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "M8 pilot accepted; freeze before the iteration count changes",
        "permitted_change_after_this_point": PERMITTED_CHANGE,

        "code": {
            "repo_head": git("rev-parse", "HEAD"),
            "repo_head_subject": git("log", "-1", "--format=%s"),
            "tree_clean": git("status", "--porcelain") == "",
            "m8_baseline_commit": "4c892f5",
            "m8_baseline_note":
                "the commit that introduces the CRN cluster gate. NOT cc38fc2 "
                "-- that is F16 only and reproduces a pilot with no gate.",
        },

        "donor": {
            "clone": str(DONOR),
            "base_commit": git("rev-parse", "HEAD", cwd=DONOR),
            "working_tree_dirty_by_design": True,
            "patches": {p: sha256(rec / p) for p in PATCHES},
            "patched_files_sha256": {
                "src/R/generate_panels.R":
                    sha256(DONOR / "src/R/generate_panels.R"),
                "src/python/run_tools.py":
                    sha256(DONOR / "src/python/run_tools.py"),
            },
            "note":
                "file hashes are recorded ALONGSIDE the patch hashes because "
                "a patch being unchanged does not establish that the file it "
                "was applied to is unchanged.",
        },

        "data": {
            "pilot_results": {"path": args.results,
                              "sha256": sha256(Path(args.results)),
                              "rows": _rows(args.results)},
            "seed_manifest": {"path": args.seeds,
                              "sha256": sha256(Path(args.seeds)),
                              "rows": _rows(args.seeds)},
            "prefix_baseline_kept_as_f17_control": {
                "path": args.baseline, "sha256": sha256(Path(args.baseline)),
                "rows": _rows(args.baseline)},
            "atlas_seven_truths": {"path": args.atlas,
                                   "sha256": sha256(Path(args.atlas)),
                                   "rows": _rows(args.atlas)},
            "known_state_note":
                "the donor clone's panels/ directory holds 25 iterations, not "
                "10: an extension was started before this freeze existed and "
                "aborted. Iterations 1-10 are identical by seed, and the "
                "aborted partial results are kept at "
                "/tmp/results_m8_partial_aborted.jsonl and are NOT part of "
                "any analysis. Recorded because an undocumented surplus is "
                "how a later run silently uses data nobody authorised.",
        },

        "design": {
            "theta_grid_new": [-0.15, -0.03125, -0.02, -0.01, 0.01, 0.0125,
                               0.051875, 0.10, 0.104375],
            "theta_grid_existing": [-0.10, -0.05, 0.0, 0.02, 0.05, 0.075,
                                    0.15],
            "action_boundaries": [float(x) for x in action_boundaries()],
            "actions": list(DEFAULT_ACTIONS),
            "multipliers": list(DEFAULT_MULTIPLIERS),
            "breakeven_is_not_a_boundary": 0.03,
            "cluster_definition": ["scenario", "iteration"],
            "iterations_analysed": "1-10",
            "gate_threshold_percentile": 95,
            "gate_yardstick": "cluster-bootstrap spread of q itself",
        },

        "result": {
            "pilot_acceptance": "ACCEPTED, 21/21 after the F17 fix",
            "f17_closure": "CLOSED: only effect_pct and runtime_seconds "
                           "differ between the pre- and post-fix runs; "
                           "consumer inventory has no entry in class "
                           "`estimation`",
            "attach_equivalence":
                "slope 1.00000 / intercept <=1.6e-09 / R2 1.00000 for three "
                "tools; causalpy slope 0.99920, intercept -1.6e-04, R2 "
                "0.99997, max|new-old| 1.1e-03, consistent with its own "
                "sampler noise rather than a different panel",
            "boundary_leave_one_out": "PASS, 0/56 above the 95th percentile",
            "boundary_stress": "PASS, 0/16 above the 95th percentile, spans "
                               "3.00-7.50pp",
            "caveat_on_the_gate":
                "the yardstick is sampling noise, which shrinks with cluster "
                "count. This is a PASS AT n=10. The gate must be re-run at "
                "n=25 before a continuous-prior EVSI is built on it, and it "
                "may fail there. That is the gate working.",
        },
    }

    out = Path(args.out)
    out.write_text(json.dumps(art, indent=2) + "\n")
    print(json.dumps(art, indent=2))
    print(f"\nwrote {out}")
    print(f"\nPERMITTED CHANGE AFTER THIS POINT: {PERMITTED_CHANGE}")
    print("Anything else differing on the next run is a protocol violation,")
    print("not a refinement, and the next freeze should say so.")


def _rows(path: str) -> int | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open() as f:
        return sum(1 for _ in f)


if __name__ == "__main__":
    main()
