# Data contract — what to start collecting today

Audience: whoever owns the CRM and the ad accounts at a design-partner
business, and whoever builds the HighLevel/CRM integration.

Purpose: in 3–12 months, this dataset must be able to answer *causal* and
*policy* questions, not just "what happened". Most CRM exports cannot, and the
reason is almost always one of four omissions:

1. only the **current state** is stored, not the event history;
2. **decisions are not logged** — you know what happened, not what was
   recommended or how the action was chosen;
3. **agent effort is not measured**, so profit per agent-hour is uncomputable;
4. **money is recorded as opportunity value**, not realised contribution.

Fix those four and almost everything else is recoverable. Miss them and no
model in this repository can help you, because the information was never
written down.

**Privacy.** Nothing here needs PII. Every identifier below is a pseudonymous
key. Names, phone numbers and e-mail addresses should stay in the operational
system and never enter the analytical store. See §79 of the brief and the
"Separation" section at the end.

---

## Priority order

If you can only do part of this, do it in this order. The ordering is by how
much analysis each unlocks per unit of engineering effort.

| Priority | What | Why it is first |
|---|---|---|
| **P0** | Immutable funnel events with timestamps | Nothing works without it. Enables funnel economics, delays, censoring. |
| **P0** | Realised financial outcome per deal | Without contribution margin, "value" is a guess. |
| **P0** | Agent effort per lead (minutes, attempts) | Without it you cannot compute profit per agent-hour — the metric that actually decides allocation. |
| **P1** | Decision log with action propensity | Unlocks off-policy evaluation and every causal method. This is the single highest-leverage *new* thing most businesses are not doing. |
| **P1** | Spend at campaign × day granularity | Unlocks acquisition economics and MMM. |
| **P2** | Standardised loss/disqualification reasons | Turns "lost" into something a model can learn from. |
| **P2** | Randomised holdout / exploration slice | Turns observational data into identified causal data. |

---

## 1. Identity

| Field | Type | Notes |
|---|---|---|
| `lead_id` | string | Stable, unique per lead record. |
| `person_id` | string | **Pseudonymous** person key. Distinct from `lead_id`: the same human often enters twice. Required for de-duplication and for honest train/test splits. |
| `opportunity_id` | string | Nullable until an opportunity exists. |
| `account_id` | string | The business/tenant, for multi-client agencies. |

> Duplicate humans across a train/test split silently inflate every model's
> score. `person_id` is what makes that detectable.

## 2. Acquisition

| Field | Type | Notes |
|---|---|---|
| `source`, `channel`, `campaign_id`, `ad_group_id`, `ad_id`, `creative_id` | string | Platform identifiers, not display names — names get edited. |
| `landing_page` | string | |
| `utm_source/medium/campaign/term/content` | string | As captured, unmodified. |
| `first_touch_channel`, `last_touch_channel` | string | **Store both.** Storing only one destroys the ability to compare attribution rules later. |
| `acquired_at` | timestamp (UTC) | |

## 3. Spend

| Field | Type | Notes |
|---|---|---|
| `date` | date | Daily is enough; hourly is better for geo tests. |
| `channel`, `campaign_id` | string | Must join to the acquisition keys above. |
| `spend`, `impressions`, `clicks` | numeric | Raw, summable quantities only. |

> Never store derived rates (CTR, CPC, ROAS) as inputs. Store the numerators
> and denominators and let the model compute the ratio — Meridian's
> documentation makes the same point, and it matters because a ratio cannot be
> re-aggregated correctly.

## 4. Funnel events — immutable, append-only

**This is the part most CRMs get wrong.** Store a row per transition, never
overwrite a status field.

| Field | Type | Notes |
|---|---|---|
| `event_id` | string | Unique. |
| `lead_id` | string | |
| `event_type` | enum | See below. |
| `occurred_at` | timestamp (UTC) | When it happened in the real world. |
| `recorded_at` | timestamp (UTC) | When your system learned. **Both**, because the gap is what lets you reconstruct what was knowable at decision time. |
| `previous_state`, `new_state` | enum | |
| `reason_code` | enum | Standard taxonomy, below. |
| `actor_type` | enum | `human` / `automation` / `system`. |
| `actor_id` | string | Pseudonymous agent key. |

Minimum event types:

```
lead_created, first_contact_attempt, contact_connected, qualified,
disqualified, appointment_set, appointment_held, no_show,
application_started, application_submitted, approved, declined,
funded_or_won, lost, reopened
```

> `recorded_at` vs `occurred_at` is not pedantry. Without it you will train
> models on information that had not arrived yet at the moment the decision was
> made, and your backtest will look wonderful and deploy terribly.

## 5. Sales effort — the field nobody collects

| Field | Type | Notes |
|---|---|---|
| `assigned_agent_id` | string | Pseudonymous. |
| `attempt_number` | int | |
| `call_started_at`, `call_ended_at` | timestamp | |
| `connected` | bool | Dialled ≠ reached. |
| `talk_seconds` | int | |
| `wrap_up_seconds` | int | Post-call admin. Frequently 30–50% of true handle time. |
| `sms_count`, `email_count` | int | Per lead, per period. |
| `manual_task_seconds` | int | Research, document chasing. Estimate if not tracked. |

