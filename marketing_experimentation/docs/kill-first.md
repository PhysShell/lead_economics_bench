# Kill-first: look for the cheapest falsifier before building the experiment

## The rule

> **Before substantial work, first find the path to KILL.**

When a question appears, the first reaction is not *what experiment would
answer this?* but:

    hypothesis
      -> necessary condition        what must be true for this to be worth pursuing
      -> cheapest falsifier         the smallest thing that could show it is not
      -> kill criterion             the result that ends the direction, written first
      -> stop-loss                  the spend at which it ends anyway

Only if the cheap test fails to kill it does the direction earn:

    tiny test  ->  bounded experiment  ->  expensive run

## The prohibition

> **If, before launching expensive work, we cannot write down the specific
> result that would cancel that work, it must not be launched.**

Not "we expect X". The concrete observation that would make us stop. If no
such observation can be named, the question is not yet sharp enough to spend
on, and sharpening it is the work.

## Why this rule exists here rather than in general

M9-B cost 64.8 aggregate process-hours and 43.8 hours of clock. It produced
a real result and it was worth running. But two of its three narrowed
follow-on questions turned out to be answerable — or at least
*premise-testable* — against **data already on disk**, in seconds. Nobody
checked, because the next move after a grid is reflexively another grid.

The lesson of the M9 sequence is not that we got better at surviving long
runs. It is that we should try not to reach them.

## Worked example: the GeoLift direction, killed or kept in 40 seconds

**Question.** GeoLift's `r_EVSI(VERDICT)` barely moves across the whole
design surface — 0.0000%–0.0571%, exactly zero in five of sixteen cells.
Three candidate explanations: an estimator limitation, a
verdict-representation artefact, or a property of this DGP.

**Hypothesis under test.** The *interface* is the bottleneck: GeoLift's raw
output does discriminate truths, and the `output -> VERDICT` transform is
what destroys it.

**Necessary condition.** GeoLift's raw `att_pct` must track true theta. If
the point estimate is itself noise, no interface change can help and the
direction dies.

**Cheapest falsifier.** Spearman rank correlation of `att_pct` against
`true_att_pct`, on the 25,600 rows already cached. No new simulation.

**Kill criterion, written before looking.** If GeoLift's
`rho(att_pct, theta)` is not materially above its `rho(verdict, theta)`, and
not comparable to the other tools', the interface hypothesis is dead.

**Result.**

| tool | `rho(att_pct, theta)` | `rho(verdict, theta)` |
|---|---|---|
| `causalimpact` | 0.7404 | 0.6432 |
| `causalpy[y_hat]` | 0.6985 | 0.6301 |
| `google_mm` | 0.7194 | 0.6202 |
| **`geolift`** | **0.6910** | **0.1561** |

GeoLift's raw output carries rank information about theta comparable to every
other tool. Its verdict carries almost none. **The premise survives.**

**Mechanism, from the same cached rows:**

| tool | median CI width | width / sd(att_pct) | P(verdict ≠ inconclusive) |
|---|---|---|---|
| `causalimpact` | 0.1615 | 1.67 | 0.474 |
| `causalpy[y_hat]` | 0.1552 | 1.54 | 0.428 |
| `google_mm` | 0.1853 | 1.85 | 0.387 |
| **`geolift`** | **0.6160** | **5.96** | **0.082** |

GeoLift's interval is ~3.8× CausalImpact's and ~6× its own estimate
dispersion, so the CI-to-verdict transform collapses 92% of its outputs to
`inconclusive` whatever the truth. The point estimate knows; the verdict
cannot say.

**Cost of this test:** two queries against existing files, under a minute.
**Cost of the milestone it replaced:** unbounded, and it would have measured
the wrong thing — more simulations of a tool whose problem is not sample size.

**What it does and does not establish.** Rank correlation is a *necessary
condition* test, not a decision-value measurement. It establishes that the
direction is not dead. It does **not** establish that a rich-output channel
would have high EVSI, and it is not a finding about GeoLift's calibration.
The next step is bounded, not expensive.

