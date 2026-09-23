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
            # NOT "repo_head". A file cannot record the hash of the commit
            # that contains it -- the hash is a function of the contents,
            # which would contain the hash. The model is two commits:
            #
            #   A = analysis_commit : all code, contracts and gates
            #   B = freeze commit   : parent A, adds ONLY this file
            #
            # This artifact names A. B is named by a pointer file written
            # one commit later -- not by a tag, since this remote refuses
            # tag pushes and a tag absent from origin identifies nothing.
            # An earlier, STALE copy of this file also sits inside A, from a
            # generation before A existed; it records tree_clean = false and
            # must not be used. Recorded here because the alternative is a
            # future reader finding two freezes and picking one.
            "analysis_commit": git("rev-parse", "HEAD"),
            "analysis_commit_subject": git("log", "-1", "--format=%s"),
            # Resolved WITHOUT a tag, because this remote refuses tag pushes
            # (branch refs only) -- a tag that exists on one clone and not on
            # the origin identifies nothing for whoever reproduces this.
            # Instead the freeze commit's SHA is written into a pointer file
            # in the FOLLOWING commit, which is not self-referential and
            # survives a clone.
            "freeze_commit": "recorded in docs/m8-pilot-freeze.commit by the "
                             "commit AFTER this file's; not recordable here, "
                             "since a file cannot contain the hash of the "
                             "commit that contains it",
            "tag_note": "this remote refuses tag pushes, so do not rely on a "
                        "tag to find the freeze",
            "stale_copy_warning":
                "a superseded copy of this artifact exists in the analysis "
                "commit itself, recording tree_clean=false. Use the one "
                "named by docs/m8-pilot-freeze.commit.",
            "tree_clean_at_generation": git("status", "--porcelain") == "",
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

        "quarantine": {
            "status": "ABORTED_UNAUTHORIZED_EXTENSION",
            "what": "a 25-iteration extension started before this freeze "
                    "existed, killed at 2,740 rows",
            "rows": _rows("/tmp/results_m8_partial_aborted.jsonl"),
            "sha256": sha256(Path("/tmp/results_m8_partial_aborted.jsonl")),
            "started_from_freeze": False,
            "eligible_for_analysis": False,
            "eligible_for_reuse": False,
            "payload_disposition": "DELETED after this manifest was written. "
                                   "The evidence that it happened is kept; "
                                   "the reusable observations are not, so no "
                                   "future glob can discover them.",
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
                "10. Iterations 1-10 are identical by seed. See `quarantine`. "
                "Recorded because an undocumented surplus is how a later run "
                "silently uses data nobody authorised.",
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
                "tools. CausalPy: slope 0.99920, intercept -1.6e-04, R2 "
                "0.99997. Its new/old deviations are COMPATIBLE with the "
                "previously observed old/old variability envelope, median at "
                "the 33rd percentile of accepted old/old pair deviations. No "
                "evidence here of an attach-equivalence failure. The "
                "mechanism underlying that variability remains unidentified "
                "(F8). NOT a claim that the distributions are the same -- 21 "
                "old/old pairs, not independent, and the new/old max slightly "
                "exceeds the old/old max.",
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
