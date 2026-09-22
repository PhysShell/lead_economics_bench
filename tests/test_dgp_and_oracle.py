"""DGP invariants and Oracle sanity."""

from __future__ import annotations

import numpy as np
import pytest

from leadbench.economics import Constraints, capacity_for_ratio, realized_net_value
from leadbench.evaluation.runner import _oracle_value
from leadbench.models.base import ActionValueEstimate
from leadbench.policies.decision import EVPolicy, enforce_true_capacity
from leadbench.synthetic.config import REGIMES, make_config
from leadbench.synthetic.dgp import generate


def _ds(regime="easy_randomized", n=6000, seed=3):
    return generate(make_config(regime, n_leads=n, seed=seed))


def test_stated_probabilities_match_realized_rates():
    """The mean of p_funded_a{a} must equal the empirical rate in that arm.

    This is the check that caught a truth-column name collision where the
    per-stage P(funded | application) silently overwrote the overall funnel
    probability.
    """
    ds = _ds(n=40_000, seed=11)
    obs, truth = ds.observed, ds.truth
    for a in range(ds.n_actions):
        arm = obs["action"] == a
        assert arm.sum() > 1000
        empirical = float(obs.loc[arm, "funded"].mean())
        stated = float(truth[f"p_funded_a{a}"].mean())
        assert empirical == pytest.approx(stated, abs=0.01), (
            f"arm {a}: empirical {empirical:.4f} vs stated {stated:.4f}"
        )


def test_overall_probability_is_the_product_of_stage_probabilities():
    ds = _ds(n=3000)
    t = ds.truth
    for a in range(ds.n_actions):
        prod = np.ones(len(t))
        for s in ("contact", "qualified", "application", "funded"):
            prod = prod * t[f"p_stage_{s}_a{a}"].to_numpy()
        assert np.allclose(prod, t[f"p_funded_a{a}"].to_numpy())


def test_potential_outcomes_are_monotone_in_probability():
    """Common random numbers: a higher stage probability cannot lose a conversion."""
    ds = _ds(n=8000)
    t = ds.truth
    call = ds.n_actions - 1
    p0, p1 = t["p_funded_a0"].to_numpy(), t[f"p_funded_a{call}"].to_numpy()
    y0, y1 = t["y_funded_a0"].to_numpy(), t[f"y_funded_a{call}"].to_numpy()
    # Where the call strictly dominates on every stage, it cannot lose.
    dominates = np.ones(len(t), dtype=bool)
    for s in ("contact", "qualified", "application", "funded"):
        dominates &= t[f"p_stage_{s}_a{call}"].to_numpy() >= t[f"p_stage_{s}_a0"].to_numpy()
    assert dominates.sum() > 100
    assert (y1[dominates] >= y0[dominates]).all()


def test_negative_control_has_no_effect():
    ds = _ds("negative_control_null_effect", n=20_000)
    t = ds.truth
    call = ds.n_actions - 1
    assert np.allclose(t["p_funded_a0"], t[f"p_funded_a{call}"])
    assert np.array_equal(t["y_funded_a0"], t[f"y_funded_a{call}"])
    assert abs(float(t[f"cate_a{call}"].mean())) < 1e-12


def test_propensity_not_uplift_regime_really_decouples_them():
    """The central scenario must actually contain the phenomenon it claims."""
    ds = _ds("propensity_not_uplift", n=40_000, seed=5)
    t = ds.truth
    call = ds.n_actions - 1
    p0 = t["p_funded_a0"].to_numpy()
    cate = t[f"cate_a{call}"].to_numpy()
    from scipy import stats

    rho = stats.spearmanr(p0, cate).statistic
    assert rho < 0.5, (
        f"baseline propensity and uplift are still strongly aligned (rho={rho:.2f}); "
        "the regime would not test what RQ2 needs"
    )


