# M9 preregistration — the cost of information

Written **before** any M9 run. The question has changed: this is no longer
about whether EVSI is computed correctly, but about

> **Is there an experiment worth running at all, and if so which one?**

    primary     ∃d : ENBS(d) > 0 ?
    secondary   d* = argmax_d ENBS(d)

with `ENBS(d) = EVSI(d) − C(d)` — expected net benefit of sampling, which is
positive exactly when the study pays for itself. `C(d)` must include the
**opportunity cost of the experimental intervention**, not only its invoice.

---

## 0. A claim of mine, withdrawn before it is built on

I said: *"a geo experiment costing more than roughly $2.6k does not pay for
itself."* That is too strong on three counts, each of which becomes a design
requirement below.

1. **It assumes a one-decision horizon.** The $2,130–$2,579 is the value of
   the signed verdict for **one** allocation decision. An experiment whose
   result informs twelve monthly budgets is worth more — though not 12×, if
   θ drifts.
2. **It compares EVSI against the wrong cost.** The relevant quantity is the
   *net economic* cost of running the experiment, not the ad spend it
   perturbs. Those differ in sign as well as magnitude.
3. **EVSI is a property of a design, not of "geo testing".** It is defined
   for a specific proposed study. One number cannot price a family.

**The defensible version, at this moment:**

> For the decision horizon represented by the current utility model, the
> modelled value of this specific sample information is on the order of a few
> thousand dollars per decision at $1M of spend under management. Any
> experiment whose *net economic cost* exceeds that value has negative ENBS
> **under this model**.

## 0a. And the dollar figure is the wrong unit

`budget_problem`'s utility is linear in `spend`, so EVPI and EVSI are
**exactly** proportional to it — verified at $0.1M through $100M, `EVPI/spend`
constant to 1e-12. The transportable quantity is therefore a **rate**:

| tool | EVSI(VERDICT) at $1M | as a share of spend |
|---|---|---|
| `causalimpact` | $2,579 | **0.258%** |
| `causalpy[y_hat]` | $2,130 | **0.213%** |
| `google_mm` | $1,504 | **0.150%** |
| `geolift` | $214 | 0.021% |
| *EVPI ceiling* | $22,120 | *2.21%* |

So "$2.6k" was never the number. **A signed verdict is worth roughly 0.15–0.26%
of the spend it governs, per decision.** A $20k experiment breaks even at
~$8–13M of governed spend for a single decision — which is a claim about
scale, and testable, in a way that "$2.6k" was not.

This supersedes the dollar framing everywhere it appears.

---

## 1. The scoping problem, found before writing the design

**The simulation contains no experiment.** `generate_panels.R:287` is the
entire treatment model:

```r
Y[post_days_idx, idx] <- Y_cf[post_days_idx, idx] * (1 + effect_pct)
```

θ is the lift that *appears*. Nothing in the DGP generates it. There is no
spend variable, no budget, no intervention and no cost. Consequences:

| design dimension | available? |
|---|---|
| **T** — duration (`pre_days`, `total_days`) | **yes**, generator parameters; changes precision, hence `q(θ)`, hence EVSI |
| **G** — number/composition of geos (`n_geos`, `n_treated`) | **yes**, same |
| **Δspend** — magnitude of the perturbation | **no** — requires a spend→lift response model the DGP does not contain |
| **direction** — increase / decrease / holdout | **no** — same, plus a revenue model for the counterfactual |

So the proposed frontier `d = (Δspend, T, G, direction)` is **half
unreachable** in this world, and the unreachable half is the half that
determines `C_intervention`. An M9-A that "uses existing designs" would be
sweeping A1–A4, which are **data regimes** (noise, outliers, autocorrelation),
not experiment designs. Sweeping them and labelling the axis "design" would be
the same category error this project has now made three times.

**This is the largest external-validity commitment in the whole track**, and
it should be made deliberately rather than discovered halfway through a run.

## 2. The reframing that makes M9-A well posed

If `C_intervention` cannot be measured from the simulation, do not assume it.
**Invert the question.** The largest net economic cost at which an experiment
still pays *is* its EVSI — no cost model required:

> **M9-A computes the break-even cost surface**, as a fraction of governed
> spend, over the parameters this world does control: decision horizon,
> prior, utility parameters, and the estimator. It outputs a threshold, not a
> verdict.