**Total handle time per lead is the denominator of the only metric that
matters under capacity: net contribution per agent-hour.** If you record one
new thing because of this document, record this.

## 6. Qualification / loss reason taxonomy

Free-text reasons are worthless for modelling. Use a closed list and let
agents add free text *in addition*:

```
not_reached, bad_contact_details, duplicate, spam_or_test,
not_interested, wrong_product, wrong_geography,
failed_prequalification, insufficient_documents, credit_ineligible,
price_objection, chose_competitor, withdrew, no_show,
declined_by_provider, expired, unknown
```

## 7. Economics — realised, not hoped-for

| Field | Type | Notes |
|---|---|---|
| `gross_deal_value` | numeric | Headline number. |
| `realised_revenue` | numeric | What was actually invoiced/collected. |
| `commission_paid`, `vendor_cost`, `processing_cost`, `servicing_cost` | numeric | |
| `refund_amount`, `clawback_amount` | numeric | With `occurred_at` — clawbacks arrive late and silently invert unit economics. |
| `net_contribution` | numeric | `realised_revenue − variable costs`. |
| `currency` | string | |

> Do not conflate **opportunity value** with **realised net contribution**.
> Optimising on opportunity value systematically over-weights big deals that
> never close, which is how a "high-value lead" model ends up losing money.

## 8. Decision log — the unlock for causal analysis

Without this table you are limited to correlational analysis forever. With it,
off-policy evaluation, uplift modelling and bandits all become possible.

| Field | Type | Notes |
|---|---|---|
| `decision_id` | string | |
| `lead_id`, `decided_at` | | |
| `model_version`, `policy_version` | string | Exact artefact identifiers. |
| `available_actions` | list | What the policy *could* have chosen. |
| `recommended_action` | enum | |
| `actual_action` | enum | Humans override. Record both. |
| `score_at_decision` | numeric | The score as of that moment, not recomputed later. |
| `action_propensity` | numeric in (0,1] | **P(chosen action \| context) under the policy in force.** |
| `assigned_agent_id` | string | |
| `override_reason` | enum | Nullable. |

### Why `action_propensity` is the most valuable column in this document

It is the difference between "we think calling helps" and "we can prove how
much, and we can evaluate a policy we never deployed".

- If every action is chosen deterministically, propensity is 1 and off-policy
  evaluation is **not identified** — no amount of cleverness recovers it.
- If the policy is stochastic and you log the probability, IPS/SNIPS/DR give
  unbiased estimates of what a *different* policy would have earned.
- It costs one float per decision.

It must be the probability **as of the decision**, written at decision time.
Reconstructing it afterwards from a model re-run does not work and is not the
same quantity.

## 9. Exploration slice — how to make the data causal

Deterministic policies create a feedback loop: the model recommends the
leads it likes, only those get worked, only their outcomes are observed, and
the next model "discovers" that the model's favourites are the best leads.
This benchmark's `policy_feedback_loop` regime exists to show what that does
to identification.

The fix is small and cheap:

- Hold out **5–10%** of leads to a randomised action assignment, or
- add mild randomisation to the ranking (e.g. epsilon-greedy with ε≈0.05, or
  Thompson sampling), and **log the resulting propensity**.

Keep the exploration slice permanently, not just during a pilot. It is the
cost of being able to measure anything, and it is far cheaper than the
alternative (discovering after 18 months that your model has been grading its
own homework).

---

## Separation of operational identity and analytical features

Two stores, one boundary:

| Operational store | Analytical store |
|---|---|
| Names, phones, e-mails, addresses | none of it |
| Used to actually contact people | `person_id`, `lead_id` only |
| Access-controlled, retention-bound | Pseudonymous, safe to model on |

Models in this repository need **zero** PII: no raw phone, e-mail or name is
used as a feature anywhere. Geography should enter as a coarse region code,
not a postcode, unless the vertical genuinely requires finer granularity.

## Lending-specific limit

If the vertical is lending, this system allocates **marketing and sales
effort**. It does not decide who gets credit. Credit eligibility must arrive
as an **outcome of the existing, legitimate underwriting process** and be
treated as an input feature or an outcome label — never as something this
system predicts in order to grant or deny. That boundary is both a legal
exposure question and a product-scope question, and blurring it would turn a
sales-efficiency tool into a regulated credit decisioning system.

## Minimum viable version

If the above is too much for a first integration, this is the irreducible set:

```
lead_id, person_id, acquired_at, campaign_id, channel,
event_type, occurred_at, recorded_at,          -- append-only
assigned_agent_id, talk_seconds, wrap_up_seconds, attempt_number,
funded_at, realised_revenue, variable_costs, refund_amount,
decided_at, recommended_action, actual_action, action_propensity,
date, campaign_id, spend, impressions, clicks  -- spend table
```

Everything else can be added later. These cannot be back-filled, because they
were never recorded.
