# Failure log — research track 2

Per the brief's §75. Every bug or invalid comparison that could have changed a
conclusion stays visible. History is not cleaned into a heroic narrative.

## F1. Reported that a free experiment was not worth running (v1 Layer 3)

**What was wrong.** `business_phase_diagram.py` (now
`significance_gate_v1.py`) modelled the decision as

    significant -> act ;  not significant -> don't act

and compared it against acting on the prior. It reported that even at zero
experiment cost, not experimenting beat experimenting over 70% of the
cost-by-prior plane, and that GeoLift was optimal in 0% of cells.

**Why it was wrong.** Value of information cannot be negative when the
information is free: you can always observe the result and then do what you
would have done anyway, so `EVSI >= 0` whenever `C_experiment = 0`. The model
was forced to obey the gate, so it was measuring the value of `p < .05` as a
binding rule, not the value of an experiment.

**What it would have changed.** Two headline claims, both wrong as stated:
"DO_NOT_RUN beats experimentation on 70% of the plane" and "GeoLift is never
optimal". Under the corrected model GeoLift's value rises **+1,296%** and the
four tools converge from an 11x spread to 17%.

**How it is prevented now.** `tests/test_decision.py` asserts `EVSI >= 0` at
zero cost, `0 <= EVSI <= EVPI`, that a useless signal is worth exactly zero,
and that a perfect signal is worth exactly EVPI. `voi_v2.py` checks all 1,800
cells and refuses to print if any fails.

**What survived.** The gate really is beaten by the prior in 70% of the
plane. That is a true and useful statement about conventional practice — it
was only the label that was wrong.

**Caught by the reader, not by me**, and it is the most consequential of the
four such entries: the whole of Layer 3 followed from having the model
corrected. The reader's argument was one line — if information is free you
can always ignore it, so `EVSI ≥ 0` at zero cost — and it was decisive.

## F2. Two reporting artefacts in the v2 first run

- "cells where best EVSI < 0: 10" was floating-point dust (largest magnitude
  $0.00 against a $0.45 tolerance) being compared against a hard zero. Now
  compared against a tolerance scaled to EVPI.
- "median share of the experiment's value discarded by the gate:
  125,698,162,152,177,744%" was division by a near-zero EVSI. Now computed
  only over cells where the experiment has material value, where the honest
  answer turns out to be 0%.

Neither changed a conclusion, but the second would have been quoted.

## F3. Two overstatements in the first landscape pass

- "Capability I is closed" — too strong. Recast benchmarked methods against
  synthetic regimes; that is not a per-business decision service, and they
  say so themselves.
- "GeoX chooses holdback vs go-dark vs heavy-up" — wrong. The user sets
  `experiment_types` and `methodology` in `DesignConfig`; GeoX optimises
  within that posture and compares configurations.

Both were caught by the reader, not by me.

## F4. Donor harness defects found at the reproducibility gate

Recorded in full in `donor-repro.md`. Five issues in
`getrecast/geolift-simulation-study` @ `5133d37`, all found before running
anything, all of which would have cost compute or confidence later:

- **D1** `.Rprofile` sources `renv/activate.R`, which `.gitignore` excludes
  and a pristine clone does not contain — R can fail on startup before
  `renv::restore()` can create it.
- **D2** README's clone URL (`getrecast/geolift-study.git`) is not the
  repository.
- **D3** `VERSIONS.md` leaves R "captured at install time" while `renv.lock`
  pins 4.5.1.
- **D4** `pyproject.toml` is loose (`pymc>=5.10`) where `requirements.txt` is
  frozen (`pymc==5.28.1`), and `make env` installs both, loose second.
- **D5** no licence of any kind — readable and citable, not forkable.

Two more were found once the donor was actually driven, and are recorded
there as **D6** (`make smoke` begins with `rm -rf results/`, deleting the
32,000-row artefact every golden comparison is measured against) and **D7**
(the figure layer hard-codes the 7.5% truth while the metrics layer derives
it).

## F5. "R 4.5.1 is unobtainable" — declared after checking two places

