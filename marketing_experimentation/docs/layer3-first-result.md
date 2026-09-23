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

GeoLift is the clean illustration and not the subject: correctly calibrated
inference → a very wide interval → TPR of 8.7% → a significance channel that
is nearly mute — while its point estimate still carries decision value within
12% of the best of the four.

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

# Addendum: the information ladder, and a claim of mine it refutes

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
> positive rate matches its nominal level, and it achieves that by being
> almost powerless in this DGP.

Meanwhile its *point estimate* is worth $46,445 — within 12% of the best of
the four. **Calibrated, nearly powerless, and as informative as anything else
once you stop thresholding it.** That is a sharper statement than the one it
replaces, and it is now supported from two independent directions.

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
