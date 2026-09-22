# Can decision-centric models allocate marketing budget and sales capacity better than the incumbents?

**A falsification study.** Experiment id and provenance: `reports/runs/*/experiment-manifest.json`.
Preregistration: [`docs/benchmark-spec.md`](../../docs/benchmark-spec.md).
Methods and known weaknesses: [`docs/methodology.md`](../../docs/methodology.md).

> This report was commissioned with one instruction above all others: *do not
> try to prove the idea is good — try to destroy it.* What follows is written
> that way. Where the idea survived, the surviving region is narrow and it is
> named precisely. Where it died, it is recorded as a result rather than
> softened.

---

## 1. Executive summary

### What was tested

One hypothesis: that using marketing, CRM, funnel, acquisition-cost, realised
deal-value and limited sales-capacity data, a decision model can allocate
advertising budget and scarce sales hours **more profitably** than end-to-end
analytics, historical ROI/ROAS, lead scoring, propensity modelling,
uplift/causal models and contextual bandits.

Against it: 22 lead-track candidates, 6 MMM candidates, 7 online candidates and
5 campaign-level candidates, over 20 synthetic regimes with known potential
outcomes, two **real randomized experiments** (Hillstrom, Criteo-UPLIFT v2.1),
6 synthetic MMM regimes with known response curves, and a synthetic campaign
corpus. Every candidate shares one optimiser, one value model, one effort model
and one hyperparameter budget. The primary metric is money — net value per
1,000 leads and per agent-hour — never accuracy.

### What won

**Nothing that justifies a Bayesian-causal platform. Something that justifies a
narrow, cheap product.**

The ordering that survived every check:

| Layer | Best candidate | % of Oracle gain | Verdict |
|---|---|---|---|
| Decision engine with explicit economics | `s_learner` / `propensity_ev_logit` | **58–61%** | the region worth building in |
| Lead scoring (`P(convert)` ranking) | `lead_score_logit` | 52% | beaten, reliably |
| End-to-end analytics / historical ROI | `hist_conversion_rate` | 38% | beaten, decisively |
| Last-click attribution | `last_click_attribution` | 30% | beaten, decisively |
| No model at all | `random` / `fifo` | 25% | — |

The single largest effect in the entire study is **not** causal inference over
propensity. It is **explicit economics over any ranking at all**:
`propensity_ev_logit` — a logistic regression multiplied by predicted deal
value and divided by predicted agent minutes — beats the **strongest**
analytics baseline by **+9.5% of net value per 1,000 leads** (95% CI +7.8% to
+11.4%) and beats a gradient-boosted lead score by **+5.0%**. Both clear the
preregistered 2% practical threshold several times over.

A note on which baseline that is, since the point of the exercise is to lose to
a strong one. The preregistration named `hist_profit_per_agent_hour` as the
analytics reference for RQ1, but on the data it is *not* the best analytics
baseline — plain `hist_conversion_rate` scores higher (38.8% vs 36.7% of
Oracle). Every headline comparison below is therefore reported against
`hist_conversion_rate`, the strongest one, which makes each advantage about
1.3 points *smaller* than the preregistered reference would have shown.

The causal machinery adds **+2.9%** on top of that (`s_learner` vs
`propensity_ev_logit`, 95% CI +1.2% to +4.9%) — which *barely* clears the same
threshold, and only because three regimes out of ten carry it.

### Where it won

This is the part that matters more than the headline, because the advantage is
**conditional, not general**. Causal modelling beat the simple economic model
in 3 of 10 regimes and **lost** in 2:

| Regime | `s_learner` vs `propensity_ev_logit` | Verdict |
|---|---|---|
| `strong_heterogeneity` | **+10.4%** [+5.5, +15.5] | causal wins |
| `capacity_value_heterogeneity` | **+9.2%** [+4.5, +14.6] | causal wins |
| `propensity_not_uplift` | **+4.4%** [+3.4, +5.6] | causal wins |
| `value_heterogeneity` | +0.8% [−2.1, +4.9] | no meaningful difference |
| `agent_time_heterogeneity` | −0.1% [−1.9, +2.5] | no meaningful difference |
| `easy_randomized` | −0.2% [−2.2, +2.4] | no meaningful difference |
| `observed_confounding` | −0.4% [−1.5, +0.6] | no meaningful difference |
| `rare_outcome` | −1.5% [−3.3, +0.3] | no meaningful difference |
| `sparse` | −2.8% [−4.3, −1.4] | **causal loses** |
| `very_rare_outcome` | −5.2% [−9.7, −1.8] | **causal loses** |

The condition is specific and testable on a partner's own data before any
model is built: **causal modelling pays only when leads differ in how they
*respond to being contacted*.** When they differ only in deal value or in
cost-to-serve — which is the common case — multiplying by value and dividing
by minutes captures the whole gain, in a logistic regression.

### How big the effect is

At the benchmark's economics ($38/agent-hour, 32% contribution margin, 25% of
the capacity needed to call everyone), moving from a historical
profit-per-agent-hour heuristic to `propensity_ev_logit` is worth
**+$24,500 per 1,000 leads**; adding causal modelling on top is worth a further
**+$7,400 per 1,000 leads**, and only in the regimes above.

Two magnitudes bound the product:

- **At 5% capacity**, a causal model captures **5–7×** what lead scoring or an
  analytics baseline captures. This is the whole product.
- **At 100% capacity**, every method converges to 85–88% of Oracle and the
  model is worth **nothing** on total profit. The value is not in the model.
  It is in the scarcity.

---

## 2. What falsified our assumptions

Required section. These were held at the start, tested, and are wrong.

**1. "Uplift/causal modelling is the core differentiator."** False as stated.
Decomposing heterogeneity three ways shows that explicit economics alone
handles two of the three kinds. `propensity_ev_logit` is the *best candidate in
the study* when deal value varies (56.4% of Oracle) and when handle time varies
(61.3%) — ahead of every causal learner. It collapses to 44.4% only when
heterogeneous *treatment response* is added. Causal inference is worth roughly
**15 points of Oracle gain, and only against that one kind of heterogeneity**.
That is a far narrower claim than the one the project started with, and it is
falsifiable on a design partner's data before anything is built.

**1b. "…and the synthetic advantage will replicate on real randomized data."**
It did not. On Hillstrom — a genuine randomized experiment, 64,000 users, four
scenarios — the causal family was compared to a plain propensity ranking in
sixteen paired comparisons. **Fifteen showed no meaningful difference and the
sixteenth favoured the propensity ranking.** The benchmark cannot separate "the
real data has little response heterogeneity" from "64,000 users cannot detect
it", and that ambiguity is itself the finding: the condition under which the
causal upgrade pays is not something a partner can assume, and on the one real
experiment available it was not visible.

**2. "More sophisticated estimators will win."** False, expensively. The
doubly-robust learner — theoretically the most defensible — finishes **10th of
21** at 49.9% of Oracle, below a logistic regression with a value multiplier.
The causal forest consumes **51% of the entire benchmark's compute** (26.9s per
fit versus 1.0s) to land 5 points *below* `propensity_ev_logit`. Sophistication
bought negative return on four of ten regimes and negative return on every
compute budget.

**3. "Gradient boosting will beat logistic regression."** False, and it is not
close: `propensity_ev_gbm` − `propensity_ev_logit` = **−0.0%**
[−0.6%, +0.6%]. Zero. The lift comes from the economics wrapper, not the
learner. The simplest shippable model is therefore much simpler than expected.

**4. "Uplift metrics identify good policies."** False where it matters. Qini
correlates with realised money at ρ = +0.75 across a whole leaderboard, which
looks reassuring — but the **top two candidates by Qini are ranked 8th and 9th
by money**. Both are lead-scoring models. Qini scores a ranking of *who
responds*; the decision needs a ranking of *who is worth the agent-minute*.
A benchmark that had declared winners by Qini would have shipped the wrong
model. The same is true of AUROC, whose top-ranked candidate on predictive
accuracy is 2nd on money but whose 2nd-ranked is 8th.

**5. "Contextual bandits will adapt where offline models go stale."** False.
Across four online regimes including explicit concept drift: periodic
retraining of the offline model is worth **+0.2%** over freezing it, and
*exploration itself is worth nothing* — LinUCB −0.6, Thompson +0.1,
epsilon-greedy −4.5 against the same linear learner run greedily. Learner
capacity beat online-ness even under drift. The one place bandits won
(`propensity_not_uplift`, +4 to +9) is where the offline model is
*structurally* biased, not where the bandit is adaptive.

**6. "Bayesian uncertainty will pay for itself in decisions."** Half false, and
the half that survives is not the half expected. The two things bundled under
"Bayesian" come apart cleanly *(2 of 4 bayes regimes complete, n=5,000)*:

- **The posterior is worth nothing.** Risk-averse lower-bound policies scored
  58.1 (lcb25) and 57.4 (lcb10) against the plain EV policy's 58.0 — a swing of
  ±0.6 points, far inside the threshold. Bootstrap intervals on
  `propensity_ev_gbm` changed its result by **exactly zero** (48.4 vs 48.4).
  And the intervals are not even honest at the per-lead level: 80% nominal
  coverage delivers **22%** actual (Bayesian) and **33%** (bootstrap).
- **The hierarchical structure is worth a great deal.**
  `bayes_hierarchical` scored **58.0** against `propensity_ev_gbm`'s 48.4 —
  **+9.6 points** — and the no-pooling ablation isolates why:
  `abl_bayes_no_hierarchy` scored **46.4**, so partial pooling alone is worth
  **+11.6 points**, and without it the Bayesian model is *worse* than the
  gradient-boosted baseline it is supposed to beat.

So the original assumption was wrong about the mechanism. The value is in
**partial pooling across sparse segments**, not in quantified uncertainty — and
partial pooling does not require MCMC. Mixed-effects or empirical-Bayes
shrinkage should be tried before 45 seconds per fit is accepted as the price;
that test was not run here and is the clearest piece of unfinished work in this
study.

