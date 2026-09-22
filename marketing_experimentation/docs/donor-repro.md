# Donor reproducibility gate — `getrecast/geolift-simulation-study`

We are building research **about whether statistical machinery can be
trusted**. Beginning it with "the environment installed, more or less" would be
an unusually elegant way to curse the project. So the donor harness passes a
gate before it produces a single new number.

**Donor:** `getrecast/geolift-simulation-study` @ `5133d37`
(2026-06-15, "Geo experiment simulation study")

```
G0  pristine clone, environment recorded
 ↓
G1  dependency bootstrap                      <- blocked, see §3
 ↓
G2  upstream `make smoke`, N=5, all four estimators
 ↓
G3  reproduce one exact published cell (DGP -> estimator -> raw output)
 ↓
G4  theta mutation at +2%, N=20-50
```

Only after G4 does an effect-size sweep begin. Two of the milestones below are
already passed and they are the reason the gate exists: reproducing
*aggregates from published raw output* (M0) tests only half the chain.

---

## 1. Milestones

| | milestone | state |
|---|---|---|
| M0 | published raw metrics reproduced from `results.jsonl` | **PASS** |
| M1 | decision-theory invariants (`0 ≤ EVSI ≤ EVPI`, free info never hurts) | **PASS** |
| M2 | significance-gate bug isolated and relabelled | **PASS** |
| M3 | information ladder on two-point θ | **PASS**, conclusion limited to S0→S1 |
| M4 | clean upstream environment | **IN PROGRESS** |
| M5 | end-to-end upstream golden replay | blocked on M4 |
| M6 | θ mutation (+2%) as a pipeline mutation test | blocked on M5 |
| M7 | coarse θ likelihood atlas | blocked on M6 |
| M8 | continuous prior + richer action set | blocked on M7 |
| M9 | business VOI / RUN–DON'T-RUN | blocked on M8 |
| M10 | regime map / method selection | blocked on M9 |

## 2. G0 — environment, recorded rather than assumed

| component | donor (`VERSIONS.md`, `renv.lock`) | here | deviation |
|---|---|---|---|
| OS / arch | macOS ARM64 (Darwin) | **Linux x86_64** 6.18.44 | **platform differs** |
| Python | 3.12.8 | **3.11.15** | minor version |
| R | **4.5.1** (`renv.lock`) | **4.6.1** (CRAN apt, installed for this gate) | **minor-series gap**; distro apt offered only 4.3.3, CRAN apt serves current 4.6.1 — 4.5.1 is not available from either |
| Make | GNU Make | GNU Make 4.3 | ok |
| C compiler | — | gcc 13.3.0 | recorded |
| CRAN reachable | — | yes (HTTP 200) | ok |
| disk free | — | 25 GB | ok |

Pinned tool versions the replay must match: CausalPy 0.8.0, PyMC 5.28.1,
ArviZ 0.23.4, CausalImpact 1.4.1, `google/matched_markets` @ `5e3cd95`,
`facebookincubator/GeoLift` @ `4d2afd4`, `augsynth` @ `65c5a6f`.

R 4.5.1 could not be obtained from either package source: the distribution
ships 4.3.3 and the CRAN repository serves the current 4.6.1. Pinning it
exactly would mean building R from source or using `rig`. We proceed on 4.6.1
and record it, because 4.5 → 4.6 is a new minor series and R packages are not
binary-compatible across it — every `renv` package will be rebuilt from
source against 4.6.1 rather than restored as the donor built them. **If G3
disagrees numerically, this is the first suspect, ahead of the platform.**

**The platform difference is not a defect, but it must be recorded**, because
it is the most likely explanation for any numerical disagreement at G3 — and
because attributing a real disagreement to "probably the platform" without
having written the platform down first is how reproducibility studies quietly
fail.

## 3. Donor defects found before running anything

None of these are complaints. Each one would have cost compute or confidence
if discovered after a long run.

### D1 — bootstrap deadlock: `.Rprofile` needs a file the repo excludes

```
.Rprofile      ->  source("renv/activate.R")
.gitignore:22  ->  renv/
```

`renv/` is absent from a pristine clone (confirmed), and `make env` runs
`Rscript -e "renv::restore()"` as its R step. R sources `.Rprofile` at
startup, so on a cold clone R can fail looking for `renv/activate.R` *before*
it is able to run the restore that would create it.

**Our handling:** bootstrap explicitly with `R --vanilla` (which skips
`.Rprofile`), install `renv`, then restore from `renv.lock`. We do **not**
patch the donor — the defect is evidence and gets recorded, not erased.

