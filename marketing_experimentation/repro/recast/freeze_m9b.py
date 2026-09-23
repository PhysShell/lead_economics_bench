#!/usr/bin/env python
"""Freeze the M9-B generator state BEFORE the first cell is run.

Why this is a separate freeze from M8's
---------------------------------------
M8's freeze answers "what was the state when the pilot was accepted, and
what single thing may change next". M9-B is a different family on a changed
generator: the world contract did not exist when M8 was frozen, and no M9-B
number is comparable to an M8 one across the A1/A3 cells. Folding it into
`m8-pilot-freeze.json` would make one manifest describe two incompatible
generators, and the next reader would have no way to tell which cell came
from which. Separate family, separate freeze.

What is different about freezing BEFORE a run
---------------------------------------------
There is no data to hash. What is recorded instead is everything that
decides what the data will be -- the generator's hash, the patch stack, the
grid, the seeds, and the verdict of the world-contract suite -- plus the
rules the run itself must obey. A freeze taken after the numbers exist can
always be accused of having been shaped by them; this one cannot.

The check is RUN, not cited
---------------------------
This script executes `m9b_world_check.py` and refuses to write a manifest if
any relation fails. A freeze that records "11/11" from memory records a
sentence, not a state.

    python marketing_experimentation/repro/recast/freeze_m9b.py \
        --out marketing_experimentation/docs/m9b-freeze.json
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
REC = Path(__file__).resolve().parent
DONOR = Path("/home/user/donor-smoke")

#: Order matters: each applies on top of the previous.
PATCHES = ["theta-mutation.patch", "m8-seed-log.patch", "m9b-axes.patch"]

#: The frozen grid. 16 cells, no reuse.
POST_DAYS = [15, 21, 28, 42]
N_CONTROL = [5, 9, 20, 40]
ITERATIONS = 25

#: The 16 M8 truths, in the order the labels sort to on disk.
THETA_GRID = [-0.15, -0.10, -0.05, -0.03125, -0.02, -0.01, 0.0, 0.01,
              0.0125, 0.02, 0.05, 0.051875, 0.075, 0.10, 0.104375, 0.15]

#: Nothing. Not "only N", not "only a label" -- the generator is frozen from
#: here to the sixteenth cell, and the only permitted action is invoking it.
PERMITTED_CHANGE = (
    "NONE. The only permitted action between this freeze and the 16th "
    "completed cell is invoking the frozen generator with the frozen flags. "
    "Any edit to generate_panels.R, run_tools.py, the patch stack, the grid "
    "or the seeds voids the freeze and requires a new one -- including an "
    "edit that only makes the run faster."
)

#: Blinding. Stated as a rule because a rule that lives only in a chat
#: message is not a rule.
BLINDING = {
    "permitted_during_the_run": [
        "operational state: which cells are complete, row counts, wall "
        "clock, exit codes, disk",
        "integrity state: seed logs, complete-cluster gate, geo/day counts "
        "per cell, the world invariants of m9b_world_check.py",
        "failures of any kind, at any time",
    ],
    "not_permitted_during_the_run": [
        "the EVSI surface, r_EVSI(T, G_c), or any function of att_pct, "
        "ci_lower, ci_upper or `significant` aggregated across cells",
        "anything that could motivate stopping the run early, extending it, "
        "reordering it, or choosing which cells to keep",
    ],
    "why": "cell-wise checkpointing makes an interim surface readable at any "
           "moment. Reading it turns a preregistered 16-cell design into a "
           "sequential one with an undeclared stopping rule, and no later "
           "analysis can undo that.",
    "reuse_rule": "a cell counts as reused only if its identity matches -- "
                  "generator sha256, patch stack, cell id, grid, seeds. Not "
                  "'looks equivalent'. Nothing is reused in M9-B; see "
                  "`reuse`.",
}


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


def run_world_check(python: str) -> tuple[bool, str, list[str]]:
    p = subprocess.run([python, str(REC / "m9b_world_check.py"),
                        "--donor", str(DONOR)],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    lines = [ln.strip() for ln in out.splitlines()
             if ln.startswith("[") or "CONTRACT" in ln]
    return p.returncode == 0, out, lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(
        REPO / "marketing_experimentation/docs/m9b-freeze.json"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--mutation-verdict", default=str(
        REPO / "marketing_experimentation/docs/m9b-mutation-verdict.txt"),
        help="output of m9b_mutations.sh; hashed, not re-run (it edits the "
             "donor clone in place, which a freeze must not do)")
    args = ap.parse_args()

    print("running the world-contract suite (this is the freeze's evidence, "
          "not a citation of it)...\n")
    ok, raw, lines = run_world_check(args.python)
    for ln in lines:
        print("   " + ln)
    if not ok:
        print("\nREFUSED: the world contract does not hold. Nothing frozen.")
        print(raw[-3000:])
        raise SystemExit(2)

    cells = [f"M9B_T{t:02d}_G{g:02d}" for t in POST_DAYS for g in N_CONTROL]

    art = {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "family": "M9-B",
        "purpose": "freeze the generator and the design BEFORE the first "
                   "cell is run; no M9-B data exists at this point",
        "permitted_change_after_this_point": PERMITTED_CHANGE,
        "supersedes_nothing": "M8 and its freeze are untouched. M9-B runs on "
                              "a changed generator and its A1/A3-shaped "
                              "cells are NOT the A1/A3 rows -- see "
                              "docs/m9-preregistration.md, M9-B Addendum 1.",

        "code": {
            # Same two-commit model as the M8 freeze: this artifact names the
            # analysis commit; the freeze commit is named by a pointer file
            # written one commit later, because a file cannot contain the
            # hash of the commit that contains it, and this remote refuses
            # tag pushes.
            "analysis_commit": git("rev-parse", "HEAD"),
            "analysis_commit_subject": git("log", "-1", "--format=%s"),
            "freeze_commit": "recorded in docs/m9b-freeze.commit by the "
                             "commit AFTER this file's",
            "tree_clean_at_generation": git("status", "--porcelain") == "",
        },

        "donor": {
            "clone": str(DONOR),
            "base_commit": git("rev-parse", "HEAD", cwd=DONOR),
            "working_tree_dirty_by_design": True,
            "patch_stack_in_order": PATCHES,
            "patches": {p: sha256(REC / p) for p in PATCHES},
            "patched_files_sha256": {
                "src/R/generate_panels.R":
                    sha256(DONOR / "src/R/generate_panels.R"),
                "src/python/run_tools.py":
                    sha256(DONOR / "src/python/run_tools.py"),
            },
            "note": "file hashes sit ALONGSIDE patch hashes because an "
                    "unchanged patch does not establish an unchanged file.",
        },

        "world_contract": {
            "max_post_days": 42,
            "max_controls": 40,
            "pre_days": 90,
            "world_shape": "90 pre + 42 post days, 1 treated + 40 controls",
            "seed_slot": 1,
            "panel_seed": "master_seed*1000 + seed_slot*10000 + iteration",
            "noise_seed_offset": 100000,
            "perm_seed_offset": 900000,
            "treated_selection": "the unchanged median-baseline rule, applied "
                                 "ONCE to the 41-geo world",
            "donor_order": "sample.int over the 40 non-treated indices, on a "
                           "dedicated substream; pools are its prefixes",
            "nesting": ["D5 subset D9 subset D20 subset D40",
                        "Y15 subset Y21 subset Y28 subset Y42"],
            "not_used": "the sorted-baseline prefix, which would fuse pool "
                        "size with donor size-similarity (F20, M-c)",
        },

        "design": {
            "cells": cells,
            "n_cells": len(cells),
            "post_days": POST_DAYS,
            "n_control": N_CONTROL,
            "theta_grid": THETA_GRID,
            "n_theta": len(THETA_GRID),
            "iterations": ITERATIONS,
            "scenario_template": "A1 -- no outlier, pre_days = 90",
            "cluster_definition": ["scenario", "iteration"],
            "cluster_note": "within a cell, (scenario, iteration) is the CRN "
                            "cluster over theta, as in M8. ACROSS cells the "
                            "same `iteration` is the same world, which is a "
                            "variance-reduction property for cell-to-cell "
                            "comparison and NOT a licence to pool cells into "
                            "one cluster set.",
            "action_boundaries": [float(x) for x in action_boundaries()],
            "actions": list(DEFAULT_ACTIONS),
            "multipliers": list(DEFAULT_MULTIPLIERS),
            "breakeven_is_not_a_boundary": 0.03,
            "estimand": "r_EVSI(T, G_c) = EVSI(T, G_c) / S_governed",
            "monotonicity": "DESCRIPTIVE. No acceptance threshold is attached "
                            "to it, and none will be invented after seeing "
                            "the surface.",
            "expected_rows": len(cells) * len(THETA_GRID) * 4 * ITERATIONS,
        },

        "reuse": {
            "cells_reused": [],
            "rationale": "M9B_T15_G20 is not A1 and M9B_T15_G09 is not A3: "
                         "21 geos drawn as 41 and sliced is a different "
                         "world from 21 drawn as 21. Reuse would have saved "
                         "~1.7 CPU-hours and bought an axis whose meaning is "
                         "false. All 16 cells regenerate.",
            "identity_fields_that_would_have_to_match":
                ["donor.patched_files_sha256", "donor.patch_stack_in_order",
                 "design.cells", "design.theta_grid", "design.iterations",
                 "world_contract"],
        },

        "verification": {
            "world_check_script": str(REC / "m9b_world_check.py"),
            "world_check_sha256": sha256(REC / "m9b_world_check.py"),
            "world_check_verdict": [ln for ln in lines],
            "world_check_run_by_this_script": True,
            "mutation_script": str(REC / "m9b_mutations.sh"),
            "mutation_script_sha256": sha256(REC / "m9b_mutations.sh"),
            "mutation_verdict_file": args.mutation_verdict,
            "mutation_verdict_sha256": sha256(Path(args.mutation_verdict)),
            "mutation_note":
                "m9b_mutations.sh is NOT re-run here: it edits the donor "
                "clone in place, and a freeze must not mutate the state it "
                "is freezing. Its recorded output is hashed instead. Two of "
                "its five mutations were accepted 10/10 by the first version "
                "of the world check -- see failures.md F20.",
        },

        "run_protocol": {
            "one_cell_per_invocation":
                "Rscript src/R/generate_panels.R --n_iterations 25 "
                "--effect_sizes <16 truths> --post_days T --n_control G "
                "--output_base panels, then run_tools.py",
            "checkpointing": "cell-wise. On each cell's completion, copy its "
                             "results rows and panels/<cell>/panel_seeds.csv "
                             "out before starting the next. run_tools.py "
                             "resumes from results.jsonl by "
                             "(scenario, effect_label, iteration, tool).",
            "seed_log_path": "panels/<cell>/panel_seeds.csv -- written beside "
                             "the panels precisely so the next cell's run "
                             "cannot overwrite it at results/raw/",
            "on_failure": "stop, record, do not silently re-run a cell into "
                          "the same results file",
            "artifacts": "PRIVATE, per docs/artifact-manifest.json. Donor-"
                         "derived output stays out of this and any public "
                         "repository; only its provenance record is committed.",
        },

        "blinding": BLINDING,

        "cost_estimate": {
            "rows": len(cells) * len(THETA_GRID) * 4 * ITERATIONS,
            "basis": "M8 measured 3,600 rows in 6,911s = 1.92 s/row at mean "
                     "n_geos 21, total_days 105",
            "mean_slice": {"n_geos": 19.5, "total_days": 116.5},
            "central_cpu_hours": 13.7,
            "uncertainty": "upward. CausalPy dominates and scales with panel "
                           "size; G_c=40 is larger than anything M8 ran.",
        },

        "what_this_does_not_establish": [
            "that the world resembles a real marketing experiment -- the DGP "
            "is synthetic and contains no spend, no budget and no "
            "intervention",
            "that r_EVSI(T, G_c) differences transport outside this DGP",
            "anything about cost: M9-B is not an ENBS and invents no cost "
            "model",
        ],
    }

    out = Path(args.out)
    out.write_text(json.dumps(art, indent=2) + "\n")
    print(f"\nwrote {out}")
    print(f"\nPERMITTED CHANGE AFTER THIS POINT:\n  {PERMITTED_CHANGE}")
    print("\nBLINDING: during the run, read operational and integrity state "
          "only.\n  The EVSI surface is not readable until all 16 cells are "
          "complete.")


if __name__ == "__main__":
    main()
