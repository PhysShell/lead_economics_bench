"""Constrained action allocation, shared by every model family.

The lead-track decision is a *multiple-choice knapsack*: each lead takes
exactly one action, each action consumes resources, and total resource use is
capped. We solve the LP relaxation exactly via a Lagrangian multiplier search
and round to an integral solution. The LP gap is bounded by the value of a
single lead, which is negligible at benchmark scale, and
``tests/test_optimizer.py`` checks the Lagrangian solution against an exact
MILP on small instances.

Keeping one optimizer for all candidates is not a convenience — it is the only
way to attribute a difference in realized profit to the *predictions* rather
than to somebody's fancier solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ..economics import Constraints

AllocationMode = Literal["ev", "rank"]


@dataclass
class AllocationResult:
    actions: np.ndarray
    resource_used: dict[str, float]
    multipliers: dict[str, float]
    binding: bool


def _argmax_reduced(values: np.ndarray, weights: list[np.ndarray], lam: np.ndarray):
    """argmax_a (v[:,a] - sum_r lam_r * w_r[:,a])."""
    reduced = values.copy()
    for r, w in enumerate(weights):
        if lam[r] != 0.0:
            reduced = reduced - lam[r] * w
    return reduced.argmax(axis=1)


def allocate_ev(
    values: np.ndarray,
    minutes: np.ndarray,
    constraints: Constraints,
    direct_cost: np.ndarray | None = None,
    control_action: int = 0,
    max_iter: int = 60,
) -> AllocationResult:
    """Maximise ``sum_i values[i, a_i]`` subject to the resource caps.

    Parameters
    ----------
    values:
        (n, A) predicted net value of each action, in dollars. This is the
        model's belief, not the truth.
    minutes:
        (n, A) predicted agent minutes consumed by each action.
    direct_cost:
        (n, A) predicted cash cost, used only when a ``cash_budget`` is set.
    """
    values = np.asarray(values, dtype=float)
    minutes = np.asarray(minutes, dtype=float)
    n, n_actions = values.shape

    resources: list[np.ndarray] = []
    caps: list[float] = []
    names: list[str] = []

    if constraints.agent_minutes is not None:
        resources.append(minutes)
        caps.append(float(constraints.agent_minutes))
        names.append("agent_minutes")
    if constraints.max_actions is not None:
        card = np.ones((n, n_actions))
        card[:, control_action] = 0.0
        resources.append(card)
        caps.append(float(constraints.max_actions))
        names.append("max_actions")
    if constraints.cash_budget is not None:
        dc = np.zeros_like(values) if direct_cost is None else np.asarray(direct_cost)
        resources.append(dc)
        caps.append(float(constraints.cash_budget))
        names.append("cash_budget")

    if not resources:
        a = values.argmax(axis=1)
        return AllocationResult(a, {}, {}, binding=False)

    lam = np.zeros(len(resources))
    a = _argmax_reduced(values, resources, lam)
    used = np.array([r[np.arange(n), a].sum() for r in resources])
    if np.all(used <= np.array(caps) + 1e-9):
        return AllocationResult(
            a,
            dict(zip(names, used)),
            dict(zip(names, lam)),
            binding=False,
        )

    # Coordinate bisection on the multipliers. Two outer sweeps is ample for
    # the two or three resources this benchmark ever uses.
    hi_init = _upper_multiplier(values, resources)
    for _ in range(2 if len(resources) > 1 else 1):
        for r in range(len(resources)):
            lo, hi = 0.0, hi_init[r]
            for _ in range(max_iter):
                mid = 0.5 * (lo + hi)
                lam[r] = mid
                a = _argmax_reduced(values, resources, lam)
                if resources[r][np.arange(n), a].sum() > caps[r]:
                    lo = mid
                else:
                    hi = mid
            lam[r] = hi
        a = _argmax_reduced(values, resources, lam)

    # Repair pass: the rounded solution can still breach a cap by one lead's
    # worth. Drop the least valuable assignments until feasible.
    a = _repair(values, resources, caps, a, control_action)
    used = np.array([r[np.arange(n), a].sum() for r in resources])
    return AllocationResult(
        a, dict(zip(names, used)), dict(zip(names, lam)), binding=True
    )


def _upper_multiplier(values: np.ndarray, resources: list[np.ndarray]) -> np.ndarray:
    """A multiplier large enough to force the cheapest action everywhere."""
    out = []
    for r in resources:
        span_v = float(np.ptp(values, axis=1).max()) if values.size else 1.0
        w = r - r.min(axis=1, keepdims=True)
        span_w = float(w[w > 0].min()) if np.any(w > 0) else 1.0
        out.append(max(10.0, 10.0 * span_v / max(span_w, 1e-9)))
    return np.array(out)


def _repair(
    values: np.ndarray,
    resources: list[np.ndarray],
    caps: list[float],
    a: np.ndarray,
    control_action: int,
) -> np.ndarray:
    n = len(a)
    idx = np.arange(n)
    a = a.copy()
    for r, cap in zip(resources, caps):
        used = r[idx, a].sum()
        if used <= cap + 1e-9:
            continue
        active = np.where(a != control_action)[0]
        if len(active) == 0:
            continue
        # Give up the assignments with the worst value-per-resource first.
        gain = values[active, a[active]] - values[active, control_action]
        spend = r[active, a[active]] - r[active, control_action]
        density = np.where(spend > 1e-12, gain / np.maximum(spend, 1e-12), np.inf)
        order = active[np.argsort(density)]
        for i in order:
            if used <= cap + 1e-9:
                break
            used -= r[i, a[i]] - r[i, control_action]
            a[i] = control_action
    return a


def allocate_rank(
    score: np.ndarray,
    minutes: np.ndarray,
    constraints: Constraints,
    primary_action: int,
    fallback_action: int = 0,
    control_action: int = 0,
) -> AllocationResult:
    """The call-list policy: sort by score, work down the list until time runs out.

    This is what a ranking-only baseline (lead score, historical conversion
    rate, FIFO) actually does in an operations team, and it deliberately does
    *not* trade value against per-lead effort. That difference is the whole
    point of RQ4.
    """
    score = np.asarray(score, dtype=float)
    n = len(score)
    a = np.full(n, fallback_action, dtype=int)

    order = np.argsort(-score, kind="stable")
    cap_min = constraints.agent_minutes
    cap_card = constraints.max_actions

    used_min = 0.0
    used_card = 0
    fallback_min = minutes[:, fallback_action]
    # The fallback (e.g. a bulk SMS) also consumes time; charge it up front.
    base_min = float(fallback_min.sum())
    used_min = base_min
    if fallback_action != control_action:
        used_card = n

    for i in order:
        extra_min = minutes[i, primary_action] - minutes[i, fallback_action]
        extra_card = int(primary_action != control_action) - int(
            fallback_action != control_action
        )
        if cap_min is not None and used_min + extra_min > cap_min + 1e-9:
            continue
        if cap_card is not None and used_card + extra_card > cap_card:
            continue
        a[i] = primary_action
        used_min += extra_min
        used_card += extra_card

    return AllocationResult(
        a,
        {"agent_minutes": float(minutes[np.arange(n), a].sum())},
        {},
        binding=cap_min is not None,
    )


def allocate_exact_milp(
    values: np.ndarray,
    minutes: np.ndarray,
    capacity: float,
    time_limit: int = 60,
) -> np.ndarray:
    """Exact multiple-choice knapsack via CBC. Reference implementation for tests."""
    import pulp

    n, n_actions = values.shape
    prob = pulp.LpProblem("mckp", pulp.LpMaximize)
    z = [
        [pulp.LpVariable(f"z_{i}_{a}", cat="Binary") for a in range(n_actions)]
        for i in range(n)
    ]
    prob += pulp.lpSum(
        values[i, a] * z[i][a] for i in range(n) for a in range(n_actions)
    )
    for i in range(n):
        prob += pulp.lpSum(z[i]) == 1
    prob += (
        pulp.lpSum(minutes[i, a] * z[i][a] for i in range(n) for a in range(n_actions))
        <= capacity
    )
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    out = np.zeros(n, dtype=int)
    for i in range(n):
        for a in range(n_actions):
            if z[i][a].value() is not None and z[i][a].value() > 0.5:
                out[i] = a
    return out
