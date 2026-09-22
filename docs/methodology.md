# Methodology, design decisions and known limitations

This document records *why* the benchmark is built the way it is, and — as
importantly — where it is weak. A benchmark whose limitations section is empty
is a benchmark whose author did not look.

## 1. Counterfactual coherence: common random numbers

Each lead carries one uniform draw per funnel stage, `u_contact`, `u_qualified`,
`u_application`, `u_funded`. A potential outcome under action `a` is

```
reached_stage_s(a) = reached_stage_{s-1}(a) AND (u_s < p_s(a))
```

This makes counterfactuals coherent and monotone: the same lead cannot get
lucky under one action and unlucky under another for reasons unrelated to the
action. Without it, "regret" measures simulation noise as much as policy
quality. `test_potential_outcomes_are_monotone_in_probability` asserts it.

## 2. The Oracle is not clairvoyant

The Oracle knows the true stage probabilities, the true *expected* net
contribution and the true handle time. It does **not** know:

- the realized uniform draws,
- the realized refund/clawback draw,
- the realized lognormal deal-value noise.

So it is the best policy *measurable with respect to the lead*, not a
fortune-teller. This matters for interpretation: 100% of Oracle is attainable
in principle by a perfect model; it is not an unreachable ceiling inflated by
hindsight. A clairvoyant reference would make every candidate look worse by a
constant and would tell you nothing.

## 3. Capacity is enforced with true effort, not predicted effort

A policy plans with its own predicted handle times; the evaluator then enforces
the constraint with the **true** minutes, dropping the lowest-priority
assignments until the plan fits.

This is deliberate and it has teeth. A model that under-predicts handle time
builds a call list it cannot finish, and the day ends whether or not the list
does. A model that over-predicts leaves capacity idle. Both are penalised, both
are realistic, and the same rule applies to every candidate including the
Oracle. It also makes the shared `EffortModel` a real part of the problem
rather than a detail — which is exactly what the "without agent time" ablation
is there to quantify.

## 4. One optimiser for everybody

The lead-allocation problem is a multiple-choice knapsack. It is solved by a
Lagrangian multiplier search over the LP relaxation, then rounded, with a
repair pass. `tests/test_optimizer_and_policies.py` checks the result against
an exact CBC MILP on small instances; the gap is bounded by roughly one lead's
value, which is negligible at benchmark scale.

Using one optimiser for every family — including the Oracle — is the only way
a difference in realized profit can be attributed to *predictions* rather than
to somebody's better solver.

### Rank mode vs EV mode

Two allocation modes exist because they represent genuinely different
operational behaviours:

- **EV mode** trades a lead's value against that lead's effort
  (value-per-minute), which is what a decision engine does.
- **Rank mode** sorts by a score and works the list top-down until the clock
  runs out, which is what a scored call queue does. It is *blind* to per-lead
  effort.

Naive and lead-scoring candidates get rank mode because that is what those
products actually do. RQ4 is exactly the difference between the two, and the
`abl_*_no_optimizer` ablations run economic models in rank mode to isolate it.

## 5. Why uplift metrics are secondary

Qini and AUUC score a *ranking*. A ranking is not a decision: it is blind to
deal value, to agent minutes and to the cost of the action. A model can top the
Qini table and lose money, and in this benchmark some do. They are reported as
secondary diagnostics and never used to declare a winner.

## 6. Propensity-EV values the control arm at zero — on purpose

`PropensityEV` computes `P(funded | X, a) · value(X) − cost(a)` and sets the
control arm's value to **zero**. That is not a bug; it is a faithful model of
what most "AI lead prioritisation" features compute. They credit the action
with the lead's entire conversion probability. Making this assumption explicit
is what lets RQ2/RQ3 measure the cost of it, and the T-learner variant
(`credit_control=True` in effect) is the corrected version sitting one rung up
the ladder.

## 7. Shared nuisance models

Every economic candidate uses the same `ValueModel` (E[net contribution |
funded, X]) and the same `EffortModel` (E[minutes | call, X]). A family cannot
win by having a better margin regression. The ablations switch each to a global
mean to measure its contribution.

## 8. What broke during construction, and what it cost

Recorded because near-misses are the most informative part of a benchmark
build, and because §66 requires failures to be visible.

1. **Truth column collision.** The per-stage probability `P(funded |
   application)` was written to `p_funded_a{a}` — the same name as the overall
   funnel probability — silently overwriting it. The Oracle's EV was computed
   before the overwrite so it was correct, but every reported "true ATE" was
   wrong by a factor of ~4 (0.0155 vs the true 0.062). Caught by reconciling
   `mean(p_funded_a{a})` against the empirical conversion rate in arm `a`.
   Now a permanent test (`test_stated_probabilities_match_realized_rates`) and
   the stage columns are prefixed `p_stage_*`.

