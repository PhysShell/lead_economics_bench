"""Candidate registry.

Tiers let the same code run as a CI smoke suite, a core benchmark and a full
benchmark without any divergence in how candidates are configured.
"""

from __future__ import annotations

from functools import partial
from typing import Callable

from ..evaluation.runner import CandidateSpec
from ..policies.decision import AbstentionPolicy, LowerBoundEVPolicy, RankPolicy
from .naive import (
    ControlOnly,
    FIFOPolicy,
    HistoricalConversionPolicy,
    HistoricalNetProfitPolicy,
    HistoricalProfitPerAgentHourPolicy,
    HistoricalROASPolicy,
    LastClickAttributionPolicy,
    LowestCPLPolicy,
    Oracle,
    RandomPolicy,
    TreatEveryone,
)
from .propensity import BootstrapPropensityEV, FunnelEV, LeadScoreModel, PropensityEV
from .uplift import (
    CausalForest,
    ClassTransformation,
    DRLearner,
    SLearner,
    TLearner,
    XLearner,
)

# Identical capacity for every gradient-boosted learner in the benchmark.
GBM_KW = dict(n_estimators=400, max_depth=5, learning_rate=0.05, min_child_weight=5)

# Causal forest sizing. Profiling showed the forest consuming ~65% of the
# entire benchmark's compute at 400 trees with 3-fold cross-fitting, which buys
# nothing this benchmark measures. At 200 trees / 2 folds it still receives
# roughly an order of magnitude more compute than any boosted candidate, so
# the comparison stays generous to it rather than the reverse.
CAUSAL_FOREST_KW = dict(n_trees=200, cv=2)


def _spec(
    name: str, factory: Callable, *tags: str, policy=None, extra_policies=None
) -> CandidateSpec:
    return CandidateSpec(
        name=name,
        factory=factory,
        policy=policy,
        tags=tags,
        extra_policies=extra_policies or {},
    )


#: Risk attitudes applied to the same fitted model. Preregistered in
#: docs/benchmark-spec.md; they are decision rules, not models, so they share
#: one fit and the contrast between them is exact rather than confounded by
#: refitting.
def _risk_variants(name: str) -> dict:
    return {
        f"{name}_lcb10": LowerBoundEVPolicy(0.10),
        f"{name}_lcb25": LowerBoundEVPolicy(0.25),
        f"{name}_abstain50": AbstentionPolicy(0.50),
        f"{name}_abstain25": AbstentionPolicy(0.25),
    }


def naive_candidates() -> list[CandidateSpec]:
    """Track A: what end-to-end analytics already gives you."""
    return [
        _spec("do_nothing", ControlOnly, "floor"),
        _spec("call_everyone", TreatEveryone, "floor"),
        _spec("random", RandomPolicy, "naive"),
        _spec("fifo", FIFOPolicy, "naive"),
        _spec("lowest_cpl", LowestCPLPolicy, "analytics"),
        _spec("hist_conversion_rate", HistoricalConversionPolicy, "analytics"),
        _spec("hist_roas", HistoricalROASPolicy, "analytics"),
        _spec("hist_net_profit", HistoricalNetProfitPolicy, "analytics"),
        _spec(
            "hist_profit_per_agent_hour",
            HistoricalProfitPerAgentHourPolicy,
            "analytics",
            "strong_baseline",
        ),
        _spec("last_click_attribution", LastClickAttributionPolicy, "analytics"),
    ]


def propensity_candidates() -> list[CandidateSpec]:
    """Track B rung 1-2: lead scoring, then lead scoring with economics."""
    return [
        _spec(
            "lead_score_logit",
            partial(LeadScoreModel, "lead_score_logit", kind="logistic", calibrate=True),
            "propensity",
        ),
        _spec(
            "lead_score_gbm",
            partial(LeadScoreModel, "lead_score_gbm", kind="xgboost", **GBM_KW),
            "propensity",
        ),
        _spec(
            "propensity_ev_logit",
            partial(PropensityEV, "propensity_ev_logit", kind="logistic", calibrate=True),
            "economic",
        ),
        _spec(
            "propensity_ev_gbm",
            partial(PropensityEV, "propensity_ev_gbm", kind="xgboost", **GBM_KW),
            "economic",
            "strong_baseline",
        ),
        _spec(
            "funnel_ev_gbm",
            partial(FunnelEV, "funnel_ev_gbm", kind="xgboost", **GBM_KW),
            "funnel",
        ),
    ]


def causal_candidates(binary_only: bool = True) -> list[CandidateSpec]:
    """Track B rung 3: models that value the control arm properly."""
    out = [
        _spec("s_learner", partial(SLearner, "s_learner", kind="xgboost", **GBM_KW), "causal"),
        _spec("t_learner", partial(TLearner, "t_learner", kind="xgboost", **GBM_KW), "causal"),
        _spec("x_learner", partial(XLearner, "x_learner", kind="xgboost", **GBM_KW), "causal"),
        _spec("dr_learner", partial(DRLearner, "dr_learner", kind="xgboost", **GBM_KW), "causal"),
        _spec(
            "causal_forest",
            partial(CausalForest, "causal_forest", kind="xgboost", **CAUSAL_FOREST_KW, **GBM_KW),
            "causal",
            "uncertainty",
        ),
    ]
    if binary_only:
        out.append(
            _spec(
                "class_transformation",
                partial(ClassTransformation, "class_transformation", kind="xgboost", **GBM_KW),
                "causal",
            )
        )
    return out


