#!/usr/bin/env python
"""Turn raw run CSVs into leaderboards, comparisons and figures.

    python scripts/build_report.py --runs reports/runs --out reports/latest

Produces:
    leaderboard.csv            primary metric per candidate per scenario, with CIs
    comparisons.csv            every candidate vs the preregistered references
    kill_criteria.csv          each criterion evaluated against the evidence
    failures.csv               every candidate that errored, and why
    pareto.csv                 value vs compute frontier
    figures/*.png              data-size, capacity and coverage curves
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from leadbench.evaluation.aggregate import (  # noqa: E402
    leaderboard,
    ok_rows,
    oracle_share,
    paired_comparisons,
    pareto_frontier,
    summarise_failures,
)

PRIMARY = "net_value_per_1k_leads"
PRACTICAL_PCT = 2.0

#: The references RQ1-RQ3 are defined against.
REFERENCES = [
    "hist_profit_per_agent_hour",  # best pure-analytics baseline  (RQ1, K3, K5)
    "lead_score_gbm",              # ordinary lead scoring         (RQ2)
    "propensity_ev_gbm",           # simple economic baseline      (RQ3, K2)
]


def load(runs: Path, suite: str) -> pd.DataFrame:
    p = runs / suite / "results.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["suite"] = suite
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="reports/runs")
    ap.add_argument("--out", default="reports/latest")
    args = ap.parse_args()
    runs, out = Path(args.runs), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)

    suites = {s: load(runs, s) for s in
              ["lead", "curves", "ablation", "bayes", "online", "real", "mmm",
               "smoke", "rq4", "pie"]}
    lead = pd.concat(
        [suites[s] for s in ("lead", "ablation", "bayes") if len(suites[s])],
        ignore_index=True,
    ) if any(len(suites[s]) for s in ("lead", "ablation", "bayes")) else pd.DataFrame()

    summary: dict[str, object] = {}

    # ---------------- leaderboards ------------------------------------
    if len(lead):
        board = leaderboard(lead, PRIMARY)
        board.to_csv(out / "leaderboard.csv", index=False)
        summary["n_lead_rows"] = int(len(lead))

        inc = leaderboard(lead, "incremental_net_value_per_1k")
        inc.to_csv(out / "leaderboard_incremental.csv", index=False)

        pct = leaderboard(lead, "pct_of_oracle_incremental")
        pct.to_csv(out / "leaderboard_pct_of_oracle.csv", index=False)

        # The stable version of the same quantity. `pct_of_oracle_incremental`
        # is a per-seed ratio and averaging it explodes wherever the Oracle's
        # own gain is small (see aggregate.oracle_share).
        share = oracle_share(lead)
        share.to_csv(out / "oracle_share_by_regime.csv")

        comps = []
        for ref in REFERENCES:
            c = paired_comparisons(lead, ref, PRIMARY, PRACTICAL_PCT)
            if len(c):
                comps.append(c)
        if comps:
            allc = pd.concat(comps, ignore_index=True)
            allc.to_csv(out / "comparisons.csv", index=False)
            summary["n_comparisons"] = int(len(allc))

        fails = summarise_failures(lead)
        fails.to_csv(out / "failures.csv", index=False)
        summary["n_failed_cells"] = int(fails["count"].sum()) if len(fails) else 0

        # Pareto on the Oracle-share scale, averaged across regimes, with the
        # two degenerate reference points removed. On the raw dollar scale
        # `do_nothing` dominates everything on cost (zero seconds, and a net
        # value that still contains the whole do-nothing floor), which makes
        # the frontier meaningless.
        # Restricted to the main lead sweep. `lead` also carries the ablation
        # and bayes suites, which run at a different dataset size and over a
        # different regime set, and averaging those into one frontier compares
        # candidates that never met. Scored on the regimes every candidate
        # completed, so one that crashed is not credited with an easier average.
        main = suites["lead"] if len(suites["lead"]) else lead
        main_share = oracle_share(main)
        common = main_share.dropna(axis=1, how="any")
        pcost = (
            ok_rows(main)
            .groupby("candidate")[["fit_seconds", "predict_seconds"]]
            .mean()
            .assign(mean=common.mean(axis=1) if common.shape[1] else float("nan"))
            .reset_index()
        )
        pcost = pcost[~pcost["candidate"].isin(["oracle", "do_nothing"])]
        pf = pareto_frontier(pcost, "mean", "fit_seconds")
        pf.to_csv(out / "pareto.csv", index=False)
        _plot_pareto(pcost, pf, out / "figures" / "pareto_value_vs_compute.png")

        _plot_regime_bars(lead, out / "figures" / "by_regime.png")
        _plot_coverage(lead, out / "figures" / "uncertainty_coverage.png")

    # ---------------- curves ------------------------------------------
    if len(suites["curves"]):
        c = suites["curves"]
        size = c[c["scenario"].str.startswith("size_")].copy()
        if len(size):
            # Configured size comes from the scenario name; older runs have the
            # test-fold size in n_leads due to a now-fixed key collision.
            size["n"] = (
                size["scenario"].astype(str).str.extract(r"_n(\d+)$")[0].astype(float)
            ).fillna(size["n_leads"])
            sb = leaderboard(size, "pct_of_oracle_incremental",
                             group_cols=("regime", "n", "candidate"))
            sb.to_csv(out / "curve_data_size.csv", index=False)
            _plot_curve(sb, "n", "data size (leads)", out / "figures" / "curve_data_size.png",
                        logx=True)
        cap = c[c["scenario"].str.startswith("capacity_")].copy()
        if len(cap):
            cb = leaderboard(cap, "pct_of_oracle_incremental",
                             group_cols=("regime", "capacity_ratio", "candidate"))
            cb.to_csv(out / "curve_capacity.csv", index=False)
            _plot_curve(cb, "capacity_ratio", "agent capacity (share of full coverage)",
                        out / "figures" / "curve_capacity.png")

    # ---------------- online ------------------------------------------
    if len(suites["online"]):
        o = suites["online"]
        ob = leaderboard(o, "pct_of_oracle_incremental",
                         group_cols=("regime", "competitor"), seed_col="seed")
        ob.to_csv(out / "leaderboard_online.csv", index=False)

    # ---------------- real --------------------------------------------
    if len(suites["real"]):
        r = suites["real"]
        r = r[r["status"] == "ok"]
        if len(r):
            rb = (
                r.groupby(["dataset", "budget", "candidate"], dropna=False)
                .agg(
                    dr_value=("dr_value", "mean"),
                    dr_ci_low=("dr_ci_low", "mean"),
                    dr_ci_high=("dr_ci_high", "mean"),
                    snips_value=("snips_value", "mean"),
                    qini=("uplift_qini_auc", "mean"),
                    ess=("dr_ess", "mean"),
                    n_seeds=("seed", "nunique"),
                )
                .reset_index()
                .sort_values(["dataset", "budget", "dr_value"], ascending=[True, True, False])
            )
            rb.to_csv(out / "leaderboard_real.csv", index=False)

    # ---------------- mmm ---------------------------------------------
    if len(suites["mmm"]):
        m = suites["mmm"]
        m = m[m["status"] == "ok"]
        cols = [c for c in m.columns if c.startswith("regret_pct_b") or c.startswith("pct_of_oracle_gain_b")]
        agg = {c: "mean" for c in cols}
        agg.update({"roi_mape": "mean", "roi_rank_spearman": "mean"})
        mb = m.groupby(["regime", "candidate"], dropna=False).agg(agg).reset_index()
        mb.to_csv(out / "leaderboard_mmm.csv", index=False)
        _plot_mmm(mb, out / "figures" / "mmm_regret.png")

    # ---------------- RQ4 focused run ---------------------------------
    if len(suites["rq4"]):
        q = suites["rq4"]
        q = q[q["status"] == "ok"]
        if len(q):
            qb = (q.groupby("candidate")[
                      ["pct_of_oracle_incremental", "net_value_per_1k_leads",
                       "net_value_per_agent_hour", "share_treated"]]
                  .mean().sort_values("pct_of_oracle_incremental", ascending=False))
            qb.to_csv(out / "leaderboard_rq4_campaign_effort.csv")

    # ---------------- PIE campaign-level track ------------------------
    if len(suites["pie"]):
        pie = suites["pie"]
        pie = ok_rows(pie)
        cols = [c for c in ["rmse", "mae", "spearman", "pct_of_oracle_selection"]
                if c in pie.columns]
        if len(pie) and cols:
            pb = (pie.groupby(["share_measured", "candidate"])[cols]
                  .mean().reset_index()
                  .sort_values(["share_measured", "rmse"]))
            pb.to_csv(out / "leaderboard_pie.csv", index=False)

    # ---------------- kill criteria -----------------------------------
    if len(lead):
        kc = _kill_criteria(lead, suites["mmm"], suites["bayes"])
        kc.to_csv(out / "kill_criteria.csv", index=False)
        summary["kill_criteria"] = kc.to_dict("records")

    # ---------------- manifest ----------------------------------------
    manifests = {}
    for s in suites:
        mp = runs / s / "experiment-manifest.json"
        if mp.exists():
            manifests[s] = json.loads(mp.read_text())
    (out / "experiment-manifest.json").write_text(json.dumps(manifests, indent=2))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"wrote report artefacts to {out}")
    for k, v in summary.items():
        if k != "kill_criteria":
            print(f"  {k}: {v}")
    return 0


def _kill_criteria(lead: pd.DataFrame, mmm: pd.DataFrame, bayes: pd.DataFrame) -> pd.DataFrame:
    """Evaluate each preregistered criterion against the evidence."""
    rows = []
    ok = lead[lead["status"] == "ok"]

    def mean_of(cand, metric="pct_of_oracle_incremental", df=None):
        d = ok if df is None else df
        v = pd.to_numeric(d.loc[d["candidate"] == cand, metric], errors="coerce")
        return float(v.mean()) if len(v) else float("nan")

    # K3 / K5: analytics sufficiency
    analytics = mean_of("hist_profit_per_agent_hour")
    best_model = np.nanmax([
        mean_of(c) for c in
        ["propensity_ev_gbm", "t_learner", "dr_learner", "x_learner", "causal_forest",
         "funnel_ev_gbm", "s_learner", "bayes_hierarchical"]
    ])
    rows.append({
        "criterion": "K3 kill lead-level decisioning",
        "test": "analytics baseline >= 80% of Oracle achievable gain",
        "value": analytics,
        "threshold": 80.0,
        "triggered": bool(analytics >= 80.0),
    })
    rows.append({
        "criterion": "K5 kill product hypothesis",
        "test": "best model within 2% (absolute pct-of-oracle) of analytics baseline",
        "value": float(best_model - analytics),
        "threshold": 2.0,
        "triggered": bool((best_model - analytics) < 2.0),
    })

    # K2: uplift
    causal = np.nanmax([mean_of(c) for c in
                        ["t_learner", "dr_learner", "x_learner", "causal_forest", "s_learner"]])
    pev = mean_of("propensity_ev_gbm")
    rows.append({
        "criterion": "K2 kill uplift",
        "test": "best causal model fails to beat propensity_ev by >2 pct-of-oracle points",
        "value": float(causal - pev),
        "threshold": 2.0,
        "triggered": bool((causal - pev) <= 2.0),
    })

    # K1: Bayesian
    if len(bayes):
        b = bayes[bayes["status"] == "ok"]
        bay = mean_of("bayes_hierarchical", df=b)
        nonbay = np.nanmax([mean_of(c, df=b) for c in
                            ["propensity_ev_gbm", "t_learner",
                             "propensity_ev_gbm_bootstrap"]])
        bt = pd.to_numeric(b.loc[b["candidate"] == "bayes_hierarchical", "fit_seconds"],
                           errors="coerce").mean()
        nt = pd.to_numeric(b.loc[b["candidate"] == "propensity_ev_gbm", "fit_seconds"],
                           errors="coerce").mean()
        ratio = float(bt / nt) if nt and nt > 0 else float("nan")
        rows.append({
            "criterion": "K1 kill Bayesian complexity",
            "test": "Bayesian within 2 pts of best non-Bayesian AND >10x compute",
            "value": float(bay - nonbay),
            "threshold": 2.0,
            "compute_multiple": ratio,
            "triggered": bool((bay - nonbay) < 2.0 and (ratio or 0) > 10.0),
        })

    # K4: MMM. Split calibrated from uncalibrated, because an SMB that has
    # never run a geo test cannot have the calibrated version -- crediting the
    # method with a lift-test-calibrated score would answer a question nobody
    # asked.
    if len(mmm):
        m = mmm[mmm["status"] == "ok"]
        col = "regret_pct_b1.0"
        if col in m.columns:
            smb = m[
                m["regime"].isin(["mmm_smb_short_history", "mmm_very_short_history"])
                & (~m["candidate"].isin(["oracle"]))
            ]
            by_cand = pd.to_numeric(smb[col], errors="coerce").groupby(
                smb["candidate"]
            ).mean()
            uncal = by_cand[~by_cand.index.astype(str).str.contains("calibrated")]
            v_all = float(by_cand.min()) if len(by_cand) else float("nan")
            v_uncal = float(uncal.min()) if len(uncal) else float("nan")
            rows.append({
                "criterion": "K4 kill MMM for SMB (no experiments)",
                "test": "best UNCALIBRATED MMM regret at SMB data sizes > 10%",
                "value": v_uncal,
                "threshold": 10.0,
                "triggered": bool(v_uncal > 10.0),
            })
            rows.append({
                "criterion": "K4b MMM for SMB WITH lift tests",
                "test": "best MMM regret including experiment-calibrated variants > 10%",
                "value": v_all,
                "threshold": 10.0,
                "triggered": bool(v_all > 10.0),
            })
        # The question a buyer actually cares about: does the model beat simply
        # splitting the budget evenly? `pct_of_oracle_gain` is normalised so
        # equal allocation scores 0 and the Oracle scores 100.
        gcol = "pct_of_oracle_gain_b1.0"
        if gcol in m.columns:
            g = pd.to_numeric(m[gcol], errors="coerce").groupby(m["candidate"]).mean()
            g = g.drop(labels=[c for c in ("oracle", "equal_allocation") if c in g.index])
            uncal_g = g[~g.index.astype(str).str.contains("calibrated")]
            best_uncal = float(uncal_g.max()) if len(uncal_g) else float("nan")
            rows.append({
                "criterion": "K4c uncalibrated MMM barely beats an equal split",
                "test": "best uncalibrated MMM captures < 25% of the gain an "
                        "Oracle has over equal allocation",
                "value": best_uncal,
                "threshold": 25.0,
                "triggered": bool(best_uncal < 25.0),
            })
    return pd.DataFrame(rows)


def _plot_pareto(all_c: pd.DataFrame, frontier: pd.DataFrame, path: Path) -> None:
    if all_c.empty:
        return
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.scatter(all_c["fit_seconds"], all_c["mean"], s=28, alpha=0.7)
    for _, r in all_c.iterrows():
        ax.annotate(r["candidate"], (r["fit_seconds"], r["mean"]),
                    fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    if len(frontier):
        f = frontier.sort_values("fit_seconds")
        ax.plot(f["fit_seconds"], f["mean"], "r--", lw=1.2, label="Pareto frontier")
        ax.legend(fontsize=8)
    ax.set_xscale("symlog", linthresh=0.05)
    ax.set_xlabel("mean fit seconds per scenario (log scale)")
    ax.set_ylabel("% of Oracle's achievable gain")
    ax.set_title("Is the extra compute buying anything?")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def _plot_regime_bars(lead: pd.DataFrame, path: Path) -> None:
    ok = lead[lead["status"] == "ok"]
    if not len(ok):
        return
    keep = ["random", "hist_profit_per_agent_hour", "lead_score_gbm",
            "propensity_ev_gbm", "t_learner", "dr_learner", "causal_forest"]
    d = ok[ok["candidate"].isin(keep)]
    if not len(d):
        return
    piv = d.pivot_table(index="regime", columns="candidate",
                        values="pct_of_oracle_incremental", aggfunc="mean")
    piv = piv.reindex(columns=[c for c in keep if c in piv.columns])
    ax = piv.plot(kind="barh", figsize=(11, max(5, 0.45 * len(piv))), width=0.8)
    ax.set_xlabel("% of Oracle's achievable gain over do-nothing")
    ax.set_ylabel("")
    ax.set_title("Lead track: share of the achievable gain captured, by regime")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def _plot_curve(board: pd.DataFrame, xcol: str, xlabel: str, path: Path,
                logx: bool = False) -> None:
    if not len(board) or xcol not in board.columns:
        return
    regimes = board["regime"].unique()
    fig, axes = plt.subplots(1, len(regimes), figsize=(5.2 * len(regimes), 4.2), squeeze=False)
    for ax, r in zip(axes[0], regimes):
        sub = board[board["regime"] == r]
        for cand, g in sub.groupby("candidate"):
            g = g.sort_values(xcol)
            ax.plot(g[xcol], g["mean"], marker="o", ms=3.5, label=cand, lw=1.4)
            ax.fill_between(g[xcol], g["ci_low"], g["ci_high"], alpha=0.12)
        if logx:
            ax.set_xscale("log")
        ax.set_title(r, fontsize=9)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel("% of Oracle achievable gain", fontsize=8)
        ax.grid(alpha=0.3)
    axes[0][-1].legend(fontsize=6.5)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def _plot_coverage(lead: pd.DataFrame, path: Path) -> None:
    ok = lead[(lead["status"] == "ok") & lead.get("coverage_80", pd.Series(dtype=float)).notna()]
    if not len(ok):
        return
    cols = [c for c in ("coverage_80", "p_coverage_80") if c in ok.columns]
    if not cols:
        return
    fig, ax = plt.subplots(figsize=(8, 4.2))
    d = ok.groupby("candidate")[cols].mean().dropna(how="all")
    if not len(d):
        plt.close()
        return
    d.plot(kind="bar", ax=ax)
    ax.axhline(0.80, color="k", ls="--", lw=1, label="nominal 80%")
    ax.set_ylabel("empirical coverage of the stated 80% interval")
    ax.set_title("Are the intervals honest? EV vs outcome probability")
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def _plot_mmm(board: pd.DataFrame, path: Path) -> None:
    col = "regret_pct_b1.0"
    if col not in board.columns:
        return
    piv = board.pivot_table(index="regime", columns="candidate", values=col, aggfunc="mean")
    ax = piv.plot(kind="barh", figsize=(10, max(4, 0.6 * len(piv))), width=0.8)
    ax.set_xlabel("budget-allocation regret (% of Oracle revenue)")
    ax.set_title("MMM track: regret at current total spend")
    ax.legend(fontsize=7)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


if __name__ == "__main__":
    sys.exit(main())
