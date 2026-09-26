# Assumption contracts

Four of this track's failures — F13, F14, F15, F16 — share one shape. The
arithmetic was correct. The **sentence describing what the arithmetic was
entitled to mean** was not, and nothing in the test suite could tell, because
the sentence was not in the test suite.

That class has a name in simulation science, and it is not "bad unit tests".
It is a **verification failure against the conceptual model** — the
distinction between checking that the implementation matches the model and
checking that the model represents reality for the intended use. The
conceptual model is not only the equations; it is the assumptions,
abstractions and descriptions around them. So:

> **Conceptual-model contract failure** — the computation was internally
> correct, but an unverified structural assumption changed what the
> computation was entitled to mean.

| | the false sentence | what it was about |
|---|---|---|
| F13 | "BIT is a coarsening of POINT" | conceptual structure |
| F14 | "the Blackwell self-test applies here" | a theorem aimed at the wrong estimand |
| F15 | "this is a lower bound" / "this is the documented prior" | a name stronger than its construction |
| F16 | "the θ samples are independent" | the experimental design |

## The process

Small, and deliberately not a cathedral. Before each milestone, every
load-bearing sentence gets four fields. A sentence with no `CHECK` is not
allowed to carry a result.

    CLAIM        the structural assertion, in one line
    SOURCE       where it comes from: file:line, or the run that evidenced it
    CONSEQUENCE  what must be observable if it is true
    CHECK        the executable thing that would fail if it were not

Two rules make it work rather than decorate:

1. **A claim needs SOURCE or CHECK, and preferably both.** Reading the donor's
   source is evidence; so is a probe on its output. Neither one alone caught
   F16 — the comment was there to read, and the +1.000 correlation was there
   to measure, and prose beat both for a milestone.
2. **The CHECK runs in the analysis, not only in CI.** F16's gate refuses the
   run. A check that merely passes in a test file does not stop a wrong
   analysis from printing a plausible number.

## Current contracts

### C1 — the significance bit is the interval excluding zero

    SOURCE       donor adapter output, empirically
    CONSEQUENCE  derived bit == stored `significant` on every row
    CHECK        audit_bit_is_garbling(); 2,800/2,800 exact
                 signed_verdict.py refuses to continue on any mismatch

### C2 — VERDICT → BIT is a deterministic garbling

    SOURCE       C1, plus the GARBLE matrix
    CONSEQUENCE  EVSI(VERDICT) >= EVSI(BIT) for every likelihood and prior
    CHECK        tests/test_signed_verdict.py, 25 random likelihoods x 6
                 priors; and min(V-B) over 400,000 posterior draws, printed
                 by every run

### C3 — new effect-size arms share the latent panel by iteration

    SOURCE       src/R/generate_panels.R:375-379 (no effect-size term in
                 `panel_seed`; comment "same seed for null and effect")
                 run_tools.py:173 (`--seed iteration` to CausalImpact)
                 run_causalpy.py:100 (`random_seed = iteration`)
                 GeoLift and Google MM take no estimator seed at all
    CONSEQUENCE  residuals across θ are paired by (scenario, iteration)
    CHECK        corr(att_pct - effect_pct) across θ within a cluster
                 measured +1.000 for all four tools (min +0.999)

### C4 — the cluster is (scenario, iteration), not iteration alone

    SOURCE       the estimator seed is the bare iteration index, so it
                 REPEATS across scenarios — C3 does not settle this
    CONSEQUENCE  if the shared seed linked scenarios, residuals for the same
                 iteration in different scenarios would correlate
    CHECK        measured: mean cross-scenario r = +0.012 (causalimpact),
                 +0.026 (causalpy) — against -0.031 (geolift) and -0.045
                 (google_mm), which take NO estimator seed. The seeded tools
                 look like the unseeded controls, so the seed does not link
                 scenarios.

### C5 — the join key is unique

    SOURCE       D13: an appended results file silently duplicates rows
    CONSEQUENCE  a duplicate is a doubled likelihood weight
    CHECK        guard_unique() and the cluster gate both refuse duplicates
                 rather than deduplicating

### C6 — the runtime is the R 4.5.1 lane

    SOURCE       F11: the Makefile's RSCRIPT governs only `make panels`,
                 while run_tools.py hardcodes "Rscript"
    CONSEQUENCE  the resolved interpreter is a property of the run
    CHECK        asserted and printed by the run itself, not inferred from
                 the environment

### C7 — the M8 pilot preserves CRN clusters

    SOURCE       this preregistration; nine new truths at 10 iterations
                 beside seven existing truths at 25
    CONSEQUENCE  every truth rests on the same set of latent panels
    CHECK        require_complete_clusters(..., expect_iterations=1-10)
                 refuses the analysis otherwise; rows per (tool, θ) must be
                 constant after gating

