#!/usr/bin/env python
"""Google Meridian adapter, run in an isolated Python 3.12 environment.

Meridian requires Python >=3.12 (via its TensorFlow-Probability stack) while
the main benchmark environment is 3.11, so it is invoked as a subprocess
rather than imported. This is the "isolate the competitor that needs another
runtime" case from section 56 -- one extra process, not a microservice circus.

Contract (deliberately dumb, so the boundary is easy to test):

    in :  --data <csv>  --channels a,b,c  --out <json>
    out:  {"grid_multipliers": [...],
           "grid_response":    [[per-channel per-period contribution], ...],
           "roi":              [...],
           "n_periods":        int,
           "mean_spend":       [...]}

``grid_response[i][c]`` is the per-period incremental outcome attributable to
channel ``c`` when its spend is held at ``grid_multipliers[i] * mean_spend[c]``.
That is the same steady-state response curve every other MMM candidate
exposes, so the shared budget optimiser can consume it unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--channels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--tune", type=int, default=400)
    ap.add_argument("--chains", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-multiple", type=float, default=3.0)
    ap.add_argument("--n-grid", type=int, default=21)
    args = ap.parse_args()

    channels = args.channels.split(",")
    df = pd.read_csv(args.data, parse_dates=["date"])

    from meridian import constants
    from meridian.analysis import analyzer
    from meridian.data import data_frame_input_data_builder as dfb
    from meridian.model import model, spec

    # Meridian wants long-ish tidy input: one row per (geo, time) with media
    # spend columns. This benchmark's MMM DGP is national, so a single geo.
    frame = pd.DataFrame(
        {
            "geo": "national",
            "time": df["date"].dt.strftime("%Y-%m-%d"),
            "revenue": df["revenue"].astype(float),
            "price_index": df["price_index"].astype(float),
            "promo": df["promo"].astype(float),
        }
    )
    for c in channels:
        frame[f"{c}_spend"] = df[f"spend_{c}"].astype(float)
        # With no impression data, spend doubles as the media execution
        # variable. Meridian supports this; ROI priors then act on spend.
        frame[f"{c}_impressions"] = df[f"spend_{c}"].astype(float)

    builder = (
        dfb.DataFrameInputDataBuilder(kpi_type=constants.REVENUE)
        .with_kpi(frame, kpi_col="revenue")
        .with_controls(frame, control_cols=["price_index", "promo"])
        .with_media(
            frame,
            media_cols=[f"{c}_impressions" for c in channels],
            media_spend_cols=[f"{c}_spend" for c in channels],
            media_channels=channels,
        )
    )
    input_data = builder.build()

    mmm = model.Meridian(input_data=input_data, model_spec=spec.ModelSpec())
    mmm.sample_prior(500, seed=args.seed)
    mmm.sample_posterior(
        n_chains=args.chains,
        n_adapt=args.tune,
        n_burnin=args.tune,
        n_keep=args.draws,
        seed=args.seed,
    )

    an = analyzer.Analyzer(mmm)
    n_periods = len(df)
    mean_spend = np.array([float(df[f"spend_{c}"].mean()) for c in channels])

    mults = np.linspace(0.0, args.max_multiple, args.n_grid)
    # response_curves returns total incremental outcome over the modelled
    # window for each spend multiplier; divide by the window length to get the
    # per-period steady-state contribution the optimiser expects.
    rc = an.response_curves(spend_multipliers=list(mults), by_reach=False)
    arr = rc["incremental_outcome"]
    dims = list(arr.dims)
    reduce_dims = [d for d in dims if d in ("chain", "draw", "metric")]
    if reduce_dims:
        if "metric" in reduce_dims:
            arr = arr.sel(metric="mean") if "mean" in list(arr.coords.get("metric", [])) else arr.mean(dim="metric")
            reduce_dims = [d for d in reduce_dims if d != "metric"]
        if reduce_dims:
            arr = arr.mean(dim=reduce_dims)
    ch_coord = "channel" if "channel" in arr.dims else arr.dims[-1]
    mult_coord = [d for d in arr.dims if d != ch_coord][0]
    grid = np.zeros((len(mults), len(channels)))
    for i in range(len(mults)):
        for j, c in enumerate(channels):
            try:
                grid[i, j] = float(arr.isel({mult_coord: i}).sel({ch_coord: c}))
            except Exception:
                grid[i, j] = float(arr.isel({mult_coord: i}).isel({ch_coord: j}))
    grid = grid / n_periods

    try:
        roi = np.asarray(an.roi().mean(dim=("chain", "draw"))).ravel().tolist()
    except Exception:
        with np.errstate(divide="ignore", invalid="ignore"):
            base = grid[np.argmin(np.abs(mults - 1.0))]
            roi = (base / np.maximum(mean_spend, 1e-9)).tolist()

    out = {
        "grid_multipliers": mults.tolist(),
        "grid_response": grid.tolist(),
        "roi": roi,
        "n_periods": int(n_periods),
        "mean_spend": mean_spend.tolist(),
        "channels": channels,
    }
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"meridian: wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