**What was wrong.** An earlier version of F4 ended: *"R 4.5.1 is
unobtainable from either the distribution (4.3.3) or CRAN apt (4.6.1), so
the replay runs on a different minor series than the donor."* That was then
used to justify accepting R 4.6.1 as the reproduction environment.

**Why it was wrong.** Two *package repositories* were checked and the search
was declared exhausted. R 4.5.1 is available from at least two ordinary
routes: the official source tarball at `cran.r-project.org/src/base/R-4/`,
and `rocker/r-ver:4.5.1`. It has since been built here from the tarball
(sha256 `b42a7921…`) and verified.

**What it would have changed.** The entire reproduction lane. Every
numerical disagreement would have had an untestable excuse attached to it,
and "we could not obtain the pinned runtime" would have been published as a
finding about the field when it was a finding about how hard I looked.

**How it is prevented now.** The two lanes are separate and 4.6.1 is the
robustness lane, not the reproduction lane. More generally: an availability
claim now requires naming the routes checked, and "apt did not have it" is
not a search.

**Caught by the reader, not by me.**

## F6. A bootstrap that carefully stepped around the donor's deadlock and built its own

**What was wrong.** `repro/recast/bootstrap.R` exists because the donor's
`.Rprofile` sources a file a pristine clone does not have (D1). Its first
substantive line read the lockfile with `jsonlite::fromJSON` — before
installing anything.

**Why it was wrong.** On a genuinely clean R, `jsonlite` is not present.
The script would have died at the first line that mattered, for the same
class of reason it was written to avoid.

**What it would have changed.** Nothing published, but it would have failed
exactly when it was needed and nowhere else — on the freshly built 4.5.1,
which is the only interpreter in this project with no packages on it.

**How it is prevented now.** The R version is parsed with base R only, on
the principle that nothing may be required before the thing that installs
requirements. Verified empirically: `requireNamespace("jsonlite")` is
`FALSE` on the target interpreter, and the parser returns `4.5.1` anyway.

**Caught by the reader, not by me.**

## F7. Misreading a rounding floor as a solver tolerance

**What was wrong.** The determinism probe found residuals of ~3e-5 for
GeoLift and CausalImpact, and the first write-up called them *"~1e-7
relative, a solver-convergence floor rather than a stochastic one"*.

**Why it was wrong.** The residual is a constant **absolute** 3e-5 across
two different tools and four scenarios whose magnitudes differ several-fold.
No solver tolerance behaves that way. Both R adapters round every level and
interval to four decimal places on output; a half-ULP is 5e-5, and a
residual combining three such values has exactly the observed median 3e-5
and maximum 9.8e-5.

**What it would have changed.** The G3 tolerance for two of four tools, in
the direction of a tolerance that could never be met. Worse, it would have
published "these tools agree to 1e-7" as a property of the tools when it is
a property of the print statement — and the true statement is stronger:
they are as deterministic as `google_mm`, and the donor did not publish
enough digits to see it.

**How it is prevented now.** Those two tolerances are marked in code and in
the document as **censored** — set by the artefact, not the tool — and
`replay_check.py` says so in its own verdict so a pass cannot be quoted as
more than it is.

**Caught within the hour, by the tell rather than by a reviewer.** The
constant-absolute-value signature is what gave it away.

## F8. Two wrong mechanisms for CausalPy's noise, offered in sequence

**What was wrong.** CausalPy's published point estimate carries ~1.3% Monte
Carlo noise while the other three carry none. Two explanations were reached
for and both were wrong: first that it was unseeded (it is seeded,
`run_causalpy.py:100`, `random_seed = iteration`), then that standardisation
differed between arms (it standardises on the pre-period,
`run_causalpy.py:71–73`, which is identical across arms by the donor's own
seeding design).

**Why this is in the log even though nothing was published.** Because the
pattern is the one the reader has caught twice already — an interpretation
presented with the confidence of a result. The third candidate, that every
published row is `posterior_type = "y_hat"` and the posterior predictive
mean carries simulated observation noise, is **also** unconfirmed, and the
`"mu"` rows the adapter can emit were never published, so it cannot be
confirmed from the donor's artefacts at all.