### C8 — +3% is not a decision boundary

    SOURCE       the quadratic adjustment cost in budget_problem
    CONSEQUENCE  the optimal action changes at b + c(d_i+d_j)/k, not at b
    CHECK        action_boundaries() against a 500,001-point brute-force
                 argmax sweep; and an assertion that +3% is not among them

### C9 — cross-channel equality for any duplicated decision-relevant scalar

    CLAIM        Any decision-relevant scalar written to more than one
                 provenance channel has a CANONICAL REPRESENTATION, and the
                 channels are checked for equality against it before analysis.
    SOURCE       θ is written twice: panel_seeds.csv via write.csv, and
                 metadata.json -> results.jsonl via jsonlite::toJSON, whose
                 default is digits = 4
    CANONICAL    the exact numeric θ passed to --effect_sizes. JSON and CSV
                 are serialisations OF it, not competing versions of it.
    CONSEQUENCE  every channel must reproduce the canonical value exactly
    CHECK        m8_pilot_check.py §1b, exact float equality; and
                 f17_closure.py, which additionally proves that the correction
                 moved only allowlisted fields

An earlier draft of this contract said merely "duplicate and compare", and
that is not enough. Duplication without a designated canonical representation
produces a disagreement with no way to say which side is wrong — two channels
and no truth is a worse position than one channel, because it manufactures the
appearance of verification. What makes the check decidable is naming the
canonical form first.

**Why the contract exists at all is worth recording.** It was not foreseen.
The seed log was added to evidence a *different* claim — that new arms attach
to old clusters — and incidentally created a second write path for θ. The
comparison fell out for free, and caught F17. Generalising: a provenance
record is worth most when it duplicates something already recorded elsewhere,
because duplication against a canonical form is what makes silent corruption
visible. A log that records only what nothing else records can confirm but
never contradict.

### C9a — the canonical representation must itself be unique

    CLAIM        canon_str(x) returns the same string for every value equal
                 to x, and never exponential notation
    SOURCE       `--effect_sizes` was given "0.10"; metadata.json records
                 0.1. The same number, two strings.
    CONSEQUENCE  a state that has not changed must not read as changed
    CHECK        tests/test_canonical.py; and the extension gate, which
                 refused an unchanged state until this was fixed

Caught by running the gate rather than by reading it. The first version
compared `str(dec(...))`, which preserves trailing zeros, so the extension
gate reported `design.theta_grid_new` as CHANGED between a freeze and itself
— a false alarm from the contract written to prevent false confidence. A
canonical representation that is not unique is not canonical; it is just a
preferred spelling. `normalize()` fixes the trailing zero and `format(...,
"f")` keeps 100 from becoming `1E+2`.

The same run also found that `numpy.float64` subclasses `float` while its
numpy-2 repr is `np.float64(-0.03125)`, which `Decimal` cannot parse — so
the canonicaliser raised on the first array scalar it met, which was one of
the action boundaries it exists to check.

### C10 — a comparison instrument must not normalise away the thing compared

    CLAIM        a diff used as evidence distinguishes "absent", "null" and
                 "present with a value"
    SOURCE       f17_closure.py's first version compared two runs through a
                 pandas merge and reported `converged` as differing in 1,080
                 rows. It does not differ: the key is simply ABSENT for three
                 of the four tools in both files, and the merge stringified
                 the missing values inconsistently between frames.
    CONSEQUENCE  a field absent in both files is identical in both files
    CHECK        the closure diff compares parsed JSON objects row by row with
                 an explicit _ABSENT sentinel, never a DataFrame round-trip

A phantom finding inside a closure check is worse than no closure check: it
spends the reader's trust on nothing, and the next real finding arrives
looking the same. This is the same family as F13-F16 — an instrument whose
described behaviour and actual behaviour differed — which is why it is a
contract and not a code comment.

## The principle underneath C9, C9a and C10

F17 and F18 are the same shape twice:

    F17   a decimal fact -> a binary serialisation -> a tolerance
          -> the tolerance itself fails on the one case it existed for

    F18   a "canonical" form -> two spellings of one value
          -> a false CHANGED -> the temptation to relax the checker

So:

> **Representation disagreements are resolved by defining identity, not by
> widening equality.**

Every time a representation question in this project was answered with a
tolerance, the tolerance was the bug. Half the last retained digit is exact
in decimal and inexact in binary. `0.10` and `0.1` are equal as numbers and
unequal as strings. Neither needed an epsilon; both needed the question asked
in the domain where the answer is exact.

