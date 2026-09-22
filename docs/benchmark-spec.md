# Benchmark specification

This document is the preregistration. It states the hypotheses, the metrics,
the datasets, the splits, the decision rule and the kill criteria **before**
results are looked at. The machine-readable version is written by
`src/leadbench/evaluation/prereg.py` into every run's
`experiment-manifest.json` and hashed.

If something here turns out to be wrong, the correct response is a **new**
experiment id with a stated reason, not an edit to this file.

## 0. The claim under test

> Using marketing, CRM, funnel, acquisition-cost, realised-deal-value and
> limited sales-capacity data, can we make economically better allocation
> decisions than existing approaches — end-to-end analytics, historical
> ROI/ROAS, lead scoring, propensity modelling, uplift/causal models and
> contextual bandits?

The benchmark is built to **falsify** this. A result showing that logistic
regression, XGBoost, a historical-profit heuristic or a bandit does as well
for less complexity is a successful outcome, not a failure.

## 1. Three tracks, never merged

Per §2, methods that solve different problems do not share a leaderboard.

| Track | Decision | Ground truth | Primary metric |
|---|---|---|---|
| **A. Measurement** | none — it is a reporting layer | — | included only as *baselines* inside track B |
| **B. Individual decisioning** | which leads get scarce agent time | synthetic potential outcomes; OPE on real randomized data | net value per 1,000 leads; net value per agent-hour |
| **C. Aggregate allocation (MMM)** | how to split a media budget | known response curves | budget-allocation regret |
| **B-online** | sequential decisions with feedback | synthetic potential outcomes | cumulative net value |

## 2. Action space

Primary lead track is **binary**: `{none, call}`. That is the real product
question ("who gets scarce human sales time?"), it keeps every family directly
comparable, and it lets Qini/AUUC apply natively. A three-action variant
`{none, sms, call}` is supported by the code as a secondary track.

## 3. Economic formulation

**Once a lead is acquired, its CPL is sunk** and must not affect the next
action. For the lead track:

```
EV(a | x) = P(funded | x, a) · E[net contribution | x] − cost(a, x)
cost(a, x) = direct_cost(a) + predicted_minutes(a, x) · agent_cost_per_minute
```

Acquisition cost enters **only** in the acquisition/MMM track, where spend is
a decision variable. `realized_net_value(..., include_acquisition_cost=)`
makes the distinction explicit and is unit-tested.

Objective under constraint:

```
max_π  Σ_i V(x_i, π(x_i))    s.t.  Σ_i minutes(π(x_i), x_i) ≤ H
```

solved as a multiple-choice knapsack by **one shared allocator** used by every
candidate including the Oracle, so that differences reflect predictions rather
than optimisation.

### Capacity is enforced with *true* effort

A policy plans using its own predicted handle times. The evaluator then
enforces the constraint using the **true** minutes, dropping the
lowest-priority assignments until the plan fits. A model that under-predicts
handle time builds a call list it cannot finish — which is what happens in a
real sales floor when the day ends.

## 4. Research questions and how each is answered

| RQ | Question | Answered by |
|---|---|---|
| RQ1 | Does a decision model beat good end-to-end analytics? | lead track vs `hist_*` baselines, all regimes |
| RQ2 | Does propensity scoring match uplift? | `lead_score_*` vs causal family, esp. `propensity_not_uplift` |
| RQ3 | Does explicit economics beat a probability score? | `propensity_ev_*` vs `lead_score_*` |
| RQ4 | Does modelling capacity matter? | `hist_net_profit` vs `hist_profit_per_agent_hour`; EV-mode vs rank-mode ablation; capacity curves |
| RQ5 | Does Bayesian uncertainty add practical value? | `bayes_*` vs `*_bootstrap`; `ev` vs `ev_lcb10/25`; coverage metrics |
| RQ6 | Does hierarchical pooling help in small segments? | `bayes_hierarchical` vs `abl_bayes_no_hierarchy`, `sparse` regime |
| RQ7 | When do contextual bandits beat a static model? | online track: bandits vs frozen vs retrained |
| RQ8 | Can observational data answer causal questions at all? | `hidden_confounding`, `policy_feedback_loop`, positivity diagnostics |
| RQ9 | How much data does each approach need? | data-size curves, 2k → 100k |
| RQ10 | When is complexity not justified? | Pareto frontier of value vs compute; kill criteria below |

