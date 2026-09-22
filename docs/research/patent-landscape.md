# Patent / prior-art landscape (preliminary)

> **This is not a legal opinion and not a freedom-to-operate analysis.** It is
> an engineering-led preliminary scan to answer two product questions: which
> parts of the idea are obviously old, and whether anything here warrants
> paying a patent attorney. Independent claims, not abstracts, are what
> matter, and independent claims are exactly what this environment could only
> partially retrieve — see the honesty note below.

Search date: **2026-09-22**.

## Honesty note on retrieval — read this before trusting any row

Primary patent full-text sources were largely **unreachable from this
execution environment**:

| Source | Result |
|---|---|
| `patents.google.com` | HTTP 503 on every attempt, via both the fetch tool and `curl` with a browser UA |
| `worldwide.espacenet.com` | HTTP 403 |
| `patents.justia.com` | HTTP 403 |
| `freepatentsonline.com` | TLS handshake failure |
| `api.patentsview.org` (legacy) | returns the SPA shell, not JSON; the current API needs a key |
| `image-ppubs.uspto.gov/.../downloadPdf/<number>` | **works** — but the grant PDFs are scanned images with no text layer |

USPTO grant PDFs were downloaded successfully and OCR (tesseract) was
attempted on the claim pages of the most relevant patent. Where claim text
below is not marked *"OCR-verified"* or *"quoted from primary source"*, it is
**paraphrased from search-engine-surfaced content** and must be re-verified
before any decision rests on it.

Consequently: **assignees, priority dates, legal status and expiry dates below
are not independently verified.** Anything load-bearing needs a professional
search. This is stated plainly rather than presented as a finished chart,
because a confident-looking patent table that nobody verified is worse than no
table.

## Candidate families

Ordered by how close they sit to the proposed system.

### 1. US 11,068,304 B2 — "Intelligent scheduling tool" — **closest hit**

*Retrieval: PDF obtained from USPTO; claim content below is paraphrased from
search-surfaced excerpts of the claims.*

Described elements, as surfaced:

- receive lead information;
- determine **connectivity rate predictions** with a connectivity prediction
  model (probability of actually reaching the lead);
- **allocate leads to timeslots** based on connectivity predictions **and
  available resources**;
- **prioritise leads** using a dynamic lead scoring model;
- apply a **contextual bandit** machine-learning process (Thompson sampling
  named as an example) to update the connectivity prediction model —
  i.e. explicit exploration/exploitation.

This is uncomfortably close to several things our design treats as
differentiators at once: capacity-aware allocation of sales contact attempts,
per-lead scoring, and online bandit updating of the model that drives it.

**Where it appears to differ.** The surfaced claim language is about
*connectivity* (probability of reaching a lead in a timeslot) and *scheduling*
— not about the **incremental causal effect** of contacting a lead, not about
**expected contribution margin**, and not about subtracting **agent-time cost**
to maximise profit per agent-hour. Whether that distinction survives a reading
of the actual independent claims is exactly what a professional search must
check.

### 2. Velocify lead-scoring family — US 2014/0149178 A1, US 2017/0237859 A1

Titled "Lead scoring"; assignee surfaced as **Velocify, Inc.**, now part of
**ICE Mortgage Technology** (Velocify was acquired by Ellie Mae in 2017).
Directly in the lending vertical named in the brief. Status of each member
(granted / abandoned) **not verified**.

Relevance: lead scoring and distribution in mortgage. Apparent difference:
scoring/prioritisation, not economic optimisation under a resource constraint.

### 3. "Next best action" family — US 9,420,100 B2, US 2015/0030151 A1, RE 47,652

Next-best-action for contact-centre agents: selecting an offer to present,
with a described "Value versus Volume" mechanism that trades **likelihood of
acceptance** against **financial benefit**, and projected financial value
computed from ARPU, monthly fees and estimated offer lifetime.

Relevance: **high, conceptually.** `probability × monetary value` for choosing
an action for a specific customer is plainly old art. The reissue (RE 47,652)
signals the family was actively maintained. Apparent difference: offer
selection per contact, rather than allocation of a scarce agent-hour budget
across a lead population, and no causal/incremental estimand.

### 4. US 11,915,262 — budget-constrained deep Q-network for campaign allocation

Allocating an advertising campaign within a fixed predefined budget over a
duration to maximise conversions, using reinforcement learning. Layer C.

Relevance: constrained budget allocation via RL is claimed art.

### 5. US 11,386,449 — lead budget allocation and optimisation, multi-channel platform

Surfaced as claiming priority to a provisional filed **2018-05-18** with a
non-provisional filed **2018-08-31**. Lead budget allocation across a
multi-channel campaign management and payment platform.

Relevance: "lead budget allocation" is close to our layer-C framing.