**How it is handled now.** It is written down as an open question with a
specific test attached — M5b runs both posterior types — rather than as a
mechanism. The A4 result (3.2% on the short panel, 30 pre-period days) is
coherent with the story and is explicitly not counted as evidence for it.

### F8.1 — H3 excluded, by exclusion rather than by a failed null test

The test ran. `config/tools.yaml` lists `posteriors: [y_hat]`; adding `mu`
enables a code path the donor already ships. Both were run on identical
panels, 20 iterations, and the determinism identity applied to each:

| | A1 | A4 |
|---|---|---|
| `causalpy[mu]` — parameter uncertainty only | **1.1372%** | **3.1046%** |
| `causalpy[y_hat]` — posterior predictive | 1.1241% | 3.1384% |

**A first draft of this entry stopped there and called it refuted.** That
would have ended the investigation with `p > .05 → no difference`, which is
the inference this project spent most of its length demonstrating to be poor.
Ending on it would have been comic.

**Reproduce:** `python marketing_experimentation/repro/recast/f8_equivalence.py`

The design supports something better. The same run identities produce both
variants, so the comparison is **paired** and between-run variance cancels.
That allows an exclusion test, and the margin is derived from H3 rather than
chosen for looking round: a mechanism that explains less than **half** of a
phenomenon is not the explanation of it, so H3 predicts
`d ≤ −0.5 × baseline`. Preregistered before looking at the differences.

Over 20 paired run identities on A1:

| | |
|---|---|
| `y_hat` noise, mean | 4.0576 |
| `mu` noise, mean | 4.0516 |
| paired difference `d` | **−0.0060**, 95% bootstrap CI **[−0.1019, +0.0887]** |
| what H3 requires | `d ≤ −2.0288` |

> **H3 is excluded.** The reduction it predicts lies entirely outside the
> interval — in relative terms `mu` changes the noise by **−0.1%
> [−2.5%, +2.2%]** against the **−50%** H3 would need. The interval is about
> twenty times narrower than the effect under test, so n = 20 is ample *for
> this question*.

**What the test does not show**, and the distinction is the point: it does
not show the two variants are identical. A difference smaller than 2.03 —
that is, smaller than half the noise — remains entirely possible and is not
addressed. The claim is bounded to match:

> **The posterior representation is not a material explanation of the
> observed CausalPy point-estimate variability. The residual mechanism
> remains unexplained.**

Not "posterior type does not matter", and not "finally". An earlier version
of this entry also argued the conclusion was independent of sample size,
which is wrong in general: n determines how small a difference can be
excluded. It happens not to bite here only because H3 was a *large* claim.

So after three attempts: **CausalPy's published point estimate carries
~1.1–1.3% noise and we do not know why.** Ruled out: the seed,
standardisation drift, and the posterior representation. What remains is H4
— that NUTS's trajectory depends on the data and not only on the seed — and
it is a hypothesis, labelled as one.

**H4 is not queued for testing merely because it is next.** What it predicts
should be stated first: if data-dependent geometry is the cause, run-level
variability should track diagnostics the harness already records — R-hat,
ESS bulk and tail, divergences, tree depth, step size, BFMI. That would be
an observational probe and hypothesis generation, not proof. The strong test
is different and more expensive: hold the panel, model and target fixed and
raise draws, warmup, `target_accept` and chains. If the variability decays
like Monte Carlo error should, the answer is dull and satisfying — it is
finite-MCMC noise. If it sits near 1% while the effective sample size grows
sharply, there is something worth writing about.

Three refutations in a row is the useful outcome. The temptation each time
was to stop at a plausible story; each story was checkable, and each was
wrong.

## F12. A probe that computed on misaligned rows instead of refusing

**What was wrong.** `determinism_probe.py` joined the two arms on a run
identity without checking that the identity was unique. The F8 run produced
doubled `y_hat` rows, and the probe reported `n=40` where 20 was correct —
silently pairing rows positionally against rows that were not their
counterparts.

