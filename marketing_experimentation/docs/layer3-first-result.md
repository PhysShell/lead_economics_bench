# Layer 3: the experiment is usually worth running; the significance gate is not

**Reproduce:** `python marketing_experimentation/scripts/voi_v2.py`
**Superseded first attempt:** `scripts/significance_gate_v1.py`
**Invariants:** `tests/test_decision.py` (131 tests)

---

## 0. The correction that produced the real finding

The first pass reported that a **free** experiment was not worth running over
70% of the business-loss plane. That cannot be true. If information costs
nothing you can always read the result and then do exactly what you would have
done anyway, so

```
EVSI >= 0    whenever   C_experiment = 0
```

always holds. The violation was diagnostic, not fatal: what v1 actually
modelled was a **significance gate**, a policy that is *forced* to obey its
own verdict:

```
significant     -> take the action
not significant -> do not take the action
```

A forced policy can lose to acting on the prior. An optimally-used signal
cannot. v1 is therefore kept and relabelled — the gate is what practice runs,
so the gap between it and the optimal policy is the result.

The invariant is now a test (`test_free_information_never_hurts`), as are
`0 <= EVSI <= EVPI`, "a useless signal is worth exactly zero", and "a perfect
signal is worth exactly EVPI". v2 refuses to print any number until all 1,800
cells pass.

---

## 1. What changes when the signal is used properly

Recast's published runs, scenario A1, `C_FN = $500k`, effect +7.5%.

| | v1 significance gate | v2 optimal use |
|---|---|---|
| cells where a free experiment has negative value | **>70%** | **0 of 450** |
| most negative value seen | large | **−$0.00** (tolerance $0.45) |
| invariant `0 ≤ EVSI ≤ EVPI` | violated | **PASS over 1,800 cells** |

**But the RUN/DON'T-RUN verdict barely moved: 12% of the plane, both times.**
The reason is completely different, and that difference is the finding.

Under v1 the experiment looked worthless because the gate destroyed value.
Under v2 it is genuinely worth something almost everywhere — the *median EVSI
is $0* because a one-bit signal usually fails to move a two-point decision at
all, and where it does move it, the value is real but smaller than a $40k
test.

## 2. The gate's damage is compulsion, not information loss

| measure | value |
|---|---|
| cells where the gate scores worse than acting on the prior | **70%** |
| median share of a *valuable* experiment discarded by the gate | **0%** |

These look contradictory and are not. Where the experiment has material value,
the gate mostly captures it. Where the gate loses, EVSI is near zero — so
there was nothing to discard, and the gate loses by **forcing an action on a
signal that should not have changed the action**.

That is a sharper claim than "p-values throw information away". The mechanism
is that `p < .05` is binding rather than advisory, and it is binding exactly
where it is least informative.

## 3. The result that reverses my earlier claim

I previously wrote that **GeoLift is never optimal — 0% of cells**. That was
an artefact of the gate. Using the *point estimate* rather than the
significance flag, at prior 0.4 and cost ratio 1 (EVPI ceiling $200k):

| tool | EVSI, binary flag | EVSI, point estimate | uplift |
|---|---|---|---|
| `geolift` | $3,600 | **$50,260** | **+1,296%** |
| `causalpy` | $8,200 | $48,661 | +493% |
| `google_mm` | $35,100 | $55,490 | +58% |
| `causalimpact` | $40,800 | **$57,006** | +40% |

**GeoLift recovers almost all of the gap.** The gate was discarding roughly
93% of its value, and "never optimal" was a statement about `p < .05`, not
about GeoLift.

> **Retraction, see the addendum.** An earlier version of this paragraph
> attributed the recovery to GeoLift's *wide interval* moving the posterior.
> The code does not show that — the likelihood here is built from `att_pct`
> alone, and adding the interval width was later measured at between −$1,475
> and +$96 with a sign that flips across bandwidths. What the data support is
> that GeoLift's **distribution of point estimates** is informative while its
> significance flag is not.

And the second-order observation matters more than the first:

> Under the binary flag the four tools span **11×** in value ($3.6k–$40.8k).
> Under the point estimate they span **17%** ($48.7k–$57.0k), and on the
> 8-split averages in the addendum, **12%** ($46.3k–$52.0k).

Recast observe that point estimates are close in easy cases and that the
uncertainty story is what separates the tools. On this evidence that
separation is largely a separation *at the threshold*: once the estimate
updates a belief rather than passing a test, the four converge to within 12%.

**An earlier version of this paragraph said their framing was right "because
their users live in the gated world", which was unfair to them.** Recast's
own practitioner guidance is explicitly decision-aware — it says the choice
depends on the relative cost of the two errors (GeoLift where a false
positive is dearer than a missed winner, Google MM where more decisive
answers are needed and extra false positives are tolerable) and warns that
GeoLift's wide intervals make decisions harder. They are not assuming the
gate; they are advising within it.

The question this track adds sits one step further out: **given that the
estimator produces a distribution, how much decision value is destroyed by
compressing it to significant / not significant at all?**

## 3a. The candidate headline — conditional on M7, stated now so it can fail

If the continuous-θ ladder confirms it, the result this track is actually
carrying is not about GeoLift and not about `p < .05`:

> **An estimator's statistical calibration and the decision value of its
> standard significance interface are different properties.** Binarisation
> can destroy most of the usable information even in a well-calibrated
> method.

