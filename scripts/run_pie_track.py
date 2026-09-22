#!/usr/bin/env python
"""Campaign-level incrementality track: PyMC-Marketing's PIE against baselines.

Why this is a *separate* track (section 17). PIE — "Predicted Incrementality
by Experimentation" — does not score leads. It fits a BART model on the corpus
of campaigns that *did* run an incrementality experiment (geo test, ghost-ad
holdout), learning the map from campaign features to **measured
incrementality**, and then predicts a posterior incrementality for campaigns
that never ran a test. The unit of analysis is a campaign, the training label
is an experimental readout, and the deliverable is a transfer/meta-learning
estimate. Presenting it as per-lead uplift scoring would be simply wrong.

So the question this track asks is PIE's own claim, not ours:

  Given a corpus of campaigns where only some ran experiments, can you predict
  the incrementality of the rest better than (a) assuming the average, (b)
  believing last-click ROAS, or (c) an ordinary regression on the same
  features?

Runs in the isolated Python 3.12 environment, because `pymc_marketing.pie`
exists only in pymc-marketing >=1.x which requires Python >=3.12, and the
module is explicitly marked alpha ("the API and defaults may change between
releases").

    .venv312/bin/python scripts/run_pie_track.py --out reports/runs/pie/results.csv
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats

VERTICALS = ["lending", "insurance", "solar", "home_services", "legal", "real_estate"]
OBJECTIVES = ["prospecting", "retargeting", "brand"]
CHANNELS = ["paid_search", "paid_social", "display", "video", "retargeting"]

# Last-touch credit inflation by channel: retargeting claims far more than it
# causes, which is the whole reason anyone wants an incrementality model.
ATTRIBUTION_BIAS = {
    "paid_search": 1.15,
    "paid_social": 1.35,
    "display": 0.85,
    "video": 0.95,
    "retargeting": 3.20,
}


def generate_campaign_corpus(
    n_campaigns: int = 400,
    share_measured: float = 0.35,
    seed: int = 0,
    interactions: bool = False,
) -> pd.DataFrame:
    """A corpus of campaigns, a minority of which ran an incrementality test.

    ``interactions=False`` makes true incrementality additive in the (logged)
    campaign features. That is a **best case for a linear model**: a ridge on
    log-budget, log-audience, creative age and one-hot categoricals is then
    correctly specified, and beating it says little about BART.

    ``interactions=True`` adds channel x vertical interactions, a non-monotone
    effect of creative age, and a budget x exposure interaction, so the
    incrementality surface is genuinely non-additive and a tree ensemble has
    something to find. Both variants are reported, because the honest question
    is not "does BART win?" but "under what shape of truth does it win?".
    """
    rng = np.random.default_rng(seed)
    vertical = rng.choice(VERTICALS, n_campaigns)
    objective = rng.choice(OBJECTIVES, n_campaigns, p=[0.5, 0.3, 0.2])
    channel = rng.choice(CHANNELS, n_campaigns)
    budget = np.exp(rng.normal(np.log(30_000), 0.8, n_campaigns))
    exposure_rate = rng.beta(2, 3, n_campaigns)
    audience_size = np.exp(rng.normal(np.log(250_000), 0.9, n_campaigns))
    creative_age_days = rng.integers(1, 180, n_campaigns)

    # True incremental ROAS. Driven by channel and objective, damped by
    # saturation at large budgets and by creative fatigue.
    base = pd.Series(channel).map(
        {"paid_search": 1.45, "paid_social": 1.15, "display": 0.55,
         "video": 0.80, "retargeting": 0.35}
    ).to_numpy()
    obj = pd.Series(objective).map(
        {"prospecting": 0.15, "retargeting": -0.30, "brand": -0.05}
    ).to_numpy()
    vert = pd.Series(vertical).map(
        {v: s for v, s in zip(VERTICALS, [0.25, 0.10, -0.05, 0.05, -0.15, 0.0])}
    ).to_numpy()
    saturation = -0.22 * (np.log(budget) - np.log(30_000))
    fatigue = -0.0012 * creative_age_days
    reach = 0.30 * (exposure_rate - 0.4)
    extra = np.zeros(n_campaigns)
    if interactions:
        # Prospecting works in lending and insurance but not in legal;
        # retargeting decays much faster with creative age; big budgets only
        # pay off when exposure is high.
        pair = pd.Series(list(zip(objective, vertical))).map(
            lambda p: 0.45 if p == ("prospecting", "lending")
            else 0.35 if p == ("prospecting", "insurance")
            else -0.40 if p == ("prospecting", "legal")
            else -0.25 if p == ("retargeting", "solar")
            else 0.0
        ).to_numpy()
        age_kink = np.where(
            (pd.Series(channel) == "retargeting").to_numpy(),
            -0.004 * np.maximum(creative_age_days - 30, 0),
            0.0,
        )
        budget_x_reach = 0.55 * (np.log(budget) - np.log(30_000)) * (exposure_rate - 0.4)
        extra = pair + age_kink + budget_x_reach
    true_iroas = np.maximum(
        base + obj + vert + saturation + fatigue + reach + extra
        + rng.normal(0, 0.12, n_campaigns),
        0.01,
    )

    # Which campaigns ran an experiment, and how precise that readout was.
    # Bigger budgets buy more statistical power, so the measured subset is
    # both non-random and unevenly precise -- exactly the real situation.
    p_measured = share_measured * (0.5 + 0.5 * (budget > np.median(budget)))
    measured = rng.random(n_campaigns) < np.clip(p_measured, 0, 1)
    se = 0.45 * np.sqrt(30_000 / budget)
    measured_iroas = np.where(measured, true_iroas + rng.normal(0, se), np.nan)

    # What the ad platform reports (last-touch), available for every campaign.
    bias = pd.Series(channel).map(ATTRIBUTION_BIAS).to_numpy()
    reported_roas = true_iroas * bias * np.exp(rng.normal(0, 0.15, n_campaigns))

    return pd.DataFrame(
        {
            "campaign_id": np.arange(n_campaigns),
            "vertical": vertical,
            "objective": objective,
            "channel": channel,
            "budget": budget,
            "exposure_rate": exposure_rate,
            "audience_size": audience_size,
            "creative_age_days": creative_age_days,
            "reported_roas": reported_roas,
            "measured": measured,
            "measured_iroas": measured_iroas,
            "measurement_se": np.where(measured, se, np.nan),
            "true_iroas": true_iroas,
        }
    )


FEATURES_PRE = ["objective", "vertical", "channel", "budget", "audience_size",
                "creative_age_days"]
FEATURES_POST = ["exposure_rate"]


def _design(df: pd.DataFrame) -> np.ndarray:
    from sklearn.preprocessing import OneHotEncoder

    cats = df[["objective", "vertical", "channel"]].astype(str)
    enc = _design.enc
    if enc is None:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        enc.fit(cats)
        _design.enc = enc
    num = np.column_stack([
        np.log(df["budget"].to_numpy()),
        np.log(df["audience_size"].to_numpy()),
        df["creative_age_days"].to_numpy(dtype=float),
        df["exposure_rate"].to_numpy(dtype=float),
    ])
    return np.column_stack([enc.transform(cats), num])


_design.enc = None


def _metrics(name: str, pred: np.ndarray, truth: np.ndarray, budget: np.ndarray) -> dict:
    ok = np.isfinite(pred) & np.isfinite(truth)
    pred, truth_ok, budget_ok = pred[ok], truth[ok], budget[ok]
    rmse = float(np.sqrt(np.mean((pred - truth_ok) ** 2)))
    mae = float(np.mean(np.abs(pred - truth_ok)))
    rho = float(stats.spearmanr(truth_ok, pred).statistic) if np.std(pred) > 1e-9 else float("nan")

    # Decision metric: put the whole budget into the top-quartile campaigns by
    # predicted incrementality, and score with the true incrementality.
    k = max(1, int(0.25 * len(pred)))
    chosen = np.argsort(-pred)[:k]
    best = np.argsort(-truth_ok)[:k]
    worst = np.argsort(truth_ok)[:k]
    realized = float(np.average(truth_ok[chosen], weights=budget_ok[chosen]))
    oracle = float(np.average(truth_ok[best], weights=budget_ok[best]))
    floor = float(np.average(truth_ok[worst], weights=budget_ok[worst]))
    captured = (
        100.0 * (realized - floor) / (oracle - floor) if oracle - floor > 1e-9 else float("nan")
    )
    return {
        "candidate": name,
        "rmse": rmse,
        "mae": mae,
        "spearman": rho,
        "top_quartile_true_iroas": realized,
        "oracle_top_quartile_iroas": oracle,
        "pct_of_oracle_selection": captured,
    }


def run_once(seed: int, n_campaigns: int, share_measured: float,
             draws: int, tune: int, interactions: bool = False) -> pd.DataFrame:
    df = generate_campaign_corpus(n_campaigns, share_measured, seed, interactions)
    train = df[df["measured"]].reset_index(drop=True)
    test = df[~df["measured"]].reset_index(drop=True)
    if len(train) < 30 or len(test) < 30:
        raise RuntimeError("corpus too small after the measured/unmeasured split")

    truth = test["true_iroas"].to_numpy()
    budget = test["budget"].to_numpy()
    rows = []

    # -- baseline 1: assume every campaign is average ----------------------
    rows.append(_metrics("global_mean_measured",
                         np.full(len(test), train["measured_iroas"].mean()), truth, budget))

    # -- baseline 2: believe the platform's last-touch ROAS ----------------
    rows.append(_metrics("reported_roas", test["reported_roas"].to_numpy(), truth, budget))

    # -- baseline 3: ordinary regression on the same features --------------
    _design.enc = None
    Xtr = _design(train)
    Xte = _design(test)
    ytr = train["measured_iroas"].to_numpy()

    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import RidgeCV

    ridge = RidgeCV(alphas=np.logspace(-3, 3, 25)).fit(Xtr, ytr)
    rows.append(_metrics("ridge_on_features", ridge.predict(Xte), truth, budget))

    gbm = HistGradientBoostingRegressor(max_iter=300, max_depth=4, random_state=seed)
    gbm.fit(Xtr, ytr)
    rows.append(_metrics("gbm_on_features", gbm.predict(Xte), truth, budget))

    # -- PIE ----------------------------------------------------------------
    from pymc_marketing.pie import PIEModel

    model = PIEModel(
        pre_determined_features=FEATURES_PRE,
        post_determined_features=FEATURES_POST,
    )
    Xtr_df = train[FEATURES_PRE + FEATURES_POST]
    Xte_df = test[FEATURES_PRE + FEATURES_POST]
    model.fit(Xtr_df, pd.Series(ytr), random_seed=seed,
              draws=draws, tune=tune, chains=2, progressbar=False)
    pie_pred = np.asarray(model.predict(Xte_df)).ravel()
    rows.append(_metrics("pie_bart", pie_pred, truth, budget))

    out = pd.DataFrame(rows)
    out["seed"] = seed
    out["n_campaigns"] = n_campaigns
    out["share_measured"] = share_measured
    out["interactions"] = interactions
    out["n_train"] = len(train)
    out["n_test"] = len(test)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports/runs/pie/results.csv")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--n-campaigns", type=int, default=400)
    ap.add_argument("--shares", default="0.15,0.35,0.60")
    ap.add_argument("--draws", type=int, default=300)
    ap.add_argument("--tune", type=int, default=300)
    ap.add_argument("--interactions", action="store_true",
                    help="non-additive incrementality surface, so BART has something to find")
    args = ap.parse_args()

    frames = []
    for share in [float(s) for s in args.shares.split(",")]:
        for seed in range(args.seeds):
            try:
                r = run_once(seed, args.n_campaigns, share, args.draws, args.tune,
                             args.interactions)
                r["status"] = "ok"
                frames.append(r)
                best = r.sort_values("rmse").iloc[0]
                print(f"  pie share={share:.2f} seed={seed}: best={best['candidate']} "
                      f"rmse={best['rmse']:.3f} | pie rmse="
                      f"{r.loc[r.candidate == 'pie_bart', 'rmse'].iloc[0]:.3f}")
            except Exception as exc:  # noqa: BLE001
                print(f"  !! pie share={share} seed={seed} failed: {type(exc).__name__}: {exc}")
                frames.append(pd.DataFrame([{
                    "candidate": "pie_bart", "seed": seed, "share_measured": share,
                    "status": f"error: {type(exc).__name__}: {exc}",
                }]))
    out = pd.concat(frames, ignore_index=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"wrote {args.out} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