2. **EconML `cate_models` typing.** X-learner's `cate_models` regress a
   continuous pseudo-effect, so passing the probability-classifier wrapper
   raised `Invalid classes inferred from unique values of y`. They must be
   genuine regressors; the outcome `models` are the ones that want the
   classifier.

3. **Hyperparameter name collision.** `CausalForest(n_estimators=...)` was
   being consumed by the forest, so the forest's *base learners* silently fell
   back to library defaults while every other family used the shared setting —
   an unfair comparison hiding in a keyword argument. Renamed to `n_trees`.

4. **Jensen gap in the PyMC-Marketing curve.** Reconstructing the response
   curve at the *posterior mean* of `(alpha, lambda, beta)` disagreed with the
   library's own fitted contributions by 15–50%, because logistic saturation is
   concave and `f(E[theta]) ≠ E[f(theta)]`. Fixed by averaging the curve over
   posterior draws; residual cross-check error is ~6% and is reported as a
   diagnostic rather than hidden. The candidate raises if it exceeds 15%.

5. **`GeometricAdstock.normalize` default.** The raw
   `pymc_marketing.mmm.transformers.geometric_adstock` function defaults to
   `normalize=False`, but the `GeometricAdstock` class used by `MMM` defaults
   to `normalize=True`. Assuming the former rescaled every channel's curve by
   a different factor. Now read from the fitted object.

6. **A candidate registered twice, fitted twice, compared wrongly.**
   `bayes_hierarchical` is both an uncertainty candidate and the control that
   `abl_bayes_no_hierarchy` is ablated against, so the bayes suite registered
   it from two registry groups. It was therefore fitted twice — 45 seconds a
   time for a PyMC candidate — and wrote two identical rows per cell. Pairing
   by seed then indexes a duplicated index, so `.loc[common]` returns more rows
   than the reference has: it raised `operands could not be broadcast together
   with shapes (8,) (4,)` here, and with a *partial* overlap it would have
   silently differenced mismatched seeds instead. Fixed at the runner
   (`dedupe_candidates`, first registration wins) and defensively in the
   aggregation, with regression tests in `tests/test_aggregation.py`.

7. **`DataFrame.get("status", "ok") == "ok"` is not a row mask.** When the
   column is absent, `.get` returns the *default scalar*, the comparison
   evaluates to the bool `True`, and `results[True]` raises `KeyError: True`.
   The online track records no failures and so has no `status` column at all,
   which meant the report builder crashed on it — after every suite had already
   run. Replaced by an explicit `ok_rows` helper at all four call sites.

8. **The headline metric was a mean of ratios.** `pct_of_oracle_incremental`
   divides by the Oracle's incremental gain *on that seed*. Under
   `concept_drift` that gain is about $3.0k per 1,000 leads against
   $109k-$208k in every other regime, because drift leaves almost nothing on
   the table for anybody. Averaging those ratios reported **1,454% of Oracle
   for `fifo`**, whose raw incremental value is negative, and 1,344% for
   `dr_learner` — and those two figures then dominated the leaderboard mean
   and floated the expensive causal learners to the top of a table where the
   raw ordering has them mid-pack. Replaced by `aggregate.oracle_share`, a
   ratio of means, which is stable at any prize size and agrees with the old
   metric wherever the denominator was never in doubt.

9. **The incumbent baseline was replayed on a quarter-size dataset.**
   `add_incumbent_baseline.py` regenerated its datasets from the `n_leads`
   column, which holds the *test-fold* size (7,722) rather than the configured
   30,000 for any row written before the `n_test_leads` rename. Long-running
   suites import the module once at start, so the lead sweep wrote the old
   shape for two hours after the fix landed. The incumbent — the one candidate
   representing what the business actually does — was therefore scored on a
   different problem than everything it was being compared with. A second
   effect of the same column: failed candidates never reach the code that
   overwrites `n_leads`, so `noisy_crm` had two distinct cell tuples per seed
   and got two incumbent rows per cell.

10. **The generated kill criteria disagreed with the report.**
    `kill_criteria.csv` scored K1/K2/K5 on Oracle-share points rather than the
    preregistered paired net-value rule, and on the lead+ablation+bayes
    concatenation rather than the lead sweep — suites with different dataset
    sizes, regime sets and candidate lists. It printed a 34-point causal
    "advantage" and marked K2 not triggered while the report, computed
    correctly, said the opposite. A benchmark whose own artefacts contradict
    its conclusions is worse than one with no artefacts.

None of these would have produced an obviously broken result. All of them
would have produced a *confidently wrong* one — and the last three are the
most instructive, because they were all found by running the reporting layer
against partial data early instead of waiting until every suite had finished.
Two of them are the same mistake in different clothes: dividing by a
denominator that is sometimes near zero, and pooling cells that never met.