GeoLift is the clean illustration and not the subject. Stated as a
**conjunction**, because an earlier draft wrote it as a causal chain —
"calibrated inference → wide interval → TPR 8.7% → mute channel" — and good
calibration is not what *causes* a wide interval. In this Recast regime
GeoLift simultaneously:

- is the only tool whose false-positive rate matches its nominal level
  (4.6% against 5%), **and**
- produces intervals ~2.5× wider than its own sampling SD would require, **and**
- detects a real +7.5% lift only 8.7% of the time, so its significance
  channel is nearly mute, **and**
- retains a point-estimate channel whose decision value is within 12% of the
  best of the four.

Those four facts hold together. Which of them explains which is not
established here, and the claim does not need it to be.

**What would falsify it.** If M7 shows that with a continuous θ and five
actions the S0 gap *narrows* — that the bit turns out to be close to a
sufficient summary once the decision is realistic — the claim dies, and the
two-point world will have been flattering it. That is the test, and it is
running.

This is written down before the result arrives so that it cannot be
retrofitted to whatever M7 says.

## 4. What this does to the research question

| layer | status |
|---|---|
| 1. statistical behaviour | occupied — Recast, Statsig, Microsoft ExP |
| 2. regime selection | prize looks smaller than assumed: under optimal use the tools converge |
| 3. business decision | **the live question, and it moved** |

The question is no longer "which estimator should this business use". It is:

> Marketing experimentation platforms compute statistical significance
> competently, and then convert evidence into budget action with a rule that
> is beaten by acting on the prior in 70% of the plane. Is the gap between
> `p < .05` and the posterior-optimal action large enough, on realistic data
> regimes, to be worth building?

That is a harder claim for a head-to-head leaderboard to kill, because it is
not a claim about estimators at all.

## 4a. The provenance of every number above, which changed after they were written

Everything in §§1–4 was computed from Recast's published `results.jsonl`,
taken on trust. That is the normal standard in this field and it is weaker
than it looks: it means the conclusions inherit any error in an artefact
nobody outside the authors has executed.

**That artefact has since been independently reproduced end to end** — see
`donor-repro.md` §4d. R 4.5.1 and Python 3.12.8 assembled to the donor's own
pins, the harness run unmodified on Linux x86_64 with reference BLAS against
a study produced on macOS ARM64:

| | |
|---|---|
| DGP (`true_att_level`) | 80/80 exact to 1e-9 |
| `google_mm` | 40/40 within 1e-9 relative, worst 2.5e-13 |
| `geolift`, `causalimpact` | 40/40, worst difference **exactly 0** |
| `causalpy` | mean Δ +0.0010pp against 2×SE 0.0122pp |

So the likelihoods underneath the EVSI figures are built on data that has
been regenerated and re-estimated, not merely downloaded. **The decision-layer
conclusions stand on a reproduced substrate.**

Two things this does *not* fix, and they are the same two as before: the DGP
is still synthetic and still two-point. Reproducing a simulation faithfully
says nothing about whether the simulation resembles a real marketing
experiment. §5 still applies in full.

One thing it does fix, and it is worth naming because it was a real risk:
the alternative was to build a decision layer on top of numbers that might
not have survived contact with an interpreter, and to discover that after
M7 rather than before it.

## 5. What this still cannot establish

- **A two-point prior.** θ ∈ {0, +7.5%} is all the published data supports,
  because Recast simulated exactly two truths. A real prior is a distribution
  over effect *size*, including negative effects — a marketing test can
  discover that a channel actively destroys money, and nothing here can
  represent that. This needs simulations at −10%, −5%, −2%, 0, +1%, +2%, +5%,
  +7.5%, +10%, +15%, or a continuous sweep.
- **Two actions.** hold / scale. Real budget decisions are cut / hold / raise
  moderately / raise hard, and the value of information rises with the
  richness of the action set.
- **One scenario and one cost setting** for the headline comparison.
- **KDE likelihood on 500 held-out runs per arm.** The fit/evaluate split is
  in place so the density has not seen the points it scores, but the tails are
  thin and the continuous EVSI numbers should be read as indicative.
- **Recast's synthetic DGP**, with its stated limitations.

## 6. Next, in order

1. Effect-size sweep — the single highest-value missing input. Everything in
   §3 rests on two points of θ.
2. Richer action set, which should raise EVSI across the board.
3. Spike-and-slab prior over effect size, ideally empirical from published
   marketing experiments.
4. Only then, re-derive the phase diagram and the selector question.

Vendor archaeology is paused until these are done. The landscape told us where
the gap is; continuing to read vendor documentation will not tell us whether
it is worth anything.

---

# Addendum 3: the loss split in two — thresholding, or the missing sign?

**Reproduce:** `python marketing_experimentation/scripts/signed_verdict.py
--results /tmp/results_atlas.jsonl --pool-scenarios --neg-sweep --alpha-scan`

No new runs. Same 2,800 rows as Addendum 2.

Addendum 2 reported that the significance bit keeps **0–11.9%** of what the
interval is worth, and three of four tools have a significance channel worth
**exactly $0**. That number is not in question here. What is in question is
the sentence everyone — including me — attached to it: *thresholding destroys
decision value*.

