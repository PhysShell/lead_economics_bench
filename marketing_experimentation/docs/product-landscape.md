# Product and prior-art landscape — marketing experimentation preflight

**Status: first pass, Phase 2 in progress.** Accessed 2026-09-22. Vendor
capability claims are marked *vendor-reported* and are not independently
verified. Where a primary source (paper, official docs, source repository)
exists it is preferred over commentary, per the brief's source hygiene rule.

This document exists to answer one question before any code is written:

> Has the profession already built the thing we are proposing?

The short answer so far is **substantially yes, and one part of it was
published three months ago**. The details of what remains are below.

---

## 1. The single most important prior-art hit

**Recast Research, "Open-Source Geo-Experiment Tools — A Head-to-Head
Simulation Study", Robson Tigre, June 2026.**
<https://research.getrecast.com/geolift-sim-study> · code at
`getrecast/geolift-simulation-study`

This is, in outline, the geo half of the benchmark this brief proposes, and it
already exists, open source, from three months ago.

It compares four tools at pinned versions — **CausalPy 0.8.0** (Dirichlet
synthetic control), **Google Matched Markets** at commit `5e3cd95` (OLS
time-based regression), **Meta GeoLift 2.7.5** (ridge augmented synthetic
control) and **CausalImpact 1.4.1** (Bayesian structural time series) — on
synthetic panels, across four scenarios, reporting bias, coverage, false
positive rate, false negative rate and CI width.

Its headline numbers matter more than its existence, because they are exactly
the kind of result this brief hopes to find:

| tool | coverage | FPR | FNR |
|---|---|---|---|
| Meta GeoLift 2.7.5 | 92–95% | **3–5%** | **91%** |
| CausalImpact 1.4.1 | — | **~30%** | detects in 52–66% of runs |
| Google MM / CausalPy | 76–86% | 14–25% | between the two |

Read that GeoLift row again. It is beautifully calibrated under the null and
**almost never detects a real effect**. Under a 30-day pre-period its
confidence intervals contain zero in **95.7%** of runs. The study's own
summary of the point-estimate view is the sentence this whole research
programme is about:

> "Point estimates alone would tell you these tools are interchangeable. The
> uncertainty story tells you why they aren't."

**What this kills.** The differentiation claim "vendor-neutral empirical
comparison of multiple geo estimators" is no longer novel. Capability level
**I** (compares multiple estimator families empirically) is *done*, publicly,
with code.

**What it leaves.** The study is deliberately narrow, and its limits are the
only remaining room:

- **Entirely synthetic.** Multiplicative panels with lognormal baselines,
  AR(1) noise at ρ=0.30, 105 days. No real geo data, no semi-synthetic worlds
  built from real distributions.
- **Four hand-picked scenarios**, not a space-filling design over a continuous
  parameter space. No sensitivity analysis, so which data property *drives*
  the ranking is not established.
- **One effect size** (7.5%) against null.
- **Recommendations are prose**, per tool, written by a human — not a fitted
  selector with measured selection regret.
- **No business cost, no value of information, no do-not-run threshold.** The
  study flags that 30 days of history is insufficient; it does not price the
  experiment or compare it against not experimenting.
- **Geo only.** No user-level track, no OPE.
- **Author is vendor-affiliated.** Recast sells MMM, and a study concluding
  that geo experiment tools are hard to trust is not adverse to that interest.
  The code is open, which is the right mitigation, but the framing is not
  neutral and should not be cited as if it were.

---

## 2. Capability grid

Levels per the brief's §4. `?` means not yet verified against a primary
source — these are the gaps Phase 2 still has to close.