**Why the duplicates existed** is a separate finding, **D13**: my F8 script
omitted `make clean`, and the donor's crash recovery (`run_tools.py:232`)
re-runs CausalPy whenever *any* of its posterior keys is missing, appending
**both** types and duplicating the one that was already there.

**What it would have changed.** As it happens, nothing: the clean `mu`
measurement (n=20, no duplicates) gives 1.1372% and agrees with both the
duplicated `y_hat` figure and the published 1.2975%, so the F8.1 conclusion
stands on rows that were never misaligned. But that is luck for the second
time today, and the same luck as F11.

**How it is prevented now.** The probe refuses on a duplicated identity and
names the likely cause. `replay_check.py` already did this — the guard
existed, in the other file, and was not carried across. Verified in both
directions: the published data still produces identical numbers, and an
injected duplicate is rejected.

**The rule, which is F11's rule again:** a property the analysis depends on
is asserted by the analysis, every run. Uniqueness of a join key is such a
property.

## F9. An M5a design that assumed artefacts the donor never shipped

**What was wrong.** The plan for R1 was to hash each regenerated panel and
compare against the donor's published panels.

**Why it was wrong.** The donor ships no panels. `panels/` is in its
`.gitignore` and absent from the repository; only `results/` is published.
There was no upstream hash to compare against, and a panel hash proves only
that this machine is deterministic.

**What it would have changed.** R1 would have been quietly downgraded to a
self-consistency check and could easily have been reported as a donor
comparison.

**How it is fixed.** R1 runs through `true_att_level`, which *is* published
and *is* a function of the generated panel: 4,000 distinct values on the
effect arm, one per (scenario, iteration), agreed by all four tools. The
null arm is excluded in code, because with θ = 0 that quantity is
identically 0.0 and would be sixteen thousand rows of zero equalling zero.

## F10. Two background watchers that could never finish

**What was wrong.** Two long-lived shells from research track 1 waited with
`until ! pgrep -f "run_benchmark.py --suite lead"; do sleep 60; done`. Their
own command lines contain that string, so `pgrep` matched them, and they
would have waited forever for themselves.

**Why it is here.** It cost nothing — the suites they were watching had long
since finished and been reported by other means — but the same pattern was
about to be used again to sequence the smoke run behind the renv restore.
That watcher polls a log file for a completion marker instead.

Not a research failure. Recorded because process failures that nearly
repeat are worth the four lines.

## F11. Two-lane isolation asserted, not verified — and only a broken library exposed it

**What was wrong.** The whole point of the version-matched / robustness split
is that a numerical disagreement is interpretable. I set the lane by passing
`RSCRIPT=/opt/R/4.5.1/bin/Rscript` to the donor's `make`, and wrote in
`donor-repro.md` that the smoke ran in the version-matched lane.

It did not. The Makefile's `RSCRIPT` governs only `make panels`. GeoLift and
CausalImpact run as subprocesses from `run_tools.py`, which hardcodes the
string `"Rscript"` (lines 115 and 162). PATH resolved that to the *other*
R — 4.6.1, the robustness lane. So the run generated data on 4.5.1 and
estimated with two of four tools on 4.6.1: precisely the mixing the two-lane
design exists to prevent.

**What it would have changed.** Everything downstream. A G3 disagreement
would have been attributed to the platform, or to a tool, when the cause was
that half the pipeline was in the wrong lane. And the R1 PASS and the
`google_mm` result — both genuine — would have been published alongside two
numbers from a mixed environment, in one table, indistinguishable.

**Why it was caught, and it was not by me.** The other R's renv library was
empty, because its restore had been rolled back by the same all-or-nothing
mechanism as D8. So both adapters died in zero seconds and wrote 40 nulls
each, and the donor's own `smoke_test.py` failed loudly.

**Had that library been complete, this would have produced plausible numbers
and nothing would have complained.** The detection was luck. The mistake was
asserting an isolation property instead of testing it — the same shape as
F5 (declaring a search exhausted after two places) and F9 (assuming the donor
shipped artefacts it does not).