## Gate 2: does the richer channel carry more DECISION value?

`rho` is not decision value, and a wide interval may be an honest report of
uncertainty rather than a lossy interface. So the same downstream framework
was given progressively richer channels — `scripts/channel_ladder.py`, zero
new simulation.

**Kill criterion, written before looking:** if the rich channels give only a
small increment over BIT/VERDICT, `rho = 0.69` was a correlation carrying no
decision-relevant information and the GeoLift direction dies.

### The result that needs no discretisation at all

VERDICT and SIGN are both natural discrete channels — **neither is binned**,
so the comparison between them is free of every binning concern. Across all
nine configurations (K ∈ {4, 8, 16} × α ∈ {0.1, 0.5, 1.0}):

| tool | VERDICT | SIGN of the point estimate | spread over 9 configs |
|---|---|---|---|
| `causalimpact` | 0.4224–0.4414% | 0.4118–0.4157% | ≤0.019pp |
| `causalpy` | 0.4042–0.4168% | 0.4620–0.4659% | ≤0.013pp |
| **`geolift`** | **0.0066–0.0135%** | **0.4252–0.4286%** | **≤0.007pp** |
| `google_mm` | 0.2710–0.2818% | 0.4558–0.4602% | ≤0.011pp |

**GeoLift's `B → C` gap is 0.412–0.422 percentage points across every
configuration.** The sign of its point estimate is worth roughly **35×** its
verdict, and — the sharper comparison — GeoLift's SIGN channel
(0.4252–0.4286%) is **indistinguishable from CausalImpact's**
(0.4118–0.4157%).

**The gate is passed.** On the sign channel GeoLift is an ordinary tool, and
`P(verdict ≠ inconclusive) = 0.082` for GeoLift against 0.39–0.47 for the
others.

**But `B → C` is not a Blackwell step, and an earlier version of this
document said the loss was "localised at `B → C`".** That overstates.
VERDICT and SIGN are two *different coarsenings of the same raw output*,
neither a garbling of the other: `inconclusive` does not reveal the sign,
and `positive` does not reveal whether it was significant. The comparison is
legitimate and informative; calling it a step in a chain asserts an ordering
Blackwell does not supply. Gate 3 repairs it.

### Gate 3: the nested family, where Blackwell actually applies

The common refinement of VERDICT and SIGN has four natural states —
`significant-negative`, `inconclusive-negative`, `inconclusive-positive`,
`significant-positive` — and every other channel is an aggregation of it:

                          VERDICT+SIGN (4)
                           /          \
                  VERDICT (3)          SIGN (2)
                      |
                    BIT (2)

Now Blackwell supplies **required** inequalities rather than empirical hopes.
`scripts/nested_channel_gate.py`, three prior strengths, 16 checks: **all
hold.** Not F24.

**The licensed comparison** — bolting the point estimate's sign onto the
*existing* verdict, a strict refinement:

| tool | VERDICT | VERDICT+SIGN | gain | ratio |
|---|---|---|---|---|
| `causalimpact` | 0.4045–0.4416% | 0.4417–0.4834% | +0.037…+0.042pp | **1.09×** |
| `causalpy` | 0.3905–0.4171% | 0.5285–0.5616% | +0.138…+0.144pp | **1.35×** |
| `google_mm` | 0.2611–0.2822% | 0.4727–0.5033% | +0.212…+0.221pp | **1.78×** |
| **`geolift`** | 0.0766–0.0966% | 0.4605–0.4909% | **+0.384…+0.394pp** | **5.1–6.0×** |

**The result is the absolute gain: +0.384 to +0.394 percentage points of
governed spend for GeoLift, against +0.037 to +0.042 for CausalImpact** —
an order of magnitude apart in what the same refinement recovers.

