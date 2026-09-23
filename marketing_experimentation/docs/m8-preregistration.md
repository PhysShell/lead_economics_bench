# M8 preregistration — a θ grid chosen by the decision, not by round numbers

Written **before** any M8 run, so it cannot be retrofitted. The same
discipline as the G3 tolerances and the §3a headline.

---

## Why the grid changes, and why the old target was wrong

The obvious plan was "densify near the +3% breakeven". That is the wrong
place, and the arithmetic says so.

`budget_problem` pays

    U(d, θ) = S·d·k·(θ − b) − S·c·d²        d = m − 1

The first term changes sign at `θ = b`. But the *action* changes where two
adjacent actions are indifferent:

    d_i·k·(θ−b) − c·d_i²  =  d_j·k·(θ−b) − c·d_j²
    θ*                    =  b + c·(d_i + d_j) / k

With `b = 3%`, `c = 0.35`, `k = 4` and multipliers `(0.5, 0.8, 1.0, 1.25,
1.6)`:

| boundary | θ* |
|---|---|
| `cut hard` ⟷ `cut` | **−3.1250%** |
| `cut` ⟷ `hold` | **+1.2500%** |
| `hold` ⟷ `increase` | **+5.1875%** |
| `increase` ⟷ `increase hard` | **+10.4375%** |

**+3% is not a decision boundary.** It falls between the second and the
third, where nothing happens. A grid densified there is densified where the
answer does not change, and EVSI only ever measures changes in the answer.

This is now `leadbench_mx.decision.action_boundaries()`, cross-checked
against a 500,001-point brute-force sweep of `argmax` — closed form against
an independent oracle, because a derivation verified only against itself is
how a correct proof gets built on a wrong formula.

## The grid

Sixteen truths. Every one has a reason.

| θ | reason |
|---|---|
| −15% | new: extends the negative tail past the current −10% endpoint |
| −10% | existing |
| −5% | existing |
| **−3.125%** | new: `cut hard` ⟷ `cut` boundary |
| −2% | new: prior resolution on the negative shoulder |
| −1% | new: prior resolution, spike edge |
| 0% | existing |
| +1% | new: prior resolution, spike edge |
| **+1.25%** | new: `cut` ⟷ `hold` boundary |
| +2% | existing |
| +5% | existing |
| **+5.1875%** | new: `hold` ⟷ `increase` boundary |
| +7.5% | existing |
| +10% | new: bracket for the fourth boundary |
| **+10.4375%** | new: `increase` ⟷ `increase hard` boundary |
| +15% | existing |

