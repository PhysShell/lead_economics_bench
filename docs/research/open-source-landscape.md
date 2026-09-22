# Open-source landscape

Scope: libraries that could plausibly be dependencies of a lead-economics /
revenue-allocation product, assessed on maintenance rather than popularity.

**Method.** Versions and release dates are read from the PyPI JSON API
(`https://pypi.org/pypi/<package>/json`) on **2026-09-22**, which is the
authoritative record of what you can actually `pip install` today — not from
blog posts or README badges. CRAN and GitHub are used where a project is not
on PyPI. Everything in the "released" column is the upload date of the current
latest version.

## What is installed and used in this benchmark

These are the versions the reported results were produced with. The full,
machine-readable list (including transitive pins) is in every run's
`experiment-manifest.json` under `libraries`.

| Package | Version used | Latest on PyPI (2026-09-22) | Released | Licence | Role here |
|---|---|---|---|---|---|
| numpy | 2.4.6 | 2.4.6 | — | BSD | core |
| pandas | 3.0.6 | 3.0.6 | — | BSD | core |
| scikit-learn | 1.9.1 | 1.9.1 | 2026-09-10 | BSD | baselines, calibration, nuisance models |
| xgboost | 3.2.0 | 3.4.1 | 2026-08-15 | Apache-2.0 | primary gradient booster |
| lightgbm | 4.7.0 | 4.7.0 | 2026-07-18 | MIT | propensity model in the real-data track |
| econml | 0.17.0 | 0.17.0 | 2026-07-31 | MIT | S/T/X/DR learners, CausalForestDML |
| scikit-uplift | 0.5.1 | 0.5.1 | **2022-08-11** | MIT | `ClassTransformation`, Qini/AUUC metrics |
| vowpalwabbit | 9.11.2 | 9.11.2 | 2026-03-07 | BSD-3 | installed; see note below |
| pymc | 5.28.5 | **6.3.2** | 2026-09-08 | Apache-2.0 | hierarchical Bayesian funnel |
| pytensor | 2.38.3 | — | — | BSD-3 | PyMC backend |
| arviz | 0.23.4 | 1.3.0 | 2026-08-11 | Apache-2.0 | posterior handling |
| pymc-marketing | 0.19.2 | **1.1.0** | 2026-08-27 | Apache-2.0 | Bayesian MMM candidate |
| pulp | 3.3.2 | — | — | MIT | exact MILP reference for the allocator |
| statsmodels | 0.15.0 | — | — | BSD-3 | diagnostics |

### Why the PyMC stack is not on the newest version

The container ships **Python 3.11.15**. `pymc-marketing==1.1.0` declares
`Requires-Python >=3.12`, so the resolver correctly selected 0.19.2, the newest
release that supports 3.11. Verified directly:

```
× No solution found when resolving dependencies:
  ╰─▶ Because the current Python version (3.11.15) does not satisfy
      Python>=3.12 and pymc-marketing==1.1.0 depends on Python>=3.12 ...
```

To confirm this is a runtime constraint and not a broken pin, a separate
Python 3.12 environment was provisioned in which `pymc 6.2.0` +
`pymc-marketing 1.1.0` install cleanly. The MMM results in this report were
produced on 0.19.2; the 1.x API differs enough that porting is a follow-up,
and it is recorded as a known limitation rather than glossed over.

## PyMC-Marketing PIE — assessed separately (brief §17)

**PIE = "Predicted Incrementality by Experimentation".** It is *not* lead
scoring, and describing it as such would be a category error.

What it actually does, from the module's own docstring and signature: fit a
**BART** model on the corpus of campaigns that **did** run an incrementality
experiment (geo test, ghost-ad holdout), learning the map from campaign
features to **measured incrementality**, then predict a full incrementality
posterior for campaigns that never ran a test.

```python
model = PIEModel(
    pre_determined_features=["objective", "vertical", "budget"],
    post_determined_features=["exposure_rate"],
)
model.fit(X, y, random_seed=42)   # y = measured incrementality from past RCTs
predictions = model.predict(X_new)
```

| Question | Answer |
|---|---|
| Unit of analysis | **campaign**, not lead |
| Training label | an **experimental readout** (measured incrementality) |
| Requires RCTs? | **Yes — it cannot exist without a corpus of past experiments** |
| Uncertainty | full BART posterior over predicted incrementality |
| vs per-lead uplift | completely different estimand: transfer/meta-learning of *campaign-level* incrementality, not heterogeneous treatment effects across individuals |
| Benchmarkable as lead scoring? | **No.** It gets its own campaign-level track. |

**Status verified 2026-09-22.** The module's own documentation states the API
is alpha: *"the API and defaults may change between releases."* Two concrete
facts found by trying to run it:

1. `pymc_marketing.pie` **does not exist in 0.19.2** (the newest release that
   supports Python 3.11). It appears only in the 1.x line, which needs
   Python ≥3.12.
2. **PIE 1.1.0 is broken against the current `pymc-bart` (0.13.1).** It imports
   `from pymc_bart.split_rules import ContinuousSplitRule, OneHotSplitRule`,
   and `pymc_bart.split_rules` was removed in 0.13 when pymc-bart moved to the
   Rust `bartrs` backend. The import sits inside a `try/except ImportError`
   that sets `pmb = None`, so the failure surfaces much later as a misleading
   *"pymc-bart is required for PIEModel. Install it with:
   `pip install 'pymc-marketing[pie]'`"* — even when pymc-bart is installed and
   imports fine.
   **Working pin: `pymc-bart==0.12.0`.**

This is exactly the "alpha, re-verify before relying on it" case the brief
anticipated. It is usable today with a pinned dependency, and it should not be
a load-bearing production dependency yet.

