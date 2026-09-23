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
    GARBLE, audit_bit_is_garbling, cluster_bootstrap_draws, dirichlet_draws,
    evsi_batch, reweight_negative, sign_loss_posterior, verdict_index,
    verdict_matrix,
)


def evsi_analytic(problem, p):
    """Single-likelihood convenience over the batched implementation."""
    return float(evsi_batch(problem, np.asarray(p)[None])[0])


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


# ---------------------------------------------------------------------------
# The Dirichlet posterior propagation. Added after a reader pointed out that a
# plug-in number plus the sentence "alpha moves this by 2-3x" is not a
# measurement of anything -- the uncertainty belongs inside the result.
# ---------------------------------------------------------------------------

def test_dirichlet_draws_are_probability_vectors():
    rng = np.random.default_rng(0)
    counts = np.array([[10.0, 40.0, 0.0], [0.0, 5.0, 45.0]])
    p = dirichlet_draws(counts, 0.5, 500, rng)
    assert p.shape == (500, 2, 3)
    assert np.allclose(p.sum(axis=-1), 1.0)
    assert (p > 0).all(), "a zero cell would make a held-out row impossible"


def test_dirichlet_concentrates_as_counts_grow():
    """The posterior must tighten with data. If it does not, the interval is
    decorative and the 'more runs per truth' recommendation is unfounded."""
    rng = np.random.default_rng(1)
    thin = dirichlet_draws(np.array([[5.0, 15.0, 5.0]]), 0.5, 4000, rng)
    thick = dirichlet_draws(np.array([[500.0, 1500.0, 500.0]]), 0.5, 4000, rng)
    assert thick[:, 0, 0].std() < thin[:, 0, 0].std() / 5


def test_alpha_pulls_an_unobserved_cell_off_zero():
    """The whole reason alpha is load-bearing: p(negative | theta=+15%) is
    0/100 for two tools, and alpha alone decides how impossible that is."""
    rng = np.random.default_rng(2)
    counts = np.array([[0.0, 40.0, 60.0]])
    small = dirichlet_draws(counts, 0.05, 4000, rng)[:, 0, 0].mean()
    large = dirichlet_draws(counts, 2.0, 4000, rng)[:, 0, 0].mean()
    assert large > 10 * small


@pytest.mark.parametrize("seed", range(10))
def test_every_posterior_draw_satisfies_blackwell(seed):
    """Not 'on average' and not 'to within Monte Carlo error'. Each draw is a
    complete likelihood, so V >= B is exact for each one, and the minimum over
    draws is the assertion worth making."""
    rng = np.random.default_rng(seed)
    problem = a_problem()
    counts = rng.integers(0, 30, size=(len(problem.theta), 3)).astype(float)
    p = dirichlet_draws(counts, 0.5, 2000, rng)
    gap = evsi_batch(problem, p) - evsi_batch(problem, p @ GARBLE.T)
    assert gap.min() >= -1e-9
    assert evsi_batch(problem, p).min() >= -1e-9


def test_sign_loss_posterior_reports_a_real_interval():
    problem = a_problem()
    counts = np.array([[40.0, 10.0, 0.0], [20.0, 25.0, 5.0],
                       [5.0, 40.0, 5.0], [2.0, 30.0, 18.0],
                       [0.0, 15.0, 35.0]])
    r = sign_loss_posterior(problem, counts, 0.5, 4000, seed=0,
                            model="cell")
    assert r["gap_lo"] <= r["gap_med"] <= r["gap_hi"]
    assert r["gap_lo"] >= -1e-9, "a credible interval below zero breaks Blackwell"
    assert r["worst_blackwell"] >= -1e-6


def test_a_mute_channel_gives_an_interval_touching_zero():
    """GeoLift's case: when almost nothing is ever significant, the sign loss
    must come back indistinguishable from zero rather than small-but-certain.
    A method that returns a confident tiny number here is broken."""
    problem = a_problem()
    counts = np.tile(np.array([0.0, 24.0, 1.0]), (len(problem.theta), 1))
    r = sign_loss_posterior(problem, counts, 0.5, 4000, seed=0,
                            model="cell")
    assert r["gap_lo"] == pytest.approx(0.0, abs=1e-6)