**How it is prevented now.** `PATH` is set to the lane's R for the whole run,
and the run script prints which `Rscript` it actually resolved before doing
anything. The lane is evidenced on every run instead of assumed once. The
donor-side half is recorded as **D11**.

**The general rule this earns:** an environment property that matters to a
conclusion gets asserted by the run itself, in its own output, every time —
not established once in a setup step and trusted thereafter.

## F13. The information ladder was not a ladder

**What was wrong.** The central apparatus of this track assumed a nesting:

    S0 significance bit  <  S1 point estimate  <  S2 estimate + interval width

and reported `EVSI(S1) − EVSI(S0)` as "the price of binarisation", with the
whole compression tax said to sit at that one rung.

**Why it was wrong.** `significant` is not computed from the point estimate.
In this harness it is exactly "the confidence interval excludes zero" —
now checked rather than assumed, at **100.00% agreement, 0 mismatches in
2,000 rows per tool**. So S0 is a function of the *interval*, not of S1. They
are two different projections of the same result, and the difference between
them was never a compression at all.

A second, compounding error: `S2 = (att, ci_width)`. The intervals are not
symmetric about the estimate — median |att − midpoint| is 1.3–8.3% of the
width — so `(att, width)` recovers significance only 94–97% of the time. Even
the S2→S0 step, the one that *looked* like a genuine nesting, was not one.

**What it changed.** A published headline. "Adding the confidence interval on
top of the point estimate is worth nothing measurable" was measured on the
width. On the full bounds the interval adds a great deal for three of four
tools — held-out AUC rises 0.76 → 0.91 for `google_mm` and 0.77 → 0.92 for
`causalimpact`. The claim survives only for GeoLift, where it holds in two
independent density families.

**How it is prevented now.** The representation graph is a fork, and the
vertical arm is a genuine garbling chain, so **Blackwell's theorem
guarantees** `EVSI(FULL) ≥ EVSI(INTERVAL) ≥ EVSI(BIT)` for any prior and
utility. That is no longer a hypothesis — it is an identity, and a violation
is therefore a **self-test on our own density estimation** rather than a
finding. It fires already: `google_mm` shows FULL < INTERVAL, correctly
identifying that the 4-d density has run out of sample.

`POINT` is reported as a side branch under its own heading, because neither
it nor the bit is a garbling of the other and Blackwell does not order them.

Held-out AUC is now computed alongside every EVSI, because EVSI in different
dimensions is not comparable and a richer signal can score higher purely by
giving the estimator more room.

**Caught by the reader, not by me** — the fifth such entry, and the one with
the largest blast radius: it invalidated the structure the track's main
result was expressed in, while leaving the underlying data untouched.

## F14. A Blackwell self-test that ran at one prior while shares were printed at seven

**What was wrong.** Two errors in the signed-verdict decomposition, in the
same afternoon, both of the same family: a theorem about the truth quietly
applied to an estimate of the truth.

**(a) "Algebraic" was the wrong word.** The module claimed that
`EVSI(VERDICT) ≥ EVSI(BIT)` was an algebraic identity in the held-out column,
on the grounds that `p(bit | θ)` is derived from `p(verdict | θ)` through the
garbling map rather than counted independently. It is not. The held-out
expectation runs over the *empirical frequency of the evaluation rows*, and
the Jensen step needs the *model's* marginals. The inequality is exact only
in the model column — where it now lives, and where it is asserted.

**(b) The self-test ran at the base prior only.** `--neg-sweep` reports the
decomposition at seven different priors. The Blackwell check ran once, at the
base prior, and passed. Six other priors were never checked. Blackwell is a
statement for *every* prior, so checking it at one and printing shares at
seven is not a check at all.

**What it changed.** It printed a sign share of **113.0%** for
`causalpy[y_hat]` at P(θ<0) = 0.50 — the decomposition's two parts were
$−550 and $7,826, a negative "part" of a total. Nothing downstream had been
written yet, so no published number moved. It would have been published.

**How it was caught.** By the percentage exceeding 100. That is luck of a
particular kind — the invariant happened to be violated in a quantity with an
obvious ceiling. Had the violation landed at 85% instead of 113% it would
have read as a finding.

