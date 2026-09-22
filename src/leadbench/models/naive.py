"""Baselines: what you can already do with end-to-end analytics, plus the Oracle.

These are written to be *strong*, not to be beaten. Segment statistics are
empirical-Bayes shrunk toward the global mean, which is what any competent
analytics team does and which makes these baselines considerably harder to
beat in sparse regimes than the raw-rate versions most papers use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..economics import Economics
from .base import (
    ActionValueEstimate,
    Candidate,
    EffortModel,
    FitContext,
    PredictContext,
    TruthAwareCandidate,
    ValueModel,
)

# Prior weight (in pseudo-leads) for shrinking segment statistics.
SHRINK_PRIOR = 50.0


def _shrunk_mean(
    df: pd.DataFrame, by: str, col: str, prior_weight: float = SHRINK_PRIOR
) -> pd.Series:
    """Empirical-Bayes shrinkage of a per-segment mean toward the global mean."""
    g = df.groupby(by, observed=True)[col].agg(["sum", "count"])
    global_mean = float(df[col].mean()) if len(df) else 0.0
    return (g["sum"] + prior_weight * global_mean) / (g["count"] + prior_weight)


class _RankBaseline(Candidate):
    """Shared machinery: build a per-lead ranking score from segment stats."""

    family = "naive"
    allocation_mode = "rank"

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._effort = EffortModel(mode="global")
        self._lookup: pd.Series | None = None
        self._lookup_key = "campaign_id"
        self._default = 0.0
        self._fallback_action = 0
        self._segment_minutes: pd.Series | None = None
        self._global_minutes = 8.0
        self._value = 0.0

    def _segment_stats(self, ctx: FitContext) -> pd.DataFrame:
        return ctx.clean()

    def _fit(self, ctx: FitContext) -> None:
        enc = self.encoder(ctx)
        train = ctx.clean()
        X = enc.transform_tree(train)
        self._effort.fit(train, X, call_action=ctx.call_action)
        self._global_minutes = self._effort._global_call
        self._value = ValueModel(mode="global").fit(train, X)._global

        called = train[train["action"] == ctx.call_action]
        if len(called):
            self._segment_minutes = called.groupby("campaign_id", observed=True)[
                "minutes_spent"
            ].mean()

        self._fallback_action = _sms_fallback(train, ctx)
        self._build_lookup(train, ctx)

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        raise NotImplementedError

    def _score(self, df: pd.DataFrame) -> np.ndarray:
        assert self._lookup is not None
        return (
            df[self._lookup_key]
            .map(self._lookup)
            .fillna(self._default)
            .to_numpy(dtype=float)
        )

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        n = len(ctx.df)
        score = self._score(ctx.df)
        minutes = np.zeros((n, ctx.n_actions))
        if ctx.n_actions >= 3:
            minutes[:, 1] = ctx.economics.sms_minutes
        if ctx.n_actions >= 2:
            # Campaign-level average handle time: what a CRM report can give
            # you without any per-lead modelling.
            if self._segment_minutes is not None:
                minutes[:, -1] = (
                    ctx.df["campaign_id"]
                    .map(self._segment_minutes)
                    .fillna(self._global_minutes)
                    .to_numpy(dtype=float)
                )
            else:
                minutes[:, -1] = self._global_minutes
        # Rank-mode candidates do not produce a dollar EV surface; the score is
        # what drives the call list. We still emit a coherent EV so that the
        # leaderboard can show what their implied economics look like.
        ev = np.zeros((n, ctx.n_actions))
        ev[:, :] = score[:, None]
        ev -= ctx.economics.action_cost(minutes)
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            score=score,
            diagnostics={"fallback_action": self._fallback_action},
        )

    @property
    def fallback_action(self) -> int:
        return self._fallback_action


def _sms_fallback(train: pd.DataFrame, ctx: FitContext) -> int:
    """Global A/B readout: is a blanket SMS worth it for the leads we do not call?

    Honest under randomized logging; deliberately naive (and therefore biased)
    under confounded logging, which is itself a result worth recording.
    """
    if "sms" not in ctx.action_names:
        return 0
    econ = ctx.economics
    margin = ValueModel(mode="global").fit(train, np.zeros((len(train), 1)))._global
    rate = {}
    for a in (0, 1):
        sub = train[train["action"] == a]
        rate[a] = float(sub["funded"].mean()) if len(sub) > 30 else np.nan
    if not np.isfinite(rate.get(1, np.nan)) or not np.isfinite(rate.get(0, np.nan)):
        return 0
    ev_none = rate[0] * margin
    ev_sms = rate[1] * margin - econ.sms_direct_cost - econ.sms_minutes * econ.cost_per_minute
    return 1 if ev_sms > ev_none else 0


# ---------------------------------------------------------------------------
# Concrete baselines
# ---------------------------------------------------------------------------


class RandomPolicy(_RankBaseline):
    def __init__(self) -> None:
        super().__init__("random")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        self._seed = ctx.seed

    def _score(self, df: pd.DataFrame) -> np.ndarray:
        rng = np.random.default_rng(self._seed + 9_999)
        return rng.random(len(df))


class FIFOPolicy(_RankBaseline):
    """Work the list in arrival order. The default in most sales floors."""

    def __init__(self) -> None:
        super().__init__("fifo")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        pass

    def _score(self, df: pd.DataFrame) -> np.ndarray:
        return -df["created_day"].to_numpy(dtype=float)


class LowestCPLPolicy(_RankBaseline):
    """Prefer leads from the cheapest source. Pure measurement-layer thinking."""

    def __init__(self) -> None:
        super().__init__("lowest_cpl")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        pass

    def _score(self, df: pd.DataFrame) -> np.ndarray:
        return -df["cpl"].to_numpy(dtype=float)


class HistoricalConversionPolicy(_RankBaseline):
    """Rank by the campaign's historical conversion rate."""

    def __init__(self) -> None:
        super().__init__("hist_conversion_rate")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        self._lookup = _shrunk_mean(train, "campaign_id", "funded")
        self._default = float(train["funded"].mean())