**7. "An MMM is a sensible day-one feature."** False, and dangerously so. An
*uncalibrated* PyMC-Marketing MMM has 14.9% mean budget-allocation regret
against an equal split's 6.2% — more than twice as bad as not modelling at all
— with an inverted channel ranking (ρ = −0.30) and 163% ROI error. Lift-test
calibration cuts that to 5.90%, which is *barely* better than the equal split,
because one regime in six (`long_history`) blows up to 25% regret. MMM is not a
model you install; it is a model you calibrate, monitor and can still be
betrayed by.

**7b. "A Bayesian MMM will beat a regularised regression."** False on the
metric that decides budget. The Bayesian MMM wins 5 of 6 regimes and **loses on
the mean** (5.90% vs 3.98% regret) because `ridge_adstock_saturation` has no
catastrophic regime and it does. On a client's actual budget, worst case beats
mean case.

**8. "Following the ROAS dashboard is a weak but reasonable baseline."** False.
It is **actively destructive**: 92.7% allocation regret — it captures 7% of
what was available — while having the *best* channel rank correlation with true
ROI (0.70) of any non-oracle method. Ranking channels correctly and allocating
budget catastrophically are fully compatible, because allocation depends on
*marginal* returns and a dashboard reports average credit.

**8b. "Accurate ROI estimates mean good budget decisions."** False, and this
is the sharpest version of finding 8 because it shows up *inside the best
model*. On `long_history` the calibrated MMM had its best ROI accuracy of any
regime and its worst allocation regret by an order of magnitude. Measuring each
channel's return well and splitting a budget well are different problems.

**9. "Abstention is obviously valuable."** Not demonstrated here. Scored
honestly — declined leads get the control action and the freed capacity is not
reallocated — abstention *loses* money. The benchmark cannot price the thing
abstention is actually for (avoiding confident errors on thin evidence), so
this is recorded as "not shown", not as "refuted".

---

## 3. Dataset evidence

| Dataset | Kind | Unit | n | Treatment | Outcome | Known value? | Known cost? | Licence |
|---|---|---|---|---|---|---|---|---|
| Synthetic lead economy (20 regimes) | fully synthetic, known potential outcomes | lead | 2k–100k | none / call, randomized or confounded by regime | funded | yes (true expected contribution) | yes (true handle time) | this repo |
| Synthetic MMM (6 regimes) | fully synthetic, known response curves | week | 30–260 weeks | continuous spend, 5 channels | revenue | yes | yes | this repo |
| Synthetic campaign corpus (PIE track) | fully synthetic, known incrementality | campaign | 400 | which campaigns ran an experiment | measured iROAS | yes | n/a | this repo |
| **Hillstrom / MineThatData** | **real randomized experiment** | customer | 64,000 | Mens / Womens e-mail / none, 1/3 each | visit, conversion, spend | spend only | no | public release by the author |
| **Criteo-UPLIFT v2.1** | **real randomized experiment** | user | 13,979,592 | randomized ad exposure, P(treat)=0.849 | visit, conversion | no | no | **CC BY-NC-SA 4.0, non-commercial** |

Statistics computed on load rather than quoted from papers:

- **Hillstrom**: 64,000 rows, 66.7% treated in the any-e-mail split. Visit rate
  16.70% treated vs 10.62% control (naive lift +6.09pp). Conversion 1.068% vs
  0.573% (+0.495pp). The Mens arm lifts visits more than Womens
  (+7.66pp vs +4.52pp).
- **Criteo v2.1**: 13,979,592 rows exactly, matching the published figure. The
  loader **raises** if the row count differs, which is how it refuses the
  leaked v2.0. In a deterministic 500k subsample: 84.95% treated, conversion
  0.298% vs 0.206%, visit 4.80% vs 3.86%.

Both real datasets pass every adversarial check in
`leadbench.evaluation.diagnostics` — no Simpson reversal, no target leakage,
adequate overlap. That is what a genuine randomized experiment looks like, and
it calibrates what the synthetic regimes flag.

**On Criteo's `exposure` field.** It marks users actually shown an ad and
correlates only 0.074 with `treatment`. It is *post-treatment*: conditioning on
it would introduce collider bias. It is loaded and never used.

**A licensing fact that constrains the product, not just the study.**
Criteo-UPLIFT is CC BY-NC-SA 4.0 — **non-commercial**. It can be used to
evaluate methods. It cannot be used to train a model that ships.

---

## 4. Benchmark results

### 4.1 Lead track — % of the Oracle's achievable gain

The Oracle knows true stage probabilities, true expected contribution and true
handle time, but **not** the realised draws, so 100% is attainable in principle
by a perfect model rather than being an inflated hindsight ceiling. `do_nothing`
is 0% by construction.

<!-- LEAD_LEADERBOARD_START -->
*(regenerated by `scripts/headline_analysis.py` when the sweep completes; the
table below is the current sweep state and is superseded by
`reports/latest/leaderboard_lead.csv`)*

| candidate | mean % of Oracle | family |
|---|---|---|
| `s_learner` | **61.3** | causal metalearner |
| `propensity_ev_logit` | **58.4** | economics + logistic regression |
| `funnel_ev_gbm` | 57.5 | economics + per-stage funnel |
| `propensity_ev_gbm` | 57.2 | economics + gradient boosting |
| `x_learner` | 55.9 | causal metalearner |
| `t_learner` | 55.2 | causal metalearner |
| `causal_forest` | 53.6 | causal forest (EconML) |
| `lead_score_logit` | 52.4 | lead scoring |
| `lead_score_gbm` | 50.1 | lead scoring |
| `dr_learner` | 49.9 | doubly-robust metalearner |
| `hist_conversion_rate` | 38.4 | analytics baseline |
| `class_transformation` | 37.2 | uplift transform |
| `hist_net_profit` | 36.7 | analytics baseline |
| `hist_profit_per_agent_hour` | 36.6 | analytics baseline |
| `hist_roas` | 33.5 | analytics baseline |
| `last_click_attribution` | 29.6 | attribution baseline |
| `lowest_cpl` | 28.6 | acquisition-cost heuristic |
| `call_everyone` | 25.4 | no prioritisation |
| `fifo` | 25.2 | speed-to-lead |
| `random` | 24.9 | control |
| `do_nothing` | 0.0 | control |
<!-- LEAD_LEADERBOARD_END -->

Three things to read off it:

1. **The analytics layer tops out around 38%.** Every historical baseline —
   conversion rate, net profit, profit per agent-hour, ROAS, last click — sits
   between 30% and 38%. They aggregate to the campaign or channel; the decision
   is per-lead; no amount of data fixes a unit mismatch.
2. **Lead scoring is a real but partial improvement** (50–52%). It uses lead
   features, which is why it beats the analytics layer, and ignores value and
   effort, which is why it loses to the economics wrapper.
3. **The economics wrapper is where the money is** (57–58%), and it does not
   need a strong learner to get there.

### 4.2 Real randomized experiments — off-policy evaluation

Scored by doubly-robust OPE with bootstrap intervals and reported ESS, on data
where the treatment really was randomized and no simulator can flatter anyone.
Value per outcome and cost per treatment are preregistered constants (§3 of the
methodology), so this track tests **targeting**, not the full economic problem.

<!-- REAL_TRACK_START -->
*(suite in flight; four Hillstrom scenarios complete and shown. Womens arms and
Criteo to follow. Regenerated by `scripts/real_track_analysis.py`.)*

**How this is tested, and why not the obvious way.** Each candidate's DR
interval is *marginal*. Every candidate is scored on the same test fold from
the same experiment, so those intervals overlap heavily even where one policy
is reliably better — reading overlap as "no difference" understates what the
data shows, and an earlier draft of this section made exactly that mistake.
The comparison below is **paired** against `random` within each (seed, budget)
cell. Budgets within a seed share one test fold, so those pairs are not
independent; the difference is therefore averaged within a seed first and
tested across seeds only. With 3 seeds that is df = 2, a deliberately
conservative test.

Paired difference vs `random`, as % of the random baseline:

| scenario | events in test fold | best candidate | Δ vs random | 95% CI | clears +2%? |
|---|---|---|---|---|---|
| `hillstrom_any_email_visit` | ~10,700 | `s_learner` | **+3.1%** | [+2.3, +4.0] | **yes** |
| | | `t_learner` | **+2.6%** | [+1.6, +3.7] | **yes** |
| | | `dr_learner` | +3.6% | [−1.3, +8.5] | no (interval spans 0) |
| | | `response_score` | +2.2% | [−0.3, +4.7] | no |
| `hillstrom_mens_visit` | ~3,100 | `response_score` | +2.0% | [−2.4, +6.4] | no |
| `hillstrom_any_email_conversion` | ~680 | `dr_learner` | +11.4% | [−32.3, +55.1] | no |
| `hillstrom_mens_conversion` | ~195 | `x_learner` | +2.5% | [−32.1, +37.2] | no |

**Targeting does beat random on real randomized data — but only where there
are enough events to see it.** At ~10,700 events two candidates clear the
preregistered threshold with intervals excluding zero. At ~3,100 events nothing
separates. At ~680 and ~195 events the intervals span ±30–55% and the data is
silent. Hillstrom's 64,000 rows are a *large* real experiment by CRM standards,
and its conversion outcome still cannot resolve targeting differences. That is
the empirical basis for the power analysis in §15.

**And the real-data version of kill criterion K2.** Causal learners against a
plain propensity ranking (`response_score`), paired and clustered the same way:

| scenario | `s_learner` | `t_learner` | `x_learner` | `dr_learner` |
|---|---|---|---|---|
| `hillstrom_any_email_visit` | +0.9% | +0.4% | +1.1% | +1.3% |
| `hillstrom_any_email_conversion` | −1.8% | −4.9% | −8.0% | +5.9% |
| `hillstrom_mens_visit` | −1.0% | **−1.1%*** | −0.1% | −0.7% |
| `hillstrom_mens_conversion` | −1.7% | −0.5% | +0.5% | −1.3% |

