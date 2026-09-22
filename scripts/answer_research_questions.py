#!/usr/bin/env python
"""Answer each preregistered research question directly from the run data.

    python scripts/answer_research_questions.py --runs reports/runs

Prints, and writes ``reports/latest/rq_answers.md``, a per-RQ verdict built
from the numbers rather than from recollection. Every comparison is paired by
seed and carries a 95% bootstrap interval; the verdict applies the
preregistered decision rule (interval excludes zero AND the point estimate
clears the practical threshold).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from leadbench.evaluation.aggregate import _paired_bootstrap  # noqa: E402

# The preregistered primary metric and decision rule (docs/benchmark-spec.md).
# A candidate beats a reference only if the paired 95% interval on the
# difference in net value per 1,000 leads excludes zero AND the point estimate
# exceeds 2% of the reference's net value per 1,000 leads.
PRIMARY = "net_value_per_1k_leads"
THRESHOLD_REL_PCT = 2.0

# Reported alongside because it is far easier to read: 0 = do nothing,
# 100 = Oracle. It is a *presentation* scale, not the decision rule -- the
# floor-inclusive denominator of the preregistered rule makes it strictly more
# conservative, and the preregistered rule is the one that decides.
SECONDARY = "pct_of_oracle_incremental"


def load(runs: Path, suite: str) -> pd.DataFrame:
    p = runs / suite / "results.csv"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_csv(p)
    return d[d.get("status", "ok") == "ok"]


def paired(df: pd.DataFrame, a: str, b: str, metric: str = PRIMARY,
           by: tuple[str, ...] = ("regime",)) -> pd.DataFrame:
    """Per-group paired difference a - b under the preregistered decision rule.

    Reports the primary (dollar) scale that the verdict is based on, and the
    Oracle-share scale for readability.
    """
    rows = []
    keys = [k for k in by if k in df.columns]
    for key, g in df.groupby(list(keys), dropna=False):
        ga = g[g["candidate"] == a].set_index("seed")
        gb = g[g["candidate"] == b].set_index("seed")
        common = ga.index.intersection(gb.index)
        if len(common) < 2:
            continue
        va = ga.loc[common, metric].to_numpy(float)
        vb = gb.loc[common, metric].to_numpy(float)
        d = va - vb
        lo, hi = _paired_bootstrap(d)
        ref_level = float(np.mean(vb))
        rel = 100.0 * float(np.mean(d)) / abs(ref_level) if abs(ref_level) > 1e-9 else np.nan

        row = {
            "group": "|".join(str(x) for x in (key if isinstance(key, tuple) else (key,))),
            "diff_$per1k": float(np.mean(d)),
            "ci_low": lo, "ci_high": hi,
            "rel_pct": rel,
            "n_seeds": len(common),
            "verdict": _verdict(float(np.mean(d)), lo, hi, rel),
        }
        if SECONDARY in ga.columns:
            sa = float(ga.loc[common, SECONDARY].mean())
            sb = float(gb.loc[common, SECONDARY].mean())
            row.update({"oracle%_a": sa, "oracle%_b": sb, "oracle%_diff": sa - sb})
        rows.append(row)
    return pd.DataFrame(rows)


def _verdict(diff: float, lo: float, hi: float, rel_pct: float) -> str:
    """The preregistered rule: interval excludes zero AND clears 2% relative."""
    if not np.isfinite(lo):
        return "insufficient data"
    if lo <= 0 <= hi:
        return "no evidence"
    if not np.isfinite(rel_pct) or abs(rel_pct) < THRESHOLD_REL_PCT:
        return ("better" if diff > 0 else "worse") + " but below threshold"
    return "BETTER" if diff > 0 else "WORSE"


def _fmt(df: pd.DataFrame, cols=None) -> str:
    if df.empty:
        return "  (no data)\n"
    cols = cols or [
        "group", "oracle%_a", "oracle%_b", "oracle%_diff",
        "diff_$per1k", "ci_low", "ci_high", "rel_pct", "verdict",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].round(2).to_string(index=False) + "\n"


def section(title: str, body: str, out: list[str]) -> None:
    out.append(f"\n## {title}\n\n```\n{body}```\n")
    print(f"\n=== {title} ===")
    print(body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="reports/runs")
    ap.add_argument("--out", default="reports/latest/rq_answers.md")
    args = ap.parse_args()
    runs = Path(args.runs)

    lead = load(runs, "lead")
    curves = load(runs, "curves")
    abl = load(runs, "ablation")
    bayes = load(runs, "bayes")
    online = load(runs, "online")
    real = load(runs, "real")
    mmm = load(runs, "mmm")

    out: list[str] = [
        "# Research-question answers\n",
        f"\nGenerated from run data. The verdict column applies the **preregistered** "
        f"rule (docs/benchmark-spec.md): the paired 95% bootstrap interval on "
        f"**{PRIMARY}** must exclude zero AND the difference must exceed "
        f"**{THRESHOLD_REL_PCT}%** of the reference's level. `oracle%` columns are the "
        f"same comparison on the readable 0-100 scale (0 = do nothing, 100 = Oracle).\n",
    ]

    if len(lead):
        best_analytics = "hist_profit_per_agent_hour"
        section(
            "RQ1  decision model vs end-to-end analytics",
            _fmt(paired(lead, "propensity_ev_gbm", best_analytics))
            + "\n-- strongest causal candidate vs the same baseline --\n"
            + _fmt(paired(lead, "t_learner", best_analytics)),
            out,
        )
        section(
            "RQ2  uplift vs ordinary lead scoring",
            _fmt(paired(lead, "t_learner", "lead_score_gbm"))
            + "\n-- and the economic-but-not-causal rung --\n"
            + _fmt(paired(lead, "propensity_ev_gbm", "lead_score_gbm")),
            out,
        )
        section(
            "RQ3  explicit economics vs a probability score",
            _fmt(paired(lead, "propensity_ev_gbm", "lead_score_gbm")),
            out,
        )
        section(
            "RQ4  does modelling capacity change the ranking?",
            "-- profit per agent-hour vs profit per lead (both analytics) --\n"
            + _fmt(paired(lead, "hist_profit_per_agent_hour", "hist_net_profit"))
            + "\n-- value-aware allocator vs a plain sorted call list (ablation) --\n"
            + _fmt(paired(abl, "propensity_ev_gbm", "abl_propensity_ev_no_optimizer"))
            + _fmt(paired(abl, "t_learner", "abl_t_learner_no_optimizer")),
            out,
        )
        section(
            "RQ2b  causal families against the simple economic baseline",
            "".join(
                _fmt(paired(lead, c, "propensity_ev_gbm"))
                for c in ["s_learner", "t_learner", "x_learner", "dr_learner", "causal_forest"]
                if c in set(lead["candidate"])
            ),
            out,
        )

    if len(bayes):
        section(
            "RQ5  does Bayesian uncertainty pay?",
            _fmt(paired(bayes, "bayes_hierarchical", "propensity_ev_gbm"))
            + "\n-- Bayesian vs a bootstrapped frequentist interval --\n"
            + _fmt(paired(bayes, "bayes_hierarchical", "propensity_ev_gbm_bootstrap"))
            + "\n-- risk-averse (lower credible bound) vs posterior mean --\n"
            + _fmt(paired(bayes, "bayes_hierarchical_lcb10", "bayes_hierarchical"))
            + "\n-- interval honesty (empirical coverage of a stated 80% interval) --\n"
            + _coverage_table(bayes),
            out,
        )
        section(
            "RQ6  hierarchical pooling vs complete pooling",
            _fmt(paired(bayes, "bayes_hierarchical", "abl_bayes_no_hierarchy")),
            out,
        )

    if len(online):
        section(
            "RQ7  bandits vs a frozen or retrained offline model",
            _online_table(online),
            out,
        )

    if len(lead):
        section(
            "RQ8  can observational data answer causal questions?",
            _identification_table(lead),
            out,
        )

    if len(curves):
        section("RQ9  how much data does each approach need?", _size_table(curves), out)
        section("RQ4b capacity sweep", _capacity_table(curves), out)

    if len(abl):
        section("Ablations: where does the advantage come from?", _ablation_table(abl), out)

    if len(real):
        section("Real randomized data (OPE)", _real_table(real), out)

    if len(mmm):
        section("MMM track", _mmm_table(mmm), out)

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(out))
    print(f"\nwrote {p}")
    return 0


def _coverage_table(bayes: pd.DataFrame) -> str:
    cols = [c for c in ["coverage_80", "p_coverage_80", "interval_width_80"] if c in bayes.columns]
    if not cols:
        return "  (no uncertainty candidates)\n"
    d = bayes.groupby("candidate")[cols].mean().dropna(how="all")
    return d.round(3).to_string() + "\n"


def _online_table(online: pd.DataFrame) -> str:
    d = online.pivot_table(index="competitor", columns="regime",
                           values=SECONDARY, aggfunc="mean")
    d["MEAN"] = d.mean(axis=1)
    return d.sort_values("MEAN", ascending=False).round(1).to_string() + "\n"


def _identification_table(lead: pd.DataFrame) -> str:
    keep = ["easy_randomized", "observed_confounding", "hidden_confounding",
            "selection_bias", "policy_feedback_loop"]
    cands = ["hist_profit_per_agent_hour", "lead_score_gbm", "propensity_ev_gbm",
             "t_learner", "dr_learner", "causal_forest"]
    d = lead[lead["regime"].isin(keep) & lead["candidate"].isin(cands)]
    if d.empty:
        return "  (no data)\n"
    t = d.pivot_table(index="candidate", columns="regime",
                      values=SECONDARY, aggfunc="mean")
    t = t.reindex(columns=[k for k in keep if k in t.columns])
    extra = ""
    if "causal_pehe" in d.columns:
        pe = d.pivot_table(index="candidate", columns="regime",
                           values="causal_pehe", aggfunc="mean")
        pe = pe.reindex(columns=[k for k in keep if k in pe.columns])
        extra = "\n-- PEHE (lower is better): how wrong is the estimated effect? --\n" + \
                pe.round(4).to_string() + "\n"
    return t.round(1).to_string() + "\n" + extra


def _size_table(curves: pd.DataFrame) -> str:
    d = curves[curves["scenario"].astype(str).str.startswith("size_")]
    if d.empty:
        return "  (no data)\n"
    t = d.pivot_table(index=["regime", "candidate"], columns="n_leads",
                      values=SECONDARY, aggfunc="mean")
    return t.round(1).to_string() + "\n"


def _capacity_table(curves: pd.DataFrame) -> str:
    d = curves[curves["scenario"].astype(str).str.startswith("capacity_")]
    if d.empty:
        return "  (no data)\n"
    t = d.pivot_table(index=["regime", "candidate"], columns="capacity_ratio",
                      values=SECONDARY, aggfunc="mean")
    return t.round(1).to_string() + "\n"


def _ablation_table(abl: pd.DataFrame) -> str:
    t = abl.pivot_table(index="candidate", columns="regime",
                        values=SECONDARY, aggfunc="mean")
    t["MEAN"] = t.mean(axis=1)
    return t.sort_values("MEAN", ascending=False).round(1).to_string() + "\n"


def _real_table(real: pd.DataFrame) -> str:
    cols = [c for c in ["dr_value", "dr_ci_low", "dr_ci_high", "snips_value",
                        "uplift_qini_auc", "dr_ess"] if c in real.columns]
    if not cols:
        return "  (no data)\n"
    d = (real.groupby(["dataset", "budget", "candidate"], dropna=False)[cols]
         .mean().reset_index())
    d[["dr_value", "dr_ci_low", "dr_ci_high", "snips_value"]] *= 1000.0
    return d.round(3).to_string(index=False) + "\n"


def _mmm_table(mmm: pd.DataFrame) -> str:
    cols = [c for c in mmm.columns if c.startswith("regret_pct_b")]
    cols = ["roi_mape", "roi_rank_spearman"] + cols
    cols = [c for c in cols if c in mmm.columns]
    t = mmm.groupby(["regime", "candidate"])[cols].mean().reset_index()
    return t.round(2).to_string(index=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
