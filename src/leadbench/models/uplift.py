"""Uplift / causal candidates.

Estimators come from maintained libraries (EconML, scikit-uplift) rather than
being hand-rolled; the only bespoke code here is the thin adapter that makes a
classifier usable where EconML expects a regressor, so that every family shares
identical base learners and hyperparameters.

All of these value the control arm properly:

    EV(a) = P(funded | X, a) * value(X) - cost(a, X)

so that the decision compares "call" against "the lead might convert anyway",
which is exactly what :class:`~leadbench.models.propensity.PropensityEV`
refuses to do.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone

from .base import ActionValueEstimate, FitContext, PredictContext
from .propensity import _SupervisedBase, make_classifier


class ProbaRegressor(BaseEstimator, RegressorMixin):
    """Expose a classifier's ``predict_proba[:, 1]`` through ``predict``.

    EconML's meta-learners want regressors for the outcome model. Fitting a
    plain regressor to a 0/1 target works but throws away the calibration a
    classifier gives you, and it lets probabilities leave [0, 1]. This adapter
    keeps every family on the identical base learner instead.
    """

    def __init__(self, kind: str = "xgboost", seed: int = 0, **kw: Any) -> None:
        self.kind = kind
        self.seed = seed
        self.kw = kw

    def fit(self, X, y, **fit_params):
        y = np.asarray(y).ravel()
        self.classes_ = np.unique(y)
        if len(self.classes_) < 2:
            self._const = float(y.mean()) if len(y) else 0.0
            self._clf = None
            return self
        self._const = None
        self._clf = make_classifier(self.kind, seed=self.seed, **self.kw)
        self._clf.fit(X, y)
        return self

    def predict(self, X):
        if self._clf is None:
            return np.full(len(X), self._const)
        return self._clf.predict_proba(X)[:, 1]


class _CausalBase(_SupervisedBase):
    """Shared plumbing: fit nuisances, turn a CATE surface into an EV surface."""

    family = "causal"
    allocation_mode = "ev"
    is_causal = True

    def _p_control(self, ctx: PredictContext) -> np.ndarray:
        """Baseline conversion probability with no action taken."""
        X = self._design(ctx.df)
        return np.clip(self._p0_model.predict(X), 1e-6, 1 - 1e-6)

    def _fit_baseline(self, ctx: FitContext, train: pd.DataFrame) -> None:
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        ctrl = t == 0
        self._p0_model = ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw)
        if ctrl.sum() >= 100 and 0 < y[ctrl].sum() < ctrl.sum():
            self._p0_model.fit(X[ctrl], y[ctrl])
        else:
            self._p0_model.fit(X, y)

    def _assemble(
        self, ctx: PredictContext, p0: np.ndarray, cate: np.ndarray
    ) -> ActionValueEstimate:
        """cate has shape (n, A) with a zero control column."""
        p = np.clip(p0[:, None] + cate, 0.0, 1.0)
        value, minutes, cost = self._nuisance_matrices(ctx)
        ev = p * value[:, None] - cost
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            p_outcome=p,
            cate=cate,
            score=ev[:, ctx.call_action] - ev[:, 0],
            value_per_conversion=value,
        )


class TLearner(_CausalBase):
    """One outcome model per arm (EconML ``metalearners.TLearner``)."""

    def _fit(self, ctx: FitContext) -> None:
        from econml.metalearners import TLearner as _T

        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        base = ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw)
        self._est = _T(models=[clone(base) for _ in range(ctx.n_actions)])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(y, t, X=X)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        cate = np.zeros((len(X), ctx.n_actions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in range(1, ctx.n_actions):
                cate[:, a] = np.asarray(self._est.effect(X, T0=0, T1=a)).ravel()
        return self._assemble(ctx, p0, cate)


class SLearner(_CausalBase):
    """Single model with treatment as a feature (EconML ``metalearners.SLearner``)."""

    def _fit(self, ctx: FitContext) -> None:
        from econml.metalearners import SLearner as _S

        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        self._est = _S(
            overall_model=ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw)
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(y, t, X=X)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        cate = np.zeros((len(X), ctx.n_actions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in range(1, ctx.n_actions):
                cate[:, a] = np.asarray(self._est.effect(X, T0=0, T1=a)).ravel()
        return self._assemble(ctx, p0, cate)


class XLearner(_CausalBase):
    """EconML ``metalearners.XLearner``: imputed-effect models weighted by propensity.

    Designed for imbalanced arms, which is exactly the shape of real CRM data
    where almost nobody is left untouched.
    """

    def _fit(self, ctx: FitContext) -> None:
        from econml.metalearners import XLearner as _X

        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        base = ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw)
        # EconML wants one estimator per arm *including control* for both
        # `models` and `cate_models`. The outcome models predict a probability,
        # so a classifier wrapper is right; the cate models regress on a
        # continuous pseudo-effect, so they must be genuine regressors.
        self._est = _X(
            models=[clone(base) for _ in range(ctx.n_actions)],
            cate_models=[_final_regressor(ctx.seed + i) for i in range(ctx.n_actions)],
            propensity_model=make_classifier(
                "logistic" if self.kind == "logistic" else "lightgbm", seed=ctx.seed
            ),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(y, t, X=X)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        cate = np.zeros((len(X), ctx.n_actions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in range(1, ctx.n_actions):
                cate[:, a] = np.asarray(self._est.effect(X, T0=0, T1=a)).ravel()
        return self._assemble(ctx, p0, cate)


class DRLearner(_CausalBase):
    """EconML ``dr.DRLearner``: doubly robust, cross-fitted.

    The estimator that should shine when the logging policy is confounded but
    the confounder is observed.
    """

    has_uncertainty = False

    def __init__(self, *args: Any, cv: int = 3, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.cv = cv

    def _fit(self, ctx: FitContext) -> None:
        from econml.dr import DRLearner as _DR

        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        self._est = _DR(
            model_propensity=make_classifier("lightgbm", seed=ctx.seed, n_estimators=200),
            model_regression=ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw),
            model_final=_final_regressor(ctx.seed),
            cv=self.cv,
            random_state=ctx.seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(y, t, X=X)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        cate = np.zeros((len(X), ctx.n_actions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in range(1, ctx.n_actions):
                cate[:, a] = np.asarray(self._est.effect(X, T0=0, T1=a)).ravel()
        return self._assemble(ctx, p0, cate)


class CausalForest(_CausalBase):
    """EconML ``dml.CausalForestDML``. Honest forests, with built-in intervals."""

    has_uncertainty = True

    def __init__(self, *args: Any, n_trees: int = 400, cv: int = 3, **kw: Any) -> None:
        # Deliberately named `n_trees`, not `n_estimators`: the latter is also a
        # base-learner hyperparameter and silently swallowing it here would give
        # the forest's base learners different capacity from every other family.
        super().__init__(*args, **kw)
        # EconML requires the forest size to be divisible by subforest_size (4).
        self.n_trees = int(np.ceil(n_trees / 4) * 4)
        self.cv = cv

    def _fit(self, ctx: FitContext) -> None:
        from econml.dml import CausalForestDML

        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = train["action"].to_numpy(dtype=int)
        self._est = CausalForestDML(
            model_y=ProbaRegressor(kind=self.kind, seed=ctx.seed, **self.model_kw),
            model_t=make_classifier("lightgbm", seed=ctx.seed, n_estimators=200),
            discrete_treatment=True,
            n_estimators=self.n_trees,
            min_samples_leaf=20,
            cv=self.cv,
            random_state=ctx.seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(y, t, X=X)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        n = len(X)
        cate = np.zeros((n, ctx.n_actions))
        lo = np.zeros((n, ctx.n_actions))
        hi = np.zeros((n, ctx.n_actions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for a in range(1, ctx.n_actions):
                cate[:, a] = np.asarray(self._est.effect(X, T0=0, T1=a)).ravel()
                try:
                    l, h = self._est.effect_interval(X, T0=0, T1=a, alpha=0.2)
                    lo[:, a] = np.asarray(l).ravel()
                    hi[:, a] = np.asarray(h).ravel()
                except Exception:
                    lo[:, a] = hi[:, a] = cate[:, a]
        est = self._assemble(ctx, p0, cate)
        # Turn the 80% CATE interval into EV draws so uncertainty-aware policies
        # can consume it on the same footing as a posterior.
        sd = np.maximum((hi - lo) / (2 * 1.2816), 1e-9)
        rng = np.random.default_rng(ctx.seed)
        draws = rng.normal(
            cate[None, :, :], sd[None, :, :], size=(64, n, ctx.n_actions)
        )
        draws[:, :, 0] = 0.0
        value, minutes, cost = self._nuisance_matrices(ctx)
        p_draws = np.clip(p0[None, :, None] + draws, 0.0, 1.0)
        est.ev_samples = p_draws * value[None, :, None] - cost[None, :, :]
        return est


class ClassTransformation(_CausalBase):
    """scikit-uplift ``ClassTransformation`` (Jaskowski/Lai revert-label).

    Binary treatment only, and it assumes a 50/50 split; it is included because
    it is the method most uplift tutorials reach for first, and it is useful to
    see how it behaves when those assumptions are only approximately true.
    """

    def _fit(self, ctx: FitContext) -> None:
        from sklift.models import ClassTransformation as _CT

        if ctx.n_actions != 2:
            raise ValueError("ClassTransformation supports binary treatment only")
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_baseline(ctx, train)
        X = self._design(train)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        t = (train["action"].to_numpy(dtype=int) > 0).astype(int)
        self._est = _CT(estimator=make_classifier(self.kind, seed=ctx.seed, **self.model_kw))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._est.fit(X, y, t)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        X = self._design(ctx.df)
        p0 = self._p_control(ctx)
        cate = np.zeros((len(X), ctx.n_actions))
        cate[:, 1] = self._est.predict(X)
        return self._assemble(ctx, p0, cate)


def _final_regressor(seed: int):
    """Final-stage CATE regressor. Deliberately low-variance."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(
        max_iter=200, learning_rate=0.05, max_depth=4, random_state=seed
    )
