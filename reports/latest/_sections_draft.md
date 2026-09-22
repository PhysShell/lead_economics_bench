# Draft sections (working file)

Sections whose content does not depend on the pending benchmark numbers.
Merged into `report.md` at assembly time. Not the deliverable.

---

## Dataset evidence

| Dataset | Kind | Unit | n | Treatment | Outcome | Known value? | Known cost? | Licence |
|---|---|---|---|---|---|---|---|---|
| Synthetic lead economy (20 regimes) | fully synthetic, known potential outcomes | lead | configurable (2k–100k used) | none / call, randomized or confounded by regime | funded | yes (true expected contribution) | yes (true handle time) | this repo |
| Synthetic MMM (6 regimes) | fully synthetic, known response curves | week | 30–260 weeks | continuous spend, 5 channels | revenue | yes | yes | this repo |
| Synthetic campaign corpus (PIE track) | fully synthetic, known incrementality | campaign | 400 | which campaigns ran an experiment | measured iROAS | yes | n/a | this repo |
| **Hillstrom / MineThatData** | **real randomized experiment** | customer | 64,000 | Mens / Womens e-mail / none, 1/3 each | visit, conversion, spend | spend only | no | public release by the author |
| **Criteo-UPLIFT v2.1** | **real randomized experiment** | user | 13,979,592 | randomized ad exposure, P(treat)=0.849 | visit, conversion | no | no | **CC BY-NC-SA 4.0, non-commercial** |

Verified statistics, computed on load rather than quoted:

- **Hillstrom**: 64,000 rows, 66.7% treated in the any-e-mail split. Visit rate
  16.70% treated vs 10.62% control (naive lift +6.09pp). Conversion 1.068% vs
  0.573% (+0.495pp). Mens arm lifts visits more than Womens (+7.66pp vs
  +4.52pp).
- **Criteo v2.1**: 13,979,592 rows exactly, matching the published figure; the
  loader raises if the row count differs, which is how it refuses the leaked
  v2.0. In a deterministic 500k subsample: 84.95% treated, conversion 0.298%
  treated vs 0.206% control, visit 4.80% vs 3.86%.

Both real datasets pass the adversarial checks (`leadbench.evaluation.diagnostics`):
no Simpson reversal, no target leakage, adequate overlap. That is what a
genuine randomized experiment should look like, and it is a useful calibration
for what the synthetic regimes flag.

**A note on Criteo's `exposure` field.** It marks users actually shown an ad
and correlates only 0.074 with `treatment`. It is a *post-treatment* variable:
conditioning on it, or using it as a feature, would introduce collider bias.
It is loaded but never used as a feature or outcome here.

**A licensing point that matters for a commercial programme.** Criteo-UPLIFT is
CC BY-NC-SA 4.0 — **non-commercial**. It can be used to evaluate methods. It
cannot be used to train a model that ships in a product.

---

## Data collection recommendation

The full specification is `docs/data-contract.md`. The short version, in
priority order, is that four omissions are what make most CRM exports useless
for this question, and all four are cheap to fix prospectively and impossible
to fix retrospectively:

1. **Immutable funnel events with both `occurred_at` and `recorded_at`.** Storing
   only the current stage destroys the ability to reconstruct what was
   knowable at decision time. Storing only one timestamp destroys it more
   subtly, by letting you train on information that had not arrived yet.
2. **Agent effort per lead**: talk seconds, wrap-up seconds, attempt count.
   Without it, profit per agent-hour — the metric that actually decides
   allocation under capacity — cannot be computed at all.
3. **Realised net contribution, not opportunity value**, including refunds and
   clawbacks with their own timestamps. Optimising on opportunity value
   systematically over-weights big deals that never close.
4. **A decision log with `action_propensity`.** One float per decision. It is
   the difference between "we think calling helps" and "we can estimate what a
   policy we never deployed would have earned". Without it, off-policy
   evaluation is not identified, and no amount of modelling recovers it.

Nice-to-have, in rough order: standardised loss-reason taxonomy; agent skill
and tenure; creative/landing-page identifiers; geo at region granularity;
call recordings' derived features; competitor-quote flags.

**Not needed**: any PII. No model in this repository uses a name, phone number
or e-mail address. Keep operational identity and the analytical feature store
separate.

---

## Next real-world experiment

Full protocol in `docs/product-rollout.md`.

**Phase 1 — shadow mode, 4–8 weeks.** Freeze the model, log every
recommendation with its score and model version at decision time, do not show
it to agents, do not retrain inside the window. This validates calibration and
the data contract. It **cannot** establish causal value: if the incumbent
process is deterministic, the leads the model wanted to call but nobody called
have no observed outcome, and no estimator recovers it.

