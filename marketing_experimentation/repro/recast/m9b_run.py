#!/usr/bin/env python
"""Run the 16 frozen M9-B cells, one at a time, blinded.

Blinding, enforced rather than promised
---------------------------------------
Cell-wise checkpointing makes an interim EVSI surface readable at any
moment, and reading it would turn a preregistered 16-cell design into a
sequential one with an undeclared stopping rule. So this runner never loads
`att_pct`, `ci_lower`, `ci_upper` or `significant` into anything it prints.
It reports two kinds of state, both permitted by the freeze:

    operational   which cells are done, rows, wall clock, exit codes, disk
    integrity     geo and day counts, arm and iteration completeness, the
                  seed log's world invariants

`ESTIMATE_FIELDS` below is the list it refuses to touch, and
`_assert_blind()` checks that refusal on every summary it emits. A promise
in a docstring is not a control.

Checkpointing
-------------
One cell per pass:

    1. clear panels/          so run_tools.py can only see this cell
    2. generate               the frozen flags, 16 truths, 25 iterations
    3. persist the seed log   BEFORE any estimation, so a crash during
                              estimation still leaves the world reproducible
    4. run_tools.py           resumes from results.jsonl by key
    5. extract + persist      this cell's rows, with a row-count gate
    6. clear panels/          ~500MB of parquet would otherwise accumulate

A cell already persisted with the right row count is skipped, so an
interrupted run resumes at cell granularity.

    python marketing_experimentation/repro/recast/m9b_run.py
    python marketing_experimentation/repro/recast/m9b_run.py --dry-run
    python marketing_experimentation/repro/recast/m9b_run.py --only M9B_T42_G40
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FREEZE = REPO / "marketing_experimentation/docs/m9b-freeze.json"
DONOR = Path("/home/user/donor-smoke")
R_BIN = "/opt/R/4.5.1/bin/Rscript"
R_LIBS = DONOR / "renv/library/linux-ubuntu-noble/R-4.5/x86_64-pc-linux-gnu"
#: run_tools.py needs the donor's own deps (causalpy 0.8.0, pymc 5.28.1),
#: not this repo's venv.
DONOR_PY = DONOR / ".venv-repro/bin/python"
PERSIST = Path("/tmp/m9b_cells")

#: Never read, never printed, never aggregated until all 16 cells are done.
ESTIMATE_FIELDS = ("att_pct", "att_level", "ci_lower", "ci_upper",
                   "ci_lower_level", "ci_upper_level", "significant",
                   "p_value", "true_att_pct", "true_att_level")

#: 4 rows per panel: causalpy, google_mm, geolift, causalimpact.
ROWS_PER_PANEL = 4


def load_freeze() -> dict:
    d = json.loads(FREEZE.read_text())
    if d["reuse"]["cells_reused"]:
        raise SystemExit("the freeze declares reused cells; this runner "
                         "regenerates all 16 and would contradict it")
    return d


def _assert_blind(obj) -> None:
    """Refuse to emit anything carrying an estimate field.

    Cheap, and it fires the moment someone adds a 'just this once' mean.
    """
    s = json.dumps(obj) if not isinstance(obj, str) else obj
    hit = [f for f in ESTIMATE_FIELDS if f in s]
    if hit:
        raise SystemExit(f"BLINDING VIOLATION: about to emit {hit}. The EVSI "
                         f"surface is not readable until all 16 cells are "
                         f"complete -- see m9b-freeze.json `blinding`.")


def theta_flag(grid: list[float]) -> str:
    # repr, not a format string: 0.051875 and 0.104375 must reach R exactly,
    # and a rounded theta on a decision boundary is F17.
    return ",".join(repr(t) for t in grid)


def child_env() -> dict:
    """Environment for every subprocess.

    R_LIBS_SITE alone is NOT enough, and getting that wrong cost this run
    half its payload (F21). `run_tools.py` shells out to a BARE `Rscript`
    for GeoLift and CausalImpact; bare resolves to /usr/bin/Rscript, which
    is R 4.6.1, which cannot load packages built for the R 4.5 library that
    R_LIBS_SITE points at. Both tools failed instantly and run_tools wrote
    all-null rows. So the matched R must lead PATH as well.
    """
    return {**os.environ,
            "R_LIBS_SITE": str(R_LIBS),
            "PATH": f"{Path(R_BIN).parent}:{os.environ.get('PATH', '')}"}


def sh(cmd: list[str], cwd: Path, log: Path) -> tuple[int, float]:
    t0 = time.time()
    with log.open("ab") as f:
        f.write(f"\n$ {' '.join(cmd)}\n".encode())
        f.flush()
        p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                           env=child_env())
    return p.returncode, time.time() - t0


def clear_panels() -> None:
    d = DONOR / "panels"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)


def cell_rows(path: Path, cell: str) -> int:
    """Count this cell's rows WITHOUT parsing estimates."""
    n = 0
    if not path.exists():
        return 0
    with path.open() as f:
        for line in f:
            # substring test, not json.loads: nothing is materialised
            if f'"scenario": "{cell}"' in line or f'"scenario":"{cell}"' in line:
                n += 1
    return n


