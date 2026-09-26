# M9 preregistration — the cost of information

Written **before** any M9 run. The question has changed: this is no longer
about whether EVSI is computed correctly, but about

> **Is there an experiment worth running at all, and if so which one?**

    primary     ∃d : ENBS(d) > 0 ?
    secondary   d* = argmax_d ENBS(d)

with `ENBS(d) = EVSI(d) − C(d)` — expected net benefit of sampling, which is
positive exactly when the study pays for itself. `C(d)` must include the
**opportunity cost of the experimental intervention**, not only its invoice.

---

## 0. A claim of mine, withdrawn before it is built on

I said: *"a geo experiment costing more than roughly $2.6k does not pay for
itself."* That is too strong on three counts, each of which becomes a design
requirement below.

1. **It assumes a one-decision horizon.** The $2,130–$2,579 is the value of
   the signed verdict for **one** allocation decision. An experiment whose
   result informs twelve monthly budgets is worth more — though not 12×, if
   θ drifts.
2. **It compares EVSI against the wrong cost.** The relevant quantity is the
   *net economic* cost of running the experiment, not the ad spend it
   perturbs. Those differ in sign as well as magnitude.
3. **EVSI is a property of a design, not of "geo testing".** It is defined
   for a specific proposed study. One number cannot price a family.

**The defensible version, at this moment:**

> For the decision horizon represented by the current utility model, the
> modelled value of this specific sample information is on the order of a few
> thousand dollars per decision at $1M of spend under management. Any
> experiment whose *net economic cost* exceeds that value has negative ENBS
> **under this model**.

## 0a. And the dollar figure is the wrong unit

`budget_problem`'s utility is linear in `spend`, so EVPI and EVSI are
**exactly** proportional to it — verified at $0.1M through $100M, `EVPI/spend`
constant to 1e-12. The transportable quantity is therefore a **rate**:

| tool | EVSI(VERDICT) at $1M | as a share of spend |
|---|---|---|
| `causalimpact` | $2,579 | **0.258%** |
| `causalpy[y_hat]` | $2,130 | **0.213%** |
| `google_mm` | $1,504 | **0.150%** |
| `geolift` | $214 | 0.021% |
| *EVPI ceiling* | $22,120 | *2.21%* |

So "$2.6k" was never the number. **A signed verdict is worth roughly 0.15–0.26%
of the spend it governs, per decision.** A $20k experiment breaks even at
~$8–13M of governed spend for a single decision — which is a claim about
scale, and testable, in a way that "$2.6k" was not.

This supersedes the dollar framing everywhere it appears.

---

## 1. The scoping problem, found before writing the design

**The simulation contains no experiment.** `generate_panels.R:287` is the
entire treatment model:

```r
Y[post_days_idx, idx] <- Y_cf[post_days_idx, idx] * (1 + effect_pct)
```

θ is the lift that *appears*. Nothing in the DGP generates it. There is no
spend variable, no budget, no intervention and no cost. Consequences:

| design dimension | available? |
|---|---|
| **T** — duration (`pre_days`, `total_days`) | **yes**, generator parameters; changes precision, hence `q(θ)`, hence EVSI |
| **G** — number/composition of geos (`n_geos`, `n_treated`) | **yes**, same |
| **Δspend** — magnitude of the perturbation | **no** — requires a spend→lift response model the DGP does not contain |
| **direction** — increase / decrease / holdout | **no** — same, plus a revenue model for the counterfactual |

So the proposed frontier `d = (Δspend, T, G, direction)` is **half
unreachable** in this world, and the unreachable half is the half that
determines `C_intervention`. An M9-A that "uses existing designs" would be
sweeping A1–A4, which are **data regimes** (noise, outliers, autocorrelation),
not experiment designs. Sweeping them and labelling the axis "design" would be
the same category error this project has now made three times.

**This is the largest external-validity commitment in the whole track**, and
it should be made deliberately rather than discovered halfway through a run.

## 2. The reframing that makes M9-A well posed

If `C_intervention` cannot be measured from the simulation, do not assume it.
**Invert the question.** The largest net economic cost at which an experiment
still pays *is* its EVSI — no cost model required:

> **M9-A computes the break-even cost surface**, as a fraction of governed
> spend, over the parameters this world does control: decision horizon,
> prior, utility parameters, and the estimator. It outputs a threshold, not a
> verdict.