**Phase 2 — randomised slice, permanently.** 5–10% of leads to randomised
assignment, or epsilon-greedy with ε≈0.05, with the propensity logged. Keep it
after the pilot: it is the cost of being able to measure anything again.

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
readout as a slower confirmation, use CUPED and stratification, and do not
promise a partner a statistically convincing profit result in six weeks on
3,000 leads — that promise cannot be kept at this variance.

---

## Market landscape (summary)

Full version: `docs/research/market-landscape.md`. Accessed 2026-09-22; vendor
capability claims marked *vendor-reported*.

- **Measurement (layer A) is a commodity.** Roistat, Calltouch, Triple Whale,
  HockeyStack, Northbeam, Rockerbox all connect spend → CRM → revenue.
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

The capability gap at layer B is real. The uncomfortable corollary is that a
gap persisting in a large, competitive market is evidence about value, not
only about opportunity — which is what the benchmark exists to test.

---

## Patent / prior-art summary

Full version, with an explicit retrieval-limits note:
`docs/research/patent-landscape.md`. **Not a legal opinion, not an FTO
analysis.**

**Retrieval was materially limited from this environment**: Google Patents
returned 503 on every attempt, Espacenet and Justia 403, FreePatentsOnline
failed TLS, and the PatentsView legacy API no longer returns JSON. USPTO grant
PDFs download but are scanned images with no text layer. Claim content below
is therefore paraphrased from search-surfaced excerpts and **assignees,
priority dates and legal status are not independently verified.**

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

**Possibly narrower, worth an attorney's hour** — and only after the value is
proven, not before: (1) allocating a scarce human sales-time budget by
*estimated incremental effect × predicted contribution margin ÷ predicted
handle time* under a capacity constraint; (2) an abstention mechanism keyed to
posterior width and logged-propensity support; (3) joint allocation across
media budget *and* sales capacity in one objective.

Recommended next step if the programme continues: a professional search scoped
to CPC `G06Q 30/0201`, `30/0242`, `30/0251`, `10/0631` and the assignees named
above. Cheap relative to building on a claim someone else owns.

---

## Open-source landscape (summary)

Full version: `docs/research/open-source-landscape.md`. Versions and dates read
from the PyPI JSON API on 2026-09-22.

Healthy and safe to depend on: **EconML 0.17.0**, **PyMC 6.3.2**,
**PyMC-Marketing 1.1.0**, **CausalML 0.17.0**, **CausalPy 0.9.0**,
**Google Meridian 2.0.0**.

Do not build on: **scikit-uplift 0.5.1** (last release 2022-08-11),
**upliftml 0.0.2** (2022-11-22), **Open Bandit Pipeline 0.5.7** (2023-04-14).
This repository uses scikit-uplift only for two small, stable functions and
implements OPE and the bandits itself (~270 lines, tested).

Two concrete version facts found by running things rather than reading about
them:

1. **PyMC-Marketing 1.1.0 requires Python ≥3.12**, so the 3.11 benchmark
   environment resolves to 0.19.2. A separate 3.12 environment confirms
   pymc 6.2.0 + pymc-marketing 1.1.0 install cleanly.
2. **PIE 1.1.0 is broken against the current pymc-bart (0.13.1)**: it imports
   `pymc_bart.split_rules`, removed in 0.13 for the Rust backend. The guarded
   import sets `pmb = None`, so it surfaces much later as a misleading
   *"pymc-bart is required"* error even when pymc-bart is installed and
   imports fine. **Working pin: `pymc-bart==0.12.0`.**

**On PIE specifically (§17).** PIE is *not* lead scoring and must not be sold
as such. It fits a BART model on the corpus of campaigns that **did** run an
incrementality experiment, learning campaign-features → **measured**
incrementality, then predicts a posterior for campaigns that never ran one.
The unit is a campaign, the label is an experimental readout, and it cannot
exist without a corpus of past experiments. It is benchmarked here on its own
claim, in its own track.

---

## What could still overturn these conclusions

1. **The synthetic DGP is our model of the world.** A method whose structure
   matches the generator has an advantage no deployment enjoys. Mitigated by
   the two real randomized datasets and by deliberately giving the Bayesian
   candidate a misspecified linear-logistic form rather than the true
   four-stage funnel — but not eliminated.