def test_logging_propensities_are_valid_distributions():
    for regime in ("easy_randomized", "selection_bias", "confounded_check"):
        if regime == "confounded_check":
            regime = "hidden_confounding"
        ds = _ds(regime, n=4000)
        cols = [f"propensity_{n}" for n in ds.actions]
        p = ds.observed[cols].to_numpy()
        assert np.allclose(p.sum(axis=1), 1.0, atol=1e-9)
        assert (p > 0).all(), "a zero propensity destroys off-policy identifiability"


def test_hidden_confounder_is_not_in_the_feature_list():
    ds = _ds("hidden_confounding", n=2000)
    assert "x_conf" not in ds.feature_columns
    assert "x_conf" not in ds.observed.columns
    ds2 = _ds("observed_confounding", n=2000)
    assert "x_conf" in ds2.feature_columns


def test_oracle_beats_every_fixed_policy_under_the_same_constraint():
    ds = _ds("capacity_value_heterogeneity", n=8000, seed=2)
    cap = capacity_for_ratio(ds, 0.25)
    cons = Constraints(agent_minutes=cap)
    oracle = _oracle_value(ds, cons)

    n = len(ds.truth)
    call = ds.n_actions - 1
    true_minutes = np.column_stack(
        [ds.truth[f"minutes_a{a}"].to_numpy() for a in range(ds.n_actions)]
    )
    rng = np.random.default_rng(0)
    for _ in range(5):
        score = rng.random(n)
        ev = np.zeros((n, ds.n_actions))
        ev[:, call] = score
        est = ActionValueEstimate(ev=ev, minutes=true_minutes, score=score)
        dec = EVPolicy().decide(est, cons)
        actions, _ = enforce_true_capacity(true_minutes, dec.actions, dec.priority, cons)
        assert realized_net_value(ds, actions).net_value <= oracle + 1e-6

    assert realized_net_value(ds, np.zeros(n, dtype=int)).net_value <= oracle + 1e-6


def test_oracle_respects_the_capacity_constraint():
    ds = _ds(n=6000)
    for ratio in (0.05, 0.25, 0.5):
        cap = capacity_for_ratio(ds, ratio)
        cons = Constraints(agent_minutes=cap)
        n_actions = ds.n_actions
        ev = np.column_stack([ds.truth[f"ev_a{a}"].to_numpy() for a in range(n_actions)])
        mins = np.column_stack(
            [ds.truth[f"minutes_a{a}"].to_numpy() for a in range(n_actions)]
        )
        dec = EVPolicy().decide(ActionValueEstimate(ev=ev, minutes=mins), cons)
        actions, _ = enforce_true_capacity(mins, dec.actions, dec.priority, cons)
        used = mins[np.arange(len(actions)), actions].sum()
        assert used <= cap + 1e-6


@pytest.mark.parametrize("regime", sorted(REGIMES))
def test_every_regime_generates_and_is_internally_consistent(regime):
    ds = generate(make_config(regime, n_leads=1500, seed=1))
    assert len(ds.observed) == len(ds.truth)
    assert ds.observed["lead_id"].is_unique
    for a in range(ds.n_actions):
        p = ds.truth[f"p_funded_a{a}"].to_numpy()
        assert ((p >= 0) & (p <= 1)).all()
    assert set(ds.feature_columns).issubset(ds.observed.columns)


def test_duplicate_regime_creates_repeat_entities():
    ds = generate(make_config("noisy_crm", n_leads=5000, seed=1))
    assert ds.observed["lead_id"].is_unique
    assert not ds.observed["person_id"].is_unique, (
        "the dirty-CRM regime must contain duplicated humans so the split "
        "hygiene check has something to catch"
    )


def test_censoring_blanks_unresolved_outcomes():
    ds = generate(make_config("delayed_censored", n_leads=8000, seed=1))
    assert ds.observed["censored"].any()
    censored = ds.observed[ds.observed["censored"]]
    assert censored["funded"].isna().any()