The verdict — do real geo experiments cost more or less than that? — then
becomes an **external-data question**, answerable against vendor
documentation and practitioner reports rather than against this DGP. That is
the honest division of labour: the simulation prices the information, the
world prices the experiment.

## 3. Cost accounting, frozen now

Four components, because collapsing them is how "$18,000" becomes
unreconstructable three milestones later:

    C(d) = C_execution + E[C_intervention] + C_delay + C_operations

| | |
|---|---|
| `C_execution` | costs existing *only because* measurement happens: analyst, engineering, platform, extra creative/config |
| `E[C_intervention]` | the economic price of the forced experimental policy — **the dominant term, and the one this DGP cannot supply** |
| `C_delay` | value of decisions deferred while the test runs |
| `C_operations` | implementation overheads the utility model does not represent |

`C_intervention` is defined against the policy the business would otherwise
have run:

    C_intervention(d, θ) = U(a_current, θ) − U(a_experiment(d), θ)
    E[C_intervention(d)] = E_θ[ C_intervention(d, θ) ]

computed **through the same utility model as EVSI**. Two dollar figures from
different utility models are two different quantities wearing one currency
symbol — which is F17–F19 with a `$` in front, and it is the single most
likely way this milestone fails.

### The accounting schema, fixed in advance

Never one field called `cost`:

    gross_spend_perturbation          ad spend moved, signed
    gross_revenue_impact              revenue consequence of moving it
    net_experimental_opportunity_cost the economic sacrifice: the two above,
                                      through the utility model
    direct_measurement_cost           C_execution + C_operations
    total_research_cost               the sum that enters ENBS

A spend-increase design has positive `gross_spend_perturbation` and may have
*negative* net cost if the added spend clears breakeven. A holdout has
negative perturbation and can be very expensive. The sign of the first field
tells you nothing about the sign of the third, which is exactly why they are
separate fields.

## 4. Decision horizon — to be fixed before any number is quoted

    L        number of future decisions the result informs
    rho_t    relevance of today's result at period t (drift)
    r        discount rate

    EVSI_lifetime = sum_t  rho_t · EVSI_t / (1+r)^t

Not necessarily that functional form. The binding rule is: **the horizon is
declared before the break-even figure is named**, and `L = 1` is a choice to
be stated, not a default to be inherited silently. Recast's own MMM
calibration assumes an experiment's constraint weakens with distance from the
test window, so `rho_t < 1` is the expected case rather than a conservatism.

## 5. Staging

**M9-A — break-even feasibility.** No new simulation campaign. Existing
n=25 data, the conditioned prior, the validated `q(θ)`. Produces the
break-even net cost as a share of governed spend, across `L` and the utility
parameters. Sets `C_execution = C_delay = 0` — maximally favourable to the
experiment — so that a negative result is decisive: if the information does
not pay even when the measurement is free, no realistic overhead rescues it.

**M9-B — the reachable frontier.** Only if M9-A leaves room. New simulation
campaigns varying **T and G only**, which the generator supports. Yields
`EVSI(T, G)` and, with the cost model, `ENBS(T, G)`.

**M9-C — the response model.** Δspend and direction. Requires committing to a
spend→lift→revenue model that this project has never had. **Not scheduled**,
and should not be slipped into M9-B as a parameter.

## 6. What counts as a result

* **Negative.** No design has `ENBS > 0` even with free measurement. Strong,
  publishable, and a genuine answer to the track's original question.
* **Conditional.** Positive only in a narrow band — then the output is
  quantitative: *how much* uncertainty is worth buying and at what price.
  More interesting than either binary.
* **Positive everywhere.** Then the interesting question moves to `d*`.

The shape worth anticipating: EVSI has diminishing returns in experiment
intensity while cost grows at least linearly, so `ENBS` is single-peaked and
the optimum is interior. "A full $20k geo test is irrational but a $1.5k test
buying 60% of the available information is optimal" is a possible outcome,
and a far better one than "geo tests are too expensive".

## 7. Out of scope

* Finding B. Still unscaled, still needs a 3-d density.
* New estimator benchmarks.
* Any claim of real-world external validity. The DGP is synthetic and — as §1
  establishes — does not even contain the economic object being priced.
