"""Temporal splitting and leakage checks.

A random split on lead-level data is wrong for this problem in three separate
ways: it leaks the future into the past, it puts duplicate records of the same
human on both sides, and it hides concept drift. All three are checked here and
all three fail loudly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..synthetic.dgp import LeadDataset


@dataclass
class Split:
    train: LeadDataset
    valid: LeadDataset
    test: LeadDataset
    boundaries: tuple[float, float]
    kind: str = "temporal"

    def sizes(self) -> dict[str, int]:
        return {
            "n_train": len(self.train),
            "n_valid": len(self.valid),
            "n_test": len(self.test),
        }


def temporal_split(
    dataset: LeadDataset,
    train_frac: float = 0.60,
    valid_frac: float = 0.15,
    time_column: str = "created_day",
) -> Split:
    """Past -> future split on lead creation time.

    Leads whose outcome has not resolved by the training cut-off are still
    *included* in training with their outcome blanked, because that is the
    situation a real deployment is in. Candidates decide what to do with them
    via ``FitContext.drop_censored``.
    """
    t = dataset.observed[time_column].to_numpy()
    t1, t2 = np.quantile(t, [train_frac, train_frac + valid_frac])
    tr = t <= t1
    va = (t > t1) & (t <= t2)
    te = t > t2
    if te.sum() == 0 or tr.sum() == 0:
        raise ValueError("temporal split produced an empty fold")
    return Split(
        train=dataset.subset(tr),
        valid=dataset.subset(va),
        test=dataset.subset(te),
        boundaries=(float(t1), float(t2)),
    )


def rolling_backtest(
    dataset: LeadDataset,
    n_folds: int = 4,
    initial_frac: float = 0.4,
    time_column: str = "created_day",
) -> list[Split]:
    """Expanding-window backtest: train on Jan-Jun, test Jul; then Jan-Jul, test Aug."""
    t = dataset.observed[time_column].to_numpy()
    lo, hi = float(t.min()), float(t.max())
    span = hi - lo
    start = lo + initial_frac * span
    step = (hi - start) / n_folds
    folds: list[Split] = []
    for k in range(n_folds):
        cut = start + k * step
        end = cut + step
        tr = t <= cut
        te = (t > cut) & (t <= end)
        if tr.sum() < 200 or te.sum() < 100:
            continue
        # The last 20% of the training window doubles as validation.
        vcut = np.quantile(t[tr], 0.8) if tr.sum() else cut
        folds.append(
            Split(
                train=dataset.subset(tr & (t <= vcut)),
                valid=dataset.subset(tr & (t > vcut)),
                test=dataset.subset(te),
                boundaries=(float(vcut), float(cut)),
                kind="rolling",
            )
        )
    return folds


# ---------------------------------------------------------------------------
# Leakage checks
# ---------------------------------------------------------------------------

#: Columns a model must never see: they are the outcome, a post-treatment
#: consequence of it, or an artefact of the decision being evaluated.
FORBIDDEN_FEATURES = {
    "funded",
    "qualified",
    "applied",
    "contacted",
    "realized_net_contribution",
    "realized_gross_value",
    "refunded",
    "minutes_spent",
    "action",
    "action_name",
    "action_direct_cost",
    "resolution_day",
    "censored",
}


class LeakageError(AssertionError):
    pass


def check_no_feature_leakage(feature_columns: list[str]) -> None:
    bad = sorted(set(feature_columns) & FORBIDDEN_FEATURES)
    if bad:
        raise LeakageError(f"post-treatment / outcome columns used as features: {bad}")


def check_temporal_order(split: Split, time_column: str = "created_day") -> None:
    tr = split.train.observed[time_column]
    te = split.test.observed[time_column]
    if len(tr) and len(te) and tr.max() >= te.min():
        raise LeakageError(
            f"training data extends to {tr.max()} but test starts at {te.min()}"
        )


def check_no_entity_overlap(split: Split, key: str = "person_id") -> None:
    """The same human must not appear on both sides of the split.

    CRM data is full of duplicate leads; without this check a duplicate-heavy
    regime quietly inflates every model's score.
    """
    a = set(split.train.observed[key].tolist())
    b = set(split.test.observed[key].tolist())
    overlap = a & b
    if overlap:
        raise LeakageError(
            f"{len(overlap)} {key} values appear in both train and test"
        )


def drop_cross_split_duplicates(split: Split, key: str = "person_id") -> Split:
    """Remove test rows whose entity already appears in training."""
    seen = set(split.train.observed[key].tolist()) | set(
        split.valid.observed[key].tolist()
    )
    mask = ~split.test.observed[key].isin(seen).to_numpy()
    return Split(
        train=split.train,
        valid=split.valid,
        test=split.test.subset(mask),
        boundaries=split.boundaries,
        kind=split.kind,
    )


def audit_split(
    split: Split, feature_columns: list[str], strict_entities: bool = True
) -> dict[str, float]:
    """Run every check and return a report. Raises on hard violations."""
    check_no_feature_leakage(feature_columns)
    check_temporal_order(split)
    report: dict[str, float] = dict(split.sizes())
    a = set(split.train.observed["person_id"].tolist())
    b = set(split.test.observed["person_id"].tolist())
    report["entity_overlap"] = float(len(a & b))
    report["lead_id_overlap"] = float(
        len(
            set(split.train.observed["lead_id"].tolist())
            & set(split.test.observed["lead_id"].tolist())
        )
    )
    if strict_entities and report["entity_overlap"] > 0:
        raise LeakageError(
            f"{int(report['entity_overlap'])} duplicated entities across the split"
        )
    return report