There is a second explanation, and M7 is what made it visible. `significant`
in this harness is **unsigned**. A channel that destroys 10% of revenue and
one that adds 15% both produce `significant = True`. So the bit might be
worth nothing not because it is coarse but because it is *ambiguous*, and
those two diagnoses have completely different consequences. Coarseness is an
argument about statistical practice. Ambiguity is a line in a report
template.

## The missing rung

INTERVAL → **VERDICT** (negative / inconclusive / positive) → BIT. Both steps
are deterministic garblings, so Blackwell orders the whole chain and the loss
splits into two non-negative parts:

* **I − V** — the price of thresholding: magnitude and uncertainty discarded.
* **V − B** — the price of literally throwing the sign away.

The premise was checked, not assumed: `significant == (verdict ≠
inconclusive)` on **2,800/2,800 rows**. F13 is what happens when that check
is skipped.

## What the bit merges

Under the seven-point prior, when each tool's bit says SIGNIFICANT, the
interval behind it is **negative**:

| tool | P(negative \| significant) | P(significant) at θ=+15% |
|---|---|---|
| `causalpy[y_hat]` | **34.6%** | 0.64 |
| `geolift` | **39.7%** | 0.19 |
| `google_mm` | 14.4% | 0.75 |
| `causalimpact` | 12.7% | 0.86 |

A third of `causalpy`'s significant results and two-fifths of `geolift`'s are
the channel losing money, reported with the same symbol as the channel
working.

## The split, at the seven-point prior

Pooled, 16 paired fit/eval splits, 50 runs fitted / 50 held out per truth,
α = 0.5. Every rung scored on the *same* held-out rows.

| tool | INTERVAL | VERDICT | BIT | I − V | V − B | **sign share** |
|---|---|---|---|---|---|---|
| `causalimpact` | $4,904 | $1,451 | $650 | $3,454 | $801 | **18.8%** |
| `causalpy[y_hat]` | $4,171 | $2,855 | $0 | $1,316 | $2,855 | **68.4%** |
| `geolift` | $5,269 | $392 | $29 | $4,877 | $363 | **6.9%** |
| `google_mm` | $6,081 | $1,388 | $11 | $4,693 | $1,377 | **22.7%** |

At *this* prior the original reading survives for three of four tools:
thresholding carries 77–93% of the loss. `causalpy` is the exception, and a
sharp one — its bit is worth **$0** while its verdict is worth $2,855. For
`causalpy`, the entire value of the discrete signal is the sign.

## And then the prior moves, and so does the answer

This is the part that damages the headline. The seven-point grid puts
**0.071** of the prior mass below zero; the continuous spike-and-slab the
project actually documents puts **0.267** there. Addendum 2 already recorded
that as a limitation. For this question it is not a limitation, it is the
whole experiment — *the value of a sign is a function of how often the sign
is bad news.*

Sign share as negative mass rises. A `+` marks a cell where I − V is not
separable from zero, so the figure is a **lower bound** — the sign accounts
for at least that much and the data cannot rule out all of it:

| P(θ<0) | `causalimpact` | `causalpy` | `geolift` | `google_mm` |
|---|---|---|---|---|
| 0.02 | 6.7% | 72.7%+ | 11.4% | 25.9% |
| 0.10 | 27.2% | 64.2% | 5.9% | 24.0% |
| 0.20 | 51.2%+ | 67.2% | 5.2% | 36.7% |
| **0.267** *(the documented prior)* | **63.3%+** | **79.4%+** | **6.8%** | **48.7%** |
| 0.30 | 68.7%+ | 87.0%+ | 7.3% | 54.0% |
| 0.50 | 65.7%+ | 100%+ | 4.0% | 57.4% |

0.267 is in the sweep because it is the negative mass of the prior this
project wrote down, not because it is a round number. At that cell the sign
is worth **$3,259** (`causalimpact`), **$5,799** (`causalpy`), **$595**
(`geolift`) and **$3,423** (`google_mm`), against bits worth $3,552, $45,
$424 and $3,185.

**At the prior this project wrote down, the missing sign carries most of the
loss for two of four tools (63%, 79%), about half for a third (49%), and
almost none for `geolift` (7%).** Not "three of four" — `google_mm` sits on
the line and saying otherwise would be rounding in the direction I want. The
"thresholding" reading was nonetheless an artefact of a discretisation that
deleted the negative half of the prior, and Addendum 2 flagged that
discretisation as a caveat without noticing it was load-bearing for the
interpretation.

One thing the table does *not* say: that the bit is inert at this prior. At
P(θ<0) = 0.267 the bit is worth $3,552 for `causalimpact` and $3,185 for
`google_mm` — far from the $650 and $11 it scores on the seven-point prior.
More negative mass makes every signal more valuable, EVPI included ($24,806 →
$33,126). The sign share rises because V − B grows faster than I − V, not
because the bit collapses.

`geolift` is the one clean exception, for a reason that is not about signs at
all: its `P(significant)` runs 0.05–0.19 across *every* truth. It has almost
no power at this sample size, so its verdict is nearly inert and there is
nothing for the sign to carry. That is a statement about `geolift`'s power,
not evidence for thresholding.

## Three things that keep this from being stronger than it is

