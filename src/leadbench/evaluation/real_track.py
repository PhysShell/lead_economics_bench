"""Benchmark track for real randomized experiments (Hillstrom, Criteo).

There is no Oracle here and there never can be: individual treatment effects
are not observable, so this track reports *estimated* policy value with
confidence intervals, not regret. Because both datasets are genuine randomized
experiments with known assignment probabilities, IPS / SNIPS / DR are
identified; the propensity is a design constant rather than something we fit.

The decision framing is a send budget: you may treat at most ``budget`` of the
population. That is what makes the problem an allocation problem rather than a
"treat everyone, e-mail is free" non-problem, and it is the same shape as the
agent-capacity constraint in the synthetic track.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.base import clone

from ..data.real import RealDataset
from ..features.encoding import TabularEncoder
from ..metrics.causal import uplift_summary
from ..metrics.ope import evaluate_policy_ope
from ..metrics.predictive import predictive_summary
from ..models.propensity import make_classifier
from ..models.uplift import ProbaRegressor


@dataclass
class RealSpec:
    """Preregistered economics and budget for a real-data cell."""

    name: str
    dataset: str
    outcome: str = "visit"
    arms: str = "any_email"
    n_rows: int | None = None
    #: Dollar value of one incremental outcome. A benchmark convention, fixed
    #: before looking at test results; results are reported per unit value too.
    value_per_outcome: float = 1.0
    #: Cost of treating one user, as a fraction of value_per_outcome.
    cost_per_treatment: float = 0.01
    #: Share of the population the policy may treat.
    budgets: tuple[float, ...] = (0.10, 0.25, 0.50)
    train_frac: float = 0.5
    seeds: tuple[int, ...] = (0, 1, 2)
    n_boot: int = 300


# ---------------------------------------------------------------------------
# Lightweight candidates for the real track
# ---------------------------------------------------------------------------


class RealCandidate:
    name = "candidate"
    family = "unspecified"
    is_causal = False

    def fit(self, X, t, y, seed: int) -> "RealCandidate":
        return self

    def uplift(self, X) -> np.ndarray:
        raise NotImplementedError

    def outcome_by_arm(self, X) -> np.ndarray:
        """(n, 2) predicted outcome probability under control and treatment."""
        raise NotImplementedError


class RandomCandidate(RealCandidate):
    name, family = "random", "naive"

    def fit(self, X, t, y, seed):
        self.rng = np.random.default_rng(seed + 77)
        self._rate = float(np.mean(y))
        return self

    def uplift(self, X):
        return self.rng.random(len(X))

    def outcome_by_arm(self, X):
        return np.full((len(X), 2), self._rate)


class ResponseRanker(RealCandidate):
    """Ordinary lead scoring: rank by P(outcome | X), treatment ignored."""

    name, family = "response_score", "propensity"

    def __init__(self, kind="lightgbm", **kw):
        self.kind, self.kw = kind, kw

    def fit(self, X, t, y, seed):
        self.clf = make_classifier(self.kind, seed=seed, **self.kw)
        self.clf.fit(X, y)
        return self

    def uplift(self, X):
        return self.clf.predict_proba(X)[:, 1]

    def outcome_by_arm(self, X):
        p = self.clf.predict_proba(X)[:, 1]
        return np.column_stack([p, p])


class TwoModel(RealCandidate):
    """T-learner: a separate outcome model per arm."""

    name, family, is_causal = "t_learner", "causal", True

    def __init__(self, kind="lightgbm", **kw):
        self.kind, self.kw = kind, kw

    def fit(self, X, t, y, seed):
        self.m = []
        for a in (0, 1):
            mask = t == a
            mdl = ProbaRegressor(kind=self.kind, seed=seed, **self.kw)
            mdl.fit(X[mask], y[mask])
            self.m.append(mdl)
        return self

    def outcome_by_arm(self, X):
        return np.clip(np.column_stack([self.m[0].predict(X), self.m[1].predict(X)]), 0, 1)

    def uplift(self, X):
        q = self.outcome_by_arm(X)
        return q[:, 1] - q[:, 0]


class SingleModel(RealCandidate):
    """S-learner: one model with treatment as a feature."""

    name, family, is_causal = "s_learner", "causal", True

    def __init__(self, kind="lightgbm", **kw):
        self.kind, self.kw = kind, kw

    def fit(self, X, t, y, seed):
        self.mdl = ProbaRegressor(kind=self.kind, seed=seed, **self.kw)
        self.mdl.fit(np.column_stack([X, t]), y)
        return self

    def outcome_by_arm(self, X):
        z = np.zeros(len(X))
        q0 = self.mdl.predict(np.column_stack([X, z]))
        q1 = self.mdl.predict(np.column_stack([X, z + 1]))
        return np.clip(np.column_stack([q0, q1]), 0, 1)

    def uplift(self, X):
        q = self.outcome_by_arm(X)
        return q[:, 1] - q[:, 0]


class EconMLCandidate(RealCandidate):
    """X-learner, DR-learner or causal forest from EconML."""

    family, is_causal = "causal", True

    def __init__(self, which: str, kind="lightgbm", **kw):
        self.which, self.kind, self.kw = which, kind, kw
        self.name = which
        self._fallback = TwoModel(kind=kind, **kw)

    def fit(self, X, t, y, seed):
        self._fallback.fit(X, t, y, seed)
        base = ProbaRegressor(kind=self.kind, seed=seed, **self.kw)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.which == "x_learner":
                from econml.metalearners import XLearner

                from sklearn.ensemble import HistGradientBoostingRegressor

                self.est = XLearner(
                    models=[clone(base), clone(base)],
                    # cate_models regress a continuous pseudo-effect: genuine
                    # regressors, not the probability-classifier wrapper.
                    cate_models=[
                        HistGradientBoostingRegressor(
                            max_iter=200, max_depth=4, random_state=seed + i
                        )
                        for i in range(2)
                    ],
                    propensity_model=make_classifier("logistic", seed=seed),
                )
                self.est.fit(y, t, X=X)
            elif self.which == "dr_learner":
                from econml.dr import DRLearner
                from sklearn.ensemble import HistGradientBoostingRegressor

                self.est = DRLearner(
                    model_propensity=make_classifier("logistic", seed=seed),
                    model_regression=clone(base),
                    model_final=HistGradientBoostingRegressor(
                        max_iter=200, max_depth=4, random_state=seed
                    ),
                    cv=3,
                    random_state=seed,
                )
                self.est.fit(y, t, X=X)
            elif self.which == "causal_forest":
                from econml.dml import CausalForestDML

                self.est = CausalForestDML(
                    model_y=clone(base),
                    model_t=make_classifier("logistic", seed=seed),
                    discrete_treatment=True,
                    n_estimators=300,
                    min_samples_leaf=50,
                    cv=3,
                    random_state=seed,
                )
                self.est.fit(y, t, X=X)
            else:
                raise ValueError(self.which)
        return self

    def uplift(self, X):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.asarray(self.est.effect(X)).ravel()

    def outcome_by_arm(self, X):
        """Baseline from the T-learner control model, plus the estimated effect."""
        q0 = self._fallback.outcome_by_arm(X)[:, 0]
        return np.clip(np.column_stack([q0, q0 + self.uplift(X)]), 0, 1)


class ClassTransformCandidate(RealCandidate):
    name, family, is_causal = "class_transformation", "causal", True

    def __init__(self, kind="lightgbm", **kw):
        self.kind, self.kw = kind, kw
        self._fallback = TwoModel(kind=kind, **kw)

    def fit(self, X, t, y, seed):
        from sklift.models import ClassTransformation

        self._fallback.fit(X, t, y, seed)
        self.est = ClassTransformation(
            estimator=make_classifier(self.kind, seed=seed, **self.kw)
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.est.fit(X, y, t)
        return self

    def uplift(self, X):
        return self.est.predict(X)

    def outcome_by_arm(self, X):
        q0 = self._fallback.outcome_by_arm(X)[:, 0]
        return np.clip(np.column_stack([q0, q0 + self.uplift(X)]), 0, 1)


def default_real_candidates(kind: str = "lightgbm") -> list[Callable[[], RealCandidate]]:
    kw = dict(n_estimators=300, learning_rate=0.05)
    return [
        lambda: RandomCandidate(),
        lambda: ResponseRanker(kind=kind, **kw),
        lambda: SingleModel(kind=kind, **kw),
        lambda: TwoModel(kind=kind, **kw),
        lambda: EconMLCandidate("x_learner", kind=kind, **kw),
        lambda: EconMLCandidate("dr_learner", kind=kind, **kw),
        lambda: EconMLCandidate("causal_forest", kind=kind, **kw),
        lambda: ClassTransformCandidate(kind=kind, **kw),
    ]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _budget_policy(score: np.ndarray, budget: float) -> np.ndarray:
    """Treat the top ``budget`` share by score."""
    n = len(score)
    k = int(np.floor(budget * n))
    a = np.zeros(n, dtype=int)
    if k > 0:
        a[np.argsort(-score, kind="stable")[:k]] = 1
    return a


def run_real_scenario(
    spec: RealSpec,
    dataset: RealDataset,
    candidates: list[Callable[[], RealCandidate]] | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    candidates = candidates or default_real_candidates()
    enc = TabularEncoder.from_columns(
        dataset.feature_columns, dataset.categorical_columns
    ).fit(dataset.df)
    X_all = enc.transform_tree(dataset.df)
    t_all = dataset.treatment
    y_all = dataset.outcome
    p_all = dataset.propensity

    rows: list[dict[str, Any]] = []
    for seed in spec.seeds:
        rng = np.random.default_rng(seed)
        perm = rng.permutation(len(X_all))
        cut = int(spec.train_frac * len(perm))
        tr, te = perm[:cut], perm[cut:]

        Xtr, ttr, ytr = X_all[tr], t_all[tr], y_all[tr]
        Xte, tte, yte = X_all[te], t_all[te], y_all[te]
        pte = p_all[te]
        pmat = np.column_stack([1 - pte, pte])

        V, c = spec.value_per_outcome, spec.cost_per_treatment
        reward = V * yte - c * tte

        for factory in candidates:
            cand = factory()
            try:
                cand.fit(Xtr, ttr, ytr, seed)
                score = cand.uplift(Xte)
                q = cand.outcome_by_arm(Xte)
                q_hat = np.column_stack([V * q[:, 0], V * q[:, 1] - c])
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "scenario": spec.name,
                        "dataset": dataset.name,
                        "seed": seed,
                        "candidate": cand.name,
                        "status": f"error: {type(exc).__name__}: {exc}",
                    }
                )
                if verbose:
                    print(f"  !! {cand.name} failed: {exc}")
                continue

            base = {
                "scenario": spec.name,
                "dataset": dataset.name,
                "outcome": spec.outcome,
                "seed": seed,
                "candidate": cand.name,
                "family": cand.family,
                "is_causal": cand.is_causal,
                "n_train": len(tr),
                "n_test": len(te),
                "status": "ok",
            }
            base.update(
                {f"uplift_{k}": v for k, v in uplift_summary(yte, tte, score).items()}
            )
            base.update(
                {
                    f"pred_{k}": v
                    for k, v in predictive_summary(
                        yte, q[np.arange(len(tte)), tte]
                    ).items()
                }
            )

            for budget in spec.budgets:
                target = _budget_policy(score, budget)
                ope = evaluate_policy_ope(
                    reward=reward,
                    logged_action=tte,
                    target_action=target,
                    propensity=pmat[np.arange(len(tte)), target],
                    propensity_matrix=pmat,
                    q_hat=q_hat,
                    n_boot=spec.n_boot,
                    seed=seed,
                )
                row = dict(base)
                row["budget"] = budget
                row.update(ope)
                row["net_value_per_1k_snips"] = 1000.0 * ope["snips_value"]
                row["net_value_per_1k_dr"] = 1000.0 * ope["dr_value"]
                rows.append(row)
                if verbose:
                    print(
                        f"  {dataset.name} seed={seed} {cand.name:22s} b={budget:.2f} "
                        f"DR/1k={row['net_value_per_1k_dr']:8.2f} "
                        f"[{1000*ope['dr_ci_low']:7.2f},{1000*ope['dr_ci_high']:7.2f}] "
                        f"ESS={ope['dr_ess']:.0f}"
                    )
    return pd.DataFrame(rows)