class HistoricalROASPolicy(_RankBaseline):
    """Rank by campaign ROAS = gross revenue / media spend."""

    def __init__(self) -> None:
        super().__init__("hist_roas")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        rev = _shrunk_mean(train, "campaign_id", "realized_gross_value")
        spend = train.groupby("campaign_id", observed=True)["cpl"].mean()
        self._lookup = (rev / spend.clip(lower=1e-6)).replace([np.inf, -np.inf], 0.0)
        self._default = float(self._lookup.median()) if len(self._lookup) else 0.0


class HistoricalNetProfitPolicy(_RankBaseline):
    """Rank by campaign net profit per lead: revenue - media - servicing."""

    def __init__(self) -> None:
        super().__init__("hist_net_profit")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        t = train.copy()
        t["_net"] = (
            t["realized_net_contribution"].fillna(0.0)
            - t["cpl"]
            - t["action_direct_cost"]
            - t["minutes_spent"] * ctx.economics.cost_per_minute
        )
        self._lookup = _shrunk_mean(t, "campaign_id", "_net")
        self._default = float(t["_net"].mean())


class HistoricalProfitPerAgentHourPolicy(_RankBaseline):
    """Rank by campaign net profit per agent-minute.

    This is the strongest purely-analytical baseline for the capacity question
    and the one RQ4 has to beat.
    """

    def __init__(self) -> None:
        super().__init__("hist_profit_per_agent_hour")

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        t = train.copy()
        t["_net"] = (
            t["realized_net_contribution"].fillna(0.0)
            - t["cpl"]
            - t["action_direct_cost"]
            - t["minutes_spent"] * ctx.economics.cost_per_minute
        )
        net = _shrunk_mean(t, "campaign_id", "_net")
        called = t[t["action"] == ctx.n_actions - 1]
        mins = called.groupby("campaign_id", observed=True)["minutes_spent"].mean()
        mins = mins.reindex(net.index).fillna(self._global_minutes).clip(lower=0.5)
        self._lookup = net / mins
        self._default = float(self._lookup.median()) if len(self._lookup) else 0.0


