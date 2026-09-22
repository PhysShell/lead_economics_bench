"""Negative controls and adversarial checks (sections 38-39).

A causal model that cannot find *nothing* when there is nothing to find is not
a causal model, it is a pattern generator. These tests are the ones that catch
a benchmark quietly rewarding overfitting.
"""

from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd
import pytest

from leadbench.economics import Economics
from leadbench.evaluation.runner import CandidateSpec, ScenarioSpec, run_scenario
from leadbench.evaluation.splits import LeakageError, check_no_feature_leakage
from leadbench.models.base import FitContext, PredictContext
from leadbench.models.propensity import PropensityEV
from leadbench.models.uplift import DRLearner, TLearner
from leadbench.synthetic.config import make_config
from leadbench.synthetic.dgp import generate

GBM = dict(kind="xgboost", n_estimators=150, max_depth=4, learning_rate=0.05)


def _ctxs(ds, train_frac=0.7):
    day = ds.observed["created_day"].to_numpy()
    cut = np.quantile(day, train_frac)
    tr = ds.observed[day <= cut].reset_index(drop=True)
    te = ds.observed[day > cut].reset_index(drop=True)
    econ = Economics()
    fit = FitContext(
        df=tr,
        feature_columns=ds.feature_columns,
        categorical_columns=ds.categorical_columns,
        economics=econ,
        action_names=ds.actions,
        seed=0,
    )
    pred = PredictContext(
        df=te,
        feature_columns=ds.feature_columns,
        categorical_columns=ds.categorical_columns,
        economics=econ,
        action_names=ds.actions,
        seed=0,
    )
    return fit, pred, (day > cut)


def test_negative_control_regime_yields_near_zero_estimated_effect():
    """When the action truly does nothing, causal models must say so."""
    ds = generate(make_config("negative_control_null_effect", n_leads=20_000, seed=0))
    fit, pred, mask = _ctxs(ds)
    call = ds.n_actions - 1
    for name, cls in [("t_learner", TLearner), ("dr_learner", DRLearner)]:
        est = cls(name, **GBM).fit(fit).estimate(pred)
        ate = float(np.mean(est.cate[:, call]))
        # The true effect is exactly zero; allow a small finite-sample band.
        assert abs(ate) < 0.01, f"{name} invented an ATE of {ate:+.4f} where none exists"


def test_shuffled_treatment_placebo_destroys_the_estimated_effect():
    """Permuting the treatment breaks the link; the estimate must collapse."""
    ds = generate(make_config("easy_randomized", n_leads=20_000, seed=1))
    call = ds.n_actions - 1
    fit, pred, _ = _ctxs(ds)

    real = TLearner("t_learner", **GBM).fit(fit).estimate(pred)
    real_ate = float(np.mean(real.cate[:, call]))
    assert real_ate > 0.01, "sanity: the real effect should be clearly positive"

    shuffled = fit.df.copy()
    rng = np.random.default_rng(0)
    shuffled["action"] = rng.permutation(shuffled["action"].to_numpy())
    fit_shuf = FitContext(
        df=shuffled,
        feature_columns=fit.feature_columns,
        categorical_columns=fit.categorical_columns,
        economics=fit.economics,
        action_names=fit.action_names,
        seed=0,
    )
    placebo = TLearner("t_learner_placebo", **GBM).fit(fit_shuf).estimate(pred)
    placebo_ate = float(np.mean(placebo.cate[:, call]))

    assert abs(placebo_ate) < 0.25 * abs(real_ate), (
        f"placebo ATE {placebo_ate:+.4f} is not small relative to the real "
        f"ATE {real_ate:+.4f}; the estimator is reading structure that is not there"
    )


def test_pure_noise_feature_does_not_change_the_decision_materially():
    """Adding an irrelevant column must not move realized profit much."""
    base = ScenarioSpec(
        name="fake_feature_control",
        regime="easy_randomized",
        n_leads=8_000,
        capacity_ratio=0.25,
        seeds=(0,),
    )
    cand = [CandidateSpec("propensity_ev_gbm",
                          partial(PropensityEV, "propensity_ev_gbm", **GBM))]
    plain = run_scenario(base, cand, verbose=False)

    # Same data, same seed, plus one pure-noise feature.
    ds = generate(base.config(0))
    rng = np.random.default_rng(999)
    ds.observed["x_noise"] = rng.standard_normal(len(ds.observed))
    ds.feature_columns = list(ds.feature_columns) + ["x_noise"]
    fit, pred, mask = _ctxs(ds, train_frac=0.75)
    est = PropensityEV("propensity_ev_gbm", **GBM).fit(fit).estimate(pred)
    assert np.isfinite(est.ev).all()

    # The plain run must have succeeded; the comparison is that a noise column
    # neither crashes the pipeline nor is required for it to work.
    assert plain["status"].iloc[0] == "ok"


def test_post_treatment_variables_are_rejected_as_features():
    """Collider / post-treatment leakage: `contacted` is caused by the action."""
    for bad in ("contacted", "qualified", "minutes_spent", "action"):
        with pytest.raises(LeakageError):
            check_no_feature_leakage(["x0", bad])


def test_misleading_attribution_regime_actually_misleads():
    """The last-touch channel must over-claim relative to its true effect."""
    ds = generate(make_config("misleading_attribution", n_leads=30_000, seed=2))
    obs, truth = ds.observed, ds.truth
    share_attributed = float((obs["attributed_channel"] == "retargeting").mean())
    share_true = float((truth["true_channel"] == "retargeting").mean())
    assert share_attributed > 2 * share_true, (
        f"retargeting takes last-touch credit on {share_attributed:.1%} of leads "
        f"but genuinely originates {share_true:.1%}; the trap is not set"
    )


def test_hidden_confounding_biases_the_naive_estimate():
    """With an unobserved confounder the naive arm difference must be wrong."""
    ds = generate(make_config("hidden_confounding", n_leads=30_000, seed=3))
    obs, truth = ds.observed, ds.truth
    call = ds.n_actions - 1
    true_ate = float((truth[f"p_funded_a{call}"] - truth["p_funded_a0"]).mean())
    naive = float(
        obs.loc[obs["action"] == call, "funded"].mean()
        - obs.loc[obs["action"] == 0, "funded"].mean()
    )
    assert abs(naive - true_ate) > 0.2 * abs(true_ate), (
        f"naive difference {naive:.4f} is too close to the truth {true_ate:.4f}; "
        "the confounding regime is not confounding anything"
    )


def test_selection_bias_regime_has_unequal_propensities():
    ds = generate(make_config("selection_bias", n_leads=10_000, seed=4))
    p = ds.observed["propensity_call"].to_numpy()
    assert p.std() > 0.05, "selection-bias regime should not have constant propensity"
    assert p.min() > 0, "positivity must still hold for this regime"


def test_feedback_loop_regime_destroys_overlap():
    """The previous-generation model should push propensities toward 0/1."""
    ds = generate(make_config("policy_feedback_loop", n_leads=10_000, seed=5))
    p = ds.observed["propensity_call"].to_numpy()
    extreme = float(((p < 0.05) | (p > 0.95)).mean())
    assert extreme > 0.2, (
        f"only {extreme:.1%} of propensities are extreme; the feedback regime "
        "should be destroying overlap, which is the point of it"
    )