2. **The economics are parameterised, not measured**: $38/agent-hour, ~8 min
   median handle time, 32% margin, 4% clawback. Conclusions that turn on the
   *ratio* of agent cost to contribution margin should be re-checked against a
   real partner's numbers.
3. **Real-data tracks test targeting, not the full economic problem.**
   Hillstrom and Criteo have no agent-time or margin data, so the constraint
   there is a send budget and the value per outcome is a preregistered
   constant.
4. **Eight seeds separate large effects from noise, not small ones.** That is
   why the decision rule requires clearing a preregistered practical threshold
   rather than merely achieving significance.

---

## FINAL TABLES (suites complete; transcribe into report.md)

### Online track (RQ7) — 4 regimes x 3 seeds, 20k leads, 8 periods, 25% capacity

% of Oracle's achievable gain:

| competitor | concept_drift | easy_randomized | policy_feedback_loop | propensity_not_uplift | MEAN |
|---|---|---|---|---|---|
| retrained_propensity_ev | 59.1 | 58.1 | 58.3 | 29.7 | **51.3** |
| static_propensity_ev | 60.1 | 57.5 | 57.4 | 29.4 | **51.1** |
| bandit_thompson | 53.7 | 55.8 | 57.0 | 35.0 | 50.4 |
| bandit_greedy_online (no exploration) | 51.4 | 53.9 | 57.1 | 38.8 | 50.3 |
| bandit_linucb | 50.6 | 52.8 | 57.3 | 38.2 | 49.7 |
| bandit_epsilon_greedy | 47.1 | 49.3 | 53.0 | 33.7 | 45.8 |
| random | 22.5 | 25.7 | 25.7 | 24.1 | 24.5 |

Paired differences vs the frozen offline model: thompson −0.7, greedy −0.8,
linucb −1.4, epsilon-greedy −5.3, periodic retraining **+0.2**.

Three independent readings, all pointing the same way:
- **online updating of a strong learner buys nothing**: retrained vs frozen = +0.2;
- **exploration buys nothing**: linucb/thompson/epsilon vs greedy_online (same
  linear learner, only the exploration rule differs) = −0.6 / +0.1 / −4.5;
- **learner capacity beats online-ness**: the linear bandits lose to a boosted
  offline model even under concept drift (−6 to −13).

The one place bandits win is `propensity_not_uplift` (+4 to +9), where the
offline Propensity-EV is *structurally* biased (it values the control arm at
zero) and the bandit, learning arm-specific outcomes from feedback, does not
inherit that bias.

**Confound to state plainly**: the bandits are linear and the offline models
are gradient-boosted. The clean within-learner comparison is greedy_online vs
the exploring bandits, and the clean within-model comparison is frozen vs
retrained. Both say the same thing as the cross-family one.

### MMM track — 5 regimes x 4 seeds (6th regime pending)

% of the Oracle's gain **over an equal budget split** (0 = equal split, 100 = Oracle):

| candidate | high_collinearity | low_signal | smb_short | standard | very_short | MEAN |
|---|---|---|---|---|---|---|
| pymc_marketing_mmm **calibrated** | 44.6 | 73.3 | 90.0 | 44.0 | 78.2 | **+66.0** |
| ridge_adstock_saturation | 39.2 | −4.8 | 3.8 | 56.3 | 67.0 | +32.3 |
| equal_allocation | 0 | 0 | 0 | 0 | 0 | 0 |
| pymc_marketing_mmm (uncalibrated) | 36.8 | −2.6 | 18.0 | **−149.4** | −1.3 | **−19.7** |
| naive_ols | −1276 | −1264 | −1333 | −1264 | −1228 | −1273 |
| reported_roas (the dashboard) | −1413 | −1399 | −1417 | −1399 | −1423 | **−1410** |

Per-channel ROI error (MAPE, 1.00 = 100% wrong): calibrated MMM **0.26**,
reported_roas 0.60, ridge 0.88, **uncalibrated MMM 1.83**.

Channel **rank** correlation with true ROI: reported_roas **0.70** (best
non-oracle), calibrated MMM 0.36, ridge −0.10, **uncalibrated MMM −0.43**.
(`equal_allocation`'s value here is an artefact — it does not estimate ROI at
all — and should be ignored.)

The two findings that matter:

1. **Following your ROAS dashboard destroys value.** It is ~14x worse than the
   entire achievable gain over an equal split, because it treats returns as
   linear and pours budget into whichever channel over-claims last-touch
   credit. Note it has the *best* channel rank correlation: ranks are not
   marginal returns, and allocation depends on marginal returns.