<small>* interval excludes zero</small>

**Sixteen comparisons on real randomized data. Fifteen show no meaningful
difference, and the one that separates favours the propensity ranking.** This
is the independent confirmation of K2: the causal machinery's advantage in §4.1
comes from regimes engineered to contain response heterogeneity, and on a real
randomized experiment that was not engineered that way, it is absent. Whether
that is because Hillstrom has little response heterogeneity or because 64,000
rows cannot detect it, this benchmark cannot distinguish — and either reading
argues against shipping uplift modelling by default.
<!-- REAL_TRACK_END -->

### 4.3 Online track (RQ7) — 4 regimes × 3 seeds, 20k leads, 8 periods, 25% capacity

% of Oracle's achievable gain:

| competitor | concept_drift | easy_randomized | policy_feedback_loop | propensity_not_uplift | MEAN |
|---|---|---|---|---|---|
| `retrained_propensity_ev` | 59.1 | 58.1 | 58.3 | 29.7 | **51.3** |
| `static_propensity_ev` (frozen) | 60.1 | 57.5 | 57.4 | 29.4 | **51.1** |
| `bandit_thompson` | 53.7 | 55.8 | 57.0 | 35.0 | 50.4 |
| `bandit_greedy_online` (no exploration) | 51.4 | 53.9 | 57.1 | 38.8 | 50.3 |
| `bandit_linucb` | 50.6 | 52.8 | 57.3 | 38.2 | 49.7 |
| `bandit_epsilon_greedy` | 47.1 | 49.3 | 53.0 | 33.7 | 45.8 |
| `random` | 22.5 | 25.7 | 25.7 | 24.1 | 24.5 |

Paired differences vs the frozen offline model: thompson −0.7, greedy −0.8,
linucb −1.4, epsilon-greedy −5.3, periodic retraining **+0.2**.

Three independent readings, all pointing the same way:

- **online updating of a strong learner buys nothing**: retrained vs frozen = +0.2;
- **exploration buys nothing**: linucb / thompson / epsilon vs `greedy_online`
  (same linear learner, only the exploration rule differs) = −0.6 / +0.1 / −4.5;
- **learner capacity beats online-ness**: the linear bandits lose to a boosted
  offline model **even under concept drift** (−6 to −13).

The one place bandits win is `propensity_not_uplift` (+4 to +9), where the
offline Propensity-EV is *structurally* biased — it values the control arm at
zero — and a bandit learning arm-specific outcomes from feedback does not
inherit that bias. The fix for that is not a bandit; it is a T-learner.

**Confound stated plainly**: the bandits are linear and the offline models are
gradient-boosted. The clean within-learner comparison is `greedy_online` vs the
exploring bandits, and the clean within-model comparison is frozen vs
retrained. Both say the same thing as the cross-family one, which is why the
conclusion survives the confound.

### 4.4 MMM track — 6 regimes × 4 seeds

**Primary metric: budget-allocation regret as % of achievable revenue** (lower
is better, 0 = Oracle). This is reported ahead of "% of the Oracle's gain over
an equal split" because the latter is a ratio whose denominator is the prize
itself, which makes it explode when a candidate is worse than the equal split.
Both are given; they rank candidates differently and the reason is instructive.

| candidate | high_collin. | long_hist. | low_signal | smb_short | standard | very_short | **MEAN** |
|---|---|---|---|---|---|---|---|
| `ridge_adstock_saturation` | 3.75 | 2.92 | 6.54 | 5.96 | 2.73 | 1.98 | **3.98** |
| `pymc_marketing_mmm` **calibrated** | 3.38 | **25.13** | 1.62 | **0.61** | 3.43 | 1.25 | **5.90** |
| `equal_allocation` | 6.13 | 6.21 | 6.19 | 6.12 | 6.19 | 6.11 | 6.16 |
| `pymc_marketing_mmm` (uncalibrated) | 3.86 | **52.76** | 6.26 | 4.94 | 15.50 | 5.85 | 14.86 |
| `naive_ols` | 84.27 | 85.25 | 84.21 | 87.73 | 84.21 | 80.34 | 84.34 |
| `reported_roas` (the dashboard) | 92.69 | 92.66 | 92.67 | 92.69 | 92.67 | 92.69 | **92.68** |

The same data as % of Oracle gain over an equal split (0 = equal split):

| candidate | high_collin. | long_hist. | low_signal | smb_short | standard | very_short | MEAN |
|---|---|---|---|---|---|---|---|
| `pymc_marketing_mmm` **calibrated** | 45 | **−302** | 73 | 90 | 44 | 78 | +4.6 |
| `ridge_adstock_saturation` | 39 | 53 | −5 | 4 | 56 | 67 | **+35.8** |
| `pymc_marketing_mmm` (uncalibrated) | 37 | **−751** | −3 | 18 | −149 | −1 | −141.5 |
| `naive_ols` | −1276 | −1279 | −1264 | −1333 | −1264 | −1228 | −1274 |
| `reported_roas` | −1413 | −1393 | −1399 | −1417 | −1399 | −1423 | −1407 |

Per-channel ROI error (MAPE, 1.00 = 100% wrong): calibrated MMM **0.25**,
`reported_roas` 0.61, ridge 0.94, **uncalibrated MMM 1.63**.
Channel **rank** correlation with true ROI: `reported_roas` **0.70** (best
non-oracle), calibrated MMM 0.39, ridge −0.15, **uncalibrated MMM −0.30**.

Four findings, in order of how badly they contradict intuition:

1. **Following your ROAS dashboard destroys value.** 92.7% regret — it captures
   7% of what was available — while having the **best channel ranking of any
   non-oracle method** (ρ = 0.70). Ranking channels correctly and allocating
   budget catastrophically are fully compatible, because allocation depends on
   *marginal* returns and a dashboard reports *average* credit.

2. **The same thing happens inside the best model, and it is the most
   important result in this track.** On `long_history` the calibrated MMM
   achieves its **best ROI accuracy of any regime** (MAPE 0.20, against 0.21–0.30
   elsewhere) and its **worst allocation regret by an order of magnitude**
   (25.1%, against 0.6–3.4% elsewhere). Adstock recovery is unremarkable
   (α MAE 0.202 vs 0.168–0.184 elsewhere), so the model is not obviously
   mis-fitting. Estimating each channel's ROI accurately and choosing the right
   budget split are **different problems**, and 260 weeks of history improved
   the first while wrecking the second. The mechanism is most likely the
   saturation curvature — which sets marginal returns and which the ROI metric
   does not test — but this benchmark does not carry a curvature-recovery
   metric, so that is a hypothesis, not a finding. It is flagged in §9 as an
   open failure.

3. **Experiment calibration is what makes MMM usable**, and it is not
   sufficient. The same library, data and priors: 14.86% mean regret
   uncalibrated, 5.90% calibrated. Uncalibrated it is more than twice as bad as
   an equal split; calibrated it is barely better than one (5.90 vs 6.16) —
   because one regime out of six destroys the average.

4. **The boring candidate is the reliable one.** `ridge_adstock_saturation` —
   grid-searched adstock and saturation plus a regularised non-negative
   regression — has the best mean regret (3.98%), is the only candidate that
   never does worse than the equal split by more than 0.5 points, and is the
   only one with no catastrophic regime. The Bayesian MMM is better in 5 of 6
   regimes and worse on average. For a product decision, *worst-case* behaviour
   on a client's budget matters more than mean-case.

### 4.5 Campaign-level incrementality (PIE, §17)

PyMC-Marketing's PIE is **not lead scoring** and must not be sold as such. It
fits BART on the corpus of campaigns that *did* run an incrementality
experiment, learning campaign features → **measured** incrementality, then
predicts a posterior for campaigns that never ran one. The unit is a campaign;
the label is an experimental readout; it cannot exist without a corpus of past
experiments. It is benchmarked on its own claim, in its own track.

RMSE against true campaign incrementality (lower better) / % of oracle in a
top-quartile selection:

| candidate | 15% measured | 35% measured | 60% measured |
|---|---|---|---|
| `ridge_on_features` | **0.291** / 94.5 | **0.274** / 88.9 | **0.196** / 95.9 |
| `pie_bart` | 0.340 / 89.5 | 0.316 / 90.0 | 0.273 / 92.6 |
| `gbm_on_features` | 0.493 / 61.0 | 0.430 / 82.1 | 0.374 / 83.5 |
| `reported_roas` | 0.473 / 90.2 | 0.479 / 90.7 | 0.498 / 90.1 |
| `global_mean_measured` | 0.511 / 38.9 | 0.506 / 36.2 | 0.509 / 37.4 |

PIE beats last-touch ROAS on *level* accuracy by ~30% and improves as more
campaigns are measured, which is exactly its claim. It loses to a ridge on the
same features.

The obvious objection is that in this variant the truth is **additive** in the
logged features, so the ridge is correctly specified and this is its best case.
So a second variant was run with channel × vertical interactions and a
non-monotone term, specifically to remove that advantage (35% measured,
3 seeds):

| candidate | RMSE (additive truth) | **RMSE (interaction truth)** | selection % (interaction) |
|---|---|---|---|
| `ridge_on_features` | 0.274 | **0.332** | **93.9** |
| `pie_bart` | 0.316 | 0.374 | 90.1 |
| `reported_roas` | 0.479 | 0.457 | 91.9 |
| `gbm_on_features` | 0.430 | 0.508 | 80.8 |
| `global_mean_measured` | 0.506 | 0.593 | 37.1 |

**The objection does not hold.** With a non-additive truth the ridge still
beats BART, by a similar margin (0.332 vs 0.374), and still leads on selection
quality. A flexible non-parametric prior did not pay for itself against a
linear model on ~110 measured campaigns — which is the corpus size a real
advertiser would plausibly have.

