#!/usr/bin/env python
"""Compare a fresh donor run against the donor's published results.

Implements levels R1 and R2 of the reproducibility ladder in
`docs/donor-repro.md`, against tolerances fixed in that document *before*
this script ever ran. It does not choose tolerances; it applies them.

    R1  generated-data replay   did the DGP reproduce?
    R2  estimator replay        did the four tools reproduce?

Why R1 is an effect-arm test
----------------------------
The donor ships no panels -- `panels/` is gitignored -- so there is no
upstream artefact to hash. The comparison has to run through a published
quantity that is a function of the generated panel, and `true_att_level`
(mean(Y - Y_counterfactual) over the treated post-period) is one: 4,000
distinct values on the effect arm, one per (scenario, iteration), agreed by
all four tools.

On the null arm theta = 0, so Y == Y_cf identically and `true_att_level` is
exactly 0.0 for every row -- one distinct value across 16,000 rows. It
carries no information about the panel at all. Reporting DGP agreement from
the null arm would be reporting that zero equals zero, so R1 refuses to
score it.

Tolerances (docs/donor-repro.md 4b)
-----------------------------------
    google_mm     1e-9 relative on att_level
    geolift       5e-5 absolute   <- censored by the donor's 4-dp output
    causalimpact  5e-5 absolute   <- same
    causalpy      two levels against its own posterior, never per-row equality

The two 5e-5 entries are as tight as the artefact allows, not as tight as
the tools deserve. Agreement there means "reproduced to the precision the
donor published" and nothing stronger; the script says so in its verdict.

    python replay_check.py --fresh /home/user/donor-smoke/results/raw/results.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PUBLISHED = (
    "/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl"
)

#: Per-tool per-row tolerance on `att_level`, from docs/donor-repro.md 4b.
#: `censored` marks a tolerance set by the donor's published precision rather
#: than by the tool, which changes how a pass may be described.
TOLERANCE = {
    "google_mm":    {"kind": "relative", "value": 1e-9, "censored": False},
    "geolift":      {"kind": "absolute", "value": 5e-5, "censored": True},
    "causalimpact": {"kind": "absolute", "value": 5e-5, "censored": True},
    "causalpy":     {"kind": "stochastic", "value": None, "censored": False},
}

#: causalpy level 1: a quarter of its own median CI half-width, in pp.
CAUSALPY_ROW_TOL_PP = 2.59
#: causalpy level 2: mean difference within this many standard errors.
CAUSALPY_SE_MULTIPLE = 2.0

KEYS = ["scenario", "effect_label", "iteration", "tool", "posterior_type"]


def load(path: str) -> pd.DataFrame:
    rows = [json.loads(line) for line in Path(path).open()]
    d = pd.DataFrame(rows)
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    return d


def align(pub: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    """Inner-join on the run identity. Only rows present in both are scored."""
    a = pub.set_index(KEYS).add_suffix("_pub")
    b = fresh.set_index(KEYS).add_suffix("_new")
    dup = [x for x in (a, b) if x.index.duplicated().any()]
    if dup:
        raise SystemExit(
            "duplicate (scenario, effect_label, iteration, tool, "
            "posterior_type) keys -- the run identity is not unique, and a "
            "join on it would compare arbitrary pairs")
    return a.join(b, how="inner")


# ---------------------------------------------------------------- R1

def check_r1(j: pd.DataFrame) -> dict:
    """Did the DGP reproduce? Effect arm only -- see the module docstring."""
    eff = j.xs("effect", level="effect_label")
    if eff.empty:
        return {"verdict": "NO DATA", "n": 0}

    d = (eff.true_att_level_new - eff.true_att_level_pub).abs()
    rel = d / eff.true_att_level_pub.abs()
    finite = np.isfinite(d)

    # The DGP is R code producing float64; agreement should be at machine
    # precision or not at all. There is no legitimate middle ground here,
    # because no estimator is involved.
    n_exact = int((d[finite] < 1e-9).sum())
    n = int(finite.sum())

    # Distinctness guard: if the fingerprints are not distinct, agreement is
    # not evidence. Counted per PANEL -- (scenario, iteration) -- not per row,
    # because all four tools report the same true_att_level for one panel and
    # counting rows would make a fine set look degenerate.
    panels = eff.reset_index()[["scenario", "iteration", "true_att_level_pub"]]
    panels = panels.drop_duplicates(subset=["scenario", "iteration"])
    distinct = int(panels.true_att_level_pub.round(9).nunique())

    return {
        "verdict": "PASS" if n and n_exact == n else "FAIL",
        "n": n,
        "n_exact": n_exact,
        "max_abs": float(d[finite].max()) if n else float("nan"),
        "max_rel": float(rel[finite].max()) if n else float("nan"),
        "distinct_fingerprints": distinct,
        "panels": int(len(panels)),
    }


# ---------------------------------------------------------------- R2

def check_r2_exact(g: pd.DataFrame, tol: dict) -> dict:
    d = (g.att_level_new - g.att_level_pub).abs()
    if tol["kind"] == "relative":
        scale = g.att_level_pub.abs().replace(0, np.nan)
        m = d / scale
    else:
        m = d
    finite = np.isfinite(m)
    n = int(finite.sum())
    within = int((m[finite] <= tol["value"]).sum())
    sig = (g.significant_new == g.significant_pub)
    return {
        "n": n,
        "within": within,
        "worst": float(m[finite].max()) if n else float("nan"),
        "sig_agree": int(sig.sum()),
        "sig_n": int(len(sig)),
        "verdict": "PASS" if n and within == n and sig.all() else "FAIL",
    }


def check_r2_stochastic(g: pd.DataFrame) -> dict:
    """causalpy: judged against its own posterior, never against zero."""
    a = g.att_pct_new.astype(float) * 100
    b = g.att_pct_pub.astype(float) * 100
    d = (a - b)
    finite = np.isfinite(d)
    d = d[finite]
    n = len(d)
    if n == 0:
        return {"verdict": "NO DATA", "n": 0}

    # Level 1: per row, against a quarter of its own median CI half-width.
    l1_within = int((d.abs() <= CAUSALPY_ROW_TOL_PP).sum())

    # Level 2 (binding): the mean difference against its standard error on
    # THIS sample -- not the 1,000-iteration SE, which would be far tighter
    # than the 20 rows actually being compared.
    se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    l2_ok = bool(abs(float(d.mean())) <= CAUSALPY_SE_MULTIPLE * se) if n > 1 \
        else False

    wid_new = (g.ci_upper_new - g.ci_lower_new).astype(float) * 100
    wid_pub = (g.ci_upper_pub - g.ci_lower_pub).astype(float) * 100
    sig = (g.significant_new == g.significant_pub)

    return {
        "n": n,
        "l1_within": l1_within,
        "mean_diff_pp": float(d.mean()),
        "se_pp": se,
        "l2_ok": l2_ok,
        "ci_width_ratio": float(np.nanmedian(wid_new) / np.nanmedian(wid_pub)),
        "sig_agree": int(sig.sum()),
        "sig_n": int(len(sig)),
        # Level 2 is the binding test; level 1 is reported, not decisive.
        "verdict": "PASS" if l2_ok else "FAIL",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", default=PUBLISHED)
    ap.add_argument("--fresh", required=True)
    args = ap.parse_args()

    pub, fresh = load(args.published), load(args.fresh)
    j = align(pub, fresh)
    if j.empty:
        raise SystemExit("no overlapping rows between the two result sets")

    print(f"published {len(pub):,} rows | fresh {len(fresh):,} rows | "
          f"compared {len(j):,}\n")

    # ---- R1
    r1 = check_r1(j)
    print("== R1: did the DGP reproduce? (effect arm only) ==")
    if r1["n"]:
        print(f"  {r1['n_exact']:,}/{r1['n']:,} true_att_level values exact "
              f"to 1e-9   max abs {r1['max_abs']:.3g}")
        print(f"  fingerprint distinctness: {r1['distinct_fingerprints']:,} "
              f"distinct over {r1['panels']:,} panels")
        if r1["distinct_fingerprints"] < r1["panels"]:
            print("  WARNING: fingerprints are not distinct -- agreement here "
                  "is weak evidence")
    print(f"  verdict: {r1['verdict']}")
    print("  (the null arm is excluded by construction: true_att_level is "
          "identically 0.0\n   there, so it cannot testify about the panel)\n")

    # ---- R2
    print("== R2: did the estimators reproduce? ==")
    rows, verdicts = [], {}
    for (tool, pt), g in j.groupby(level=["tool", "posterior_type"]):
        tol = TOLERANCE.get(tool)
        if tol is None:
            continue
        if tol["kind"] == "stochastic":
            res = check_r2_stochastic(g)
            detail = (f"mean d {res['mean_diff_pp']:+.4f}pp vs "
                      f"{CAUSALPY_SE_MULTIPLE:.0f}xSE "
                      f"{CAUSALPY_SE_MULTIPLE * res['se_pp']:.4f}pp | "
                      f"L1 {res['l1_within']}/{res['n']} | "
                      f"CI width x{res['ci_width_ratio']:.3f}")
        else:
            res = check_r2_exact(g, tol)
            unit = "rel" if tol["kind"] == "relative" else "abs"
            detail = (f"{res['within']}/{res['n']} within "
                      f"{tol['value']:g} {unit} | worst {res['worst']:.3g}")
        label = f"{tool}" + (f"[{pt}]" if pt else "")
        note = "  (censored by 4-dp output)" if tol["censored"] else ""
        print(f"  {label:22s} {res['verdict']:5s}  {detail}")
        print(f"  {'':22s}        significant agrees "
              f"{res['sig_agree']}/{res['sig_n']}{note}")
        verdicts[label] = res["verdict"]
        rows.append(dict(tool=label, **res))

    # ---- overall
    censored = [t for t in TOLERANCE if TOLERANCE[t]["censored"]]
    ok = r1["verdict"] == "PASS" and all(v == "PASS" for v in verdicts.values())
    print(f"\n== G3 verdict: {'PASS' if ok else 'FAIL'} ==")
    if ok:
        print("  R1 reproduced exactly. R2 reproduced within the "
              "preregistered tolerances.")
        print(f"  For {', '.join(censored)} this means 'to the precision the "
              f"donor published'\n  (4 decimal places) and nothing stronger.")
    else:
        print("  Investigate before proceeding. A tolerance is not to be "
              "widened after\n  seeing this output -- record the "
              "disagreement in docs/failures.md instead.")

    Path("replay_check_results.json").write_text(
        json.dumps({"r1": r1, "r2": rows}, indent=2, default=float))
    print("\nwrote replay_check_results.json")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