| | A analyze | B power/N | C metric valid | D sim A/A | E inject effect | F placebo | G design rec | H estimator choice | I multi-estimator | J business cost | K do-not-run | L VOI | M engine regression | N vendor-neutral |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Statsig** | ✅ | ✅ | ✅ | **✅ daily, all customers** | ? | — | — | partial | — | — | — | — | ✅ | — |
| **Microsoft ExP** | ✅ | ✅ | **✅ A-D uniformity** | ✅ | ? | — | — | — | — | — | — | — | ✅ | internal only |
| **Meta GeoLift** | ✅ | ✅ | — | — | ✅ power sim | ✅ | partial | — | — | partial (CPIC) | — | — | — | OSS |
| **Google Meridian GeoX** | ✅ | ? | — | — | ? | — | **✅ holdback/go-dark/heavy-up** | — | — | ? | — | — | — | *vendor-reported* publisher-agnostic |
| **Google Trimmed Match** | ✅ | ✅ design | — | — | ✅ | — | ✅ pairing | — | — | — | — | — | — | OSS |
| **Google Matched Markets / TBR** | ✅ | ✅ | — | — | ✅ | — | ✅ | — | — | — | — | — | — | OSS |
| **Haus** | ✅ | ✅ | — | — | — | **✅ pre-launch placebo → holdout size** | ✅ | — | — | ✅ | — | — | ? | — |
| **Rockerbox** | ✅ | ✅ | — | — | — | — | ✅ market selection | — | — | ? | — | — | — | — |
| **Measured** | ✅ | ✅ | — | — | — | — | ✅ | — | — | ? | — | — | — | — |
| **Recast (study)** | ✅ | — | — | — | ✅ | ✅ | — | — | **✅ published** | — | — | — | — | ✅ OSS study |

**The answer to the brief's central landscape question — "does a mature
product already do I–N?" — is: no single product does, but I is published, G
is productised by Meridian GeoX and Haus, F is productised by Haus, D is
productised by Statsig, and J is partially in GeoLift and Haus. What is
unclaimed across the whole grid is K, L and a fitted, measured version of
H+I.**

---

## 3. Confirmed capability detail

### Statsig — simulated A/A, daily, for every customer (capability D)

Statsig runs simulated A/A tests **every day in the background for every
company on the platform** (*vendor-reported*, Statsig docs and blog). Reported
validation: 10,000 simulated A/A tests at 100k users per group enrolled over
14 days; their sequential methodology holds FPR below 5%, a fixed-horizon
z-test sits at ~5%, and a z-test **with peeking exceeds 20%**.

That last figure is independent corroboration of the brief's §22 peeking
torture test, from a vendor with production data. It also means the peeking
result is *known*, not a discovery waiting to be made.

Sources: <https://docs.statsig.com/experiments/types/aa-test>,
<https://www.statsig.com/blog/sequential-testing-on-statsig>

### Microsoft ExP — metric trustworthiness by simulated A/A (capability C+D)

Across roughly a dozen Microsoft products, **the typical product has 10–15% of
its metrics failing p-value uniformity under the null, with some products as
high as 30%.** The test used is Anderson–Darling on the p-value distribution
across many simulated A/A runs.

This is the strongest published evidence that the pain is real, and it is also
the strongest evidence that the *diagnosis* is a solved, published technique
rather than an invention.

Source: <https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/p-values-for-your-p-values-validating-metric-trustworthiness-by-simulated-a-a-tests/>

### Meta GeoLift — end-to-end geo methodology (capabilities B, E, F, G)

*Vendor-reported*: "an end-to-end solution to geo-experimentation which spans
data ingestion, power analyses, market selection, and inference." Includes
power calculators taking a dataset, a list of test locations and a **Cost Per
Incremental Conversion** to determine the investment needed for a well-powered
test, and **power simulation that tells you which markets to treat before any
money is spent**.

That is preflight, market selection and a cost input, already shipped and open
source. The Recast study's finding that GeoLift has a 91% false negative rate
under its baseline scenario is the thing to check, not its feature list.

Sources: <https://github.com/facebookincubator/GeoLift>,
<https://facebookincubator.github.io//GeoLift/docs/Methodology/>

### Google Meridian GeoX — design selection (capability G)

*Vendor-reported*: helps determine **which experiment design — holdback, go
dark, or heavy up — is best suited** to a business objective, uses time-based
regression plus stratified sampling as the measurement engine, supports native
multi-cell execution against a common control, and is positioned as
publisher-agnostic. Exited beta claiming **31% cheaper geo experiments**
(*vendor-reported*, unverified).

The official overview page is thin on method: it does not document pre-experiment
power/MDE, geo selection, multi-estimator comparison, experiment cost or a
do-not-run path. **Phase 2 must read the API reference, the user guide and the
repository before the grid row above is treated as settled.**

