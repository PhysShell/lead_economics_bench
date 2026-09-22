"""Economic accounting. Signs live here and nowhere else.

Every dollar in this benchmark flows through :func:`realized_net_value`. If a
sign is wrong here it is wrong everywhere, which is precisely why
``tests/test_economics.py`` hammers this module.

Sign convention, no exceptions:

* realized net contribution from a funded deal      -> **+**
* action direct cost (telephony, SMS)               -> **-**
* agent time                                        -> **-**
* media spend / acquisition cost                    -> **-**
* refund / clawback                                 -> **-** (already folded
  into the realized net contribution by the DGP)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .synthetic.config import ACTIONS, CONTROL_ACTION
from .synthetic.dgp import LeadDataset


@dataclass(frozen=True)
class Economics:
    """Cost/value parameters visible to *models* (not the DGP's secrets)."""

    agent_cost_per_hour: float = 38.0
    sms_direct_cost: float = 0.03
    call_direct_cost: float = 0.06
    sms_minutes: float = 0.25
    # Fallback per-funded-deal margin, used by baselines that do not model
    # deal value per lead. Estimated from training data, never from test.
    default_net_contribution: float = 1_000.0

    @property
    def cost_per_minute(self) -> float:
        return self.agent_cost_per_hour / 60.0

    def direct_cost_vector(self, n_actions: int = len(ACTIONS)) -> np.ndarray:
        """Cash cost per action. The last index is always the human call."""
        v = np.zeros(n_actions)
        if n_actions >= 2:
            v[-1] = self.call_direct_cost
        if n_actions >= 3:
            v[1] = self.sms_direct_cost
        return v

    def action_cost(self, minutes: np.ndarray) -> np.ndarray:
        """Total cost of each action given predicted minutes. Shape (n, A)."""
        direct = self.direct_cost_vector(minutes.shape[1])
        return direct[None, :] + minutes * self.cost_per_minute


@dataclass(frozen=True)
class Constraints:
    """Resource limits the allocator must respect."""

    agent_minutes: float | None = None  # total sales capacity for the period
    max_actions: int | None = None  # cardinality cap, if any
    cash_budget: float | None = None  # cap on direct action spend

    def is_unconstrained(self) -> bool:
        return (
            self.agent_minutes is None
            and self.max_actions is None
            and self.cash_budget is None
        )


@dataclass
class RealizedOutcome:
    """Result of running a policy against ground truth."""

    net_value: float
    revenue: float
    action_cost: float
    agent_minutes: float
    n_leads: int
    conversions: float
    action_counts: dict[str, int]

    @property
    def net_value_per_1k_leads(self) -> float:
        return 1000.0 * self.net_value / max(self.n_leads, 1)

    @property
    def net_value_per_agent_hour(self) -> float:
        hours = self.agent_minutes / 60.0
        if hours <= 1e-9:
            return float("nan")
        return self.net_value / hours

    def to_dict(self) -> dict[str, float]:
        # NB: the key is `n_test_leads`, not `n_leads`. The scenario row
        # already carries the *configured* dataset size under `n_leads`, and
        # emitting the same key here silently overwrote it with the test-fold
        # size -- which scrambled every data-size curve until it was caught.
        return {
            "net_value": self.net_value,
            "net_value_per_1k_leads": self.net_value_per_1k_leads,
            "net_value_per_agent_hour": self.net_value_per_agent_hour,
            "revenue": self.revenue,
            "action_cost": self.action_cost,
            "agent_hours_used": self.agent_minutes / 60.0,
            "conversions": self.conversions,
            "n_test_leads": float(self.n_leads),
            **{f"n_action_{k}": float(v) for k, v in self.action_counts.items()},
        }


def realized_net_value(
    dataset: LeadDataset,
    actions: np.ndarray,
    include_acquisition_cost: bool = False,
) -> RealizedOutcome:
    """Score a per-lead action vector against the dataset's ground truth.

    ``include_acquisition_cost`` must stay ``False`` for the individual
    decisioning track: once a lead has been bought, its CPL is sunk and cannot
    change the optimal next action. It is switched on only for the acquisition
    track, where media spend is genuinely a decision variable.
    """
    truth = dataset.truth
    n = len(truth)
    actions = np.asarray(actions, dtype=int)
    if actions.shape != (n,):
        raise ValueError(f"actions must have shape ({n},), got {actions.shape}")
    if actions.min() < 0 or actions.max() >= dataset.n_actions:
        raise ValueError("action index out of range")

    idx = np.arange(n)
    y = np.column_stack(
        [truth[f"y_funded_a{a}"].to_numpy() for a in range(dataset.n_actions)]
    )
    cost = np.column_stack(
        [truth[f"action_cost_a{a}"].to_numpy() for a in range(dataset.n_actions)]
    )
    mins = np.column_stack(
        [truth[f"minutes_a{a}"].to_numpy() for a in range(dataset.n_actions)]
    )

    funded = y[idx, actions]
    net_contrib = truth["net_contribution"].to_numpy()

    revenue = float(np.sum(funded * net_contrib))  # +
    total_action_cost = float(np.sum(cost[idx, actions]))  # -
    total_minutes = float(np.sum(mins[idx, actions]))
    net = revenue - total_action_cost

    if include_acquisition_cost:
        net -= float(truth["cpl"].sum())  # -

    counts = {
        name: int(np.sum(actions == a)) for a, name in enumerate(dataset.actions)
    }
    return RealizedOutcome(
        net_value=net,
        revenue=revenue,
        action_cost=total_action_cost,
        agent_minutes=total_minutes,
        n_leads=n,
        conversions=float(funded.sum()),
        action_counts=counts,
    )


def true_action_values(dataset: LeadDataset) -> tuple[np.ndarray, np.ndarray]:
    """Oracle inputs: true expected net value and true minutes per action."""
    truth = dataset.truth
    ev = np.column_stack(
        [truth[f"ev_a{a}"].to_numpy() for a in range(dataset.n_actions)]
    )
    minutes = np.column_stack(
        [truth[f"minutes_a{a}"].to_numpy() for a in range(dataset.n_actions)]
    )
    return ev, minutes


def estimate_default_net_contribution(train: pd.DataFrame) -> float:
    """Average net contribution per funded deal, from *training* data only."""
    funded = train["funded"] == 1
    if funded.sum() == 0:
        return 0.0
    vals = train.loc[funded, "realized_net_contribution"].dropna()
    if len(vals) == 0:
        return 0.0
    return float(vals.mean())


def capacity_for_ratio(
    dataset: LeadDataset, ratio: float, action: int | None = None
) -> float:
    """Agent minutes equal to ``ratio`` x the minutes needed to call everyone.

    ``ratio=1.0`` means the sales floor could work every single lead; the
    interesting product regime is far below that.
    """
    a = dataset.n_actions - 1 if action is None else action
    total = float(dataset.truth[f"minutes_a{a}"].sum())
    return ratio * total


def control_everything_value(dataset: LeadDataset) -> RealizedOutcome:
    """The do-nothing counterfactual: no action on any lead."""
    return realized_net_value(
        dataset, np.full(len(dataset.truth), CONTROL_ACTION, dtype=int)
    )