1. **α is not a nuisance parameter.** What makes a signed verdict valuable is
   the rare cell — `p(negative | θ=+15%)` is 0/50 for two tools, so seeing
   `negative` nearly proves θ < 0. Smoothing sets the probability of exactly
   those decisive-but-unobserved events. The sign share across α ∈
   {0.05, 0.5, 2.0}: `causalimpact` 24.3→8.7%, `causalpy` 82.0→36.8%,
   `geolift` 13.3→0.0%, `google_mm` 30.4→7.6%. The ordering never reverses —
   heavier smoothing always costs the sign — but the magnitude moves by 2–3×.
   **The sign's share is a range, not a point**, and closing it needs more
   runs per truth, not a better α.
2. **The `+` cells have two readings.** The thresholding loss is
   indistinguishable from zero there. That is consistent with the verdict
   genuinely being as good as the interval, *and* with a 3-d KDE on 50 points
   being too weak to demonstrate the interval's advantage. Both are live, and
   they differ by a lot — 63% and 100% are not the same claim. Addendum 2's
   own INTERVAL − POINT result was undetectable for all four tools at this
   sample size, which is the same weakness showing up twice.
3. **Two estimators, reported side by side.** The *model* column (exact EVSI
   of the fitted likelihood) and the *held-out* column (the plug-in policy
   scored on fresh runs) agree closely here — $1,451 vs $1,514, $2,855 vs
   $2,780, $392 vs $386, $1,388 vs $1,491 — so this is not an estimation
   artefact. The distinction still matters: only the model column is
   guaranteed non-negative, and on the A1-only data at high negative mass the
   held-out BIT went to **−$374**, a calibrated-on-a-pilot policy that is
   worse than ignoring the experiment.

## What this does to the research question

It does not kill the central idea, and it does not confirm it as stated. It
**splits** it:

> The significance bit is worth near-zero in a five-action budget decision.
> Under the seven-point grid that is mostly thresholding; under the prior the
> project actually documents, the discarded sign carries most of it for two
> of four tools and about half for a third. The two explanations are
> separable, they were never separated before, and which one dominates
> depends on how much prior mass sits below zero.

The practical consequence is uncomfortable and worth stating: **a large part
of the loss this track has been attributing to significance testing is
recoverable by printing a sign.** That is a cheaper remedy than the one the
brief was circling, and an honest report has to lead with it rather than
bury it.

What survives intact is the narrower claim, because the sign does not rescue
it: even the *signed* verdict keeps only 8–68% of the interval's value at the
seven-point prior. Thresholding costs real money. It is just not the whole
bill, and it is not the majority of it under the documented prior.

---

# Addendum 2: M7 — seven truths, five actions

**Reproduce:** `python marketing_experimentation/scripts/continuous_ladder.py
--results /tmp/results_atlas.jsonl --pool-scenarios`

2,800 rows, θ ∈ {−10, −5, 0, +2, +5, +7.5, +15}%, 25 iterations × 4
scenarios, 0 duplicated identities. Pooled across scenarios for ~100 rows per
(tool, θ) — at 25 a 3-d density has no chance, and the A1-only run showed it:
`causalimpact`'s INTERVAL EVSI was $11,985 there and is $5,273 pooled.

| tool | BIT | POINT | INTERVAL | **BIT keeps** |
|---|---|---|---|---|
| `causalimpact` | $626 | $5,058 | $5,273 | **11.9%** |
| `causalpy` | $0 | $4,644 | $4,435 | **0.0%** |
| `geolift` | $0 | $4,778 | $6,207 | **0.0%** |
| `google_mm` | $0 | $4,712 | $6,322 | **0.0%** |

## The preregistered claim is not falsified

§3a said the claim dies if the S0 gap *narrows* once θ is continuous and the
action set realistic. It widened:

> **BIT keeps 0–11.9% of INTERVAL** under seven truths and five actions,
> against **7.2–34.1%** under two truths and two actions.

Three of four tools have a significance channel worth **exactly $0** — the
bit never changes the optimal action at any point of the seven-truth grid.
That is not a small ratio; it is inertness, and it should be said that way.

## What this does **not** settle, and it is the same question twice

Addendum 0 retracted "the interval adds nothing" because on the two-point
data with the full bounds it added a great deal (held-out AUC 0.77 → 0.92).
Here, pooled:

| tool | INTERVAL − POINT | |
|---|---|---|
| `google_mm` | +$1,610 (±1,210) | undetectable |
| `geolift` | +$1,429 (±1,541) | undetectable |
| `causalimpact` | +$215 (±1,070) | undetectable |
| `causalpy` | −$209 (±732) | undetectable |

**All four undetectable.** That is not a second retraction, because the two
measurements are not comparable: different decision problem, different number
of truths, and 1,000 rows per arm there against ~100 here. **The seven-truth
run is too thin to adjudicate it**, and the AUC evidence at n=1,000 remains
the strongest thing available on that question.

Blackwell does not order POINT against INTERVAL, so `causalpy`'s −$209 is
permitted and is not a harness failure. The guaranteed inequality —
INTERVAL ≥ BIT — holds for all four.

## Two limitations of this run, both structural

1. **The seven-point grid loses the negative half.** Carrying the
   spike-and-slab prior onto the simulated truths by Voronoi bins puts
   **0.071** of the mass below zero against **0.267** in the continuous
   prior, because the bin nearest zero spans (−2.50%, +1.00%] and absorbs
   everything on either side. The decision problem being solved is not the
   one the prior describes, and it is under-exercised on exactly the half the
   brief cares about most. The script now prints this as a warning rather
   than leaving it to be discovered.
