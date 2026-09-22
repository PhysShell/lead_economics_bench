"""Invariants for the value-of-information layer.

These exist because the first Layer 3 pass shipped a number that violated
one of them -- a free experiment that was not worth running -- and nothing
caught it. Every property below would have.
"""

from __future__ import annotations

import numpy as np
import pytest

from leadbench_mx.decision import (
    DecisionProblem,
    check_invariants,
    enbs,
    evsi,
    gate_information_loss,
    two_point_problem,
    value_of_significance_gate,
)


def binary_likelihoods(fpr: float, fnr: float) -> tuple[np.ndarray, np.ndarray]:
    """p(y | theta) and p(y) for a significant/not-significant signal."""
    p_sig = np.array([fpr, 1.0 - fnr])          # P(significant | theta)
    like = np.vstack([1.0 - p_sig, p_sig])       # rows: not-sig, sig
    return like, p_sig


def marginal(prior: np.ndarray, like: np.ndarray) -> np.ndarray:
    return like @ prior


# -- the invariant that was violated ----------------------------------------

@pytest.mark.parametrize("pi", [0.05, 0.2, 0.5, 0.8, 0.95])
@pytest.mark.parametrize("ratio", [0.1, 0.5, 1.0, 3.0, 10.0])
@pytest.mark.parametrize("fpr,fnr", [(0.046, 0.913), (0.278, 0.379),
                                     (0.169, 0.571), (0.198, 0.662)])
def test_free_information_never_hurts(pi, ratio, fpr, fnr):
    """EVSI >= 0 for every method, prior and cost ratio.

    You can always look at the result and then do what you would have done
    anyway, so information at zero price cannot have negative value. The
    first Layer 3 model reported it did, over 70% of this plane.
    """
    c_fn = 500_000.0
    p = two_point_problem(pi, ratio * c_fn, c_fn)
    like, _ = binary_likelihoods(fpr, fnr)
    assert evsi(p, like, marginal(p.prior, like)) >= -1e-9


@pytest.mark.parametrize("pi", [0.1, 0.3, 0.5, 0.7, 0.9])
@pytest.mark.parametrize("ratio", [0.2, 1.0, 5.0])
def test_evsi_never_exceeds_evpi(pi, ratio):
    """An experiment cannot be worth more than being told the truth."""
    c_fn = 500_000.0
    p = two_point_problem(pi, ratio * c_fn, c_fn)
    like, _ = binary_likelihoods(0.169, 0.571)
    checks = check_invariants(p, like, marginal(p.prior, like))
    assert checks["ok"], checks


def test_useless_experiment_is_worth_nothing():
    """A signal independent of the truth has EVSI = 0 exactly."""
    p = two_point_problem(0.4, 300_000.0, 500_000.0)
    # Same distribution under both hypotheses: pure noise.
    like = np.array([[0.7, 0.7], [0.3, 0.3]])
    assert evsi(p, like, marginal(p.prior, like)) == pytest.approx(0.0, abs=1e-9)


def test_perfect_experiment_is_worth_evpi():
    """A signal that reveals theta exactly must attain the ceiling."""
    p = two_point_problem(0.4, 300_000.0, 500_000.0)
    like = np.eye(2)  # signal 0 iff theta 0, signal 1 iff theta 1
    assert evsi(p, like, marginal(p.prior, like)) == pytest.approx(p.evpi())


def test_evpi_is_zero_when_one_action_dominates_everywhere():
    """If the same action is best under every theta, knowing theta is worthless."""
    theta = np.array([0.0, 0.05])
    prior = np.array([0.5, 0.5])
    utility = np.array([[-10.0, -20.0], [0.0, -1.0]])  # action 1 always better
    p = DecisionProblem(theta, prior, utility, ("a", "b"))
    assert p.evpi() == pytest.approx(0.0)


# -- the gate, which is a policy rather than a bug ---------------------------

def test_significance_gate_can_be_worse_than_the_prior():
    """The finding that motivated all of this, pinned as a property.

    A forced gate must obey its own verdict, so with a high false-negative
    rate it can be beaten by simply acting on the prior. This is a fact about
    conventional practice, not an arithmetic error -- and the optimal policy
    on the identical signal cannot do this.
    """
    pi, c_fn = 0.6, 500_000.0
    p = two_point_problem(pi, 1.0 * c_fn, c_fn)
    fpr, fnr = 0.046, 0.913  # geolift
    like, p_sig = binary_likelihoods(fpr, fnr)

    gate = value_of_significance_gate(p, p_sig, "scale", "hold")
    assert gate < p.value_no_experiment()               # the gate loses
    assert evsi(p, like, marginal(p.prior, like)) >= 0  # the signal does not


def test_gate_loss_is_non_negative():
    """Using a signal optimally is never worse than gating on it."""
    c_fn = 500_000.0
    for pi in (0.1, 0.4, 0.7):
        for fpr, fnr in ((0.046, 0.913), (0.278, 0.379)):
            p = two_point_problem(pi, 2.0 * c_fn, c_fn)
            like, p_sig = binary_likelihoods(fpr, fnr)
            loss = gate_information_loss(
                p, like, marginal(p.prior, like), p_sig, "scale", "hold"
            )
            assert loss >= -1e-9


# -- cost enters only after the information is valued ------------------------

def test_enbs_is_evsi_minus_cost():
    p = two_point_problem(0.5, 500_000.0, 500_000.0)
    like, _ = binary_likelihoods(0.169, 0.571)
    m = marginal(p.prior, like)
    assert enbs(p, like, m, 40_000.0) == pytest.approx(evsi(p, like, m) - 40_000.0)