The verdict — do real geo experiments cost more or less than that? — then
becomes an **external-data question**, answerable against vendor
documentation and practitioner reports rather than against this DGP. That is
the honest division of labour: the simulation prices the information, the
world prices the experiment.

## 3. Cost accounting, frozen now

Four components, because collapsing them is how "$18,000" becomes
unreconstructable three milestones later:

    C(d) = C_execution + E[C_intervention] + C_delay + C_operations

| | |
|---|---|
| `C_execution` | costs existing *only because* measurement happens: analyst, engineering, platform, extra creative/config |
| `E[C_intervention]` | the economic price of the forced experimental policy — **the dominant term, and the one this DGP cannot supply** |
| `C_delay` | value of decisions deferred while the test runs |
| `C_operations` | implementation overheads the utility model does not represent |

`C_intervention` is defined against the policy the business would otherwise
have run:

    C_intervention(d, θ) = U(a_current, θ) − U(a_experiment(d), θ)
    E[C_intervention(d)] = E_θ[ C_intervention(d, θ) ]

computed **through the same utility model as EVSI**. Two dollar figures from
different utility models are two different quantities wearing one currency
symbol — which is F17–F19 with a `$` in front, and it is the single most
likely way this milestone fails.

### The accounting schema, fixed in advance

Never one field called `cost`:

    gross_spend_perturbation          ad spend moved, signed
    gross_revenue_impact              revenue consequence of moving it
    net_experimental_opportunity_cost the economic sacrifice: the two above,
                                      through the utility model
    direct_measurement_cost           C_execution + C_operations
    total_research_cost               the sum that enters ENBS

A spend-increase design has positive `gross_spend_perturbation` and may have
*negative* net cost if the added spend clears breakeven. A holdout has
negative perturbation and can be very expensive. The sign of the first field
tells you nothing about the sign of the third, which is exactly why they are
separate fields.

## 4. Decision horizon — to be fixed before any number is quoted

    L        number of future decisions the result informs
    rho_t    relevance of today's result at period t (drift)
    r        discount rate

    EVSI_lifetime = sum_t  rho_t · EVSI_t / (1+r)^t

Not necessarily that functional form. The binding rule is: **the horizon is
declared before the break-even figure is named**, and `L = 1` is a choice to
be stated, not a default to be inherited silently. Recast's own MMM
calibration assumes an experiment's constraint weakens with distance from the
test window, so `rho_t < 1` is the expected case rather than a conservatism.

## 5. Staging

**M9-A — break-even feasibility.** No new simulation campaign. Existing
n=25 data, the conditioned prior, the validated `q(θ)`. Produces the
break-even net cost as a share of governed spend, across `L` and the utility
parameters. Sets `C_execution = C_delay = 0` — maximally favourable to the
experiment — so that a negative result is decisive: if the information does
not pay even when the measurement is free, no realistic overhead rescues it.

**M9-B — the reachable frontier.** Only if M9-A leaves room. New simulation
campaigns varying **T and G only**, which the generator supports. Yields
`EVSI(T, G)` and, with the cost model, `ENBS(T, G)`.

**M9-C — the response model.** Δspend and direction. Requires committing to a
spend→lift→revenue model that this project has never had. **Not scheduled**,
and should not be slipped into M9-B as a parameter.

## 6. What counts as a result

* **Negative.** No design has `ENBS > 0` even with free measurement. Strong,
  publishable, and a genuine answer to the track's original question.
* **Conditional.** Positive only in a narrow band — then the output is
  quantitative: *how much* uncertainty is worth buying and at what price.
  More interesting than either binary.
* **Positive everywhere.** Then the interesting question moves to `d*`.

The shape worth anticipating: EVSI has diminishing returns in experiment
intensity while cost grows at least linearly, so `ENBS` is single-peaked and
the optimum is interior. "A full $20k geo test is irrational but a $1.5k test
buying 60% of the available information is optimal" is a possible outcome,
and a far better one than "geo tests are too expensive".

## 7. Out of scope

* Finding B. Still unscaled, still needs a 3-d density.
* New estimator benchmarks.
* Any claim of real-world external validity. The DGP is synthetic and — as §1
  establishes — does not even contain the economic object being priced.

---

# M9-A RESULT — the price of information, as a rate

**Reproduce:** `python marketing_experimentation/scripts/m9a_break_even.py`

