#!/usr/bin/env python
"""Benchmark entrypoint.

    python scripts/run_benchmark.py --suite smoke        # minutes, CI-sized
    python scripts/run_benchmark.py --suite lead         # the main lead track
    python scripts/run_benchmark.py --suite all          # everything

Each suite writes a CSV into ``reports/runs/<suite>/`` plus a frozen
experiment manifest. The manifest is written *before* any test metric is
computed; see ``src/leadbench/evaluation/prereg.py``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from leadbench.economics import Economics  # noqa: E402
from leadbench.evaluation.prereg import ExperimentManifest, KillCriteria  # noqa: E402
from leadbench.evaluation.runner import ScenarioSpec, run_scenario  # noqa: E402
from leadbench.models.registry import get_tier  # noqa: E402

OUT_ROOT = Path("reports/runs")

# --- the preregistered experiment matrix ----------------------------------

#: Regimes for the headline lead-track sweep.
CORE_REGIMES = [
    "easy_randomized",
    "propensity_not_uplift",
    "sparse",
    "rare_outcome",
    "very_rare_outcome",
    "strong_heterogeneity",
    "agent_time_heterogeneity",
    "campaign_effort_heterogeneity",
    "value_heterogeneity",
    "capacity_value_heterogeneity",
    "observed_confounding",
    "hidden_confounding",
    "selection_bias",
    "policy_feedback_loop",
    "noisy_crm",
    "misleading_attribution",
    "concept_drift",
    "delayed_censored",
    "seasonality_trend",
    "negative_control_null_effect",
]

#: Regimes where the product hypothesis should look best, used for the curves.
FOCUS_REGIMES = ["propensity_not_uplift", "capacity_value_heterogeneity", "sparse"]

DEFAULT_SEEDS = (0, 1, 2, 3, 4, 5, 6, 7)
DEFAULT_N = 40_000
DEFAULT_CAPACITY = 0.25


def _manifest(suite: str, description: str, scenarios: list[dict]) -> ExperimentManifest:
    return ExperimentManifest(
        experiment_id=f"{suite}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}",
        description=description,
        scenarios=scenarios,
        economics=Economics().__dict__,
        constraints={"capacity_ratio_default": DEFAULT_CAPACITY},
        kill_criteria=KillCriteria(),
        seeds=DEFAULT_SEEDS,
    ).freeze()


#: Set by --out-name so a focused re-run cannot overwrite a full sweep's CSV.
OUT_NAME_OVERRIDE: str | None = None


def _write(df: pd.DataFrame, suite: str, name: str, manifest: ExperimentManifest) -> Path:
    out = OUT_ROOT / (OUT_NAME_OVERRIDE or suite)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.csv"
    df.to_csv(path, index=False)
    manifest.write(out / "experiment-manifest.json")
    print(f"[{suite}] wrote {path} ({len(df)} rows)")
    return path


# --- suites ----------------------------------------------------------------


def suite_smoke(args) -> None:
    specs = [
        ScenarioSpec(
            name=f"smoke_{r}",
            regime=r,
            n_leads=6_000,
            capacity_ratio=DEFAULT_CAPACITY,
            seeds=(0, 1),
        )
        for r in ["easy_randomized", "propensity_not_uplift"]
    ]
    man = _manifest("smoke", "CI smoke suite: end-to-end on two regimes", [s.name for s in specs])
    frames = [run_scenario(s, get_tier("smoke")) for s in specs]
    _write(pd.concat(frames, ignore_index=True), "smoke", "results", man)


def suite_lead(args) -> None:
    regimes = args.regimes or CORE_REGIMES
    specs = [
        ScenarioSpec(
            name=f"lead_{r}",
            regime=r,
            n_leads=args.n_leads,
            capacity_ratio=DEFAULT_CAPACITY,
            seeds=tuple(range(args.seeds)),
        )
        for r in regimes
    ]
    man = _manifest(
        "lead",
        "Main lead-track sweep: every candidate family across all regimes at a "
        "25% agent-capacity constraint.",
        [s.name for s in specs],
    )
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_scenario(s, get_tier("core")))
        _write(pd.concat(frames, ignore_index=True), "lead", "results", man)


def suite_curves(args) -> None:
    """Data-size, capacity and rare-outcome curves (sections 33-35)."""
    from leadbench.models.registry import (
        _spec,
        GBM_KW,
    )
    from functools import partial
    from leadbench.models.naive import (
        HistoricalProfitPerAgentHourPolicy,
        Oracle,
        RandomPolicy,
    )
    from leadbench.models.propensity import LeadScoreModel, PropensityEV
    from leadbench.models.uplift import DRLearner, TLearner

    cands = [
        _spec("oracle", Oracle, "oracle"),
        _spec("random", RandomPolicy, "naive"),
        _spec("hist_profit_per_agent_hour", HistoricalProfitPerAgentHourPolicy, "analytics"),
        _spec("lead_score_gbm", partial(LeadScoreModel, "lead_score_gbm", kind="xgboost", **GBM_KW), "propensity"),
        _spec("propensity_ev_gbm", partial(PropensityEV, "propensity_ev_gbm", kind="xgboost", **GBM_KW), "economic"),
        _spec("t_learner", partial(TLearner, "t_learner", kind="xgboost", **GBM_KW), "causal"),
        _spec("dr_learner", partial(DRLearner, "dr_learner", kind="xgboost", **GBM_KW), "causal"),
    ]

    specs: list[ScenarioSpec] = []
    for r in FOCUS_REGIMES:
        for n in (2_000, 5_000, 10_000, 25_000, 50_000, 100_000):
            specs.append(
                ScenarioSpec(
                    name=f"size_{r}_n{n}",
                    regime=r,
                    n_leads=n,
                    capacity_ratio=DEFAULT_CAPACITY,
                    seeds=tuple(range(args.seeds)),
                )
            )
    for r in ["capacity_value_heterogeneity", "propensity_not_uplift"]:
        for cap in (0.05, 0.10, 0.25, 0.50, 1.00):
            specs.append(
                ScenarioSpec(
                    name=f"capacity_{r}_c{cap}",
                    regime=r,
                    n_leads=args.n_leads,
                    capacity_ratio=cap,
                    seeds=tuple(range(args.seeds)),
                )
            )
    man = _manifest("curves", "Data-size, capacity and rare-outcome curves", [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_scenario(s, cands))
        _write(pd.concat(frames, ignore_index=True), "curves", "results", man)


def suite_ablation(args) -> None:
    specs = [
        ScenarioSpec(
            name=f"abl_{r}",
            regime=r,
            n_leads=args.n_leads,
            capacity_ratio=DEFAULT_CAPACITY,
            seeds=tuple(range(args.seeds)),
        )
        for r in FOCUS_REGIMES + ["agent_time_heterogeneity", "value_heterogeneity"]
    ]
    man = _manifest("ablation", "Where does the advantage come from? (section 37)", [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_scenario(s, get_tier("ablation")))
        _write(pd.concat(frames, ignore_index=True), "ablation", "results", man)


def suite_bayes(args) -> None:
    """Uncertainty candidates. Slower, so fewer regimes and smaller N."""
    from leadbench.models.registry import (
        bayes_ablation_candidates,
        risk_policy_variants,
        uncertainty_candidates,
        _spec,
        GBM_KW,
    )
    from functools import partial
    from leadbench.models.naive import HistoricalProfitPerAgentHourPolicy, Oracle
    from leadbench.models.propensity import PropensityEV
    from leadbench.models.uplift import TLearner

    cands = (
        [
            _spec("oracle", Oracle, "oracle"),
            _spec("hist_profit_per_agent_hour", HistoricalProfitPerAgentHourPolicy, "analytics"),
            _spec("propensity_ev_gbm", partial(PropensityEV, "propensity_ev_gbm", kind="xgboost", **GBM_KW), "economic"),
            _spec("t_learner", partial(TLearner, "t_learner", kind="xgboost", **GBM_KW), "causal"),
        ]
        + uncertainty_candidates()
        + bayes_ablation_candidates()
        + risk_policy_variants()
    )
    sizes = tuple(int(x) for x in str(args.bayes_sizes).split(","))
    specs = []
    for r in args.regimes or [
        "sparse", "propensity_not_uplift", "very_rare_outcome", "hidden_confounding"
    ]:
        for n in sizes:
            specs.append(
                ScenarioSpec(
                    name=f"bayes_{r}_n{n}",
                    regime=r,
                    n_leads=n,
                    capacity_ratio=DEFAULT_CAPACITY,
                    seeds=tuple(range(min(args.seeds, 4))),
                )
            )
    man = _manifest("bayes", "Bayesian / uncertainty candidates (RQ5, RQ6)", [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_scenario(s, cands))
        _write(pd.concat(frames, ignore_index=True), "bayes", "results", man)


def suite_pooling(args) -> None:
    """RQ5-followup: partial pooling without MCMC, and value-model shrinkage.

    Both questions the completed study left open, in one suite. Run at the
    same n and on the same regimes as `--suite bayes` so the pooling results
    are directly comparable with `bayes_hierarchical`, plus the two
    value-heterogeneity regimes where shrinking the margin unexpectedly helped.
    """
    from leadbench.models.registry import (
        oracle_candidate,
        pooling_candidates,
        value_shrinkage_candidates,
        _spec,
    )
    from functools import partial
    from leadbench.models.naive import HistoricalProfitPerAgentHourPolicy

    cands = (
        oracle_candidate()
        + [_spec("hist_profit_per_agent_hour", HistoricalProfitPerAgentHourPolicy,
                 "analytics")]
        + pooling_candidates()
        + value_shrinkage_candidates()
    )
    sizes = tuple(int(x) for x in str(args.bayes_sizes).split(","))
    regimes = args.regimes or [
        # The four the bayes suite used, so pooling is comparable like-for-like.
        "sparse", "propensity_not_uplift", "very_rare_outcome", "hidden_confounding",
        # Plus the two where the value-model ablation produced its surprise.
        "capacity_value_heterogeneity", "value_heterogeneity",
    ]
    specs = [
        ScenarioSpec(
            name=f"pool_{r}_n{n}",
            regime=r,
            n_leads=n,
            capacity_ratio=DEFAULT_CAPACITY,
            seeds=tuple(range(min(args.seeds, 6))),
        )
        for r in regimes
        for n in sizes
    ]
    man = _manifest("pooling",
                    "Cheap partial pooling and value-model shrinkage (RQ5 follow-up)",
                    [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_scenario(s, cands))
        _write(pd.concat(frames, ignore_index=True), "pooling", "results", man)


def suite_online(args) -> None:
    from leadbench.evaluation.online import OnlineSpec, run_online_scenario

    regimes = args.regimes or [
        "easy_randomized",
        "concept_drift",
        "propensity_not_uplift",
        "policy_feedback_loop",
        "sparse",
    ]
    specs = [
        OnlineSpec(
            name=f"online_{r}",
            regime=r,
            n_leads=args.n_leads,
            capacity_ratio=DEFAULT_CAPACITY,
            seeds=tuple(range(min(args.seeds, 5))),
            n_periods=args.online_periods,
        )
        for r in regimes
    ]
    man = _manifest("online", "Bandits vs frozen vs retrained offline models (RQ7)", [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_online_scenario(s))
        _write(pd.concat(frames, ignore_index=True), "online", "results", man)


def suite_real(args) -> None:
    from leadbench.data.real import load_criteo, load_hillstrom, verify
    from leadbench.evaluation.real_track import RealSpec, run_real_scenario

    frames = []
    scen = []
    hashes = {}
    for arms in ("any_email", "mens", "womens"):
        for outcome in ("visit", "conversion"):
            ds = load_hillstrom(arms=arms, outcome=outcome)
            spec = RealSpec(
                name=f"hillstrom_{arms}_{outcome}",
                dataset="hillstrom",
                outcome=outcome,
                arms=arms,
                seeds=tuple(range(min(args.seeds, 5))),
            )
            scen.append(spec.name)
            print(f"\n=== {spec.name} ===")
            frames.append(run_real_scenario(spec, ds))
            # Write after every scenario: this suite is long and a crash at the
            # end would otherwise discard hours of completed work.
            _write(pd.concat(frames, ignore_index=True), "real", "results",
                   _manifest("real", "Real randomized experiments scored by OPE", scen))
    hashes["hillstrom"] = verify("hillstrom")["sha256"]

    if not args.skip_criteo:
        # --criteo-rows 0 means "use every row" (13.98M).
        n_rows = args.criteo_rows if args.criteo_rows > 0 else None
        for outcome in ("visit", "conversion"):
            ds = load_criteo(n_rows=n_rows, outcome=outcome)
            spec = RealSpec(
                name=f"criteo_{outcome}_n{n_rows or 'full'}",
                dataset="criteo",
                outcome=outcome,
                seeds=tuple(range(min(args.seeds, 3))),
                n_rows=n_rows,
            )
            scen.append(spec.name)
            print(f"\n=== {spec.name} ===")
            frames.append(run_real_scenario(spec, ds))
            _write(pd.concat(frames, ignore_index=True), "real", "results",
                   _manifest("real", "Real randomized experiments scored by OPE", scen))
        hashes["criteo"] = verify("criteo")["sha256"]

    man = _manifest("real", "Real randomized experiments scored by OPE", scen)
    man.dataset_hashes = hashes
    man.freeze()
    _write(pd.concat(frames, ignore_index=True), "real", "results", man)


def suite_mmm(args) -> None:
    from leadbench.evaluation.mmm_track import MMMSpec, run_mmm_scenario

    regimes = [
        "mmm_standard",
        "mmm_smb_short_history",
        "mmm_very_short_history",
        "mmm_high_collinearity",
        "mmm_low_signal",
        "mmm_long_history",
    ]
    if args.meridian:
        # Meridian needs its own interpreter and is by far the slowest
        # candidate, so it runs on a representative subset. The command for
        # the full sweep is in docs/methodology.md.
        regimes = ["mmm_standard", "mmm_smb_short_history", "mmm_high_collinearity"]
    specs = [
        MMMSpec(
            name=f"mmm_{r}",
            regime=r,
            seeds=tuple(range(min(args.seeds, 4))),
            include_bayesian=not args.skip_bayesian_mmm,
            include_meridian=args.meridian,
        )
        for r in regimes
    ]
    man = _manifest("mmm", "Marketing-mix track: ROI recovery and budget-allocation regret", [s.name for s in specs])
    frames = []
    for s in specs:
        print(f"\n=== {s.name} ===")
        frames.append(run_mmm_scenario(s))
        _write(pd.concat(frames, ignore_index=True), "mmm", "results", man)


SUITES = {
    "smoke": suite_smoke,
    "lead": suite_lead,
    "curves": suite_curves,
    "ablation": suite_ablation,
    "bayes": suite_bayes,
    "pooling": suite_pooling,
    "online": suite_online,
    "real": suite_real,
    "mmm": suite_mmm,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", required=True, choices=list(SUITES) + ["all"])
    ap.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    ap.add_argument("--n-leads", type=int, default=DEFAULT_N)
    ap.add_argument("--regimes", nargs="*", default=None)
    ap.add_argument("--criteo-rows", type=int, default=2_000_000)
    ap.add_argument("--online-periods", type=int, default=12)
    ap.add_argument("--bayes-sizes", default="5000,20000",
                    help="comma-separated dataset sizes for the bayes suite")
    ap.add_argument("--skip-criteo", action="store_true")
    ap.add_argument("--skip-bayesian-mmm", action="store_true")
    ap.add_argument("--meridian", action="store_true", help="include Google Meridian (needs .venv312)")
    ap.add_argument(
        "--out-name",
        default=None,
        help="write results to reports/runs/<out-name>/ instead of the suite name; "
             "use it for focused re-runs so they cannot clobber a full sweep",
    )
    args = ap.parse_args()

    global OUT_NAME_OVERRIDE
    OUT_NAME_OVERRIDE = args.out_name

    names = list(SUITES) if args.suite == "all" else [args.suite]
    for nm in names:
        t0 = time.time()
        print(f"\n########## suite: {nm} ##########")
        SUITES[nm](args)
        print(f"########## {nm} done in {time.time() - t0:.0f}s ##########")


if __name__ == "__main__":
    main()