2. **25 iterations per cell.** Enough for the atlas questions — bias,
   variance, power — and not enough for a 3-d density. Pooling buys 4× at the
   cost of making `p(y|θ)` a mixture over the donor's four regimes, which is
   arguably the right likelihood for someone who does not know their regime
   and the wrong one for someone who does.

**The next move is more iterations and a finer grid near zero, not a louder
claim.**

---

# Addendum 0: the ladder was not a ladder — a structural retraction

**Everything in Addendum 1 below was computed on a representation graph that
does not hold.** The error is structural rather than numerical, and it
changes one of this track's headline claims.

## What was wrong

The ladder assumed S0 (significance bit) was a coarsening of S1 (point
estimate), which was a coarsening of S2 (estimate + interval width), and
asserted `EVSI(S2) ≥ EVSI(S1) ≥ EVSI(S0)` as a nesting.

**`significant` is not computed from the point estimate.** In this harness it
is exactly "the confidence interval excludes zero" — checked here rather than
assumed, at **100.00% agreement, 0 mismatches in 2,000 rows per tool**. So
the bit is a function of the *interval*, and S0 was never a coarsening of S1.
They are two different projections of the same result, and

> `EVSI(S1) − EVSI(S0)` could not be called "the price of binarisation",
> because S0 is not S1 binarised.

## The correct structure, and what it buys

```
FULL   (att, ci_lo, ci_hi, diagnostic)
  │
  ├──────────────────────→ POINT  (att)          side branch
  │
  ▼
INTERVAL (att, ci_lo, ci_hi)
  │
  ▼  deterministic garbling
BIT    (does the interval exclude zero?)
```

Along the vertical chain the bit genuinely is a deterministic garbling, so
**Blackwell's theorem guarantees** `EVSI(FULL) ≥ EVSI(INTERVAL) ≥ EVSI(BIT)`
for *any* prior and utility. That is no longer a hypothesis to test but an
identity — which converts a violation into a **self-test on the harness**: if
measured EVSI(INTERVAL) falls below EVSI(BIT), the density estimation is
broken, because the information ordering cannot be.

`POINT` sits off the chain. Neither it nor the bit is a garbling of the other
— the point drops the interval, the bit drops the magnitude — and Blackwell
orders only comparable experiments. `POINT − BIT` is an empirical property of
a particular decision problem, not a theorem, and is now reported under its
own heading.

**S2 also had to change from `(att, width)` to `(att, ci_lower, ci_upper)`.**
The intervals are not symmetric about the estimate — median |att − midpoint|
runs 1.3–8.3% of the width — so `(att, width)` recovers significance only
**94–97%** of the time and would have silently broken the nesting.

## What the corrected measurement says

| tool | BIT | POINT | INTERVAL | FULL |
|---|---|---|---|---|
| `causalimpact` | $40,800 | $51,967 | **$119,599** | n/a |
| `google_mm` | $35,100 | $51,335 | **$117,561** | $105,664 † |
| `causalpy` | $8,200 | $46,825 | $64,624 | $65,278 |
| `geolift` | $3,600 | $46,445 | $49,856 | $49,984 |

† flagged by the Blackwell self-test: FULL < INTERVAL, so the 4-d density has
run out of sample. Treat the FULL column as unreliable.

**This retracts the claim that "the interval adds nothing".** That was
measured on `(att, width)`, and the width alone really does add little. The
full bounds add a great deal for three of four tools.

## Held-out AUC, because EVSI across dimensions is not comparable

A 3-d KDE has more room to find structure that is not there. AUC on the same
held-out points is dimension-agnostic and cannot be inflated by overfitting
the fit half:

| tool | POINT | INTERVAL | Δ | |
|---|---|---|---|---|
| `causalimpact` | 0.7725 | **0.9200** | +0.1475 | interval discriminates better |
| `google_mm` | 0.7630 | **0.9126** | +0.1496 | interval discriminates better |
| `causalpy` | 0.7581 | 0.8244 | +0.0663 | interval discriminates better |
| `geolift` | 0.7553 | 0.7224 | **−0.0329** | no better — the extra dimensions cost more than they carry |

Cross-checked against three other families — **reproduce:**
`python marketing_experimentation/scripts/likelihood_models.py`. The
direction survives, and the **magnitudes do not, by a wide margin**:

| tool | INTERVAL EVSI across four families |
|---|---|
| `google_mm` | $64,339 – **$171,729** |
| `causalimpact` | $72,752 – **$148,771** |
| `causalpy` | $61,021 – $100,672 |
| `geolift` | $49,856 – $60,053 |

A spread of up to **2.7×**, against roughly 1.3× at POINT. **So the EVSI
*levels* at INTERVAL carry no weight at all** — a Gaussian mixture wins on
held-out log-likelihood for every tool and also produces the largest
numbers, which is exactly the pattern that cannot be told apart from a
better fit finding real structure without a dimension-agnostic arbiter.

That arbiter is the held-out AUC above, and it is the only part of this
comparison that should be quoted. The dollar figures are reported so the
family-dependence is visible, not because any of them is the answer.

