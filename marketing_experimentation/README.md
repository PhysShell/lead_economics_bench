# marketing_experimentation — research track 2

A separate, falsification-oriented track. It does **not** continue the
lead-economics product hypothesis; it tests a different one.

> Can a vendor-neutral system decide, from a business's own historical data,
> whether a marketing experiment is worth running at all — and if so, which
> design and which estimator?

**Isolation.** Track 1 is frozen at `7ce8c6b`. Nothing here modifies its
manifests, results or report; those stay reproducible byte-for-byte.

---

## Where the question went

It started as "which geo estimator is best". That gap turned out to be
occupied: Recast Research published a head-to-head simulation of four
open-source geo tools in June 2026, with code. So the track moved up a layer,
and then the layer it moved to produced a result that moved it again.

| layer | question | state |
|---|---|---|
| 1. statistical behaviour | which estimator is most accurate? | **occupied** — Recast, Statsig, Microsoft ExP |
| 2. regime selection | which estimator for which data regime? | prize looks smaller than assumed: under optimal use the tools converge to within 12% |
| 3. business decision | is this experiment worth running, and what should the result change? | **the live question** |

The current claim, stated as narrowly as the evidence allows:

> Marketing experimentation platforms compute statistical significance
> competently, and then convert evidence into budget action with a rule that
> is beaten by acting on the prior across most of the business plane. The gap
> between `p < .05` and the posterior-optimal action is the thing worth
> measuring.

---

## What is established

### The decision layer — `docs/layer3-first-result.md`

- **Thresholding an interval into a bit destroys 66–93% of its decision
  value.** Because `significant` is exactly "the interval excludes zero"
  (verified, 0 mismatches in 2,000 rows per tool), the bit is a *deterministic
  garbling* of the interval, so Blackwell's theorem guarantees the ordering
  and a violation would be a bug in our density estimation rather than a
  finding. That makes it a compression measurement rather than a comparison.
- **The point estimate is a side branch, not a rung.** It is not comparable
  to the bit by Blackwell — neither is a garbling of the other — so
  `POINT − BIT` is an empirical property of a decision problem, reported
  separately. An earlier version of this track treated the two as nested and
  was wrong; see `docs/failures.md` F13.
- **Under optimal use the four tools converge** from an 11× spread at the
  significance bit to ~12% at the point estimate. The disagreement the
  vendors document is largely a disagreement about where to put a threshold
  nobody is obliged to use.
- **The bit's value is determined in closed form by its two error rates.**
  For the published two-point experiment, `EVSI(BIT)` is reconstructed to the
  dollar ($0.00 difference, all four tools) from Recast's own FPR and FNR.
  Not a correlation — the 32,000 rows enter that rung through two numbers and
  nothing else. And the tool keeping most value through the gate is the
  worst-calibrated one.
- **In most of the business plane the significance bit is worth ~$0** for
  every tool. For GeoLift it is inert across 83% of cells examined.
- **Part of that loss is not thresholding at all — it is the missing sign.**
  `significant` is unsigned: a channel destroying 10% and one adding 15% emit
  the same symbol. Inserting the signed verdict (negative / inconclusive /
  positive) gives a second garbling chain, and `VERDICT → BIT` is measurable
  from multinomial counts with **no density estimation at all** — a
  `Dirichlet(counts + α)` posterior propagated through EVSI. The sign loss is
  **$2,792 [1,538–4,537]** for CausalPy, whose significance bit is worth
  **$0 in all four scenarios**; $1,402 [692–3,262] for Google MM; $937
  [512–1,375] for CausalImpact. For GeoLift it is **not established**
  ([0–1,337]) — its `P(significant)` is 0.05–0.19 at *every* truth, so its
  verdict is nearly mute and there is nothing for the sign to carry.
  Addendum 3, Finding A.

### What the information is worth — `docs/layer3-first-result.md` Addendum 4

- **The sign loss, on the documented prior.** Computed on
  `0.45·δ₀ + 0.55·N(0.04, 0.06²)` conditioned on the validated support, with
  the spike kept as an **atom**: CausalPy **$2,130 [1,546–3,459]** against a
  significance bit worth **$0**; CausalImpact $1,088; Google MM $1,064;
  GeoLift $214, not established. EVPI $22,120.
- **82–90% of it (net) comes from prior mass below zero.** The economically
  important information an unsigned signal destroys is *directional
  information in adverse-effect states* — an unsigned `significant` cannot
  tell a business to cut.