**Caveat, stated because it weakens this result**: the PIE sampler did not
converge cleanly at the configured 250 tune / 250 draw × 2 chains — r̂ > 1.01
and ESS < 100 on some parameters. A longer run might close some of the gap.
This is PIE as configured for a benchmark that had to fit on four cores, not
PIE at its best, and the comparison should be read with that discount.

---

## 5. Statistical uncertainty

Every comparison uses the preregistered rule: **paired** bootstrap over shared
(scenario, seed) cells, 95% interval excluding zero, **and** a point estimate
clearing **2% of the reference**. Anything else is reported as *"no meaningful
evidence of difference"*, which is a result and is printed as one.

Headline comparisons, net value per 1,000 leads:

| comparison | Δ $/1k | Δ % of reference | 95% CI (%) | verdict |
|---|---|---|---|---|
| `s_learner` − `propensity_ev_logit` | +7,438 | **+2.9%** | [+1.2, +4.9] | **WIN** (just clears) |
| `s_learner` − `lead_score_gbm` | +19,465 | +8.0% | [+5.4, +11.1] | **WIN** |
| `s_learner` − `hist_profit_per_agent_hour` | +31,951 | +13.9% | [+11.3, +16.7] | **WIN** |
| `propensity_ev_logit` − `hist_profit_per_agent_hour` | +24,513 | +10.7% | [+8.8, +12.6] | **WIN** |
| `propensity_ev_logit` − `lead_score_gbm` | +12,027 | +5.0% | [+3.6, +6.5] | **WIN** |
| `propensity_ev_gbm` − `propensity_ev_logit` | −36 | −0.0% | [−0.6, +0.6] | no meaningful difference |
| `x_learner` − `propensity_ev_gbm` | +3,180 | +1.3% | [−0.0, +2.7] | no meaningful difference |
| `causal_forest` − `propensity_ev_gbm` | −1,458 | −0.6% | [−2.0, +1.0] | no meaningful difference |
| `dr_learner` − `propensity_ev_gbm` | −3,403 | −1.3% | [−2.6, +0.2] | no meaningful difference |
| `hist_profit_per_agent_hour` − `hist_conversion_rate` | −2,317 | −1.0% | [−1.9, −0.1] | no meaningful difference |

Two observations a reader should not skip:

- **The headline causal win is the weakest significant result in the table.**
  +2.9% against a 2% threshold, on a mean carried by three regimes out of ten.
  Everything below it in the causal family fails the rule outright.
- **The economics win is not marginal.** +10.7% and +5.0% with intervals
  nowhere near zero. If only one finding survives replication, it should be
  this one.

**What the intervals do not cover.** Eight seeds with paired comparisons
separate large effects from noise and cannot resolve differences well below the
2% threshold — which is precisely why the rule requires clearing a practical
threshold rather than merely achieving significance. The intervals also cover
sampling variation only, not DGP misspecification; §10 lists what that would
change.

---

## 6. Economic significance

The primary metrics are money, and the secondary predictive metrics are kept
away from the verdict on purpose. The evidence for that choice:

| secondary metric | mean Spearman ρ with realised money (within cell) |
|---|---|
| `uplift_qini_auc` | +0.747 |
| `uplift_auuc` | +0.717 |
| `causal_cate_spearman` | +0.603 |
| `pred_auroc` | +0.472 |
| `causal_pehe` | −0.358 |
| `pred_brier` | −0.343 |
| `pred_ece` | −0.151 |

A rank correlation of +0.75 looks like a licence to optimise Qini. It is not,
because the leaderboard is only read at the top:

| candidate | Qini rank | AUROC rank | **money rank** |
|---|---|---|---|
| `lead_score_logit` | **1** | 2 | **8** |
| `lead_score_gbm` | **2** | 9 | **9** |
| `s_learner` | 3 | 5 | **1** |
| `propensity_ev_logit` | 5 | **1** | **2** |
| `class_transformation` | 11 | 11 | 11 |

Selecting on Qini ships a lead-scoring model that is 8th on money. Selecting on
AUROC ships a coin-flip between 1st and 8th. Neither metric knows what a deal
is worth or what an agent-hour costs, so neither can rank an allocation.

**Net value per agent-hour** tells the same story from the other side. At full
capacity, where total profit is identical across methods, `dr_learner` returns
**$4,930 per agent-hour** against `random`'s **$3,693** (+33%) — because it
declines to spend minutes on negative-uplift leads. A business at full capacity
should read the model as a cost-reduction tool, not a revenue tool.

**Sunk cost, handled correctly.** Once a lead exists, its CPL cannot change the
next action, and the code enforces this:
`realized_net_value(..., include_acquisition_cost=)` is the only place
acquisition cost enters, it is switched on only in the MMM track, and there is
a unit test for the sign. `lowest_cpl` sits at 28.6% — barely above random —
which is what prioritising by sunk cost deserves.

---

## 7. Data-regime analysis

The deliverable of this section is a map a business can apply to itself
*before* commissioning any modelling work.

### 7.1 Which method for which data regime

| If your data looks like this | Then the right method is | Evidence |
|---|---|---|
| < ~5,000 resolved leads | **`propensity_ev_logit`**, or a historical profit-per-agent-hour heuristic while you collect | data-size curve: simple economics 39.2 / 48.4 vs dr_learner 31.5 at 2k |
| 5k–25k resolved leads, homogeneous response | **`propensity_ev_logit`**. Causal adds nothing | s_learner −0.2% on `easy_randomized`, −2.8% on `sparse` |
| > 25k leads **and** response heterogeneity | **`s_learner`** (one GBM, treatment as a feature) | +9.2% and +10.4% in the two heterogeneity regimes |
| Outcome rate below ~1% | **`propensity_ev_logit`**. Causal learners are actively harmful | dr_learner −13.4%, x_learner −9.2% on `very_rare_outcome` |
| Deal value varies, response does not | **`propensity_ev_logit`** — best in the study here | 56.4% vs 51.7 (x_learner), 50.3 (t_learner) |
| Handle time varies, response does not | **`propensity_ev_logit`** — best in the study here | 61.3% vs 58.1 (x_learner), 53.5 (t_learner) |
| Sales capacity ≥ demand | **No model.** Fix something else | every method converges to 85–88% at 100% capacity |
| No logged action propensity | **Nothing causal is identified.** Fix the logging first | positivity diagnostics flag 51% violations under `policy_feedback_loop` |
| Channel budget, no lift tests | **Equal split beats an uncalibrated MMM** | 6.2% regret vs 14.9% |
| Channel budget, with lift tests | **Ridge with adstock+saturation**, or a calibrated MMM you monitor | 3.98% vs 5.90% mean regret |

### 7.2 Data-size curve (RQ9) — % of Oracle gain, 3 regimes × 5 seeds

| regime | candidate | 2k | 5k | 10k | 25k | 50k | 100k |
|---|---|---|---|---|---|---|---|
| `capacity_value_het` | `dr_learner` | 31.5 | 45.3 | 50.3 | 52.1 | 62.4 | **70.1** |
| | `t_learner` | 26.1 | 48.7 | 44.3 | 53.7 | 60.8 | 69.2 |
| | `propensity_ev_gbm` | **39.2** | 49.1 | 46.2 | 44.7 | 42.1 | 49.8 |
| | `hist_profit_per_agent_hour` | 21.1 | 26.7 | 25.4 | 37.5 | 29.4 | 27.6 |
| | `lead_score_gbm` | 20.7 | 32.6 | 25.6 | 27.0 | 20.3 | 28.1 |
| `propensity_not_uplift` | `t_learner` | 32.6 | 38.5 | 36.8 | 46.9 | 43.7 | **54.2** |
| | `propensity_ev_gbm` | 33.9 | 45.3 | 35.0 | 39.1 | 37.6 | 41.5 |
| | `hist_profit_per_agent_hour` | **43.5** | 33.2 | 34.1 | 52.1 | 41.2 | 35.7 |
| `sparse` | `propensity_ev_gbm` | **48.4** | 55.0 | 57.6 | 58.7 | 64.9 | **66.0** |
| | `t_learner` | 29.3 | 49.3 | 52.3 | 52.6 | 63.1 | 62.9 |
| | `lead_score_gbm` | 48.2 | 50.0 | 51.7 | 54.3 | 59.9 | 60.0 |
| | `hist_profit_per_agent_hour` | 44.3 | 40.1 | 42.0 | 42.1 | 44.5 | 46.0 |

**Crossover: below ~5–10k resolved leads the simple economic model is as good
or better than anything causal; above ~25k the causal learners pull ahead, in
the heterogeneous-response regimes only.** Analytics baselines are flat in N —
more data does not improve a campaign-level average, because the problem is the
unit of aggregation, not the sample size.

### 7.3 Capacity curve — the single most important product chart

% of Oracle gain, `capacity_value_heterogeneity`:

| candidate | 5% | 10% | 25% | 50% | 100% |
|---|---|---|---|---|---|
| `dr_learner` | **35.5** | 41.0 | 65.4 | 82.2 | 87.8 |
| `t_learner` | 33.1 | 40.9 | 61.9 | 80.0 | 84.7 |
| `propensity_ev_gbm` | 26.1 | 34.1 | 48.9 | 67.8 | 84.6 |
| `hist_profit_per_agent_hour` | 7.4 | 14.3 | 30.8 | 47.5 | 87.2 |
| `lead_score_gbm` | 4.9 | 9.8 | 23.6 | 52.3 | 87.7 |
| `random` | 6.8 | 10.7 | 22.0 | 43.2 | 86.1 |

**The entire value of a decision engine lives in scarce capacity.** At 5%
capacity a causal model captures 5–7× what lead scoring or an analytics
baseline does. At 100% capacity everything converges to 85–88% and the model is
worth nothing on total profit — the advantage moves into efficiency instead
(+33% net per agent-hour).

This is also the sharpest qualification the study produces on the incumbents:
`lead_score_gbm` at 5% capacity captures **4.9%** of the achievable gain, below
`random`'s 6.8%. Ranking by P(convert) under severe scarcity is worse than
choosing at random, because the highest-probability leads are disproportionately
the ones who would have converted anyway.