def test_expensive_experiment_is_rejected_not_the_information():
    """DO-NOT-RUN must come from the cost exceeding the value, never from the
    information being worth less than nothing."""
    p = two_point_problem(0.5, 500_000.0, 500_000.0)
    like, _ = binary_likelihoods(0.046, 0.913)
    m = marginal(p.prior, like)
    assert evsi(p, like, m) >= 0
    assert enbs(p, like, m, 10_000_000.0) < 0


def test_prior_must_be_normalised():
    with pytest.raises(ValueError):
        DecisionProblem(np.array([0.0, 1.0]), np.array([0.5, 0.9]),
                        np.zeros((2, 2)), ("a", "b"))


# ---------------------------------------------------------------------------
# The five-action budget problem. Two actions can only answer "which side of
# a threshold"; a real team asks "how much", and that changes what an
# experiment is worth.
# ---------------------------------------------------------------------------

from leadbench_mx.decision import (  # noqa: E402
    DEFAULT_ACTIONS, DEFAULT_MULTIPLIERS, budget_problem, spike_slab_prior,
    theta_grid,
)


def _default_problem():
    th = theta_grid()
    return th, budget_problem(th, spike_slab_prior(th))


def test_optimal_action_is_monotone_in_the_truth():
    """Bigger true lift must never call for less spend. A payoff that failed
    this would be modelling something other than a budget."""
    th, p = _default_problem()
    opt = p.utility.argmax(axis=0)
    assert np.all(np.diff(opt) >= 0), f"not monotone: {opt}"


def test_every_action_is_optimal_somewhere():
    """An action that is never right for any truth is not part of the
    decision, and would silently inflate the action count without changing
    the problem."""
    _, p = _default_problem()
    assert set(p.utility.argmax(axis=0)) == set(range(len(DEFAULT_ACTIONS)))


def test_hold_is_the_prior_optimal_action():
    """With a spike-and-slab prior centred near breakeven, doing nothing is
    the right default. If it were not, the problem would be begging the
    question the experiment is meant to answer."""
    _, p = _default_problem()
    assert p.best_action_no_experiment() == "hold"


def test_adjustment_cost_is_what_makes_the_action_set_matter():
    """Without a quadratic adjustment cost the optimum is always the most
    extreme action available, and every intermediate option is dead weight."""
    th = theta_grid()
    pr = spike_slab_prior(th)
    flat = budget_problem(th, pr, adjust_cost=0.0)
    opt = set(flat.utility.argmax(axis=0))
    assert opt <= {0, len(DEFAULT_MULTIPLIERS) - 1}, (
        f"with no adjustment cost only the extremes should ever win, got {opt}")


def test_richer_nested_action_set_raises_evpi():
    """Adding options to an existing set can only make knowing theta more
    valuable, because the no-information baseline is unchanged."""
    th = theta_grid()
    pr = spike_slab_prior(th)
    nested = [
        (("hold", "increase"), (1.0, 1.25)),
        (("hold", "increase", "increase hard"), (1.0, 1.25, 1.6)),
        (("cut", "hold", "increase", "increase hard"), (0.8, 1.0, 1.25, 1.6)),
        (DEFAULT_ACTIONS, DEFAULT_MULTIPLIERS),
    ]
    evpis = [budget_problem(th, pr, multipliers=m, action_names=n).evpi()
             for n, m in nested]
    assert all(b >= a - 1e-9 for a, b in zip(evpis, evpis[1:])), evpis
    assert evpis[-1] > evpis[0], "the full set should be strictly better"


def test_non_nested_action_set_can_lower_evpi():
    """The guard on the test above. 'Richer action set raises VOI' is true
    for sets you ADD to, and false for sets you REPLACE. Dropping the hedge
    wrecks the no-information baseline and inflates EVPI, which looks like
    information becoming more valuable and is not.
    """
    th = theta_grid()
    pr = spike_slab_prior(th)
    extremes = budget_problem(th, pr, multipliers=(0.5, 1.6),
                              action_names=("cut hard", "increase hard"))
    full = budget_problem(th, pr)
    assert extremes.evpi() > full.evpi()
    assert extremes.value_no_experiment() < full.value_no_experiment()


def test_cutting_is_worth_more_information_than_raising():
    """The largest EVPI gain comes from being able to cut, not to raise --
    because a quarter of the prior mass sits below zero. This is the
    decision-theoretic reason the theta = -5% sign mutation (M6b) matters."""
    th = theta_grid()
    pr = spike_slab_prior(th)
    base = budget_problem(th, pr, multipliers=(1.0, 1.25),
                          action_names=("hold", "increase"))
    add_up = budget_problem(th, pr, multipliers=(1.0, 1.25, 1.6),
                            action_names=("hold", "increase", "increase hard"))
    add_down = budget_problem(th, pr, multipliers=(0.8, 1.0, 1.25),
                              action_names=("cut", "hold", "increase"))
    assert add_down.evpi() - base.evpi() > add_up.evpi() - base.evpi()


def test_prior_has_real_mass_on_a_channel_that_destroys_money():
    """A prior with no negative mass cannot represent the question a business
    most needs answered, and would make the sign mutation untestable."""
    th = theta_grid()
    pr = spike_slab_prior(th)
    assert pr[th < 0].sum() > 0.15
    assert np.isclose(pr.sum(), 1.0)
