"""The common-random-numbers gate.

These exist because F16 -- the claim that the per-truth samples were
independent, in a design whose seed comment says otherwise -- survived a
whole milestone as prose. The assumption now has an executable home, and
these tests are what make the home load-bearing.

The case each one is built around is the M8 pilot: nine new truths at 10
iterations beside seven existing truths at 25. Analysed as-is, `q(theta)`
would be estimated from 25 latent panels on some rows and 10 on others, and
the interpolation error the boundary test is trying to measure would be
mixed with a difference in Monte Carlo samples.
"""

from __future__ import annotations

import pandas as pd
import pytest

from leadbench_mx.clusters import (
    audit_clusters, require_complete_clusters,
)

THETAS = [0.0, 0.05, 0.15]


def frame(rows) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["tool_label", "scenario", "iteration", "effect_pct"])


def full(tools=("a", "b"), scenarios=("A1",), iterations=(1, 2),
         thetas=THETAS) -> pd.DataFrame:
    return frame([(t, s, i, th) for t in tools for s in scenarios
                  for i in iterations for th in thetas])


def test_a_complete_design_passes_untouched():
    d = full()
    out = require_complete_clusters(d, THETAS, expect_iterations=[1, 2])
    assert len(out) == len(d)


def test_the_pilot_trap_is_refused():
    """THE case this module exists for: old truths carry 25 iterations, new
    truths carry 10. The intersection is 10, so silently dropping would
    'work' -- and would estimate different rows of one transition matrix
    from different numbers of latent panels."""
    rows = []
    for t in ("a",):
        for i in range(1, 26):                    # old truths: 25 iterations
            rows += [(t, "A1", i, 0.0), (t, "A1", i, 0.05)]
        for i in range(1, 11):                    # new truth: 10 iterations
            rows.append((t, "A1", i, 0.15))
    d = frame(rows)
    # The intersection IS 1..10, so the pilot's own expectation passes:
    out = require_complete_clusters(d, THETAS, expect_iterations=range(1, 11))
    assert out.groupby(["tool_label", "effect_pct"]).size().nunique() == 1
    assert len(out) == 30
    # ...and asserting the full 25 correctly fails.
    with pytest.raises(SystemExit, match="reopens F16"):
        require_complete_clusters(d, THETAS, expect_iterations=range(1, 26))


def test_rows_per_theta_are_equal_after_gating():
    """The observable consequence of a correct gate: every truth ends up
    resting on exactly the same set of latent panels."""
    rows = [("a", "A1", i, th) for i in range(1, 8) for th in THETAS]
    rows += [("a", "A1", 8, 0.0), ("a", "A1", 8, 0.05)]      # partial cluster
    out = require_complete_clusters(frame(rows), THETAS)
    counts = out.groupby("effect_pct").size()
    assert counts.nunique() == 1 and counts.iloc[0] == 7


def test_a_cluster_complete_for_one_tool_only_is_not_shared():
    """Tools must rest on the SAME panels or a cross-tool comparison is
    confounded by which panels each one happened to see."""
    rows = [("a", "A1", i, th) for i in (1, 2) for th in THETAS]
    rows += [("b", "A1", 1, th) for th in THETAS]
    rows += [("b", "A1", 2, 0.0)]                 # tool b misses two truths
    rep = audit_clusters(frame(rows), THETAS)
    assert rep.complete["a"] == {("A1", 1), ("A1", 2)}
    assert rep.complete["b"] == {("A1", 1)}
    assert rep.shared == {("A1", 1)}
    out = require_complete_clusters(frame(rows), THETAS)
    assert set(out.iteration) == {1}


def test_a_duplicate_is_refused_not_deduplicated():
    """A duplicate is a doubled weight on one latent panel. Silently taking
    the first row would hide it; D13 is what that costs."""
    d = pd.concat([full(tools=("a",)), full(tools=("a",)).head(1)])
    with pytest.raises(SystemExit, match="doubled weight"):
        require_complete_clusters(d, THETAS)


def test_no_shared_cluster_refuses_rather_than_returning_empty():
    rows = [("a", "A1", 1, th) for th in THETAS]
    rows += [("b", "A1", 2, th) for th in THETAS]
    with pytest.raises(SystemExit, match="no cluster is complete"):
        require_complete_clusters(frame(rows), THETAS)


def test_per_scenario_expectation_is_checked_per_scenario():
    """A2 quietly running 5 iterations while A1 runs 10 must fail: pooling
    them would weight A1's panels twice as heavily as A2's."""
    rows = [("a", "A1", i, th) for i in range(1, 11) for th in THETAS]
    rows += [("a", "A2", i, th) for i in range(1, 6) for th in THETAS]
    with pytest.raises(SystemExit, match="scenario A2"):
        require_complete_clusters(frame(rows), THETAS,
                                  expect_iterations=range(1, 11))


def test_the_gate_is_indifferent_to_theta_ordering_and_float_noise():
    """Truths arrive as floats from JSON. A gate that missed 0.15 because it
    was stored as 0.15000000000000002 would drop every cluster and blame the
    data."""
    rows = [("a", "A1", i, th) for i in (1, 2)
            for th in (0.15000000000000002, 0.0, 0.05)]
    out = require_complete_clusters(frame(rows), [0.05, 0.15, 0.0])
    assert len(out) == 6