The ratio column is **descriptive only**. GeoLift's VERDICT denominator is
tiny and prior-sensitive, and dividing by nearly zero is a reliable way to
manufacture an impressive number. The gain is the quantity that survives;
the multiplier is a way of reading it, not a measurement.

For GeoLift, `V+S ≈ SIGN >> VERDICT`: adding significance to SIGN buys
relatively little, while adding SIGN to VERDICT buys a great deal, so the
decision-relevant piece the current representation discards sits in the
distinction between `inconclusive-negative` and `inconclusive-positive`. Significance does add something
of its own beyond sign for every tool (+0.028…+0.094pp), so the flag is not
worthless — it is just far less valuable than the direction it suppresses.

**Caveat on the denominator.** GeoLift's VERDICT *level* is prior-sensitive
(0.0766–0.0966% here; 0.0066–0.0135% under the earlier inconsistent scheme)
because the channel is nearly degenerate at 92% `inconclusive`, so the prior
dominates. The **gain** is stable; the small denominator is not, and the
"5–6×" should be read as "large", not as a measured multiplier.

### What the gate does NOT support

- **`D → E` is not trustworthy here.** The Blackwell self-test failed 7 of
  36 times, always on `POINT+CI ≥ POINT`, never on the other two relations
  — see the note below. No claim is made about whether the CI adds value.
- **`C → D` magnitudes are lower bounds** and grow with K (GeoLift
  0.4988→0.6608 from K=4 to K=16), exactly as a discretised lower bound
  should. That magnitude beyond sign is worth something is stable in
  direction; how much is not quantified here.
- Nothing about GeoLift's calibration, and nothing that transports outside
  this DGP.

### The methodological trap the self-test caught

A fixed Dirichlet α adds `n_state × α` total pseudo-mass, so a 3K-state
channel is smoothed **three times as hard** as a K-state one. That biases
the comparison *against* the richer channel. Failures are monotone in both
knobs, which is the signature:

| | α=0.1 | α=0.5 | α=1.0 |
|---|---|---|---|
| **K=4** | 0 | 0 | 0 |
| **K=8** | 0 | 1 | 2 |
| **K=16** | 0 | 1 | 3 |

At α=0.1 the relation never fails. The fix, for any future channel
comparison, is to hold the **total** pseudo-mass constant (α/n_state) rather
than the per-state α — otherwise richer channels are penalised by
construction. Recorded as F23.

### Cost

Two gates, both on cached rows. No new simulation, and the direction is now
a specific mechanism claim rather than "something is wrong with GeoLift".

## Kill-plans for the two remaining M9-B directions

Written before any work, per the prohibition above. **Neither is scheduled.**

### Duration saturation

| | |
|---|---|
| hypothesis | the duration gradient flattens somewhere beyond T=42 |
| necessary condition | the gradient must not already be flat *inside* the grid — otherwise the question is about a region we have no reason to visit |
| cheapest falsifier | fit the four T points per tool against the cached draws; test whether the T=28→42 increment is smaller than T=15→21 |
| kill criterion | if the increment is not shrinking across the observed range, "saturation beyond 42" is speculation with no support in hand and is not funded |
| stop-loss | one bounded run at a single T beyond 42, at one `G_c`, not a grid |
| cost of the falsifier | zero new compute; the draws are cached |

### VERDICT information loss

| | |
|---|---|
| hypothesis | the `estimator output -> VERDICT` transform destroys decision value beyond what the estimator itself loses |
| necessary condition | rich output must have materially higher decision value than VERDICT **for the tools where VERDICT already works** — GeoLift alone would not generalise |
| cheapest falsifier | the INTERVAL → VERDICT rung on cached rows, for all four tools, with the density caveat this document already records |
| kill criterion | if rich output and VERDICT have near-equal decision value for `causalimpact`, `causalpy` and `google_mm`, the interface is a GeoLift-specific pathology, not a general bottleneck, and the general direction dies |
| stop-loss | if the INTERVAL density estimate is again the binding uncertainty (it has been twice), stop and fix the estimator rather than buying more simulations |
| cost of the falsifier | zero new compute |