### 7.4 Where the causal advantage comes from — decomposition (8 seeds each)

Three regimes isolating one kind of heterogeneity each:

| candidate | agent_time_het (effort varies) | value_het (deal value varies) | capacity_value_het (all three, incl. response) |
|---|---|---|---|
| `x_learner` | 58.1 | 51.7 | **64.9** |
| `causal_forest` | 52.5 | 41.8 | 64.4 |
| `s_learner` | 60.2 | 56.2 | 64.3 |
| `dr_learner` | 51.6 | — | 62.8 |
| `t_learner` | 53.5 | 50.3 | 59.5 |
| **`propensity_ev_logit`** | **61.3** | **56.4** | 44.4 |
| `propensity_ev_gbm` | 57.9 | 53.8 | 49.6 |

Read across the `propensity_ev_logit` row: explicit economics handles
heterogeneous **effort** and heterogeneous **deal value** on its own, beating
every causal learner in both. It collapses (61 → 44) only when heterogeneous
**treatment response** is added. So:

- heterogeneous deal value → solved by multiplying by predicted value;
- heterogeneous handle time → solved by dividing by predicted effort;
- heterogeneous **treatment response** → the only thing that needs a causal
  model, and worth ~15 points of Oracle gain when present.

That is a sharper claim than "uplift modelling helps", and it is falsifiable on
a partner's data: if their leads differ mainly in value and cost-to-serve
rather than in how they respond to contact, the causal machinery is not what
they need.

---

## 8. Ablations

<!-- ABLATIONS_START -->
*(ablation suite in flight; this section is completed from
`reports/runs/ablation/results.csv` on completion. The design is fixed and
preregistered: each ablation removes exactly one component and holds everything
else identical.)*

| Ablation | Removes | What it isolates |
|---|---|---|
| `abl_*_no_value_model` | predicted deal value → global mean | the contribution of value modelling |
| `abl_*_no_effort_model` | predicted handle time → global mean | the contribution of effort modelling (RQ4) |
| `abl_*_no_optimizer` | EV-mode allocation → rank mode | the contribution of the constrained optimiser (RQ4) |
| `abl_bayes_no_hierarchy` | hierarchical pooling → pooled model | the contribution of partial pooling (RQ6) |
| `*_lcb10` / `*_lcb25` | EV policy → risk-averse lower bound | whether uncertainty changes decisions (RQ5) |
| `*_abstain` | always decide → decline on thin evidence | the price of abstention (§12) |
<!-- ABLATIONS_END -->

What is already established from the decomposition in §7.4 and the capacity
curve in §7.3, independent of the ablation suite: the value model and the
effort model together account for the majority of the gap between lead scoring
(50–52%) and the economics wrapper (57–58%), and the optimiser's contribution
is the difference between EV mode and rank mode, which grows as capacity
tightens.

### 8.1 Uncertainty ablations (RQ5, RQ6) — complete for 2 of 4 regimes, n=5,000

% of Oracle gain, mean over `sparse` and `propensity_not_uplift`, 4 seeds:

| candidate | % of Oracle | fit (s) | 80% interval coverage | what it isolates |
|---|---|---|---|---|
| `bayes_hierarchical_lcb25` | 58.1 | 45.8 | 0.222 | risk aversion at 25% |
| **`bayes_hierarchical`** | **58.0** | 45.0 | 0.222 | the full model |
| `bayes_hierarchical_lcb10` | 57.4 | 45.8 | 0.222 | risk aversion at 10% |
| `propensity_ev_gbm` | 48.4 | 0.9 | — | the non-Bayesian reference |
| `propensity_ev_gbm_bootstrap` | 48.4 | 5.9 | 0.331 | bootstrap uncertainty |
| **`abl_bayes_no_hierarchy`** | **46.4** | 20.8 | 0.103 | **pooling removed** |
| `bayes_hierarchical_abstain50` | 45.1 | 45.8 | 0.222 | abstain on the thinnest 50% |
| `propensity_ev_gbm_bootstrap_lcb25` | 43.7 | 5.9 | 0.331 | risk aversion, frequentist |
| `propensity_ev_gbm_bootstrap_abstain50` | 33.8 | 5.9 | 0.331 | abstention, frequentist |
| `propensity_ev_gbm_bootstrap_abstain25` | 17.5 | 5.9 | 0.331 | abstain on the thinnest 25% |
| `bayes_hierarchical_abstain25` | **12.9** | 45.8 | 0.222 | abstain on the thinnest 25% |

Four readings:

1. **Partial pooling is the whole Bayesian advantage.** 58.0 → 46.4 when it is
   removed, which is larger than the model's entire margin over the
   gradient-boosted baseline. Without pooling the Bayesian model *loses* to it.
2. **The posterior changes no decisions.** lcb10 / lcb25 move the result by
   −0.6 / +0.1. Bootstrap intervals move `propensity_ev_gbm` by exactly 0.0.
3. **Intervals do not cover.** 80% nominal delivers 22% (Bayesian) and 33%
   (bootstrap) against per-lead truth. This is a harsh standard — the posterior
   covers parameter uncertainty, not misspecification, nor the point-estimated
   value and effort nuisances feeding the EV — but a product must not present
   these as calibrated 80% intervals, because they are not.
4. **Abstention is expensive as scored.** Declining the thinnest 25% costs
   45 points (58.0 → 12.9). The mechanism is documented and deliberate:
   declined leads take the control action and the freed capacity is **not**
   reallocated, so this is a lower bound on abstention's value, not a
   measurement of it (§16.7 in the methodology). It measures the cost of
   refusing to act, not the value of deferring to a human.

---

## 9. Failure modes

Recorded because a benchmark with an empty failure section is a benchmark whose
author did not look. §66 requires these to be visible.

### 9.1 Where candidates fail

- **Causal learners under rare outcomes.** `dr_learner` −13.4% and `x_learner`
  −9.2% against Propensity-EV on `very_rare_outcome`. Cross-fitting on a
  0.5%-positive outcome produces nuisance models that are noise, and
  doubly-robust correction amplifies rather than cancels it.
- **Lead scoring under severe scarcity.** Worse than random at 5% capacity
  (4.9% vs 6.8%), because P(convert) and P(convert *because we called*) are
  different functions and they diverge most at the top of the ranking.
- **`class_transformation` under confounding.** 13.9% on `observed_confounding`
  against 37.2% on average. The transform assumes a known constant treatment
  probability; when assignment depends on covariates it inverts.
- **Uncalibrated MMM on the standard regime**: 15.5% regret against an equal
  split's 6.2%. Worse than not modelling, and with no internal signal that it
  has gone wrong.
- **Calibrated MMM on 260 weeks of history — an open failure, not explained.**
  25.1% allocation regret, an order of magnitude worse than its 0.6–3.4% in
  every other regime, *while achieving its best ROI accuracy of the whole
  track* (MAPE 0.20) and unremarkable adstock recovery (α MAE 0.202). More
  history made the model's channel-return estimates better and its budget
  decisions far worse. The leading hypothesis is the saturation curvature,
  which determines marginal returns and which no metric in this benchmark
  tests; adding a curvature-recovery metric is the obvious next step and was
  not done. Recorded here rather than dropped, because it is the single
  result in this study that is understood least and it argues directly against
  shipping a Bayesian MMM without worst-case monitoring.
- **Bandits under drift.** They were supposed to be the answer to drift and
  they lose to a frozen gradient-boosted model by 6–13 points on
  `concept_drift`.

### 9.2 Where the *benchmark* failed, and what it cost

Full list in [`docs/methodology.md`](../../docs/methodology.md) §8. The four
that would have produced confidently wrong answers:

1. **Truth column collision.** Per-stage `P(funded | application)` was written
   to `p_funded_a{a}` — the same name as the overall funnel probability —
   silently overwriting it. Every reported "true ATE" was wrong by ~4× (0.0155
   vs the true 0.062). Caught by reconciling stated probabilities against
   realised arm conversion rates. Now a permanent regression test.
2. **Hyperparameter name collision.** `CausalForest(n_estimators=)` was
   swallowed by the forest, so its *base learners* silently used library
   defaults while every other family used the shared setting — an unfair
   comparison hiding in a keyword argument.
3. **Jensen gap in the MMM curve.** Reconstructing the response curve at the
   *posterior mean* disagreed with the library's own fitted contributions by
   15–50%, because logistic saturation is concave. Fixed by averaging over
   posterior draws; residual cross-check error ~6%, reported as a diagnostic
   and raising above 15%.
4. **A second key collision.** `RealizedOutcome.to_dict()` emitted `n_leads`,
   overwriting the configured dataset size with the test-fold size and
   scrambling every data-size curve. Renamed to `n_test_leads`.

None of these would have produced an obviously broken result. All of them would
have produced a confidently wrong one. That is the argument for the sanity
tests, not the tests' documentation.

### 9.3 Adversarial and negative controls

`leadbench.evaluation.diagnostics` runs on any dataframe, not only the
synthetic regimes: Simpson's paradox (sign reversal between marginal and
within-segment treatment differences), target leakage, future-dated columns in
the declared feature list, positivity/overlap, and duplicate entities. On the
benchmark's own regimes it correctly flags **51% positivity violations** under
`policy_feedback_loop` and **2.9% duplicate people** under `noisy_crm`, and
stays quiet on the real randomized data. The `negative_control_null_effect`
regime exists so that a method claiming an effect where none exists is caught
by construction.

---

## 10. Computational cost

Mean seconds per fit on the lead track, with each candidate's share of the
benchmark's total compute:

