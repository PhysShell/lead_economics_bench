#!/usr/bin/env python
"""F8, closed by exclusion rather than by a failed significance test.

The hypothesis under test (H3) was that CausalPy's published point estimate
carries ~1.1-1.3% Monte Carlo noise **because** every published row is
`posterior_type = "y_hat"` -- the posterior predictive, whose mean includes
simulated observation noise -- while the `mu` variant, parameter uncertainty
only, would not.

The wrong way to end this
-------------------------
Run both, observe that the difference is not significant, and write "no
difference". This project has spent most of its length demonstrating why
that inference is poor; ending on it would be comic. `p > .05` is not
evidence of absence, and at n=13 it is barely evidence of anything.

The right way
-------------
The design is **paired**: the same 13 run identities produce both variants,
so the comparison is within-pair and the between-run variance cancels. That
supports an exclusion test rather than a null test::

    d_i = noise_i(mu) - noise_i(y_hat)      per run identity
    bootstrap CI on the paired mean of d

and then ask whether the CI excludes the reduction H3 predicts.

The margin is derived, not chosen for looking round
---------------------------------------------------
H3 is a claim about *magnitude*: the posterior-predictive layer is supposed
to explain the anomaly. For it to be a plausible explanation it would have
to account for a material share of the observed noise. We preregister that
share at **50%** -- a mechanism that explains less than half of a phenomenon
is not the explanation of it.

So the exclusion region is `d <= -0.5 * baseline`, where `baseline` is the
`y_hat` noise level. If the paired CI lies entirely above that, H3 is dead
**even at n=13**, because the effect it predicts is far larger than the
interval we can place.

What this cannot do
-------------------
It cannot show the two variants are identical. A small difference -- smaller
than the exclusion margin -- remains entirely possible and is not addressed.
The claim is bounded accordingly: H3 fails *as an explanation of the observed
magnitude*, not "posterior type has no effect".

    python marketing_experimentation/repro/recast/f8_equivalence.py \
        --results /home/user/donor-smoke/results/raw/results.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

#: The share of the observed noise H3 would have to explain to count as its
#: explanation. Fixed here before looking at the paired differences.
EXPLANATORY_SHARE = 0.50


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(line) for line in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    for c in ("att_level", "true_att_level"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def paired_noise(d: pd.DataFrame, scenario: str) -> pd.DataFrame:
    """Per-run determinism residual, for each posterior type, on shared keys.

    The metric is the same identity the probe uses:

        |att(effect) - att(null) - true_att|

    which is zero for an estimator that injects no noise of its own. It is
    computed per (scenario, iteration) so the pairing is exact.
    """
    cp = d[(d.tool == "causalpy") & (d.scenario == scenario)]
    out = {}
    for pt, g in cp.groupby("posterior_type"):
        eff = g[g.effect_pct != 0].set_index("iteration")
        nul = g[g.effect_pct == 0].set_index("iteration")
        if eff.index.duplicated().any() or nul.index.duplicated().any():
            raise SystemExit(
                f"duplicated iterations in posterior_type={pt!r} -- see D13")
        common = eff.index.intersection(nul.index)
        r = ((eff.loc[common].att_level - nul.loc[common].att_level)
             - eff.loc[common].true_att_level).abs()
        out[pt] = r
    if set(out) != {"mu", "y_hat"}:
        raise SystemExit(f"need both posterior types, found {sorted(out)}")
    both = pd.DataFrame(out).dropna()
    return both


def bootstrap_ci(x: np.ndarray, n: int = 20000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n, len(x)))
    means = x[idx].mean(axis=1)
    return (float(np.quantile(means, alpha / 2)),
            float(np.quantile(means, 1 - alpha / 2)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--scenario", default="A1")
    args = ap.parse_args()

    both = paired_noise(load(args.results), args.scenario)
    n = len(both)
    mu, yh = both["mu"].to_numpy(), both["y_hat"].to_numpy()
    d = mu - yh

    print(f"scenario {args.scenario} | {n} PAIRED run identities")
    print("metric: |att(effect) - att(null) - true_att| per run\n")
    print(f"  y_hat  mean {yh.mean():8.4f}   median {np.median(yh):8.4f}")
    print(f"  mu     mean {mu.mean():8.4f}   median {np.median(mu):8.4f}")

    baseline = float(yh.mean())
    margin = -EXPLANATORY_SHARE * baseline
    lo, hi = bootstrap_ci(d)

    print(f"\npaired difference d = noise(mu) - noise(y_hat)")
    print(f"  mean d           {d.mean():+8.4f}")
    print(f"  95% bootstrap CI [{lo:+.4f}, {hi:+.4f}]   (20,000 resamples "
          f"over the {n} pairs)")

    print(f"\nH3 predicts a reduction of at least {100*EXPLANATORY_SHARE:.0f}% "
          f"of the observed noise,")
    print(f"i.e. d <= {margin:+.4f}. Preregistered above, before looking.")

    excluded = lo > margin
    print(f"\n  CI lower bound {lo:+.4f} {'>' if excluded else '<='} "
          f"margin {margin:+.4f}")
    if excluded:
        print("\n  H3 EXCLUDED. The reduction it predicts lies entirely "
              "outside the\n  interval, so the posterior-predictive layer is "
              "not a material\n  explanation of the observed magnitude -- "
              f"even at n={n}, because the\n  effect predicted is far larger "
              "than the interval we can place.")
    else:
        print("\n  NOT EXCLUDED. The predicted reduction is still inside the "
              "interval;\n  more pairs are needed before H3 can be ruled out.")

    print(f"\n  What this does NOT show: that the two variants are identical.")
    print(f"  A difference smaller than {abs(margin):.4f} remains entirely")
    print(f"  possible and is not addressed by this test.")

    # Relative form, easier to carry into prose.
    rel = 100 * d.mean() / baseline
    rlo, rhi = 100 * lo / baseline, 100 * hi / baseline
    print(f"\n  in relative terms: mu changes the noise by {rel:+.1f}% "
          f"[{rlo:+.1f}%, {rhi:+.1f}%]")
    print(f"  against the {-100*EXPLANATORY_SHARE:.0f}% H3 would require.")


if __name__ == "__main__":
    main()