class LastClickAttributionPolicy(_RankBaseline):
    """Rank by last-touch channel profitability. The attribution trap."""

    def __init__(self) -> None:
        super().__init__("last_click_attribution")
        self._lookup_key = "attributed_channel"

    def _build_lookup(self, train: pd.DataFrame, ctx: FitContext) -> None:
        t = train.copy()
        t["_net"] = t["realized_net_contribution"].fillna(0.0) - t["cpl"]
        self._lookup = _shrunk_mean(t, "attributed_channel", "_net")
        self._default = float(t["_net"].mean())


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


class Oracle(TruthAwareCandidate):
    """Knows the true probabilities, the true expected value and the true effort.

    It is *not* clairvoyant: it does not see the realized uniform draws, the
    realized refund or the realized deal-value noise. It is the best policy
    measurable with respect to the lead, which is the right ceiling for a
    decision system.
    """

    allocation_mode = "ev"
    is_causal = True

    def __init__(self, name: str = "oracle") -> None:
        super().__init__(name)
        self._truth: pd.DataFrame | None = None

    def _fit(self, ctx: FitContext) -> None:
        return None

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        if self._truth is None:
            raise RuntimeError("Oracle.set_truth must be called before estimating")
        t = self._truth
        A = ctx.n_actions
        ev = np.column_stack([t[f"ev_a{a}"].to_numpy() for a in range(A)])
        minutes = np.column_stack([t[f"minutes_a{a}"].to_numpy() for a in range(A)])
        p = np.column_stack([t[f"p_funded_a{a}"].to_numpy() for a in range(A)])
        cate = p - p[:, [0]]
        return ActionValueEstimate(
            ev=ev,
            minutes=minutes,
            p_outcome=p,
            cate=cate,
            value_per_conversion=t["expected_net_contribution"].to_numpy(),
        )


class ControlOnly(Candidate):
    """Do nothing to anybody. The floor for the incremental-value metric."""

    family = "naive"
    allocation_mode = "fixed"

    def __init__(self) -> None:
        super().__init__("do_nothing")

    def _fit(self, ctx: FitContext) -> None:
        return None

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        n, A = len(ctx.df), ctx.n_actions
        minutes = np.zeros((n, A))
        if A > 1:
            minutes[:, 1] = ctx.economics.sms_minutes
        ev = np.zeros((n, A))
        ev[:, 0] = 1.0  # always prefer control
        return ActionValueEstimate(ev=ev, minutes=minutes, score=np.zeros(n))


class TreatEveryone(Candidate):
    """Call every single lead. Only feasible when capacity is unlimited.

    Under a binding capacity it degenerates to "work the list in arrival
    order", which is the correct degenerate behaviour rather than a fake one.
    """

    family = "naive"
    allocation_mode = "rank"

    def __init__(self) -> None:
        super().__init__("call_everyone")
        self._effort = EffortModel(mode="global")

    def _fit(self, ctx: FitContext) -> None:
        enc = self.encoder(ctx)
        train = ctx.clean()
        self._effort.fit(train, enc.transform_tree(train), call_action=ctx.n_actions - 1)

    def _estimate(self, ctx: PredictContext) -> ActionValueEstimate:
        n, A = len(ctx.df), ctx.n_actions
        enc = self._encoder
        X = enc.transform_tree(ctx.df) if enc is not None else np.zeros((n, 1))
        minutes = self._effort.predict_matrix(X, A, ctx.economics)
        ev = np.zeros((n, A))
        ev[:, A - 1] = 1.0
        return ActionValueEstimate(ev=ev, minutes=minutes, score=np.ones(n))


NAIVE_BASELINES = [
    RandomPolicy,
    FIFOPolicy,
    LowestCPLPolicy,
    HistoricalConversionPolicy,
    HistoricalROASPolicy,
    HistoricalNetProfitPolicy,
    HistoricalProfitPerAgentHourPolicy,
    LastClickAttributionPolicy,
]