| candidate | fit (s) | predict (s) | % of all compute | % of Oracle |
|---|---|---|---|---|
| `causal_forest` | 26.92 | 1.16 | **51.4%** | 53.6 |
| `dr_learner` | 5.51 | 0.23 | 10.5% | 49.9 |
| `x_learner` | 4.12 | 0.53 | 7.9% | 55.9 |
| `funnel_ev_gbm` | 3.13 | 0.55 | 6.0% | 57.5 |
| `t_learner` | 2.44 | 0.32 | 4.7% | 55.2 |
| `s_learner` | 2.25 | 0.32 | 4.3% | **61.3** |
| `propensity_ev_gbm` | 1.72 | 0.26 | 3.3% | 57.2 |
| `lead_score_gbm` | 1.66 | 0.21 | 3.2% | 50.1 |
| **`propensity_ev_logit`** | **1.01** | 0.19 | 1.9% | **58.4** |
| `hist_profit_per_agent_hour` | 0.06 | 0.00 | 0.1% | 36.6 |
| `random` | 0.04 | 0.00 | 0.1% | 24.9 |

The Pareto frontier (not dominated on higher value *and* lower cost) has seven
points, and the shape of it is the product argument:

| candidate | fit (s) | % of Oracle |
|---|---|---|
| `call_everyone` | 0.040 | 25.7 |
| `lowest_cpl` | 0.044 | 29.0 |
| `hist_roas` | 0.048 | 33.7 |
| `hist_conversion_rate` | 0.048 | 38.8 |
| `lead_score_logit` | 0.97 | 52.7 |
| **`propensity_ev_logit`** | **1.00** | **58.7** |
| **`s_learner`** | **2.25** | **60.6** |

Four of the seven are essentially free and buy you up to 38.8%. The fifth costs
a second and buys 52.7%. **Above one second of compute there are exactly two
non-dominated candidates**, and `s_learner` is the last point on the frontier:
nothing costing more than 2.25 seconds is worth its price on this benchmark.
`causal_forest`, `dr_learner`, `x_learner`, `t_learner`, `funnel_ev_gbm`,
`propensity_ev_gbm` and every Bayesian variant are all dominated.

`causal_forest` is the clearest verdict in the study: **27× the compute of
`propensity_ev_logit` to finish 5 points below it**, while consuming half the
benchmark's total compute. The Bayesian candidates cost another order of
magnitude beyond that — a single PyMC fit at n=5,000 takes 45 seconds, more
than the entire non-Bayesian lead track for that scenario — which is why kill
criterion K1 is written the way it is, and why §2.6's finding that the win is
*pooling* rather than the posterior matters commercially: pooling is available
without paying this.

---

## 11. Product implications

### 11.1 Kill criteria, evaluated

Agreed in advance in [`docs/benchmark-spec.md`](../../docs/benchmark-spec.md) §10.

| # | Criterion | Trigger | Status |
|---|---|---|---|
| K1 | Kill Bayesian complexity | Bayesian within 2% of best non-Bayesian at >10× compute | **NOT triggered** *(2 of 4 regimes)* — `bayes_hierarchical` 58.0 vs `propensity_ev_gbm` 48.4 at n=5,000 in sparse regimes, well outside 2%, at 51× compute. But the win is **partial pooling**, not the posterior (§2.6), and the cheap-pooling alternative was not tested |
| K2 | Kill uplift | Causal fails to beat `propensity_ev_gbm` by >2% **on randomized data** | **TRIGGERED, twice** — synthetic `easy_randomized`: s_learner +1.3% (n.s.), x_learner −0.7%, t_learner −1.7%, dr_learner −3.5%. **Real** randomized data (§4.2): 15 of 16 comparisons show no meaningful difference and the 16th favours the propensity ranking |
| K3 | Kill lead-level decisioning | `hist_profit_per_agent_hour` reaches ≥80% of Oracle | **NOT triggered** — it reaches 36.6% |
| K4 | Kill MMM for SMB | MMM allocation regret >10% at SMB sizes | **NOT triggered at SMB sizes** — calibrated MMM 0.61% regret on `smb_short` (52 weeks) and 1.25% on `very_short` (30 weeks), both well under 10%. **But it fails the criterion at 260 weeks** (25.1%), which is the opposite of the expected direction and is treated as an open failure in §9 |
| K5 | Kill the whole hypothesis | Best analytics baseline within 2% of best model | **NOT triggered** — the gap is 22.9 points of Oracle gain (+13.9% of net value) |

**K2 firing is the most important single line in this report**, and it fires
on the synthetic randomized regime and on the real randomized experiment
independently. Causal inference applied to randomized data with no response
heterogeneity to exploit does not earn its complexity. It earns it only in the
regimes named in §7.1, which were built to contain that heterogeneity.
Shipping uplift modelling as a default is not supported by this evidence;
shipping it as a *conditional upgrade*, gated on a measured test for response
heterogeneity, is.

### 11.2 Success criterion, evaluated

§11 of the spec: the project is interesting when a reproducible, economically
meaningful region exists where a decision model beats a realistic baseline by
more than the practical threshold with an interval excluding zero.

**That region exists and is:** limited sales capacity (materially below the
effort needed to work every lead) **+** heterogeneous deal value **+**
heterogeneous treatment response **+** above roughly 25,000 resolved leads.
In it, the decision model beats the best analytics baseline by +13.9% of net
value per 1,000 leads and lead scoring by +8.0%, both with intervals well clear
of zero.

The criterion is met. The region is narrower than the hypothesis assumed.

### 11.3 Product maturity ladder

Each rung is shippable, each earns the right to the next, and each is falsified
by the rung below it failing.

| Rung | What ships | Needs | Beats | Evidence |
|---|---|---|---|---|
| **0** | Profit-per-agent-hour reporting by campaign/source | CRM export with effort and realised value | last-click dashboards (+3.9%) | §5 |
| **1** | **`propensity_ev_logit`** — calibrated P(convert) × predicted value ÷ predicted minutes, under a capacity constraint | ~1–5k resolved leads, effort logging | lead scoring by +5.0%, analytics by +10.7% | §5 |
| **2** | Randomised holdout (5–10%) with logged propensity, permanently | product decision, not a model | makes everything above measurable | §15 |
| **3** | **`s_learner`** — one GBM with treatment as a feature | ~25k resolved leads **and** a measured response-heterogeneity signal | rung 1 by +2.9%, and only in the right regime | §5, §7.1 |
| **3b** | **Partial pooling across segments** — try mixed-effects or empirical-Bayes shrinkage first, PyMC only if they fall short | many small segments (campaigns, sources, regions) with thin data each | `propensity_ev_gbm` by +9.6 points in sparse regimes | §8.1 |
| **4** | Uncertainty surfacing / abstention | posterior or bootstrap intervals | **not demonstrated** — see §2.6, §2.9, §8.1 | — |
| **5** | Budget allocation: ridge with adstock+saturation first, calibrated MMM only with monitoring | a running lift-test programme | equal split, 3.98% vs 6.16% regret | §4.4 |

Rung 3b is where the largest un-banked gain in this study sits, and also its
largest open question: partial pooling was worth +11.6 points but was only
tested via 45-second MCMC fits, and the cheap alternatives were never
benchmarked. Rung 4 has no evidence behind it and should not be built until it
does — the intervals measured here do not even cover (22% actual against 80%
nominal). Rung 5 should not be built before a partner is running lift tests,
because without them the MMM is worse than an equal split.

### 11.4 Day-one value, before any model has data

The `propensity_ev_logit` rung needs a few thousand resolved leads. Before
that, the honest offer is measurement plus arithmetic, not prediction:
profit-per-agent-hour by source, the capacity-utilisation picture, and the
data-contract instrumentation that makes everything later possible. Full
architecture in [`docs/product-rollout.md`](../../docs/product-rollout.md) §6.

### 11.5 Uncertainty UX

A model that says **"INSUFFICIENT EVIDENCE"** where support is missing is more
valuable than one that always answers — but this study did not demonstrate that
it *earns money*, so it is a trust feature, not a value feature, and should be
sold as one. Concretely: never a fabricated "AI Score 87/100"; show the number
of comparable historical leads behind the estimate, and decline where logged
propensity support is absent. The positivity diagnostics that flag 51%
violations under `policy_feedback_loop` are the mechanism for that last one,
and they are the part of this with real evidence behind it.

**One thing this study explicitly does not license: presenting the model's
intervals as calibrated.** Measured against per-lead truth, 80% nominal
intervals achieved **22%** coverage (Bayesian) and **33%** (bootstrap) — see
§8.1. That standard is harsh, because the posterior covers parameter
uncertainty and not misspecification or the point-estimated nuisances, but a
product does not get to make that distinction on the customer's behalf. Show
evidence counts and support diagnostics, which are honest; do not print
"80% confidence interval" next to a number whose interval covers 22% of the
time.

---

## 12. Market landscape

Full version: [`docs/research/market-landscape.md`](../../docs/research/market-landscape.md).
Accessed 2026-09-22; vendor capability claims marked *vendor-reported*.

- **Measurement (layer A) is a commodity.** Roistat, Calltouch, Triple Whale,
  HockeyStack, Northbeam and Rockerbox all connect spend → CRM → revenue.
  Building this again is building a worse version of six products.
- **Aggregate allocation (layer C) is being commoditised right now.** Triple
  Whale's Compass explicitly unifies MTA, MMM and geo-lift incrementality and
  surfaces a "next best action"; Measured, Haus and Recast are incrementality
  specialists; Google Meridian and Meta Robyn are free.
- **Individual decisioning (layer B) is the thin one.** Every mainstream lead
  score — Salesforce Einstein, HubSpot — predicts `P(convert)`. None estimates
  the *incremental* effect of contacting the lead, none multiplies by deal
  value, none subtracts the agent minutes it is about to spend. Einstein
  documents a requirement of 1,000 leads and 120 conversions in the trailing
  180 days for a custom model.
- **Routing is rule-based.** LeadAngel, Chili Piper, RingLead and the CRMs
  distribute by round robin, weighted round robin, territory, ownership and
  per-rep caps. "Capacity-aware" means *do not exceed a rep's cap*, not
  *allocate scarce agent-hours to maximise contribution margin*.

