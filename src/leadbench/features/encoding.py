"""Shared feature encoding.

Every model family gets the *same* features from the *same* encoder. If a
gradient booster beats a Bayesian model here it is not because somebody hand
crafted better inputs for it.

Two views of the same columns:

* ``transform_tree``  - ordinal codes, NaN preserved (trees handle missing).
* ``transform_linear`` - one-hot categoricals, standardised numerics, median
  imputation plus explicit missingness indicators.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class TabularEncoder:
    numeric_columns: list[str] = field(default_factory=list)
    categorical_columns: list[str] = field(default_factory=list)

    _categories: dict[str, pd.Index] = field(default_factory=dict, init=False)
    _medians: dict[str, float] = field(default_factory=dict, init=False)
    _means: dict[str, float] = field(default_factory=dict, init=False)
    _stds: dict[str, float] = field(default_factory=dict, init=False)
    _fitted: bool = field(default=False, init=False)

    @classmethod
    def from_columns(
        cls, feature_columns: list[str], categorical_columns: list[str]
    ) -> "TabularEncoder":
        cats = [c for c in feature_columns if c in set(categorical_columns)]
        nums = [c for c in feature_columns if c not in set(categorical_columns)]
        return cls(numeric_columns=nums, categorical_columns=cats)

    def fit(self, df: pd.DataFrame) -> "TabularEncoder":
        for c in self.categorical_columns:
            self._categories[c] = pd.Index(pd.unique(df[c].astype("object").dropna()))
        for c in self.numeric_columns:
            col = pd.to_numeric(df[c], errors="coerce")
            self._medians[c] = float(col.median()) if col.notna().any() else 0.0
            self._means[c] = float(col.mean()) if col.notna().any() else 0.0
            s = float(col.std()) if col.notna().any() else 1.0
            self._stds[c] = s if s > 1e-9 else 1.0
        self._fitted = True
        return self

    def _check(self) -> None:
        if not self._fitted:
            raise RuntimeError("TabularEncoder.fit must be called first")

    @property
    def tree_feature_names(self) -> list[str]:
        return list(self.numeric_columns) + [f"{c}__code" for c in self.categorical_columns]

    def transform_tree(self, df: pd.DataFrame) -> np.ndarray:
        self._check()
        cols = []
        for c in self.numeric_columns:
            cols.append(pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float))
        for c in self.categorical_columns:
            codes = self._categories[c].get_indexer(df[c].astype("object"))
            cols.append(codes.astype(float))  # -1 marks unseen levels
        return np.column_stack(cols) if cols else np.zeros((len(df), 0))

    @property
    def linear_feature_names(self) -> list[str]:
        names = list(self.numeric_columns)
        names += [f"{c}__isna" for c in self.numeric_columns]
        for c in self.categorical_columns:
            names += [f"{c}={v}" for v in self._categories[c]]
        return names

    def transform_linear(self, df: pd.DataFrame) -> np.ndarray:
        self._check()
        n = len(df)
        blocks = []
        num, isna = [], []
        for c in self.numeric_columns:
            col = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
            miss = np.isnan(col)
            filled = np.where(miss, self._medians[c], col)
            num.append((filled - self._means[c]) / self._stds[c])
            isna.append(miss.astype(float))
        if num:
            blocks.append(np.column_stack(num))
            blocks.append(np.column_stack(isna))
        for c in self.categorical_columns:
            cats = self._categories[c]
            codes = cats.get_indexer(df[c].astype("object"))
            oh = np.zeros((n, len(cats)))
            valid = codes >= 0
            oh[np.arange(n)[valid], codes[valid]] = 1.0
            blocks.append(oh)
        return np.column_stack(blocks) if blocks else np.zeros((n, 0))


def add_treatment_column(X: np.ndarray, treatment: np.ndarray, n_actions: int) -> np.ndarray:
    """One-hot append the treatment, for S-learner style models."""
    t = np.asarray(treatment, dtype=int)
    oh = np.zeros((len(t), n_actions))
    oh[np.arange(len(t)), t] = 1.0
    return np.column_stack([X, oh])
