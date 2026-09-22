"""The shared allocator must be correct, or every leaderboard is noise."""

from __future__ import annotations

import numpy as np
import pytest

from leadbench.economics import Constraints
from leadbench.models.base import ActionValueEstimate
from leadbench.optimization.allocator import (
    allocate_ev,
    allocate_exact_milp,
    allocate_rank,
)
from leadbench.policies.decision import (
    AbstentionPolicy,
    EVPolicy,
    LowerBoundEVPolicy,
    RankPolicy,
    enforce_true_capacity,
)


def _instance(n=60, seed=0):
    rng = np.random.default_rng(seed)
    values = np.column_stack([np.zeros(n), rng.normal(50, 40, n)])
    minutes = np.column_stack([np.zeros(n), rng.uniform(2, 30, n)])
    return values, minutes


def test_lagrangian_matches_exact_milp_on_small_instances():
    for seed in range(4):
        values, minutes = _instance(50, seed)
        cap = 0.35 * minutes[:, 1].sum()
        approx = allocate_ev(values, minutes, Constraints(agent_minutes=cap)).actions
        exact = allocate_exact_milp(values, minutes, cap)
        idx = np.arange(len(approx))
        v_approx = values[idx, approx].sum()
        v_exact = values[idx, exact].sum()
        assert v_approx <= v_exact + 1e-6
        # The LP gap is bounded by roughly one item's value.
        assert v_exact - v_approx <= max(values.max(), 1.0) * 1.5


def test_allocator_respects_capacity():
    values, minutes = _instance(200, 1)
    for ratio in (0.05, 0.25, 0.9):
        cap = ratio * minutes[:, 1].sum()
        res = allocate_ev(values, minutes, Constraints(agent_minutes=cap))
        used = minutes[np.arange(len(res.actions)), res.actions].sum()
        assert used <= cap + 1e-6


def test_allocator_respects_cardinality_cap():
    values, minutes = _instance(200, 2)
    res = allocate_ev(values, minutes, Constraints(max_actions=17))
    assert int((res.actions != 0).sum()) <= 17


def test_unconstrained_allocation_is_plain_argmax():
    values, minutes = _instance(100, 3)
    res = allocate_ev(values, minutes, Constraints())
    assert np.array_equal(res.actions, values.argmax(axis=1))


def test_allocator_never_takes_a_negative_value_action_when_unconstrained():
    n = 50
    values = np.column_stack([np.zeros(n), -np.ones(n)])
    minutes = np.column_stack([np.zeros(n), np.ones(n)])
    res = allocate_ev(values, minutes, Constraints())
    assert (res.actions == 0).all()


def test_rank_policy_fills_capacity_in_score_order():
    n = 100
    rng = np.random.default_rng(0)
    score = rng.random(n)
    minutes = np.column_stack([np.zeros(n), np.full(n, 10.0)])
    cap = 10.0 * 30  # room for exactly 30 calls
    res = allocate_rank(score, minutes, Constraints(agent_minutes=cap), primary_action=1)
    chosen = np.where(res.actions == 1)[0]
    assert len(chosen) == 30
    top30 = set(np.argsort(-score)[:30].tolist())
    assert set(chosen.tolist()) == top30


def test_enforce_true_capacity_truncates_worst_priority_first():
    n = 20
    actions = np.ones(n, dtype=int)
    priority = np.arange(n, dtype=float)  # 0 is worst
    true_minutes = np.column_stack([np.zeros(n), np.full(n, 10.0)])
    cons = Constraints(agent_minutes=100.0)  # room for 10
    out, info = enforce_true_capacity(true_minutes, actions, priority, cons)
    assert out.sum() == 10
    assert (out[:10] == 0).all(), "the lowest-priority assignments must be dropped"
    assert (out[10:] == 1).all()
    assert info["truncated"] == 10


def test_enforce_true_capacity_is_a_noop_when_feasible():
    n = 10
    actions = np.ones(n, dtype=int)
    true_minutes = np.column_stack([np.zeros(n), np.full(n, 1.0)])
    out, info = enforce_true_capacity(
        true_minutes, actions, np.arange(n, dtype=float), Constraints(agent_minutes=1e6)
    )
    assert np.array_equal(out, actions)
    assert info["truncated"] == 0


def test_a_model_that_underestimates_effort_gets_truncated():
    """The point of enforcing capacity with *true* minutes."""
    n = 50
    believed = np.column_stack([np.zeros(n), np.full(n, 1.0)])
    actual = np.column_stack([np.zeros(n), np.full(n, 10.0)])
    ev = np.column_stack([np.zeros(n), np.full(n, 100.0)])
    cons = Constraints(agent_minutes=100.0)
    dec = EVPolicy().decide(ActionValueEstimate(ev=ev, minutes=believed), cons)
    assert int((dec.actions != 0).sum()) == n  # it thinks it can call everyone
    out, info = enforce_true_capacity(actual, dec.actions, dec.priority, cons)
    assert int((out != 0).sum()) == 10
    assert info["truncated"] == 40


def test_lower_bound_policy_is_more_conservative_than_the_mean():
    n = 200
    rng = np.random.default_rng(0)
    ev = np.column_stack([np.zeros(n), rng.normal(5.0, 1.0, n)])
    samples = rng.normal(ev[None, :, :], 30.0, size=(200, n, 2))
    samples[:, :, 0] = 0.0
    minutes = np.column_stack([np.zeros(n), np.ones(n)])
    est = ActionValueEstimate(ev=ev, minutes=minutes, ev_samples=samples)
    mean_dec = EVPolicy().decide(est, Constraints())
    lcb_dec = LowerBoundEVPolicy(0.10).decide(est, Constraints())
    assert (lcb_dec.actions != 0).sum() < (mean_dec.actions != 0).sum()


def test_lower_bound_policy_falls_back_to_the_mean_without_samples():
    n = 30
    ev = np.column_stack([np.zeros(n), np.ones(n)])
    minutes = np.column_stack([np.zeros(n), np.ones(n)])
    est = ActionValueEstimate(ev=ev, minutes=minutes)
    dec = LowerBoundEVPolicy(0.10).decide(est, Constraints())
    assert (dec.actions == 1).all()
    assert dec.diagnostics["used_uncertainty"] == 0.0


def test_abstention_reduces_coverage():
    n = 200
    rng = np.random.default_rng(1)
    ev = np.column_stack([np.zeros(n), rng.normal(10, 5, n)])
    minutes = np.column_stack([np.zeros(n), np.ones(n)])
    est = ActionValueEstimate(ev=ev, minutes=minutes)
    full = EVPolicy().decide(est, Constraints())
    half = AbstentionPolicy(0.5).decide(est, Constraints())
    assert (half.actions != 0).sum() <= (full.actions != 0).sum()


def test_estimate_rejects_non_finite_values():
    with pytest.raises(ValueError):
        ActionValueEstimate(ev=np.array([[0.0, np.nan]]), minutes=np.zeros((1, 2)))
    with pytest.raises(ValueError):
        ActionValueEstimate(ev=np.zeros((2, 2)), minutes=np.zeros((3, 2)))
