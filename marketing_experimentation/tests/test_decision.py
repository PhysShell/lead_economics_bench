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
