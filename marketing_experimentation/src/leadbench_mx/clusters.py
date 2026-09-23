"""The common-random-numbers cluster, and the gate that refuses without it.

Why this is a module and not three lines in a script
-----------------------------------------------------
The donor generates every effect size inside one `(scenario, iteration)` from
a single panel seed -- `src/R/generate_panels.R:375` has no effect-size term,
and its own comment says *"same seed for null and effect"*. The estimator
randomness is shared too, where there is any: `run_tools.py:173` passes
`--seed iteration` to CausalImpact and `run_causalpy.py:100` sets
`random_seed = iteration`; GeoLift and Google MM take no seed at all and are
deterministic given the panel.

So the independent unit of this experiment is the **cluster**::

    (scenario, iteration)  ->  one latent panel  ->  one row per theta

Mistaking that for `n_theta` independent samples is F16, and it survived in a
docstring for a whole milestone. This module exists so the assumption has a
single executable home rather than being restated in prose per script.

The trap this gate is built for
--------------------------------
The M8 pilot adds nine new truths at 10 iterations while seven existing
truths already have 25. Analysing that as-is would estimate `q(theta)` for
old truths from 25 noise realisations and for new ones from 10 -- different
latent panels per row of the same transition matrix. The interpolation error
the boundary test is trying to measure would then be mixed with a difference
in Monte Carlo samples, and F16 would reopen under a new name.

Hence: analysis runs on the **complete intersection** of clusters, or it
refuses to run. Iterations 11-25 of the old truths are not lost; they are
simply not entitled to participate until the new truths reach 25.

Verified, not assumed, that the cluster is `(scenario, iteration)` and not
`iteration` alone: the estimator seed is the bare iteration index, so it
repeats across scenarios. If that induced dependence, residuals for the same
iteration in different scenarios would correlate. Measured on the M7 atlas:
mean cross-scenario r is +0.012 (causalimpact) and +0.026 (causalpy), against
-0.031 (geolift) and -0.045 (google_mm) which take **no** estimator seed at
all. The seeded tools look exactly like the unseeded controls, so the shared
seed does not link scenarios and the cluster is the pair.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: Columns that together name one latent panel.
CLUSTER_KEYS = ("scenario", "iteration")


@dataclass(frozen=True)
class ClusterReport:
    """What the data actually contains, before anyone computes on it."""

    thetas: tuple[float, ...]
    complete: dict[str, set] = field(default_factory=dict)
    incomplete: dict[str, dict] = field(default_factory=dict)
    duplicated: dict[str, list] = field(default_factory=dict)

    @property
    def shared(self) -> set:
        """Clusters complete for EVERY tool. The only ones fit to compare."""
        if not self.complete:
            return set()
        it = iter(self.complete.values())
        out = set(next(it))
        for s in it:
            out &= s
        return out

    def summary(self) -> str:
        lines = [f"clusters, over {len(self.thetas)} truths:"]
        for tool in sorted(self.complete):
            n_inc = len(self.incomplete.get(tool, {}))
            n_dup = len(self.duplicated.get(tool, []))
            lines.append(
                f"   {tool:18s} {len(self.complete[tool]):4d} complete"
                f"   {n_inc:3d} incomplete   {n_dup:3d} duplicated")
        lines.append(f"   shared across all tools: {len(self.shared)}")
        return "\n".join(lines)


def audit_clusters(d: pd.DataFrame, thetas, tool_col: str = "tool_label",
                   theta_col: str = "effect_pct") -> ClusterReport:
    """Describe cluster completeness without judging it.

    A cluster is complete for a tool when it carries **exactly one** row at
    every truth. Two rows at one truth is as disqualifying as none: a
    duplicate is a doubled weight on one panel (D13), and a gap is a panel
    that contributes to some truths and not others.
    """
    thetas = tuple(float(t) for t in thetas)
    rep = ClusterReport(thetas=thetas, complete={}, incomplete={},
                        duplicated={})
    for tool, g in d.groupby(tool_col):
        complete, incomplete, dup = set(), {}, []
        for key, sub in g.groupby(list(CLUSTER_KEYS)):
            counts = {t: int(np.isclose(sub[theta_col], t, atol=1e-9).sum())
                      for t in thetas}
            missing = [t for t, c in counts.items() if c == 0]
            extra = [t for t, c in counts.items() if c > 1]
            if extra:
                dup.append((key, extra))
            if missing:
                incomplete[key] = missing
            elif not extra:
                complete.add(key)
        rep.complete[tool] = complete
        rep.incomplete[tool] = incomplete
        rep.duplicated[tool] = dup
    return rep


def require_complete_clusters(
    d: pd.DataFrame, thetas, expect_iterations=None,
    tool_col: str = "tool_label", theta_col: str = "effect_pct",
) -> pd.DataFrame:
    """Return only rows in clusters complete for every tool, or refuse.

    ``expect_iterations`` preregisters the answer. Pass ``range(1, 11)`` for
    the M8 pilot and the gate fails loudly if the intersection is anything
    else -- including the case that matters, where old truths quietly bring
    iterations 11-25 along and new ones do not.

    Refusing is the point. A gate that silently drops the incomplete clusters
    would let a half-populated pilot produce a plausible-looking number, and
    the whole reason this exists is that plausible-looking numbers are how
    the last four failures got published.
    """
    rep = audit_clusters(d, thetas, tool_col, theta_col)

    bad = {t: v for t, v in rep.duplicated.items() if v}
    if bad:
        raise SystemExit(
            f"duplicated rows inside clusters: {bad}\n"
            f"A duplicate is a doubled weight on one latent panel -- see D13.")

    shared = rep.shared
    if not shared:
        raise SystemExit(
            f"no cluster is complete across all tools.\n{rep.summary()}\n"
            f"Nothing here can be analysed as a common-random-numbers design.")

    if expect_iterations is not None:
        want = set(int(i) for i in expect_iterations)
        for scen in sorted({k[0] for k in shared}):
            got = {int(k[1]) for k in shared if k[0] == scen}
            if got != want:
                raise SystemExit(
                    f"scenario {scen}: complete clusters are iterations "
                    f"{sorted(got)},\nexpected {sorted(want)}.\n"
                    f"Mixing iteration counts across truths estimates "
                    f"q(theta) from different\nlatent panels per row. That "
                    f"reopens F16 under a new name -- refusing.\n"
                    f"{rep.summary()}")

    keep = d.set_index(list(CLUSTER_KEYS)).index.isin(shared)
    out = d[keep]
    per_tool = out.groupby([tool_col, theta_col]).size()
    if per_tool.nunique() != 1:
        raise SystemExit(
            f"after gating, rows per (tool, theta) are not constant:\n"
            f"{per_tool.describe()}\nThe gate is wrong, not the data.")
    return out
