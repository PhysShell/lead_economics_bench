"""Preregistration and reproducibility manifests.

The rule this module enforces: the manifest is written **before** any test-set
number exists, and it is hashed. Once results are computed the manifest is
immutable. If we later find a mistake, we create a *new* experiment id with a
stated reason rather than editing the old one.

This is the difference between a benchmark and a sales deck. Without it,
"we tried a few thresholds and this one worked" is indistinguishable from
"this threshold works".
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True
        )
        return bool(out.strip())
    except Exception:
        return False


def library_versions() -> dict[str, str]:
    import importlib

    names = [
        "numpy", "pandas", "scipy", "sklearn", "xgboost", "lightgbm",
        "econml", "sklift", "pymc", "pytensor", "arviz", "pymc_marketing",
        "statsmodels", "pulp",
    ]
    out: dict[str, str] = {"python": sys.version.split()[0]}
    for n in names:
        try:
            out[n] = getattr(importlib.import_module(n), "__version__", "?")
        except Exception:
            out[n] = "absent"
    return out


def hardware_info() -> dict[str, Any]:
    import os

    info: dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total_kb"] = int(line.split()[1])
                    break
    except Exception:
        pass
    return info


def stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass
class KillCriteria:
    """Conditions under which a component of the idea is declared not worth building.

    Fixed in advance, so that a disappointing result cannot be renegotiated
    into a success afterwards.
    """

    #: Smallest uplift in net value per 1,000 leads, relative to the best
    #: analytics baseline, that we would call practically important.
    min_practical_uplift_pct: float = 2.0
    #: If a Bayesian candidate is not at least this much better than the best
    #: non-Bayesian candidate while costing more than `max_compute_multiple`
    #: times the compute, recommend the simple one.
    bayes_min_uplift_pct: float = 2.0
    max_compute_multiple: float = 10.0
    #: If causal candidates do not beat Propensity-EV by this much on
    #: randomized data, uplift modelling is not earning its complexity.
    causal_min_uplift_pct: float = 2.0
    #: If the best analytics baseline captures at least this share of the
    #: Oracle's achievable gain, lead-level decisioning is not the bottleneck.
    analytics_sufficient_pct_of_oracle: float = 80.0
    #: MMM budget-allocation regret above this is "not trustworthy for SMB".
    mmm_max_acceptable_regret_pct: float = 10.0


@dataclass
class ExperimentManifest:
    experiment_id: str
    description: str
    primary_metric: str = "net_value_per_1k_leads"
    secondary_metrics: tuple[str, ...] = (
        "incremental_net_value_per_1k",
        "net_value_per_agent_hour",
        "pct_of_oracle_incremental",
        "regret_per_1k",
        "pred_ece",
        "pred_log_loss",
        "uplift_qini_auc",
        "causal_pehe",
        "coverage_80",
        "fit_seconds",
    )
    decision_rule: str = (
        "A candidate is declared better than a reference only if the paired "
        "difference in the primary metric has a 95% interval excluding zero AND "
        "the point estimate exceeds the preregistered practical threshold."
    )
    kill_criteria: KillCriteria = field(default_factory=KillCriteria)
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)
    risk_policies: tuple[str, ...] = ("ev", "ev_lcb10", "ev_lcb25")
    abstention_coverages: tuple[float, ...] = (0.25, 0.50, 0.75, 1.0)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    dataset_hashes: dict[str, str] = field(default_factory=dict)
    economics: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    hyperparameter_budget: str = (
        "Every gradient-boosted learner in every family uses the identical "
        "configuration (n_estimators=400, max_depth=5, learning_rate=0.05, "
        "min_child_weight=5). No per-family tuning, no test-set selection. "
        "Bayesian candidates get a fixed sampler budget recorded in the results."
    )
    git_commit: str = field(default_factory=_git_commit)
    git_dirty: bool = field(default_factory=_git_dirty)
    libraries: dict[str, str] = field(default_factory=library_versions)
    hardware: dict[str, Any] = field(default_factory=hardware_info)
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    supersedes: str | None = None
    supersede_reason: str | None = None
    frozen_hash: str | None = None

    def freeze(self) -> "ExperimentManifest":
        """Seal the manifest. Must be called before any test metric is computed."""
        body = asdict(self)
        body.pop("frozen_hash", None)
        self.frozen_hash = stable_hash(body)
        return self

    def write(self, path: str | Path) -> Path:
        if self.frozen_hash is None:
            self.freeze()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2, default=str))
        return p

    @staticmethod
    def load(path: str | Path) -> dict[str, Any]:
        return json.loads(Path(path).read_text())

    def verify(self) -> bool:
        """Check that a loaded manifest has not been edited since freezing."""
        body = asdict(self)
        claimed = body.pop("frozen_hash", None)
        return claimed is not None and claimed == stable_hash(body)


def dataset_fingerprint(df, columns: list[str] | None = None) -> str:
    """Content hash of a dataframe, for the manifest."""
    import pandas as pd

    cols = columns or list(df.columns)
    sub = df[cols]
    return hashlib.sha256(
        pd.util.hash_pandas_object(sub, index=False).values.tobytes()
    ).hexdigest()[:16]
