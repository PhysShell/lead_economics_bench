"""Real randomized-experiment datasets.

Two datasets, both genuine randomized experiments, both with documented
provenance. Neither is committed to the repository: Criteo is CC BY-NC-SA 4.0
(non-commercial only) and Hillstrom is a third-party release. Use
``scripts/download_datasets.py``.

Provenance
----------
**Hillstrom / MineThatData E-Mail Analytics And Data Mining Challenge (2008)**
  64,000 customers who last purchased within twelve months, randomly assigned
  in thirds to a Mens e-mail campaign, a Womens e-mail campaign, or no e-mail.
  Outcomes observed over the following two weeks: ``visit``, ``conversion``,
  ``spend``.
  Source: http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv
  Announcement: https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html
  Randomisation: stated by the publisher as a 1/3 : 1/3 : 1/3 random split.
  Accessed: 2026-09-22. SHA256 of the CSV is pinned in ``DATASETS`` below.

**Criteo-UPLIFT v2.1**
  13,979,592 rows, 12 dense features ``f0..f11``, a binary ``treatment``, and
  ``visit`` / ``conversion`` labels plus an ``exposure`` flag. Collected from
  several incrementality tests in which a random part of the population was
  prevented from being targeted.
  Source page: https://ailab.criteo.com/criteo-uplift-prediction-dataset/
  Direct file: http://go.criteo.net/criteo-research-uplift-v2.1.csv.gz
  Paper: Diemert, Betlei, Renaudin, Amini, "A Large Scale Benchmark for Uplift
  Modeling", AdKDD & TargetAd Workshop, KDD 2018.
  Licence: CC BY-NC-SA 4.0 -- **non-commercial use only**. This is a real
  constraint on a commercial product programme, not a formality.
  Version: v2.1 is the corrected release. The original v2.0 had a documented
  leak caused by non-uniform incrementality across advertisers; this module
  refuses to load v2.0.
  Accessed: 2026-09-22.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DATA_DIR = Path(os.environ.get("LEADBENCH_DATA", "data/raw"))

DATASETS: dict[str, dict[str, Any]] = {
    "hillstrom": {
        "url": (
            "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_"
            "E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
        ),
        "filename": "hillstrom.csv",
        "sha256": "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece",
        "licence": "Released publicly by Kevin Hillstrom / MineThatData for the 2008 challenge",
        "randomized": True,
        "n_rows": 64_000,
    },
    "criteo": {
        "url": "http://go.criteo.net/criteo-research-uplift-v2.1.csv.gz",
        "filename": "criteo-research-uplift-v2.1.csv.gz",
        "sha256": "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc",
        "licence": "CC BY-NC-SA 4.0 (non-commercial)",
        "randomized": True,
        "n_rows": 13_979_592,
    },
}


@dataclass
class RealDataset:
    """A randomized experiment framed as a lead-allocation problem."""

    name: str
    df: pd.DataFrame
    feature_columns: list[str]
    categorical_columns: list[str]
    treatment_column: str
    outcome_column: str
    value_column: str | None
    propensity: np.ndarray  # P(treated) under the logging (experimental) policy
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.df)

    @property
    def treatment(self) -> np.ndarray:
        return self.df[self.treatment_column].to_numpy(dtype=int)

    @property
    def outcome(self) -> np.ndarray:
        return self.df[self.outcome_column].to_numpy(dtype=float)

    def propensity_matrix(self) -> np.ndarray:
        p = np.clip(self.propensity, 1e-6, 1 - 1e-6)
        return np.column_stack([1 - p, p])

    def describe(self) -> dict[str, Any]:
        t, y = self.treatment, self.outcome
        return {
            "dataset": self.name,
            "n": len(self.df),
            "treated_share": float(t.mean()),
            "outcome_rate_overall": float(y.mean()),
            "outcome_rate_treated": float(y[t == 1].mean()),
            "outcome_rate_control": float(y[t == 0].mean()),
            "naive_ate": float(y[t == 1].mean() - y[t == 0].mean()),
            **self.meta,
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(name: str, data_dir: Path | None = None) -> dict[str, Any]:
    spec = DATASETS[name]
    path = (data_dir or DATA_DIR) / spec["filename"]
    if not path.exists():
        raise FileNotFoundError(
            f"{name} not found at {path}. Run: python scripts/download_datasets.py --dataset {name}"
        )
    digest = _sha256(path)
    if spec["sha256"] and digest != spec["sha256"]:
        raise ValueError(
            f"{name} checksum mismatch: expected {spec['sha256']}, got {digest}"
        )
    return {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}


# ---------------------------------------------------------------------------
# Hillstrom
# ---------------------------------------------------------------------------

HILLSTROM_FEATURES = [
    "recency",
    "history",
    "mens",
    "womens",
    "newbie",
    "history_segment",
    "zip_code",
    "channel",
]
HILLSTROM_CATEGORICAL = ["history_segment", "zip_code", "channel"]


def load_hillstrom(
    data_dir: Path | None = None,
    outcome: str = "visit",
    arms: str = "any_email",
) -> RealDataset:
    """Load the MineThatData e-mail experiment.

    ``arms``:
        ``any_email``  - Mens or Womens e-mail versus no e-mail (P(treat)=2/3)
        ``mens``       - Mens e-mail versus no e-mail, Womens rows dropped
        ``womens``     - Womens e-mail versus no e-mail, Mens rows dropped
    """
    spec = DATASETS["hillstrom"]
    path = (data_dir or DATA_DIR) / spec["filename"]
    df = pd.read_csv(path)
    expected = {
        "recency", "history_segment", "history", "mens", "womens", "zip_code",
        "newbie", "channel", "segment", "visit", "conversion", "spend",
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"hillstrom schema mismatch, missing {sorted(missing)}")
    if len(df) != spec["n_rows"]:
        raise ValueError(f"hillstrom row count {len(df)} != {spec['n_rows']}")

    seg = df["segment"]
    if arms == "any_email":
        t = (seg != "No E-Mail").astype(int)
        p = np.full(len(df), 2.0 / 3.0)
    elif arms in ("mens", "womens"):
        want = "Mens E-Mail" if arms == "mens" else "Womens E-Mail"
        keep = seg.isin([want, "No E-Mail"])
        df = df.loc[keep].reset_index(drop=True)
        seg = df["segment"]
        t = (seg == want).astype(int)
        # Conditional on being in one of these two arms, each was assigned with
        # probability 1/3 unconditionally, so the conditional probability is 1/2.
        p = np.full(len(df), 0.5)
    else:
        raise ValueError(f"unknown arms {arms!r}")

    df = df.copy()
    df["treatment"] = t.to_numpy()
    return RealDataset(
        name=f"hillstrom_{arms}_{outcome}",
        df=df,
        feature_columns=list(HILLSTROM_FEATURES),
        categorical_columns=list(HILLSTROM_CATEGORICAL),
        treatment_column="treatment",
        outcome_column=outcome,
        value_column="spend",
        propensity=p,
        meta={
            "randomized": True,
            "arms": arms,
            "source": spec["url"],
            "licence": spec["licence"],
        },
    )


# ---------------------------------------------------------------------------
# Criteo
# ---------------------------------------------------------------------------

CRITEO_FEATURES = [f"f{i}" for i in range(12)]


def load_criteo(
    data_dir: Path | None = None,
    outcome: str = "conversion",
    n_rows: int | None = 2_000_000,
    seed: int = 12345,
) -> RealDataset:
    """Load Criteo-UPLIFT v2.1.

    ``n_rows`` takes a *deterministic* subsample so that every algorithm in the
    benchmark sees byte-identical data. The subsample is drawn by a seeded
    permutation of the loaded rows, and the seed is part of the experiment
    manifest. ``n_rows=None`` loads all 13.98M rows.
    """
    spec = DATASETS["criteo"]
    path = (data_dir or DATA_DIR) / spec["filename"]
    if not path.exists():
        raise FileNotFoundError(
            f"criteo not found at {path}. Run: python scripts/download_datasets.py --dataset criteo"
        )
    usecols = CRITEO_FEATURES + ["treatment", "conversion", "visit", "exposure"]
    dtypes = {c: "float32" for c in CRITEO_FEATURES}
    dtypes.update({c: "int8" for c in ["treatment", "conversion", "visit", "exposure"]})
    df = pd.read_csv(path, usecols=usecols, dtype=dtypes)

    if len(df) != spec["n_rows"]:
        raise ValueError(
            f"criteo row count {len(df)} != {spec['n_rows']}; this is probably the "
            "leaked v2.0 file rather than the corrected v2.1"
        )
    if n_rows is not None and n_rows < len(df):
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(df))[:n_rows]
        idx.sort()
        df = df.iloc[idx].reset_index(drop=True)

    p_treat = float(df["treatment"].mean())
    return RealDataset(
        name=f"criteo_{outcome}",
        df=df,
        feature_columns=list(CRITEO_FEATURES),
        categorical_columns=[],
        treatment_column="treatment",
        outcome_column=outcome,
        value_column=None,
        propensity=np.full(len(df), p_treat),
        meta={
            "randomized": True,
            "version": "v2.1-unbiased",
            "subsample_rows": n_rows,
            "subsample_seed": seed,
            "empirical_treat_share": p_treat,
            "source": spec["url"],
            "licence": spec["licence"],
        },
    )


LOADERS = {"hillstrom": load_hillstrom, "criteo": load_criteo}