**How it is prevented now.** The check runs inside the sweep loop, at every
prior, and there are three outcomes rather than two: a share, a **lower
bound** when `I − V` is not separable from zero, and `KDE!` when `I − V` is
negative by more than two split SDs. `tests/test_signed_verdict.py` asserts
Blackwell across a parametrised range of negative-mass priors and 25 random
likelihoods, and asserts the null case — that the sign is worth *exactly*
zero when no verdict is ever negative — so the finding cannot be produced by
a metric that is simply always positive.

**Caught by me, not by the reader.** Recorded anyway, because §75 asks for
every invalid comparison that *could* have changed conclusions, and an
invalid comparison caught by a lucky ceiling is not a process that works.

## F15. A lower bound that was not a bound, and a prior that was not the prior

Three defects in the signed-verdict result published as `26d2f6f`, all found
by the reader, all in the same direction: each one made the finding look more
established than it was.

**(a) `63.3%+` was not a lower bound.** The sweep printed the sign share with
a `+` marker wherever `I − V` was indistinguishable from zero, on the reading
"the sign accounts for at least this much". That does not follow. The share
is `(V−B) / ((I−V) + (V−B))`, and uncertainty in the **denominator** moves
the true value in *both* directions. With point estimates `I−V = 100` and
`V−B = 200` the share reads 67%; if `I−V` is really 300 the share is 40%. An
unresolved denominator makes the ratio unresolved, not bounded below.

*What it changed.* The headline figures 63%, 79% and 68.4% — every one of
them a ratio whose denominator had failed to separate from zero. Withdrawn.
The script now prints `unresolved` and both dollar magnitudes instead, and
the share survives in only 9 of 20 cells, running 0.0–24.8%.

**(b) "the prior the project actually documents" was a seven-point prior
matched on one marginal.** `reweight_negative(problem, 0.267)` sets
`P(θ<0) = 0.267` and preserves the relative weights inside each half. The
spike-and-slab has structure near zero that a seven-point grid cannot
represent, and *where* the negative mass sits is decisive for a five-action
decision: mass at −10% and −5% argues for `cut hard`, the same mass at −2%
and −1% argues for `hold`. Matching a marginal is not reconstructing a prior.
Now described as a **seven-point sensitivity prior whose negative mass
matches the documented continuous prior**, and the docstring of
`reweight_negative` says why the stronger phrasing is unavailable until the θ
grid is finer.

**(c) One table mixed a reliable measurement with an unreliable one.**
VERDICT → BIT is a discrete channel measurable from multinomial counts with
no density estimation at all. INTERVAL → VERDICT needs a 3-d KDE, the
estimator this log already records failing twice. Reporting them in one table
let the weaker one contaminate the stronger. They are now Finding A
(discrete, robust) and Finding B (continuous, provisional), and the ratio
between them is printed only where it is resolved.

**A fourth thing, which was my own claim and also wrong.** I reported that α
moves the sign share "by a factor of 2–3" and called that a fundamental
limitation needing more runs. With a `Dirichlet(counts + α)` posterior
propagated through EVSI, the credible intervals at α ∈ {0.05, 0.5, 2.0}
overlap heavily — `causalpy` gives [1,642–4,759], [1,538–4,537],
[1,238–3,962]. The factor of 2–3 was the spread between three plug-in point
estimates, each with an interval far wider than the spread between them. α
was never the binding constraint; reporting a point estimate was.

**Caught by the reader** — the sixth such entry. The pattern across (a), (b)
and (c) is one thing: a quantity was named more strongly than its derivation
supported. F13 was the same error about a garbling chain, F14 about a
Blackwell check. Naming something a bound, a prior, or a measurement is a
claim, and it needs the same evidence as a number does.

## F16. Independence asserted across θ, in a design built on common random numbers

**What was wrong.** `dirichlet_draws()` carried this docstring:

> Independent across truths because each truth's runs are a separate
> multinomial sample — **nothing in the design links them**, and pretending
> otherwise would be a smoothing assumption smuggled in as a prior.

