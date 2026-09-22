"""Leakage, split hygiene, determinism and metric correctness."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leadbench.evaluation.runner import ScenarioSpec, run_scenario
from leadbench.evaluation.splits import (
    FORBIDDEN_FEATURES,
    LeakageError,
    audit_split,
    check_no_feature_leakage,
    drop_cross_split_duplicates,
    rolling_backtest,
    temporal_split,
)
from leadbench.metrics.causal import pehe, qini_auc, uplift_at_k
from leadbench.metrics.economic import regret, regret_ratio
from leadbench.metrics.ope import effective_sample_size, ips, snips, support_diagnostics
from leadbench.metrics.predictive import expected_calibration_error, predictive_summary
from leadbench.metrics.uncertainty import interval_coverage, uncertainty_summary
from leadbench.synthetic.config import make_config
from leadbench.synthetic.dgp import generate


# --- leakage ---------------------------------------------------------------


@pytest.mark.parametrize("bad", sorted(FORBIDDEN_FEATURES))
def test_outcome_and_post_treatment_columns_are_rejected(bad):
    with pytest.raises(LeakageError):
        check_no_feature_leakage(["x0", "x1", bad])


def test_declared_feature_list_is_clean():
    ds = generate(make_config("easy_randomized", n_leads=500, seed=0))
    check_no_feature_leakage(ds.feature_columns)


def test_temporal_split_has_no_future_in_training():
    ds = generate(make_config("seasonality_trend", n_leads=5000, seed=0))
    split = temporal_split(ds)
    assert split.train.observed["created_day"].max() < split.test.observed["created_day"].min()
    audit_split(split, ds.feature_columns)


def test_split_audit_catches_duplicate_entities():
    ds = generate(make_config("noisy_crm", n_leads=6000, seed=0))
    split = temporal_split(ds)
    # Force an overlap by putting a training person into the test fold.
    test_obs = split.test.observed.copy()
    test_obs.loc[test_obs.index[0], "person_id"] = split.train.observed["person_id"].iloc[0]
    split.test.observed = test_obs
    with pytest.raises(LeakageError):
        audit_split(split, ds.feature_columns)


def test_dropping_cross_split_duplicates_makes_the_audit_pass():
    ds = generate(make_config("noisy_crm", n_leads=8000, seed=2))
    split = drop_cross_split_duplicates(temporal_split(ds))
    report = audit_split(split, ds.feature_columns)
    assert report["entity_overlap"] == 0
    assert report["lead_id_overlap"] == 0


def test_rolling_backtest_folds_move_forward():
    ds = generate(make_config("concept_drift", n_leads=12000, seed=0))
    folds = rolling_backtest(ds, n_folds=3)
    assert len(folds) >= 2
    for f in folds:
        assert f.train.observed["created_day"].max() <= f.test.observed["created_day"].min()
    starts = [f.test.observed["created_day"].min() for f in folds]
    assert starts == sorted(starts)


# --- determinism -----------------------------------------------------------


def test_generation_is_deterministic_for_a_seed():
    a = generate(make_config("sparse", n_leads=3000, seed=42))
    b = generate(make_config("sparse", n_leads=3000, seed=42))
    pd.testing.assert_frame_equal(a.observed, b.observed)
    pd.testing.assert_frame_equal(a.truth, b.truth)


def test_different_seeds_give_different_data():
    a = generate(make_config("sparse", n_leads=2000, seed=1))
    b = generate(make_config("sparse", n_leads=2000, seed=2))
    assert not a.observed["funded"].equals(b.observed["funded"])


def test_benchmark_run_is_reproducible():
    from leadbench.models.registry import get_tier

    spec = ScenarioSpec(
        name="determinism", regime="easy_randomized", n_leads=3000,
        capacity_ratio=0.25, seeds=(0,),
    )
    a = run_scenario(spec, get_tier("smoke"), verbose=False)
    b = run_scenario(spec, get_tier("smoke"), verbose=False)
    key = ["candidate", "net_value_per_1k_leads", "share_treated"]
    pd.testing.assert_frame_equal(
        a[key].reset_index(drop=True), b[key].reset_index(drop=True)
    )


# --- metrics ---------------------------------------------------------------


def test_regret_and_regret_ratio():
    assert regret(100.0, 60.0) == pytest.approx(40.0)
    assert regret_ratio(100.0, 60.0, 20.0) == pytest.approx(0.5)
    assert regret_ratio(100.0, 100.0, 20.0) == pytest.approx(0.0)
    assert regret_ratio(100.0, 20.0, 20.0) == pytest.approx(1.0)
    assert np.isnan(regret_ratio(100.0, 60.0, 100.0))


def test_perfect_predictions_score_perfectly():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 4000)
    y = (rng.random(4000) < p).astype(float)
    s = predictive_summary(y, p)
    assert s["auroc"] > 0.75
    assert s["ece"] < 0.05
    assert s["calibration_slope"] == pytest.approx(1.0, abs=0.25)


def test_miscalibrated_predictions_are_penalised():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 4000)
    y = (rng.random(4000) < p).astype(float)
    good = expected_calibration_error(y, p)
    bad = expected_calibration_error(y, np.clip(p * 2.5, 0, 1))
    assert bad > good * 3


def test_pehe_is_zero_for_a_perfect_cate_estimate():
    t = np.linspace(-0.2, 0.2, 500)
    assert pehe(t, t) == pytest.approx(0.0)
    assert pehe(t, t + 0.1) == pytest.approx(0.1, rel=1e-6)


def test_qini_rewards_a_real_uplift_ranking():
    rng = np.random.default_rng(0)
    n = 20_000
    u = rng.random(n)  # true uplift, higher is better
    t = rng.integers(0, 2, n)
    p = 0.1 + 0.4 * u * t
    y = (rng.random(n) < p).astype(float)
    good = qini_auc(y, t, u)
    bad = qini_auc(y, t, rng.random(n))
    assert good > bad
    assert uplift_at_k(y, t, u, 0.2) > uplift_at_k(y, t, rng.random(n), 0.2)


def test_interval_coverage_is_measured_correctly():
    truth = np.zeros(1000)
    assert interval_coverage(truth, np.full(1000, -1.0), np.full(1000, 1.0)) == 1.0
    assert interval_coverage(truth, np.full(1000, 0.5), np.full(1000, 1.0)) == 0.0
    rng = np.random.default_rng(0)
    samples = rng.normal(0, 1, (2000, 1000))
    s = uncertainty_summary(truth, samples, nominal=0.80)
    assert s["coverage_80"] == pytest.approx(1.0, abs=0.02)


def test_ips_is_unbiased_under_known_randomization():
    rng = np.random.default_rng(0)
    n = 200_000
    p = 0.5
    logged = (rng.random(n) < p).astype(int)
    reward_if_treated = rng.normal(2.0, 1.0, n)
    reward_if_control = rng.normal(1.0, 1.0, n)
    reward = np.where(logged == 1, reward_if_treated, reward_if_control)
    target = np.ones(n, dtype=int)  # treat everyone
    est = ips(reward, logged, target, np.full(n, p), n_boot=100)
    assert est.value == pytest.approx(2.0, abs=0.05)
    assert est.ci_low < 2.0 < est.ci_high
    est2 = snips(reward, logged, target, np.full(n, p), n_boot=100)
    assert est2.value == pytest.approx(2.0, abs=0.05)


def test_effective_sample_size_falls_with_extreme_weights():
    balanced = np.ones(1000)
    skewed = np.concatenate([np.full(999, 0.001), [1000.0]])
    assert effective_sample_size(balanced) == pytest.approx(1000.0)
    assert effective_sample_size(skewed) < 10


def test_support_diagnostics_flag_positivity_violations():
    n = 1000
    pmat = np.column_stack([np.full(n, 0.999), np.full(n, 0.001)])
    diag = support_diagnostics(pmat, np.ones(n, dtype=int), min_propensity=0.01)
    assert diag["violation_rate"] == 1.0
    diag2 = support_diagnostics(pmat, np.zeros(n, dtype=int), min_propensity=0.01)
    assert diag2["violation_rate"] == 0.0