def uncertainty_candidates() -> list[CandidateSpec]:
    """Candidates whose point of existence is an interval (RQ5, section 26).

    Each is fitted once and scored under every preregistered risk attitude, so
    "posterior mean vs lower credible bound vs abstain" is a within-model
    contrast rather than a comparison of separately refitted models.
    """
    out = [
        _spec(
            "propensity_ev_gbm_bootstrap",
            partial(
                BootstrapPropensityEV,
                "propensity_ev_gbm_bootstrap",
                kind="xgboost",
                n_bootstrap=16,
                **GBM_KW,
            ),
            "economic",
            "uncertainty",
            extra_policies=_risk_variants("propensity_ev_gbm_bootstrap"),
        ),
    ]
    try:
        from .bayesian import HierarchicalBayesianFunnel  # noqa: F401

        out.append(
            _spec(
                "bayes_hierarchical",
                partial(HierarchicalBayesianFunnel, "bayes_hierarchical"),
                "bayesian",
                "uncertainty",
                extra_policies=_risk_variants("bayes_hierarchical"),
            )
        )
    except Exception:
        pass
    return out


def risk_policy_variants() -> list[CandidateSpec]:
    """Kept for compatibility: risk variants now ride along with their model."""
    return []


def bayes_ablation_candidates() -> list[CandidateSpec]:
    """RQ6: does partial pooling actually buy anything over complete pooling?"""
    try:
        from .bayesian import HierarchicalBayesianFunnel, PooledBayesianFunnel
    except Exception:
        return []
    return [
        _spec(
            "bayes_hierarchical",
            partial(HierarchicalBayesianFunnel, "bayes_hierarchical"),
            "bayesian",
            "uncertainty",
        ),
        _spec(
            "abl_bayes_no_hierarchy",
            partial(PooledBayesianFunnel, "abl_bayes_no_hierarchy"),
            "bayesian",
            "ablation",
        ),
    ]


def oracle_candidate() -> list[CandidateSpec]:
    return [_spec("oracle", Oracle, "oracle")]


def ablation_candidates() -> list[CandidateSpec]:
    """Section 37: where does the advantage actually come from?"""
    return [
        _spec(
            "abl_propensity_ev_no_effort_model",
            partial(
                PropensityEV,
                "abl_propensity_ev_no_effort_model",
                kind="xgboost",
                effort_mode="global",
                **GBM_KW,
            ),
            "ablation",
        ),
        _spec(
            "abl_propensity_ev_no_value_model",
            partial(
                PropensityEV,
                "abl_propensity_ev_no_value_model",
                kind="xgboost",
                value_mode="global",
                **GBM_KW,
            ),
            "ablation",
        ),
        _spec(
            "abl_propensity_ev_no_optimizer",
            partial(PropensityEV, "abl_propensity_ev_no_optimizer", kind="xgboost", **GBM_KW),
            "ablation",
            policy=RankPolicy(),
        ),
        _spec(
            "abl_t_learner_no_value_model",
            partial(
                TLearner,
                "abl_t_learner_no_value_model",
                kind="xgboost",
                value_mode="global",
                **GBM_KW,
            ),
            "ablation",
        ),
        _spec(
            "abl_t_learner_no_effort_model",
            partial(
                TLearner,
                "abl_t_learner_no_effort_model",
                kind="xgboost",
                effort_mode="global",
                **GBM_KW,
            ),
            "ablation",
        ),
        _spec(
            "abl_t_learner_no_optimizer",
            partial(TLearner, "abl_t_learner_no_optimizer", kind="xgboost", **GBM_KW),
            "ablation",
            policy=RankPolicy(),
        ),
    ]


TIERS: dict[str, Callable[[], list[CandidateSpec]]] = {
    "smoke": lambda: (
        oracle_candidate()
        + [
            _spec("do_nothing", ControlOnly, "floor"),
            _spec("random", RandomPolicy, "naive"),
            _spec(
                "hist_profit_per_agent_hour",
                HistoricalProfitPerAgentHourPolicy,
                "analytics",
            ),
            _spec(
                "lead_score_gbm",
                partial(LeadScoreModel, "lead_score_gbm", kind="xgboost", n_estimators=120),
                "propensity",
            ),
            _spec(
                "propensity_ev_gbm",
                partial(PropensityEV, "propensity_ev_gbm", kind="xgboost", n_estimators=120),
                "economic",
            ),
            _spec(
                "t_learner",
                partial(TLearner, "t_learner", kind="xgboost", n_estimators=120),
                "causal",
            ),
        ]
    ),
    "core": lambda: (
        oracle_candidate()
        + naive_candidates()
        + propensity_candidates()
        + causal_candidates()
    ),
    "full": lambda: (
        oracle_candidate()
        + naive_candidates()
        + propensity_candidates()
        + causal_candidates()
        + uncertainty_candidates()
        + risk_policy_variants()
    ),
    "ablation": lambda: (
        oracle_candidate()
        + [
            _spec(
                "hist_profit_per_agent_hour",
                HistoricalProfitPerAgentHourPolicy,
                "analytics",
            ),
            _spec(
                "propensity_ev_gbm",
                partial(PropensityEV, "propensity_ev_gbm", kind="xgboost", **GBM_KW),
                "economic",
            ),
            _spec("t_learner", partial(TLearner, "t_learner", kind="xgboost", **GBM_KW), "causal"),
        ]
        + ablation_candidates()
    ),
}


def get_tier(name: str) -> list[CandidateSpec]:
    if name not in TIERS:
        raise KeyError(f"unknown tier {name!r}; known: {sorted(TIERS)}")
    return TIERS[name]()
