"""Online track: contextual bandits versus a frozen model versus a retrained one.

RQ7 asks when the loop

    context -> action -> reward -> update

beats

    train once -> deploy a fixed policy.

To answer that honestly every competitor must get the *same* history, the same
capacity, the same deal-value and effort models, and its own trajectory. The
last part matters: once competitors choose differently they observe different
outcomes, which is exactly the selection feedback loop the product is supposed
to worry about (section 47). A competitor that only ever calls its own
favourites only ever learns about its own favourites.
"""

from __future__ import annotations

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
from ..features.encoding import TabularEncoder
from ..metrics.economic import economic_summary
from ..models.bandits import ONLINE_LEARNERS, OnlineLearner
from ..models.base import (
    ActionValueEstimate,
    EffortModel,
    FitContext,
    PredictContext,
    ValueModel,
)
from ..models.propensity import PropensityEV
from ..policies.decision import EVPolicy, enforce_true_capacity
from ..synthetic.config import DGPConfig, make_config
from ..synthetic.dgp import LeadDataset, generate
from .splits import temporal_split


@dataclass
class OnlineSpec:
    name: str
    regime: str
    n_leads: int = 30_000
    capacity_ratio: float = 0.25
    seeds: tuple[int, ...] = (0, 1, 2)
    action_set: tuple[str, ...] = ("none", "call")
    history_frac: float = 0.40
    n_periods: int = 12
    retrain_every: int = 3
    economics: Economics = field(default_factory=Economics)

    def config(self, seed: int) -> DGPConfig:
        return make_config(
            self.regime,
            n_leads=self.n_leads,
            seed=seed,
            action_set=self.action_set,
        )


def materialise_observation(
    ds: LeadDataset, idx: np.ndarray, actions: np.ndarray, econ: Economics
) -> pd.DataFrame:
    """Build the CRM rows that *would* have been logged under ``actions``.

    This is the simulator writing the decision log: outcomes, effort and
    revenue all follow from the potential outcomes for the action actually
    taken, so a competitor learns only from what it chose to do.
    """
    obs = ds.observed.iloc[idx].copy().reset_index(drop=True)
    truth = ds.truth.iloc[idx].reset_index(drop=True)
    n = len(obs)
    rows = np.arange(n)
    A = ds.n_actions

    y = np.column_stack([truth[f"y_funded_a{a}"].to_numpy() for a in range(A)])
    yq = np.column_stack([truth[f"y_qualified_a{a}"].to_numpy() for a in range(A)])
    mins = np.column_stack([truth[f"minutes_a{a}"].to_numpy() for a in range(A)])

    funded = y[rows, actions]
    obs["action"] = actions
    obs["action_name"] = np.asarray(ds.actions)[actions]
    obs["minutes_spent"] = mins[rows, actions]
    obs["action_direct_cost"] = econ.direct_cost_vector(A)[actions]
    obs["funded"] = funded
    obs["qualified"] = yq[rows, actions]
    obs["realized_net_contribution"] = np.where(
        funded > 0, truth["net_contribution"].to_numpy(), 0.0
    )
    obs["realized_gross_value"] = np.where(
        funded > 0, truth["gross_value"].to_numpy(), 0.0
    )
    obs["censored"] = False
    return obs


class _Competitor:
    name = "competitor"
    kind = "offline"

    def act(self, X, df, ds, idx, constraints, econ) -> np.ndarray:
        raise NotImplementedError

    def learn(self, X, obs_df, actions, rewards) -> None:
        return None


class BanditCompetitor(_Competitor):
    kind = "bandit"

    def __init__(self, learner: OnlineLearner, name: str, value, effort, econ):
        self.learner = learner
        self.name = name
        self.value = value
        self.effort = effort
        self.econ = econ

    def act(self, X, df, ds, idx, constraints, econ) -> np.ndarray:
        p = self.learner.score(X)
        value = self.value.predict(X)
        minutes = self.effort.predict_matrix(X, ds.n_actions, econ)
        cost = econ.action_cost(minutes)
        ev = p * value[:, None] - cost
        est = ActionValueEstimate(ev=ev, minutes=minutes, p_outcome=p)
        dec = EVPolicy().decide(est, constraints)
        true_minutes = np.column_stack(
            [ds.truth.iloc[idx][f"minutes_a{a}"].to_numpy() for a in range(ds.n_actions)]
        )
        actions, _ = enforce_true_capacity(
            true_minutes, dec.actions, dec.priority, constraints
        )
        return actions

    def learn(self, X, obs_df, actions, rewards) -> None:
        self.learner.update(X, actions, rewards)