## 9. Blockers and things not done

Stated concretely, per §87, rather than deferred to "future work".

- **Meta Robyn was not benchmarked.** It is an R package; its official Python
  distribution is a self-described LLM-translated beta. Benchmarking the
  translation would measure the translation. The
  `ridge_adstock_saturation` candidate occupies the same methodological slot
  (grid-searched adstock/saturation + regularised non-negative regression).
- **PyMC-Marketing is 0.19.2, not the current 1.1.0.** The container runs
  Python 3.11.15 and `pymc-marketing==1.1.0` requires `>=3.12`. Verified by
  resolver error. A separate Python 3.12 environment was provisioned in which
  `pymc 6.2.0 + pymc-marketing 1.1.0` install cleanly; the 1.x API differs
  enough that porting the MMM candidate is follow-up work.
- **Google Meridian runs in an isolated Python 3.12 interpreter.** Meridian
  2.0.0 installs and runs; it is driven as a subprocess via
  `scripts/run_meridian.py` because it cannot coexist with the 3.11 benchmark
  environment. It is the slowest candidate by a wide margin, so it runs on a
  representative subset of MMM regimes. Full sweep:
  ```
  python scripts/run_benchmark.py --suite mmm --seeds 4 --meridian
  ```
- **Patent primary sources were unreachable.** `patents.google.com` returned
  503 on every attempt, Espacenet and Justia 403, FreePatentsOnline failed TLS.
  USPTO grant PDFs download but are image-only. See
  `docs/research/patent-landscape.md`, which states per-row what is verified
  and what is not.
- **Criteo full-data run.** The benchmark uses a deterministic 2M-row
  subsample (seed in the manifest) so every algorithm sees byte-identical data
  within a reasonable runtime. Full 13.98M-row command:
  ```
  python scripts/run_benchmark.py --suite real --criteo-rows 0 --seeds 3
  ```
  (`--criteo-rows 0` is interpreted as "all rows" by `load_criteo(n_rows=None)`.)
- **Vowpal Wabbit** is installed but not entered as a candidate; see
  `docs/research/open-source-landscape.md` for why (its CB reductions bundle
  exploration with their own learner, confounding the exploration comparison).

## 10. Known limitations of the benchmark itself

These would change conclusions if they are wrong, so they are stated plainly.

1. **The synthetic DGP is our own model of the world.** It is rich — 20
   regimes, hierarchical effects, delays, censoring, dirty CRM, confounding —
   but a model that matches the DGP's structure has an advantage no real
   deployment would enjoy. This is mitigated by (a) the real randomized
   datasets, where no such advantage exists, and (b) deliberately giving the
   Bayesian candidate a *misspecified* linear-logistic form rather than the
   true four-stage funnel.

2. **The economics are parameterised, not measured.** Agent cost $38/h, ~8 min
   median handle time, 32% margin, 4% clawback. These are plausible
   mid-ticket-sales numbers, not numbers from a real partner. Conclusions that
   depend on the *ratio* of agent cost to contribution margin should be
   re-checked against a partner's real figures. The capacity and value-spread
   sweeps exist partly to show how sensitive the answer is to that ratio.

3. **Real-data economics are a benchmark convention.** Hillstrom and Criteo
   have no agent-time or margin data, so value-per-outcome and cost-per-
   treatment are preregistered constants and the constraint is a send budget.
   Those tracks therefore test *targeting* quality, not the full economic
   problem.

4. **Interval coverage is measured against per-lead truth.** This is a harsh
   standard: the posterior covers parameter uncertainty, not model
   misspecification, and not the point-estimated value/effort nuisances feeding
   the EV. Probability-level coverage is reported separately precisely so the
   two explanations can be told apart.

5. **Seeds, not infinite replication.** The headline sweep uses 8 seeds with
   paired comparisons. That is enough to separate large effects from noise and
   *not* enough to resolve differences well below the 2% practical threshold —
   which is why the decision rule requires clearing that threshold rather than
   merely achieving significance.

6. **One capacity level dominates the headline table** (25% of the effort
   needed to call everyone). The capacity sweep covers 5%–100%, and the answer
   does move with it, so the headline number should be read as "at this
   capacity", not as a universal constant.

7. **Abstention is scored pessimistically, on purpose.** When
   `AbstentionPolicy` declines to decide, the lead receives the *control*
   action and the freed capacity is not reallocated. A real deployment would
   hand those leads back to the existing human process, which would work some
   of them, and would presumably spend the freed agent-hours elsewhere. So the
   abstention numbers are a **lower bound** on its value: they measure the cost
   of refusing to act, not the value of deferring to a human. Read "abstention
   loses money here" as "abstention is not free", not as "never abstain" — the
   argument for abstention is about avoiding confident errors on thin evidence,
   and this benchmark cannot price that.
