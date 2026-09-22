"""Scenario runner: generate -> split -> fit -> decide -> score.

One code path for every candidate. The Oracle goes through the identical
allocator, the identical capacity enforcement and the identical accounting, so
"percent of Oracle" means something.
"""

from __future__ import annotations

import gc
import resource
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from ..economics import (
    Constraints,
    Economics,
    capacity_for_ratio,
    control_everything_value,
    estimate_default_net_contribution,
    realized_net_value,
)
from ..metrics.causal import causal_summary, uplift_summary
from ..metrics.economic import economic_summary
from ..metrics.predictive import predictive_summary
from ..metrics.uncertainty import uncertainty_summary
from ..models.base import (
    ActionValueEstimate,
    Candidate,
    FitContext,
    PredictContext,
    TruthAwareCandidate,
)
from ..policies.decision import (
    EVPolicy,
    Policy,
    RankPolicy,
    enforce_true_capacity,
)
from ..synthetic.config import DGPConfig, make_config
from ..synthetic.dgp import LeadDataset, generate
from .splits import audit_split, drop_cross_split_duplicates, temporal_split


@dataclass
class ScenarioSpec:
    """A single benchmark cell: regime x sample size x capacity."""

    name: str
    regime: str
    n_leads: int = 20_000
    capacity_ratio: float | None = 0.25
    seeds: tuple[int, ...] = (0, 1, 2)
    action_set: tuple[str, ...] = ("none", "call")
    train_frac: float = 0.60
    valid_frac: float = 0.15
    economics: Economics = field(default_factory=Economics)
    dgp_overrides: dict[str, Any] = field(default_factory=dict)

    def config(self, seed: int) -> DGPConfig:
        return make_config(
            self.regime,
            n_leads=self.n_leads,
            seed=seed,
            action_set=self.action_set,
            **self.dgp_overrides,
        )


CandidateFactory = Callable[[], Candidate]


@dataclass
class CandidateSpec:
    name: str
    factory: CandidateFactory
    policy: Policy | None = None  # None -> chosen from candidate.allocation_mode
    tags: tuple[str, ...] = ()
    #: Extra policies to apply to the SAME fitted model, as
    #: ``{row_name: policy}``. Risk attitude is a property of the decision
    #: rule, not of the model, so refitting an expensive posterior once per
    #: risk setting wastes compute and makes the comparison unpaired. Sharing
    #: one fit makes "mean EV vs lower credible bound" an exact within-model
    #: contrast.
    extra_policies: dict[str, Policy] = field(default_factory=dict)


