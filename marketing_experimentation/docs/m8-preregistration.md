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
