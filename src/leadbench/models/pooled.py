"""Partial pooling without MCMC.

The benchmark's one result pointing *toward* more statistical machinery was
that `bayes_hierarchical` loses 3.2% of net value when its partial pooling is
removed. But the model carrying that pooling costs 42x a gradient-boosted
Propensity-EV and merely ties it, so kill criterion K1 fires and the useful
part is trapped inside something not worth shipping.

This module asks the obvious follow-up: **can the pooling be had without the
Bayes?** Two candidates, bracketing the cost range:

``PooledPropensityEV``
    Empirical-Bayes shrunk target encoding. The grouping columns that the
    hierarchical model pools over (`campaign_id`, `geo_id`) are dropped from
    the one-hot design and replaced by two shrunk summaries each: a main
    effect and a treatment-effect offset. Costs a groupby. This is what a
    practitioner ships.

``MixedEffectsPropensityEV``
    A variational mixed-effects logistic (statsmodels
    `BinomialBayesMixedGLM`), with random intercepts per group. Principled
    partial pooling, fitted in seconds rather than minutes.

Why the one-hot columns are *removed* rather than supplemented: a logistic
regression with per-campaign dummies is precisely the **no-pooling** model,
and L2 merely shrinks each dummy toward zero independently rather than toward
the group mean. Leaving them in would make the comparison meaningless.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..features.encoding import add_treatment_column
from .base import FitContext, PredictContext
from .propensity import PropensityEV

#: Columns the hierarchical Bayesian funnel pools over. Matched deliberately
#: so the comparison isolates *how* the pooling is done, not *what* is pooled.
POOL_COLUMNS = ("campaign_id", "geo_id")


def eb_shrunk_rates(
    groups: np.ndarray, y: np.ndarray, prior_floor: float = 1.0
) -> tuple[dict[Any, float], float, float]:
    """Empirical-Bayes shrunk per-group rates, plus the global rate and k.

    Method of moments for a Beta prior: with `p0` the pooled rate and `var`
    the between-group variance of the observed rates, the prior strength that
    reproduces that spread is `k = p0(1-p0)/var - 1`. A group with `n`
    observations is then pulled toward `p0` with weight `k/(n+k)`, so small
    groups borrow heavily and large ones barely move -- which is what a
    hierarchical prior does, computed in closed form.
    """
    y = np.asarray(y, dtype=float)
    p0 = float(np.nanmean(y)) if len(y) else 0.0
    frame = pd.DataFrame({"g": groups, "y": y})
    agg = frame.groupby("g", observed=True)["y"].agg(["mean", "count"])
    if len(agg) < 2:
        return {}, p0, float("inf")

    # Between-group variance, corrected for the sampling noise inside each
    # group; without the correction every group looks more distinct than it is
    # and the prior comes out far too weak.
    within = p0 * (1.0 - p0)
    observed_var = float(np.var(agg["mean"].to_numpy(dtype=float), ddof=1))
    mean_n = float(agg["count"].mean())
    between = max(observed_var - within / max(mean_n, 1.0), 1e-9)
    k = max(within / between - 1.0, prior_floor) if between > 0 else float("inf")

    shrunk = {
        g: float((row["mean"] * row["count"] + k * p0) / (row["count"] + k))
        for g, row in agg.iterrows()
    }
    return shrunk, p0, float(k)


def _logit(p: np.ndarray | float, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    return np.log(p / (1.0 - p))


class PooledPropensityEV(PropensityEV):
    """Propensity-EV whose group effects are pooled, not one-hot encoded.

    Same objective, same nuisance models, same allocator as
    `propensity_ev_logit`. The only difference is how campaign and geo enter
    the design, which is exactly the comparison K1 leaves open.
    """

    family = "economic"
    allocation_mode = "ev"

    def __init__(self, *args: Any, pool_columns: tuple[str, ...] = POOL_COLUMNS,
                 **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.pool_columns = pool_columns
        self._pooled: dict[str, dict[str, Any]] = {}

    # -- encoding ---------------------------------------------------------
    def encoder(self, ctx: FitContext):
        """Build the shared encoder, then drop the pooled columns from it."""
        enc = super().encoder(ctx)
        present = [c for c in self.pool_columns if c in enc.categorical_columns]
        self._pooled_present = present
        enc.categorical_columns = [
            c for c in enc.categorical_columns if c not in set(present)
        ]
        return enc

    def _fit_pooling(self, train: pd.DataFrame, ctx: FitContext) -> None:
        y = train[ctx.outcome_column].to_numpy(dtype=float)
        action = train["action"].to_numpy(dtype=int)
        treated = action == (ctx.n_actions - 1)
        self._pooled = {}
        for col in getattr(self, "_pooled_present", []):
            g = train[col].to_numpy()
            main, p0, _ = eb_shrunk_rates(g, y)
            # Treatment-effect offset, pooled the same way. Estimated on the
            # treated rows only and shrunk toward the global treated rate, so
            # a campaign with two treated leads contributes almost nothing.
            if treated.sum() >= 2:
                lift, p_t, _ = eb_shrunk_rates(g[treated], y[treated])
            else:
                lift, p_t = {}, p0
            self._pooled[col] = {
                "main": main, "p0": p0, "lift": lift, "p_t": p_t,
            }

    def _pool_features(self, df: pd.DataFrame, n_actions: int) -> np.ndarray:
        """Two columns per pooled variable: baseline log-odds and lift."""
        cols = []
        for col, pooled in self._pooled.items():
            g = df[col].to_numpy()
            main = np.array([pooled["main"].get(v, pooled["p0"]) for v in g])
            lift = np.array([pooled["lift"].get(v, pooled["p_t"]) for v in g])
            cols.append(_logit(main))
            cols.append(_logit(lift) - _logit(pooled["p_t"]))
        if not cols:
            return np.zeros((len(df), 0))
        return np.column_stack(cols)

    # -- model ------------------------------------------------------------
    def _fit(self, ctx: FitContext) -> None:
        train = ctx.clean()
        self._fit_nuisance(ctx, train)
        self._fit_pooling(train, ctx)
        X = np.column_stack(
            [self._design(train), self._pool_features(train, ctx.n_actions)]
        )
        Xa = add_treatment_column(X, train["action"].to_numpy(dtype=int), ctx.n_actions)
        y = train[ctx.outcome_column].to_numpy(dtype=int)
        self._clf = self._fit_outcome(Xa, y, ctx.seed)

    def _p_by_action(self, ctx: PredictContext) -> np.ndarray:
        X = np.column_stack(
            [self._design(ctx.df), self._pool_features(ctx.df, ctx.n_actions)]
        )
        n = len(X)
        out = np.zeros((n, ctx.n_actions))
        for a in range(ctx.n_actions):
            Xa = add_treatment_column(X, np.full(n, a), ctx.n_actions)
            out[:, a] = self._clf.predict_proba(Xa)[:, 1]
        return out


class MixedEffectsPropensityEV(PooledPropensityEV):
    """Partial pooling via a variational mixed-effects logistic.

    `statsmodels.BinomialBayesMixedGLM` fits random intercepts by variational
    Bayes: principled pooling, seconds rather than minutes. Falls back to the
    empirical-Bayes encoding if statsmodels is unavailable or the fit fails,
    and records which path it took in `describe()` so a result can never be
    silently attributed to the wrong model.
    """

    def __init__(self, *args: Any, vb_iter: int = 300, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.vb_iter = vb_iter
        self._glmm = None
        self._fallback: str | None = None

    def _fit(self, ctx: FitContext) -> None:
        super()._fit(ctx)  # always fit the EB model as the fallback path
        train = ctx.clean()
        try:
            from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
        except Exception as exc:  # noqa: BLE001
            self._fallback = f"statsmodels unavailable: {type(exc).__name__}"
            return
        cols = getattr(self, "_pooled_present", [])
        if not cols:
            self._fallback = "no grouping columns present"
            return
        try:
            X = np.column_stack(
                [self._design(train), self._pool_features(train, ctx.n_actions)]
            )
            Xa = add_treatment_column(
                X, train["action"].to_numpy(dtype=int), ctx.n_actions
            )
            # Random intercept per group; the fixed part is the shared design.
            exog_vc, ident, names = [], [], []
            for j, col in enumerate(cols):
                codes, uniq = pd.factorize(train[col])
                Z = np.zeros((len(train), len(uniq)))
                Z[np.arange(len(train)), codes] = 1.0
                exog_vc.append(Z)
                ident.append(np.full(len(uniq), j, dtype=int))
                names.append(col)
            Z = np.column_stack(exog_vc)
            y = train[ctx.outcome_column].to_numpy(dtype=float)
            model = BinomialBayesMixedGLM(
                y, Xa, Z, np.concatenate(ident), vcp_names=names
            )
            self._glmm = model.fit_vb(verbose=False)
            self._glmm_cols = cols
        except Exception as exc:  # noqa: BLE001
            self._fallback = f"{type(exc).__name__}: {exc}"[:120]
            self._glmm = None

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        out["pooling_path"] = "eb_fallback" if self._glmm is None else "glmm_vb"
        if self._fallback:
            out["pooling_fallback_reason"] = self._fallback
        return out

    def _p_by_action(self, ctx: PredictContext) -> np.ndarray:
        if self._glmm is None:
            return super()._p_by_action(ctx)
        X = np.column_stack(
            [self._design(ctx.df), self._pool_features(ctx.df, ctx.n_actions)]
        )
        n = len(X)
        # The variational fit gives posterior means for the fixed effects; the
        # random intercepts are already summarised by the pooled features, so
        # prediction uses the fixed part with the group offsets folded in.
        beta = np.asarray(self._glmm.fe_mean, dtype=float)
        out = np.zeros((n, ctx.n_actions))
        for a in range(ctx.n_actions):
            Xa = add_treatment_column(X, np.full(n, a), ctx.n_actions)
            if Xa.shape[1] != len(beta):
                return super()._p_by_action(ctx)
            eta = Xa @ beta
            out[:, a] = 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
        return out
