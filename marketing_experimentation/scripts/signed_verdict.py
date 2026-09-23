#!/usr/bin/env python
"""Where does the compression loss go: thresholding, or the discarded sign?

The finding this exists to test
-------------------------------
M7 put six non-null truths on the table, two of them negative. That exposed
something the two-point world could not show: `significant` in this harness
is "the confidence interval excludes zero", **unsigned**. A channel that
destroys 10% of revenue and one that adds 15% both produce
`significant = True`. The bit answers "is something happening" and refuses to
say what.

So the near-zero EVSI of the significance bit under a five-action budget
decision has two candidate explanations, and they are very different:

  (a) THRESHOLDING. Collapsing a continuous estimate with its uncertainty
      into a discrete verdict destroys the magnitude, and magnitude is what
      a "how much should I spend" decision needs.
  (b) THE SIGN. The bit is not merely discrete, it is *unsigned* -- it maps
      "cut hard" and "increase hard" to the same symbol.

(a) is a statement about statistics in general. (b) is a statement about one
specific, fixable convention.

Two findings of different strength, kept apart on purpose
---------------------------------------------------------
Inserting the missing rung gives a chain of two deterministic garblings::

      INTERVAL   (att, ci_lo, ci_hi)
        |
        v   threshold at zero, KEEP the sign
      VERDICT    negative / inconclusive / positive
        |
        v   discard the sign
      BIT        significant / not significant

Blackwell orders the whole chain. But the two steps are **not measurable to
the same standard**, and an earlier version of this file reported them in one
table as though they were:

    FINDING A -- the cost of discarding the sign.  VERDICT and BIT are both
    discrete. p(verdict | theta) is a multinomial estimated from counts, and
    p(bit | theta) follows from it exactly through the garbling map. **No
    density estimation is involved anywhere.** The uncertainty is a Dirichlet
    posterior over the transition matrix, propagated through EVSI, so the
    result is an interval rather than a plug-in number.

    FINDING B -- the cost of thresholding.  INTERVAL needs a 3-d density from
    ~50 runs per truth. That is the estimator this project has already caught
    running out of sample twice. Provisional, and labelled so.

Keeping them in one table let an unreliable KDE contaminate a conclusion
about a perfectly reliable three-state channel. They are now separate
sections and the share between them is printed only where it is resolved.

What `alpha` is doing, and why it gets a posterior rather than a footnote
-------------------------------------------------------------------------
What makes a signed verdict valuable is the rare cell: `p(negative |
theta=+15%)` is 0 out of 100 for two of these tools, and seeing `negative`
then nearly proves the truth is below zero. Smoothing sets the probability of
exactly those decisive-but-unobserved events. A plug-in number hides that
entirely. `Dirichlet(counts + alpha)` does not: alpha remains a prior choice,
but its consequences arrive as a visible interval, at three values.

The scenarios are not a sample from anything
---------------------------------------------
A1-A4 are four regimes the donor chose. Pooling them weights each one
equally, which is a belief about a population that does not exist. Results
are reported **per scenario**, and the pooled figure is offered as a
sensitivity analysis rather than the headline.

    python marketing_experimentation/scripts/signed_verdict.py \
        --results /tmp/results_atlas.jsonl --neg-sweep --alpha-scan
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

from leadbench_mx.decision import (  # noqa: E402
    DEFAULT_ACTIONS, DecisionProblem, budget_problem, spike_slab_prior,
)

#: The signed verdict, ordered so that index 1 is the "says nothing" cell.
VERDICT_LEVELS = ("negative", "inconclusive", "positive")

#: The garbling that produces the conventional bit: rows are bit values,
#: columns are verdict values. Row 0 is "not significant", row 1 is
#: "significant". This matrix IS the information the convention destroys.
GARBLE = np.array([[0.0, 1.0, 0.0],
                   [1.0, 0.0, 1.0]])

#: Dirichlet concentration added to the verdict counts. Not a nuisance
#: parameter: it sets the probability of the decisive cells that were never
#: observed, and it shrinks VERDICT's three cells harder than BIT's two.
#: `--alpha-scan` reports the posterior at three values instead of pretending
#: one of them is right.
ALPHA = 0.5

INTERVAL_COLS = ["att_pct", "ci_lower", "ci_upper"]

#: The negative mass of the continuous spike-and-slab prior. The seven-point
#: Voronoi binning moves it to ~0.071, so the sweep includes this value --
#: but a seven-point prior matched on this ONE MARGINAL is not the documented
#: prior. See `reweight_negative`.
DOCUMENTED_NEGATIVE_MASS = 0.267


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(line) for line in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(
        lambda s: f"[{s}]" if s else "")
    for c in INTERVAL_COLS + ["effect_pct"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def guard_unique(d: pd.DataFrame) -> None:
    """A duplicated run identity is a doubled likelihood weight -- see D13."""
    keys = ["tool_label", "scenario", "effect_pct", "iteration"]
    dup = d.duplicated(subset=keys)
    if dup.any():
        raise SystemExit(
            f"{int(dup.sum())} duplicated run identities. Regenerate with "
            f"`make clean` -- see D13 in docs/donor-repro.md.")


def verdict_index(d: pd.DataFrame) -> np.ndarray:
    """0 negative, 1 inconclusive, 2 positive, from the interval alone."""
    lo = d.ci_lower.to_numpy(dtype=float)
    hi = d.ci_upper.to_numpy(dtype=float)
    v = np.ones(len(d), dtype=int)
    v[hi < 0] = 0
    v[lo > 0] = 2
    return v


def audit_bit_is_garbling(d: pd.DataFrame) -> tuple[int, int]:
    """The premise: `significant` must be exactly "the verdict is not
    inconclusive". If it is not, the chain below is not a garbling chain and
    every inequality in this file is unearned -- the same structural error
    recorded as F13, which is why it is checked rather than assumed."""
    derived = verdict_index(d) != 1
    actual = d.significant.astype(bool).to_numpy()
    return int((derived == actual).sum()), len(d)


# ---------------------------------------------------------------------------
# FINDING A -- the sign, measured from counts. No density estimation.
# ---------------------------------------------------------------------------

def verdict_counts(g: pd.DataFrame, thetas: list[float]) -> np.ndarray | None:
    """(n_theta, 3) counts of negative / inconclusive / positive.

    Uses every row. Finding A involves no density and no held-out evaluation,
    so there is nothing to protect against overfitting and no reason to
    discard half the data -- the estimation uncertainty is carried by the
    Dirichlet posterior instead of by a fit/eval split.
    """
    out = np.zeros((len(thetas), 3))
    for j, th in enumerate(thetas):
        sub = g[np.isclose(g.effect_pct, th, atol=1e-9)]
        if sub.empty:
            return None
        out[j] = np.bincount(verdict_index(sub), minlength=3)
    return out


def dirichlet_draws(counts: np.ndarray, alpha: float, n_draws: int,
                    rng: np.random.Generator) -> np.ndarray:
    """Posterior draws of p(verdict | theta), independently per truth.

    Returns (n_draws, n_theta, 3). Independent across truths because each
    truth's runs are a separate multinomial sample -- nothing in the design
    links them, and pretending otherwise would be a smoothing assumption
    smuggled in as a prior.
    """
    a = counts + alpha
    g = rng.gamma(a, size=(n_draws,) + a.shape)
    return g / g.sum(axis=-1, keepdims=True)


def evsi_batch(problem: DecisionProblem, P: np.ndarray) -> np.ndarray:
    """Exact EVSI of each discrete likelihood in a batch.

    ``P`` is (n_draws, n_theta, n_levels) = p(y | theta). The expectation runs
    over each draw's OWN implied marginal, which is what makes `EVSI >= 0` and
    Blackwell exact for every draw rather than approximately true on average.
    """
    joint = problem.prior[None, :, None] * P
    marg = joint.sum(axis=1)                                # (D, n_levels)
    post = joint / np.clip(marg, 1e-300, None)[:, None, :]
    vals = np.einsum("aj,djy->day", problem.utility, post)
    total = (marg * vals.max(axis=1)).sum(axis=1)
    return total - problem.value_no_experiment()


def sign_loss_posterior(problem: DecisionProblem, counts: np.ndarray,
                        alpha: float = ALPHA, n_draws: int = 20_000,
                        seed: int = 0) -> dict:
    """Posterior for EVSI(VERDICT), EVSI(BIT) and the sign loss between them.

    Every draw satisfies V >= B exactly (Jensen on that draw's own marginals),
    so `P(V - B > 0)` is close to vacuous here -- Blackwell has already ruled
    out the other sign. The informative quantity is the **lower credible
    bound**: how much of the loss survives the worst plausible transition
    matrix.
    """
    rng = np.random.default_rng(seed)
    pv = dirichlet_draws(counts, alpha, n_draws, rng)
    pb = pv @ GARBLE.T
    v, b = evsi_batch(problem, pv), evsi_batch(problem, pb)
    gap = v - b
    return {
        "v_med": float(np.median(v)), "b_med": float(np.median(b)),
        "gap_med": float(np.median(gap)),
        "gap_lo": float(np.quantile(gap, 0.025)),
        "gap_hi": float(np.quantile(gap, 0.975)),
        "p_gap_pos": float((gap > 1e-9).mean()),
        "worst_blackwell": float(gap.min()),
    }


# ---------------------------------------------------------------------------
# FINDING B -- thresholding. Needs a 3-d density, and is weaker for it.
# ---------------------------------------------------------------------------

def held_out_pair(g: pd.DataFrame, thetas: list[float], seed: int,
                  frac_fit: float = 0.5, bw="scott", alpha: float = ALPHA):
    """INTERVAL and VERDICT likelihoods on the SAME held-out rows.

    Finding B is a comparison, so both rungs must be scored on one split or
    the difference confounds information with sample size. Finding A does not
    use this at all.
    """
    rng = np.random.default_rng(seed)
    fit_rows, ev_rows = [], []
    for th in thetas:
        sub = g[np.isclose(g.effect_pct, th, atol=1e-9)]
        if len(sub) < 8:
            return None
        idx = rng.permutation(len(sub))
        cut = max(int(frac_fit * len(sub)), 4)
        fit_rows.append(sub.iloc[idx[:cut]])
        ev_rows.append(sub.iloc[idx[cut:]])

    kdes = []
    for f in fit_rows:
        X = f[INTERVAL_COLS].to_numpy(dtype=float)
        if len(X) < 4 or np.linalg.matrix_rank(X - X.mean(0)) < X.shape[1]:
            return None
        try:
            kdes.append(gaussian_kde(X.T, bw_method=bw))
        except np.linalg.LinAlgError:
            return None

    pv = np.empty((len(thetas), 3))
    for j, f in enumerate(fit_rows):
        c = np.bincount(verdict_index(f), minlength=3).astype(float)
        pv[j] = (c + alpha) / (c.sum() + 3 * alpha)

    ev = pd.concat(ev_rows, ignore_index=True)
    src = np.concatenate([[j] * len(e) for j, e in enumerate(ev_rows)])
    pts = ev[INTERVAL_COLS].to_numpy(dtype=float).T
    return {
        "INTERVAL": np.column_stack([np.clip(k(pts), 1e-300, None)
                                     for k in kdes]),
        "VERDICT": pv[:, verdict_index(ev)].T,
        "src": src, "n_fit": int(min(len(f) for f in fit_rows)),
    }


def evsi_held_out(problem: DecisionProblem, L: np.ndarray,
                  src: np.ndarray) -> float:
    """EVSI of the plug-in policy, scored on fresh runs.

    The outer expectation is taken under the PRIOR, not under the empirical
    frequency of the held-out rows -- the simulation ran equal iterations per
    truth, which is a design choice, not a belief.
    """
    post = problem.prior * L
    post = post / np.clip(post.sum(axis=1, keepdims=True), 1e-300, None)
    best = (post @ problem.utility.T).max(axis=1)
    total = 0.0
    for j in range(len(problem.theta)):
        m = src == j
        if not m.any():
            return np.nan
        total += problem.prior[j] * float(best[m].mean())
    return total - problem.value_no_experiment()


def reweight_negative(problem: DecisionProblem, w: float) -> DecisionProblem:
    """The same seven-point problem with prior mass ``w`` below zero.

    **This does not reconstruct the continuous prior.** It matches ONE
    marginal -- total mass below zero -- and preserves the relative weights
    inside each half. The spike-and-slab has structure near zero that a
    seven-point grid cannot represent at all, and where the negative mass
    sits matters enormously to a five-action decision: mass at -10% and -5%
    argues for `cut hard`, the same mass at -2% and -1% argues for `hold`.

    So a run at w = 0.267 is a **seven-point sensitivity prior whose negative
    mass matches the documented continuous prior**, and must be described
    that way. Calling it "the documented prior" -- as an earlier version of
    this file's output did -- claims a reconstruction that has not happened
    and cannot happen until the theta grid is finer near zero.
    """
    p = np.asarray(problem.prior, dtype=float).copy()
    neg = problem.theta < 0
    if not neg.any() or p[neg].sum() <= 0 or p[~neg].sum() <= 0:
        raise SystemExit("cannot reweight: a half carries no prior mass")
    p[neg] = w * p[neg] / p[neg].sum()
    p[~neg] = (1.0 - w) * p[~neg] / p[~neg].sum()
    return DecisionProblem(problem.theta, p, problem.utility,
                           problem.action_names)


def build_problem(thetas: list[float]) -> tuple[DecisionProblem, float]:
    grid = np.linspace(-0.15, 0.25, 81)
    pri = spike_slab_prior(grid)
    th = np.array(thetas)
    edges = np.concatenate(([-np.inf], (th[:-1] + th[1:]) / 2, [np.inf]))
    idx = np.digitize(grid, edges) - 1
    p7 = np.array([pri[idx == j].sum() for j in range(len(thetas))])
    return budget_problem(th, p7 / p7.sum()), float(pri[grid < 0].sum())


def money(v: float) -> str:
    return f"${v:,.0f}" if np.isfinite(v) else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--seeds", type=int, default=16)
    ap.add_argument("--draws", type=int, default=20_000)
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--neg-sweep", action="store_true")
    ap.add_argument("--alpha-scan", action="store_true")
    ap.add_argument("--skip-interval", action="store_true",
                    help="Finding A only; it needs no density estimation")
    args = ap.parse_args()

    d = load(args.results)
    guard_unique(d)
    n0 = len(d)
    d = d[np.isfinite(d[INTERVAL_COLS].to_numpy(dtype=float)).all(axis=1)
          & d.significant.notna()]
    print(f"{len(d):,} usable rows"
          + (f" ({n0 - len(d)} dropped for non-finite interval)"
             if n0 != len(d) else ""))

    ok, tot = audit_bit_is_garbling(d)
    print(f"\n== premise check: is BIT a garbling of VERDICT? ==")
    print(f"   `significant` == (verdict != inconclusive) on {ok:,}/{tot:,} "
          f"rows = {100*ok/tot:.2f}%")
    if ok != tot:
        raise SystemExit(
            f"   {tot-ok} rows disagree. BIT is then NOT a deterministic\n"
            f"   function of VERDICT, Blackwell does not apply, and this\n"
            f"   whole decomposition is unearned -- the F13 error again.")
    print("   exact. INTERVAL -> VERDICT -> BIT is a garbling chain.")

    thetas = sorted(float(t) for t in d.effect_pct.unique())
    tools = sorted(d.tool_label.unique())
    scenarios = sorted(d.scenario.unique())
    problem, cont_neg = build_problem(thetas)

    print(f"\n== the decision ==")
    print(f"   actions: {', '.join(DEFAULT_ACTIONS)}")
    print(f"   truths:  {[round(100*t, 1) for t in thetas]} (%)")
    print(f"   prior mass below zero: "
          f"{float(problem.prior[problem.theta<0].sum()):.3f} on this grid, "
          f"{cont_neg:.3f} in the continuous prior.")
    print(f"   Those are different decision problems, and matching the one")
    print(f"   marginal does not make them the same -- see --neg-sweep.")
    print(f"   no-experiment action: {problem.best_action_no_experiment()!r}"
          f"   |   EVPI {money(problem.evpi())}")

    # -- what the bit merges, per tool, per scenario ------------------------
    print(f"\n== what the unsigned bit merges ==")
    print("   P(verdict | theta), per tool. Pooling tools here would average")
    print("   four different sign-error rates into a number describing none.")
    for tool in tools:
        gt = d[d.tool_label == tool]
        print(f"\n   {tool}   (all scenarios, n=100 per truth)")
        print(f"     {'theta':>7s}  {'P(neg)':>7s} {'P(incon)':>9s} "
              f"{'P(pos)':>7s}   {'P(significant)':>14s}")
        for th in thetas:
            sub = gt[np.isclose(gt.effect_pct, th, atol=1e-9)]
            f = np.bincount(verdict_index(sub), minlength=3) / len(sub)
            print(f"     {100*th:+6.1f}%  {f[0]:7.3f} {f[1]:9.3f} "
                  f"{f[2]:7.3f}   {f[0]+f[2]:14.3f}")

    # =====================================================================
    # FINDING A
    # =====================================================================
    print(f"\n\n{'='*72}")
    print("FINDING A -- the cost of discarding the sign")
    print(f"{'='*72}")
    print("VERDICT -> BIT is a purely discrete channel. Multinomial counts,")
    print("an exact garbling map, no kernel density anywhere. The uncertainty")
    print(f"is a Dirichlet(counts + {args.alpha}) posterior over the transition")
    print(f"matrix, propagated through EVSI: {args.draws:,} draws.")
    print("\nPer scenario, because A1-A4 are four regimes the donor chose and")
    print("not a sample from any population. Pooled is a sensitivity check.\n")

    def counts_for(tool: str, scen: str | None):
        g = d[d.tool_label == tool]
        if scen is not None:
            g = g[g.scenario == scen]
        return verdict_counts(g, thetas)

    print(f"   {'tool':18s} {'where':8s} {'n/truth':>7s} {'VERDICT':>9s} "
          f"{'BIT':>9s} {'V-B median':>11s} {'95% credible':>22s}")
    finding_a = {}
    for tool in tools:
        for scen in scenarios + [None]:
            c = counts_for(tool, scen)
            if c is None:
                continue
            res = sign_loss_posterior(problem, c, args.alpha, args.draws)
            finding_a[(tool, scen)] = res
            label = scen or "pooled"
            print(f"   {tool:18s} {label:8s} {int(c[0].sum()):>7d} "
                  f"{money(res['v_med']):>9s} {money(res['b_med']):>9s} "
                  f"{money(res['gap_med']):>11s} "
                  f"  [{money(res['gap_lo'])}, {money(res['gap_hi'])}]")
        print()

    worst = min(r["worst_blackwell"] for r in finding_a.values())
    print(f"   self-test: min(V - B) over all "
          f"{len(finding_a) * args.draws:,} draws = {worst:+.3e}")
    print(f"   {'PASS' if worst >= -1e-6 else 'FAIL -- STOP'}. V >= B is exact "
          f"per draw (Jensen on that draw's own\n   marginals), which is why "
          f"P(V-B > 0) is near-vacuous here:")
    print(f"   Blackwell has already excluded the other sign. The informative")
    print(f"   number is the LOWER credible bound -- how much of the loss")
    print(f"   survives the worst plausible transition matrix.")

    if args.alpha_scan:
        print(f"\n== Finding A under three smoothing priors ==")
        print("   alpha sets the probability of the decisive cells that were")
        print("   never observed -- p(negative | theta=+15%) is 0/100 for two")
        print("   tools. It stays a prior choice; what changes is that its")
        print("   consequences now arrive as intervals rather than as a")
        print("   factor-of-three wobble in a plug-in number.\n")
        print(f"   {'tool':18s} " + "".join(
            f"{'alpha=' + str(a):>26s}" for a in (0.05, 0.5, 2.0)))
        for tool in tools:
            c = counts_for(tool, None)
            cells = []
            for a in (0.05, 0.5, 2.0):
                r_ = sign_loss_posterior(problem, c, a, args.draws)
                cells.append(f"{money(r_['gap_med']):>7s} "
                             f"[{money(r_['gap_lo'])},{money(r_['gap_hi'])}]"
                             .rjust(26))
            print(f"   {tool:18s} " + "".join(cells))
        print("\n   (pooled; the credible intervals overlap heavily across")
        print("   alpha, which the earlier plug-in presentation could not show)")

    if args.skip_interval:
        return

    # =====================================================================
    # FINDING B
    # =====================================================================
    print(f"\n\n{'='*72}")
    print("FINDING B -- the cost of thresholding  (PROVISIONAL)")
    print(f"{'='*72}")
    print("INTERVAL needs a 3-d density per truth. This project has already")
    print("caught that estimator running out of sample twice. Both rungs are")
    print("scored on the same held-out rows so the difference is paired, and")
    print("the split-to-split SD is printed because it is the point.\n")
    print(f"   {'tool':18s} {'where':8s} {'fit/truth':>9s} {'INTERVAL':>9s} "
          f"{'VERDICT':>9s} {'I-V':>9s} {'±':>7s}  verdict")
    finding_b, finding_b_verdict = {}, {}
    for tool in tools:
        for scen in scenarios + [None]:
            g = d[d.tool_label == tool]
            if scen is not None:
                g = g[g.scenario == scen]
            ms = [m for m in (held_out_pair(g, thetas, s, alpha=args.alpha)
                              for s in range(args.seeds)) if m is not None]
            if not ms:
                continue
            iv = np.array([evsi_held_out(problem, m["INTERVAL"], m["src"])
                           - evsi_held_out(problem, m["VERDICT"], m["src"])
                           for m in ms])
            i_ = float(np.nanmean([evsi_held_out(problem, m["INTERVAL"],
                                                 m["src"]) for m in ms]))
            v_ = float(np.nanmean([evsi_held_out(problem, m["VERDICT"],
                                                 m["src"]) for m in ms]))
            mean, sd = float(np.nanmean(iv)), float(np.nanstd(iv))
            finding_b[(tool, scen)] = (mean, sd)
            finding_b_verdict[(tool, scen)] = v_
            verdict = ("separated from zero" if mean > 2 * sd else
                       "BLACKWELL VIOLATION" if mean < -2 * sd else
                       "NOT separated from zero")
            print(f"   {tool:18s} {scen or 'pooled':8s} {ms[0]['n_fit']:>9d} "
                  f"{money(i_):>9s} {money(v_):>9s} {money(mean):>9s} "
                  f"{sd:>7,.0f}  {verdict}")
        print()

    # =====================================================================
    # The share -- only where it is resolved
    # =====================================================================
    print(f"{'='*72}")
    print("THE SHARE BETWEEN THEM -- printed only where it is resolved")
    print(f"{'='*72}")
    print("sign share = (V-B) / ((I-V) + (V-B)). An earlier version printed")
    print("this as `63.3%+`, a LOWER BOUND, wherever I-V was indistinguishable")
    print("from zero. That was wrong, and wrong in the direction that")
    print("flattered the finding: uncertainty in the DENOMINATOR moves the")
    print("true share both ways. If I-V is really $300 rather than the $100")
    print("estimated, a share of 67% is really 40%. An unresolved denominator")
    print("makes the ratio unresolved, not bounded below.\n")
    print("One more inconsistency, stated rather than hidden: the numerator")
    print("comes from Finding A (Dirichlet median, every row) and the")
    print("denominator's first part from Finding B (held-out, half the rows).")
    print("Those use different estimators for VERDICT. `V_A` and `V_B` below")
    print("are the two, so the reader can see whether the mixing matters.\n")
    print(f"   {'tool':18s} {'where':8s} {'V_A':>8s} {'V_B':>8s} {'I-V':>9s} "
          f"{'V-B':>9s} {'share':>18s}")
    for tool in tools:
        for scen in scenarios + [None]:
            if (tool, scen) not in finding_b or (tool, scen) not in finding_a:
                continue
            mean, sd = finding_b[(tool, scen)]
            gap = finding_a[(tool, scen)]["gap_med"]
            va = finding_a[(tool, scen)]["v_med"]
            vb = finding_b_verdict[(tool, scen)]
            if mean > 2 * sd and mean + gap > 0:
                share = f"{100 * gap / (mean + gap):17.1f}%"
            elif mean < -2 * sd:
                share = f"{'unresolved (KDE)':>18s}"
            else:
                share = f"{'unresolved':>18s}"
            print(f"   {tool:18s} {scen or 'pooled':8s} {money(va):>8s} "
                  f"{money(vb):>8s} {money(mean):>9s} {money(gap):>9s} "
                  f"{share}")
        print()
    print("   Where it reads `unresolved`, both dollar figures are still")
    print("   sound -- V-B never touches the density estimator. It is the")
    print("   RATIO that has no defensible value, and the honest output is")
    print("   the two magnitudes rather than a percentage of them.")

    if args.neg_sweep:
        print(f"\n{'='*72}")
        print("SENSITIVITY: where the negative prior mass sits")
        print(f"{'='*72}")
        print("The seven-point grid carries "
              f"{float(problem.prior[problem.theta<0].sum()):.3f} of the mass "
              f"below zero; the continuous\nprior carries {cont_neg:.3f}. "
              "Matching that ONE MARGINAL does not reconstruct\nthe prior: "
              "mass at -10% and -5% argues for `cut hard`, the same mass\n"
              "at -2% and -1% argues for `hold`, and a seven-point grid cannot"
              "\ntell them apart. So w = 0.267 below is a **seven-point "
              "sensitivity\nprior matched on negative mass**, not the "
              "documented prior.\n")
        print("V-B in dollars with its credible interval. No share column:")
        print("the denominator is Finding B, which is provisional.\n")
        ws = [0.02, 0.05, 0.10, 0.20, DOCUMENTED_NEGATIVE_MASS, 0.40, 0.50]
        for tool in tools:
            c = counts_for(tool, None)
            print(f"   {tool}")
            print(f"     {'P(th<0)':>8s} {'EVPI':>9s} {'VERDICT':>9s} "
                  f"{'BIT':>9s} {'V-B median':>11s} {'95% credible':>22s}")
            for w in ws:
                pw = reweight_negative(problem, w)
                r_ = sign_loss_posterior(pw, c, args.alpha, args.draws)
                mark = " <- matched to continuous" if w == \
                    DOCUMENTED_NEGATIVE_MASS else ""
                print(f"     {w:8.3f} {money(pw.evpi()):>9s} "
                      f"{money(r_['v_med']):>9s} {money(r_['b_med']):>9s} "
                      f"{money(r_['gap_med']):>11s} "
                      f"  [{money(r_['gap_lo'])}, {money(r_['gap_hi'])}]{mark}")
            print()


if __name__ == "__main__":
    main()
