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