**GeoLift is the exception in both families**, which rescues a piece of the
original claim in a narrower form: for GeoLift specifically, the interval
adds nothing on top of the point estimate. For the other three it adds
substantially, and the earlier blanket statement was an artefact of using the
width instead of the bounds.

---

# Addendum 1: the information ladder, and a claim of mine it refutes

> **Superseded in structure by Addendum 0.** The S1→S2 numbers below were
> computed with `S2 = (att, ci_width)` on an assumed nesting that does not
> hold. They are kept because the bandwidth and likelihood-family analysis in
> §A remains valid *for the signal it actually measured* — the width — and
> because the reasoning is part of the record.

**Reproduce:** `python marketing_experimentation/scripts/information_ladder.py --bandwidth-scan`

## A. The overstatement, retracted

I wrote that GeoLift's "wide, conservative interval still moves the posterior
enough to change a budget decision". **The code did not show that and now
shows it is not detectable.** `voi_v2.py` built its likelihood from `att_pct`
alone; the interval of any individual run never entered it. The claim was an
interpretation dressed as a result.

Measuring it properly, by adding the interval width as a second signal
dimension:

| rung the decision sees | causalimpact | causalpy | geolift | google_mm |
|---|---|---|---|---|
| **S0** significant / not | $40,800 | $8,200 | $3,600 | $35,100 |
| **S1** point estimate | $51,967 | $46,825 | $46,445 | $51,335 |
| **S2** estimate + CI width | $51,040 | $46,920 | $46,272 | $49,860 |
| **S3** + tool diagnostic | n/a | $51,325 | $45,945 | $50,378 |

`S1 → S2` is worth between **−$1,475 and +$96**, against a per-cell standard
deviation of $2–3k across 8 fit/evaluate splits. And the bandwidth scan shows
the *sign flips*: +$1.2k at bw=0.3, −$1.7k at Scott's rule, +$1.9k at bw=1.5.
So it is not a small effect, it is an undetectable one, and no direction can
be claimed.

**The interval adds nothing measurable on top of the point estimate here.**

### A.1 The obvious objection, tested and rejected

Every number above passes through one Gaussian KDE, and a KDE is exactly the
estimator that degrades when a dimension is added. So the null had an
alternative explanation that the bandwidth scan alone could not rule out:
**the second dimension might carry information the estimator cannot see.**

**Reproduce:** `python marketing_experimentation/scripts/likelihood_models.py`

Four likelihood families, each fitted on half the runs and scored on the
other half by held-out log-likelihood — a proper scoring rule, so no family
can win by flexibility alone. `S2 − S1` under each:

| tool | kde | gauss | student-t | gmm |
|---|---|---|---|---|
| `causalimpact` | −$927 | **+$475** | −$1,321 | **+$651** |
| `causalpy` | +$96 | +$1,330 | −$1,579 | +$2,120 |
| `geolift` | −$173 | +$1,850 | −$1,220 | +$4,681 |
| `google_mm` | −$1,475 | +$126 | −$903 | +$403 |

Per-cell standard deviations run $1,800–$4,000, so every entry is inside one.
And:

> **Tools where all four families agree even on the *sign*: 0 of 4.**

The decisive entry is `gauss`. A full-covariance Gaussian has five parameters
in two dimensions and cannot be starved by the extra dimension the way a KDE
can — if the CI width carried information that the KDE was too thin to see,
the Gaussian would see it. It finds nothing either. **The null is a property
of the data, not of the density estimator**, and the ladder result stands.

The one entry worth naming: GeoLift under `gmm`, +$4,681 against a $2,511
standard deviation — 1.9σ, the largest anywhere in the table, and in the
direction my retracted claim guessed. It is contradicted in sign by two of
the other three families and does not survive as evidence. Recorded rather
than buried, because if θ ranges widely at M7 and it reappears, it was the
first sign.

### A.2 A caveat this comparison exposes, which the ladder did not

The *level* of EVSI is strongly family-dependent, even though the
differences are not:

| family | S1 range across the four tools | spread |
|---|---|---|
| `kde` | $46,445 – $51,967 | 11.9% |
| `gauss` | $54,621 – $60,695 | 11.1% |
| `student_t` | $60,971 – $67,386 | 10.5% |
| `gmm` | $49,485 – $56,694 | 14.6% |

So the headline EVSI figures in §3 and §B are **KDE figures**, and a
Student-t density would put them 30% higher. They should be read as
"of this order", not as estimates. That the published ones happen to be the
lowest is luck, not caution, and is noted so that a later switch of density
cannot look like an improvement.

**The convergence claim is unaffected, and that is the one that mattered.**
The four tools span 10.5–14.6% at S1 under every family, against **11× at
S0**. Whatever separates these tools in an FPR/FNR table stops separating
them once the estimate updates a belief — and that conclusion does not
depend on how the belief is updated.

## B. What is actually true, and it is stronger

The whole compression tax sits at one rung — **S0 → S1** — and it is enormous
and strikingly unequal between tools:

| tool | share of its own decision value that survives the significance bit |
|---|---|
| `geolift` | **7.8%** |
| `causalpy` | 17.5% |
| `google_mm` | 70.4% |
| `causalimpact` | 79.9% |

GeoLift does not have a weak estimator. **It has an informative estimator
behind a gate that discards 92% of what it knows.** That is a property of the
reporting interface, not of the synthetic control underneath it.

