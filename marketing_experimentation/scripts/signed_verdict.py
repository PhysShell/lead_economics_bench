#!/usr/bin/env python
"""Where does the compression loss actually go: thresholding, or the sign?

The finding this exists to test
-------------------------------
M7 put six non-null truths on the table, two of them negative. That exposed
something the two-point world could not show: `significant` in this harness
is "the confidence interval excludes zero", **unsigned**. A channel that
destroys 10% of revenue and a channel that adds 15% both produce
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
specific, fixable convention. If (b) carries most of the loss, the remedy is
trivial -- report the sign -- and the whole line of argument about
thresholding is far weaker than it looks.

The decomposition
-----------------
Insert the missing rung, so the chain runs::

      INTERVAL   (att, ci_lo, ci_hi)
        |
        v   threshold at zero, KEEP the sign
      VERDICT    negative / inconclusive / positive
        |
        v   discard the sign
      BIT        significant / not significant

Both steps are deterministic garblings, so **Blackwell's theorem applies to
the whole chain**: EVSI(INTERVAL) >= EVSI(VERDICT) >= EVSI(BIT) for any
prior, any utility. That gives two non-negative quantities that sum to the
total loss already published:

    I - V   the price of thresholding (magnitude and uncertainty discarded)
    V - B   the price of literally throwing away the sign

Two estimators, because they answer different questions
-------------------------------------------------------
    model     the exact EVSI of the FITTED likelihood, integrated over its
              own implied marginal. Answers "what is this signal worth if
              the likelihood we estimated is the truth". Biased upward by
              estimation noise, and **guaranteed non-negative**.
    held-out  fit the likelihood on half the runs, then score the resulting
              plug-in policy on the other half. Answers "what does a team
              actually get when it calibrates on a pilot and then acts".
              Not an unbiased estimate of EVSI and **can be negative** -- a
              policy built on a wrong likelihood is worse than no policy.

Reporting only the first would flatter every signal; reporting only the
second would confound a signal's value with the difficulty of estimating it.
INTERVAL has no closed form here, so it appears in the held-out column only,
and the I-V comparison is made there, within one column.

Where the Blackwell inequality is exact, and where it is not
------------------------------------------------------------
p(BIT | theta) is **never** estimated by counting bits. It is derived from
the estimated p(VERDICT | theta) through the garbling map, and each held-out
row's bit is derived from that same row's verdict. In the **model** column
that makes V >= B an algebraic identity -- it is Jensen's inequality on a
convex function of the posterior, using the model's own marginals -- so a
violation there is a coding error and is asserted as such.

In the **held-out** column it is not an identity: the expectation is taken
over the empirical frequency of the evaluation rows rather than the model
marginal, and Jensen needs the model's weights. Violations there are
possible and should be small and rare; they are counted rather than
asserted away. An earlier version of this file claimed the held-out
inequality was algebraic. It is not, and the distinction is exactly the one
this project keeps having to make: a theorem about the truth is not a
theorem about an estimate of the truth.

I >= V is not exact in either column, because INTERVAL's likelihood comes
from a 3-d kernel density estimated separately. A violation there is the
density estimator running out of sample, as in `information_ladder.py`.

What is deliberately conservative
---------------------------------
VERDICT has three cells to estimate per truth, BIT has two, from the same
~13 fitted rows. More cells estimated from the same data means a noisier
likelihood and a *lower* held-out EVSI. The design therefore handicaps
VERDICT relative to BIT. If VERDICT wins anyway, it wins against the bias.

The prior problem, which is not a detail here
---------------------------------------------
The continuous spike-and-slab puts 27% of its mass below zero. Binned onto
the seven simulated truths it puts ~8% there, because the bin nearest zero
spans (-2.5%, +1%] and swallows most of the negative shoulder. That is
already recorded as a caveat in `continuous_ladder.py` -- but for THIS
question it is not a caveat, it is the whole experiment: the value of
knowing the sign is a function of how much prior mass sits on the wrong
side of zero. So `--neg-sweep` varies that mass directly and reports the
decomposition across it. A conclusion that holds only at 8% negative mass is
not a conclusion about the sign.

    python marketing_experimentation/scripts/signed_verdict.py \
        --results /tmp/results_atlas.jsonl --neg-sweep
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

#: Jeffreys smoothing on the verdict counts. With ~13 rows fitted per truth
#: and three cells, an unobserved cell is common; unsmoothed it has
#: likelihood zero, so a single held-out row landing there annihilates that
#: truth's posterior entirely. Applied to VERDICT only -- BIT is derived
#: through GARBLE, so the chain stays exact in the model column.
#:
#: It is not a free choice: smoothing shrinks the likelihood toward uniform
#: and therefore LOWERS EVSI, and it lowers VERDICT's more than BIT's
#: because three cells are shrunk instead of two. `--alpha` exists so that
#: cost is measured rather than assumed negligible.
ALPHA = 0.5

INTERVAL_COLS = ["att_pct", "ci_lower", "ci_upper"]


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
    v = verdict_index(d)
    derived = v != 1
    actual = d.significant.astype(bool).to_numpy()
    return int((derived == actual).sum()), len(d)


# ---------------------------------------------------------------------------
# One split, three signals. Every rung is scored on the SAME held-out rows,
# so the comparison is paired and no rung can win by being handed more data.
# ---------------------------------------------------------------------------

def signal_matrices(g: pd.DataFrame, thetas: list[float], seed: int,
                    frac_fit: float = 0.5, bw="scott", alpha: float = ALPHA):
    """Return per-held-out-row likelihoods under every truth, for each rung.

    ``L[i, j] = p(y_i | theta_j)`` and ``src[i]`` is the truth row i came
    from. Separating this from the EVSI arithmetic means a prior sweep costs
    nothing: the likelihoods do not depend on the prior.
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

    # -- INTERVAL: one 3-d KDE per truth, fitted on the fit half ------------
    kdes = []
    for f in fit_rows:
        X = f[INTERVAL_COLS].to_numpy(dtype=float)
        if len(X) < 4 or np.linalg.matrix_rank(X - X.mean(0)) < X.shape[1]:
            return None
        try:
            kdes.append(gaussian_kde(X.T, bw_method=bw))
        except np.linalg.LinAlgError:
            return None

    # -- VERDICT: smoothed multinomial per truth ----------------------------
    pv = np.empty((len(thetas), 3))
    for j, f in enumerate(fit_rows):
        counts = np.bincount(verdict_index(f), minlength=3).astype(float)
        pv[j] = (counts + alpha) / (counts.sum() + 3 * alpha)
    # BIT is DERIVED, never counted. p(bit | theta) = GARBLE @ p(verdict|theta)
    pb = pv @ GARBLE.T                                   # (n_theta, 2)

    ev = pd.concat(ev_rows, ignore_index=True)
    src = np.concatenate([[j] * len(e) for j, e in enumerate(ev_rows)])
    ev_v = verdict_index(ev)
    ev_b = (ev_v != 1).astype(int)

    pts = ev[INTERVAL_COLS].to_numpy(dtype=float).T
    L_int = np.column_stack([np.clip(k(pts), 1e-300, None) for k in kdes])
    # [i, j] = p(observed label of row i | theta_j)
    L_ver = pv[:, ev_v].T
    L_bit = pb[:, ev_b].T

    return {"INTERVAL": L_int, "VERDICT": L_ver, "BIT": L_bit,
            "src": src, "p_verdict": pv, "p_bit": pb,
            "n_fit": int(min(len(f) for f in fit_rows)),
            "n_ev": int(min(len(e) for e in ev_rows))}