The same principle is what C10 is about from the other side: `absent`,
`null`, `NaN` and `""` are four distinct states, and systems built for
convenience — pandas among them — will merge them into one comfortable
swamp. A comparison that has already merged them cannot answer a question
about which one it was.

### C11 — every M9-B cell is a slice of one maximal world

    SOURCE       docs/m9-preregistration.md, M9-B Addendum 1; the measured
                 behaviour of draw_baselines()/select_treated() when n_geos
                 moves (treated geo City 3/5/11/21 at n_geos 6/10/21/41)
    CLAIM        Moving T or G_c changes the DESIGN and not the WORLD:
                 the treated geo, its trajectory, the donor ordering and
                 the shared panel_seed are identical across all 16 cells of
                 a replication.
    CONSEQUENCE  r_EVSI(T, G_c) - r_EVSI(T', G_c') is a design effect. Under
                 the donor's own knobs it would also carry a change of
                 world, and the axis would mean something false.
    CHECK        repro/recast/m9b_world_check.py, W1-W7. W6 is the negative
                 test (strip the maximal cell down to the smallest and
                 require equality); W3d re-derives the donor permutation
                 from perm_seed in a separate R process. Five generator
                 mutations are required to be refused -- see F20.

### C12 — Proxy-preserving adversarial witness

    SOURCE       F22: the same defect three times in one milestone. F20's
                 metamorphic suite counted NESTING while guarding
                 RANDOMNESS; F21's completion gate counted ROWS while
                 guarding WHETHER TOOLS RAN; the M9-B blinding seal counted
                 FILES while guarding COMPLETENESS.
    CLAIM        Every gate protects an invariant, and every gate is
                 written where some cheaper PROXY for that invariant is
                 conveniently visible. The proxy is the shortcut the author
                 will take. A generic negative test does not catch this,
                 because a generic negative fails the proxy too.
    PATTERN      A *proxy-preserving adversarial witness*. This is a
                 variant of the test-oracle problem: where no cheap correct
                 answer exists, one checks necessary relations instead --
                 and the failure mode is that the relation chosen is a
                 SURROGATE the defect also satisfies. A generic negative
                 fixture does not help, because it fails the surrogate too
                 and so exercises nothing. The witness must PRESERVE every
                 surrogate signal of correctness and break only the
                 invariant.
    REQUIREMENT  For every gate there must exist a STORED ARTIFACT that
                   (a) satisfies every cheap proxy signal the gate is
                       tempted to count, AND
                   (b) violates the invariant the gate exists to protect,
                 and the gate must REJECT it. Both halves are asserted: a
                 witness that fails its own proxy proves nothing.
    WITNESSES    repro/recast/gate_witnesses.py, deterministic fixtures:
                   nesting      pools genuinely nest, D5 subset D9 subset
                                D20 subset D40, every recorded field
                                self-consistent -- donor order is the
                                SORTED geo index, not a substream draw
                   completeness exactly 1,600 well-formed rows, every key
                                present, `significant` populated -- one
                                tool's att_pct is null throughout
                   seal         all 16 cell files present at exactly the
                                right row count -- half carry two tools
                                with no estimates at all
    CHECK        `python repro/recast/gate_witnesses.py` -- for each
                 witness it asserts the proxy PASSES and the gate REJECTS.
                 Currently 3/3.
    NOTE         writing the general form down is not a control. F20's
                 lesson predates F21 by four days and F21's predates the
                 seal by two. Only executing a gate against an artifact
                 built to defeat its shortcut has ever caught one.

## Metamorphic relations

Where no oracle exists — and for a simulator there usually is none — the
checkable thing is a **relation that must hold between related runs**. The
failure log arrived at several of these before anyone named the technique:

| relation | must hold |
|---|---|
| information is free | `EVSI >= 0` |
| a signal is garbled | EVSI cannot increase |
| same panel, new θ | cross-arm residual identity `att(θ) − att(null) − true == 0` |
| θ negated | the sign propagates to the estimate |
| a richer exact signal | Blackwell ordering |
| a useless signal | EVSI is exactly 0, not merely small |
| a design axis moves | the latent world does not (M9-B W1–W7) |
| a slice of a larger run | equals the smaller run exactly (M9-B W6) |

Each one is already an executable check somewhere in this repository. The
point of listing them together is that they are the same tool, and the next
one should be reached for deliberately rather than discovered after a
milestone.

## What this does not fix

It will not stop the next error. It narrows the class: a structural claim can
no longer sit in a docstring for a milestone without either a source citation
or something that fails when it is false. F16 had both available — a comment
in the donor's own source, and a correlation of +1.000 sitting in the results
file — and neither was consulted, because nothing required it.