## The template

Filled in **before any code**, and validated by
`repro/recast/plan_gate.py`, which refuses a plan whose KILL names no
observation.

| field | question |
|---|---|
| **CLAIM** | what are we trying to establish? |
| **NECESSARY CONDITION** | what must be true for this to be worth pursuing? |
| **CHEAPEST FALSIFIER** | how do we most cheaply refute that? |
| **KILL** | the specific result that closes the direction |
| **SURVIVE** | the minimum permitted next step if it survives |
| **BUDGET** | max time / compute / money before the next decision |
| **INVARIANT** | a mathematical or structural property that MUST hold |
| **CONSTRUCTION** | can the violation be made unrepresentable? (C15) |
| **WITNESS** | if not, which proxy-preserving counterexample is rejected? (C12) |

**KILL is written before the result, and this is the field the gate is
mostly about.** A human can explain, after any outcome whatsoever, why the
thing is actually very interesting and deserves a little more looking. That
is a remarkably reliable way to turn research into a hobby. An entry with no
KILL is not a plan and does not get run.

`--self-test` is C12 applied to the plan gate itself: a plan with all nine
headings present and non-empty, which the gate must still reject because
KILL defers rather than terminates.

### The gate caught its own version of the defect

Its first KILL check matched the substring `investigate`, and promptly
rejected the real GeoLift plan — whose KILL reads *"GeoLift is not
investigated further"*, a perfectly concrete termination. Matching a word
where the property is *does KILL name a result that ends the direction*
is this project's recurring defect in miniature, arriving inside the tool
built to enforce the lesson. Now phrase-based and boundary-anchored, and
the episode is left in the source comment rather than tidied away.

---

# The GeoLift mechanism branch — CLOSED / HOLD

## The claim, at the width the evidence supports

> **For the investigated decision problem and the M9-B surface**, GeoLift's
> thresholded VERDICT discards substantial decision-relevant *directional*
> information. Adding the point-estimate sign while preserving the existing
> verdict — a strict refinement — raises `r_EVSI` by **0.384 to 0.394
> percentage points** of governed spend, and the resulting channel has value
> close to the sign-only channel.

The qualifier is load-bearing and is not throat-clearing. Blackwell's
ordering is universal: a refinement is worth at least as much as its
garbling for *any* prior and *any* loss. The **size** of the gain is not
universal — it is a property of this decision problem, this prior and this
surface. A different loss function would preserve the ordering and could
change the magnitude to anything.

## Why it stops here

Every question that was *necessary for a decision* is answered:

| question | answer |
|---|---|
| does the estimator carry a direction signal? | yes — within-cell ρ 0.71, comparable to peers |
| does the current VERDICT preserve it? | largely no — `P(≠inconclusive)` 0.082 vs 0.39–0.47 |
| can the loss be shown through a *real* refinement? | yes — VERDICT+SIGN, 16/16 Blackwell checks hold |
| is it an artefact of smoothing strength? | no — survives a 16-fold prior sweep |
| does the measurement framework check the required information ordering? | yes — and it caught F23 by failing |
| **is a new expensive experiment needed to locate the bottleneck?** | **no** |

The remaining questions — continuous channels, alternative decision rules,
conditional mutual information, calibration curves — are *interesting*. None
of them changes a decision. That is the difference between a research
programme and a series.

**Further work on this branch requires a new reason, not curiosity.**

## What the protocol actually bought

The default next move after "GeoLift's EVSI is ~0" is more observations,
more donors, more replications. That experiment would have been expensive
and would have produced a worse answer: `T=90` might well have shown GeoLift
still inert, and it would not have said **why**.

Three gates on cached rows located the bottleneck instead, and turned up a
measurement artefact (F23) that would have biased the very comparison being
made — in the direction that makes "the interface loses nothing" look true.

Kill-first did not kill the hypothesis. **It killed the necessity of the
large experiment**, which is the better outcome and the one worth designing
for.