Horizon declared, not inherited: **L = 1 decision, ρ = 1, no discounting.**

## Linearity, verified rather than assumed

`EVPI/spend` over six decades (1e4 → 1e9): constant to **6.9e−18**. A dollar
figure is a statement about the budget it was computed at; the transportable
quantity is a rate.

## The price

Share of the spend the decision governs, per decision. 2,000 cluster-bootstrap
draws, conditioned prior, validated `q(θ)`.

| tool | VERDICT | BIT | **V − B** | V−B 95% credible |
|---|---|---|---|---|
| `causalimpact` | **0.2579%** | 0.1472% | 0.1088% | [0.0639%, 0.1657%] |
| `causalpy[y_hat]` | **0.2130%** | 0.0000% | 0.2129% | [0.1546%, 0.3459%] |
| `google_mm` | **0.1504%** | 0.0315% | 0.1064% | [0.0666%, 0.1991%] |
| `geolift` | 0.0214% | 0.0000% | 0.0214% | [0.0000%, 0.0749%] |
| *EVPI ceiling* | *2.2120%* | | | |

## Break-even, which is EVSI restated

The largest **net economic cost** at which the signed-verdict experiment
still pays. No cost model is required to state a threshold — that is the
point of the inversion.

| governed spend | `causalimpact` | `causalpy` | `google_mm` | `geolift` |
|---|---|---|---|---|
| $250,000 | $645 | $533 | $376 | $53 |
| $1,000,000 | $2,579 | $2,130 | $1,504 | $214 |
| $5,000,000 | $12,893 | $10,651 | $7,522 | $1,068 |
| $20,000,000 | $51,574 | $42,605 | $30,088 | $4,272 |
| $100,000,000 | $257,868 | $213,023 | $150,442 | $21,359 |

Read the other way, which is the form the outside world can answer:

    a $5,000 net-cost experiment breaks even at  $1.9M – $23.4M governed spend
    a $20,000 net-cost experiment breaks even at $7.8M – $93.6M
    a $50,000 net-cost experiment breaks even at $19.4M – $234M

(one decision; the range spans the four estimators, `geolift` at the far end)

## What M9-A hands over, and to whom

The simulation prices the information. **Whether real geo experiments cost
more than these thresholds is an external-data question** — and the figure to
compare against is the *net economic* cost, not the ad spend perturbed, which
differs in sign as well as magnitude.

Not an ENBS (no cost model, deliberately). Not a design frontier. Not a
lifetime value. Not external validity.

---

# M9-B — axes frozen, not yet run

## Three corrections to the proposed axes, from reading the generator

**1. The G knob is the donor pool — confirmed, and the guardrail was needed.**
`generate_panels.R:35-36`:

```r
n_treated <- 1   # Number of treated geos (always 1 in this study)
n_control <- 20  # Number of control/donor geos
```

`n_treated` is hardcoded to 1. The axis is therefore **`G_c` = control/donor
pool size**, and scenario A3 is `n_control = 9`. `{5, 9, 20, 40}` maps to
scarce / A3 anchor / A1 default / saturation probe. Varying *treated* geos
would be a different intervention-design question and is not available.

**2. The T anchor is 15, not 14.** Defaults are `total_days = 105,
pre_days = 90`, so post-days = **15**. Using 15 makes the anchor exact and
free rather than approximately free. **Frozen: T ∈ {15, 21, 28, 42}
post-days**, with `pre_days = 90` held fixed — which satisfies the 2× rule at
every point (2 × 42 = 84 ≤ 90), so the pre-period never becomes a stealth
second axis. 56 and 70 are excluded for exactly that reason.

**3. Scenario A4 is not a duration variant.** It is `total_days = 45,
pre_days = 30` — post-days **15**, the same test length as A1, with a
*shorter calibration window*. Treating it as the short-duration arm would
have swept pre-period under a duration label. It is excluded from M9-B.

## Frozen design

    T (post-days)      15, 21, 28, 42      pre_days = 90 throughout
    G_c (donor pool)    5,  9, 20, 40      n_treated = 1 throughout
    theta               the 16 M8 truths
    scenario            S1/A1 regime ONLY -- not crossed with A2-A4,
                        which answer robustness rather than marginal-
                        information questions
    iterations          25, clusters (scenario, iteration) as before

