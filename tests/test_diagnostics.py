"""The adversarial checks must fire on data that is genuinely broken."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leadbench.evaluation.diagnostics import (
    duplicate_entity_check,
    positivity_check,
    run_all,
    simpson_check,
    target_leakage_check,
)
from leadbench.synthetic.config import make_config
from leadbench.synthetic.dgp import generate


def _sev(findings, check):
    return next(f.severity for f in findings if f.check == check)


def test_simpson_paradox_is_detected_when_constructed():
    """Treatment helps in every segment but looks harmful in aggregate."""
    rows = []
    # The confounding has to run *against* the treatment for the paradox to
    # appear: the HIGH-baseline segment is mostly control and the LOW-baseline
    # segment is mostly treated. Treatment then adds +5pp inside each segment
    # while the pooled comparison shows it doing harm.
    for seg, base, n_t, n_c in [("A", 0.60, 100, 900), ("B", 0.10, 900, 100)]:
        for _ in range(n_t):
            rows.append({"campaign_id": seg, "action": 1, "funded": 0.0})
        for _ in range(n_c):
            rows.append({"campaign_id": seg, "action": 0, "funded": 0.0})
    df = pd.DataFrame(rows)
    rng = np.random.default_rng(0)
    base = df["campaign_id"].map({"A": 0.60, "B": 0.10})
    # Treatment adds a uniform +5pp inside every segment.
    p = base + 0.05 * df["action"]
    df["funded"] = (rng.random(len(df)) < p).astype(float)

    out = simpson_check(df, "action", "funded", "campaign_id", min_cell=30)
    f = out[0]
    assert f.severity == "fail", f"expected a sign reversal, got: {f}"
    assert f.detail["marginal_diff"] * f.detail["within_segment_weighted_diff"] < 0


def test_no_paradox_flagged_on_clean_randomized_data():
    ds = generate(make_config("easy_randomized", n_leads=30_000, seed=1))
    out = simpson_check(ds.observed, "action", "funded", "campaign_id")
    assert out[0].severity in ("info", "warn")
    assert out[0].severity != "fail"


def test_target_leakage_is_caught():
    rng = np.random.default_rng(0)
    n = 2000
    y = (rng.random(n) < 0.3).astype(float)
    df = pd.DataFrame({
        "funded": y,
        "x_ok": rng.standard_normal(n),
        "x_leak": y + 0.01 * rng.standard_normal(n),  # basically the outcome
    })
    out = target_leakage_check(df, ["x_ok", "x_leak"], "funded")
    fails = [f for f in out if f.severity == "fail"]
    assert len(fails) == 1
    assert fails[0].detail["column"] == "x_leak"


def test_clean_features_are_not_flagged_as_leakage():
    ds = generate(make_config("easy_randomized", n_leads=8000, seed=0))
    out = target_leakage_check(ds.observed, ds.feature_columns, "funded")
    assert all(f.severity != "fail" for f in out)


def test_positivity_failure_in_the_feedback_regime():
    ds = generate(make_config("policy_feedback_loop", n_leads=20_000, seed=0))
    out = positivity_check(ds.observed, min_propensity=0.05)
    assert out[0].severity in ("warn", "fail")


def test_positivity_passes_under_randomized_logging():
    ds = generate(make_config("easy_randomized", n_leads=8000, seed=0))
    out = positivity_check(ds.observed, min_propensity=0.01)
    assert out[0].severity == "info"


def test_missing_propensities_are_flagged_as_a_warning():
    df = pd.DataFrame({"action": [0, 1], "funded": [0.0, 1.0]})
    out = positivity_check(df)
    assert out[0].severity == "warn"
    assert "not identified" in out[0].message


def test_duplicate_entities_are_reported():
    ds = generate(make_config("noisy_crm", n_leads=6000, seed=0))
    out = duplicate_entity_check(ds.observed)
    assert out[0].severity == "warn"
    assert out[0].detail["duplicate_share"] > 0.0


def test_run_all_sorts_worst_first_and_covers_every_check():
    ds = generate(make_config("policy_feedback_loop", n_leads=8000, seed=0))
    out = run_all(ds.observed, ds.feature_columns)
    checks = {f.check for f in out}
    assert checks == {
        "simpson", "target_leakage", "future_information",
        "positivity", "duplicate_entity",
    }
    order = {"fail": 0, "warn": 1, "info": 2}
    sev = [order[f.severity] for f in out]
    assert sev == sorted(sev)


def test_future_dated_column_only_fails_when_used_as_a_feature():
    from leadbench.evaluation.diagnostics import future_information_check

    ds = generate(make_config("easy_randomized", n_leads=3000, seed=0))
    clean = future_information_check(ds.observed, ds.feature_columns)
    assert clean[0].severity == "info", "a resolution timestamp that is merely present is fine"
    assert "resolution_day" in clean[0].detail["future_dated_columns"]

    leaky = future_information_check(
        ds.observed, list(ds.feature_columns) + ["resolution_day"]
    )
    assert any(f.severity == "fail" for f in leaky)
