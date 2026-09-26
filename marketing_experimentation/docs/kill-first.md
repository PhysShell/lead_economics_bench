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

## Template

Copy this into the preregistration before any substantial work.

    HYPOTHESIS
    NECESSARY CONDITION        what must hold for this to be worth pursuing
    CHEAPEST FALSIFIER         smallest test that could show it does not
    KILL CRITERION             the specific result that ends this, written
                               BEFORE looking
    STOP-LOSS                  the spend at which it ends regardless
    COST OF THE FALSIFIER
    COST IF IT SURVIVES

An entry with an empty KILL CRITERION is not a plan and does not get run.