A campaign-level benchmark for PIE's *own* claim is implemented in
`scripts/run_pie_track.py`; results are in the final report.

## Maintenance assessment

The single most decision-relevant column is "last release", because a causal
inference library that has not shipped in four years is a liability in a
product, whatever its citation count.

| Project | Latest | Released | Verdict |
|---|---|---|---|
| **EconML** (py-why) | 0.17.0 | 2026-07-31 | **Healthy.** Actively released, broad estimator coverage, the reference implementation for DR-learner and causal forests in Python. Safe dependency. |
| **PyMC** | 6.3.2 | 2026-09-08 | **Healthy.** Frequent releases. Note the 5.x → 6.x major bump; pin deliberately. |
| **PyMC-Marketing** | 1.1.0 | 2026-08-27 | **Healthy but fast-moving.** Reached 1.0 recently; API churn between 0.19 and 1.1 is real. Requires Python ≥3.12. |
| **CausalML** (Uber) | 0.17.0 | 2026-07-04 | **Healthy.** Overlaps EconML heavily; needs a C/Cython build. |
| **DoWhy** (py-why) | 0.14 | 2025-11-08 | **Moderate.** ~10 months since release. Useful for refutation tests rather than estimation. |
| **CausalPy** (PyMC Labs) | 0.9.0 | 2026-07-28 | **Healthy.** Quasi-experimental designs (geo lift, synthetic control) — relevant to the incrementality-calibration question. |
| **scikit-uplift** | 0.5.1 | **2022-08-11** | **Effectively unmaintained** (4 years). Used here only for `ClassTransformation` and the Qini/AUUC metrics, both stable and small. **Do not build a product on it.** |
| **upliftml** (Booking.com) | 0.0.2 | **2022-11-22** | **Abandoned.** Never left 0.0.x. Excluded. |
| **Open Bandit Pipeline (`obp`)** | 0.5.7 | **2023-04-14** | **Stale** (3.5 years). It is the best-known OPE library, but this benchmark implements IPS/SNIPS/DR directly (≈150 lines, fully tested) rather than take a stale dependency. |
| **Vowpal Wabbit** | 9.11.2 | 2026-03-07 | **Maintained but niche.** See note below. |
| **Google Meridian** | 2.0.0 | 2026-09-03 | **Healthy, vendor-backed.** Geo-level Bayesian MMM. Heavy (TensorFlow Probability). |
| **Meta Robyn** | CRAN 3.12.1 (2025-07-02) | — | **R-only in practice; direction unclear.** The Python port is described by the project as an LLM-translated beta that "might encounter bugs". Trade press reports Meta de-prioritising it. Not benchmarked — see below. |
| **CausalTune** | 0.3.0 | 2026-07-19 | Small. AutoML over EconML estimators. Not used. |

## Candidates considered and deliberately not benchmarked

Per §87, the blocker is named rather than deferred to "future work".

- **Meta Robyn.** R package. The official Python distribution is a
  self-described LLM-translated beta. Benchmarking a beta translation would
  measure the translation, not the method. Running the R original would need a
  second language runtime inside the harness for one candidate; the
  `ridge_adstock_saturation` candidate in this repo occupies the same
  methodological slot (grid-searched adstock/saturation + regularised
  regression with non-negativity), so the comparison is not lost.
- **Google Meridian.** Installation into an isolated Python 3.12 environment
  was attempted; see `docs/methodology.md` for the outcome. Meridian's own
  documentation is used as a *data-requirements* source regardless, and that
  turns out to be the more important contribution to the MMM conclusion than
  its score would have been.
- **Vowpal Wabbit.** Installed and importable. The online track needs
  per-arm posterior/confidence state that is inspectable so that LinUCB,
  Thompson sampling and a no-exploration control differ *only* in the
  exploration rule. VW's contextual-bandit reductions bundle exploration with
  its own cost-sensitive learner, which would confound the exploration
  comparison with a learner change. The bandits here are therefore explicit
  linear models (~120 lines, tested), and VW is left as an implementation
  option rather than a benchmark entrant.
- **CausalML.** Requires a compiled build and duplicates EconML's estimator
  coverage for the estimators this benchmark needs. Keeping one causal library
  keeps base learners identical across families, which matters more for
  fairness than having two.

## Practical recommendation

For a product in this space, the defensible dependency set today is:

1. **scikit-learn + XGBoost/LightGBM** for outcome, value and effort models.
2. **EconML** for causal estimation, if causal estimation earns its place
   (see the benchmark results — it does not, everywhere).
3. **PyMC** only where partial pooling or posterior decision-making is doing
   real work, pinned, and on Python ≥3.12 if PyMC-Marketing is wanted.
4. **Own code** for OPE and for bandits. Both are small, both are the parts
   you most need to be able to debug and test, and the available libraries are
   stale.

Avoid taking scikit-uplift, upliftml or `obp` as load-bearing dependencies.

## Sources

- PyPI JSON API, `https://pypi.org/pypi/<package>/json`, accessed 2026-09-22.
- CRAN, *Robyn: Semi-Automated Marketing Mix Modeling (MMM) from Meta
  Marketing Science*, https://cran.r-project.org/package=Robyn, accessed
  2026-09-22.
- Meta, Robyn project site and repository,
  https://github.com/facebookexperimental/Robyn, accessed 2026-09-22.
- Google, *Meridian* developer documentation, https://developers.google.com/meridian,
  accessed 2026-09-22.
- AdExchanger, "Google's Meridian And Meta's Robyn: A Gift To Measurement Or
  Trojan Horses?", https://www.adexchanger.com/marketers/googles-meridian-and-metas-robyn-a-gift-to-measurement-or-trojan-horses/
  — trade reporting, cited as *press-reported*, not as established fact.