**Estimand:** `r_EVSI(T, G_c) = EVSI(T, G_c) / S_governed`, and hence the
break-even surface `C*(T, G_c, S) = r_EVSI(T, G_c) · S`. Not ENBS — there is
still no cost model, and M9-B does not invent one.

**Monotonicity is descriptive, not an acceptance criterion.** More data can
improve the experiment while an estimator's own calibration moves
differently; the donor study already shows tool-specific rather than uniform
behaviour. No threshold is attached to it, and none will be invented after
seeing the surface.

## Cost, and the two cells already paid for

16 cells × 16 truths × 4 tools × 25 iterations = **25,600 rows**. But
`(T=15, G_c=20)` is A1 and `(T=15, G_c=9)` is A3, both already at 25
iterations over all 16 truths in the merged M8 file. So **14 new cells,
22,400 rows**.

M8 ran 3,600 rows in 6,911s. Mean panel size across the grid is close to the
M8 baseline (mean `n_geos` 19.5 against 21; mean `total_days` 116.5 against
105), so the central estimate is **~12 CPU-hours**, with real uncertainty
upward since CausalPy dominates and scales with panel size.

That is ~6× the largest run in this project so far. **Not launched.**

---

# M9-B Addendum 1 — the axes are slices of one world, and that cost the two free cells

*Written before any M9-B cell was generated for analysis. The investigation
below was run first; the decision follows from it.*

## The question that had to be asked before launching

The frozen design varies `T` and `G_c` and reads the difference in `r_EVSI`
as the marginal value of a longer test or a bigger donor pool. That reading
has a precondition nobody had checked: **the world must be the same on both
sides of the comparison.** The preregistration's "two cells already paid for"
line assumed something stronger still — that `(T=15, G_c=20)` *is* A1 and
`(T=15, G_c=9)` *is* A3, so their rows could be reused.

Both assumptions were tested against the generator. Both are false.

## What the generator actually does when you move an axis

Running the donor's own `draw_baselines()` and `select_treated()` at a fixed
seed (52001), varying only the geo count:

    n_geos= 6   first3: 1700.7, 2459.6, 2650.4   treated: City 3  (2650.4)
    n_geos=10   first3: 1038.2, 1700.7, 2459.6   treated: City 5  (2760.0)
    n_geos=21   first3:  854.7,  989.3, 1038.2   treated: City 11 (3305.1)
    n_geos=41   first3:  854.7,  989.3, 1038.2   treated: City 21 (3305.1)

    baselines nested?              NO
    treated geo stable across G_c? NO

Three independent mechanisms, none of them a bug — nothing in the donor's
design ever asked for nesting:

1. `draw_baselines` calls `rlnorm(n_geos, ...)` and then `sort()`s. The RNG
   *stream* is nested; the sorted vector is not, so a 6-geo draw is not a
   prefix of a 10-geo draw.
2. `select_treated` picks the geo nearest the **median** baseline, and the
   median moves with pool size. A different city is treated in every cell.
3. The noise loop is `for (geo) { for (day) }`, so raising `total_days`
   shifts the stream for every geo after the first. `T=15` is not a prefix
   of `T=42` either.

So a 16-cell sweep on the donor's knobs compares **16 different worlds**.
Every number in it would be correctly computed, and the axis would mean
something false — the F13–F19 class exactly: *a computation that is
internally correct under a structural assumption that was never checked.*
Nothing downstream would have noticed. An EVSI difference between `G_c=5` and
`G_c=40` would have been reported as the value of a larger donor pool when
part of it is the value of a different treated city.

## The decision

The two readings were mutually exclusive — keep the donor's sampling and
accept confounded axes, or nest the worlds and pay to regenerate the two
"free" cells. **Nested, all 16 cells regenerated.** Reusing A1 and A3 saves
about 1.7 CPU-hours and buys an axis whose meaning is false.

## The world contract, as implemented

`repro/recast/m9b-axes.patch` adds `--post_days` and `--n_control` (both or
neither; a partial invocation refuses). Every replication generates one
**maximal latent world** —

    90 pre days + MAX_POST_DAYS (42) post days,  1 treated + MAX_CONTROLS (40) geos

— and every cell is a slice of it:

| | |
|---|---|
| treated geo | chosen **once**, from the 41-geo world, by the unchanged median rule. The same city in every cell. |
| donor pools | the other 40 geos in a fixed random order; each cell takes a prefix, so `D5 ⊂ D9 ⊂ D20 ⊂ D40`. |
| durations | prefixes of the maximal post-period: `Y15 ⊂ Y21 ⊂ Y28 ⊂ Y42`. |