- **The transportable unit is a rate, not a dollar.** Utility is exactly
  linear in spend, so a signed verdict is worth **0.15–0.26% of the spend it
  governs, per decision**. M9 asks whether any experiment design clears that
  bar; see `docs/m9-preregistration.md`.

### Which design axis is worth paying for — Addendum 5

16 cells, 25,600 rows, every cell a slice of the **same maximal latent
world**, so a cell-to-cell difference is a design effect and not two
independent Monte Carlo draws. Each axis contrast holds the other axis fixed.

> **In the investigated grid, increasing test duration systematically raised
> `r_EVSI` for the tools that had an informative VERDICT at all, while
> increasing the donor pool from 5 to 40 showed no comparable stable gain.**

- **Duration, T=15 → T=42 at fixed `G_c`:** 8 of 12 spans established
  positive among the tools with signal, **none negative**. CausalImpact 4/4,
  +0.31 to +0.40 percentage points of governed spend.
- **Donor pool, 5 → 40 at fixed T:** **1 of 16** spans excludes zero. That
  licenses *no convincing evidence of appreciable benefit over this range* —
  **not** "donors do nothing". An effect that is not established is not an
  effect of zero.
- **A contrast that moves both axes is not evidence about either.** The
  poorest → richest step (+0.402% for CausalImpact) characterises a change of
  design and is excluded from the axis claims.
- **GeoLift is inert on this surface** — median `r_EVSI` 0.0000%–0.0571%,
  exactly zero in five of sixteen cells, no span excluding zero on either
  axis. Descriptive, with the range attached.
- **Sign loss is larger by point estimate on richer cells** (CausalPy 0.2975%
  → 0.4758%). An observation, not yet a law: it has not had the
  paired-interval treatment the axis contrasts received.
- **What it narrows:** widening the donor pool further is a weaker candidate
  for the next experiment than duration, the decision interface, or the sign
  loss — on observed yield per unit of compute, not on a demonstrated null.

### The donor reproduces — `docs/donor-repro.md`

An independent end-to-end reproduction of the Recast study, on a different
OS, architecture and BLAS:

| | |
|---|---|
| R0 published rows → published aggregates | **PASS** |
| R1 same seed → same generated data | **PASS**, 320/320 exact to 1e-9 |
| R2 same panel → same estimator output | **PASS**, all four tools |
| G4 θ mutation at +2% | **PASS** 6/6 criteria |

**The packaging is fragile and the science underneath it is sound.** Thirteen
defects had to be worked through first, two of them blocking — and every one
of them is about packaging, not method. A by-product nobody has published:

| tool | same answer on a different machine? |
|---|---|
| `google_mm` | yes, to machine precision |
| `geolift` | yes, exactly, at the precision it reports |
| `causalimpact` | yes, exactly — seeded BSTS, not the coin-flip it looks like |
| `causalpy` | distributionally; individual runs differ by ~1.3% of the effect |

---

## What is **not** established

Kept here rather than in a footnote, because the track's whole method is
refusing to overclaim:

- **The DGP is synthetic.** M7 took it from two truths to seven, two of them
  negative, but reproducing a simulation faithfully still says nothing about
  whether it resembles a real marketing experiment. This is the largest
  limitation by a distance.
- **The *other* half of the split — thresholding — is provisional.**
  `INTERVAL → VERDICT` needs a 3-d density from ~50 runs per truth, the
  estimator this project has already caught running out of sample twice. It
  separates from zero pooled for three tools and not for CausalPy, and at 12
  fitted rows per truth the per-scenario figures are noise. The **ratio**
  between the two halves is therefore resolved in only 9 of 20 cells; where
  it is not, the honest output is two dollar figures, not a percentage of
  them. Previously published shares of 63%, 79% and 68.4% are withdrawn —
  see F15.
- **The sweep's `P(θ<0) = 0.267` row is a sensitivity, not a reconstruction.**
  It matches one marginal of the documented continuous prior onto a
  seven-point grid. Where the negative mass *sits* decides a five-action
  problem — mass at −10% argues for `cut hard`, the same mass at −1% argues
  for `hold` — and seven points cannot tell them apart. A finer grid near
  zero and near the four **action boundaries** (M8) is what would fix it —
  and those are at −3.125%, +1.25%, +5.1875% and +10.4375%, *not* at the +3%
  economic breakeven, which is not a decision boundary at all.
- **Nothing here has touched a real business's data.** No experiment has been
  run, no budget moved.