The donor's source says the opposite, in a comment, at
`src/R/generate_panels.R:375`:

```r
panel_seed <- master_seed * 1000 + match(sc_id, names(scenarios)) * 10000 + it
# Step 1: Draw baselines (same seed for null and effect)
```

There is **no effect-size term in that seed.** The loop over effect sizes
sits outside it, so every θ inside one `(scenario, iteration)` reuses the same
baselines, the same noise realisation, the same pre-period and the same
counterfactual skeleton; only the treatment multiplier changes. That is a
common-random-numbers design — a deliberate variance-reduction choice, and a
good one — and I read it as independence.

**How wrong.** Not marginally. The correlation of `att_pct − effect_pct`
across θ *within* a cluster is **+1.000** for all four tools (min +0.999).
The seven "independent multinomial samples" per scenario are seven views of
the same 25 noise realisations. Thresholding to a verdict destroys some of
that dependence — excess agreement between two truths' verdicts over a
shuffled baseline is +0.012 to +0.078 — but the draw underneath is shared.

**What it changed.** The point estimates barely moved, as predicted. The
*intervals* did, and one qualitative claim flipped:

| tool | scenarios excluding zero, cell model | cluster model |
|---|---|---|
| `causalimpact` | 1 of 4 | **3 of 4** |
| `geolift` | 1 of 4 | 2 of 4 |
| `causalpy[y_hat]` | 4 of 4 | 4 of 4 |
| `google_mm` | 3 of 4 | 3 of 4 |

So Addendum 3's sentence "`causalimpact` is weaker than the pooled figure
suggests — only one of four scenarios excludes zero on its own" was itself an
artefact of the wrong uncertainty model. Corrected.

The cluster intervals are **not uniformly narrower**: width ratio median 0.83
over 20 cells, range 0.00–1.12. The direction of the error could not have been
argued from first principles, which is precisely why it had to be measured
rather than reasoned about.

**How it is prevented now.** `verdict_matrix()` builds one row per
`(scenario, iteration)` carrying the whole θ-vector, and
`cluster_bootstrap_draws()` gives each cluster a single Dirichlet(1,…,1)
weight applied across all of its truths at once. The cell-wise model is kept,
labelled as a parametric sensitivity, and printed beside the cluster result so
the cost of the assumption stays visible rather than argued.

A consequence worth stating because it bites elsewhere: **the same clusters
feed all four tools.** The four rows are not four independent tests, so "3 of
4 tools exclude zero" is one correlated observation. The upside is that a
*paired* comparison between tools on shared clusters would be more powerful
than the unpaired one — not yet done.

**Caught by the reader** — the seventh.

### The class these four belong to

F13, F14, F15 and F16 are one failure mode, and it has a name in simulation
science rather than in software testing. The distinction is between
*verification* — does the implementation match the conceptual model — and
*validation* — does the model represent reality for the intended use. The
conceptual model is not only the equations; it includes the assumptions,
abstractions and descriptions around them, which is why a perfectly verified
implementation can still compute something other than what is claimed:

> **Conceptual-model contract failure** — the computation was internally
> correct, but an unverified structural assumption changed what the
> computation was entitled to mean.

| | the false sentence | what it was about |
|---|---|---|
| F13 | "BIT is a coarsening of POINT" | conceptual structure |
| F14 | "the Blackwell self-test applies here" | a theorem aimed at the wrong estimand |
| F15 | "this is a lower bound" / "this is the documented prior" | a name stronger than its construction |
| F16 | "the θ samples are independent" | the experimental design |

The arithmetic was right in all four. A unit test for the arithmetic cannot
catch any of them, because the defect is in the sentence and the sentence is
not in the test. The response is `docs/assumption-contracts.md`: every
load-bearing claim carries a SOURCE (file:line or an evidencing run) and a
CHECK (something that fails when the claim is false), and the check runs
**inside the analysis**, not only in CI — F16's gate refuses the run rather
than passing quietly in a test file.

It will not stop the next error. It narrows the class. F16 had both a comment
in the donor's own source and a correlation of +1.000 sitting in the results
file, and neither was consulted, because nothing required it.