### D2 — README gives a clone URL that does not exist

```
README.md:84   git clone https://github.com/getrecast/geolift-study.git
actual repo    https://github.com/getrecast/geolift-simulation-study
```

Trivial, and pointed: a reproducibility study whose first instruction is a
404.

### D3 — `VERSIONS.md` contradicts `renv.lock` on the R version

`VERSIONS.md` records R as "(captured at install time — run `R --version`)"
while `renv.lock` pins **R 4.5.1** exactly. The manifest that a reader
consults is vaguer than the lockfile that actually governs the restore.

### D4 — two dependency specifications that disagree

| | `pyproject.toml` | `requirements.txt` |
|---|---|---|
| PyMC | `pymc>=5.10` | `pymc==5.28.1` |
| arviz | `arviz>=0.15` | `arviz==0.23.4` |
| matched-markets | `git+...` (no pin) | resolved pin |

`requirements.txt` states its own provenance — "Frozen dependencies for exact
reproduction. Generated from Python 3.12.8 on macOS (ARM64), March 2026".
`make env` installs **both**, `requirements.txt` first and then `pip install
-e .`, so the loose constraints run second and could in principle move a
pinned version.

**Our handling:** install from `requirements.txt` only, then `pip install -e .
--no-deps`.

### D5 — no licence

No `LICENSE`, `LICENSE.md` or `LICENSE.txt` in the repository, and the GitHub
API reports no SPDX licence. Reading the artefact, recomputing from published
outputs and citing it are ordinary research use. **Forking the harness into a
product is not available without a grant from the authors.**

**Our handling:** we do not vendor donor source into this repository. We
record bootstrap instructions and content hashes, and keep the clone external
at `/home/user/getrecast/geolift-simulation-study`.

## 4. G3 tolerances, fixed before the replay

Defined in advance so a disagreement cannot be rationalised afterwards. One
seed from `A1` null and one from `A1` +7.5%, all four tools, comparing
`att_pct`, `ci_lower`, `ci_upper`, `significant` and available diagnostics.

| tool | expectation | tolerance on `att_pct` |
|---|---|---|
| `google_mm` | OLS/TBR, essentially deterministic | tight — any material gap is a real finding |
| `geolift` | deterministic block-conformal inference per donor | tight |
| `causalpy` | PyMC MCMC, platform-sensitive | loose, judged against its own MC error |
| `causalimpact` | BSTS, platform-sensitive | loose, same basis |

The per-method reproducibility profile that falls out of this is worth having
on its own: "which of these tools gives the same answer on a different
machine" is a question a buyer would ask and nobody has published.

## 5. G4 — the mutation test, and what it is really checking

Before any sweep: `A1`, θ = **+2%**, N = 20–50. Not for statistics — to find
out whether the pipeline is parameterised in θ or merely appears to be.

Specifically, whether anything downstream assumes `effect ∈ {0, 0.075}`:
`effect_label == "effect"` used as a proxy for the magnitude, a hard-coded
`0.075` in metric computation, `true_att_pct` not recomputed, the
`results.jsonl` schema, or golden-comparison logic keyed to the two known
arms. A generator can be fully parameterised while the analysis quietly is
not.

## 6. Then a two-stage sweep, not a uniform one

Coarse first — θ ∈ {−10%, −5%, 0, +2%, +5%, +7.5%, +15%}, `A1` only, ~100
iterations — to see the *shape* of `p(S|θ)`: discontinuities, pathological
failures, how variance moves, whether errors are symmetric about zero, and
whether the S0/S1 story survives more than two truths.

Only then place θ densely where the decision boundary actually moves. A
uniform 13 × 4 × 1000 × 4 grid is 208,000 fits, most of them spent confirming
that every method detects a +20% lift.

## 7. A limitation of the current result this gate will resolve

The information ladder found `S1 → S2` worth between −$1,475 and +$96, with a
sign that flips across bandwidths — the interval adding nothing measurable on
top of the point estimate.

**That may be an artefact of the two-point world rather than a property of
intervals.** With θ ∈ {0, +7.5%} the point estimate nearly identifies the
state on its own, leaving the interval nothing to contribute. Once θ ranges
over −10% to +15%, two identical point estimates carrying different
uncertainty can imply different posteriors and different actions, and S2 gets
its first fair test.

So the current conclusion is strictly: **the large loss is at thresholding a
continuous estimate into a significance bit.** It is *not* "confidence
intervals are useless", and nothing here licenses that.
