# Layer 3: the experiment is usually worth running; the significance gate is not

**Reproduce:** `python marketing_experimentation/scripts/voi_v2.py`
**Superseded first attempt:** `scripts/significance_gate_v1.py`
**Invariants:** `tests/test_decision.py` (123 tests)

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

Recast conclude that "point estimates alone would tell you these tools are
interchangeable — the uncertainty story tells you why they aren't." On this
evidence that is precisely backwards *for a decision-maker*: once the estimate
is used to update a belief rather than to pass a threshold, the tools become
close to interchangeable, and the disagreement they document is largely a
disagreement about where to put a threshold nobody is obliged to use.

Their framing is right for their users, because their users live in the gated
world. That is the point.

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