Sources: <https://developers.google.com/meridian/geox>,
<https://github.com/google/meridian-geox>,
<https://business.google.com/us/accelerate/announcements/meridian-geox-googles-new-open-source-geo-incrementality-solution/>

### Google Trimmed Match — design for small, heterogeneous geo sets

Addresses exactly the regime the brief cares about: few geos, heavy-tailed
response across geos due to geo heterogeneity, and response varying
dramatically over time. Combines optimal subset pairing, Trimmed Match iROAS
estimation and cross-validation. **Python**, open source — the "R is
inconvenient" objection does not apply to Google's geo stack at all.

Sources: <https://arxiv.org/pdf/2105.07060>,
<https://github.com/google/trimmed_match>, <https://github.com/google/matched_markets>

### Haus — pre-launch placebo testing (capability F, and this is our §28)

*Vendor-reported*: "A placebo test runs simulations on historical data from a
period before the actual campaign launched to see if the model falsely detects
effects. Since nothing has fundamentally changed, the lift should be zero; if
the tests register a lot of lift, they're false positives, **and that noise
level helps determine the holdout size for your real test**."

That is the brief's §28 geo placebo test, wired directly into design sizing,
already productised. Haus also states ≥80% power as a design target and uses
synthetic control rather than matched markets.

Sources: <https://www.haus.io/experiments>,
<https://www.haus.io/blog/incrementality-experiments-best-practices-and-mistakes-to-avoid>,
<https://www.haus.io/blog/matched-market-tests-dont-cut-it-why-haus-uses-synthetic-control-in-incrementality-experiments>

### Value of information — advice, not a feature

Google's own guidance tells marketers to "compare test costs with the value of
getting the budget decision right" and to test investments they are uncertain
about. Industry sources note single incrementality experiments historically
costing upward of $100,000.

But across every vendor checked so far, **VOI appears as prose guidance in a
blog post, never as a computed number in a product**. No tool found so far
takes spend, uncertainty and experiment cost and returns an expected value of
information, and none found so far will output DO NOT RUN.

Sources: <https://business.google.com/uk/think/measurement/marketing-experimentation-incrementality-testing/>,
<https://business.google.com/en-all/think/measurement/incrementality-testing/>

---

## 4. Where this leaves the hypothesis

The brief's working hypothesis was that a gap exists for "vendor-neutral
empirical preflight that compares several design/estimator families on a
business's historical data". After one pass of the landscape, that hypothesis
needs narrowing on three fronts and may not survive the rest of Phase 2:

1. **Multi-estimator comparison is published** (Recast, June 2026). Claiming
   it as differentiation would be false. What is *not* done is continuous
   regime mapping with sensitivity analysis, on real or semi-synthetic data,
   with a fitted selector scored by selection regret.
2. **Preflight on the customer's own data is productised** — by Statsig for
   user-level A/A, by Haus for geo placebo, by GeoLift for power and market
   selection. The remaining question is not "does preflight exist" but "does
   *cross-method* preflight change the decision often enough to pay for
   itself".
3. **Design selection is productised** by Meridian GeoX. What is unclaimed is
   choosing between *methodologies from different vendors*, which is precisely
   what no vendor is incentivised to build.

The two capability columns nobody occupies are **K (do-not-run)** and
**L (value of information)**. Those are also the two that require a business
cost model rather than a statistical one, which may be why. Whether they are
unoccupied because they are valuable and hard, or because they are worthless,
is a question the benchmark can actually answer — and the brief's K5 already
names the condition under which they die.

---

## 5. Still to verify before Phase 2 closes

- Meridian GeoX API reference and repo: power/MDE, geo selection, cost,
  multi-cell semantics, whether any do-not-run path exists.
- Eppo, GrowthBook, Optimizely, Amplitude Experiment, Spotify Confidence —
  none checked yet.
- tea-tasting, ABiasales, Ambrosia, ABacus — current versions and maintenance
  status (§72 currentness; the previous study found two dead uplift libraries
  this way).
- Measured and Rockerbox: whether "simulation-based MDE" is real or marketing
  language. Rockerbox's public pages describe consultative test design, not a
  simulation engine.
- Triple Whale, Recast as *products* (as distinct from Recast's study).
- Whether any academic or industry work already does algorithm selection for
  experiment design — the meta-learning framing may itself be prior art.
