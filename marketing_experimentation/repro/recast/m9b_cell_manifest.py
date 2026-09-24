#!/usr/bin/env python
"""Record what each completed M9-B cell IS, in a file that survives /tmp.

Why
---
The session container was restarted mid-run on 2026-09-24. /tmp happened to
survive; next time it may not. The cells themselves are donor-derived output
and stay PRIVATE (docs/artifact-manifest.json), so they cannot go in the
repository -- but their cryptographic record can, and that is the difference
between "regenerate and check identity" and "regenerate and hope".

Blinding
--------
This reads bytes and counts lines. It never parses a results row, so it
cannot see an estimate. Hashing is not reading.

    python marketing_experimentation/repro/recast/m9b_cell_manifest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "marketing_experimentation/docs/m9b-cell-manifest.json"
EXPECT_ROWS = 1600
EXPECT_SEEDS = 401  # 400 records + header


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="/tmp/m9b_cells")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--runner-log", default="/tmp/m9b_run.out",
                    help="the RUNNER's stdout, which carries the [N/16] and "
                         "'estimated in' lines. run.log holds the R and "
                         "run_tools subprocess output instead.")
    a = ap.parse_args()
    d = Path(a.cells)

    # wall clock per cell, from the runner's own log lines
    timings = {}
    log = Path(a.runner_log)
    if log.exists():
        cur = None
        for ln in log.read_text(errors="replace").splitlines():
            m = re.match(r"\[(\d+)/16\] (M9B_\S+)", ln.strip())
            if m:
                cur = m.group(2)
            m = re.search(r"estimated in ([\d.]+) min", ln)
            if m and cur:
                timings[cur] = float(m.group(1))

    cells = {}
    for f in sorted(d.glob("M9B_*.jsonl")):
        c = f.stem
        s = d / f"{c}.panel_seeds.csv"
        rows = sum(1 for _ in f.open("rb"))
        cells[c] = {
            "rows": rows,
            "complete": rows == EXPECT_ROWS,
            "results_sha256": sha256(f),
            "results_bytes": f.stat().st_size,
            "seed_log_sha256": sha256(s) if s.exists() else None,
            "seed_log_records": (sum(1 for _ in s.open("rb")) - 1)
                                if s.exists() else None,
            "estimate_minutes": timings.get(c),
        }

    fz = json.loads((REPO / "marketing_experimentation/docs/m9b-freeze.json"
                     ).read_text())
    done = [c for c, v in cells.items() if v["complete"]]
    art = {
        "schema": "leadbench-mx M9-B cell manifest v1",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "distribution_status":
            "The CELLS are PRIVATE donor-derived output and are NOT in this "
            "repository. This file is their provenance record only -- hashes, "
            "row counts and wall clock. See docs/artifact-manifest.json.",
        "purpose":
            "A container restart on 2026-09-24 killed the run mid-cell. /tmp "
            "survived that one. This file is what lets a regenerated cell be "
            "checked for IDENTITY against the cell it replaces, rather than "
            "assumed equal to it.",
        "freeze": {
            "analysis_commit": fz["code"]["analysis_commit"],
            "generator_sha256":
                fz["donor"]["patched_files_sha256"]["src/R/generate_panels.R"],
            "patch_stack": fz["donor"]["patch_stack_in_order"],
        },
        "expected": {"cells": 16, "rows_per_cell": EXPECT_ROWS,
                     "seed_records_per_cell": 400},
        "progress": {"complete": len(done), "of": len(fz["design"]["cells"]),
                     "missing": [c for c in fz["design"]["cells"]
                                 if c not in done]},
        "cells": cells,
        "blinding_note":
            "Produced by hashing bytes and counting lines. No results row was "
            "parsed, so nothing here is a function of an estimate.",
    }
    Path(a.out).write_text(json.dumps(art, indent=2) + "\n")
    print(f"{len(done)}/16 complete -> {a.out}")
    for c, v in cells.items():
        flag = "" if v["complete"] else f"  <-- {v['rows']} rows, INCOMPLETE"
        t = f"{v['estimate_minutes']:6.1f} min" if v["estimate_minutes"] else "    -    "
        print(f"   {c}  {t}  {v['results_sha256'][:16]}{flag}")


if __name__ == "__main__":
    main()
