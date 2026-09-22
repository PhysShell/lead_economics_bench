# Market landscape: what the incumbents already decide for you

The question this document answers is **not** "who are the competitors?" but
the narrower one from §48: *what level of decision capability does an existing
buyer already get for their money?* A product is only interesting if it does
something the incumbent stack cannot.

Accessed 2026-09-22. Vendor capability claims are marked **[vendor-reported]**
where they come from vendor documentation or marketing; they are not treated
as verified performance.

## The three layers again

| Layer | Question | Typical incumbent |
|---|---|---|
| **A. Measurement** | Where did the money come from? | End-to-end analytics / attribution |
| **B. Individual decisioning** | What should we do with *this* lead, now? | CRM lead scoring + routing rules |
| **C. Aggregate allocation** | Where should the next $1,000 of media go? | MMM / ROAS dashboards |

Almost every product below is strong at A, thin at B, and only recently
serious at C. The interesting question is whether the thinness at B is a gap
or a signal that B is not worth much.

## A. End-to-end analytics / attribution

| Product | Attribution | Funnel to revenue | Incrementality | Decision output |
|---|---|---|---|---|
| **Roistat** | Multi-channel, cohort analysis; 200+ integrations [vendor-reported] | Yes — ad spend → CRM deal → revenue, ROI/ROAS/CAC | Not a first-class feature | Reports; human reads and reallocates |
| **Calltouch** | Call tracking-first, 100+ integrations [vendor-reported] | Yes, strongest where calls dominate | Not a first-class feature | Reports |
| **Triple Whale** | MTA + MMM + **incrementality (GeoLift)** unified in "Compass"; explicitly reconciles the three and surfaces a "next best action" [vendor-reported] | Yes (DTC-shaped) | **Yes** — geo holdout tests, and MMM recalibrated against GeoLift iROAS | Closest thing on the market to a decision engine at layer C |
| **HockeyStack** | B2B multi-touch attribution + journey analytics | Yes | Increasingly | Reports + alerting |
| **Northbeam / Rockerbox / Measured / Haus / Recast** | MTA and/or MMM; Haus and Measured are incrementality-experiment specialists | Yes | **Yes**, as the core product | Budget recommendations at layer C |

**Read.** Layer A is a commodity, and in the DTC segment layer C is being
commoditised right now. Triple Whale's Compass in particular is doing the
"reconcile MMM, MTA and experiments into one recommendation" job that a
naive version of our idea would have claimed as novel. Building a measurement
layer would be building the thing everyone already has (§78).

## B. Individual decisioning — the thin layer

### Scoring

| Product | What the model predicts | Data requirement | Economics? | Causal? |
|---|---|---|---|---|
| **Salesforce Einstein Lead Scoring** | `P(convert)` from historical leads, with top contributing factors | **1,000 leads and 120 conversions in the trailing 180 days** for a custom model [vendor-reported] | No | No |
| **HubSpot predictive lead scoring** | `P(convert)` / buyer intent | ≥50 contacts, balanced classes [vendor-reported] | No | No |
| **Velocify (ICE Mortgage Technology)** | Lead scoring + distribution for mortgage; patented (see patent landscape) | — | Partially (prioritisation) | No |

Every mainstream scoring product is a **propensity** model. None of them
estimates the *incremental* effect of contacting the lead, none multiplies by
deal value, and none subtracts the cost of the agent minutes it is about to
spend. That is the precise gap our hypothesis claims.

Two things follow, and the second is the uncomfortable one:

1. The gap is real as a *capability* gap.
2. Whether closing it is worth money is an empirical question, and it is
   exactly what this benchmark measures. A gap in the feature matrix is not
   the same as a gap in the P&L.

### Routing and distribution

Lead routing products (LeadAngel, Chili Piper, RingLead, and the routing
inside Velocify and the major CRMs) distribute leads by **rules**: round
robin, weighted round robin, territory, account ownership, sticky assignment,
and per-rep caps [vendor-reported]. "Capacity-aware" in this market means
*do not exceed a rep's cap*, not *allocate scarce agent-hours to maximise
expected contribution margin*.