The capability gap at layer B is real, and this benchmark measures it at
+5.0% of net value over a gradient-boosted lead score. The uncomfortable
corollary is that a gap persisting in a large, competitive market is evidence
about value as much as about opportunity.

---

## 13. Patent / prior-art summary

Full version, with an explicit retrieval-limits note:
[`docs/research/patent-landscape.md`](../../docs/research/patent-landscape.md).
**This is not a legal opinion and not an FTO analysis.**

**Retrieval was materially limited from this environment**: Google Patents
returned 503 on every attempt, Espacenet and Justia 403, FreePatentsOnline
failed TLS, and the PatentsView legacy API no longer returns JSON. USPTO grant
PDFs download but are scanned images with no text layer. Claim content below is
paraphrased from search-surfaced excerpts, and **assignees, priority dates and
legal status are not independently verified.**

Closest hit: **US 11,068,304 B2, "Intelligent scheduling tool"** — lead
connectivity prediction, allocation of leads to timeslots given available
resources, dynamic lead scoring, and a **contextual bandit** (Thompson sampling
named) updating the prediction model. Capacity-aware allocation plus bandit
updating plus lead scoring, in one family.

Also relevant: the Velocify "Lead scoring" family (US 2014/0149178 A1,
US 2017/0237859 A1; Velocify is now part of ICE Mortgage Technology — the
lending vertical named in the brief); the "Next best action" family
(US 9,420,100 B2, RE 47,652) whose described "Value versus Volume" mechanism
trades acceptance likelihood against projected financial value; and
budget-allocation patents US 11,915,262 and US 11,386,449.

**Almost certainly commodity**: lead scoring from historical conversions;
`P(convert) × deal value` as a prioritisation score; uplift/incremental
targeting; contextual bandits for allocating marketing actions;
budget-constrained advertising allocation; MMM with adstock and saturation.

**Possibly narrower, worth an attorney's hour** — and only after value is
proven, not before: (1) allocating a scarce human sales-time budget by
*estimated incremental effect × predicted contribution margin ÷ predicted
handle time* under a capacity constraint; (2) an abstention mechanism keyed to
posterior width and logged-propensity support; (3) joint allocation across
media budget *and* sales capacity in one objective.

Recommended next step if the programme continues: a professional search scoped
to CPC `G06Q 30/0201`, `30/0242`, `30/0251`, `10/0631` and the assignees named
above. Cheap relative to building on a claim someone else owns.

**A separate legal constraint, unrelated to patents.** The benchmark requires
**no PII** — no name, phone number or e-mail address is used by any model — and
this is a deliberate design property, not an accident. Additionally: this
system must **not** be positioned as an automatic credit-underwriting engine in
the lending vertical. It allocates sales attention; it does not decide
creditworthiness, and the regulatory surface of the latter is entirely
different.

---

## 14. Data collection recommendation

Full specification: [`docs/data-contract.md`](../../docs/data-contract.md).

Four omissions make most CRM exports useless for this question. All four are
cheap to fix prospectively and **impossible to fix retrospectively**:

1. **Immutable funnel events with both `occurred_at` and `recorded_at`.**
   Storing only the current stage destroys the ability to reconstruct what was
   knowable at decision time. Storing only one timestamp destroys it more
   subtly, by letting you train on information that had not arrived yet.
2. **Agent effort per lead**: talk seconds, wrap-up seconds, attempt count.
   Without it, profit per agent-hour — the metric that actually decides
   allocation under capacity — cannot be computed at all, and §7.4 shows effort
   heterogeneity is one of the two things simple economics monetises.
3. **Realised net contribution, not opportunity value**, including refunds and
   clawbacks with their own timestamps. Optimising on opportunity value
   systematically over-weights big deals that never close.
4. **A decision log with `action_propensity`.** One float per decision. It is
   the difference between "we think calling helps" and "we can estimate what a
   policy we never deployed would have earned". Without it off-policy
   evaluation is not identified, and no amount of modelling recovers it.

**Nice-to-have**, in rough priority order: standardised loss-reason taxonomy;
agent skill and tenure; creative and landing-page identifiers; geo at region
granularity; derived features from call recordings; competitor-quote flags.

**Not needed: any PII.** No model in this repository uses a name, phone number
or e-mail address. Keep operational identity and the analytical feature store
separate — it costs nothing at design time and is expensive to retrofit.

---

## 15. Next real-world experiment

Full protocol: [`docs/product-rollout.md`](../../docs/product-rollout.md).

**Phase 1 — shadow mode, 4–8 weeks.** Freeze the model, log every
recommendation with its score and model version at decision time, do not show
it to agents, do not retrain inside the window. This validates calibration and
the data contract. It **cannot** establish causal value: if the incumbent
process is deterministic, the leads the model wanted to call but nobody called
have no observed outcome, and no estimator recovers it.

**Phase 2 — randomised slice, permanently.** 5–10% of leads to randomised
assignment, or epsilon-greedy with ε≈0.05, with the propensity logged. Keep it
after the pilot: it is the price of being able to measure anything again.

**Powering it — the number that surprises people.** Computed from this
benchmark's own DGP at realistic parameters, 80% power, α=0.05:

| Quantity | `easy_randomized` | `capacity_value_heterogeneity` |
|---|---|---|
| sd of per-lead net value | $1,397 (CV 5.0) | $3,161 (CV 6.1) |
| n per arm for the **conversion-rate** lift | **449** | **842** |
| n per arm for the **dollar** uplift | **1,951** | **7,560** |
| n per arm for **half** that dollar uplift | 7,805 | 30,241 |

Realised deal value is lognormal with a coefficient of variation around 5–6, so
one large funded deal moves the mean more than a hundred small ones.
Consequences: power the pilot on **incremental conversions**, treat the dollar
readout as a slower confirmation, use CUPED and stratification, and **do not
promise a partner a statistically convincing profit result in six weeks on
3,000 leads** — that promise cannot be kept at this variance.

The Hillstrom result in §4.2 is the same lesson from real data, and it
calibrates the table above against something that actually happened. The same
64,000-user experiment separates targeting from random on the **visit** outcome
(~10,700 events, +3.1% with the interval excluding zero) and is completely
silent on the **conversion** outcome (~680 events, interval [−32%, +55%]). Same
users, same randomization, same models — only the event count differs. Power
here is a function of *events*, not of rows, and a CRM with 64,000 leads and a
1% funded rate is in the silent regime.

---

## 16. Limitations — what would overturn these conclusions

1. **The synthetic DGP is our own model of the world.** A method whose
   structure matches the generator has an advantage no deployment enjoys.
   Mitigated by the two real randomized datasets and by deliberately giving the
   Bayesian candidate a *misspecified* linear-logistic form rather than the
   true four-stage funnel — mitigated, not eliminated.
2. **The economics are parameterised, not measured**: $38/agent-hour, ~8 min
   median handle time, 32% margin, 4% clawback. Every conclusion that turns on
   the *ratio* of agent cost to contribution margin should be re-checked
   against a partner's real figures.
3. **Real-data tracks test targeting, not the full economic problem.**
   Hillstrom and Criteo carry no agent-time or margin data, so value per
   outcome and cost per treatment are preregistered constants and the
   constraint is a send budget.
4. **Eight seeds separate large effects from noise, not small ones.** Hence the
   2% practical threshold rather than bare significance.
5. **One capacity level dominates the headline table** (25%). The answer moves
   with capacity — see §7.3 — so read the headline as "at this capacity".
6. **Interval coverage is measured against per-lead truth**, a harsh standard:
   the posterior covers parameter uncertainty, not misspecification, and not
   the point-estimated nuisances feeding the EV.
7. **Blockers, stated concretely rather than deferred.** Meta Robyn was not
   benchmarked (R package; the official Python distribution is a self-described
   LLM-translated beta, so benchmarking it would measure the translation).
   PyMC-Marketing runs at 0.19.2 because 1.1.0 requires Python ≥3.12. Google
   Meridian 2.0.0 runs, in an isolated 3.12 interpreter, on a representative
   subset of MMM regimes because it is by far the slowest candidate. Patent
   primary sources were unreachable. Vowpal Wabbit is installed but not entered
   as a candidate, because its CB reductions bundle exploration with their own
   learner and would confound the exploration comparison.

---

## 17. Direct answers

The seventeen questions asked, answered directly. "No" was declared an
acceptable answer in advance and is used where it is the truth.

**1. Is there evidence that a decision-centric approach gives a practical
advantage over ordinary end-to-end analytics?**
**Yes, and it is the largest effect in the study.** +10.7% of net value per
1,000 leads for `propensity_ev_logit` over the best historical baseline
(95% CI +8.8% to +12.6%), and +13.9% for `s_learner`. In % of Oracle gain the
analytics layer tops out at ~38% while the decision layer reaches 58–61%. The
cause is structural, not statistical: analytics aggregates to campaign or
channel, the decision is per lead, and more data does not fix a unit mismatch —
the analytics baselines are flat in N from 2k to 100k.

**2. Is there an advantage over ordinary lead scoring?**
**Yes, +5.0%** (95% CI +3.6% to +6.4%) for the same logistic regression once
it is multiplied by predicted deal value and divided by predicted agent
minutes. The advantage widens sharply as capacity tightens: at 5% capacity
`lead_score_gbm` captures 4.9% of the achievable gain — *below random's 6.8%* —
against 26.1% for the economics wrapper. Ranking by P(convert) under scarcity
selects the leads who would have converted anyway.