def extract(src: Path, cell: str, dst: Path) -> tuple[int, dict]:
    """Write the cell's rows out, and count USABLE rows per tool.

    A row-count gate passes 1,600 rows whether or not any of them carries an
    estimate. That is how this run produced 16 cells of "1,600 rows (OK)"
    with two of four tools empty in every one -- absence normalised into a
    value, the same class as C10. `att_pct is None` is the only field read
    here, and only for presence: no value is compared, ordered or summarised,
    so blinding holds.
    """
    n = 0
    usable: dict = {}
    with src.open() as fin, dst.open("w") as fout:
        for line in fin:
            if f'"scenario": "{cell}"' not in line and \
               f'"scenario":"{cell}"' not in line:
                continue
            fout.write(line)
            n += 1
            r = json.loads(line)
            t = r["tool"] + (f"[{r['posterior_type']}]"
                             if r.get("posterior_type") else "")
            e = usable.setdefault(t, [0, 0])
            e[0] += 1
            if r.get("att_pct") is not None:
                e[1] += 1
    return n, usable


def check_seed_log(path: Path, cell: str, t: int, g: int,
                   iterations: int, n_theta: int) -> list[str]:
    """Integrity only: world shape, arm completeness, CRN across arms."""
    import csv
    msgs = []
    with path.open() as f:
        rows = list(csv.DictReader(f))
    if len(rows) != iterations * n_theta:
        msgs.append(f"{len(rows)} seed records, expected "
                    f"{iterations * n_theta}")
    by_it: dict[str, set] = {}
    for r in rows:
        if int(r["world_n_geos"]) != 41 or int(r["world_total_days"]) != 132:
            msgs.append("a record claims a world other than 41 x 132")
        if int(r["requested_post_days"]) != t or int(r["requested_n_control"]) != g:
            msgs.append("a record's requested axes disagree with the cell id")
        if int(r["perm_seed"]) != int(r["panel_seed"]) + 900000:
            msgs.append("perm_seed is not panel_seed + 900000")
        by_it.setdefault(r["iteration"], set()).add(
            (r["panel_seed"], r["donor_order"], r["treated_geo"]))
    for it, s in by_it.items():
        if len(s) != 1:
            msgs.append(f"iteration {it}: the world moves across arms -- "
                        f"common random numbers are broken")
    return sorted(set(msgs))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None, help="one cell id")
    ap.add_argument("--persist", default=str(PERSIST))
    a = ap.parse_args()

    fz = load_freeze()
    grid = fz["design"]["theta_grid"]
    iters = fz["design"]["iterations"]
    cells = fz["design"]["cells"]
    expect = iters * len(grid) * ROWS_PER_PANEL

    persist = Path(a.persist)
    persist.mkdir(parents=True, exist_ok=True)
    log = persist / "run.log"
    results = DONOR / "results/raw/results.jsonl"

    print("=" * 72)
    print("M9-B: 16 cells, blinded")
    print("=" * 72)
    print(f"freeze      : {FREEZE.name}  analysis_commit "
          f"{fz['code']['analysis_commit'][:12]}")
    print(f"generator   : {fz['donor']['patched_files_sha256']['src/R/generate_panels.R'][:16]}")
    print(f"grid        : {len(grid)} truths x {iters} iterations x "
          f"{ROWS_PER_PANEL} tools = {expect:,} rows/cell")
    print(f"persist to  : {persist}")
    print(f"permitted   : {fz['permitted_change_after_this_point'][:60]}...")
    print()

    # run_tools.py appends to one results file and resumes from it by key,
    # so M9-B rows must not land on top of M8's. Park them once, explicitly,
    # rather than filtering later: a results file holding two families is
    # how a later glob silently analyses both.
    if results.exists():
        with results.open() as f:
            foreign = any('"scenario": "M9B_' not in ln
                          and '"scenario":"M9B_' not in ln for ln in f)
        if foreign:
            parked = results.parent / "results_pre_m9b.jsonl"
            if parked.exists():
                raise SystemExit(f"{parked} already exists; refusing to "
                                 f"overwrite a parked results file")
            shutil.move(str(results), str(parked))
            print(f"parked pre-M9B rows -> {parked} "
                  f"(M8's are already archived and hash-verified)")

    todo = [c for c in cells if (a.only is None or c == a.only)]
    done, skipped = [], []
    for c in todo:
        p = persist / f"{c}.jsonl"
        if p.exists() and sum(1 for _ in p.open()) == expect:
            skipped.append(c)
    print(f"{len(skipped)} of {len(todo)} cells already complete"
          + (f": {', '.join(skipped)}" if skipped else ""))

    if a.dry_run:
        for c in todo:
            if c in skipped:
                continue
            t = int(c.split("_T")[1][:2]); g = int(c.split("_G")[1][:2])
            print(f"  would run {c}: --post_days {t} --n_control {g} "
                  f"--n_iterations {iters} --effect_sizes "
                  f"{theta_flag(grid)[:40]}...")
        return 0

    t_start = time.time()
    for i, c in enumerate(todo, 1):
        if c in skipped:
            continue
        t = int(c.split("_T")[1][:2])
        g = int(c.split("_G")[1][:2])
        print(f"\n[{i}/{len(todo)}] {c}  (T={t}, G_c={g})  "
              f"{datetime.now(timezone.utc):%H:%M:%SZ}")

        clear_panels()
        rc, dt = sh([R_BIN, "src/R/generate_panels.R",
                     "--n_iterations", str(iters),
                     "--effect_sizes", theta_flag(grid),
                     "--post_days", str(t), "--n_control", str(g),
                     "--output_base", "panels"], DONOR, log)
        if rc != 0:
            print(f"   GENERATOR FAILED (exit {rc}). See {log}. Stopping.")
            return 2
        print(f"   generated in {dt:.0f}s")

        seeds = DONOR / f"panels/{c}/panel_seeds.csv"
        if not seeds.exists():
            print(f"   no seed log at {seeds}. Stopping.")
            return 2
        shutil.copy2(seeds, persist / f"{c}.panel_seeds.csv")
        msgs = check_seed_log(seeds, c, t, g, iters, len(grid))
        if msgs:
            print("   SEED LOG INTEGRITY FAILED:")
            for m in msgs:
                print(f"     - {m}")
            return 2
        print(f"   seed log persisted and clean "
              f"({iters * len(grid)} records, world 41x132)")

        rc, dt = sh([str(DONOR_PY), "src/python/run_tools.py"], DONOR, log)
        if rc != 0:
            print(f"   run_tools FAILED (exit {rc}). See {log}. Stopping.")
            return 2

        n, usable = extract(results, c, persist / f"{c}.jsonl")
        dead = sorted(t for t, (_, u) in usable.items() if u == 0)
        thin = sorted(t for t, (tot, u) in usable.items() if 0 < u < tot)
        print(f"   estimated in {dt/60:.1f} min -> {n:,} rows "
              f"({'OK' if n == expect else f'EXPECTED {expect:,}'}), "
              f"{len(usable)} tools, "
              + ", ".join(f"{t} {u}/{tot}" for t, (tot, u) in sorted(usable.items())))
        if n != expect:
            print("   row count gate FAILED. Stopping; the partial cell is "
                  "kept for inspection but is not complete.")
            return 2
        if dead:
            print(f"   USABLE-ROW GATE FAILED: {dead} produced 0 estimates in "
                  f"{n:,} rows. That is a tool that did not run, not a tool "
                  f"that found nothing. Stopping.")
            return 2
        if thin:
            print(f"   note: partial coverage in {thin} -- not fatal, but "
                  f"recorded.")

        done.append(c)
        clear_panels()

        el = time.time() - t_start
        rem = len(todo) - len(skipped) - len(done)
        line = (f"   [{len(done)} done, {rem} left] elapsed {el/3600:.2f}h, "
                f"projected remaining {el/max(len(done),1)*rem/3600:.2f}h")
        _assert_blind(line)
        print(line)

    print("\n" + "=" * 72)
    print(f"{len(done)} cells completed this pass, {len(skipped)} already "
          f"done, {time.time()-t_start:.0f}s")
    total = sum(1 for c in cells
                if (persist / f"{c}.jsonl").exists()
                and sum(1 for _ in (persist / f'{c}.jsonl').open()) == expect)
    print(f"{total}/{len(cells)} cells complete overall")
    if total == len(cells):
        print("\nAll 16 cells complete. The EVSI surface is now readable.")
        print("Nothing in this run read it.")
    else:
        print("\nSurface still sealed: not all cells are complete.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