- **CausalPy's ~1.1–1.3% point-estimate noise is unexplained.** Three
  mechanisms proposed, three excluded (F8) — the last by a *paired exclusion
  test* rather than a failed null test: `mu` changes the noise by −0.1%
  [−2.5%, +2.2%] against the −50% the mechanism would require. A fourth is
  written down as a hypothesis, with what it predicts, and is deliberately
  **not** queued.
- **EVSI *levels* are density-dependent** — $46k under a KDE, $67k under a
  Student-t, and the 3-d interval density inflates further. Only the
  orderings and the held-out AUC differences are robust, which is why AUC is
  now computed alongside every EVSI.
- **The figure layer of the donor lies on any θ ≠ 7.5%** unless patched. Ours
  patches it; theirs does not.

---

## Running

| | what it answers |
|---|---|
| `scripts/voi_v2.py` | is a free experiment ever worth negative value? (no — that was the v1 bug) |
| `scripts/information_ladder.py` | what does thresholding cost? Blackwell self-test, held-out AUC, `--sweep` for the business plane |
| `scripts/likelihood_models.py` | is a null result a property of the data or of the density estimator? |
| `scripts/s0_reconstruction.py` | is the bit's value determined by its error rates alone? |
| `scripts/theta_atlas.py` | how does each tool behave as the truth moves? |
| `scripts/continuous_ladder.py` | the ladder with five actions and a real prior over effect size |
| `scripts/signed_verdict.py` | is the bit worthless because it is coarse, or because it is *unsigned*? `--neg-sweep`, `--alpha-scan` |
| `repro/recast/extend_from_freeze.py` | refuses to extend the run unless exactly one thing changed since the freeze |
| `scripts/theta_interpolation.py` | can `q(θ)` be interpolated between simulated truths? leave-one-θ-out against bootstrap noise |
| `src/leadbench_mx/clusters.py` | the common-random-numbers gate: refuses any analysis whose truths rest on different latent panels |
| `scripts/m9b_surface.py` | what is a longer test, or a bigger donor pool, worth? `r_EVSI(T, G_c)`, every difference paired across the shared world. Refuses to read the surface until all 16 cells are complete |
| `repro/recast/m9b_world_check.py` | do the M9-B design axes move the design without moving the world? 11 metamorphic relations, plus the five generator mutations they must refuse |
| `repro/recast/m9b_run_invariants.py` | does the run that actually happened obey the world contract? Same invariants, on the seed logs the run emitted, at full scale |
| `repro/recast/gate_witnesses.py` | C12: for each gate, an artifact that passes every cheap proxy and violates the invariant. Asserts the proxy passes AND the gate rejects |
| `repro/recast/closure_attest.py` | C14: an attestation *about* a frozen subject set. Refuses on a dirty tree, excludes itself from its own subjects, hashes last |
| `repro/recast/` | the reproduction gate: bootstrap, replay check, θ mutation, G4 criteria |
| `scripts/significance_gate_v1.py` | **superseded.** Kept because the bug it contains is the finding |

Tests: `pytest tests/` from this directory (232 invariants).

---

## Method notes

- **Preregistration before results.** G3's tolerances were fixed, in writing,
  before any replay ran — and revised once *before* seeing output, with the
  evidence for the revision recorded so it cannot later be mistaken for a
  tolerance widened to fit.
- **`docs/failures.md` is not decoration.** Twenty-two entries, seven of them
  errors the reader caught rather than me. F22 is the sharpest: **the same
  defect three times in one milestone** — a suite that counted *nesting*
  while guarding *randomness*, a gate that counted *rows* while guarding
  *whether tools ran*, a seal that counted *files* while guarding
  *completeness*. Writing the general form down after the first two did not
  prevent the third. What would have is C12, the **adversarial gate
  witness**: for every gate, a stored artifact that satisfies every cheap
  proxy signal *and* violates the invariant, which the gate must reject.
  `repro/recast/gate_witnesses.py` holds one per gate; currently 3/3.
- **Kill-first** (`docs/kill-first.md`, C13). Before substantial work:
  hypothesis → necessary condition → cheapest falsifier → kill criterion →
  stop-loss. **If the result that would cancel the work cannot be named in
  advance, the work is not launched.** M9-B cost 64.8 aggregate
  process-hours; two of its three follow-on questions turned out to be
  premise-testable against cached data in under a minute. The GeoLift
  direction *survived* its falsifier and is better specified for it — the
  protocol is not an argument for doing less, but for finding out which work
  is real before paying for it.
- **No web app, no ad spend** (§76, §77).
- **Licence hygiene** (§70): the donor has no licence. Nothing of theirs is
  vendored here — the reproduction works through an external wrapper and a
  recorded diff.