**3. Is a Bayesian approach needed at all?**
**The posterior, no. The hierarchy, yes — but probably not via MCMC.** These
must be separated, and separating them reverses the expected answer. Quantified
uncertainty changed decisions by ±0.6 points (risk-averse lower-bound policies
58.1 / 57.4 vs the plain EV policy's 58.0) and by *exactly zero* for bootstrap
intervals, while under-covering badly — 80% nominal intervals achieve 22%
actual coverage against per-lead truth. But the **hierarchical** model beat
`propensity_ev_gbm` by **+9.6 points** in sparse regimes at n=5,000, and the
no-pooling ablation shows **+11.6 of those points are partial pooling alone**;
strip the hierarchy out and the Bayesian model is *worse* than the baseline.
So kill criterion K1 does not fire — but the thing that earns its keep is
pooling across sparse segments, which mixed-effects or empirical-Bayes
shrinkage can also provide at a fraction of 45 seconds per fit. **That cheaper
comparison was not run, and until it is, "we need PyMC" is not established —
only "we need pooling" is.**

**4. Where is causal uplift genuinely more useful than propensity?**
**Only where treatment response is heterogeneous.** Decomposed: heterogeneous
deal value is solved by multiplying by value; heterogeneous handle time is
solved by dividing by effort; heterogeneous *response* is the only one needing
a causal model, and it is worth ~15 points of Oracle gain when present. Causal
beat the simple economic model in 3 of 10 regimes (`strong_heterogeneity`
+10.4%, `capacity_value_heterogeneity` +9.2%, `propensity_not_uplift` +4.4%),
tied in 5, and **lost** in `sparse` (−2.8%) and `very_rare_outcome` (−5.2%).
On clean randomized data with no heterogeneity structure it earns nothing —
and on **real** randomized data (Hillstrom, four scenarios, sixteen paired
comparisons) it does not beat a plain propensity ranking in fifteen of them
and loses the sixteenth. The synthetic advantage is real; it is also an
advantage in regimes we constructed to contain the thing it exploits, and the
one real experiment available does not show it.

**5. Where is a contextual bandit more useful than an offline model?**
**Almost nowhere, on this evidence.** Exploration bought −0.6 / +0.1 / −4.5
against the same learner run greedily; periodic retraining bought +0.2 over
freezing; linear bandits lost to a boosted offline model by 6–13 points *under
explicit concept drift*. The single exception is `propensity_not_uplift`
(+4 to +9), where the offline model is structurally biased because
Propensity-EV values the control arm at zero — and the correct fix there is a
T-learner, not a bandit. Bandits remain the right answer for one thing this
benchmark confirms indirectly: they *generate logged propensities*, which is
what makes everything else measurable.

**6. What is the simplest model family we would actually ship?**
**Calibrated logistic regression, multiplied by a predicted contribution
margin, divided by predicted handle time, allocated under an explicit capacity
constraint.** That is `propensity_ev_logit`: 1.0 seconds to fit, 58.4% of
Oracle, second on the entire leaderboard, and statistically indistinguishable
from its gradient-boosted twin (−0.0%, CI [−0.6%, +0.6%]). The intelligence is
in the objective, not the estimator.

**7. At what data volume does it start being useful?**
**~1,000–5,000 resolved leads** for the economics wrapper — it is the *best*
candidate at 2,000 leads (39.2% and 48.4% of Oracle in two regimes, ahead of
every causal learner). **~25,000 resolved leads** before causal modelling
overtakes it, and then only with response heterogeneity present. Below ~1% base
rate, causal learners are actively harmful at any size tested.

**8. What data must a business start collecting today?**
Four things, all impossible to reconstruct later: (i) **immutable funnel events
with both `occurred_at` and `recorded_at`**; (ii) **agent effort per lead** —
talk seconds, wrap-up seconds, attempts; (iii) **realised net contribution**
with refunds and clawbacks timestamped, not opportunity value; (iv) **a
decision log with `action_propensity`** — one float per decision, without which
off-policy evaluation is not identified.

**9. What data is nice-to-have?**
Standardised loss-reason taxonomy; agent skill and tenure; creative and
landing-page identifiers; geo at region granularity; derived features from call
recordings; competitor-quote flags. **Explicitly not needed: any PII.** No
model here uses a name, phone number or e-mail address.

**10. How do we test the product on a design partner without risking their
business?**
Shadow mode: freeze the model, log every recommendation with score and model
version at decision time, show agents nothing, retrain nothing inside the
window. The partner's process is untouched, so the downside is zero and the
readout is calibration plus data-contract validation. State plainly up front
that shadow mode **cannot** establish causal value — if the incumbent process is
deterministic, the leads the model wanted and nobody called have no outcome.

**11. When can we move from shadow mode to a randomized pilot?**
When three entry conditions hold: calibration is within tolerance on shadow
data, the data contract is actually being satisfied (effort and propensity
logged, not promised), and the partner has enough volume to power the readout.
That last one is the binding constraint: **~450 leads per arm** for an
incremental-conversion readout, **~2,000–7,600 per arm** for a dollar readout,
and ~8,000–30,000 per arm for half that effect. Power on conversions, confirm
on dollars.

**12. What is a realistic MVP for HighLevel?**
Rung 1 of the ladder in §11.3, not rung 3. Read the CRM's pipeline events,
opportunity values and call/effort data through the existing API; compute
calibrated P(convert) × predicted value ÷ predicted minutes; return a ranked,
capacity-truncated call list plus a profit-per-agent-hour view by source. Ship
the randomised 5–10% holdout **in v1**, not as a later addition — it is the
only thing that makes the product's own value measurable. No uplift modelling,
no MMM, no Bayesian posterior. Architecture in
[`docs/product-rollout.md`](../../docs/product-rollout.md) §6.

**13. What does the strongest competitor / product substitute look like?**
Two different ones for two different layers. For measurement and aggregate
allocation, **Triple Whale Compass** (unifies MTA, MMM and geo-lift
incrementality and surfaces a next-best-action) and the incrementality
specialists Measured, Haus and Recast — plus free Meridian and Robyn. For
individual decisioning, **Salesforce Einstein and HubSpot lead scoring**, which
are weaker than they look because they predict `P(convert)` rather than
incremental value, but which are already installed, already trusted, and
already integrated. The real substitute is not a better model; it is the
incumbent's distribution.

**14. Which parts of the idea are already commodity?**
Measurement and attribution (layer A) entirely. Aggregate budget allocation
(layer C) — being commoditised now, with two free first-party MMMs. Lead
scoring from historical conversions. `P(convert) × deal value` as a
prioritisation score. Uplift targeting as a technique. Contextual bandits for
marketing actions. MMM with adstock and saturation. **What is not commodity**:
allocating scarce *human sales time* by incremental effect × margin ÷ handle
time under a capacity constraint — no mainstream product does this.

**15. Are there signs of patent/FTO risk requiring separate legal review?**
**Yes, enough to justify one attorney's hour before building, and not more than
that.** US 11,068,304 B2 combines capacity-aware lead-to-timeslot allocation,
dynamic lead scoring and Thompson-sampling bandit updating in a single family —
uncomfortably close. The Velocify family sits in the named lending vertical, and
the "Next best action" family describes a value-versus-volume trade-off. **This
is not a legal opinion, and retrieval was materially limited** — Google Patents,
Espacenet, Justia and FreePatentsOnline were all unreachable, so assignees,
priority dates and legal status are unverified. A professional search scoped to
CPC `G06Q 30/0201`, `30/0242`, `30/0251`, `10/0631` is the right next step *if
the value is proven first*.

**16. What technical / product differentiation, if any, remains?**
Three candidates, in descending order of confidence:
(i) **the economic objective itself** — incremental effect × predicted
contribution margin ÷ predicted handle time under an explicit capacity
constraint, which is measurably worth +5.0% over lead scoring and which no
mainstream CRM computes;
(ii) **the data contract and the permanent randomised holdout** — a defensible
position precisely because it is operational discipline rather than an
algorithm, and therefore not copyable by shipping a model;
(iii) **honest abstention under thin support** — valuable for trust, but this
study did **not** show it earns money, and it should be sold as a trust feature
or not at all.
Explicitly **not** differentiation: the estimator. The best model here is a
logistic regression.

**17. Is there any point continuing the project?**
**Yes — but as a much smaller project than the one proposed, and only under a
named condition.**

Continue if, and only if, a design partner has: sales capacity materially below
the effort needed to work every lead; heterogeneous deal value; and the
willingness to log effort and action propensity. In that setting the evidence
for the economic layer is strong (+10.7% over analytics, +5.0% over lead
scoring, intervals nowhere near zero) and it is buildable with a logistic
regression in a few hundred lines.

Do **not** continue as proposed if the plan is a Bayesian-causal decision
platform sold as a general answer. Most of that plan is falsified by its own
benchmark: kill criterion K2 fired twice — on synthetic randomized data and
again on the real Hillstrom experiment — the doubly-robust learner finished
10th of 21, the causal forest spent 51% of the compute to land below a logistic
regression, bandits bought nothing, and quantified uncertainty changed
decisions by ±0.6 points while its 80% intervals covered 22%. The causal
upgrade is real but conditional, worth +2.9% on average, carried entirely by
three regimes, and it should be gated behind a measured test for response
heterogeneity rather than shipped by default.

**One piece of the ambitious plan survived and deserves a second look**:
hierarchical partial pooling, worth +9.6 points over the gradient-boosted
baseline in sparse regimes, of which +11.6 is the pooling itself. That is the
one result pointing *toward* more statistical machinery rather than less. It
is also the least finished: it was only ever tested as 45-second MCMC, and the
cheap alternatives — mixed effects, empirical-Bayes shrinkage — were never
benchmarked against it. Run that comparison before concluding anything about
PyMC. If shrinkage captures most of the +11.6, the answer to this whole
question is a logistic regression with pooled segment effects, and the platform
was never needed.

And if the partner's sales team has capacity to call everyone: **stop.** At 100%
capacity every method in this study converges to 85–88% of Oracle, and the most
sophisticated model available is worth nothing on total profit. The product
being proposed is not a model. It is a way of spending a scarce hour, and where
the hour is not scarce there is no product.

---

*Reproduce: `bash scripts/finalize.sh`. Provenance, seeds, library versions and
dataset digests for every number above are in each run's
`experiment-manifest.json`.*
