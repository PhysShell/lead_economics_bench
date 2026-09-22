"""Decision policies: beliefs in, actions out.

A policy is deliberately dumb about modelling and smart about constraints. It
receives an :class:`~leadbench.models.base.ActionValueEstimate` and returns one
action per lead plus a *priority* ordering, which the evaluator uses to decide
who gets dropped when the plan turns out to consume more real agent time than
the model predicted.

That last part matters. A model that under-predicts handle time will build a
call list it cannot finish, and the day ends whether or not the list does. We
simulate that honestly instead of quietly granting extra capacity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..economics import Constraints
from ..models.base import ActionValueEstimate
from ..optimization.allocator import allocate_ev, allocate_rank


@dataclass
class Decision:
    actions: np.ndarray
    priority: np.ndarray
    planned_minutes: float
    multipliers: dict[str, float]
    diagnostics: dict[str, float]


class Policy:
    name: str = "policy"

    def decide(
        self,
        estimate: ActionValueEstimate,
        constraints: Constraints,
        control_action: int = 0,
    ) -> Decision:
        raise NotImplementedError


def _density_priority(
    values: np.ndarray, minutes: np.ndarray, actions: np.ndarray, control: int
) -> np.ndarray:
    """Believed value per agent-minute of the chosen action, for triage order."""
    idx = np.arange(len(actions))
    gain = values[idx, actions] - values[idx, control]
    spend = minutes[idx, actions] - minutes[idx, control]
    out = np.where(spend > 1e-9, gain / np.maximum(spend, 1e-9), np.inf)
    # Anything not receiving an action is dropped last: it costs nothing.
    out[actions == control] = np.inf
    return out


class EVPolicy(Policy):
    """Maximise believed net value subject to the resource caps."""

    name = "ev"

    def decide(self, estimate, constraints, control_action=0) -> Decision:
        res = allocate_ev(
            estimate.ev,
            estimate.minutes,
            constraints,
            direct_cost=estimate.direct_cost,
            control_action=control_action,
        )
        pri = _density_priority(
            estimate.ev, estimate.minutes, res.actions, control_action
        )
        return Decision(
            actions=res.actions,
            priority=pri,
            planned_minutes=float(
                estimate.minutes[np.arange(estimate.n), res.actions].sum()
            ),
            multipliers=res.multipliers,
            diagnostics={"binding": float(res.binding)},
        )


class RankPolicy(Policy):
    """Work a sorted call list top-down until the clock runs out.

    Note what this deliberately does *not* do: it never trades a lead's value
    against that lead's effort. That is the operational reality of a scored
    call queue and the thing RQ4 is testing.
    """

    name = "rank"

    def __init__(self, fallback_action: int = 0) -> None:
        self.fallback_action = fallback_action

    def decide(self, estimate, constraints, control_action=0) -> Decision:
        score = estimate.score
        if score is None:
            score = estimate.ev[:, -1] - estimate.ev[:, control_action]
        fallback = int(
            estimate.diagnostics.get("fallback_action", self.fallback_action)
        )
        res = allocate_rank(
            score,
            estimate.minutes,
            constraints,
            primary_action=estimate.n_actions - 1,
            fallback_action=fallback,
            control_action=control_action,
        )
        return Decision(
            actions=res.actions,
            priority=np.asarray(score, dtype=float),
            planned_minutes=float(
                estimate.minutes[np.arange(estimate.n), res.actions].sum()
            ),
            multipliers={},
            diagnostics={"fallback_action": float(fallback)},
        )


class FixedActionPolicy(Policy):
    """Always take the same action, subject to capacity."""

    name = "fixed"

    def __init__(self, action: int) -> None:
        self.action = action

    def decide(self, estimate, constraints, control_action=0) -> Decision:
        n = estimate.n
        if self.action == control_action:
            a = np.full(n, control_action)
            return Decision(a, np.zeros(n), 0.0, {}, {})
        res = allocate_rank(
            estimate.score if estimate.score is not None else np.zeros(n),
            estimate.minutes,
            constraints,
            primary_action=self.action,
            fallback_action=control_action,
            control_action=control_action,
        )
        return Decision(
            actions=res.actions,
            priority=np.zeros(n),
            planned_minutes=float(
                estimate.minutes[np.arange(n), res.actions].sum()
            ),
            multipliers={},
            diagnostics={},
        )


class LowerBoundEVPolicy(Policy):
    """Risk-averse: optimise the lower credible bound of EV, not its mean.

    Preregistered variants are q in {0.10, 0.25}. Falls back to the mean when
    the candidate produces no uncertainty, which keeps the comparison honest
    rather than silently crediting the policy with information it lacks.
    """

    name = "ev_lcb"

    def __init__(self, q: float = 0.10) -> None:
        self.q = q
        self.name = f"ev_lcb{int(q * 100)}"

    def decide(self, estimate, constraints, control_action=0) -> Decision:
        vals = estimate.ev_lower_bound(self.q)
        if vals is None:
            vals = estimate.ev
        res = allocate_ev(
            vals,
            estimate.minutes,
            constraints,
            direct_cost=estimate.direct_cost,
            control_action=control_action,
        )
        pri = _density_priority(vals, estimate.minutes, res.actions, control_action)
        return Decision(
            actions=res.actions,
            priority=pri,
            planned_minutes=float(
                estimate.minutes[np.arange(estimate.n), res.actions].sum()
            ),
            multipliers=res.multipliers,
            diagnostics={"used_uncertainty": float(estimate.ev_samples is not None)},
        )


class AbstentionPolicy(Policy):
    """Act only where the evidence is strong enough; otherwise hand back to the human.

    ``coverage`` is the share of leads on which the system is willing to make a
    call at all. Leads outside that share are marked abstained and left to the
    existing process (here: the control action), which lets us plot profit
    against coverage.
    """

    name = "abstain"

    def __init__(self, coverage: float = 0.5, base: Policy | None = None) -> None:
        self.coverage = coverage
        self.base = base or EVPolicy()
        self.name = f"abstain{int(coverage * 100)}"

    def decide(self, estimate, constraints, control_action=0) -> Decision:
        dec = self.base.decide(estimate, constraints, control_action)
        conf = _confidence(estimate)
        if conf is None:
            return dec
        k = int(np.ceil(self.coverage * len(conf)))
        if k >= len(conf):
            return dec
        keep = np.zeros(len(conf), dtype=bool)
        keep[np.argsort(-conf)[:k]] = True
        actions = np.where(keep, dec.actions, control_action)
        return Decision(
            actions=actions,
            priority=dec.priority,
            planned_minutes=float(
                estimate.minutes[np.arange(estimate.n), actions].sum()
            ),
            multipliers=dec.multipliers,
            diagnostics={"coverage": float(keep.mean())},
        )


def _confidence(estimate: ActionValueEstimate) -> np.ndarray | None:
    """How sure are we that the recommended action beats control?

    With samples: the posterior probability that the gap is positive. Without:
    the absolute size of the believed gap, which is a weaker but still
    meaningful proxy.
    """
    best = estimate.ev.argmax(axis=1)
    idx = np.arange(estimate.n)
    if estimate.ev_samples is not None:
        gap = estimate.ev_samples[:, idx, best] - estimate.ev_samples[:, idx, 0]
        return np.abs((gap > 0).mean(axis=0) - 0.5) * 2.0
    return np.abs(estimate.ev[idx, best] - estimate.ev[idx, 0])


def enforce_true_capacity(
    true_minutes: np.ndarray,
    actions: np.ndarray,
    priority: np.ndarray,
    constraints: Constraints,
    control_action: int = 0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Drop the lowest-priority assignments until the *real* clock allows the plan.

    Applied identically to every candidate. A model with a better effort model
    fills the day more completely; a model that under-predicts handle time gets
    truncated, exactly as it would in an actual sales floor.
    """
    actions = np.asarray(actions).copy()
    n = len(actions)
    idx = np.arange(n)
    cap = constraints.agent_minutes
    used = float(true_minutes[idx, actions].sum())
    info = {"planned_true_minutes": used, "truncated": 0.0}
    if cap is None or used <= cap + 1e-9:
        info["final_true_minutes"] = used
        return actions, info

    active = np.where(actions != control_action)[0]
    order = active[np.argsort(priority[active], kind="stable")]  # worst first
    dropped = 0
    for i in order:
        if used <= cap + 1e-9:
            break
        used -= true_minutes[i, actions[i]] - true_minutes[i, control_action]
        actions[i] = control_action
        dropped += 1
    info["truncated"] = float(dropped)
    info["final_true_minutes"] = float(true_minutes[idx, actions].sum())
    return actions, info


POLICY_REGISTRY = {
    "ev": EVPolicy,
    "rank": RankPolicy,
    "ev_lcb10": lambda: LowerBoundEVPolicy(0.10),
    "ev_lcb25": lambda: LowerBoundEVPolicy(0.25),
}
