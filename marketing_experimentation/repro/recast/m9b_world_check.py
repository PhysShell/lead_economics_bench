#!/usr/bin/env python
"""Metamorphic tests for the M9-B nested maximal-world generator.

Run this BEFORE the M9-B freeze and BEFORE any cell is generated for
analysis. It has no oracle to check against -- there is no published M9-B
result -- so it checks *relations between runs* that must hold if the world
contract holds, and that fail loudly if it does not.

The contract under test
-----------------------
Every replication generates ONE maximal latent world:

    90 pre days + MAX_POST_DAYS(42) post days, 1 treated + MAX_CONTROLS(40)
    potential controls

and every design cell is a SLICE of it:

    treated geo   chosen once, from the 41-geo world, by the unchanged
                  median-baseline rule
    donor pools   nested by prefix of a dedicated-substream permutation:
                  D5 subset D9 subset D20 subset D40
    durations     nested by prefix: Y15 subset Y21 subset Y28 subset Y42

Why it matters. If the world moved with the axis, a cell-to-cell difference
in EVSI would confound "more donors help" with "a different world". The axis
would have a false meaning, and no downstream statistic would notice.

Why these tests and not a golden file. A golden hash pins the numbers we
happen to produce today; it does not say what makes them right. These say
what makes them right, so they survive a legitimate change to the numbers
and still catch an illegitimate one.

    python marketing_experimentation/repro/recast/m9b_world_check.py \
        --donor /home/user/donor-smoke
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

R_BIN = "/opt/R/4.5.1/bin/Rscript"
R_LIBS = ("renv/library/linux-ubuntu-noble/R-4.5/x86_64-pc-linux-gnu")

#: The preregistered M9-B grid. Kept here so the tests exercise the values
#: the study will actually run, not a convenient subset of them.
POST_DAYS = (15, 21, 28, 42)
N_CONTROL = (5, 9, 20, 40)
PRE_DAYS = 90

#: Two truths and two iterations are enough for every relation below: each
#: one is an identity between runs, not an estimate, so more replication buys
#: nothing. The negative test is the one that needs the full maximal cell.
TEST_THETAS = "0,0.075"
TEST_ITERS = 2

PANEL_COLS = ["geo", "date", "Y", "Y_counterfactual", "treated"]


class Fail(Exception):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_generator(script: Path, cwd: Path, out_base: Path, *flags: str) -> None:
    """Invoke generate_panels.R, failing loudly on a non-zero exit."""
    env = dict(os.environ)
    env["R_LIBS_SITE"] = str(Path(args_donor) / R_LIBS)
    cmd = [R_BIN, str(script), "--n_iterations", str(TEST_ITERS),
           "--effect_sizes", TEST_THETAS, "--output_base", str(out_base),
           *flags]
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise Fail(f"generator exited {p.returncode}\n"
                   f"  cmd: {' '.join(cmd)}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")


def load_cell(base: Path, cell: str) -> pd.DataFrame:
    """Every panel of one cell, tagged with its arm and iteration."""
    frames = []
    for eff_dir in sorted((base / cell).iterdir()):
        if not eff_dir.is_dir():
            continue
        for pf in sorted(eff_dir.glob("panel_*.parquet")):
            d = pd.read_parquet(pf)[PANEL_COLS]
            d["effect_label"] = eff_dir.name
            d["iteration"] = int(pf.stem.split("_")[1])
            frames.append(d)
    if not frames:
        raise Fail(f"no panels under {base / cell}")
    return pd.concat(frames, ignore_index=True)


def canon(d: pd.DataFrame) -> pd.DataFrame:
    """Sort into a representation-independent order.

    Row order is an artefact of how the slice was taken, not of the world.
    Comparing without this would report a difference that is not one -- the
    same class of mistake as C10's phantom `converged` finding, where a
    merge normalised absence into a value.
    """
    by = [c for c in ("effect_label", "iteration", "geo", "date") if c in d]
    return d.sort_values(by, kind="mergesort").reset_index(drop=True)


def identical(a: pd.DataFrame, b: pd.DataFrame, cols: list[str]) -> str | None:
    """Exact equality on `cols`. Returns a description of the first
    difference, or None. No tolerance: these are copies of the same floats,
    not two computations of the same quantity."""
    a, b = canon(a), canon(b)
    if len(a) != len(b):
        return f"row counts differ: {len(a)} vs {len(b)}"
    for c in cols:
        if c not in a or c not in b:
            return f"column {c} missing"
        eq = (a[c] == b[c]) | (a[c].isna() & b[c].isna())
        if not eq.all():
            i = int((~eq).idxmax())
            return (f"column {c} differs first at row {i}: "
                    f"{a[c].iloc[i]!r} vs {b[c].iloc[i]!r} "
                    f"({int((~eq).sum())} rows differ)")
    return None


# ── the checks ────────────────────────────────────────────────────────

def check_legacy(donor: Path, work: Path, report: list) -> None:
    """L: with no M9-B flags, the patched generator must be byte-identical.

    Checked against the file the patch was applied to, recovered by
    reverse-applying the patch -- not against a copy taken by hand, which
    would only prove that the copy matches itself.
    """
    patched = donor / "src/R/generate_panels.R"
    patch = Path(__file__).resolve().parent / "m9b-axes.patch"

    base_root = work / "legacy_base"
    new_root = work / "legacy_new"
    for root in (base_root, new_root):
        (root / "src/R").mkdir(parents=True, exist_ok=True)
    shutil.copy2(patched, new_root / "src/R/generate_panels.R")
    shutil.copy2(patched, base_root / "src/R/generate_panels.R")

    p = subprocess.run(["git", "apply", "-R", "-p1", str(patch)],
                       cwd=base_root, capture_output=True, text=True)
    if p.returncode != 0:
        # git apply can refuse outside a work tree depending on the git
        # version; patch(1) does not care.
        p = subprocess.run(["patch", "-R", "-p1", "-s", "-i", str(patch)],
                           cwd=base_root, capture_output=True, text=True)
        if p.returncode != 0:
            raise Fail("could not reverse-apply m9b-axes.patch to recover "
                       f"the pre-M9B file:\n{p.stdout}\n{p.stderr}")

    if sha256(base_root / "src/R/generate_panels.R") == sha256(patched):
        raise Fail("reverse-applying the patch changed nothing -- the test "
                   "would compare the patched file against itself")

    for root, tag in ((base_root, "pre-M9B"), (new_root, "patched")):
        run_generator(root / "src/R/generate_panels.R", root, root / "panels")

    diffs = []
    for f in sorted((base_root / "panels").rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(base_root / "panels")
        other = new_root / "panels" / rel
        if not other.exists():
            diffs.append(f"{rel}: missing after the patch")
        elif sha256(f) != sha256(other):
            diffs.append(f"{rel}: bytes differ")
    for f in sorted((new_root / "panels").rglob("*")):
        if f.is_file():
            rel = f.relative_to(new_root / "panels")
            if not (base_root / "panels" / rel).exists():
                diffs.append(f"{rel}: new file the pre-M9B run did not write")

    n = sum(1 for f in (base_root / "panels").rglob("*") if f.is_file())
    seeds = []
    for root in (base_root, new_root):
        s = root / "results/raw/panel_seeds.csv"
        seeds.append(sha256(s) if s.exists() else None)
    if seeds[0] != seeds[1]:
        diffs.append("results/raw/panel_seeds.csv: bytes differ")

    report.append(("L1 legacy preservation: all four scenarios, "
                   f"{n} files byte-identical", not diffs,
                   "; ".join(diffs) if diffs else
                   f"A1-A4 x 2 arms x {TEST_ITERS} iterations, "
                   f"parquet + metadata.json + seed log"))


def gen_cells(donor: Path, work: Path, cells: list[tuple[int, int]]) -> Path:
    """Generate the M9-B cells needed by the world tests."""
    root = work / "m9b"
    (root / "src/R").mkdir(parents=True, exist_ok=True)
    shutil.copy2(donor / "src/R/generate_panels.R", root / "src/R/generate_panels.R")
    base = root / "panels"
    for t, g in cells:
        run_generator(root / "src/R/generate_panels.R", root, base,
                      "--post_days", str(t), "--n_control", str(g))
    return base


def cell_id(t: int, g: int) -> str:
    return f"M9B_T{t:02d}_G{g:02d}"


def check_world(base: Path, report: list) -> None:
    fixed_t, fixed_g = POST_DAYS[0], N_CONTROL[0]

    g_cells = {g: load_cell(base, cell_id(fixed_t, g)) for g in N_CONTROL}
    t_cells = {t: load_cell(base, cell_id(t, fixed_g)) for t in POST_DAYS}

    # ── W1: one treated geo, the same one in every cell ──────────────
    treated = set()
    for d in list(g_cells.values()) + list(t_cells.values()):
        treated |= set(d.loc[d.treated, "geo"].unique())
    report.append(("W1 treated geo identical across every cell",
                   len(treated) == 1,
                   f"treated = {sorted(treated)}"))

    # ── W2: the treated geo's own trajectory does not move with G_c ──
    ref = g_cells[fixed_g]
    ref_t = ref[ref.treated]
    msgs = []
    for g, d in g_cells.items():
        if g == fixed_g:
            continue
        err = identical(ref_t, d[d.treated], ["date", "Y", "Y_counterfactual"])
        if err:
            msgs.append(f"G={g}: {err}")
    report.append(("W2 treated Y and Y_counterfactual invariant in G_c",
                   not msgs, "; ".join(msgs) or
                   f"G_c in {N_CONTROL} at T={fixed_t}, "
                   f"{len(ref_t)} rows each, exact"))

    # ── W3: donor pools nest by prefix ───────────────────────────────
    # PER REPLICATION. Each replication draws its own permutation from its
    # own substream, so pooling replications would take the union of two
    # different pools and report a nesting failure that is not one.
    iterations = sorted(g_cells[fixed_g].iteration.unique())
    msgs, sizes = [], {}
    for it in iterations:
        sets = {g: set(d.loc[d.iteration == it, "geo"].unique())
                for g, d in g_cells.items()}
        sizes[int(it)] = [len(sets[g]) for g in N_CONTROL]
        for a, b in zip(N_CONTROL, N_CONTROL[1:]):
            if not sets[a] < sets[b]:
                msgs.append(f"it{it}: D{a} is not a strict subset of D{b} "
                            f"(extra: {sorted(sets[a] - sets[b])})")
            if len(sets[a]) != a + 1:
                msgs.append(f"it{it}: D{a} has {len(sets[a])} geos, "
                            f"expected {a + 1}")
    report.append((f"W3 donor pools nest: "
                   + " subset ".join(f"D{g}" for g in N_CONTROL),
                   not msgs, "; ".join(msgs) or
                   f"sizes {sizes} (1 treated + G_c), "
                   f"{len(iterations)} replications checked separately"))

    # ── W3b: the pool is the recorded permutation's prefix ───────────
    seeds = pd.read_csv(base / cell_id(fixed_t, N_CONTROL[-1]) / "panel_seeds.csv")
    msgs, shown = [], None
    for it in iterations:
        order = seeds.loc[seeds.iteration == it, "donor_order"].iloc[0].split("|")
        if shown is None:
            shown = order[:N_CONTROL[0]]
        if len(set(order)) != len(order) or len(order) != N_CONTROL[-1]:
            msgs.append(f"it{it}: donor_order is not a permutation of "
                        f"{N_CONTROL[-1]} distinct geos")
        for g in N_CONTROL:
            s = pd.read_csv(base / cell_id(fixed_t, g) / "panel_seeds.csv")
            row = s[s.iteration == it].iloc[0]
            if row.cell_donors.split("|") != order[:g]:
                msgs.append(f"it{it}: D{g} is not the first {g} of donor_order")
            # Weld the recorded provenance to the data on disk. Without this
            # the chain "panel geos <- cell_donors <- donor_order <- seed"
            # has a gap at its first link, and a seed log can describe a
            # slice that was never taken.
            on_disk = set(g_cells[g].loc[g_cells[g].iteration == it, "geo"])
            claimed = set(row.cell_donors.split("|")) | {row.treated_geo}
            if on_disk != claimed:
                msgs.append(f"it{it}: D{g} on disk != the seed log's claim "
                            f"(symmetric difference "
                            f"{sorted(on_disk ^ claimed)})")
    report.append(("W3b each pool is the prefix of one recorded permutation",
                   not msgs, "; ".join(msgs) or
                   f"donor_order[:{N_CONTROL[0]}] = {shown}"))

    # ── W3c [desc]: the pool is not a sorted-baseline prefix ─────────
    # Descriptive, not an assertion: a uniform permutation CAN begin with
    # City 1..City 5, so asserting it does not would be asserting that a
    # random draw avoided a particular value. The guarantee is structural
    # (sample.int on a dedicated substream); this only makes it visible.
    idx = sorted(int(n.split()[1]) for n in shown)
    report.append((f"W3c [desc] D{N_CONTROL[0]} City indices, replication "
                   f"{iterations[0]}: {idx} "
                   f"(a size-sorted prefix would read {list(range(1, N_CONTROL[0] + 1))})",
                   None, "not an assertion -- see the comment in the source"))

    # ── W3d: re-derive the permutation from the recorded seed alone ──
    # W3 and W3b would BOTH still pass if the donor order were the sorted
    # baseline prefix -- prefixes of a sorted list nest just as happily, and
    # "smaller pool" would silently also mean "donors closer to the treated
    # geo in size". This is the check that separates them, and it is exact,
    # not probabilistic: it recomputes sample.int() from perm_seed outside
    # the generator and demands the recorded order match element for element.
    msgs = []
    for it in iterations:
        row = seeds[seeds.iteration == it].iloc[0]
        treated_i = int(str(row.treated_geo).split()[1])
        n_world = int(row.world_n_geos)
        r = subprocess.run(
            [R_BIN, "-e",
             f'set.seed({int(row.perm_seed)}); '
             f'ci <- setdiff(seq_len({n_world}), {treated_i}); '
             f'cat(paste("City", ci[sample.int(length(ci))]), sep="|")'],
            capture_output=True, text=True,
            env={**os.environ, "R_LIBS_SITE": str(Path(args_donor) / R_LIBS)})
        if r.returncode != 0:
            raise Fail(f"could not re-derive the permutation:\n{r.stderr}")
        rederived = r.stdout.strip().split("|")
        recorded = str(row.donor_order).split("|")
        if rederived != recorded:
            k = next(i for i, (x, y) in enumerate(zip(rederived, recorded))
                     if x != y)
            msgs.append(f"it{it}: differs at position {k}: "
                        f"re-derived {rederived[k]}, recorded {recorded[k]}")
    report.append(("W3d donor order re-derived from perm_seed alone matches "
                   "the recorded one, exactly",
                   not msgs, "; ".join(msgs) or
                   f"sample.int on seed panel_seed+900000, "
                   f"{len(iterations)} replications x {N_CONTROL[-1]} geos, "
                   f"recomputed outside the generator"))

    # ── W4: durations nest by prefix ─────────────────────────────────
    msgs = []
    for a, b in zip(POST_DAYS, POST_DAYS[1:]):
        short, long = t_cells[a], t_cells[b]
        cut = long[long.date <= PRE_DAYS + a]
        err = identical(short, cut, ["geo", "date", "Y", "Y_counterfactual",
                                     "treated"])
        if err:
            msgs.append(f"T{a} != prefix(T{b}): {err}")
    report.append((f"W4 durations nest: "
                   + " == prefix of ".join(f"Y{t}" for t in POST_DAYS),
                   not msgs, "; ".join(msgs) or
                   f"G_c={fixed_g}, exact on Y and Y_counterfactual"))

    # ── W5: the counterfactual does not move with theta ──────────────
    msgs = []
    for name, d in (("G-cells", g_cells[fixed_g]), ("T-cells", t_cells[POST_DAYS[-1]])):
        arms = sorted(d.effect_label.unique())
        a0 = d[d.effect_label == arms[0]].drop(columns=["effect_label"])
        for arm in arms[1:]:
            a1 = d[d.effect_label == arm].drop(columns=["effect_label"])
            err = identical(a0, a1, ["geo", "date", "Y_counterfactual"])
            if err:
                msgs.append(f"{name} {arms[0]} vs {arm}: {err}")
            # and Y itself must agree everywhere the treatment is not applied
            pre0 = a0[(a0.date <= PRE_DAYS) | (~a0.treated)]
            pre1 = a1[(a1.date <= PRE_DAYS) | (~a1.treated)]
            err = identical(pre0, pre1, ["geo", "date", "Y"])
            if err:
                msgs.append(f"{name} untreated cells {arms[0]} vs {arm}: {err}")
    report.append(("W5 Y_counterfactual invariant in theta; Y invariant "
                   "outside the treated post-period",
                   not msgs, "; ".join(msgs) or
                   "common random numbers hold across arms"))

    # ── W6: the negative test ────────────────────────────────────────
    # Generate the maximal cell, strip it down to the smallest cell's geos
    # and days, and require equality. This is the test that fails if the
    # world was sized to the request rather than sliced from the maximum.
    small = load_cell(base, cell_id(POST_DAYS[0], N_CONTROL[0]))
    full = load_cell(base, cell_id(POST_DAYS[-1], N_CONTROL[-1]))
    msgs = []
    for it in iterations:
        s = small[small.iteration == it]
        keep_geo = set(s.geo.unique())          # per replication, as in W3
        stripped = full[(full.iteration == it)
                        & full.geo.isin(keep_geo)
                        & (full.date <= PRE_DAYS + POST_DAYS[0])]
        err = identical(s, stripped,
                        ["geo", "date", "Y", "Y_counterfactual", "treated"])
        if err:
            msgs.append(f"it{it}: {err}")
    report.append((f"W6 NEGATIVE TEST: "
                   f"strip({cell_id(POST_DAYS[-1], N_CONTROL[-1])}) == "
                   f"{cell_id(POST_DAYS[0], N_CONTROL[0])}",
                   not msgs, "; ".join(msgs) or
                   f"{len(small):,} rows over {len(iterations)} replications, "
                   f"exact, both axes stripped at once"))

    # ── W7: one world per replication, across cells ──────────────────
    rows = []
    for t, g in [(fixed_t, g) for g in N_CONTROL] + \
                [(t, fixed_g) for t in POST_DAYS] + \
                [(POST_DAYS[-1], N_CONTROL[-1])]:
        s = pd.read_csv(base / cell_id(t, g) / "panel_seeds.csv")
        s["cell"] = cell_id(t, g)
        rows.append(s)
    seeds = pd.concat(rows, ignore_index=True)
    msgs = []
    for it, grp in seeds.groupby("iteration"):
        if grp.panel_seed.nunique() != 1:
            msgs.append(f"iteration {it}: {grp.panel_seed.nunique()} "
                        f"distinct panel_seeds across cells")
        if grp.donor_order.nunique() != 1:
            msgs.append(f"iteration {it}: donor_order moves across cells")
        if grp.treated_geo.nunique() != 1:
            msgs.append(f"iteration {it}: treated_geo moves across cells")
    bad = seeds[seeds.perm_seed != seeds.panel_seed + 900000]
    if len(bad):
        msgs.append(f"{len(bad)} rows where perm_seed != panel_seed + 900000")
    if (seeds.world_n_geos != 41).any() or (seeds.world_total_days != 132).any():
        msgs.append("a cell recorded a world other than 41 geos x 132 days")
    report.append(("W7 one world per replication: panel_seed, donor_order, "
                   "treated_geo and world size constant across cells",
                   not msgs, "; ".join(msgs) or
                   f"{len(seeds)} seed records, "
                   f"{seeds.cell.nunique()} cells, "
                   f"{seeds.iteration.nunique()} replications"))


def check_one_panel_per_tool(donor: Path, report: list) -> None:
    """W8: every tool sees the same input panel.

    A source-level structural check, stated as such: it establishes that
    `run_panel` reads the parquet ONCE and derives all four tool formats
    from that one DataFrame. It is not a measurement of the four inputs.
    """
    sys.path.insert(0, str(donor / "src/python"))
    src = (donor / "src/python/run_tools.py").read_text()
    start = src.index("def run_panel(")
    end = src.index("\ndef ", start + 1)
    body = src[start:end]
    n_read = body.count("read_parquet")
    formats = ["to_causalpy_format(df", "to_google_mm_format(df",
               "to_geolift_format(df", 'df[["geo", "date", "Y"]]']
    missing = [f for f in formats if f not in body]
    ok = n_read == 1 and not missing
    report.append(("W8 [structural] run_panel reads the panel once and "
                   "derives all four tool inputs from it",
                   ok,
                   f"read_parquet x{n_read}; missing: {missing}" if not ok
                   else "1 read_parquet, 4 formats all derived from `df`"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--donor", default="/home/user/donor-smoke")
    ap.add_argument("--work", default=None,
                    help="scratch dir; a temp dir under it is reused")
    ap.add_argument("--skip-legacy", action="store_true",
                    help="skip L1 only (it runs the generator twice more)")
    a = ap.parse_args()

    global args_donor
    args_donor = a.donor
    donor = Path(a.donor).resolve()
    work = Path(a.work or (Path(os.environ.get("TMPDIR", "/tmp")) / "m9b_check"))
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print("=" * 74)
    print("M9-B world contract: metamorphic tests")
    print("=" * 74)
    print(f"donor clone : {donor}")
    print(f"generator   : sha256 {sha256(donor / 'src/R/generate_panels.R')}")
    print(f"R           : {R_BIN}")
    print(f"grid        : T in {POST_DAYS}, G_c in {N_CONTROL}, "
          f"thetas {TEST_THETAS}, {TEST_ITERS} iterations\n")

    report: list = []
    try:
        if not a.skip_legacy:
            print("generating the legacy comparison (two full four-scenario "
                  "runs)...")
            check_legacy(donor, work, report)
        else:
            report.append(("L1 legacy preservation", None, "SKIPPED"))

        cells = ([(POST_DAYS[0], g) for g in N_CONTROL]
                 + [(t, N_CONTROL[0]) for t in POST_DAYS[1:]]
                 + [(POST_DAYS[-1], N_CONTROL[-1])])
        print(f"generating {len(cells)} M9-B cells...")
        base = gen_cells(donor, work, cells)
        check_world(base, report)
        check_one_panel_per_tool(donor, report)
    except Fail as e:
        print(f"\nHARNESS FAILURE: {e}")
        return 2

    print()
    n_pass = n_fail = 0
    for name, ok, detail in report:
        if ok is None:
            mark = "  ·  "
        elif ok:
            mark = " PASS"
            n_pass += 1
        else:
            mark = " FAIL"
            n_fail += 1
        print(f"[{mark}] {name}")
        print(f"         {detail}")

    print()
    print("=" * 74)
    if n_fail:
        print(f"M9-B WORLD CONTRACT: REFUSED -- {n_fail} of {n_pass + n_fail} "
              f"checks failed. Do not freeze, do not run cells.")
    else:
        print(f"M9-B WORLD CONTRACT: {n_pass}/{n_pass + n_fail} checks pass.")
        print("The axes mean what they say: every cell is a slice of one "
              "world.")
    print("=" * 74)
    print("\nWhat this does NOT establish: that the world resembles a real "
          "marketing\nexperiment. It is the same synthetic DGP, with the "
          "same limitation, sliced\nhonestly instead of dishonestly.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
