# Layer 3, first result: the statistical winner and the business winner are different rules

**What this is.** A decision layer bolted onto Recast's published per-run
results. No new estimator, no new simulation — their 32,000 runs, plus a loss
function. Produced before writing any benchmark of our own, deliberately,
because it can kill or sharpen the hypothesis for the cost of an afternoon.

**Reproduce:** `python marketing_experimentation/scripts/business_phase_diagram.py`

---

## 1. Their numbers, recomputed from raw

First, an independent check. Recast publish `results/raw/results.jsonl`
(32,000 records, repo `getrecast/geolift-simulation-study` @ `5133d37`,
2026-06-15). Recomputing FPR and FNR from those records rather than reading
them off the prose:

| tool | FPR A1 | A2 | A3 | A4 | FNR A1 | A2 | A3 | A4 |
|---|---|---|---|---|---|---|---|---|
| `geolift` 2.7.5 | **4.6** | 4.2 | 4.9 | **3.3** | **91.3** | 91.0 | 89.3 | **95.7** |
| `google_mm` | 16.9 | 18.3 | 19.1 | 14.5 | 57.1 | 53.0 | 47.3 | 65.9 |
| `causalpy` 0.8.0 | 19.8 | 18.2 | 18.0 | 24.8 | 66.2 | 64.3 | 65.2 | 63.5 |
| `causalimpact` 1.4.1 | **27.8** | 30.0 | 28.9 | 29.5 | **37.9** | 37.2 | 34.3 | 47.8 |

1,000 null runs and 1,000 effect runs per cell; effect = +7.5%. This
reproduces their published claims exactly, which also establishes that their
artefact is usable as an external golden test.

## 2. The decision model

A method is a rule returning significant / not. With `pi` the prior that the
channel really works:

```
loss(method)  = (1-pi) * FPR * C_FP  +  pi * FNR * C_FN  +  C_test
loss(no test) = min((1-pi) * C_FP,  pi * C_FN)
```

`DO_NOT_RUN` competes on equal terms: without an experiment you act on the
prior and take whichever mistake it makes cheaper, paying no experiment cost.
The gap between the two is the value of information.

## 3. The result

At `C_FN = $500k`, `C_test = $40k`, over a grid of cost ratio
`C_FP/C_FN ∈ [0.1, 10]` and prior `pi ∈ [0.05, 0.90]`:

| rule | share of the plane it wins |
|---|---|
| **`DO_NOT_RUN`** | **87.8%** |
| `causalimpact` | 11.8% |
| `google_mm` | 0.4% |
| `causalpy` | 0% |
| `geolift` | **0%** |

Regret of committing to one rule everywhere:

| policy | mean regret | p90 | max | optimal in |
|---|---|---|---|---|
| `DO_NOT_RUN` | **$4,429** | $8,185 | $103,432 | 87.8% |
| `google_mm` | $145,448 | $286,295 | $832,025 | 0.4% |
| `geolift` | $153,313 | $348,402 | $446,080 | 0% |
| `causalimpact` | $164,858 | $422,949 | $1,344,975 | 11.8% |
| `causalpy` | $184,357 | $334,631 | $972,050 | 0% |

**And it is not an artefact of the experiment's price.** Sweeping `C_test`:

| `C_test` | `C_test/C_FN` | plane where running wins |
|---|---|---|
| $0 | 0.000 | **30%** |
| $5,000 | 0.010 | 27% |
| $20,000 | 0.040 | 20% |
| $40,000 | 0.080 | 12% |
| $80,000 | 0.160 | 5% |

**Even a free experiment is not worth running over 70% of this plane.** The
driver is not cost, it is the false-negative rates: at a +7.5% effect these
tools miss 38–91% of real effects, so the test often fails to shift the
decision away from what the prior already implied.

## 4. What this says that Recast's study does not

Recast conclude, correctly, that tool choice is a business tradeoff between
false positives and false negatives, and stop there. Pricing the tradeoff
changes three things:

1. **GeoLift is never the right answer under this loss model — 0% of cells,
   in both costings.** It is the best-calibrated tool in the study (FPR
   3–5%) and that is exactly why: a 91% false-negative rate means it
   rarely produces information, so a decision-maker who would otherwise pay
   for it is better off keeping the money. "Well calibrated" and "worth
   running" are different properties, and only the second one is a business
   question.
2. **The dominant competitor is not another estimator, it is not
   experimenting.** Any product in this space whose baseline is "which tool
   should you use" is benchmarking against the wrong opponent.
3. **A single fixed default beats every learned alternative here**, and the
   default is `DO_NOT_RUN` at $4,429 mean regret against $145k+ for any tool.
   On this evidence, the *selector* half of the hypothesis is in trouble and
   the *feasibility* half is not.

## 5. What this cannot establish

Stated before the result is quoted anywhere, because the result is
uncomfortable enough to be quoted carelessly.

- **The decision is binary.** Significant / not throws away the point
  estimate, and a real budget decision uses magnitude. This is deliberately
  the crude version: it shows the ranking is cost-dependent, not the size of
  the effect. A magnitude-aware version would favour running more often.
- **One effect size.** +7.5% is a large lift. Businesses chasing 1–2% face
  worse false-negative rates than these, which pushes further toward
  `DO_NOT_RUN` — but the point estimate would also be more informative than a
  significance flag, pushing the other way. Unresolved.
- **Recast's synthetic DGP.** Lognormal baselines, AR(1) at ρ=0.30, weekly
  seasonality, 105-day panels. Recast themselves note their DGP omits real
  geo complications and that the ranking may move on dirtier data.
- **The no-test benchmark is charitable to itself.** `min(...)` assumes the
  business acts optimally on its prior. A business with miscalibrated beliefs
  loses more by not testing than this model charges it.
- **Tools are configured as Recast configured them.** A tuned GeoLift might
  trade some of that calibration for power. Configuration is a separate axis
  and untested here.

## 6. Consequence for the research question

The three-layer framing holds up, and the weight has moved:

| layer | status after this |
|---|---|
| **1. Statistical behaviour** — FPR/FNR/coverage | occupied: Recast, Statsig, Microsoft ExP |
| **2. Regime selection** — data properties → best method | partially occupied; and this result suggests the prize may be small, since one fixed rule already wins most of the plane |
| **3. Business decision** — costs, prior, RUN/DON'T RUN | unoccupied, and **the only layer where the answer changed anything** |

The sharpest open question is no longer "which estimator wins where". It is:

> Does a business-cost-aware feasibility layer change the run/don't-run
> decision often enough, on *realistic* data regimes and with a
> magnitude-aware decision rule, to be worth building — given that a single
> fixed rule already achieves $4,429 mean regret on the crude version?

That question has a preregisterable answer and a cheap first test, and it is
a much narrower claim than the brief started with.