2. **Experiment calibration is what makes MMM work.** The same PyMC-Marketing
   model goes from −19.7 (worse than an equal split, with an *inverted* channel
   ranking and 183% ROI error) to +66.0 with lift-test calibration. An
   uncalibrated MMM on 156 weeks of data was worse than splitting evenly.

### Data-size curve (RQ9) — % of Oracle gain, 3 regimes x 5 seeds, 25% capacity

| regime | candidate | 2k | 5k | 10k | 25k | 50k | 100k |
|---|---|---|---|---|---|---|---|
| capacity_value_het | dr_learner | 31.5 | 45.3 | 50.3 | 52.1 | 62.4 | **70.1** |
| | t_learner | 26.1 | 48.7 | 44.3 | 53.7 | 60.8 | 69.2 |
| | propensity_ev_gbm | **39.2** | 49.1 | 46.2 | 44.7 | 42.1 | 49.8 |
| | hist_profit_per_agent_hour | 21.1 | 26.7 | 25.4 | 37.5 | 29.4 | 27.6 |
| | lead_score_gbm | 20.7 | 32.6 | 25.6 | 27.0 | 20.3 | 28.1 |
| propensity_not_uplift | t_learner | 32.6 | 38.5 | 36.8 | 46.9 | 43.7 | **54.2** |
| | propensity_ev_gbm | 33.9 | 45.3 | 35.0 | 39.1 | 37.6 | 41.5 |
| | hist_profit_per_agent_hour | **43.5** | 33.2 | 34.1 | 52.1 | 41.2 | 35.7 |
| sparse | propensity_ev_gbm | **48.4** | 55.0 | 57.6 | 58.7 | 64.9 | **66.0** |
| | t_learner | 29.3 | 49.3 | 52.3 | 52.6 | 63.1 | 62.9 |
| | lead_score_gbm | 48.2 | 50.0 | 51.7 | 54.3 | 59.9 | 60.0 |
| | hist_profit_per_agent_hour | 44.3 | 40.1 | 42.0 | 42.1 | 44.5 | 46.0 |

Crossover: below ~5–10k resolved leads the simple economic model is as good or
better than anything causal; above ~25k the causal learners pull ahead **in the
heterogeneous-response regimes only**. Analytics baselines are flat in N — more
data does not help a campaign-level average.

### Capacity curve (RQ4b / §35) — the single most important product chart

% of Oracle gain, `capacity_value_heterogeneity`:

| candidate | 5% | 10% | 25% | 50% | 100% |
|---|---|---|---|---|---|
| dr_learner | **35.5** | 41.0 | 65.4 | 82.2 | 87.8 |
| t_learner | 33.1 | 40.9 | 61.9 | 80.0 | 84.7 |
| propensity_ev_gbm | 26.1 | 34.1 | 48.9 | 67.8 | 84.6 |
| hist_profit_per_agent_hour | 7.4 | 14.3 | 30.8 | 47.5 | 87.2 |
| lead_score_gbm | 4.9 | 9.8 | 23.6 | 52.3 | 87.7 |
| random | 6.8 | 10.7 | 22.0 | 43.2 | 86.1 |

**The entire value of the decision engine lives in scarce capacity.** At 5%
capacity a causal model captures 5–7x what lead scoring or an analytics
baseline does; at 100% capacity every method converges to ~85–88% and the
model is worth nothing on total profit. At full capacity the advantage shows
up instead in *efficiency*: $4,930 net per agent-hour for dr_learner vs $3,693
for random (+33%), because the model declines to spend time on negative-uplift
leads.

### PIE campaign-level track (§17) — additive-truth variant, 3 shares x 3 seeds

RMSE against true campaign incrementality (lower better) / % of oracle in a
top-quartile selection:

| candidate | 15% measured | 35% measured | 60% measured |
|---|---|---|---|
| ridge_on_features | **0.291** / 94.5 | **0.274** / 88.9 | **0.196** / 95.9 |
| pie_bart | 0.340 / 89.5 | 0.316 / 90.0 | 0.273 / 92.6 |
| gbm_on_features | 0.493 / 61.0 | 0.430 / 82.1 | 0.374 / 83.5 |
| reported_roas | 0.473 / 90.2 | 0.479 / 90.7 | 0.498 / 90.1 |
| global_mean_measured | 0.511 / 38.9 | 0.506 / 36.2 | 0.509 / 37.4 |

PIE beats last-touch ROAS on *level* accuracy by ~30% and improves with more
measured campaigns. It loses to a ridge on the same features — but in this
variant the truth is additive in the logged features, so the ridge is
correctly specified and this is its best case. See the interaction variant.
