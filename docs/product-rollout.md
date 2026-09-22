# Shadow mode, pilot design and MVP architecture

How to take whatever survives the benchmark to a real design partner without
risking their business. Written to be executed, not admired.

## 1. Shadow mode — the first four to eight weeks

The system observes, recommends, and is **ignored**.

```
production data  ->  model  ->  recommendation  ->  LOGGED
                                                     |
       existing human/rule process  ->  actual decision  ->  executed
                                                     |
                                            outcome arrives later
                                                     |
                                        score recommendation vs actual
```

Rules that make it worth doing:

1. **Freeze the model** before the window opens. Train on history, write the
   artefact hash into the decision log, and do not retrain inside the window.
2. **Log at decision time**, not afterwards: `score_at_decision`,
   `recommended_action`, `available_actions`, `model_version`,
   `decided_at`. A score recomputed later is a different quantity.
3. **Do not reveal the recommendation to the agents.** If agents see it, they
   act on it, and the "control" process is no longer the control process.
4. **Unlock outcomes only at the end.** No peeking, no mid-flight tweaks. If
   the model is wrong, that is the result.

### What shadow mode can and cannot tell you

**Can:** predictive calibration (do leads scored 0.2 convert 20% of the time?),
ranking quality against realised outcomes, how far the recommendation differs
from what humans did, and whether the data contract is actually being
populated. That last one is usually the biggest finding.

**Cannot:** the causal value of *following* the recommendation. If the existing
process is deterministic, the leads the model wanted to call but nobody called
have **no observed outcome**, and no estimator recovers it. Off-policy
evaluation needs overlap, and a deterministic logging policy has none.

This is not a technicality that cleverness gets around. It is why step 2 below
exists, and why `action_propensity` is the highest-leverage column in
`docs/data-contract.md`.

## 2. Randomized pilot — when and how

### Entry criteria

Move from shadow to pilot only when all of these hold:

- the decision log is populated and reconciles with the CRM;
- outcome resolution lag is measured (you know how long to wait);
- shadow-mode calibration is not catastrophic (ECE within a few points);
- the partner accepts a small deliberate randomisation.

### Design

Hold out **5–10%** of leads to randomised assignment, or add mild
randomisation to the ranking (epsilon-greedy ε≈0.05, or Thompson sampling),
and **log the propensity**. Keep 90–95% on the existing policy so the
business is never materially exposed.

Keep the exploration slice **permanently**, not just during the pilot. It is
the cost of being able to measure anything ever again, and it is far cheaper
than discovering in 18 months that the model has been grading its own homework
(see the `policy_feedback_loop` regime).

### How long — the number that surprises people

Computed from this benchmark's own DGP at realistic parameters (60,000 leads,
two regimes), 80% power, α=0.05, two-sided:

| Quantity being measured | Regime `easy_randomized` | Regime `capacity_value_heterogeneity` |
|---|---|---|
| Per-lead net value: sd | $1,397 (CV 5.0) | $3,161 (CV 6.1) |
| **n per arm to detect the conversion-rate lift** | **449** | **842** |
| **n per arm to detect the full dollar uplift** | **1,951** | **7,560** |
| n per arm to detect *half* that dollar uplift | 7,805 | 30,241 |

**The operational consequence.** Conversion lift is measurable in weeks;
**profit** lift takes an order of magnitude longer, because realised deal value
is lognormal with a coefficient of variation around 5–6. A single large funded
deal moves the mean more than a hundred small ones.

Three things follow:

1. **Power the pilot on incremental conversions**, and treat the dollar
   readout as a slower, secondary confirmation.
2. **Use variance reduction**: CUPED on pre-period covariates, stratify by
   campaign and product, and consider trimming or winsorising deal value for
   the primary test while reporting the untrimmed number alongside.
3. **Be honest in the contract.** If a partner is promised a statistically
   convincing profit result in six weeks on 3,000 leads, that promise cannot be
   kept at this variance. Say so before signing, not after.

### Stopping rules, fixed in advance

- Minimum runtime stated up front; no peeking-and-stopping.
- A pre-agreed guardrail: if the treated arm's conversion rate drops by more
  than X% with a one-sided 95% bound excluding zero, stop and revert.
- The analysis plan (primary metric, covariates, exclusions) is written before
  unblinding, exactly as `docs/benchmark-spec.md` does here.

## 3. Avoiding the selection feedback loop

The failure mode:

```
model recommends high-score leads
  -> only high-score leads get worked
    -> only their outcomes are observed
      -> next model "discovers" high-score leads are best
        -> the loop tightens until the model is unfalsifiable
```

Three defences, all cheap:

1. **Exploration slice**, permanently, with logged propensities.
2. **Propensity floor**: never let any action's probability fall below ~1-2%
   for leads in scope. It costs almost nothing and preserves identifiability.
3. **Monitor overlap**: track the share of decisions whose chosen action had a
   logging probability below the floor. When that share climbs, your ability to
   evaluate anything is degrading — the benchmark reports exactly this as
   `violation_rate` in its support diagnostics.

## 4. Uncertainty UX

Do not ship `AI Score 87/100`. It invites false confidence and it is not what
the model knows. Ship the decision and its basis:

```
┌──────────────────────────────────────────────┐
│  Call this lead?              RECOMMENDED    │
│                                              │
│  Expected value of calling        +$83       │
│  80% range                  -$12  to  +$176  │
│  Est. handle time                  11 min    │
│  Value per agent-hour              +$453     │
│                                              │
│  Evidence: MEDIUM                            │
│    31 comparable leads                       │
│    4 resolved outcomes                       │
│    campaign live 18 days                     │
└──────────────────────────────────────────────┘
```

And where the evidence is thin, say so rather than inventing a number:

```
┌──────────────────────────────────────────────┐
│  Call this lead?      INSUFFICIENT EVIDENCE  │
│                                              │
│  New campaign, 6 comparable leads,           │
│  0 resolved outcomes.                        │
│  Falling back to your existing priority.     │
└──────────────────────────────────────────────┘
```

Two reasons this is not just good manners. First, it is the honest
representation of what a model with 4 resolved outcomes knows. Second, the
benchmark measures whether abstention actually pays (profit versus coverage),
so the UX is backed by a number rather than a philosophy.

## 5. Design partner profile

The ideal first partner:

- **already spends real money on ads** (so acquisition economics exist);
- **has 12+ months of CRM history** with stage timestamps;
- **logs calls/messages** with durations, not just counts;
- **records realised revenue**, including refunds and clawbacks;
- has **enough volume**: at the variance above, aim for ≥3,000–5,000 leads per
  month so a conversion-lift readout lands in a quarter, not a year;
- has **capacity that actually binds** — if reps can call every lead, the
  allocation problem does not exist and nothing here helps;
- **tolerates a 5-10% exploration slice**.

An **agency with several similar clients** is worth more than one large
advertiser: it multiplies the segments available for hierarchical pooling and
gives cross-client validation, which is the only cheap defence against
overfitting a single business's quirks.

Deal-breakers: no timestamps, no call durations, opportunity value recorded
instead of realised revenue, or a refusal to randomise anything ever.

## 6. HighLevel-first MVP architecture

Only if the evidence supports building. Verified against the HighLevel
developer marketplace documentation (accessed 2026-09-22): API v2 with OAuth
2.0, webhook subscriptions, and custom fields/values as the extension point.

```
  HighLevel sub-account
        |  OAuth 2.0 install (marketplace app, scoped)
        v
  Webhook receiver  ──►  raw event store (append-only, immutable)
   contact.create        |
   opportunity.*         v
   conversation.*     normalise to the data contract
   appointment.*         |
        |                v
        |          feature store (pseudonymous; no PII)
        |                |
        |                v
        |          model pipeline  (nightly retrain, versioned artefacts)
        |                |
        v                v
  Decision API  ◄───  policy + constrained allocator
        |                     (capacity from rep calendars)
        v
  write back:  custom field "next_best_action" + "expected_value"
               + "evidence_level"
        |
        v
  decision log (every recommendation, propensity, model version)
        |
        v
  shadow mode  ->  exploration slice  ->  measured pilot
```

Deliberately **not** in the MVP:

- **No attribution/measurement layer.** HighLevel plus the ad platforms plus
  an existing analytics tool already do this. Rebuilding it is the fastest way
  to spend a year shipping a commodity (§78).
- **No MMM.** See the benchmark's MMM results and Meridian's own stated data
  requirements; an SMB does not have the data for a trustworthy one.
- **No credit decisioning.** In lending, eligibility arrives as an *outcome* of
  the partner's existing underwriting. This system allocates marketing and
  sales effort and must not be positioned otherwise.

### Day-one value, before any model has data

A new account must see something useful in week one, or it churns before the
model is trainable. All of these are pure measurement and need no model:

- cost per lead / per qualified / per won, by campaign;
- net contribution per lead, by campaign and product;
- **sales minutes per lead** and **profit per agent-hour**, by campaign and by
  rep — almost nobody computes this, and it is frequently the single most
  surprising chart in the first review;
- funnel leakage: where leads die, and how long each stage takes;
- speed-to-first-touch distribution against outcome.

The model layer switches on later, per segment, when that segment has enough
resolved outcomes — and says INSUFFICIENT EVIDENCE until it does.