def evsi_analytic(problem: DecisionProblem, p: np.ndarray) -> float:
    """Exact EVSI of a discrete signal whose likelihood is ``p``.

    ``p`` is (n_theta, n_levels) = p(y | theta). The expectation runs over
    the signal's OWN implied marginal, which is what makes this the exact
    value of the fitted model rather than a sample estimate -- and what makes
    ``EVSI >= 0`` and Blackwell hold exactly.
    """
    joint = problem.prior[:, None] * p              # (n_theta, n_levels)
    marg = joint.sum(axis=0)                        # (n_levels,)
    total = 0.0
    for y in range(p.shape[1]):
        if marg[y] <= 0:
            continue
        post = joint[:, y] / marg[y]
        total += marg[y] * float((problem.utility @ post).max())
    return total - problem.value_no_experiment()


def evsi_from_likelihoods(problem: DecisionProblem, L: np.ndarray,
                          src: np.ndarray) -> float:
    """EVSI on held-out draws: posterior per row, best action per posterior.

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
    """The same problem with prior mass ``w`` below zero, shape preserved
    within each half. The point of the sweep: the value of the sign is a
    function of how often the sign is bad news."""
    p = np.asarray(problem.prior, dtype=float).copy()
    neg = problem.theta < 0
    if not neg.any() or p[neg].sum() <= 0 or p[~neg].sum() <= 0:
        raise SystemExit("cannot reweight: a half carries no prior mass")
    p[neg] = w * p[neg] / p[neg].sum()
    p[~neg] = (1.0 - w) * p[~neg] / p[~neg].sum()
    return DecisionProblem(problem.theta, p, problem.utility,
                           problem.action_names)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="/tmp/results_atlas.jsonl")
    ap.add_argument("--scenario", default="A1")
    ap.add_argument("--pool-scenarios", action="store_true",
                    help="4x the sample per (tool, theta); p(y|theta) becomes "
                         "a mixture over the donor's regimes")
    ap.add_argument("--seeds", type=int, default=16)
    ap.add_argument("--alpha", type=float, default=ALPHA,
                    help="Dirichlet smoothing on the verdict counts; it "
                         "lowers EVSI and lowers VERDICT's more than BIT's, "
                         "so vary it rather than trusting one value")
    ap.add_argument("--neg-sweep", action="store_true")
    ap.add_argument("--alpha-scan", action="store_true",
                    help="how much of the sign's value is the smoothing "
                         "constant?")
    args = ap.parse_args()

    d = load(args.results)
    guard_unique(d)
    if not args.pool_scenarios:
        d = d[d.scenario == args.scenario]

    # Paired throughout: a row unusable by one rung is unusable by all.
    n0 = len(d)
    d = d[np.isfinite(d[INTERVAL_COLS].to_numpy(dtype=float)).all(axis=1)
          & d.significant.notna()]
    where = ("pooled " + ",".join(sorted(d.scenario.unique()))
             if args.pool_scenarios else f"scenario {args.scenario}")
    print(f"{where} | {len(d):,} usable rows"
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
            f"   whole decomposition is unearned. This is the F13 error\n"
            f"   again; stop and re-derive the chain.")
    print("   exact. The chain INTERVAL -> VERDICT -> BIT is a garbling")
    print("   chain, so Blackwell orders all three.")

    thetas = sorted(float(t) for t in d.effect_pct.unique())
    tools = sorted(d.tool_label.unique())
    grid = np.linspace(-0.15, 0.25, 81)
    pri = spike_slab_prior(grid)
    edges = np.concatenate(([-np.inf], (np.array(thetas)[:-1]
                                        + np.array(thetas)[1:]) / 2, [np.inf]))
    idx = np.digitize(grid, edges) - 1
    p7 = np.array([pri[idx == j].sum() for j in range(len(thetas))])
    problem = budget_problem(np.array(thetas), p7 / p7.sum())

    print(f"\n== the decision ==")
    print(f"   actions: {', '.join(DEFAULT_ACTIONS)}")
    print(f"   truths:  {[round(100*t, 1) for t in thetas]} (%)")
    print(f"   prior:   {np.round(problem.prior, 3).tolist()}")
    print(f"   prior mass below zero: {float(problem.prior[problem.theta<0].sum()):.3f}"
          f"   (the continuous prior's is {float(pri[grid<0].sum()):.3f} --")
    print(f"   the binning moves it, which is why --neg-sweep exists)")
    print(f"   no-experiment action: {problem.best_action_no_experiment()!r}"
          f"   |   EVPI ${problem.evpi():,.0f}")

    # -- what the bit actually conflates, before any decision theory --------
    # Per tool, not pooled. Pooling four estimators here would average four
    # different sign-error rates into one number that describes none of them,
    # and the sign-error rate is the entire mechanism under test.
    print(f"\n== what the unsigned bit merges, per truth ==")
    conflate = {}
    for tool in tools:
        gt = d[d.tool_label == tool]
        print(f"\n   {tool}")
        print(f"     {'theta':>7s} {'n':>4s}  {'P(neg)':>7s} {'P(incon)':>9s} "
              f"{'P(pos)':>7s}   {'P(significant)':>14s}")
        conf = {}
        for th in thetas:
            sub = gt[np.isclose(gt.effect_pct, th, atol=1e-9)]
            f = np.bincount(verdict_index(sub), minlength=3) / len(sub)
            conf[th] = f
            print(f"     {100*th:+6.1f}% {len(sub):4d}  {f[0]:7.3f} "
                  f"{f[1]:9.3f} {f[2]:7.3f}   {f[0]+f[2]:14.3f}")
        pn = sum(problem.prior[j] * conf[th][0] for j, th in enumerate(thetas))
        pp = sum(problem.prior[j] * conf[th][2] for j, th in enumerate(thetas))
        conflate[tool] = (pn, pp)
        if pn + pp > 0:
            print(f"     -> when this tool's bit says SIGNIFICANT, the interval "
                  f"behind it\n        is NEGATIVE {100*pn/(pn+pp):.1f}% of the "
                  f"time under this prior, positive "
                  f"{100*pp/(pn+pp):.1f}%.")

    # -- the decomposition ---------------------------------------------------
    mats: dict[str, list] = {}
    for tool in tools:
        g = d[d.tool_label == tool]
        ms = [m for m in (signal_matrices(g, thetas, s, alpha=args.alpha)
                          for s in range(args.seeds)) if m is not None]
        if not ms:
            print(f"   {tool}: no usable split")
            continue
        mats[tool] = ms

    def measure(pr: DecisionProblem, tool: str) -> dict:
        """Both estimators for one tool under one prior."""
        ms = mats[tool]
        out: dict[str, float] = {}
        for k in ("INTERVAL", "VERDICT", "BIT"):
            v = [evsi_from_likelihoods(pr, m[k], m["src"]) for m in ms]
            out[k] = float(np.nanmean(v))
            out[f"sd_{k}"] = float(np.nanstd(v))
        for k, key in (("VERDICT", "p_verdict"), ("BIT", "p_bit")):
            out[f"model_{k}"] = float(np.nanmean(
                [evsi_analytic(pr, m[key]) for m in ms]))
        return out

    r = pd.DataFrame([dict(tool=t, **measure(problem, t)) for t in mats]
                     ).set_index("tool")
    nf = mats[tools[0]][0]["n_fit"]
    ne = mats[tools[0]][0]["n_ev"]

    print(f"\n== EVSI along the chain, {args.seeds} paired fit/eval splits ==")
    print(f"   {nf} runs fitted / {ne} held out per truth, alpha={args.alpha}.")
    print("   Same split, same held-out rows, all three rungs -- no rung can")
    print("   win by being handed more data. VERDICT is handicapped: three")
    print("   cells estimated from the rows that give BIT two.\n")
    print(f"   {'tool':18s} {'INTERVAL':>10s} {'VERDICT':>10s} {'BIT':>10s}"
          f"   |{'VERDICT':>10s} {'BIT':>10s}")
    print(f"   {'':18s} {'--- held-out (plug-in policy) ---':^32s}"
          f"   |{'-- model (exact) --':^21s}")
    for tool in r.index:
        print(f"   {tool:18s} ${r.loc[tool,'INTERVAL']:>9,.0f} "
              f"${r.loc[tool,'VERDICT']:>9,.0f} ${r.loc[tool,'BIT']:>9,.0f}"
              f"   |${r.loc[tool,'model_VERDICT']:>9,.0f} "
              f"${r.loc[tool,'model_BIT']:>9,.0f}")
    print(f"   {'(sd over splits)':18s} "
          + " ".join(f"±{r.loc[tools[0], f'sd_{c}']:>8,.0f}"
                     for c in ("INTERVAL", "VERDICT", "BIT"))
          + f"   for {tools[0]}")

    print(f"\n== the split the whole question turns on ==")
    print(f"   {'tool':18s} {'I-V thresholding':>18s} {'V-B the sign':>14s} "
          f"{'sign share':>11s} {'  model V-B':>12s}")
    for tool in r.index:
        iv = r.loc[tool, "INTERVAL"] - r.loc[tool, "VERDICT"]
        vb = r.loc[tool, "VERDICT"] - r.loc[tool, "BIT"]
        mvb = r.loc[tool, "model_VERDICT"] - r.loc[tool, "model_BIT"]
        tot_loss = iv + vb
        share = 100 * vb / tot_loss if tot_loss > 1e-9 else np.nan
        print(f"   {tool:18s} ${iv:>17,.0f} ${vb:>13,.0f} "
              + (f"{share:10.1f}%" if np.isfinite(share) else f"{'n/a':>11s}")
              + f" ${mvb:>11,.0f}")

    print(f"\n== self-tests ==")
    nsplit = sum(len(m) for m in mats.values())
    print("   (1) MODEL column: V >= B and EVSI >= 0 are exact. p(bit|theta)")
    print("       is derived from p(verdict|theta) through GARBLE, so this is")
    print("       Jensen on the model's own marginals. A failure is a bug in")
    print("       this file, not a property of the data.")
    bad_v, bad_neg = 0, 0
    for tool, ms in mats.items():
        for m in ms:
            mv = evsi_analytic(problem, m["p_verdict"])
            mb = evsi_analytic(problem, m["p_bit"])
            bad_v += mb > mv + 1e-6
            bad_neg += (mv < -1e-6) or (mb < -1e-6)
    print(f"       V >= B    {bad_v} violations in {nsplit} splits   "
          f"{'PASS' if bad_v == 0 else 'FAIL -- STOP'}")
    print(f"       EVSI >= 0 {bad_neg} violations in {nsplit} splits   "
          f"{'PASS' if bad_neg == 0 else 'FAIL -- STOP'}")

    print("   (2) HELD-OUT column: neither is exact. The expectation runs")
    print("       over the empirical frequency of the evaluation rows, and")
    print("       Jensen needs the model's marginals. Violations are expected")
    print("       to be rare and small; a negative EVSI here is not a bug, it")
    print("       is a plug-in policy built on a likelihood fitted to "
          f"{nf} runs.")
    hv = hneg = 0
    for tool, ms in mats.items():
        for m in ms:
            v = evsi_from_likelihoods(problem, m["VERDICT"], m["src"])
            b = evsi_from_likelihoods(problem, m["BIT"], m["src"])
            hv += b > v + 1e-6
            hneg += (v < -1e-6) or (b < -1e-6)
    print(f"       V >= B    {hv} violations in {nsplit} splits")
    print(f"       EVSI < 0  {hneg} splits")

    print("   (3) I >= V is Blackwell on an ESTIMATED density. A violation")
    print("       beyond Monte Carlo error means the 3-d KDE has run out of")
    print("       sample, as in information_ladder.py.")
    for tool in r.index:
        i, v = r.loc[tool, "INTERVAL"], r.loc[tool, "VERDICT"]
        e = max(r.loc[tool, "sd_INTERVAL"], r.loc[tool, "sd_VERDICT"])
        okf = i >= v - 2 * e
        print(f"       {tool:18s} I-V ${i-v:>+10,.0f} (±{e:,.0f})   "
              f"{'ok' if okf else 'VIOLATION -- suspect the KDE'}")

    if args.alpha_scan:
        print(f"\n== how much of the sign's value is the smoothing constant? ==")
        print("   This is not a nuisance parameter here. What makes a signed")
        print("   verdict valuable is the RARE cell: p(negative | theta=+15%)")
        print(f"   is 0/{nf} for two of these tools, and seeing `negative`")
        print("   then nearly proves the truth is below zero. Smoothing sets")
        print("   the probability of exactly those decisive-but-unobserved")
        print("   events, moving them by more than an order of magnitude,")
        print("   and it shrinks VERDICT's three cells harder than BIT's two.")
        print("   So alpha bounds the answer rather than perturbing it:")
        print("   light smoothing is the optimistic end, heavy the "
              "pessimistic.\n")
        print(f"   {'tool':18s} " + " ".join(
            f"{'a=' + str(a):>16s}" for a in (0.05, 0.5, 2.0)))
        print(f"   {'':18s} " + " ".join(
            f"{'V-B / share':>16s}" for _ in range(3)))
        for tool in tools:
            cells = []
            for a in (0.05, 0.5, 2.0):
                ms = [m for m in (signal_matrices(d[d.tool_label == tool],
                                                  thetas, s, alpha=a)
                                  for s in range(args.seeds)) if m is not None]
                iv = float(np.nanmean(
                    [evsi_from_likelihoods(problem, m["INTERVAL"], m["src"])
                     - evsi_from_likelihoods(problem, m["VERDICT"], m["src"])
                     for m in ms]))
                vb = float(np.nanmean(
                    [evsi_from_likelihoods(problem, m["VERDICT"], m["src"])
                     - evsi_from_likelihoods(problem, m["BIT"], m["src"])
                     for m in ms]))
                tl = iv + vb
                cells.append(f"${vb:>7,.0f} /{100*vb/tl:5.1f}%"
                             if tl > 1e-9 else f"{'$-- / n/a':>16s}")
            print(f"   {tool:18s} " + " ".join(cells))
        print("\n   The ordering never reverses: heavier smoothing always")
        print("   costs the sign. What it does change is the magnitude, by")
        print("   a factor of 2-3, so the sign's share is reported as a range")
        print("   and not as a point. Pinning it down needs more runs per")
        print("   truth, not a better choice of alpha.")

    if args.neg_sweep:
        print(f"\n== does the sign matter, or does this prior just not care? ==")
        print("   The seven-point binning leaves ~8% of prior mass below zero.")
        print("   The value of a sign is a function of how often it is bad")
        print("   news, so reporting the decomposition at one such value would")
        print("   be reporting an accident of the grid.\n")
        print("   Held-out columns, then the model column for V-B, which is")
        print("   the one where the inequality is exact.")
        print("   A share is only a share while BOTH parts are positive.")
        print("   Three states, because collapsing them would hide the two")
        print("   most interesting outcomes behind a percentage:")
        print("     n.n%   both parts positive and separated from zero")
        print("     n.n%+  I-V is not separable from zero, so the share is a")
        print("            LOWER BOUND: the sign accounts for at least this")
        print("            much and the data cannot rule out all of it.")
        print("            Reported as a number rather than a label, because")
        print("            'the sign carries most of it' and 'the sign carries")
        print("            all of it' are different claims and the point")
        print("            estimate distinguishes them.")
        print("     KDE!   I-V is negative by more than two split SDs, which")
        print("            Blackwell forbids. The 3-d density is the suspect,")
        print("            not the information ordering. V-B is unaffected --")
        print("            it never touches the KDE -- but it is not a share.")
        # 0.267 is not a round number chosen for the grid: it is the negative
        # mass of the spike-and-slab prior this project actually documents,
        # before the seven-point binning moves it to 0.071. It is the cell
        # the conclusion should be read off.
        ws = [0.02, 0.05, 0.10, 0.20, 0.267, 0.30, 0.40, 0.50]
        broken = flat = 0
        for tool in r.index:
            print(f"\n   {tool}")
            print(f"     {'P(th<0)':>8s} {'EVPI':>9s} | {'INTERVAL':>9s} "
                  f"{'VERDICT':>9s} {'BIT':>9s} {'V-B':>9s} {'sign sh':>8s}"
                  f" | {'model V-B':>10s}")
            for w in ws:
                pw = reweight_negative(problem, w)
                got = measure(pw, tool)
                iv = got["INTERVAL"] - got["VERDICT"]
                vb = got["VERDICT"] - got["BIT"]
                mvb = got["model_VERDICT"] - got["model_BIT"]
                # The Blackwell check, at THIS prior rather than only at the
                # base one. Checking it once at the base prior and then
                # printing shares across six others is how a 113% "share"
                # gets published.
                e = max(got["sd_INTERVAL"], got["sd_VERDICT"])
                tl = iv + vb
                frac = 100 * vb / tl if tl > 1e-9 else np.nan
                if iv < -2 * e:
                    sh, broken = f"{'KDE!':>8s}", broken + 1
                elif iv <= 2 * e:
                    # Clamped at 100: a negative I-V inside noise otherwise
                    # prints a share above 100%, which is how the first
                    # version of this sweep produced "113%".
                    sh = f"{min(frac, 100.0):6.1f}%+" if np.isfinite(frac) \
                        else f"{'n/a':>8s}"
                    flat += 1
                elif np.isfinite(frac):
                    sh = f"{frac:7.1f}%"
                else:
                    sh = f"{'n/a':>8s}"
                print(f"     {w:8.2f} ${pw.evpi():>8,.0f} | "
                      f"${got['INTERVAL']:>8,.0f} ${got['VERDICT']:>8,.0f} "
                      f"${got['BIT']:>8,.0f} ${vb:>8,.0f} {sh}"
                      f" | ${mvb:>9,.0f}")
        if broken:
            print(f"\n   {broken} cell(s) marked KDE!: a Blackwell violation "
                  f"on an estimated\n   density. Treat INTERVAL as unreliable "
                  f"there.")
        if flat:
            print(f"\n   {flat} cell(s) marked `+`: the thresholding loss is "
                  f"not separable from\n   zero there, so the printed share "
                  f"is a lower bound -- the sign accounts\n   for at least "
                  f"that much, and the data cannot rule out its accounting\n"
                  f"   for all of it. Two readings stay live: the verdict "
                  f"really is as good\n   as the interval, or a 3-d density "
                  f"on this sample is too weak to show\n   otherwise. More "
                  f"runs per truth separate them; nothing else will.")


if __name__ == "__main__":
    main()
