"""Hierarchical Bayesian candidate (PyMC).

The point of this model is *not* to be Bayesian. It is to do three specific
things that the gradient-boosted candidates cannot:

1. **Partial pooling on the treatment effect.** Each campaign gets its own
   uplift, shrunk toward the global uplift by an amount the data chooses. This
   is the mechanism RQ6 is about, and it is why the sparse regime exists.
2. **A posterior over EV**, so an uncertainty-aware policy has something real
   to be risk-averse about (RQ5), and so interval coverage can be scored.
3. **Honest behaviour when the data is thin** - wide intervals rather than
   confident nonsense, which is what an abstention policy needs.

Structure (logit scale, outcome = funded):

    eta = mu + b_campaign[c] + b_geo[g] + X @ beta
          + T * (tau + t_campaign[c] + Xh @ gamma)

with non-centred half-normal hierarchies on the campaign and geo effects.
Treatment heterogeneity enters through ``gamma`` on a small set of features,
which keeps the parameter count in the dozens rather than the thousands.
"""

from __future__ import annotations

import time
import warnings
from typing import Any

import numpy as np
import pandas as pd

from .base import ActionValueEstimate, FitContext, PredictContext
from .propensity import _SupervisedBase


class HierarchicalBayesianFunnel(_SupervisedBase):
    """Hierarchical Bayesian logistic outcome model with pooled treatment effects."""

    family = "bayesian"
    allocation_mode = "ev"
    is_causal = True
    has_uncertainty = True

    def __init__(
        self,
        name: str = "bayes_hierarchical",
        draws: int = 400,
        tune: int = 400,
        chains: int = 2,
        target_accept: float = 0.9,
        use_hierarchy: bool = True,
        n_het_features: int = 6,
        max_rows: int = 30_000,
        sampler: str = "auto",
        posterior_draws: int = 200,
        **kw: Any,
    ) -> None:
        kw.setdefault("kind", "logistic")
        super().__init__(name, **kw)
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.target_accept = target_accept
        self.use_hierarchy = use_hierarchy
        self.n_het_features = n_het_features
        self.max_rows = max_rows
        self.sampler = sampler
        self.posterior_draws = posterior_draws
        self._idata = None
        self._sampler_used = "none"

    # -- design ------------------------------------------------------------
    def _numeric_matrix(self, df: pd.DataFrame) -> np.ndarray:
        cols = [c for c in self._num_cols]
        X = df[cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        X = np.where(np.isnan(X), self._num_median[None, :], X)
        return (X - self._num_mean[None, :]) / self._num_sd[None, :]

    def _index(self, df: pd.DataFrame, col: str) -> np.ndarray:
        cats = self._cats[col]
        idx = cats.get_indexer(df[col].astype("object"))
        # Unseen levels fall back to the pooled mean, i.e. the extra index.
        return np.where(idx < 0, len(cats), idx).astype(int)

    def _fit(self, ctx: FitContext) -> None:
        import pymc as pm

        train = ctx.clean()
        if len(train) > self.max_rows:
            train = train.sample(self.max_rows, random_state=ctx.seed)
        self._fit_nuisance(ctx, train)

        self._num_cols = [
            c
            for c in ctx.feature_columns
            if c not in set(ctx.categorical_columns) and c != "hour_of_day"
        ]
        raw = train[self._num_cols].apply(pd.to_numeric, errors="coerce")
        self._num_median = raw.median().to_numpy(dtype=float)
        self._num_mean = raw.mean().to_numpy(dtype=float)
        sd = raw.std().to_numpy(dtype=float)
        self._num_sd = np.where(sd > 1e-9, sd, 1.0)

        self._cats = {
            c: pd.Index(pd.unique(train[c].astype("object").dropna()))
            for c in ("campaign_id", "geo_id")
        }

        X = self._numeric_matrix(train)
        Xh = X[:, : min(self.n_het_features, X.shape[1])]
        camp = self._index(train, "campaign_id")
        geo = self._index(train, "geo_id")
        T = (train["action"].to_numpy(dtype=int) > 0).astype(float)
        y = train[ctx.outcome_column].to_numpy(dtype=int)

        n_camp = len(self._cats["campaign_id"]) + 1
        n_geo = len(self._cats["geo_id"]) + 1

        with pm.Model() as model:
            mu = pm.Normal("mu", 0.0, 2.5)
            beta = pm.Normal("beta", 0.0, 1.0, shape=X.shape[1])
            tau = pm.Normal("tau", 0.0, 1.0)
            gamma = pm.Normal("gamma", 0.0, 0.5, shape=Xh.shape[1])

            if self.use_hierarchy:
                # Non-centred parameterisation: better geometry, fewer divergences.
                sd_c = pm.HalfNormal("sd_campaign", 0.5)
                z_c = pm.Normal("z_campaign", 0.0, 1.0, shape=n_camp)
                b_camp = pm.Deterministic("b_campaign", z_c * sd_c)

                sd_g = pm.HalfNormal("sd_geo", 0.5)
                z_g = pm.Normal("z_geo", 0.0, 1.0, shape=n_geo)
                b_geo = pm.Deterministic("b_geo", z_g * sd_g)

                # The bit that matters: campaign-level uplift, pooled.
                sd_tc = pm.HalfNormal("sd_tau_campaign", 0.4)
                z_tc = pm.Normal("z_tau_campaign", 0.0, 1.0, shape=n_camp)
                t_camp = pm.Deterministic("tau_campaign", z_tc * sd_tc)
            else:
                b_camp = np.zeros(n_camp)
                b_geo = np.zeros(n_geo)
                t_camp = np.zeros(n_camp)

            eta = (
                mu
                + b_camp[camp]
                + b_geo[geo]
                + pm.math.dot(X, beta)
                + T * (tau + t_camp[camp] + pm.math.dot(Xh, gamma))
            )
            pm.Bernoulli("y", logit_p=eta, observed=y)

            self._idata = self._sample(pm, model, ctx.seed, len(train))

        self._model_shapes = (X.shape[1], Xh.shape[1], n_camp, n_geo)

    def _sample(self, pm, model, seed: int, n_rows: int):
        """NUTS when it is affordable, ADVI when it is not. Record which."""
        want = self.sampler
        if want == "auto":
            want = "nuts" if n_rows <= 20_000 else "advi"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if want == "nuts":
                t0 = time.perf_counter()
                idata = pm.sample(
                    draws=self.draws,
                    tune=self.tune,
                    chains=self.chains,
                    cores=min(self.chains, 2),
                    target_accept=self.target_accept,
                    random_seed=seed,
                    progressbar=False,
                    compute_convergence_checks=False,
                )
                self._sampler_used = "nuts"
                self._sample_seconds = time.perf_counter() - t0
                return idata
            approx = pm.fit(
                n=30_000,
                method="advi",
                random_seed=seed,
                progressbar=False,
            )
            self._sampler_used = "advi"
            return approx.sample(self.posterior_draws)

    # -- prediction ---------------------------------------------------------
    def _posterior_matrix(self, name: str) -> np.ndarray:
        post = self._idata.posterior[name]
        return post.stack(sample=("chain", "draw")).transpose("sample", ...).to_numpy()

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        df = ctx.df
        X = self._numeric_matrix(df)
        Xh = X[:, : self._model_shapes[1]]
        camp = self._index(df, "campaign_id")
        geo = self._index(df, "geo_id")

        mu = self._posterior_matrix("mu")
        beta = self._posterior_matrix("beta")
        tau = self._posterior_matrix("tau")
        gamma = self._posterior_matrix("gamma")
        S = len(mu)
        keep = np.linspace(0, S - 1, min(self.posterior_draws, S)).astype(int)

        base = mu[keep, None] + beta[keep] @ X.T
        if self.use_hierarchy:
            b_camp = self._posterior_matrix("b_campaign")[keep]
            b_geo = self._posterior_matrix("b_geo")[keep]
            t_camp = self._posterior_matrix("tau_campaign")[keep]
            base = base + b_camp[:, camp] + b_geo[:, geo]
            delta = tau[keep, None] + t_camp[:, camp] + gamma[keep] @ Xh.T
        else:
            delta = tau[keep, None] + gamma[keep] @ Xh.T

        p0 = _sigmoid(base)
        p1 = _sigmoid(base + delta)

        value, minutes, cost = self._nuisance_matrices(ctx)
        n, A = len(df), ctx.n_actions
        p_draws = np.zeros((len(keep), n, A))
        p_draws[:, :, 0] = p0
        for a in range(1, A):
            p_draws[:, :, a] = p1
        ev_draws = p_draws * value[None, :, None] - cost[None, :, :]

        p_mean = p_draws.mean(axis=0)
        ev_mean = ev_draws.mean(axis=0)
        return ActionValueEstimate(
            ev=ev_mean,
            minutes=minutes,
            p_outcome=p_mean,
            cate=p_mean - p_mean[:, [0]],
            ev_samples=ev_draws,
            p_samples=p_draws,
            score=ev_mean[:, ctx.call_action] - ev_mean[:, 0],
            value_per_conversion=value,
            diagnostics={"sampler": self._sampler_used},
        )


class PooledBayesianFunnel(HierarchicalBayesianFunnel):
    """Ablation: the same model with the hierarchy switched off (RQ6)."""

    def __init__(self, name: str = "bayes_no_hierarchy", **kw: Any) -> None:
        kw["use_hierarchy"] = False
        super().__init__(name, **kw)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -35, 35)))