And the convergence result holds at every continuous rung: the four tools span
**11×** at S0 and about **12%** at S1–S2 ($46.3k–$52.0k against a $200k EVPI
ceiling). Whatever separates these tools in an FPR/FNR table largely stops
separating them once the estimate updates a belief instead of passing a
threshold.

Monotonicity `EVSI(S2) ≥ EVSI(S1) ≥ EVSI(S0)` holds for all four tools within
two standard deviations, so the ladder is behaving as a coarsening hierarchy
should and the S1→S2 null is not a density-estimation artefact.

## B.1 Why the S0 ranking is what it is — and why it is not a quality ranking

§B reports that the share of decision value surviving the significance bit
runs from 7.8% (`geolift`) to 79.9% (`causalimpact`). That ordering needed an
explanation, and it has an exact one, using Recast's own published
calibration numbers rather than anything of ours.

At rung S0 the decision sees exactly one bit. That channel is **fully
described by two numbers** — how often it fires under each truth — and
nothing else about the estimator reaches the decision. Scenario A1, from the
donor's `metrics.csv`:

| tool | FPR | TPR | coverage | bias | **S0 keeps** |
|---|---|---|---|---|---|
| `geolift` | **4.6%** | 8.7% | 92–95% | +0.2 pp | **7.8%** |
| `causalpy` | 19.8% | 33.8% | 80% | −1.0 pp | 17.5% |
| `google_mm` | 16.9% | 42.9% | 83% | +2.0 pp | 70.4% |
| `causalimpact` | **27.8%** | 62.1% | 72% | +3.8 pp | **79.9%** |

**Reproduce:** `python marketing_experimentation/scripts/s0_reconstruction.py`

An earlier version of this section reported a Spearman correlation of 1.00
between discrimination (TPR − FPR) and S0 retention, and called it a
mechanistic explanation. **It is not one.** A perfect rank correlation on
four points has an exact two-sided permutation p-value of 2/4! = 0.083, and
more fundamentally a correlation is not a mechanism. The mechanism is
available in closed form:

```
EVSI(S0) = min(pi*c_FN, (1-pi)*c_FP)
         - min(pi*(1-TPR)*c_FN, (1-pi)*(1-FPR)*c_FP)
         - min(pi*TPR*c_FN,     (1-pi)*FPR*c_FP)
```

Evaluated from Recast's **published** FPR and FNR — aggregated by their
`compute_metrics.py`, not ours — against the S0 figures the ladder obtained by
counting significance flags row by row:

| tool | from published rates | from our row counts | difference |
|---|---|---|---|
| `causalimpact` | $40,800 | $40,800 | **$0.00** |
| `google_mm` | $35,100 | $35,100 | **$0.00** |
| `causalpy` | $8,200 | $8,200 | **$0.00** |
| `geolift` | $3,600 | $3,600 | **$0.00** |

> **EVSI(S0) is reconstructed to the dollar from two numbers per tool.**
> `(FPR, TPR)` is a **sufficient statistic** for it: all 32,000 published
> rows enter the S0 rung through those two numbers and nothing else. Every
> point estimate, every interval, every diagnostic is discarded before the
> decision sees anything.

Stated carefully, because the temptation is to call this two independent
measurements and it is not — both paths read the same `significant` flags,
and what differs is the aggregating code. The content is the **sufficiency**,
which is precisely what the compression-tax result needs: it is not that S0
correlates with the binary channel, it is that S0 *is* the binary channel.

GeoLift, written out: `200,000 − 182,600 − 13,800 = 3,600`.

**A shortcut that does not work**, recorded because the first draft of the
script was about to assert it. `EVSI = EVPI × (TPR − FPR)` matches a few
cells and is wrong by up to **$80,000** across the grid; it would put GeoLift
at $8,200 where the true value is $3,600. The `min()` structure is the whole
content — the bit is worth something only where it moves the posterior far
enough to change which loss binds. This is also why the earlier rank
correlation, though real, explained nothing: the ordering happens to agree
with discrimination without being a function of it.

Reading the table left to right then makes the uncomfortable part plain:

**The tool that keeps most of its value through the significance gate is the
worst-calibrated one, and the tool that keeps least is the only
well-calibrated one.** `causalimpact` scores highest at S0 because it rejects
often — 27.8% of the time when nothing is happening — and a bit that fires
often discriminates more in a world where the effect is present 40% of the
time. Its intervals cover 72% of the time against a nominal 95%, and it
overstates lift by nearly four percentage points.

### What this does to the GeoLift claim, which it strengthens

§B said GeoLift "has an informative estimator behind a gate that discards 92%
of what it knows". That was an inference from our EVSI numbers. It now has
direct support from the donor's:

> **GeoLift detects a real +7.5% lift 8.7% of the time.** Its interval is
> 52 pp wide against 19–22 pp for the others. It is the only tool whose false
> positive rate matches its nominal level (4.6% against 5%).

Meanwhile its *point estimate* is worth $46,445 — within 12% of the best of
the four. **Calibrated, nearly powerless, and as informative as anything else
once you stop thresholding it.**

An earlier version of this passage said it "achieves that by being almost
powerless", which asserts a causal link this evidence does not carry. The
four properties — nominal FPR, wide interval, low TPR, informative point
estimate — are observed together in this DGP. Which explains which is not
established, and the claim does not require it to be.