### 6. Adjacent / background

- **US 2009/0234710 A1** — customer-centric revenue management; addresses
  capacity in the sense of constrained inventory.
- **US 2014/0244351 A1**, **US 2016/0078455 A1** — CRM systems and
  CRM content/workflow enhancement; background art.

## Preliminary claim mapping

Categories per §52: `clearly absent` / `possibly analogous` / `apparently
present` / `unclear`. Assessed against *surfaced* claim language only.

| Our component | US11068304 (scheduling+bandit) | Velocify scoring | Next-best-action | Budget-allocation RL |
|---|---|---|---|---|
| Per-lead outcome probability model | apparently present | apparently present | apparently present | clearly absent |
| `probability × monetary value` decision rule | unclear | clearly absent | **apparently present** | possibly analogous |
| Subtracting **cost of agent time** from the decision value | unclear | clearly absent | unclear | clearly absent |
| **Incremental / causal** treatment effect as the estimand | clearly absent (surfaced text is predictive, not causal) | clearly absent | clearly absent | possibly analogous (RL reward is causal-ish) |
| Allocation under an explicit **agent-hour capacity constraint** | **apparently present** (timeslots + available resources) | clearly absent | clearly absent | possibly analogous (budget, not agent-hours) |
| **Contextual bandit** exploration updating the model | **apparently present** (Thompson sampling named) | clearly absent | clearly absent | possibly analogous |
| Posterior **uncertainty** driving an abstention / risk-averse decision | unclear | clearly absent | clearly absent | clearly absent |
| Joint optimisation over **media budget and sales capacity together** | clearly absent | clearly absent | clearly absent | clearly absent |

No infringement conclusion is drawn or implied, in either direction. That is a
question for a patent attorney with access to the real claim text and the file
histories.

## Prior art vs patentability — the blunt version

**Almost certainly old, treat as commodity:**

- lead scoring from historical conversions;
- `P(convert) × deal value` as a prioritisation score;
- uplift/incremental-response targeting (a large academic and industrial
  literature predates any of this — Criteo's own uplift benchmark paper is
  from AdKDD 2018, and uplift modelling in direct marketing is older still);
- contextual bandits for allocating marketing/sales actions;
- budget-constrained advertising allocation;
- marketing mix modelling with adstock and saturation.

Anyone claiming novelty on any single item above is going to have a bad time.

**Possibly narrower, and the only places worth an attorney's hour:**

1. Allocating a **scarce human sales-time budget** using an **estimated
   incremental (causal) effect** multiplied by a **per-lead predicted
   contribution margin**, net of a **per-lead predicted handle time**, solved
   as a constrained knapsack — i.e. optimising *profit per agent-hour* rather
   than *probability* or *profit per lead*. US11068304 has capacity and
   bandits, but (on surfaced text) predicts connectivity, not incremental
   profit.
2. An **abstention mechanism** that declines to automate a decision when the
   posterior is too wide or support is too thin, with the evidence threshold
   itself calibrated from logged decision propensities.
3. **Joint** allocation across media budget *and* sales capacity in one
   objective — nothing found claims both.

I would not try to manufacture novelty beyond this. On the benchmark evidence
in this repo, (1) is also where most of the measurable economic value sits, so
if any filing is worth making it is that one — but the honest sequence is
*prove the value first, file second*, not the reverse.

## Recommended next step

If the project continues past the go/no-go in the final report, commission a
professional prior-art / FTO search scoped to:

- CPC classes around `G06Q 30/0201`, `G06Q 30/0242`, `G06Q 30/0251`,
  `G06Q 10/0631` (resource allocation/planning);
- assignees: Microsoft, Salesforce, Oracle, Adobe, SAS, Velocify / ICE
  Mortgage Technology, Pegasystems, NICE, Genesys, eBay, Criteo;
- the specific combination "incremental treatment effect + agent capacity
  constraint + contribution margin".

Cost of that search is trivial next to the cost of building on a claim that is
already owned.

## Sources

- USPTO grant PDFs retrieved from
  `https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/<number>`
  (11068304, accessed 2026-09-22). Image-only; OCR attempted.
- Search-engine-surfaced excerpts of US11068304, US20170237859A1,
  US20140149178A1, US9420100B2, US11915262, US11386449 (accessed 2026-09-22).
  **Not verified against primary claim text.**
- ICE Mortgage Technology, *Velocify*,
  https://mortgagetech.ice.com/products/velocify (accessed 2026-09-22).
- Diemert, Betlei, Renaudin, Amini, "A Large Scale Benchmark for Uplift
  Modeling", AdKDD & TargetAd Workshop, KDD 2018 — cited as evidence that
  uplift modelling for advertising is established prior art.