## 5. Datasets

### Synthetic (known truth)

Twenty regimes, all listed in `src/leadbench/synthetic/config.py`:
`easy_randomized`, `sparse`, `rare_outcome`, `very_rare_outcome`,
`strong_heterogeneity`, `propensity_not_uplift`, `agent_time_heterogeneity`,
`campaign_effort_heterogeneity`, `value_heterogeneity`,
`capacity_value_heterogeneity`, `delayed_censored`,
`seasonality_trend`, `concept_drift`, `observed_confounding`,
`hidden_confounding`, `selection_bias`, `policy_feedback_loop`, `noisy_crm`,
`misleading_attribution`, `negative_control_null_effect`.

`campaign_effort_heterogeneity` was added mid-project, after noticing that
handle time varied only at the lead level, which made a campaign-aggregated
"profit per agent-hour" baseline a monotone transform of "profit per lead" and
left RQ4 untestable at the analytics layer. It is reported as a separate
experiment id rather than folded into the original sweep.

Counterfactual coherence comes from **common random numbers**: one uniform
draw per funnel stage per lead, so a potential outcome under action `a` is
`1[u_stage < p_stage(a)]`.

### Real randomized experiments

| Dataset | n | Treatment | Outcomes | Licence |
|---|---|---|---|---|
| Hillstrom / MineThatData (2008) | 64,000 | Mens / Womens e-mail / none, randomized 1/3 each | visit, conversion, spend | publicly released by the author |
| Criteo-UPLIFT **v2.1** | 13,979,592 | randomized ad exposure, P(treat)≈0.85 | visit, conversion | **CC BY-NC-SA 4.0 — non-commercial only** |

Criteo v2.0 is explicitly refused by the loader: it has a documented leak from
non-uniform incrementality across advertisers. The loader checks the row count
and raises.

Neither dataset is committed. `scripts/download_datasets.py` fetches them and
SHA256 digests are pinned in `src/leadbench/data/real.py`.

**Economics on the real track.** These datasets carry no agent time and no
margin, so the constraint is a **send budget** (treat the top `k` share) and
the value per outcome and cost per treatment are preregistered constants.
Under a fixed budget every policy treats exactly the same *number* of users,
so total treatment cost is identical across candidates and the comparison is
driven entirely by **incremental outcomes**; the value/cost constants rescale
the reported level but cannot change the ranking. This track therefore tests
targeting quality, not the full economic problem.

### MMM

Six regimes over an aggregate DGP with geometric adstock, exponential
saturation, seasonality, trend, controls, correlated spend and **biased
last-touch reporting**: `mmm_standard` (156 weeks), `mmm_smb_short_history`
(52), `mmm_very_short_history` (30), `mmm_high_collinearity`, `mmm_low_signal`,
`mmm_long_history` (260).

## 6. Splits

- **Temporal**, never random: train on the past, test on the future.
- Leads whose outcome has not resolved by the cut-off stay in training with a
  blanked outcome, because that is the situation a deployment is in.
- Entities (`person_id`) appearing on both sides are **dropped from test**,
  then asserted to be zero.
- Automated checks: forbidden-feature leakage, temporal ordering, entity
  overlap. All raise `LeakageError`.
- Real data has no time dimension, so it uses a seeded permutation split;
  the seed is in the manifest.

## 7. Metrics

**Primary (decision/economic):** net value per 1,000 leads; net value per
agent-hour; incremental net value vs do-nothing; incremental conversions; cost
per incremental conversion; policy regret vs Oracle; % of Oracle's achievable
gain; resource utilisation.