### Where this leaves Recast's conclusion and ours

They are compatible, and they are answers to different questions:

**Recast are not naive about this**, and an earlier draft of this section
implied they were. Their own practitioner guidance says the choice depends on
the relative cost of the two errors — GeoLift when a false positive is more
expensive than a missed winner, Google MM when more decisive answers are
needed and extra false positives are tolerable — and they warn explicitly
that GeoLift's wide intervals make decisions harder. They also note that
point estimates are close in easy cases and that the uncertainty story is
what separates the tools.

So this is a continuation, not a contradiction:

| | question answered |
|---|---|
| **Recast** | given that you must report a verdict, which tool's error rates are what they claim, and how should the cost of the two errors steer the choice? |
| **This track** | how much decision value is destroyed by compressing the estimate into that verdict at all? |

The S0 ranking — an 11× spread — is largely a ranking of **how willing each
tool is to reject**, and it disappears at S1, where the four converge to
within 12%. The interesting object is the compression, not the ranking.

## B.2 Does the retention result survive the rest of the business plane?

Every figure in §B is computed at **one cell**: prior 0.4, cost ratio 1. If
"GeoLift keeps 7.8%" became 60% at a different prior, the headline would be a
coincidence of that cell. Swept over 7 priors × 5 cost ratios = 35 cells.

**Reproduce:** `python marketing_experimentation/scripts/information_ladder.py --sweep`

The first thing the sweep says is not about the ordering at all:

| tool | cells where its bit is worth > $100 | median retention *there* | at 0.4/1.0 |
|---|---|---|---|
| `causalimpact` | **12 / 35** | 72.3% | 78.5% |
| `google_mm` | **12 / 35** | 59.3% | 68.4% |
| `causalpy` | **6 / 35** | 30.8% | 17.5% |
| `geolift` | **6 / 35** | 9.9% | 7.8% |

> **In most of the plane the significance bit is worth approximately nothing
> — for every tool.** It does not move a two-point budget decision at all.
> For GeoLift the bit is inert across **83%** of the cells examined.

That reframes the compression-tax result rather than contradicting it. The
retention percentages describe the **minority region where a significance
test changes the decision**, which is the only region where the question is
interesting. Outside it, the tax is not 92% — there is nothing to tax.

It also kills a statistic that looked usable. A median retention taken over
all 35 cells is 0.0% for all four tools, because most cells are zeros, and an
ordering among those ties would be an artefact of floating-point noise. An
earlier version of this sweep printed exactly that ordering. It is not in the
document because it does not mean anything.

### The ordering, tested pairwise where both bits are live

A rank that survives cell by cell is worth more than a rank of aggregates:

| | | holds in |
|---|---|---|
| `geolift` | < `causalpy` | **100%** of 5 cells |
| `geolift` | < `google_mm` | **100%** of 6 |
| `geolift` | < `causalimpact` | **100%** of 6 |
| `causalpy` | < `google_mm` | **100%** of 6 |
| `causalpy` | < `causalimpact` | **100%** of 6 |
| `google_mm` | < `causalimpact` | 80% of 10 |

Five of six pairwise comparisons hold in every shared cell; the sixth in four
of five. So the ordering `geolift < causalpy < google_mm < causalimpact` is
**robust across the examined 7 × 5 decision grid, under this DGP** — not a
coincidence of the single cell it was first measured in.

That is deliberately weaker than "a property of the tools". Still held fixed:
the donor's DGP, its two truths, this prior family, this payoff model, the
$100 threshold defining an active cell, and the business parameters swept.
M7 removes the largest of those; the others remain.

And the headline numbers are representative rather than cherry-picked: at
0.4/1.0 each tool sits near the median of its own active region (GeoLift 7.8%
against a median of 9.9%, CausalImpact 78.5% against 72.3%).

## C. Prior art on the decision layer itself

Decision theory over experiments is emphatically not new, and the landscape
document now says so:

- **"A Decision Theoretic Approach to A/B Testing"**, arXiv
  [1710.03410](https://arxiv.org/pdf/1710.03410) (2017) — loss, actions and
  Bayes risk in place of a universal `p < .05`, demonstrated on eBay data.
- **Imbens & Ng, "Scalable Decisions Using a Bayesian Decision-Theoretic
  Approach"**, arXiv [2601.20031](https://arxiv.org/abs/2601.20031)
  (27 Jan 2026) — experimenter-defined loss functions, hierarchical priors
  from history, applied to Amazon supply-chain experiments.
- **"Profit over Proxies: A Scalable Bayesian Decision Framework for
  Optimizing Multi-Variant Online Experiments"**, arXiv
  [2509.22677](https://arxiv.org/pdf/2509.22677).

So the claim available to us is not "decision theory applied to experiments".
It is narrower and, on this evidence, unoccupied:

> Empirical likelihoods of *real geo-experiment implementations*, combined
> with business utilities and experiment cost, to price what conventional
> reporting throws away and to choose design and method accordingly.

## D. What the bug turned out to be worth

The v1 error did not find bad statistics. It found a bad interface between
statistics and decisions — and the corrected measurement puts a number on it:
for two of four tools, **more than 80% of the decision value of the
experiment is destroyed at the moment the result is converted to a
significance verdict.**
