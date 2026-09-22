"""Regression tests for the aggregation layer (sections 32, 62).

Both bugs pinned here silently corrupted comparisons rather than crashing
loudly, which is the failure mode this benchmark exists to avoid. One of them
did crash, but only once a suite without a `status` column reached the report
builder — late enough that hours of compute were already spent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leadbench.evaluation.aggregate import leaderboard, ok_rows, paired_comparisons
from leadbench.evaluation.runner import CandidateSpec, dedupe_candidates


def _frame(candidates, seeds=(0, 1, 2, 3), value=1000.0, with_status=True):
    rows = []
    for cand, offset in candidates.items():
        for seed in seeds:
            row = dict(
                scenario="s1", regime="r1", capacity_ratio=0.25,
                seed=seed, candidate=cand,
                net_value_per_1k_leads=value + offset + seed,
            )
            if with_status:
                row["status"] = "ok"
            rows.append(row)
    return pd.DataFrame(rows)


def test_ok_rows_handles_a_frame_without_a_status_column():
    """`results.get("status", "ok") == "ok"` collapses to the scalar True when
    the column is absent, so `results[True]` raises KeyError. The online track
    records no failures and therefore has no status column at all."""
    d = _frame({"a": 0.0}, with_status=False)
    assert "status" not in d.columns
    assert len(ok_rows(d)) == len(d)


def test_ok_rows_filters_failures_when_the_column_is_present():
    d = _frame({"a": 0.0, "b": 10.0})
    d.loc[d.candidate == "b", "status"] = "failed"
    kept = ok_rows(d)
    assert set(kept.candidate) == {"a"}


def test_leaderboard_accepts_a_frame_without_a_status_column():
    d = _frame({"a": 0.0, "b": 50.0}, with_status=False)
    board = leaderboard(d)
    assert set(board.candidate) == {"a", "b"}


def test_duplicate_rows_do_not_corrupt_a_paired_comparison():
    """A candidate contributed by two registry groups is fitted twice and
    writes two identical rows per cell. `.loc[common]` on the duplicated index
    then returns more rows than the reference has: before the fix this raised
    `operands could not be broadcast together with shapes (8,) (4,)`, and with
    a partial overlap it would have silently paired the wrong seeds."""
    d = _frame({"ref": 0.0, "dup": 100.0})
    doubled = pd.concat([d, d[d.candidate == "dup"]], ignore_index=True)
    assert (doubled.groupby(["candidate", "seed"]).size() > 1).any()

    comp = paired_comparisons(doubled, "ref", n_boot=200)
    row = comp[comp.candidate == "dup"].iloc[0]
    assert row.n_seeds == 4
    # The duplicate is an exact copy, so the honest answer is the clean one.
    clean = paired_comparisons(d, "ref", n_boot=200)
    assert row.mean_diff == pytest.approx(
        clean[clean.candidate == "dup"].iloc[0].mean_diff
    )
    assert row.mean_diff == pytest.approx(100.0)


def test_dedupe_candidates_keeps_the_first_registration():
    specs = [
        CandidateSpec(name="a", factory=lambda: None, tags=("economic",)),
        CandidateSpec(name="b", factory=lambda: None, tags=("causal",)),
        CandidateSpec(name="a", factory=lambda: None, tags=("bayesian",)),
    ]
    out = dedupe_candidates(specs)
    assert [c.name for c in out] == ["a", "b"]
    assert out[0].tags == ("economic",)


def test_dedupe_candidates_is_a_no_op_on_distinct_names():
    specs = [
        CandidateSpec(name=n, factory=lambda: None) for n in ("a", "b", "c")
    ]
    assert len(dedupe_candidates(specs)) == 3


def test_paired_comparison_pairs_by_seed_not_by_position():
    """The whole point of pairing is that both candidates saw the identical
    population. Shuffling one side's row order must not change the answer."""
    d = _frame({"ref": 0.0, "cand": 250.0})
    shuffled = pd.concat(
        [d[d.candidate == "ref"],
         d[d.candidate == "cand"].iloc[::-1]],
        ignore_index=True,
    )
    a = paired_comparisons(d, "ref", n_boot=200)
    b = paired_comparisons(shuffled, "ref", n_boot=200)
    assert a[a.candidate == "cand"].iloc[0].mean_diff == pytest.approx(
        b[b.candidate == "cand"].iloc[0].mean_diff
    )
    assert np.isfinite(a[a.candidate == "cand"].iloc[0].ci_low)
