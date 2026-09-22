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