class ModelCompetitor(_Competitor):
    """A frozen or periodically retrained offline model."""

    kind = "offline"

    def __init__(self, name: str, factory: Callable, retrain_every: int | None, ctx_proto):
        self.name = name
        self.factory = factory
        self.retrain_every = retrain_every
        self.ctx_proto = ctx_proto
        self.model = None
        self.history: list[pd.DataFrame] = []
        self.periods_since_fit = 0

    def fit_initial(self, history: pd.DataFrame) -> None:
        self.history = [history]
        self._refit()

    def _refit(self) -> None:
        df = pd.concat(self.history, ignore_index=True)
        ctx = FitContext(
            df=df,
            feature_columns=self.ctx_proto["feature_columns"],
            categorical_columns=self.ctx_proto["categorical_columns"],
            economics=self.ctx_proto["economics"],
            action_names=self.ctx_proto["action_names"],
            seed=self.ctx_proto["seed"],
        )
        self.model = self.factory()
        self.model.fit(ctx)
        self.periods_since_fit = 0

    def act(self, X, df, ds, idx, constraints, econ) -> np.ndarray:
        ctx = PredictContext(
            df=df,
            feature_columns=self.ctx_proto["feature_columns"],
            categorical_columns=self.ctx_proto["categorical_columns"],
            economics=econ,
            action_names=ds.actions,
            seed=self.ctx_proto["seed"],
        )
        est = self.model.estimate(ctx)
        dec = EVPolicy().decide(est, constraints)
        true_minutes = np.column_stack(
            [ds.truth.iloc[idx][f"minutes_a{a}"].to_numpy() for a in range(ds.n_actions)]
        )
        actions, _ = enforce_true_capacity(
            true_minutes, dec.actions, dec.priority, constraints
        )
        return actions

    def learn(self, X, obs_df, actions, rewards) -> None:
        if self.retrain_every is None:
            return
        self.history.append(obs_df)
        self.periods_since_fit += 1
        if self.periods_since_fit >= self.retrain_every:
            self._refit()


class OracleCompetitor(_Competitor):
    kind = "oracle"
    name = "oracle"

    def act(self, X, df, ds, idx, constraints, econ) -> np.ndarray:
        tr = ds.truth.iloc[idx]
        A = ds.n_actions
        ev = np.column_stack([tr[f"ev_a{a}"].to_numpy() for a in range(A)])
        minutes = np.column_stack([tr[f"minutes_a{a}"].to_numpy() for a in range(A)])
        est = ActionValueEstimate(ev=ev, minutes=minutes)
        dec = EVPolicy().decide(est, constraints)
        actions, _ = enforce_true_capacity(minutes, dec.actions, dec.priority, constraints)
        return actions


class RandomCompetitor(_Competitor):
    kind = "naive"
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def act(self, X, df, ds, idx, constraints, econ) -> np.ndarray:
        n = len(df)
        A = ds.n_actions
        minutes = np.column_stack(
            [ds.truth.iloc[idx][f"minutes_a{a}"].to_numpy() for a in range(A)]
        )
        score = self.rng.random(n)
        ev = np.zeros((n, A))
        ev[:, -1] = score
        est = ActionValueEstimate(ev=ev, minutes=minutes, score=score)
        from ..policies.decision import RankPolicy

        dec = RankPolicy().decide(est, constraints)
        actions, _ = enforce_true_capacity(minutes, dec.actions, dec.priority, constraints)
        return actions


