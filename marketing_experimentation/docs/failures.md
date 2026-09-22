# Failure log — research track 2

Per the brief's §75. Every bug or invalid comparison that could have changed a
conclusion stays visible. History is not cleaned into a heroic narrative.

## F1. Reported that a free experiment was not worth running (v1 Layer 3)

**What was wrong.** `business_phase_diagram.py` (now
`significance_gate_v1.py`) modelled the decision as

    significant -> act ;  not significant -> don't act

and compared it against acting on the prior. It reported that even at zero
experiment cost, not experimenting beat experimenting over 70% of the
cost-by-prior plane, and that GeoLift was optimal in 0% of cells.

**Why it was wrong.** Value of information cannot be negative when the
information is free: you can always observe the result and then do what you
would have done anyway, so `EVSI >= 0` whenever `C_experiment = 0`. The model
was forced to obey the gate, so it was measuring the value of `p < .05` as a
binding rule, not the value of an experiment.

**What it would have changed.** Two headline claims, both wrong as stated:
"DO_NOT_RUN beats experimentation on 70% of the plane" and "GeoLift is never
optimal". Under the corrected model GeoLift's value rises **+1,296%** and the
four tools converge from an 11x spread to 17%.

**How it is prevented now.** `tests/test_decision.py` asserts `EVSI >= 0` at
zero cost, `0 <= EVSI <= EVPI`, that a useless signal is worth exactly zero,
and that a perfect signal is worth exactly EVPI. `voi_v2.py` checks all 1,800
cells and refuses to print if any fails.

**What survived.** The gate really is beaten by the prior in 70% of the
plane. That is a true and useful statement about conventional practice — it
was only the label that was wrong.

## F2. Two reporting artefacts in the v2 first run

- "cells where best EVSI < 0: 10" was floating-point dust (largest magnitude
  $0.00 against a $0.45 tolerance) being compared against a hard zero. Now
  compared against a tolerance scaled to EVPI.
- "median share of the experiment's value discarded by the gate:
  125,698,162,152,177,744%" was division by a near-zero EVSI. Now computed
  only over cells where the experiment has material value, where the honest
  answer turns out to be 0%.

Neither changed a conclusion, but the second would have been quoted.

## F3. Two overstatements in the first landscape pass

- "Capability I is closed" — too strong. Recast benchmarked methods against
  synthetic regimes; that is not a per-business decision service, and they
  say so themselves.
- "GeoX chooses holdback vs go-dark vs heavy-up" — wrong. The user sets
  `experiment_types` and `methodology` in `DesignConfig`; GeoX optimises
  within that posture and compares configurations.

Both were caught by the reader, not by me.
