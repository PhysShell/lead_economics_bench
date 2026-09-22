"""Decision and economic metrics. These are the primary leaderboard."""

from __future__ import annotations

import numpy as np

from ..economics import RealizedOutcome


def regret(oracle_value: float, policy_value: float) -> float:
    """Dollars left on the table versus the best feasible policy."""
    return float(oracle_value - policy_value)


def regret_ratio(
    oracle_value: float, policy_value: float, baseline_value: float
) -> float:
    """Normalised regret: 0 = Oracle, 1 = the reference baseline.

    Values above 1 mean the candidate is *worse* than the reference, which
    happens more often than the literature would have you believe.
    """
    denom = oracle_value - baseline_value
    if abs(denom) < 1e-9:
        return float("nan")
    return float((oracle_value - policy_value) / denom)


def incremental_value(policy: RealizedOutcome, do_nothing: RealizedOutcome) -> float:
    """Net value created *by acting at all*, versus leaving every lead alone."""
    return float(policy.net_value - do_nothing.net_value)


def incremental_conversions(
    policy: RealizedOutcome, do_nothing: RealizedOutcome
) -> float:
    return float(policy.conversions - do_nothing.conversions)


def cost_per_incremental_conversion(
    policy: RealizedOutcome, do_nothing: RealizedOutcome
) -> float:
    inc = incremental_conversions(policy, do_nothing)
    if abs(inc) < 1e-9:
        return float("nan")
    return float(policy.action_cost / inc)


def resource_utilisation(policy: RealizedOutcome, capacity_minutes: float | None) -> float:
    if capacity_minutes is None or capacity_minutes <= 0:
        return float("nan")
    return float(policy.agent_minutes / capacity_minutes)


def economic_summary(
    policy: RealizedOutcome,
    do_nothing: RealizedOutcome,
    oracle_value: float | None = None,
    baseline_value: float | None = None,
    capacity_minutes: float | None = None,
) -> dict[str, float]:
    out = policy.to_dict()
    out["incremental_net_value"] = incremental_value(policy, do_nothing)
    out["incremental_net_value_per_1k"] = (
        1000.0 * out["incremental_net_value"] / max(policy.n_leads, 1)
    )
    out["incremental_conversions"] = incremental_conversions(policy, do_nothing)
    out["cost_per_incremental_conversion"] = cost_per_incremental_conversion(
        policy, do_nothing
    )
    out["resource_utilisation"] = resource_utilisation(policy, capacity_minutes)
    if oracle_value is not None:
        out["regret"] = regret(oracle_value, policy.net_value)
        out["regret_per_1k"] = 1000.0 * out["regret"] / max(policy.n_leads, 1)
        out["pct_of_oracle_incremental"] = _pct_of_oracle(
            policy.net_value, do_nothing.net_value, oracle_value
        )
        if baseline_value is not None:
            out["regret_ratio"] = regret_ratio(
                oracle_value, policy.net_value, baseline_value
            )
    return out


def _pct_of_oracle(policy_value: float, floor_value: float, oracle_value: float) -> float:
    """Share of the Oracle's *achievable* gain that the policy captured.

    Measured above the do-nothing floor, because crediting a policy with the
    profit that would have arrived on its own is how vendors get to 95%.
    """
    denom = oracle_value - floor_value
    if abs(denom) < 1e-9:
        return float("nan")
    return float(100.0 * (policy_value - floor_value) / denom)
