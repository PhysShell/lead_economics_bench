"""Standardised model and policy interfaces.

The separation this module enforces:

    model  -> ActionValueEstimate  (beliefs: probabilities, effects, dollars)
    policy -> actions              (decisions, subject to constraints)

A model never sees ground truth. :class:`FitContext` and :class:`PredictContext`
carry the *observed* frame only; the Oracle is the single, explicit exception
and it subclasses :class:`TruthAwareCandidate` so the exception is greppable.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..economics import Economics
from ..features.encoding import TabularEncoder


@dataclass
class FitContext:
    """Everything a candidate may learn from. Observed data only."""

    df: pd.DataFrame
    feature_columns: list[str]
    categorical_columns: list[str]
    economics: Economics
    action_names: tuple[str, ...]
    seed: int = 0
    outcome_column: str = "funded"
    # Set when the fold's outcomes are partially censored.
    drop_censored: bool = True

    @property
    def n_actions(self) -> int:
        return len(self.action_names)

    @property
    def call_action(self) -> int:
        return len(self.action_names) - 1

    def clean(self) -> pd.DataFrame:
        """Rows usable for supervised learning (resolved outcome)."""
        df = self.df
        if self.drop_censored and "censored" in df.columns:
            df = df[~df["censored"].astype(bool)]
        return df[df[self.outcome_column].notna()]


@dataclass
class PredictContext:
    df: pd.DataFrame
    feature_columns: list[str]
    categorical_columns: list[str]
    economics: Economics
    action_names: tuple[str, ...]
    seed: int = 0

    @property
    def n_actions(self) -> int:
        return len(self.action_names)

    @property
    def call_action(self) -> int:
        return len(self.action_names) - 1


@dataclass
class ActionValueEstimate:
    """A candidate's beliefs about every (lead, action) pair.

    ``ev`` is always in dollars and always includes the control column, so
    policies can compare "do nothing" against "spend agent time" on one scale.
    """

    ev: np.ndarray  # (n, A) expected net value
    minutes: np.ndarray  # (n, A) expected agent minutes
    p_outcome: np.ndarray | None = None  # (n, A)
    cate: np.ndarray | None = None  # (n, A) uplift vs control, probability scale
    ev_samples: np.ndarray | None = None  # (S, n, A) posterior / bootstrap draws
    # (S, n, A) draws of the outcome probability. Scored separately from EV so
    # that a badly covered EV interval can be attributed either to the outcome
    # model or to the point-estimated value/effort nuisances feeding it.
    p_samples: np.ndarray | None = None
    direct_cost: np.ndarray | None = None  # (n, A)
    score: np.ndarray | None = None  # (n,) ranking score for rank-mode policies
    value_per_conversion: np.ndarray | None = None  # (n,)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ev = np.asarray(self.ev, dtype=float)
        self.minutes = np.asarray(self.minutes, dtype=float)
        if self.ev.shape != self.minutes.shape:
            raise ValueError("ev and minutes must share shape (n, A)")
        if not np.isfinite(self.ev).all():
            raise ValueError("ev contains non-finite values")

    @property
    def n(self) -> int:
        return self.ev.shape[0]

    @property
    def n_actions(self) -> int:
        return self.ev.shape[1]

    def ev_lower_bound(self, q: float = 0.10) -> np.ndarray | None:
        if self.ev_samples is None:
            return None
        return np.quantile(self.ev_samples, q, axis=0)

    def ev_upper_bound(self, q: float = 0.90) -> np.ndarray | None:
        if self.ev_samples is None:
            return None
        return np.quantile(self.ev_samples, q, axis=0)


class Candidate(abc.ABC):
    """A model under test."""

    family: str = "unspecified"
    #: "ev" -> value-aware constrained allocation; "rank" -> call-list policy.
    allocation_mode: str = "ev"
    #: Whether this candidate estimates causal effects at all.
    is_causal: bool = False
    #: Whether it produces calibrated uncertainty.
    has_uncertainty: bool = False

    def __init__(self, name: str) -> None:
        self.name = name
        self.fit_seconds: float = float("nan")
        self.predict_seconds: float = float("nan")
        self._encoder: TabularEncoder | None = None

    # -- lifecycle ---------------------------------------------------------
    @abc.abstractmethod
    def _fit(self, ctx: FitContext) -> None: ...

    @abc.abstractmethod
    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate: ...

    def fit(self, ctx: FitContext) -> "Candidate":
        t0 = time.perf_counter()
        self._fit(ctx)
        self.fit_seconds = time.perf_counter() - t0
        return self

    def estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        t0 = time.perf_counter()
        est = self._estimate(ctx)
        self.predict_seconds = time.perf_counter() - t0
        return est

    # -- helpers -----------------------------------------------------------
    def encoder(self, ctx: FitContext) -> TabularEncoder:
        if self._encoder is None:
            self._encoder = TabularEncoder.from_columns(
                ctx.feature_columns, ctx.categorical_columns
            ).fit(ctx.df)
        return self._encoder

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "allocation_mode": self.allocation_mode,
            "is_causal": self.is_causal,
            "has_uncertainty": self.has_uncertainty,
        }


class TruthAwareCandidate(Candidate):
    """Base class for candidates that are *allowed* to see ground truth.

    Exactly one production candidate should ever inherit from this: the Oracle.
    """

    family = "oracle"

    def set_truth(self, truth: pd.DataFrame) -> None:
        self._truth = truth


# ---------------------------------------------------------------------------
# Shared nuisance components: deal value and agent effort.
# Every economic candidate uses the same ones so that differences in the
# leaderboard come from the outcome/causal model, not from a better margin
# regression.
# ---------------------------------------------------------------------------


class ValueModel:
    """E[net contribution | funded, X].

    ``mode='global'`` is the "no margin variation" ablation: one average deal
    for everybody, which is what most lead-scoring products implicitly assume.
    """

    def __init__(self, mode: str = "model", seed: int = 0,
                 shrink: float = 1.0) -> None:
        self.mode = mode
        self.seed = seed
        #: Weight on the per-lead prediction, 0 = global mean for everybody.
        #: The ablation found that removing the value model entirely *improved*
        #: `capacity_value_heterogeneity` (50.8 -> 61.7% of Oracle), because a
        #: per-lead margin multiplies whatever error is in the response
        #: estimate and multiplies it hardest on exactly the big-ticket leads
        #: that dominate the objective. Shrinking toward the mean is the
        #: obvious middle ground and `shrink` is how it gets measured.
        self.shrink = float(shrink)
        self._global = 0.0
        self._model = None

    def fit(self, df: pd.DataFrame, X: np.ndarray) -> "ValueModel":
        funded = (df["funded"] == 1).to_numpy()
        vals = df["realized_net_contribution"].to_numpy(dtype=float)
        ok = funded & np.isfinite(vals)
        self._global = float(vals[ok].mean()) if ok.sum() > 0 else 0.0
        if self.mode == "model" and ok.sum() >= 200:
            from sklearn.ensemble import HistGradientBoostingRegressor

            m = HistGradientBoostingRegressor(
                max_iter=150, learning_rate=0.08, random_state=self.seed
            )
            m.fit(X[ok], vals[ok])
            self._model = m
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None or self.shrink <= 0.0:
            return np.full(len(X), self._global)
        pred = self._model.predict(X)
        if self.shrink >= 1.0:
            return pred
        return self.shrink * pred + (1.0 - self.shrink) * self._global


class EffortModel:
    """E[agent minutes | action, X], learned from the logged effort."""

    def __init__(self, mode: str = "model", seed: int = 0) -> None:
        self.mode = mode
        self.seed = seed
        self._global_call = 8.0
        self._sms_minutes = 0.25
        self._model = None

    def fit(self, df: pd.DataFrame, X: np.ndarray, call_action: int) -> "EffortModel":
        called = (df["action"] == call_action).to_numpy()
        mins = df["minutes_spent"].to_numpy(dtype=float)
        ok = called & np.isfinite(mins) & (mins > 0)
        if ok.sum() > 0:
            self._global_call = float(mins[ok].mean())
        if self.mode == "model" and ok.sum() >= 200:
            from sklearn.ensemble import HistGradientBoostingRegressor

            m = HistGradientBoostingRegressor(
                max_iter=150, learning_rate=0.08, random_state=self.seed
            )
            m.fit(X[ok], mins[ok])
            self._model = m
        return self

    def predict_matrix(self, X: np.ndarray, n_actions: int, econ: Economics) -> np.ndarray:
        """Predicted agent minutes per action. Last index is always the call."""
        n = len(X)
        out = np.zeros((n, n_actions))
        if n_actions >= 3:
            out[:, 1] = econ.sms_minutes
        if n_actions >= 2:
            call = (
                self._model.predict(X)
                if self._model is not None
                else np.full(n, self._global_call)
            )
            out[:, -1] = np.clip(call, 0.5, 120.0)
        return out
