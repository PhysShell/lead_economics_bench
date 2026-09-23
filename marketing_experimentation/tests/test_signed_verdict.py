"""Invariants for the INTERVAL -> VERDICT -> BIT decomposition.

The decomposition's whole authority comes from one structural claim: that the
significance bit is a *deterministic garbling* of the signed verdict, so
Blackwell orders them. F13 is what happens when such a claim is asserted
rather than checked -- the S0/S1 "ladder" was not a ladder for eight
commits. These tests check it on synthetic data, where the answer is known,
so a failure cannot be blamed on the estimator.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from leadbench_mx.decision import budget_problem, spike_slab_prior  # noqa: E402
from signed_verdict import (  # noqa: E402
    GARBLE, audit_bit_is_garbling, evsi_analytic, reweight_negative,
    verdict_index,
)


def a_problem(thetas=(-0.10, -0.05, 0.0, 0.05, 0.15)):
    th = np.array(thetas)
    grid = np.linspace(-0.15, 0.25, 81)
    pri = spike_slab_prior(grid)
    edges = np.concatenate(([-np.inf], (th[:-1] + th[1:]) / 2, [np.inf]))
    idx = np.digitize(grid, edges) - 1
    p = np.array([pri[idx == j].sum() for j in range(len(th))])
    return budget_problem(th, p / p.sum())


def random_verdict_likelihood(rng, n_theta: int) -> np.ndarray:
    p = rng.dirichlet(np.ones(3) * 0.7, size=n_theta)
    return p


def test_garble_maps_verdict_to_bit():
    """Row 0 of GARBLE must pick out exactly `inconclusive`, row 1 the two
    signed cells. Getting this matrix backwards would silently invert the
    entire result, and nothing downstream would notice."""
    assert GARBLE.shape == (2, 3)
    assert GARBLE[0].tolist() == [0.0, 1.0, 0.0]
    assert GARBLE[1].tolist() == [1.0, 0.0, 1.0]
    # every verdict maps to exactly one bit
    assert np.allclose(GARBLE.sum(axis=0), 1.0)


def test_verdict_index_reads_the_interval_not_the_estimate():
    """The verdict is a function of the bounds alone. A point estimate far
    from zero with an interval spanning it is INCONCLUSIVE -- if this ever
    starts consulting att_pct, the chain stops being a garbling of the
    interval and the theorem stops applying."""
    d = pd.DataFrame({
        "att_pct": [0.50, -0.50, 0.001, -0.001],
        "ci_lower": [-0.10, -0.90, 0.0005, -0.90],
        "ci_upper": [0.90, -0.10, 0.0020, -0.0001],
    })
    assert verdict_index(d).tolist() == [1, 0, 2, 0]


def test_significant_must_equal_verdict_not_inconclusive():
    """The premise check has to fail when the premise fails. This is F13 in
    miniature: a `significant` column computed from something other than the
    interval."""
    d = pd.DataFrame({
        "ci_lower": [0.01, -0.10, -0.90],
        "ci_upper": [0.09, 0.10, -0.10],
        "significant": [True, False, True],
    })
    assert audit_bit_is_garbling(d) == (3, 3)
    d.loc[2, "significant"] = False          # now it disagrees with the CI
    assert audit_bit_is_garbling(d) == (2, 3)


@pytest.mark.parametrize("seed", range(25))
def test_blackwell_holds_for_every_random_likelihood(seed):
    """EVSI(VERDICT) >= EVSI(BIT), for arbitrary likelihoods and arbitrary
    priors. This is the inequality the whole decomposition rests on, and it
    is a theorem, so random data must not be able to break it."""
    rng = np.random.default_rng(seed)
    problem = a_problem()
    pv = random_verdict_likelihood(rng, len(problem.theta))
    pb = pv @ GARBLE.T
    v, b = evsi_analytic(problem, pv), evsi_analytic(problem, pb)
    assert v >= b - 1e-9, f"garbling gained value: V={v}, B={b}"
    assert b >= -1e-9, "EVSI of the bit went negative under its own model"
    assert v <= problem.evpi() + 1e-9, "EVSI exceeded EVPI"


@pytest.mark.parametrize("w", [0.0, 0.02, 0.2, 0.5, 0.9, 1.0])
def test_blackwell_survives_the_negative_mass_sweep(w):
    """The sweep is where a violation nearly shipped: the self-test ran at
    the base prior only, while shares were printed at six others. Blackwell
    is a statement for EVERY prior, so it is checked at every prior used."""
    rng = np.random.default_rng(7)
    problem = a_problem()
    if 0.0 < w < 1.0:
        problem = reweight_negative(problem, w)
        assert np.isclose(problem.prior[problem.theta < 0].sum(), w)
    pv = random_verdict_likelihood(rng, len(problem.theta))
    assert evsi_analytic(problem, pv) >= evsi_analytic(problem, pv @ GARBLE.T) - 1e-9


def test_an_uninformative_signal_is_worth_nothing():
    """A likelihood identical across truths carries no information, so both
    rungs must price at exactly zero. If smoothing or a normalisation bug
    ever leaks value in, it shows up here first."""
    problem = a_problem()
    pv = np.tile(np.array([0.2, 0.5, 0.3]), (len(problem.theta), 1))
    assert evsi_analytic(problem, pv) == pytest.approx(0.0, abs=1e-9)
    assert evsi_analytic(problem, pv @ GARBLE.T) == pytest.approx(0.0, abs=1e-9)


def test_the_sign_is_worth_nothing_when_no_verdict_is_ever_negative():
    """The decomposition must attribute value to the sign only when the sign
    varies. With p(negative) = 0 at every truth, VERDICT and BIT are the same
    experiment relabelled, so V - B must be exactly zero -- not merely small.
    This is the null case the finding has to be distinguishable from."""
    rng = np.random.default_rng(3)
    problem = a_problem()
    pv = random_verdict_likelihood(rng, len(problem.theta))
    pv[:, 0] = 0.0
    pv = pv / pv.sum(axis=1, keepdims=True)
    gap = evsi_analytic(problem, pv) - evsi_analytic(problem, pv @ GARBLE.T)
    assert gap == pytest.approx(0.0, abs=1e-9)


def test_the_sign_is_worth_something_when_it_separates_the_truths():
    """The complementary case, so the test above cannot pass by the metric
    being dead. A verdict that reports the sign correctly at the extremes
    must beat a bit that merges them."""
    problem = a_problem()
    n = len(problem.theta)
    pv = np.full((n, 3), 0.02)
    for j, t in enumerate(problem.theta):
        pv[j] = [0.90, 0.08, 0.02] if t < 0 else (
            [0.02, 0.08, 0.90] if t > 0 else [0.05, 0.90, 0.05])
    pv = pv / pv.sum(axis=1, keepdims=True)
    gap = evsi_analytic(problem, pv) - evsi_analytic(problem, pv @ GARBLE.T)
    assert gap > 1.0, "a sign-perfect verdict should beat an unsigned bit"


def test_reweight_negative_preserves_shape_within_each_half():
    """The sweep must move mass ACROSS zero without reshaping either side --
    otherwise it varies two things at once and the sweep means nothing."""
    problem = a_problem()
    neg = problem.theta < 0
    before = problem.prior[neg] / problem.prior[neg].sum()
    after = reweight_negative(problem, 0.4)
    assert np.allclose(after.prior[neg] / after.prior[neg].sum(), before)
    assert np.isclose(after.prior.sum(), 1.0)
    assert np.isclose(after.prior[neg].sum(), 0.4)