**Secondary (predictive):** log loss, Brier, AUROC, AUPRC, **expected
calibration error**, calibration slope. Calibration is the one that matters,
because an EV policy multiplies a probability by dollars.

**Uplift (secondary, never decisive):** Qini AUC, AUUC, uplift@k. A ranking is
not a decision; it is blind to deal value, agent minutes and action cost.

**Causal error (synthetic only):** PEHE, ATE error, Spearman correlation with
true CATE. On real data ITE is unobservable and no ground truth is simulated.

**Uncertainty:** 80% interval coverage and width, for EV **and separately for
the outcome probability**, so a badly covered EV interval can be attributed
either to the posterior or to the point-estimated nuisance models feeding it.

**Cost:** fit seconds, predict seconds, peak RSS delta.

## 8. Fairness rules

- Identical datasets, splits, features, constraints, cost model.
- **Identical base learners.** Every gradient-boosted model in every family
  uses `n_estimators=400, max_depth=5, learning_rate=0.05,
  min_child_weight=5`. No per-family tuning; no selection on test.
- Shared nuisance components: one `ValueModel` and one `EffortModel` class,
  so a family cannot win by having a better margin regression.
- Shared allocator.
- Where a method needs a different information set (e.g. bandits get online
  feedback), it is stated explicitly and the comparison is structured around it.

## 9. Statistical decision rule — fixed in advance

A candidate beats a reference only if **both** hold:

1. the **paired** difference (same seeds, same populations) in the primary
   metric has a 95% bootstrap interval excluding zero; **and**
2. the point estimate exceeds the practical threshold below.

Otherwise the verdict is *"no meaningful evidence of difference"*, which is
reported as a result.

### Practical significance threshold

**2% of the reference's net value per 1,000 leads.**

Rationale: a decision system carries integration, monitoring and model-risk
costs. Below roughly 2% uplift, a realistic business would not notice the gain
against month-to-month variance in lead quality, and would be better served by
spending the same effort on speed-to-lead or offer quality. The number is a
judgement call, stated in advance, and every table reports the raw difference
and interval so a reader can apply their own threshold.

## 10. Kill criteria — agreed before seeing results

| # | Criterion | Trigger | Consequence |
|---|---|---|---|
| K1 | **Kill Bayesian complexity** | Bayesian candidates within 2% of the best non-Bayesian candidate while costing >10× compute | Ship the simple model |
| K2 | **Kill uplift** | Causal candidates fail to beat `propensity_ev_gbm` by >2% on randomized data | Do not ship causal inference on theory alone |
| K3 | **Kill lead-level decisioning** | `hist_profit_per_agent_hour` reaches ≥80% of the Oracle's achievable gain in realistic regimes | The bottleneck is not lead selection |
| K4 | **Kill MMM for SMB** | MMM budget-allocation regret >10% at SMB data sizes | Do not sell MMM as a day-one feature |
| K5 | **Kill the whole product hypothesis** | The best analytics baseline is within 2% of the best model across realistic regimes | Stop; recommend the analytics layer |

## 11. Success criterion

The project is interesting **not** when a Bayesian model wins, but when a
reproducible, economically meaningful region exists — e.g. *limited sales
capacity + heterogeneous deal value + heterogeneous treatment response +
N above some threshold* — where a decision model beats a realistic baseline by
more than the practical threshold, with an interval excluding zero.

## 12. Abstention

Candidates may decline to decide. `AbstentionPolicy` restricts action to the
most confident share of leads; profit-versus-coverage is reported. A system
that says INSUFFICIENT EVIDENCE where support is missing is more valuable than
one that always answers, and `hidden_confounding` / `policy_feedback_loop`
exist to find where that line is.

## 13. Reproducibility

Every run records: experiment id, git commit + dirty flag, config hash,
dataset SHA256, seeds, library versions, hardware, timestamps. One command:

```
python scripts/run_benchmark.py --suite smoke    # CI
python scripts/run_benchmark.py --suite lead     # main track
python scripts/run_benchmark.py --suite all      # everything
```