Speed-to-lead is the headline metric, and it is a good one: Chili Piper
reports that instant scheduling after a form fill raises form-to-meeting
conversion from 30% to 66.7% across ~4M form submissions [vendor-reported,
and note this is an observational comparison, not a randomized test].

**Read.** Nobody in this segment is solving a constrained optimisation
problem. They are solving a fairness-and-latency problem. That is a genuine
structural gap — and also a warning: if the profit available from solving the
optimisation problem were large and easy, one of these vendors would likely
have taken it.

## C. The GoHighLevel ecosystem specifically

HighLevel exposes a documented public API v2 with OAuth 2.0, a developer
marketplace, webhook subscriptions for real-time events, and custom
fields/custom values as the extension point for storing integration state
[vendor-reported, from `marketplace.gohighlevel.com/docs/`]. That is
sufficient for the MVP architecture sketched in the final report: OAuth
install, webhook ingestion of contact/opportunity events, an external decision
service, and write-back of a recommendation into a custom field.

What HighLevel does **not** give you for free is the thing the models need
most: a reliable, immutable event history with timestamps, logged decisions
and per-lead agent effort. See `docs/data-contract.md`.

## Competitive gap — answering §49 honestly

> *Is there a real product gap between end-to-end analytics / CRM scoring and
> a full decision engine that accounts for causal effect, margin, human sales
> cost, constraints and uncertainty?*

**As a capability gap: yes, at layer B.** No mainstream CRM scoring product
combines incremental effect × contribution margin − agent-time cost under a
capacity constraint. Routing is rule-based; scoring is propensity-based;
the two are not even connected to each other.

**At layer C: the gap is closing fast and is not ours to take.** Triple Whale,
Measured, Haus, Recast, Northbeam, plus Google Meridian and Meta Robyn as free
open-source engines, already occupy aggregate budget allocation with
incrementality calibration. Competing there means out-executing funded
specialists with better data access.

**The caveat that matters.** A capability gap persisting in a large, competitive
market is evidence about value, not just about opportunity. Before concluding
"nobody built it because nobody thought of it", the benchmark has to test the
alternative explanation: that the extra machinery does not pay for itself.
That is what the kill criteria in `docs/benchmark-spec.md` are for.

## Sources

- Salesforce, *Einstein Lead Scoring*, Salesforce Help,
  https://help.salesforce.com/apex/HTViewHelpDoc?id=einstein_sales_lead_insights.htm
  (accessed 2026-09-22).
- HubSpot predictive lead scoring documentation and secondary comparisons
  (accessed 2026-09-22).
- Triple Whale, *Incrementality Testing in Triple Whale*,
  https://kb.triplewhale.com/en/articles/12441418-incrementality-testing-in-triple-whale;
  *GeoLift 101*, https://www.triplewhale.com/blog/geolift-geo-based-incrementality-testing;
  *The Marketer's Guide to Unified Measurement with MMM, MTA, and
  Incrementality Testing*, https://www.triplewhale.com/blog/mmm-mta-incrementality
  (accessed 2026-09-22). [vendor-reported]
- Roistat and Calltouch product/integration pages and 2026 third-party
  comparisons (accessed 2026-09-22). [vendor-reported]
- LeadAngel, *LeadAngel vs Chili Piper vs RingLead*,
  https://www.leadangel.com/blog/comparison/leadangel-vs-chili-piper-vs-ringlead-lead-assignment-rules-comparison/
  (accessed 2026-09-22). [vendor-reported]
- HighLevel, *HighLevel API Documentation — Developer Portal*,
  https://marketplace.gohighlevel.com/docs/ (accessed 2026-09-22).
- ICE Mortgage Technology, *Velocify*,
  https://mortgagetech.ice.com/products/velocify (accessed 2026-09-22).
