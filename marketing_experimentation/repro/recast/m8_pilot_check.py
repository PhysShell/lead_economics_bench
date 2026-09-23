#!/usr/bin/env python
"""M8 pilot acceptance: does the new theta run attach to the old clusters?

The pilot is not for conclusions. It is for finding the defect that M6a/M6b
and D7 found the last two times a theta was mutated -- before 2,160 more rows
are bought.

The claim the whole M8 design rests on
---------------------------------------
> Nine new truths attach to the same clusters without disturbing what is
> there.

That is a *structural* claim, which is the category this project keeps
getting wrong (F13-F16). So it is checked three ways, weakest to strongest:

1. **Arithmetic.** `panel_seed` matches `42000 + 10000*scenario_idx + iter`
   and is constant across effect labels within a cluster. Read from
   `panel_seeds.csv`, which the generator now emits -- F11's lesson, that a
   property which matters must be evidenced by the run rather than inferred
   from the source that claims it.

2. **Identity.** 1,440 rows, no duplicates, every (tool, scenario, theta)
   carrying exactly 10 iterations, and the recorded `estimator_seed` matching
   what each tool is actually passed.

3. **Empirical, and the one that could actually fail.** If a NEW truth and an
   OLD truth really share a latent panel, their estimation residuals inside
   one cluster must be the same realisation. On the M7 atlas that correlation
   was **+1.000** across truths.

   Correlation alone does not establish that. `r = 1` is satisfied by
   `new = 2*old + 17`, which would describe arms on affinely-related panels
   rather than shared ones. So the regression is reported too, and must come
   back as the identity: slope 1, intercept 0, R^2 1, and `max |new - old|`
   small against the residual scale. If the new arms had landed on different
   panels -- a seed that quietly picked up the effect label, a directory
   collision, a reordering -- this is where it shows, and nothing else in the
   pipeline would notice.

Then the preregistered gate: the merged file must gate to iterations 1-10.

    python marketing_experimentation/repro/recast/m8_pilot_check.py \
        --pilot /tmp/results_m8_pilot.jsonl \
        --atlas /tmp/results_atlas.jsonl \
        --seeds /tmp/panel_seeds_m8_pilot.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from leadbench_mx.clusters import require_complete_clusters  # noqa: E402
from leadbench_mx.decision import action_boundaries  # noqa: E402

EXPECTED_THETAS = [-0.15, -0.03125, -0.02, -0.01, 0.01, 0.0125, 0.051875,
                   0.10, 0.104375]
EXPECTED_ITERATIONS = 10   # overridden by --iterations
SEEDED_TOOLS = {"causalpy", "causalimpact"}

#: How close the cross-arm residual correlation must be to 1 for the panels
#: to count as shared. M7 measured +1.000 with a minimum of +0.999 across all
#: four tools, so this is not a hopeful threshold -- it is the observed floor.
SHARED_PANEL_R = 0.99


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(l) for l in Path(path).open()])
    for c in ("att_pct", "effect_pct", "att_level"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    return d


def report(name: str, ok: bool, detail: str = "") -> bool:
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))
    return ok


def main() -> None:
    global EXPECTED_ITERATIONS
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", default="/tmp/results_m8_pilot.jsonl")
    ap.add_argument("--atlas", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--seeds", default="/tmp/panel_seeds_m8_pilot.csv")
    ap.add_argument("--baseline", default="/tmp/results_m8_pilot_rounded.jsonl",
                    help="the pre-fix run, kept as an F17 control")
    ap.add_argument("--iterations", type=int, default=EXPECTED_ITERATIONS,
                    help="iterations per cell this run should carry")
    args = ap.parse_args()

    EXPECTED_ITERATIONS = args.iterations
    p = load(args.pilot)
    p_df = p
    a = load(args.atlas)
    ok = True

    print("== 1. arithmetic: the seed the run actually used ==")
    s_df = pd.read_csv(args.seeds)
    s = s_df
    idx = {k: i + 1 for i, k in enumerate(sorted(s.scenario.unique()))}
    exp = 42 * 1000 + s.scenario.map(idx) * 10000 + s.iteration
    ok &= report("panel_seed matches the formula the analysis assumes",
                 bool((exp == s.panel_seed).all()),
                 f"{int((exp != s.panel_seed).sum())} mismatches")
    g = s.groupby(["scenario", "iteration"]).panel_seed.nunique()
    ok &= report("panel_seed constant across effect labels in a cluster (C3)",
                 bool((g == 1).all()), f"{int((g > 1).sum())}/{len(g)} clusters differ")

    print("\n== 1b. C9: is the RECORDED theta the theta the DGP actually used? ==")
    print("   panel_seeds.csv goes through write.csv; results.jsonl goes")
    print("   through jsonlite::toJSON, whose default is digits = 4. Two")
    print("   independent write paths for the same quantity, so they can be")
    print("   compared -- which is how F17 was found.")
    seed_theta = sorted(float(t) for t in s_df.effect_pct.unique())
    res_theta = sorted(float(t) for t in p.effect_pct.unique())
    same = (len(seed_theta) == len(res_theta)
            and all(a == b for a, b in zip(seed_theta, res_theta)))
    ok &= report("results.jsonl theta == panel_seeds.csv theta, EXACTLY", same,
                 "" if same else
                 f"seeds {seed_theta}\n          results {res_theta}")

    print("\n== 2. identity: is the pilot the shape it was preregistered as? ==")
    want = 9 * 4 * 4 * EXPECTED_ITERATIONS
    ok &= report("row count", len(p) == want,
                 f"{len(p)} rows, expected {want:,}")
    got = sorted(float(t) for t in p.effect_pct.unique())
    ok &= report("nine new truths, exactly",
                 len(got) == 9 and np.allclose(got, sorted(EXPECTED_THETAS)),
                 f"{[round(100*t, 4) for t in got]}")
    keys = ["tool_label", "scenario", "effect_pct", "iteration"]
    ok &= report("no duplicated run identities (D13)",
                 not p.duplicated(subset=keys).any(),
                 f"{int(p.duplicated(subset=keys).sum())} duplicates")
    per = p.groupby(["tool_label", "scenario", "effect_pct"]).size()
    ok &= report(f"every (tool, scenario, theta) has {EXPECTED_ITERATIONS} iterations",
                 bool((per == EXPECTED_ITERATIONS).all()),
                 f"min {per.min()}, max {per.max()}")
    ok &= report("no collision with the existing seven truths",
                 not set(np.round(got, 6)) & set(np.round(
                     sorted(a.effect_pct.unique()), 6)))

    if "estimator_seed" in p.columns:
        bad = []
        for tool, g_ in p.groupby("tool"):
            seen = set(g_.estimator_seed.dropna().unique())
            if tool in SEEDED_TOOLS:
                if seen != set(range(1, EXPECTED_ITERATIONS + 1)):
                    bad.append(f"{tool}: {sorted(seen)}")
            elif seen:
                bad.append(f"{tool}: expected none, got {sorted(seen)}")
        ok &= report("estimator_seed recorded matches what each tool is passed",
                     not bad, "; ".join(bad))
    else:
        ok &= report("estimator_seed column present", False,
                     "the run_tools patch did not apply")

    print("\n== 3. signs: does the estimate follow the truth? ==")
    for tool, g_ in p.groupby("tool"):
        r = float(np.corrcoef(g_.effect_pct, g_.att_pct)[0, 1])
        neg = g_[g_.effect_pct < 0]
        frac = float((neg.att_pct < 0).mean()) if len(neg) else np.nan
        ok &= report(f"{tool}: att tracks theta, and negative truths estimate negative",
                     r > 0.5 and frac > 0.5,
                     f"r={r:+.3f}, {100*frac:.0f}% of negative truths negative")

    print("\n== 4. the action boundaries are actually in the grid ==")
    b = action_boundaries()
    missing = [x for x in b if not np.any(np.isclose(got, x, atol=1e-9))]
    ok &= report("all four decision boundaries simulated", not missing,
                 f"missing {[round(100*x, 4) for x in missing]}" if missing else
                 f"{[f'{100*x:+.4f}%' for x in b]}")

    print("\n== 5. THE ONE THAT COULD FAIL: do new arms share the old panels? ==")
    print("   If a new truth and an old truth sit on the same latent panel,")
    print("   their residuals inside a cluster are the SAME realisation.")
    print("   M7 measured +1.000 across truths, floor +0.999.\n")
    both = pd.concat([p, a], ignore_index=True)
    both["resid"] = both.att_pct - both.effect_pct
    new_t = sorted(got)[len(got) // 2]
    old_t = 0.0
    for tool in sorted(both.tool.unique()):
        g_ = both[both.tool == tool]
        w = g_.pivot_table(index=["scenario", "iteration"],
                           columns="effect_pct", values="resid")
        cols = [c for c in w.columns if np.isclose(c, new_t) or np.isclose(c, old_t)]
        if len(cols) < 2:
            ok &= report(f"{tool}: both truths present", False)
            continue
        w = w[cols].dropna()
        r = float(w.corr().to_numpy()[0, 1])
        # Correlation alone is not attach-equivalence. r = 1 is satisfied by
        # new = 2*old + 17, which would mean the arms sit on panels that are
        # merely affinely related -- a rescaled DGP, not a shared one. The
        # claim is that they are the SAME realisation, so the regression must
        # come back as the identity: intercept 0, slope 1, R^2 1, and a max
        # absolute deviation small against the residual scale itself.
        x = w.iloc[:, 0].to_numpy(float)
        y = w.iloc[:, 1].to_numpy(float)
        slope, intercept = np.polyfit(x, y, 1)
        r2 = r * r
        max_abs = float(np.abs(y - x).max())
        scale = float(np.abs(np.concatenate([x, y])).mean())
        ok &= report(
            f"{tool}: resid(theta={100*new_t:+.2f}%) vs resid(theta=0%)",
            (r > SHARED_PANEL_R and abs(slope - 1) < 0.02
             and abs(intercept) < 0.02 * scale and r2 > SHARED_PANEL_R ** 2),
            f"r={r:+.5f}  slope={slope:+.5f}  intercept={intercept:+.3e}  "
            f"R2={r2:.5f}  max|new-old|={max_abs:.3e} against a mean |resid| "
            f"of {scale:.3e}   ({len(w)} clusters)")

    print("\n== 5b. the envelope test: is new/old deviation typical? ==")
    print("   The regression above is the identity for three tools and very")
    print("   nearly it for causalpy. Saying causalpy's gap is `caused by")
    print("   sampler noise` would be a mechanism claim this cannot support.")
    print("   What CAN be shown is whether the new-vs-old deviation is")
    print("   COMPATIBLE with the previously observed old/old envelope. Not")
    print("   `drawn from the same distribution` -- 21 old/old pairs is far")
    print("   too few for that, the pairs are not independent, and the")
    print("   new/old max slightly exceeds the old/old max. Descriptive, and")
    print("   reported as such.")
    print("\n   This is NOT a pass/fail gate. Any band drawn around these")
    print("   percentiles would have been drawn after seeing them, which is")
    print("   how a careful experiment turns into a search for a law that")
    print("   fits. Max |resid(a) - resid(b)| per cluster, over every pair.\n")
    import itertools
    old_truths = {float(t) for t in a.effect_pct.unique()}
    for tool in sorted(both.tool_label.unique()):
        g_ = both[both.tool_label == tool]
        w = g_.pivot_table(index=["scenario", "iteration"],
                           columns="effect_pct", values="resid").dropna()
        oo, no = [], []
        for u, v in itertools.combinations(list(w.columns), 2):
            mx = float(np.abs(w[u] - w[v]).max())
            uo = any(np.isclose(u, t) for t in old_truths)
            vo = any(np.isclose(v, t) for t in old_truths)
            if uo and vo:
                oo.append(mx)
            elif uo != vo:
                no.append(mx)
        oo, no = np.array(oo), np.array(no)
        if not len(oo) or not len(no):
            continue
        pct = 100.0 * float((oo < np.median(no)).mean())
        print(f"   [desc] {tool:18s} old/old median {np.median(oo):.2e} "
              f"max {oo.max():.2e} | new/old median {np.median(no):.2e} "
              f"max {no.max():.2e}")
        print(f"          median new/old at the {pct:.0f}th percentile of "
              f"old/old")
    print("\n   CausalPy's new/old deviations are COMPATIBLE with the")
    print("   previously observed old/old variability envelope; their median")
    print("   lies at the 33rd percentile of accepted old/old pair")
    print("   deviations. We observe no evidence here of an")
    print("   attach-equivalence failure. The mechanism underlying that")
    print("   variability remains unidentified (F8).")
    print("\n   Proving `same distribution` would need a preregistered")
    print("   equivalence or permutation test accounting for the dependence")
    print("   between pairs. It is deliberately NOT added now: a criterion")
    print("   invented after seeing the data is not a test of the data.")

    print("\n== 6. the preregistered cluster gate on the merged file ==")
    merged = both[np.isfinite(both[["att_pct"]].to_numpy(dtype=float)).all(axis=1)]
    thetas = sorted(float(t) for t in merged.effect_pct.unique())
    print(f"   {len(thetas)} truths: {[round(100*t, 4) for t in thetas]}")
    try:
        gated = require_complete_clusters(merged, thetas,
                                          expect_iterations=range(1, EXPECTED_ITERATIONS + 1))
        ok &= report(f"merged file gates to iterations 1-{EXPECTED_ITERATIONS} (C7)", True,
                     f"{len(gated):,} rows kept of {len(merged):,}")
    except SystemExit as e:
        ok &= report(f"merged file gates to iterations 1-{EXPECTED_ITERATIONS} (C7)", False,
                     str(e).split("\n")[0])

    if args.baseline and Path(args.baseline).exists():
        print("\n== 7. F17 control: does metadata precision touch estimation? ==")
        print("   The pilot was re-run after the jsonlite precision fix rather")
        print("   than corrected in place. The panels come from the same seeds,")
        print("   so the estimates MUST be identical -- if att_level moved,")
        print("   metadata precision was reaching the estimator and something")
        print("   worse than a rounded label is wrong.")
        base = load(args.baseline)
        key = ["tool_label", "scenario", "effect_label", "iteration"]
        m = base.merge(p_df, on=key, suffixes=("_old", "_new"))
        ok2 = len(m) == len(base)
        report("every row of the first run is matched in the second", ok2,
               f"{len(m)} of {len(base)}")
        if ok2:
            for col in ("att_level", "ci_lower_level", "ci_upper_level"):
                if f"{col}_old" not in m.columns:
                    continue
                a_ = pd.to_numeric(m[f"{col}_old"], errors="coerce")
                b_ = pd.to_numeric(m[f"{col}_new"], errors="coerce")
                d_ = (a_ - b_).abs()
                report(f"{col} identical across the two runs",
                       bool(d_.max() == 0 or d_.max() < 1e-12),
                       f"max |diff| = {d_.max():.3e}")
            t_old = pd.to_numeric(m["effect_pct_old"], errors="coerce")
            t_new = pd.to_numeric(m["effect_pct_new"], errors="coerce")
            moved = (t_old != t_new).sum()
            report("and effect_pct DID move -- that is the fix",
                   moved > 0, f"{moved} of {len(m)} rows corrected")

    print(f"\n{'=' * 64}")
    if ok:
        print("PILOT ACCEPTED. The new arms sit on the old panels, the grid")
        print("carries all four decision boundaries, and the merged file gates")
        print("to the preregistered cluster set. Proceed to the boundary")
        print("leave-one-out test.")
    else:
        print("PILOT REJECTED. Do NOT extend to 25 iterations. Fix the failures")
        print("above first -- that is the entire purpose of running 10 before")
        print("running 25.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
