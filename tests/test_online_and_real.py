"""Tests for the online (bandit) and real-data (OPE) tracks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leadbench.economics import Economics
from leadbench.evaluation.online import (
    OnlineSpec,
    materialise_observation,
    run_online_scenario,
)
from leadbench.evaluation.real_track import (
    RealSpec,
    ResponseRanker,
    TwoModel,
    _budget_policy,
    run_real_scenario,
)
from leadbench.models.bandits import ONLINE_LEARNERS, LinUCB, ThompsonSampling
from leadbench.synthetic.config import make_config
from leadbench.synthetic.dgp import generate


# --- bandits ---------------------------------------------------------------


def test_linucb_learns_a_better_arm_from_feedback():
    rng = np.random.default_rng(0)
    d = 4
    b = LinUCB(n_actions=2, n_features=d, seed=0, ridge=1.0)
    X = rng.standard_normal((4000, d))
    # Arm 1 is genuinely better for everybody.
    y = np.where(rng.random(4000) < 0.5, 1.0, 0.0)
    actions = rng.integers(0, 2, 4000)
    rewards = np.where(actions == 1, y, y * 0.2)
    b.update(X, actions, rewards)
    p = b.mean_probability(X)
    assert p[:, 1].mean() > p[:, 0].mean()


def test_exploration_bonus_shrinks_as_evidence_accumulates():
    rng = np.random.default_rng(1)
    d = 3
    b = LinUCB(n_actions=2, n_features=d, seed=0, alpha=1.0)
    X = rng.standard_normal((50, d))
    before = b.score(X) - b.mean_probability(X)
    b.update(
        rng.standard_normal((5000, d)),
        rng.integers(0, 2, 5000),
        rng.random(5000),
    )
    after = b.score(X) - b.mean_probability(X)
    assert after.mean() < before.mean(), "the UCB bonus must decay with data"


def test_thompson_sampling_is_stochastic_but_seeded():
    rng = np.random.default_rng(2)
    X = rng.standard_normal((100, 3))
    a = ThompsonSampling(n_actions=2, n_features=3, seed=7)
    s1, s2 = a.score(X), a.score(X)
    assert not np.allclose(s1, s2), "Thompson sampling must draw fresh each call"
    b = ThompsonSampling(n_actions=2, n_features=3, seed=7)
    assert np.allclose(b.score(X), s1), "the same seed must reproduce the draw"


@pytest.mark.parametrize("key", sorted(ONLINE_LEARNERS))
def test_every_learner_produces_valid_probabilities(key):
    rng = np.random.default_rng(3)
    X = rng.standard_normal((200, 5))
    lr = ONLINE_LEARNERS[key](n_actions=2, n_features=5, seed=0)
    lr.update(X, rng.integers(0, 2, 200), rng.random(200))
    s = lr.score(X)
    assert s.shape == (200, 2)
    assert np.isfinite(s).all()
    assert ((s >= 0) & (s <= 1)).all()


# --- the simulator's decision log -----------------------------------------


def test_materialised_observation_reflects_the_action_taken():
    ds = generate(make_config("easy_randomized", n_leads=3000, seed=0))
    idx = np.arange(500)
    call = ds.n_actions - 1
    econ = Economics()

    all_call = materialise_observation(ds, idx, np.full(500, call), econ)
    none = materialise_observation(ds, idx, np.zeros(500, dtype=int), econ)

    # Outcomes must equal the potential outcome for the action taken.
    assert np.array_equal(
        all_call["funded"].to_numpy(),
        ds.truth[f"y_funded_a{call}"].to_numpy()[:500],
    )
    assert np.array_equal(
        none["funded"].to_numpy(), ds.truth["y_funded_a0"].to_numpy()[:500]
    )
    # Effort and revenue must follow the action too.
    assert all_call["minutes_spent"].sum() > 0
    assert none["minutes_spent"].sum() == 0
    assert (none.loc[none["funded"] == 0, "realized_net_contribution"] == 0).all()


def test_online_scenario_runs_and_oracle_leads():
    spec = OnlineSpec(
        name="online_test", regime="easy_randomized", n_leads=6000,
        seeds=(0,), n_periods=4, capacity_ratio=0.25,
    )
    df = run_online_scenario(spec, verbose=False)
    assert len(df) > 0
    oracle = df.loc[df["competitor"] == "oracle", "net_value"].iloc[0]
    for _, r in df.iterrows():
        assert r["net_value"] <= oracle + 1e-6, (
            f"{r['competitor']} beat the Oracle, which is impossible"
        )
    # Every competitor should be at least as good as doing nothing on average.
    assert df["pct_of_oracle_incremental"].max() == pytest.approx(100.0)


# --- real-data track -------------------------------------------------------


def test_budget_policy_treats_exactly_the_top_share():
    score = np.arange(1000, dtype=float)
    for b in (0.1, 0.25, 0.5):
        a = _budget_policy(score, b)
        assert a.sum() == int(np.floor(b * 1000))
        # The highest scores must be the treated ones.
        assert a[np.argsort(-score)[: a.sum()]].all()


def test_real_track_end_to_end_on_a_synthetic_randomized_dataset():
    """Exercise the OPE path without needing a downloaded dataset."""
    from leadbench.data.real import RealDataset

    rng = np.random.default_rng(0)
    n = 20_000
    X = rng.standard_normal((n, 4))
    t = (rng.random(n) < 0.5).astype(int)
    # Uplift is genuinely heterogeneous in x0.
    p = 0.05 + 0.10 * (X[:, 0] > 0) * t
    y = (rng.random(n) < p).astype(int)
    df = pd.DataFrame(X, columns=[f"f{i}" for i in range(4)])
    df["treatment"] = t
    df["visit"] = y
    ds = RealDataset(
        name="synthetic_rct",
        df=df,
        feature_columns=[f"f{i}" for i in range(4)],
        categorical_columns=[],
        treatment_column="treatment",
        outcome_column="visit",
        value_column=None,
        propensity=np.full(n, 0.5),
    )
    spec = RealSpec(
        name="probe", dataset="synthetic", outcome="visit",
        budgets=(0.25,), seeds=(0,), n_boot=80,
    )
    out = run_real_scenario(
        spec, ds,
        candidates=[lambda: ResponseRanker(kind="lightgbm", n_estimators=80),
                    lambda: TwoModel(kind="lightgbm", n_estimators=80)],
        verbose=False,
    )
    assert (out["status"] == "ok").all()
    assert {"ips_value", "snips_value", "dr_value"}.issubset(out.columns)
    # A model that knows the true effect modifier must beat response ranking.
    two = out.loc[out["candidate"] == "t_learner", "dr_value"].iloc[0]
    resp = out.loc[out["candidate"] == "response_score", "dr_value"].iloc[0]
    assert two > resp, "uplift should win when uplift is what varies"
    # The estimator must report honest support diagnostics.
    assert out["violation_rate"].iloc[0] == 0.0  # 50/50 randomisation
