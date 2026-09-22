"""Economic accounting tests.

If a sign is wrong here, the whole benchmark recommends burning money, and it
does so confidently. These tests exist so that cannot happen quietly.
"""

from __future__ import annotations

import numpy as np
import pytest

from leadbench.economics import (
    Constraints,
    Economics,
    capacity_for_ratio,
    control_everything_value,
    realized_net_value,
)
from leadbench.synthetic.config import make_config
from leadbench.synthetic.dgp import generate


@pytest.fixture(scope="module")
def ds():
    return generate(make_config("easy_randomized", n_leads=4000, seed=7))


def test_revenue_is_positive_and_costs_are_negative(ds):
    """Net value must equal revenue minus cost, with cost subtracted."""
    call = ds.n_actions - 1
    actions = np.full(len(ds.truth), call, dtype=int)
    out = realized_net_value(ds, actions)
    assert out.revenue > 0
    assert out.action_cost > 0
    assert out.net_value == pytest.approx(out.revenue - out.action_cost, rel=1e-9)


def test_doing_nothing_costs_nothing(ds):
    out = control_everything_value(ds)
    assert out.action_cost == pytest.approx(0.0)
    assert out.agent_minutes == pytest.approx(0.0)
    # Some leads convert anyway; the control arm is not worth zero.
    assert out.revenue > 0


def test_calling_everyone_consumes_more_time_than_calling_nobody(ds):
    call = ds.n_actions - 1
    treat = realized_net_value(ds, np.full(len(ds.truth), call, dtype=int))
    none = control_everything_value(ds)
    assert treat.agent_minutes > none.agent_minutes
    assert treat.action_cost > none.action_cost


def test_more_expensive_action_never_looks_better_holding_outcomes_fixed(ds):
    """Guard against a flipped agent-cost sign.

    Take the leads whose outcome is identical with and without a call. For
    those, calling is pure cost, so net value must strictly fall.
    """
    call = ds.n_actions - 1
    same = (
        ds.truth[f"y_funded_a{call}"].to_numpy()
        == ds.truth["y_funded_a0"].to_numpy()
    )
    sub = ds.subset(same)
    assert len(sub.truth) > 100
    treat_all = realized_net_value(sub, np.full(len(sub.truth), call, dtype=int))
    treat_none = realized_net_value(sub, np.zeros(len(sub.truth), dtype=int))
    assert treat_all.net_value < treat_none.net_value, (
        "calling leads whose outcome does not change must reduce net value; "
        "an agent-cost sign error would invert this"
    )


def test_acquisition_cost_is_subtracted_only_when_requested(ds):
    actions = np.zeros(len(ds.truth), dtype=int)
    without = realized_net_value(ds, actions, include_acquisition_cost=False)
    with_cpl = realized_net_value(ds, actions, include_acquisition_cost=True)
    assert with_cpl.net_value < without.net_value
    assert without.net_value - with_cpl.net_value == pytest.approx(
        float(ds.truth["cpl"].sum()), rel=1e-9
    )


def test_refunds_reduce_net_contribution(ds):
    refunded = ds.truth["refunded_draw"].to_numpy().astype(bool)
    net = ds.truth["net_contribution"].to_numpy()
    assert (net[refunded] < 0).all(), "a clawback must not book positive contribution"


def test_expected_net_contribution_matches_refund_arithmetic(ds):
    cfg = ds.config
    truth = ds.truth
    # E[net] = (1-r) * net_if_kept - r * servicing
    kept = truth["gross_value"].to_numpy() * cfg.margin_rate - cfg.servicing_cost_per_funded
    expected = (
        1 - cfg.refund_rate
    ) * kept - cfg.refund_rate * cfg.servicing_cost_per_funded
    assert np.allclose(truth["expected_net_contribution"].to_numpy(), expected)


def test_per_1k_and_per_agent_hour_scaling(ds):
    call = ds.n_actions - 1
    out = realized_net_value(ds, np.full(len(ds.truth), call, dtype=int))
    assert out.net_value_per_1k_leads == pytest.approx(
        1000.0 * out.net_value / out.n_leads
    )
    assert out.net_value_per_agent_hour == pytest.approx(
        out.net_value / (out.agent_minutes / 60.0)
    )


def test_economics_cost_vector_places_call_last():
    for n in (2, 3):
        e = Economics()
        v = e.direct_cost_vector(n)
        assert v[0] == 0.0, "control must be free"
        assert v[-1] == e.call_direct_cost


def test_action_cost_increases_with_minutes():
    e = Economics()
    cheap = e.action_cost(np.array([[0.0, 1.0]]))
    dear = e.action_cost(np.array([[0.0, 60.0]]))
    assert dear[0, 1] > cheap[0, 1]
    assert dear[0, 1] - cheap[0, 1] == pytest.approx(59.0 * e.cost_per_minute)


def test_capacity_for_ratio_is_proportional(ds):
    full = capacity_for_ratio(ds, 1.0)
    half = capacity_for_ratio(ds, 0.5)
    assert half == pytest.approx(0.5 * full)
    assert full == pytest.approx(float(ds.truth[f"minutes_a{ds.n_actions-1}"].sum()))


def test_rejects_malformed_action_vectors(ds):
    with pytest.raises(ValueError):
        realized_net_value(ds, np.zeros(len(ds.truth) - 1, dtype=int))
    with pytest.raises(ValueError):
        realized_net_value(ds, np.full(len(ds.truth), 99, dtype=int))