def _evsi_reference(problem, p):
    """A transparent, slow EVSI for ONE likelihood matrix.

    Written as loops on purpose. `evsi_batch` is now the only implementation
    in the file, and every other test in here -- Blackwell, monotonicity,
    the mute channel -- computes through it, so all of them would agree with
    an einsum that reduced over the wrong axis. A reference that shares no
    code with it is the only thing that can catch that.
    """
    prior, util = problem.prior, problem.utility
    total = 0.0
    for y in range(p.shape[1]):
        marg = sum(prior[j] * p[j, y] for j in range(len(prior)))
        if marg <= 0:
            continue
        post = [prior[j] * p[j, y] / marg for j in range(len(prior))]
        best = max(sum(util[a, j] * post[j] for j in range(len(prior)))
                   for a in range(util.shape[0]))
        total += marg * best
    return total - problem.value_no_experiment()


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_vectorised_evsi_matches_an_independent_loop(seed):
    """The einsum has no second implementation to disagree with."""
    rng = np.random.default_rng(seed)
    pr = a_problem()
    P = rng.dirichlet(np.ones(3), size=(6, len(pr.theta)))
    got = evsi_batch(pr, P)
    want = np.array([_evsi_reference(pr, P[d]) for d in range(P.shape[0])])
    assert np.allclose(got, want, atol=1e-10), (got, want)


def test_the_reference_also_agrees_on_a_two_level_signal():
    """BIT has two levels, VERDICT three; an axis bug can hide in one shape."""
    rng = np.random.default_rng(5)
    pr = a_problem()
    P = rng.dirichlet(np.ones(2), size=(4, len(pr.theta)))
    got = evsi_batch(pr, P)
    want = np.array([_evsi_reference(pr, P[d]) for d in range(P.shape[0])])
    assert np.allclose(got, want, atol=1e-10)


# ---------------------------------------------------------------------------
# The cluster bootstrap. Added after the reader found that the donor shares one
# panel seed across effect sizes (generate_panels.R:375), so the per-truth
# samples are common random numbers rather than independent draws. See F16.
# ---------------------------------------------------------------------------

def test_cluster_bootstrap_draws_are_probability_vectors():
    rng = np.random.default_rng(0)
    V = rng.integers(0, 3, size=(40, 5))
    p = cluster_bootstrap_draws(V, 0.5, 300, rng)
    assert p.shape == (300, 5, 3)
    assert np.allclose(p.sum(axis=-1), 1.0)
    assert (p > 0).all()


def test_cluster_bootstrap_recovers_the_observed_frequencies_on_average():
    """The posterior must be centred on the data, or every interval built
    from it is displaced before it is widened."""
    rng = np.random.default_rng(1)
    V = rng.integers(0, 3, size=(200, 4))
    p = cluster_bootstrap_draws(V, 0.5, 4000, rng).mean(axis=0)
    obs = np.stack([np.bincount(V[:, j], minlength=3) / len(V)
                    for j in range(V.shape[1])])
    assert np.abs(p - obs).max() < 0.02


def test_cluster_bootstrap_carries_a_whole_theta_vector_together():
    """The property the cell-wise model destroys. With two truths whose
    verdicts are identical in every cluster, the resampled probabilities must
    stay identical in every draw -- a cell-wise resample would let them drift
    apart, inventing a contrast the design cannot produce."""
    rng = np.random.default_rng(2)
    col = rng.integers(0, 3, size=60)
    V = np.column_stack([col, col])                 # perfectly linked truths
    p = cluster_bootstrap_draws(V, 0.5, 500, rng)
    assert np.abs(p[:, 0, :] - p[:, 1, :]).max() < 1e-12

    counts = np.stack([np.bincount(col, minlength=3)] * 2).astype(float)
    q = dirichlet_draws(counts, 0.5, 500, np.random.default_rng(2))
    assert np.abs(q[:, 0, :] - q[:, 1, :]).max() > 0.01, (
        "the cell-wise model should drift -- if it does not, this test is "
        "no longer distinguishing the two models")


@pytest.mark.parametrize("seed", range(8))
def test_cluster_draws_also_satisfy_blackwell(seed):
    rng = np.random.default_rng(seed)
    problem = a_problem()
    V = rng.integers(0, 3, size=(50, len(problem.theta)))
    p = cluster_bootstrap_draws(V, 0.5, 1500, rng)
    gap = evsi_batch(problem, p) - evsi_batch(problem, p @ GARBLE.T)
    assert gap.min() >= -1e-9
    assert evsi_batch(problem, p).min() >= -1e-9


def test_verdict_matrix_drops_incomplete_clusters():
    """A cluster missing a truth, resampled as if complete, would reweight the
    truths it does have. Dropping is the only safe option and must be the
    behaviour, not an accident of pandas."""
    d = pd.DataFrame({
        "scenario": ["A1"] * 5,
        "iteration": [1, 1, 2, 2, 2],
        "effect_pct": [0.0, 0.05, 0.0, 0.05, 0.15],
        "_verdict": [1, 2, 1, 2, 2],
    })
    V, keys = verdict_matrix(d, [0.0, 0.05, 0.15])
    assert len(V) == 1 and keys == [("A1", 2)]
    assert V[0].tolist() == [1, 2, 2]
