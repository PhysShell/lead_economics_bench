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
| `scripts/theta_interpolation.py` | can `q(θ)` be interpolated between simulated truths? leave-one-θ-out against bootstrap noise |
| `src/leadbench_mx/clusters.py` | the common-random-numbers gate: refuses any analysis whose truths rest on different latent panels |
| `repro/recast/` | the reproduction gate: bootstrap, replay check, θ mutation, G4 criteria |
| `scripts/significance_gate_v1.py` | **superseded.** Kept because the bug it contains is the finding |

Tests: `pytest tests/` from this directory (213 invariants).

---

## Method notes

- **Preregistration before results.** G3's tolerances were fixed, in writing,
  before any replay ran — and revised once *before* seeing output, with the
  evidence for the revision recorded so it cannot later be mistaken for a
  tolerance widened to fit.
- **`docs/failures.md` is not decoration.** Sixteen entries, seven of them
  errors the reader caught rather than me. Four of them — F13–F16 — are one
  class, **conceptual-model contract failure**: correct arithmetic under a
  structural assumption that was never checked. `docs/assumption-contracts.md`
  is the response: every load-bearing claim carries a source and an
  executable check, and the check runs inside the analysis, not only in CI — including F13, which invalidated
  the structure the main result was expressed in. History is not cleaned into a
  heroic narrative (brief §75).
- **No web app, no ad spend** (§76, §77).
- **Licence hygiene** (§70): the donor has no licence. Nothing of theirs is
  vendored here — the reproduction works through an external wrapper and a
  recorded diff.
