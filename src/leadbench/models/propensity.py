"""Propensity models and the simple economic baseline.

Three rungs of a ladder, deliberately kept distinct because RQ2 and RQ3 are
about the gap between them:

1. :class:`LeadScoreModel` - rank by ``P(funded | X)``. Ordinary lead scoring.
2. :class:`PropensityEV` - ``P(funded | X, a) x E[net contribution] - cost(a)``
   with the control arm valued at **zero**. This is what almost every "AI lead
   prioritisation" feature on the market actually computes: it credits the
   action with the lead's entire conversion probability. It is economically
   literate and causally naive, and it is the baseline our idea has to beat.
3. Uplift/causal models (see :mod:`leadbench.models.uplift`) which value the
   control arm properly.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

from ..features.encoding import add_treatment_column
from .base import (
    ActionValueEstimate,
    Candidate,
    EffortModel,
    FitContext,
    PredictContext,
    ValueModel,
)


#: Thread count for the boosted learners. Set LEADBENCH_NJOBS=1 when running
#: several benchmark processes in parallel, so they do not fight for cores and
#: contaminate the wall-time measurements.
DEFAULT_N_JOBS = int(os.environ.get("LEADBENCH_NJOBS", "2"))


def make_classifier(kind: str, seed: int = 0, **kw: Any):
    """Comparable-capacity classifiers. One knob set, applied to everybody."""
    if kind == "logistic":
        return LogisticRegression(max_iter=2000, C=kw.get("C", 1.0), solver="lbfgs")
    if kind == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=kw.get("n_estimators", 400),
            max_depth=kw.get("max_depth", 5),
            learning_rate=kw.get("learning_rate", 0.05),
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=kw.get("min_child_weight", 5),
            reg_lambda=1.0,
            eval_metric="logloss",
            tree_method="hist",
            n_jobs=kw.get("n_jobs", DEFAULT_N_JOBS),
            random_state=seed,
        )
    if kind == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=kw.get("n_estimators", 400),
            max_depth=kw.get("max_depth", -1),
            num_leaves=kw.get("num_leaves", 31),
            learning_rate=kw.get("learning_rate", 0.05),
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=kw.get("min_child_samples", 30),
            n_jobs=kw.get("n_jobs", DEFAULT_N_JOBS),
            random_state=seed,
            verbose=-1,
        )
    raise ValueError(f"unknown classifier {kind!r}")


class _SupervisedBase(Candidate):
    """Shared fitting: encoder, outcome model, value model, effort model."""

    def __init__(
        self,
        name: str,
        kind: str = "xgboost",
        calibrate: bool = False,
        value_mode: str = "model",
        effort_mode: str = "model",
        n_bootstrap: int = 0,
        **model_kw: Any,
    ) -> None:
        super().__init__(name)
        self.kind = kind
        self.calibrate = calibrate
        self.value_mode = value_mode
        self.effort_mode = effort_mode
        self.n_bootstrap = n_bootstrap
        self.model_kw = model_kw
        self._value: ValueModel | None = None
        self._effort: EffortModel | None = None
        self._n_actions = 3
        self._linear = kind == "logistic"

    def _design(self, df: pd.DataFrame) -> np.ndarray:
        enc = self._encoder
        assert enc is not None
        return enc.transform_linear(df) if self._linear else enc.transform_tree(df)

    def _fit_nuisance(self, ctx: FitContext, train: pd.DataFrame) -> None:
        enc = self.encoder(ctx)
        Xt = enc.transform_tree(train)
        self._value = ValueModel(mode=self.value_mode, seed=ctx.seed).fit(train, Xt)
        self._effort = EffortModel(mode=self.effort_mode, seed=ctx.seed).fit(
            train, Xt, call_action=ctx.n_actions - 1
        )
        self._n_actions = ctx.n_actions

    def _nuisance_matrices(
        self, ctx: PredictContext
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        enc = self._encoder
        assert enc is not None and self._value is not None and self._effort is not None
        Xt = enc.transform_tree(ctx.df)
        value = self._value.predict(Xt)
        minutes = self._effort.predict_matrix(Xt, ctx.n_actions, ctx.economics)
        cost = ctx.economics.action_cost(minutes)
        return value, minutes, cost

    def _fit_outcome(self, X: np.ndarray, y: np.ndarray, seed: int):
        clf = make_classifier(self.kind, seed=seed, **self.model_kw)
        if self.calibrate:
            n_pos = int(y.sum())
            if n_pos >= 50 and len(y) - n_pos >= 50:
                method = "isotonic" if n_pos >= 500 else "sigmoid"
                clf = CalibratedClassifierCV(clf, method=method, cv=3)
        clf.fit(X, y)
        return clf


class LeadScoreModel(_SupervisedBase):
    """Ordinary lead scoring: rank by ``P(funded | X)``, action ignored.

    No economics, no counterfactual. This is the incumbent that a decision
    engine claims to beat, so it gets a fair shot: it is trained on all
    historical leads exactly as a CRM scoring feature would be.
    """

    family = "propensity"
    allocation_mode = "rank"

    def _fit(self, ctx: FitContext) -> None:
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        self._clf = self._fit_outcome(X, y, ctx.seed)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p = self._clf.predict_proba(X)[:, 1]
        value, minutes, cost = self._nuisance_matrices(ctx)
        ev = p[:, None] * value[:, None] - cost
        ev[:, 0] = 0.0
        p_mat = np.tile(p[:, None], (1, ctx.n_actions))
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            p_outcome=p_mat,
            score=p,
            value_per_conversion=value,
        )


class PropensityEV(_SupervisedBase):
    """``P(funded | X, a) x value(X) - cost(a)`` with the control arm at zero.

    Economically literate, causally naive. The single most important baseline
    in this benchmark: if it lands close to the Oracle, the causal machinery is
    not worth shipping.
    """

    family = "economic"
    allocation_mode = "ev"

    def __init__(self, *args: Any, credit_control: bool = False, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.credit_control = credit_control

    def _fit(self, ctx: FitContext) -> None:
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        X = self._design(train)
        Xa = add_treatment_column(
            X, train["action"].to_numpy(dtype=int), ctx.n_actions
        )
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        self._clf = self._fit_outcome(Xa, y, ctx.seed)

    def _p_by_action(self, ctx: PredictContext) -> np.ndarray:
        X = self._design(ctx.df)
        n = len(X)
        out = np.zeros((n, ctx.n_actions))
        for a in range(ctx.n_actions):
            Xa = add_treatment_column(X, np.full(n, a), ctx.n_actions)
            out[:, a] = self._clf.predict_proba(Xa)[:, 1]
        return out

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        p = self._p_by_action(ctx)
        value, minutes, cost = self._nuisance_matrices(ctx)
        ev = p * value[:, None] - cost
        if not self.credit_control:
            # The defining assumption of this family: an untouched lead is
            # assumed worth nothing, i.e. the action gets credit for the
            # lead's whole conversion probability.
            ev[:, 0] = 0.0
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            p_outcome=p,
            cate=p - p[:, [0]],
            score=ev[:, ctx.n_actions - 1],
            value_per_conversion=value,
        )


class FunnelEV(_SupervisedBase):
    """Decomposed funnel: P(contact) x P(qual|contact) x P(app|qual) x P(fund|app).

    Each stage model sees the action. Stage models are trained on the rows that
    actually reached the previous stage, which is the honest construction and
    also the one that runs out of data first in rare-outcome regimes.
    """

    family = "funnel"
    allocation_mode = "ev"

    STAGES = ("contacted", "qualified", "applied", "funded")
    PARENTS = (None, "contacted", "qualified", "applied")

    def __init__(self, *args: Any, credit_control: bool = False, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.credit_control = credit_control

    def _fit(self, ctx: FitContext) -> None:
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._models: list[Any] = []
        self._fallback: list[float] = []
        X_all = self._design(train)
        act = train["action"].to_numpy(dtype=int)
        for s, (stage, parent) in enumerate(zip(self.STAGES, self.PARENTS)):
            if parent is None:
                mask = np.ones(len(train), dtype=bool)
            else:
                mask = (train[parent] == 1).to_numpy()
            mask = mask & train[stage].notna().to_numpy()
            y = train.loc[mask, stage].to_numpy(dtype=int)
            base = float(y.mean()) if len(y) else 0.0
            self._fallback.append(base)
            if len(y) < 100 or y.sum() < 10 or (len(y) - y.sum()) < 10:
                self._models.append(None)
                continue
            Xa = add_treatment_column(X_all[mask], act[mask], ctx.n_actions)
            self._models.append(self._fit_outcome(Xa, y, ctx.seed + s))

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        n = len(X)
        p = np.ones((n, ctx.n_actions))
        stage_p: dict[str, np.ndarray] = {}
        for s, stage in enumerate(self.STAGES):
            ps = np.zeros((n, ctx.n_actions))
            for a in range(ctx.n_actions):
                if self._models[s] is None:
                    ps[:, a] = self._fallback[s]
                else:
                    Xa = add_treatment_column(X, np.full(n, a), ctx.n_actions)
                    ps[:, a] = self._models[s].predict_proba(Xa)[:, 1]
            stage_p[stage] = ps
            p = p * ps
        value, minutes, cost = self._nuisance_matrices(ctx)
        ev = p * value[:, None] - cost
        if not self.credit_control:
            ev[:, 0] = 0.0
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            p_outcome=p,
            cate=p - p[:, [0]],
            score=ev[:, ctx.n_actions - 1],
            value_per_conversion=value,
            diagnostics={"stage_models_fitted": sum(m is not None for m in self._models)},
        )


class BootstrapPropensityEV(PropensityEV):
    """Propensity-EV with bagged uncertainty.

    The frequentist answer to RQ5: you do not need a posterior to get an
    interval. If bagging closes most of the gap to a Bayesian model, the
    Bayesian machinery is buying calibration, not information.
    """

    family = "economic"
    has_uncertainty = True

    def __init__(self, *args: Any, n_bootstrap: int = 20, **kw: Any) -> None:
        kw["n_bootstrap"] = n_bootstrap
        super().__init__(*args, **kw)

    def _fit(self, ctx: FitContext) -> None:
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        X = self._design(train)
        act = train["action"].to_numpy(dtype=int)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        Xa = add_treatment_column(X, act, ctx.n_actions)
        self._clf = self._fit_outcome(Xa, y, ctx.seed)
        rng = np.random.default_rng(ctx.seed)
        self._ens = []
        n = len(y)
        for b in range(self.n_bootstrap):
            idx = rng.integers(0, n, n)
            if y[idx].sum() < 5:
                continue
            self._ens.append(self._fit_outcome(Xa[idx], y[idx], ctx.seed + 1000 + b))

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        est = super()._estimate(ctx)
        if not self._ens:
            return est
        X = self._design(ctx.df)
        n = len(X)
        value, minutes, cost = self._nuisance_matrices(ctx)
        samples = np.zeros((len(self._ens), n, ctx.n_actions))
        for b, m in enumerate(self._ens):
            for a in range(ctx.n_actions):
                Xa = add_treatment_column(X, np.full(n, a), ctx.n_actions)
                samples[b, :, a] = m.predict_proba(Xa)[:, 1]
        est.p_samples = samples.copy()
        samples = samples * value[None, :, None] - cost[None, :, :]
        if not self.credit_control:
            samples[:, :, 0] = 0.0
        est.ev_samples = samples
        return est