The donor order comes from a **dedicated RNG substream** (`panel_seed +
900000`), not from the DGP's noise stream and not from the sorted baselines.
The sorted-baseline prefix was the cheap option and is wrong twice: "fewer
donors" would silently also mean "donors closer to the treated geo in size",
collapsing two axes into one, and the pool would stop being independent of
the treated selection.

`MAX_*` and `requested_*` are named apart deliberately. Sizing the world to
the request looks like pure savings and destroys every property above
without a single downstream test failing. A `stopifnot()` in the loop is the
tripwire; W6 below is the proof.

## Evidence, before the freeze

`repro/recast/m9b_world_check.py`, 11/11 at generator sha256 `fac70c97`:

| | check | result |
|---|---|---|
| L1 | no flags → byte-identical to the pre-M9B generator, A1–A4 | PASS, 20 files |
| W1 | treated geo identical across every cell | PASS, `City 21` |
| W2 | treated `Y`/`Y_cf` invariant in `G_c` | PASS, exact |
| W3 | `D5 ⊂ D9 ⊂ D20 ⊂ D40`, per replication | PASS, sizes 6/10/21/41 |
| W3b | each pool is the prefix of one recorded permutation, **and equals the geo set on disk** | PASS |
| W3c | `[desc]` D5 City indices = 1, 13, 18, 22, 38 (a size-sorted prefix would read 1–5) | descriptive |
| W3d | donor order **re-derived from `perm_seed` alone**, outside the generator, matches exactly | PASS |
| W4 | `Y15 == prefix(Y21) == prefix(Y28) == prefix(Y42)` | PASS, exact |
| W5 | `Y_counterfactual` invariant in θ; `Y` invariant outside the treated post-period | PASS |
| W6 | **negative test** — strip `M9B_T42_G40` to the smaller cell's geos and days → equals `M9B_T15_G05` | PASS, exact |
| W7 | one world per replication: `panel_seed`, `donor_order`, `treated_geo`, world size constant across cells | PASS |
| W8 | `[structural]` `run_panel` reads the panel once; all four tool inputs derive from it | PASS |

L1 recovers the pre-M9B file by **reverse-applying the patch**, not from a
copy taken by hand — a hand copy only proves that a copy matches itself.

### The suite was then attacked

A passing suite that has never failed on a real defect is an assertion. Five
mutations were introduced into the generator; the harness must refuse each:

| mutation | outcome |
|---|---|
| M-a world sized to the request, tripwire left in | generator **exits 1** — nothing is written |
| M-b same, tripwire deleted | REFUSED, 6/11 fail (W1, W2, W3b, W4, W6, W7) |
| M-c donors are the sorted-baseline prefix | REFUSED — **by W3d alone** |
| M-d permutation drawn from the DGP noise seed | REFUSED — **by W3d alone** |
| M-e treated geo chosen from the slice, not the world | REFUSED, 6/11 fail |
| — restored | 11/11 PASS |

M-c and M-d are the finding. See `docs/failures.md` F20.

## What is no longer claimed

**A1/A3 reproduction is not an M9-B acceptance condition.** `M9B_T15_G20`
has 21 geos drawn as 41 and sliced; A1 has 21 geos drawn as 21. Their
numbers differ, and must — that difference *is* the confound being removed.
Only the legacy invocation must reproduce A1–A4, and it does, byte-for-byte
(L1). Anyone comparing an M9-B cell against a published A-scenario figure is
comparing two different worlds.

## Revised cost

16 cells × 16 truths × 4 tools × 25 iterations = **25,600 rows**, none
reused. At M8's measured 1.92 s/row and the same mean slice size (`n_geos`
19.5, `total_days` 116.5), the central estimate is **~13.7 CPU-hours**,
against ~12 for the 14-cell reuse plan. Generation is now always 41×132 per
panel, which is cheap; estimation still runs on the slice.

Uncertainty remains upward: CausalPy dominates and scales with panel size,
and `G_c=40` is larger than anything M8 ran.

## The estimand, stated narrowly

From the decision that authorised M9-B — recorded here verbatim because it
**predates the freeze** and is therefore what the freeze was taken *of*, not
a reading applied to results afterwards:

