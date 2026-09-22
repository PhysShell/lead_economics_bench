# leadbench — Lead Economics Benchmark

A falsification-oriented benchmark for one product hypothesis:

> Using marketing, CRM, funnel, acquisition-cost, realised-deal-value and
> limited sales-capacity data, can you make **economically better** allocation
> decisions than end-to-end analytics, historical ROI/ROAS, lead scoring,
> propensity models, uplift/causal models and contextual bandits?

This repository is built to **kill** that hypothesis, not to support it. If
logistic regression, XGBoost, a historical profit-per-agent-hour heuristic or a
bandit does as well for less complexity, that is a successful result and the
kill criteria in [`docs/benchmark-spec.md`](docs/benchmark-spec.md) say so in
advance.

**Read the findings in [`reports/latest/report.md`](reports/latest/report.md).**

---

## What it measures

Money, not accuracy. The primary metrics are net value per 1,000 leads, net
value per agent-hour, and regret against an Oracle that knows the true data
generating process. AUROC, Qini and AUUC are reported as secondary
diagnostics and are never used to declare a winner — a model can top the Qini
table and lose money, and here some do.

Three tracks are kept separate, because methods that solve different problems
do not belong on one leaderboard:

| Track | Decision | Scored against |
|---|---|---|
| **B. Individual decisioning** | which leads get scarce agent time | synthetic potential outcomes; OPE on real randomized experiments |
| **B-online** | sequential decisions with feedback | cumulative realised value |
| **C. Aggregate allocation (MMM)** | how to split a media budget | known response curves |

Measurement/attribution (Track A) is not given its own leaderboard; it appears
as the *baselines* Track B has to beat, which is the honest framing.

## Quick start

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[ml,bayes,mmm,dev]"

# CI-sized end-to-end run (~20 seconds)
PYTHONPATH=src .venv/bin/python scripts/run_benchmark.py --suite smoke

# tests, including the economic sign tests
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q

# the main lead track
PYTHONPATH=src .venv/bin/python scripts/run_benchmark.py --suite lead --seeds 8

# real randomized data (downloads ~300 MB for Criteo)
python scripts/download_datasets.py --all
PYTHONPATH=src .venv/bin/python scripts/run_benchmark.py --suite real

# build leaderboards, comparisons, kill-criteria table and figures
PYTHONPATH=src .venv/bin/python scripts/build_report.py
```

Suites: `smoke`, `lead`, `curves`, `ablation`, `bayes`, `online`, `real`,
`mmm`, `all`.

## What is in here

```
src/leadbench/
  synthetic/      lead-level DGP (20 regimes) + aggregate MMM DGP, known truth
  models/         baselines, lead scoring, Propensity-EV, funnel, S/T/X/DR,
                  causal forest, hierarchical Bayesian (PyMC), bandits
  policies/       EV, rank, risk-averse lower-bound, abstention
  optimization/   shared constrained allocator + exact MILP reference
  metrics/        economic, predictive, causal, uplift, uncertainty, OPE
  evaluation/     splits + leakage audits, runners, preregistration, aggregation
  data/           Hillstrom and Criteo-UPLIFT v2.1 loaders
docs/
  benchmark-spec.md     preregistered hypotheses, metrics, kill criteria
  data-contract.md      what a business must start collecting today
  methodology.md        design decisions, what broke, limitations
  product-rollout.md    shadow mode, pilot power analysis, MVP architecture
  research/             market, open-source and patent landscapes
scripts/
  run_benchmark.py      every suite behind one entrypoint
  build_report.py       leaderboards, comparisons, kill criteria, figures
  answer_research_questions.py   per-RQ verdicts under the preregistered rule
  run_meridian.py       Google Meridian, in an isolated Python 3.12 runtime
  run_pie_track.py      PyMC-Marketing PIE, campaign-level track
  finalize.sh           assemble reports/latest in one command
```

### Data quality checks you can point at a real CRM export

`leadbench.evaluation.diagnostics` runs the adversarial checks on any
dataframe, not just the synthetic regimes: Simpson's paradox (sign reversal
between marginal and within-segment treatment differences), target leakage,
future-dated columns used as features, positivity/overlap, and duplicate
entities. On this benchmark's own regimes they correctly flag 51% positivity
violations under the policy-feedback regime and 2.9% duplicate people in the
dirty-CRM regime, and stay quiet on clean randomized data.

## Design decisions that matter

- **Common random numbers.** One uniform draw per funnel stage per lead, so
  potential outcomes across actions are coherent and monotone. Regret measures
  policy quality, not simulation noise.
- **The Oracle is not clairvoyant.** It knows true probabilities and true
  *expected* value; it does not know the realised draws. It is the best policy
  measurable with respect to the lead — a reachable ceiling, not a fantasy.
- **Truth is quarantined.** `LeadDataset` keeps `observed` and `truth` in
  separate frames. Models receive only the declared feature columns of
  `observed`. The one class permitted to see truth subclasses
  `TruthAwareCandidate`, so the exception is greppable.
- **Capacity is enforced with *true* effort.** A policy plans with its own
  predicted handle times; the evaluator enforces the constraint with the real
  ones and truncates the call list. Under-predict handle time and your day
  ends before your list does — as it would in a real sales floor.
- **One optimiser for everybody**, including the Oracle, so differences reflect
  predictions rather than solvers. Checked against an exact MILP.
- **Identical base learners** across every family. No per-family tuning, no
  selection on test.
- **Preregistration.** The manifest — hypotheses, metrics, thresholds, kill
  criteria, seeds, splits — is hashed and written *before* any test metric
  exists. Mistakes get a new experiment id with a stated reason, not an edit.

## Datasets

| Dataset | Kind | n | Licence |
|---|---|---|---|
| Synthetic (20 regimes) | fully synthetic, known truth | configurable | this repo |
| MMM synthetic (6 regimes) | fully synthetic, known truth | 30–260 weeks | this repo |
| Hillstrom / MineThatData | **real randomized experiment** | 64,000 | publicly released by the author |
| Criteo-UPLIFT **v2.1** | **real randomized experiment** | 13,979,592 | **CC BY-NC-SA 4.0 — non-commercial** |

Neither real dataset is committed. `scripts/download_datasets.py` fetches them;
SHA256 digests are pinned and verified. The loader **refuses** Criteo v2.0,
which has a documented incrementality leak.

> The Criteo licence is non-commercial. That is a real constraint on a
> commercial product programme, not a formality — it can be used to evaluate
> methods, not to build a shipped model on.

## Reproducibility

Every run records experiment id, git commit and dirty flag, config hash,
dataset SHA256, seeds, library versions, hardware and timestamps into
`experiment-manifest.json`. Determinism is asserted by a test: the same seed
produces byte-identical data and identical benchmark rows.

## Licence

Apache-2.0 for the code. Dataset licences are the datasets' own; see above.