def _policy_for(candidate: Candidate, override: Policy | None) -> Policy:
    if override is not None:
        return override
    if candidate.allocation_mode == "rank":
        return RankPolicy()
    return EVPolicy()


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run_scenario(
    spec: ScenarioSpec,
    candidates: list[CandidateSpec],
    verbose: bool = True,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for seed in spec.seeds:
        ds = generate(spec.config(seed))
        split = temporal_split(ds, spec.train_frac, spec.valid_frac)
        split = drop_cross_split_duplicates(split)
        audit = audit_split(split, ds.feature_columns)

        test = split.test
        capacity = (
            capacity_for_ratio(test, spec.capacity_ratio)
            if spec.capacity_ratio is not None
            else None
        )
        constraints = Constraints(agent_minutes=capacity)

        econ = Economics(
            agent_cost_per_hour=spec.economics.agent_cost_per_hour,
            sms_direct_cost=spec.economics.sms_direct_cost,
            call_direct_cost=spec.economics.call_direct_cost,
            sms_minutes=spec.economics.sms_minutes,
            default_net_contribution=estimate_default_net_contribution(
                split.train.observed
            ),
        )

        fit_ctx = FitContext(
            df=split.train.observed,
            feature_columns=ds.feature_columns,
            categorical_columns=ds.categorical_columns,
            economics=econ,
            action_names=ds.actions,
            seed=seed,
        )
        pred_ctx = PredictContext(
            df=test.observed,
            feature_columns=ds.feature_columns,
            categorical_columns=ds.categorical_columns,
            economics=econ,
            action_names=ds.actions,
            seed=seed,
        )

        floor = control_everything_value(test)
        oracle_value = _oracle_value(test, constraints)

        true_minutes = np.column_stack(
            [test.truth[f"minutes_a{a}"].to_numpy() for a in range(test.n_actions)]
        )

        for cs in candidates:
            base_row: dict[str, Any] = {
                "scenario": spec.name,
                "regime": spec.regime,
                "n_leads": spec.n_leads,
                "capacity_ratio": spec.capacity_ratio,
                "seed": seed,
                "candidate": cs.name,
                "tags": ",".join(cs.tags),
                **audit,
            }
            try:
                rss0 = _peak_rss_mb()
                cand = cs.factory()
                if isinstance(cand, TruthAwareCandidate):
                    cand.set_truth(test.truth)
                cand.fit(fit_ctx)
                est = cand.estimate(pred_ctx)
                rss = max(_peak_rss_mb() - rss0, 0.0)

                variants: list[tuple[str, Policy]] = [
                    (cs.name, _policy_for(cand, cs.policy))
                ]
                variants += list(cs.extra_policies.items())

                for row_name, policy in variants:
                    row = dict(base_row)
                    dec = policy.decide(est, constraints)
                    actions, cap_info = enforce_true_capacity(
                        true_minutes, dec.actions, dec.priority, constraints
                    )
                    outcome = realized_net_value(test, actions)

                    row.update(cand.describe())
                    row["candidate"] = row_name
                    row["base_model"] = cs.name
                    row["policy"] = policy.name
                    row.update(
                        economic_summary(
                            outcome,
                            floor,
                            oracle_value=oracle_value,
                            capacity_minutes=capacity,
                        )
                    )
                    row.update(_quality_metrics(est, test, actions))
                    row["fit_seconds"] = cand.fit_seconds
                    row["predict_seconds"] = cand.predict_seconds
                    row["peak_rss_delta_mb"] = rss
                    row["planned_minutes"] = dec.planned_minutes
                    row.update({f"cap_{k}": v for k, v in cap_info.items()})
                    row["status"] = "ok"
                    rows.append(row)
                    if verbose:
                        print(
                            f"  {spec.name} seed={seed} {row_name:34s} "
                            f"net/1k={row.get('net_value_per_1k_leads', float('nan')):9.1f} "
                            f"%oracle={row.get('pct_of_oracle_incremental', float('nan')):6.1f}"
                        )
                del cand, est
                gc.collect()
            except Exception as exc:  # noqa: BLE001 - failures are results too
                base_row["status"] = f"error: {type(exc).__name__}: {exc}"
                base_row["traceback"] = traceback.format_exc()[-1200:]
                rows.append(base_row)
                if verbose:
                    print(f"  !! {cs.name} failed: {type(exc).__name__}: {exc}")
    return pd.DataFrame(rows)


def _oracle_value(test: LeadDataset, constraints: Constraints) -> float:
    """Best feasible policy, using the same allocator every candidate gets."""
    from ..models.naive import Oracle

    n_actions = test.n_actions
    ev = np.column_stack([test.truth[f"ev_a{a}"].to_numpy() for a in range(n_actions)])
    minutes = np.column_stack(
        [test.truth[f"minutes_a{a}"].to_numpy() for a in range(n_actions)]
    )
    est = ActionValueEstimate(ev=ev, minutes=minutes)
    dec = EVPolicy().decide(est, constraints)
    actions, _ = enforce_true_capacity(minutes, dec.actions, dec.priority, constraints)
    return realized_net_value(test, actions).net_value


def _quality_metrics(
    est: ActionValueEstimate, test: LeadDataset, actions: np.ndarray
) -> dict[str, float]:
    """Predictive, causal, uplift and uncertainty metrics, where applicable."""
    out: dict[str, float] = {}
    obs, truth = test.observed, test.truth
    call = test.n_actions - 1
    logged = obs["action"].to_numpy(dtype=int)
    y = obs["funded"].to_numpy(dtype=float)
    resolved = np.isfinite(y)

    # Predictive quality is scored on the arm that was actually logged, which
    # is the only arm with an observed outcome.
    if est.p_outcome is not None:
        p_logged = est.p_outcome[np.arange(len(logged)), logged]
        out.update(
            {
                f"pred_{k}": v
                for k, v in predictive_summary(y[resolved], p_logged[resolved]).items()
            }
        )

    if est.cate is not None and f"cate_a{call}" in truth.columns:
        out.update(
            {
                f"causal_{k}": v
                for k, v in causal_summary(
                    truth[f"cate_a{call}"].to_numpy(), est.cate[:, call]
                ).items()
            }
        )

    # Uplift ranking metrics need a binary treatment view of the logged data.
    score = est.score
    if score is None and est.cate is not None:
        score = est.cate[:, call]
    if score is not None and test.n_actions == 2:
        t_bin = (logged == call).astype(int)
        m = resolved & np.isfinite(score)
        if m.sum() > 100 and 0 < t_bin[m].mean() < 1:
            out.update(
                {f"uplift_{k}": v for k, v in uplift_summary(y[m], t_bin[m], score[m]).items()}
            )

    # Uncertainty: does the stated 80% interval on EV(call) cover the truth?
    if est.ev_samples is not None:
        out.update(
            uncertainty_summary(
                truth[f"ev_a{call}"].to_numpy(), est.ev_samples[:, :, call]
            )
        )
        # Same question one level up the chain. If probability coverage is fine
        # but EV coverage is not, the blame sits with the point-estimated deal
        # value and effort models, not with the posterior.
        if est.p_samples is not None:
            pcov = uncertainty_summary(
                truth[f"p_funded_a{call}"].to_numpy(), est.p_samples[:, :, call]
            )
            out.update({f"p_{k}": v for k, v in pcov.items()})

    # True economic value of what the policy believed versus what it chose.
    true_ev = np.column_stack(
        [truth[f"ev_a{a}"].to_numpy() for a in range(test.n_actions)]
    )
    idx = np.arange(len(actions))
    out["chosen_true_ev_mean"] = float(true_ev[idx, actions].mean())
    out["share_treated"] = float((actions != 0).mean())
    return out
