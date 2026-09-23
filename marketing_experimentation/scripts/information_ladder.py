#!/usr/bin/env python
"""What does each interface to an experiment's result cost, in currency?

A CORRECTION TO THE STRUCTURE OF THIS FILE
------------------------------------------
Earlier versions called this a "ladder": S0 (bit) below S1 (point estimate)
below S2 (estimate + width), and asserted

    EVSI(S2) >= EVSI(S1) >= EVSI(S0)

as a coarsening hierarchy. **That was wrong, and the error was structural
rather than numerical.** In this harness `significant` is computed from the
confidence interval, not from the point estimate -- verified here at 100.00%
agreement with "CI excludes zero", 0 mismatches in 2,000 rows per tool. So
the bit is NOT a function of the point estimate, and S0 was never a
coarsening of S1. They are two different projections of the same result.

The representation graph is therefore a fork, not a chain::

      FULL   (att, ci_lo, ci_hi, diagnostic)
        |
        +---------------------> POINT  (att)        side branch
        |
        v
      INTERVAL (att, ci_lo, ci_hi)
        |
        v  deterministic garbling
      BIT    (does the interval exclude zero?)

What this buys, and it is worth more than the tidiness
------------------------------------------------------
Along the vertical chain the bit really is a deterministic garbling of the
interval, so **Blackwell's theorem guarantees**

    EVSI(FULL) >= EVSI(INTERVAL) >= EVSI(BIT)

for *any* decision problem, prior and utility. That converts a hoped-for
empirical regularity into an identity -- and turns a violation into a
**self-test on this harness**: if the measured EVSI(INTERVAL) falls below
EVSI(BIT) by more than Monte Carlo error, the density estimation is broken,
because the information ordering cannot be.

POINT sits off the chain. Neither it nor the bit is a garbling of the other
(the point drops the interval; the bit drops the magnitude), Blackwell
orders only comparable experiments, and no inequality between them is
guaranteed. `POINT - BIT` is an empirical property of a particular decision
problem, and is reported under its own heading so it cannot be read as the
compression result.

INTERVAL carries both bounds, not the width. The intervals are not symmetric
about the estimate -- median |att - midpoint| runs 1.3-8.3% of the width --
so (att, width) recovers significance only 94-97% of the time and would
silently break the nesting everything above depends on.

The dimensionality caveat, now with a guard
-------------------------------------------
INTERVAL is a 3-d density from ~500 held-out runs per arm, and a degraded
density *lowers* measured EVSI. Previously that ambiguity was unresolvable
from the numbers alone. Now it is not: a Blackwell violation can only be
estimation error, so the self-test above says directly when the sample has
run out. `--bandwidth-scan` remains for the finer question.

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
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leadbench_mx.decision import two_point_problem  # noqa: E402

#: The representation graph. NOT a linear ladder -- an earlier version of
#: this file treated it as one and the difference matters.
#:
#:      FULL   (att, ci_lo, ci_hi, diagnostic)
#:        |
#:        +---------------------> POINT  (att)        side branch
#:        |
#:        v
#:      INTERVAL (att, ci_lo, ci_hi)
#:        |
#:        v  deterministic
#:      BIT    (CI excludes zero?)
#:
#: `significant` in this harness is exactly "the interval excludes zero" --
#: verified at 100.00% agreement, 0 mismatches in 2,000 rows per tool. So BIT
#: is a deterministic *garbling* of INTERVAL, and by Blackwell's theorem
#:
#:      EVSI(FULL) >= EVSI(INTERVAL) >= EVSI(BIT)
#:
#: holds BY CONSTRUCTION for any decision problem. A violation beyond Monte
#: Carlo error is therefore not a finding about information, it is a bug in
#: our density estimation -- which makes it a self-test for the harness.
#:
#: POINT is a *side branch*. Neither POINT nor BIT is a garbling of the
#: other, so Blackwell does not order them and no inequality between them is
#: guaranteed. Their comparison is an empirical fact about this decision
#: problem, not a theorem, and it is reported separately for that reason.
#:
#: INTERVAL carries the full bounds rather than the width: the intervals are
#: NOT symmetric about the estimate (median |att - midpoint| is 1.3-8.3% of
#: the width), so (att, width) recovers significance only 94-97% of the time
#: and would break the nesting the whole argument rests on.
RUNGS: dict[str, list[str]] = {
    "BIT_significance": [],                 # discrete, handled separately
    "POINT_estimate": ["att_pct"],          # SIDE BRANCH
    "INTERVAL_full": ["att_pct", "ci_lower", "ci_upper"],
    "FULL_plus_diagnostic": ["att_pct", "ci_lower", "ci_upper", "diagnostic"],
}

#: The chain along which Blackwell guarantees monotonicity, coarsest first.
GARBLING_CHAIN = ["BIT_significance", "INTERVAL_full", "FULL_plus_diagnostic"]

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
    g["ci_width"] = g.ci_upper - g.ci_lower  # reporting only
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


def evsi_continuous(problem, fit, ev, bw: float | str = "scott",
                    want_auc: bool = False):
    """EVSI when the decision sees the full continuous signal.

    With `want_auc`, also returns the held-out AUC of the posterior. That
    matters because EVSI in different dimensions is not directly comparable
    -- a richer signal can score higher simply by giving a 3-d KDE more room
    to find structure that is not there. AUC is computed on the SAME held-out
    points, is dimension-agnostic, and cannot be inflated by overfitting the
    fit half. It is the arbiter when a rung's EVSI jumps.
    """
    kdes = {}
    for j, X in fit.items():
        if X.shape[1] == 1:
            kdes[j] = gaussian_kde(X[:, 0], bw_method=bw)
        else:
            kdes[j] = gaussian_kde(X.T, bw_method=bw)
    total = 0.0
    ys, scores = [], []
    for j, X in ev.items():
        pts = X[:, 0] if X.shape[1] == 1 else X.T
        like = np.vstack([np.clip(kdes[k](pts), 1e-300, None) for k in (0, 1)]).T
        post = problem.prior * like
        post /= np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
        total += problem.prior[j] * float((post @ problem.utility.T).max(axis=1).mean())
        ys += [j] * len(X)
        scores += list(post[:, 1])
    evsi = total - problem.value_no_experiment()
    if not want_auc:
        return evsi
    try:
        auc = float(roc_auc_score(ys, scores))
    except ValueError:
        auc = float("nan")
    return evsi, auc


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
    out = {"BIT_significance": evsi_binary(problem, g)}
    for rung, cols in RUNGS.items():
        if not cols:
            continue
        if "diagnostic" in cols and not g["diagnostic"].notna().any():
            out[rung] = np.nan
            continue
        fit, ev = split(g, cols, seed)
        if fit is None:
            out[rung] = np.nan
            out[f"auc_{rung}"] = np.nan
        else:
            out[rung], out[f"auc_{rung}"] = evsi_continuous(
                problem, fit, ev, bw, want_auc=True)
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
    print("== EVSI by representation ==")
    print("   BIT <- INTERVAL <- FULL is a garbling chain (Blackwell applies).")
    print("   POINT is a side branch: not comparable to BIT by Blackwell.\n")
    disp = r[order].copy()
    for c in order:
        disp[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in r[c]]
    print(disp.to_string())

    print("\n== HARNESS SELF-TEST: Blackwell monotonicity on the garbling chain ==")
    print("   BIT is a deterministic function of INTERVAL, so EVSI(INTERVAL)")
    print("   >= EVSI(BIT) holds for ANY decision problem. A violation beyond")
    print("   Monte Carlo error is a density-estimation bug, not a finding.\n")
    violations = 0
    for tool in r.index:
        b = r.loc[tool, "BIT_significance"]
        i = r.loc[tool, "INTERVAL_full"]
        f = r.loc[tool, "FULL_plus_diagnostic"]
        ei = r.loc[tool, "sd_INTERVAL_full"]
        ef = r.loc[tool, "sd_FULL_plus_diagnostic"]
        ok_ib = i >= b - 2 * (ei if np.isfinite(ei) else 0)
        ok_fi = (not np.isfinite(f)) or f >= i - 2 * max(
            ei if np.isfinite(ei) else 0, ef if np.isfinite(ef) else 0)
        flag = "ok" if (ok_ib and ok_fi) else "VIOLATION -- suspect the KDE"
        violations += 0 if (ok_ib and ok_fi) else 1
        print(f"   {tool:18s} BIT ${b:>9,.0f}  INTERVAL ${i:>9,.0f}"
              f"(±{ei:,.0f})  FULL ${f:>9,.0f}   {flag}")
    if violations:
        print(f"\n   {violations} violation(s). The 3-dimensional density for")
        print("   INTERVAL is estimated from ~500 points per arm, which is")
        print("   where this is expected to break first. Treat the INTERVAL")
        print("   column as unreliable until the sample supports it.")

    print("\n== what thresholding costs, along the guaranteed chain ==")
    tax = pd.DataFrame(index=r.index)
    tax["INTERVAL-BIT"] = r["INTERVAL_full"] - r["BIT_significance"]
    tax["BIT keeps %"] = 100 * r["BIT_significance"] / r["INTERVAL_full"]
    out = tax.copy()
    out["INTERVAL-BIT"] = [f"${v:,.0f}" if np.isfinite(v) else "n/a"
                           for v in tax["INTERVAL-BIT"]]
    out["BIT keeps %"] = tax["BIT keeps %"].round(1)
    print(out.to_string())
    print("\n   This IS a compression tax: the bit is that signal, thresholded.")

    print("\n== held-out AUC: is a richer rung genuinely more discriminating? ==")
    print("   EVSI across dimensions is not comparable -- a 3-d KDE has more")
    print("   room to find structure that is not there. AUC is on the same")
    print("   held-out points, is dimension-agnostic, and cannot be inflated")
    print("   by overfitting the fit half.\n")
    acols = [c for c in r.columns if c.startswith("auc_")]
    if acols:
        a = r[acols].copy()
        a.columns = [c[4:] for c in acols]
        print(a.round(4).to_string())
        if "POINT_estimate" in a.columns and "INTERVAL_full" in a.columns:
            print("\n   INTERVAL - POINT, in AUC:")
            for tool in a.index:
                dv = a.loc[tool, "INTERVAL_full"] - a.loc[tool, "POINT_estimate"]
                verdict = ("the interval discriminates better" if dv > 0.02 else
                           "no better; the extra dimensions cost more than "
                           "they carry" if dv < -0.02 else "indistinguishable")
                print(f"     {tool:18s} {dv:+.4f}   {verdict}")

    print("\n== the side branch, which is a different claim ==")
    side = pd.DataFrame(index=r.index)
    side["POINT"] = r["POINT_estimate"]
    side["BIT"] = r["BIT_significance"]
    side["POINT - BIT"] = r["POINT_estimate"] - r["BIT_significance"]
    o2 = side.copy()
    for c in o2.columns:
        o2[c] = [f"${v:,.0f}" if np.isfinite(v) else "n/a" for v in side[c]]
    print(o2.to_string())
    print("\n   Neither signal is a garbling of the other -- the point estimate")
    print("   drops the interval, the bit drops the magnitude -- so Blackwell")
    print("   does not order them and this gap is an empirical property of")
    print("   THIS decision problem, not a theorem. It says the conventional")
    print("   point-estimate interface can be far more decision-useful than")
    print("   the conventional significance interface, which is worth saying")
    print("   and is not the same as 'thresholding destroys information'.")

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
                    s0 = float(np.nanmean([v["BIT_significance"] for v in vals]))
                    s1 = float(np.nanmean([v["INTERVAL_full"] for v in vals]))
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
        base = {t: 100 * r.loc[t, "BIT_significance"]
                / r.loc[t, "INTERVAL_full"] for t in tools}
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
                s1 = np.nanmean([v["POINT_estimate"] for v in vals])
                s2 = np.nanmean([v["INTERVAL_full"] for v in vals])
                line += f" {tool[:2]}:{'+' if s2 >= s1 else '-'}{abs(s2-s1)/1000:5.1f}k"
            print(line)


if __name__ == "__main__":
    main()
