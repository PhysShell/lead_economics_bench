#!/usr/bin/env python
"""Score the incumbent policy: replay what the business actually did.

Section 74 asks for the existing business policy to be treated as a full
competitor rather than as "the thing we obviously beat". On synthetic data the
logged action *is* the incumbent's decision, so its realized value can be
computed exactly, without fitting anything, for every (regime, seed) cell.

Two variants are produced:

``existing_policy_replay``
    Do exactly what was logged. Under a binding capacity this is truncated by
    the evaluator like any other plan, dropping in arrival order.

``existing_policy_capped``
    The same ranking, but with the plan trimmed to fit capacity *before*
    execution — a sales manager who knows the day is only so long.

    python scripts/add_incumbent_baseline.py --runs reports/runs/lead
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

from leadbench.economics import (  # noqa: E402
    Constraints,
    capacity_for_ratio,
    control_everything_value,
    realized_net_value,
)
from leadbench.evaluation.runner import ScenarioSpec, _oracle_value  # noqa: E402
from leadbench.evaluation.splits import (  # noqa: E402
    drop_cross_split_duplicates,
    temporal_split,
)
from leadbench.metrics.economic import economic_summary  # noqa: E402
from leadbench.policies.decision import enforce_true_capacity  # noqa: E402
from leadbench.synthetic.dgp import generate  # noqa: E402


def incumbent_rows(regime: str, n_leads: int, capacity_ratio: float, seed: int) -> list[dict]:
    spec = ScenarioSpec(
        name=f"lead_{regime}",
        regime=regime,
        n_leads=n_leads,
        capacity_ratio=capacity_ratio,
        seeds=(seed,),
    )
    ds = generate(spec.config(seed))
    split = drop_cross_split_duplicates(temporal_split(ds, spec.train_frac, spec.valid_frac))
    test = split.test
    cap = capacity_for_ratio(test, capacity_ratio) if capacity_ratio is not None else None
    cons = Constraints(agent_minutes=cap)

    floor = control_everything_value(test)
    oracle = _oracle_value(test, cons)
    true_minutes = np.column_stack(
        [test.truth[f"minutes_a{a}"].to_numpy() for a in range(test.n_actions)]
    )
    logged = test.observed["action"].to_numpy(dtype=int)

    out = []
    # Arrival order is the tie-break a real floor uses when the day runs out.
    arrival_priority = -test.observed["created_day"].to_numpy(dtype=float)
    for name, priority in [
        ("existing_policy_replay", arrival_priority),
        # A manager who trims the list by the campaign-level profit they can see.
        ("existing_policy_capped", _campaign_profit_priority(split.train.observed, test)),
    ]:
        actions, info = enforce_true_capacity(true_minutes, logged.copy(), priority, cons)
        outcome = realized_net_value(test, actions)
        row = {
            "scenario": spec.name,
            "regime": regime,
            "n_leads": n_leads,
            "capacity_ratio": capacity_ratio,
            "seed": seed,
            "candidate": name,
            "family": "incumbent",
            "tags": "incumbent",
            "allocation_mode": "replay",
            "policy": "replay",
            "status": "ok",
            "fit_seconds": 0.0,
            "predict_seconds": 0.0,
        }
        row.update(
            economic_summary(outcome, floor, oracle_value=oracle, capacity_minutes=cap)
        )
        row["share_treated"] = float((actions != 0).mean())
        row.update({f"cap_{k}": v for k, v in info.items()})
        out.append(row)
    return out


def _campaign_profit_priority(train: pd.DataFrame, test) -> np.ndarray:
    """Campaign-level historical net profit per lead, as a manager would see it."""
    t = train.copy()
    t["_net"] = t["realized_net_contribution"].fillna(0.0) - t["cpl"]
    lut = t.groupby("campaign_id", observed=True)["_net"].mean()
    return (
        test.observed["campaign_id"]
        .map(lut)
        .fillna(float(t["_net"].mean()))
        .to_numpy(dtype=float)
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", default="reports/runs/lead")
    args = ap.parse_args()
    path = Path(args.runs) / "results.csv"
    if not path.exists():
        print(f"no results at {path}")
        return 1
    df = pd.read_csv(path)
    have = set(df.loc[df["candidate"].astype(str).str.startswith("existing_policy"), "scenario"])
    cells = (
        df[["regime", "n_leads", "capacity_ratio", "seed"]]
        .drop_duplicates()
        .to_dict("records")
    )
    rows = []
    for c in cells:
        if f"lead_{c['regime']}" in have:
            continue
        try:
            rows += incumbent_rows(
                c["regime"], int(c["n_leads"]),
                None if pd.isna(c["capacity_ratio"]) else float(c["capacity_ratio"]),
                int(c["seed"]),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {c}: {type(exc).__name__}: {exc}")
    if not rows:
        print("nothing to add")
        return 0
    out = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(path, index=False)
    print(f"added {len(rows)} incumbent rows to {path} (now {len(out)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