def run_online_scenario(spec: OnlineSpec, verbose: bool = True) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for seed in spec.seeds:
        ds = generate(spec.config(seed))
        split = temporal_split(ds, spec.history_frac, 0.0)
        history = split.train.observed
        live = ds.subset(
            ds.observed["created_day"].to_numpy() > split.boundaries[0]
        )

        econ = Economics(
            default_net_contribution=estimate_default_net_contribution(history)
        )
        enc = TabularEncoder.from_columns(
            ds.feature_columns, ds.categorical_columns
        ).fit(history)
        Xh = enc.transform_tree(history)
        value = ValueModel(mode="model", seed=seed).fit(history, Xh)
        effort = EffortModel(mode="model", seed=seed).fit(
            history, Xh, call_action=ds.n_actions - 1
        )

        ctx_proto = {
            "feature_columns": ds.feature_columns,
            "categorical_columns": ds.categorical_columns,
            "economics": econ,
            "action_names": ds.actions,
            "seed": seed,
        }

        # Period boundaries over the live window.
        days = live.observed["created_day"].to_numpy()
        edges = np.quantile(days, np.linspace(0, 1, spec.n_periods + 1))
        edges[0] -= 1

        total_capacity = capacity_for_ratio(live, spec.capacity_ratio)

        competitors: list[_Competitor] = [OracleCompetitor(), RandomCompetitor(seed)]
        for key in ("linucb", "thompson", "epsilon_greedy", "greedy_online"):
            learner = ONLINE_LEARNERS[key](
                n_actions=ds.n_actions, n_features=Xh.shape[1], seed=seed
            )
            learner.warm_start(
                Xh,
                history["action"].to_numpy(dtype=int),
                history["funded"].fillna(0).to_numpy(dtype=float),
            )
            competitors.append(
                BanditCompetitor(learner, f"bandit_{key}", value, effort, econ)
            )

        from functools import partial

        static = ModelCompetitor(
            "static_propensity_ev",
            partial(PropensityEV, "static_propensity_ev", kind="xgboost", n_estimators=300),
            retrain_every=None,
            ctx_proto=ctx_proto,
        )
        static.fit_initial(history)
        periodic = ModelCompetitor(
            "retrained_propensity_ev",
            partial(PropensityEV, "retrained_propensity_ev", kind="xgboost", n_estimators=300),
            retrain_every=spec.retrain_every,
            ctx_proto=ctx_proto,
        )
        periodic.fit_initial(history)
        competitors += [static, periodic]

        totals = {c.name: 0.0 for c in competitors}
        treated = {c.name: 0 for c in competitors}
        n_live = 0

        for p in range(spec.n_periods):
            lo, hi = edges[p], edges[p + 1]
            idx = np.where((days > lo) & (days <= hi))[0]
            if len(idx) == 0:
                continue
            n_live += len(idx)
            period_df = live.observed.iloc[idx].reset_index(drop=True)
            Xp = enc.transform_tree(period_df)
            cap = total_capacity * len(idx) / len(days)
            constraints = Constraints(agent_minutes=cap)
            sub = live.subset(np.isin(np.arange(len(live.observed)), idx))

            for c in competitors:
                actions = c.act(Xp, period_df, live, idx, constraints, econ)
                out = realized_net_value(sub, actions)
                totals[c.name] += out.net_value
                treated[c.name] += int((actions != 0).sum())
                obs_df = materialise_observation(live, idx, actions, econ)
                c.learn(Xp, obs_df, actions, obs_df["funded"].to_numpy(dtype=float))

        floor = control_everything_value(live).net_value
        oracle_total = totals["oracle"]
        for c in competitors:
            denom = oracle_total - floor
            rows.append(
                {
                    "scenario": spec.name,
                    "regime": spec.regime,
                    "seed": seed,
                    "competitor": c.name,
                    "kind": c.kind,
                    "net_value": totals[c.name],
                    "net_value_per_1k_leads": 1000.0 * totals[c.name] / max(n_live, 1),
                    "incremental_net_value": totals[c.name] - floor,
                    "pct_of_oracle_incremental": (
                        100.0 * (totals[c.name] - floor) / denom
                        if abs(denom) > 1e-9
                        else float("nan")
                    ),
                    "share_treated": treated[c.name] / max(n_live, 1),
                    "n_live": n_live,
                    "capacity_ratio": spec.capacity_ratio,
                    "n_periods": spec.n_periods,
                }
            )
            if verbose:
                print(
                    f"  online {spec.regime} seed={seed} {c.name:26s} "
                    f"%oracle={rows[-1]['pct_of_oracle_incremental']:6.1f}"
                )
    return pd.DataFrame(rows)
