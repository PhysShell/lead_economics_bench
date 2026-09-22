#!/usr/bin/env python
"""How much business value is destroyed by compressing an experiment result?

The question this track is now about. An experiment produces a rich object;
the decision consumes a progressively poorer summary of it:

    S3  estimate + interval + method diagnostics
    S2  estimate + interval width
    S1  point estimate only
    S0  one bit: significant / not

If S0 and S1 are genuine coarsenings of S2, then a decision-maker using each
optimally must satisfy

    EVSI(S3) >= EVSI(S2) >= EVSI(S1) >= EVSI(S0)

up to Monte Carlo and density-estimation error. Measuring the gaps prices
information compression in currency, per method.

A caveat that is not optional here
----------------------------------
Each rung adds a dimension to a kernel density estimated from ~500 held-out
runs per arm. In higher dimensions that estimate degrades, and a degraded
density *lowers* measured EVSI. So a violation of monotonicity is ambiguous
between "this rung carries no extra information" and "the KDE ran out of
data". `--bandwidth-scan` exists to tell those apart: if the ordering is
stable across bandwidths and sample sizes, it is information; if it moves, it
is estimation error. Reported either way.

    python marketing_experimentation/scripts/information_ladder.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import two_point_problem  # noqa: E402

#: What each rung of the ladder lets the decision-maker see.
RUNGS: dict[str, list[str]] = {
    "S0_significance_bit": [],          # handled separately: discrete
    "S1_point_estimate": ["att_pct"],
    "S2_estimate_plus_ci": ["att_pct", "ci_width"],
    "S3_plus_diagnostics": ["att_pct", "ci_width", "diagnostic"],
}

#: Tool-specific diagnostic used for S3. Not every tool emits one.
DIAGNOSTIC = {
    "google_mm": "r_squared",
    "causalpy": "rhat_max",
    "geolift": "p_value",
    "causalimpact": None,
}


def tool_labels(d: pd.DataFrame) -> pd.DataFrame:
    """A tool's identity includes its posterior type.

    CausalPy can emit `mu` (parameter uncertainty) or `y_hat` (posterior
    predictive, which adds observation noise). Recast published only `y_hat`,
    so on the published file this is a no-op. On any file containing both,
    pooling them would average two different signals into one likelihood and
    the EVSI would describe neither.
    """
    if "posterior_type" not in d.columns:
        d = d.assign(posterior_type="")
    d = d.copy()
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    return d


def prepare(d: pd.DataFrame, tool_label: str, scenario: str) -> pd.DataFrame:
    g = d[(d.tool_label == tool_label) & (d.scenario == scenario)].copy()
    g["ci_width"] = g.ci_upper - g.ci_lower
    diag = DIAGNOSTIC.get(g.tool.iloc[0] if len(g) else "")
    if diag and diag in g.columns and g[diag].notna().any():
        g["diagnostic"] = pd.to_numeric(g[diag], errors="coerce")
    else:
        g["diagnostic"] = np.nan
    return g


def arms(g: pd.DataFrame) -> list[str]:
    """The two arms, ordered null-first, read from the data.

    Not hard-coded as ("null", "effect"): that is the pair of labels one
    particular theta happens to produce, and reading a magnitude off a label
    is the defect recorded as D7. Ordered by effect size so index 0 is always
    the null state the decision problem expects.
    """
    order = (g.groupby("effect_label").effect_pct.median()
             .sort_values().index.tolist())
    return order


def split(g: pd.DataFrame, cols: list[str], seed: int, frac_fit: float = 0.5):
    """Fit/evaluate split, per truth, so no density scores its own points."""
    rng = np.random.default_rng(seed)
    fit, ev = {}, {}
    labels = arms(g)
    if len(labels) != 2:
        return None, None
    for j, label in enumerate(labels):
        sub = g[g.effect_label == label]
        X = sub[cols].to_numpy(dtype=float)
        X = X[np.isfinite(X).all(axis=1)]
        if len(X) < 20:
            return None, None
        idx = rng.permutation(len(X))
        cut = int(frac_fit * len(X))
        fit[j], ev[j] = X[idx[:cut]], X[idx[cut:]]
    return fit, ev


def evsi_continuous(problem, fit, ev, bw: float | str = "scott") -> float:
    """EVSI when the decision sees the full continuous signal."""
    kdes = {}
    for j, X in fit.items():
        if X.shape[1] == 1:
            kdes[j] = gaussian_kde(X[:, 0], bw_method=bw)
        else:
            kdes[j] = gaussian_kde(X.T, bw_method=bw)
    total = 0.0
    for j, X in ev.items():
        pts = X[:, 0] if X.shape[1] == 1 else X.T
        like = np.vstack([np.clip(kdes[k](pts), 1e-300, None) for k in (0, 1)]).T
        post = problem.prior * like
        post /= np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
        total += problem.prior[j] * float((post @ problem.utility.T).max(axis=1).mean())
    return total - problem.value_no_experiment()


def evsi_binary(problem, g: pd.DataFrame) -> float:
    """EVSI for the one-bit significance signal, used optimally."""
    labels = arms(g)
    p_sig = np.array([
        float(g[g.effect_label == lab].significant.mean()) for lab in labels
    ])
    like = np.vstack([1.0 - p_sig, p_sig])
    marg = like @ problem.prior
    total = 0.0
    for y in range(2):
        post = problem.prior * like[y]
        s = post.sum()
        post = post / s if s > 0 else problem.prior
        total += marg[y] * float((problem.utility @ post).max())
    return total - problem.value_no_experiment()


def ladder_for(problem, g: pd.DataFrame, seed: int, bw="scott") -> dict:
    out = {"S0_significance_bit": evsi_binary(problem, g)}
    for rung, cols in RUNGS.items():
        if not cols:
            continue
        if "diagnostic" in cols and not g["diagnostic"].notna().any():
            out[rung] = np.nan
            continue
        fit, ev = split(g, cols, seed)
        out[rung] = np.nan if fit is None else evsi_continuous(problem, fit, ev, bw)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results",
        default="/home/user/getrecast/geolift-simulation-study/results/raw/results.jsonl")
    ap.add_argument("--scenario", default="A1")
    ap.add_argument("--prior", type=float, default=0.4)
    ap.add_argument("--c-fn", type=float, default=500_000.0)
    ap.add_argument("--ratio", type=float, default=1.0)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--bandwidth-scan", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="does the S0 retention survive the business plane?")
    args = ap.parse_args()

    d = tool_labels(pd.DataFrame(
        [json.loads(l) for l in Path(args.results).open()]))
    tools = sorted(d.tool_label.unique())
    problem = two_point_problem(args.prior, args.ratio * args.c_fn, args.c_fn)

    print(f"scenario {args.scenario} | prior P(effect)={args.prior} | "
          f"C_FP/C_FN={args.ratio} | C_FN=${args.c_fn:,.0f}")
    print(f"EVPI ceiling ${problem.evpi():,.0f} | {args.seeds} "
          f"fit/eval splits per cell\n")

    rows = []
    for tool in tools:
        g = prepare(d, tool, args.scenario)
        per_seed = [ladder_for(problem, g, seed) for seed in range(args.seeds)]

        def _mean(key):
            vals = [p[key] for p in per_seed]
            vals = [v for v in vals if np.isfinite(v)]
            return float(np.mean(vals)) if vals else np.nan

        def _sd(key):
            vals = [p[key] for p in per_seed]
            vals = [v for v in vals if np.isfinite(v)]
            return float(np.std(vals)) if len(vals) > 1 else np.nan

        agg = {k: _mean(k) for k in per_seed[0]}
        sd = {k: _sd(k) for k in per_seed[0]}
        rows.append(dict(tool=tool, **agg,
                         **{f"sd_{k}": v for k, v in sd.items()}))
    r = pd.DataFrame(rows).set_index("tool")

    order = list(RUNGS)
    print("== EVSI by rung of the information ladder ==")
    disp = r[order].copy()
    for c in order:
        disp[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in r[c]]
    print(disp.to_string())

    print("\n== the compression tax: value lost going down the ladder ==")
    tax = pd.DataFrame(index=r.index)
    tax["S2->S1"] = r["S2_estimate_plus_ci"] - r["S1_point_estimate"]
    tax["S1->S0"] = r["S1_point_estimate"] - r["S0_significance_bit"]
    tax["total S2->S0"] = r["S2_estimate_plus_ci"] - r["S0_significance_bit"]
    tax["S0 keeps %"] = 100 * r["S0_significance_bit"] / r["S2_estimate_plus_ci"]
    out = tax.copy()
    for c in ("S2->S1", "S1->S0", "total S2->S0"):
        out[c] = [f"${v:,.0f}" for v in tax[c]]
    out["S0 keeps %"] = tax["S0 keeps %"].round(1)
    print(out.to_string())

    print("\n== monotonicity: EVSI(S2) >= EVSI(S1) >= EVSI(S0)? ==")
    for tool in r.index:
        s0, s1, s2 = (r.loc[tool, k] for k in order[:3])
        e0, e1, e2 = (r.loc[tool, f"sd_{k}"] for k in order[:3])
        ok21 = s2 >= s1 - 2 * max(e1, e2)
        ok10 = s1 >= s0 - 2 * max(e0, e1)
        flag = "ok" if (ok21 and ok10) else "VIOLATION"
        print(f"  {tool:14s} S0 ${s0:>9,.0f}(±{e0:,.0f})  "
              f"S1 ${s1:>9,.0f}(±{e1:,.0f})  S2 ${s2:>9,.0f}(±{e2:,.0f})  {flag}")

    if args.sweep:
        # Every retention figure above is computed at ONE point of the
        # business plane: prior 0.4, cost ratio 1. If "GeoLift keeps 7.8% of
        # its value through the significance bit" becomes 60% at a different
        # prior, the headline is a coincidence of one cell. Checked here
        # rather than assumed.
        print("\n== does the S0 retention survive the business plane? ==")
        priors = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        ratios = [0.25, 0.5, 1.0, 2.0, 4.0]
        prepped = {t: prepare(d, t, args.scenario) for t in tools}
        ACTIVE = 100.0     # a bit is "doing something" if S0 clears $100
        cells: list[dict] = []
        for pi in priors:
            for ratio in ratios:
                pr = two_point_problem(pi, ratio * args.c_fn, args.c_fn)
                row = {"prior": pi, "ratio": ratio}
                for t in tools:
                    vals = [ladder_for(pr, prepped[t], s) for s in range(4)]
                    s0 = float(np.nanmean([v["S0_significance_bit"] for v in vals]))
                    s1 = float(np.nanmean([v["S1_point_estimate"] for v in vals]))
                    row[f"{t}|s0"] = s0
                    row[f"{t}|keep"] = (100 * max(s0, 0.0) / s1
                                        if np.isfinite(s1) and s1 > 1.0 else np.nan)
                cells.append(row)
        C = pd.DataFrame(cells)
        n = len(C)
        print(f"   {len(priors)}x{len(ratios)} = {n} cells, 4 splits each\n")

        # The first thing the sweep says is not about ordering at all.
        print(f"   {'tool':18s} {'bit worth >$100':>16s} {'median|active':>14s} "
              f"{'max':>7s} {'at 0.4/1.0':>11s}")
        base = {t: 100 * r.loc[t, "S0_significance_bit"]
                / r.loc[t, "S1_point_estimate"] for t in tools}
        act = {}
        for t in tools:
            live = C[C[f"{t}|s0"] > ACTIVE]
            act[t] = live[f"{t}|keep"].dropna()
            med = f"{act[t].median():.1f}%" if len(act[t]) else "n/a"
            mx = C[f"{t}|keep"].max()
            print(f"   {t:18s} {len(live):>7d}/{n:<8d} {med:>14s} "
                  f"{mx:6.1f}% {base[t]:10.1f}%")

        print("\n   READ THIS BEFORE THE ORDERING. In most cells the "
              "significance bit is\n   worth ~$0 for every tool -- it does "
              "not move a two-point decision at\n   all. So a median over "
              "all cells is a median over mostly-zeros, and an\n   ordering "
              "among those ties would be an artefact. The retention figures\n"
              "   in the addendum describe the MINORITY of cells where the "
              "bit does\n   something, which is where the question is "
              "interesting.")

        # The sharp test: cell by cell, where BOTH tools' bits are live,
        # does the ordering hold? A rank that survives pairwise beats a
        # rank of aggregates.
        print("\n   pairwise, over cells where both tools' bits clear $100:")
        for i, a in enumerate(tools):
            for b in tools[i + 1:]:
                both = C[(C[f"{a}|s0"] > ACTIVE) & (C[f"{b}|s0"] > ACTIVE)]
                if both.empty:
                    print(f"     {a:16s} vs {b:16s} no shared live cells")
                    continue
                frac = float((both[f"{a}|keep"] < both[f"{b}|keep"]).mean())
                lo, hi = (a, b) if frac >= 0.5 else (b, a)
                print(f"     {lo:16s} < {hi:16s} in "
                      f"{100 * max(frac, 1 - frac):5.1f}% of {len(both)} cells")

    if args.bandwidth_scan:
        print("\n== is any violation information or density estimation? ==")
        print("   (if the ordering is stable across bandwidths it is "
              "information; if it moves, it is KDE error)\n")
        for bw in (0.3, 0.5, "scott", "silverman", 1.5):
            line = f"  bw={str(bw):10s}"
            for tool in tools:
                g = prepare(d, tool, args.scenario)
                vals = [ladder_for(problem, g, s, bw) for s in range(3)]
                s1 = np.nanmean([v["S1_point_estimate"] for v in vals])
                s2 = np.nanmean([v["S2_estimate_plus_ci"] for v in vals])
                line += f" {tool[:2]}:{'+' if s2 >= s1 else '-'}{abs(s2-s1)/1000:5.1f}k"
            print(line)


if __name__ == "__main__":
    main()