> M9-B defines a fixed treated unit within each maximal simulated world and
> varies only the amount of donor and temporal information exposed to the
> estimators.

The question is

    holding the treated world fixed, what is the marginal value of
    additional observations?

and it is **not** the question A1/A3 answer, which is closer to

    what happens under a different simulated market universe whose treated
    median is reselected?

Both are legitimate. Only the first is M9-B, and that is the whole reason
A1/A3 cannot be reused — not compute hygiene, and not a preference for
common random numbers as a technique. CRN earns its place here specifically
because the comparison is between simulated *alternatives*: sharing the
world makes a paired difference reflect the changed factor rather than two
independent Monte Carlo draws.

**A1 becomes prior evidence; M9-B is a new controlled experiment.** The
surface no longer has to pretend that `(T=15, G_c=20)` is A1. It is not.

This also matches what the methods themselves do: GeoLift-style estimators
distinguish the treated/test market set from the remaining donor pool, so
holding the treated object fixed while varying donor availability is a
closer analogue of the real methodological question than re-electing a new
treated geography every time `G_c` moves.

### Two properties of the donor permutation, both deliberate

| | |
|---|---|
| **within** a replication | `D5 ⊂ D9 ⊂ D20 ⊂ D40`. The permutation is drawn once per replication and every pool is its prefix. |
| **across** replications | the permutation changes. Small donor sets are therefore not systematically the smallest, largest or closest-baseline geos — the design integrates over *which donor subset happened to be available*. |

The second is a feature, not drift: `perm_seed = panel_seed + 900000` and
`panel_seed` carries the iteration index, so the order moves with the
replication and with nothing else. It is invariant in θ, T, `G_c` and tool,
which is what W3b, W3d and W7 check.

A note on "stable latent IDs before sorting": the concern that motivated it
— that `sort()` makes geo identity depend on pool size — cannot arise here,
because the world is *always* drawn at 41 geos. The sort is over a fixed
set, so the post-sort names `City 1 … City 41` are themselves the stable
latent IDs, and the slices carry them through unchanged (a `G_c=5` cell
holds, for replication 1, `City 21` treated and donors `City 1, 38, 22, 18,
13` — non-contiguous, and visibly not a size prefix).

### Nothing computational changed with this section

It clarifies what the frozen design means. The five things
`m9b-freeze.json` forbids changing — `generate_panels.R`, `run_tools.py`,
the patch stack, the grid and the seeds — are untouched, and the run was
already in flight when it was written.

---

# M9-B — CLOSED

`docs/m9b-closure.json` is the closure record: hashes of the eight code files
and eight documents, the private artifact's hash, the verification results
and the compute accounting. Reopening M9-B means a **new freeze**, not an
edit to this one.

Corrections that change no data, claim or artifact are recorded in the
record's own `amendments` array, carrying the superseded hashes — never
applied silently. There is one, and it includes a defect in the record
itself: its first generation hashed this very file *before* the section you
are reading was appended, so it shipped certifying a state that had already
moved. Hashes must be taken as the last act, or the generator must refuse on
a dirty tree.

## The result, at the width the evidence supports

> In the investigated grid, increasing test duration systematically raised
> `r_EVSI` for the tools that had an informative VERDICT at all, while
> increasing the donor pool from 5 to 40 showed no comparable stable gain.

Duration (T=15 → T=42, `G_c` fixed): 8 of 12 spans established positive
among tools with signal, none negative. Donor pool (5 → 40, T fixed): 1 of
16 spans excludes zero — **no convincing evidence of appreciable benefit
over this range, not a demonstrated null.** Full tables in
`docs/layer3-first-result.md` Addendum 5.

## Verification at closure

| | |
|---|---|
| world contract on the executed run | 7/7 PASS |
| complete-cluster gate | 16/16 PASS, 100% retention |
| generator mutations refused | 5/5 |
| adversarial gate witnesses rejected | 3/3 |

## What M9-B narrows for the next experiment

Not a proof that donors are irrelevant. A reallocation of priority: 5 → 40
donors consumed a large share of this milestone's compute and produced no
gradient comparable to 15 → 42 days. So **duration, the decision interface,
and the sign-information loss are better candidates for the next experiment
than a wider donor pool** — on observed yield per unit of compute, not on a
demonstrated null.

**M9-C (the spend → lift → revenue response model) remains explicitly NOT
scheduled.** It requires an economic object this DGP does not contain.
