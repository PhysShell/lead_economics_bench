"""Automatic adversarial checks on a dataset before anyone models it.

Section 39 asks for automated detection of the classic traps. These are cheap,
they run on observed data only, and they are meant to be run against a *real*
partner's export as much as against the synthetic regimes — the first time a
CRM extract goes through this, it usually finds something.

None of these prove a dataset is sound. They catch the obvious cases, which is
most of the cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class Finding:
    check: str
    severity: str  # "info" | "warn" | "fail"
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.severity.upper():4s}] {self.check}: {self.message}"


def simpson_check(
    df: pd.DataFrame,
    treatment: str = "action",
    outcome: str = "funded",
    by: str = "campaign_id",
    min_cell: int = 50,
) -> list[Finding]:
    """Does the treatment-outcome association flip sign when we condition?

    The marginal difference ``E[Y|T=1] - E[Y|T=0]`` is compared with the
    size-weighted average of the same difference computed *within* each
    segment. A sign flip is Simpson's paradox and means the marginal number is
    actively misleading.
    """
    out: list[Finding] = []
    d = df[[treatment, outcome, by]].dropna()
    if d.empty:
        return [Finding("simpson", "info", "no usable rows")]
    t = (d[treatment] > 0).astype(int)
    y = d[outcome].astype(float)
    if t.nunique() < 2:
        return [Finding("simpson", "info", "only one treatment arm present")]

    marginal = float(y[t == 1].mean() - y[t == 0].mean())

    num, den = 0.0, 0.0
    flipped = []
    for seg, g in d.groupby(by, observed=True):
        tt = (g[treatment] > 0).astype(int)
        if tt.sum() < min_cell or (1 - tt).sum() < min_cell:
            continue
        yy = g[outcome].astype(float)
        diff = float(yy[tt == 1].mean() - yy[tt == 0].mean())
        w = len(g)
        num += w * diff
        den += w
        if np.sign(diff) != np.sign(marginal) and abs(diff) > 1e-9:
            flipped.append((seg, round(diff, 5)))

    if den == 0:
        return [Finding("simpson", "info", f"no {by} cell had {min_cell}+ rows per arm")]
    within = num / den

    detail = {
        "marginal_diff": round(marginal, 6),
        "within_segment_weighted_diff": round(within, 6),
        "n_segments_with_opposite_sign": len(flipped),
        "examples": flipped[:5],
    }
    if np.sign(marginal) != np.sign(within) and abs(marginal) > 1e-6:
        out.append(Finding(
            "simpson", "fail",
            f"the marginal treatment-outcome difference ({marginal:+.4f}) has the "
            f"opposite sign to the within-{by} weighted difference ({within:+.4f}); "
            "the aggregate number is misleading",
            detail,
        ))
    elif len(flipped) > 0:
        out.append(Finding(
            "simpson", "warn",
            f"{len(flipped)} {by} segments show the opposite sign to the marginal "
            "difference; aggregate reporting will mislead for those segments",
            detail,
        ))
    else:
        out.append(Finding("simpson", "info", "no sign reversal detected", detail))
    return out


def target_leakage_check(
    df: pd.DataFrame,
    feature_columns: list[str],
    outcome: str = "funded",
    threshold: float = 0.85,
) -> list[Finding]:
    """A feature that predicts the outcome almost perfectly is usually the outcome."""
    out: list[Finding] = []
    y = pd.to_numeric(df[outcome], errors="coerce")
    ok = y.notna()
    for c in feature_columns:
        x = pd.to_numeric(df[c], errors="coerce")
        m = ok & x.notna()
        if m.sum() < 100 or x[m].nunique() < 2 or y[m].nunique() < 2:
            continue
        r = float(np.corrcoef(x[m], y[m])[0, 1])
        if abs(r) >= threshold:
            out.append(Finding(
                "target_leakage", "fail",
                f"feature {c!r} correlates {r:+.3f} with {outcome!r}; it is almost "
                "certainly a consequence of the outcome rather than a predictor",
                {"column": c, "corr": round(r, 4)},
            ))
    if not out:
        out.append(Finding("target_leakage", "info", "no feature is suspiciously predictive"))
    return out


def future_information_check(
    df: pd.DataFrame,
    feature_columns: list[str] | None = None,
    decision_time: str = "created_day",
    candidate_time_columns: tuple[str, ...] = (
        "resolution_day", "funded_at", "closed_at", "approved_at",
    ),
) -> list[Finding]:
    """Anything timestamped after the decision cannot be an input to it.

    Only escalates for columns that are actually in the declared feature list.
    A dataset merely *containing* a resolution timestamp is normal and fine;
    feeding one to a model is not.
    """
    out: list[Finding] = []
    if decision_time not in df.columns:
        return [Finding("future_information", "info", f"no {decision_time} column")]
    features = set(feature_columns or [])
    future_cols = []
    for col in candidate_time_columns:
        if col not in df.columns:
            continue
        later = float((pd.to_numeric(df[col], errors="coerce")
                       > pd.to_numeric(df[decision_time], errors="coerce")).mean())
        if later > 0.5:
            future_cols.append((col, later))

    for col, later in future_cols:
        if col in features:
            out.append(Finding(
                "future_information", "fail",
                f"{col!r} resolves after {decision_time!r} for {later:.0%} of rows "
                "and is declared as a model feature; this leaks the future",
                {"column": col, "share_later": round(later, 4)},
            ))
    if not out:
        out.append(Finding(
            "future_information", "info",
            f"{len(future_cols)} future-dated column(s) present and none is used "
            "as a feature",
            {"future_dated_columns": [c for c, _ in future_cols]},
        ))
    return out


def positivity_check(
    df: pd.DataFrame,
    propensity_columns: list[str] | None = None,
    min_propensity: float = 0.01,
) -> list[Finding]:
    """Without overlap, no off-policy or causal estimate is identified."""
    cols = propensity_columns or [c for c in df.columns if c.startswith("propensity_")]
    cols = [c for c in cols if c != "propensity"]
    if not cols:
        return [Finding("positivity", "warn",
                        "no logged action propensities; off-policy evaluation is "
                        "not identified and causal claims rest on assumptions "
                        "the data cannot check")]
    p = df[cols].to_numpy(dtype=float)
    worst = float(np.nanmin(p))
    share = float(np.nanmean(p.min(axis=1) < min_propensity))
    detail = {"min_propensity": round(worst, 6), "share_below_threshold": round(share, 4)}
    if share > 0.10:
        return [Finding("positivity", "fail",
                        f"{share:.0%} of rows have an action with probability below "
                        f"{min_propensity}; overlap is destroyed and off-policy "
                        "estimates will extrapolate", detail)]
    if share > 0.01:
        return [Finding("positivity", "warn",
                        f"{share:.1%} of rows sit below the overlap threshold", detail)]
    return [Finding("positivity", "info", "overlap looks adequate", detail)]


def duplicate_entity_check(
    df: pd.DataFrame, entity: str = "person_id", key: str = "lead_id"
) -> list[Finding]:
    if entity not in df.columns:
        return [Finding("duplicate_entity", "info", f"no {entity} column")]
    n_rows, n_entities = len(df), df[entity].nunique()
    dupe_share = 1.0 - n_entities / max(n_rows, 1)
    detail = {"rows": n_rows, "entities": n_entities, "duplicate_share": round(dupe_share, 4)}
    if dupe_share > 0.005:
        return [Finding("duplicate_entity", "warn",
                        f"{dupe_share:.1%} of rows are repeat appearances of the same "
                        f"{entity}; splits must be made on {entity}, not {key}", detail)]
    return [Finding("duplicate_entity", "info", "no meaningful duplication", detail)]


def run_all(
    df: pd.DataFrame,
    feature_columns: list[str],
    outcome: str = "funded",
    treatment: str = "action",
    segment: str = "campaign_id",
) -> list[Finding]:
    """Every check, in one call. Returns findings sorted worst-first."""
    findings: list[Finding] = []
    findings += simpson_check(df, treatment, outcome, segment)
    findings += target_leakage_check(df, feature_columns, outcome)
    findings += future_information_check(df, feature_columns)
    findings += positivity_check(df)
    findings += duplicate_entity_check(df)
    order = {"fail": 0, "warn": 1, "info": 2}
    return sorted(findings, key=lambda f: order.get(f.severity, 3))


def report(findings: list[Finding]) -> str:
    return "\n".join(str(f) for f in findings)