**Nine new truths, not sixteen.** Seven already exist and are not
recomputed — the donor's seeding is deterministic per `(scenario,
iteration)`, so new effect sizes attach to the same clusters without
disturbing what is there.

## Cost

M7 cost **3.48 CPU-hours** for 2,800 rows. CausalPy (9.69 s/run) and GeoLift
(6.65 s/run) are essentially the whole bill; Google MM is 0.02 s/run.

| stage | rows | est. CPU-hours |
|---|---|---|
| pilot: 9 new θ × 4 scenarios × 4 tools × 10 iterations | 1,440 | ~1.8 |
| full: extend the same iteration IDs to 25 | +2,160 | ~2.7 |
| **total new** | **3,600** | **~4.5** |

Against ~8 for a naive 16-point regrid at 25 iterations. The pilot exists to
catch labelling, sign and action-boundary defects before the full spend, not
to produce conclusions — M6a/M6b and D7 are the precedent for what a θ
mutation gets wrong when nobody looks first.

## What changes in the analysis, and what gets frozen

1. **The continuous prior becomes the prior.** Finding A is computed as

       documented continuous prior + estimated q(θ) + utility → EVSI

   not by Voronoi-binning the prior onto simulated truths. The seven-point
   "sensitivity prior matched on negative mass" was a diagnostic; it has done
   its job and is retired as a primary result.

2. **Uncertainty stays clustered.** Bayesian bootstrap over `(scenario,
   iteration)`, carrying the whole θ-vector. Cell-wise Dirichlet remains only
   as a labelled sensitivity. See F16.

3. **Finding B is not scaled yet.** `INTERVAL → VERDICT` needs a 3-d density
   and has been unstable twice. Finding A is where the statistical mechanics
   are clean; B waits until A says whether it is worth buying sample for.

## The gate: interpolation must survive falsification

`q(θ)` is only usable as a function if neighbours can predict a held-out
truth. `scripts/theta_interpolation.py` leaves out each interior truth,
rebuilds `q` from the rest in multinomial-logit space, and compares — against
the right yardstick, the cluster-bootstrap spread of `q` itself.

**Current status on the seven-point grid: 0 of 20 cells above the 95th
percentile on either total-variation distance or |ΔEVSI|.** Worst cell is
`causalpy` at θ = 0, |ΔEVSI| $577, at the 46.6th percentile of sampling
noise. So interpolation costs less than the noise already present.

That is encouraging and it is **not** the test that matters. The seven-point
grid is testing itself across 5%-wide gaps, and it says nothing about
−3.125% or +1.25%, where no truth was ever simulated and where the optimal
action actually changes.

**Preregistered falsification.** After the M8 pilot, rerun the leave-one-out
check with the boundary truths held out. If a boundary truth's |ΔEVSI| lands
above the 95th percentile of cluster-bootstrap noise, then `q` is *not*
interpolable across that boundary, no continuous-prior EVSI is built on it,
and the grid gets denser there instead. Stated now, with the threshold fixed,
so a failure cannot be renegotiated into a success.

## What M8 is actually asking

Not "more θ". This:

> Can the decision-value surface be recovered under the actual continuous
> prior, particularly around the points where the optimal business action
> changes?

---

## Not in scope

- Finding B at scale (see above).
- Any claim about real business data. The DGP is still synthetic; M8 does not
  change that and is not evidence about it.
- A web app (§76), ad spend (§77), or anything that would modify track 1.

---

## Added before GO: the complete-cluster gate (C7)

The pilot runs nine new truths at **10** iterations beside seven existing
truths at **25**. Analysed as-is, `q(θ)` would be estimated from 25 latent
panels on some rows and 10 on others — different Monte Carlo samples per row
of one transition matrix. The boundary falsification would then be measuring
interpolation error *plus* a sample-size difference, which is F16 reopening
under a new name.

`leadbench_mx.clusters.require_complete_clusters` enforces two assertions and
**refuses the analysis** rather than silently dropping:

    for each scenario:
        intersection(iterations over all 16 θ) == {1..10}

    for each tool × scenario × iteration in the analysis:
        exactly one row at every one of the 16 θ

plus a third that follows from the same logic: a cluster complete for one
tool and not another is excluded from both, or a cross-tool comparison is
confounded by which panels each tool happened to see.

Iterations 11–25 of the existing truths are not lost. They are simply not
entitled to participate in the boundary interpolation test until the new
truths reach 25.

Verified no-op on M7: 100/100 clusters complete, 2,800/2,800 rows kept.

## Added before GO: seeds are evidenced by the run, not by the source

F11's lesson — an environment property that matters must be evidenced by the
run itself, not inferred from a file. The pilot output records per row:

    scenario | iteration | theta | panel_seed | estimator_seed

Not because the source is in doubt. Because "nine new truths attach to the
same clusters without disturbing what is there" is only true if the patch
preserved the seed function **and** no effect label leaks into a downstream
estimator RNG. Checked in the source already:

| tool | estimator seed | so θ shares it? |
|---|---|---|
| `causalimpact` | `--seed iteration` (`run_tools.py:173`) | yes — strengthens CRN |
| `causalpy` | `random_seed = iteration` (`run_causalpy.py:100`) | yes — strengthens CRN |
| `geolift` | none | deterministic given the panel |
| `google_mm` | none | deterministic given the panel |

And the question that raises, since the estimator seed is the bare iteration
index and therefore repeats **across scenarios**: is the cluster `(scenario,
iteration)` or `iteration` alone? Measured on M7 — mean cross-scenario
residual correlation +0.012 (causalimpact) and +0.026 (causalpy), against
−0.031 (geolift) and −0.045 (google_mm), which take no estimator seed at all.
The seeded tools look exactly like the unseeded controls. The cluster is the
pair. Recorded as contract C4.

## Execution order

1. ~~complete-cluster pilot gate~~ — done, verified no-op on M7
2. freeze this preregistration as the M8 baseline commit
3. run 9 new θ × 10 iterations × 4 scenarios × 4 tools (1,440 rows, ~1.8 CPU-h)
4. check row identities, seeds, signs, and all four action-boundary truths
5. boundary leave-one-out interpolation test
6. if the 95th-percentile gate PASSES → extend the new θ to 25 iterations
7. if any boundary FAILS → do **not** build continuous EVSI across it;
   densify locally there first

---

# M8 RESULT — the preregistered gate, run at n=25

**Reproduce:**
`python marketing_experimentation/scripts/theta_interpolation.py --results /tmp/results_m8_full_merged.jsonl --expect-iterations 1-25 --boundary-stress`

6,400 rows: 16 truths × 4 scenarios × 4 tools × 25 iterations. 0 duplicated
run identities, 25 iterations in every cell, all 16 recorded θ exact against
canonical (C9), 100 complete CRN clusters, 6,400/6,400 rows surviving the
gate (C7).

## Verdict: PASS

| | |
|---|---|
| plain leave-one-out, interior truths | **0 / 56** above the 95th percentile on TV and on \|ΔEVSI\| |
| boundary stress, spans 3.00–7.50pp | **0 / 16** above the 95th percentile |
| worst boundary cell | `google_mm` +5.1875%, TV at the 36.0th percentile, \|ΔEVSI\| $4 at the 0.3rd |
| largest boundary \|ΔEVSI\| | $26 (`google_mm` +10.4375%), at the 1.8th percentile |

`q(θ)` is reconstructable across every action boundary, spanning gaps
comparable to the original grid, to within cluster-bootstrap noise.

## The caveat that was carried into this run, and what happened to it

The freeze recorded: *the yardstick is sampling noise, which shrinks with
cluster count; the n=10 PASS does not transfer, and the gate may fail at
n=25.* That was the right thing to write down. What actually happened:

* The |ΔEVSI| percentiles did **not** move systematically. Cell by cell,
  **8 of 16 rose and 8 fell** — a wash.
* The maximum fell, 5.1% → 3.0%.
* Nothing came near 95 at either n.

So the bar did rise, and the interpolation error fell at a comparable rate.
That is informative on its own: most of the apparent interpolation error at
n=10 was **estimation noise in `q` itself**, not model misspecification. Had
it been misspecification, the error would have stayed put while the bar
tightened, and the ratio would have climbed.

*(An earlier reading of this comparison, taken off the worst-five list rather
than the full sixteen, reported that the percentiles fell. That was a
selection artefact — the worst-five list re-selects which cells it shows.)*

## What this authorises, and what it does not

Authorised: a continuous-prior Finding A. `q(θ)` may be evaluated on the
documented spike-and-slab's own grid rather than on a seven-point prior
mutilated to fit the simulated truths. The "sensitivity prior matched on
negative mass" can retire.

Not authorised by this: anything about Finding B. `INTERVAL → VERDICT` still
needs a 3-d density and was not scaled. And the DGP is still synthetic —
16 truths at 25 iterations is a better-resolved simulation, not evidence
about a real marketing experiment.
