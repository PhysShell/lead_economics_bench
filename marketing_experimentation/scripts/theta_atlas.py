#!/usr/bin/env python
"""The shape of p(S | theta): what each tool's output distribution does as the
truth moves.

Everything in this track so far rests on two truths, theta in {0, +7.5%},
because that is all Recast simulated. Two points cannot show a bias that
grows with effect size, an estimator that fails on negative effects, a
variance that moves with the signal, or a decision boundary that sits
between them. This reads the atlas.

Five questions, in the order they can invalidate what came before
--------------------------------------------------------------------
1. PATHOLOGY   Does any tool fail (NaN, non-convergence) at some theta and
               not others? A tool that quietly drops out on negative effects
               would make every aggregate comparison conditional on the sign
               of the truth.
2. BIAS        Is E[att_hat] - theta flat in theta, or does it grow? Flat
               means an offset; growing means a scale error; neither is
               visible with two points, and they imply different fixes.
3. VARIANCE    Does SD(att_hat) move with theta? If it does, an interval
               calibrated at one effect size is miscalibrated at another --
               and a significance threshold tuned on +7.5% is not the same
               test at +2%.
4. SYMMETRY    Are errors symmetric about zero? A method built on a
               "lift" framing can be quietly one-sided, and a marketing
               decision cares most about the negative half: the question is
               often whether a channel destroys money, not how much it makes.
5. LADDER      Does the S0 -> S1 compression tax survive more than two
               truths? This is the headline result of the track and the one
               with the most to lose.

    python marketing_experimentation/scripts/theta_atlas.py \
        --results /home/user/donor-smoke/results/raw/results.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load(path: str) -> pd.DataFrame:
    d = pd.DataFrame([json.loads(l) for l in Path(path).open()])
    if "posterior_type" not in d.columns:
        d["posterior_type"] = ""
    d["posterior_type"] = d["posterior_type"].fillna("")
    d["tool_label"] = d.tool + d.posterior_type.map(lambda s: f"[{s}]" if s else "")
    # theta comes from the data, never from the arm label -- D7 is precisely
    # the failure of reading a magnitude off a label.
    d["theta_pct"] = d.effect_pct.astype(float) * 100
    d["att_pct_100"] = pd.to_numeric(d.att_pct, errors="coerce") * 100
    d["ci_width"] = (pd.to_numeric(d.ci_upper, errors="coerce")
                     - pd.to_numeric(d.ci_lower, errors="coerce")) * 100
    d["err"] = d.att_pct_100 - d.theta_pct
    return d


def q1_pathology(d: pd.DataFrame) -> pd.DataFrame:
    """Failure rate per (tool, theta). A tool that drops out at some theta
    makes every pooled comparison conditional on the truth."""
    g = d.groupby(["tool_label", "theta_pct"]).apply(
        lambda x: pd.Series({
            "n": len(x),
            "nan_pct": 100 * x.att_pct_100.isna().mean(),
            "nonconv_pct": (100 * (~x.converged.fillna(True).astype(bool)).mean()
                            if "converged" in x.columns else 0.0),
        }), include_groups=False)
    return g.reset_index()


def q2_q3_q4(d: pd.DataFrame) -> pd.DataFrame:
    """Bias, spread and skew of the error, per (tool, theta)."""
    ok = d[d.att_pct_100.notna()]
    g = ok.groupby(["tool_label", "theta_pct"]).apply(
        lambda x: pd.Series({
            "n": len(x),
            "bias": x.err.mean(),
            "se_bias": x.err.std(ddof=1) / max(np.sqrt(len(x)), 1),
            "sd": x.err.std(ddof=1),
            "skew": x.err.skew(),
            "ci_width": x.ci_width.median(),
            "sig_rate": 100 * x.significant.astype(bool).mean(),
            "coverage": (100 * x.coverage.astype(bool).mean()
                         if "coverage" in x.columns else np.nan),
        }), include_groups=False)
    return g.reset_index()


def report_bias_shape(s: pd.DataFrame) -> None:
    """Flat bias is an offset; bias growing in theta is a scale error."""
    print("\n== Q2: is bias flat in theta (offset) or growing (scale error)? ==")
    print("   slope of bias on theta, by OLS. |slope| near 0 => offset only.\n")
    for tool, g in s.groupby("tool_label"):
        g = g.sort_values("theta_pct")
        if len(g) < 3:
            print(f"  {tool:18s} needs >=3 theta values, have {len(g)}")
            continue
        x, y = g.theta_pct.to_numpy(), g.bias.to_numpy()
        slope, intercept = np.polyfit(x, y, 1)
        # A scale error of s means att_hat ~ (1+s)*theta, so bias slope == s.
        verdict = ("offset only" if abs(slope) < 0.02 else
                   f"SCALE ERROR: att_hat ~ {1 + slope:.3f} x theta")
        print(f"  {tool:18s} slope {slope:+.4f}  intercept {intercept:+.4f}pp"
              f"   {verdict}")


def report_variance_shape(s: pd.DataFrame) -> None:
    """Two questions that an earlier version of this file ran together.

    Heteroskedasticity does not imply miscalibration. An estimator can have
    SD 2pp at theta = 0 and 5pp at theta = 15% and hold 95% coverage at both,
    provided its interval procedure adapts. The earlier text said a moving SD
    meant "an interval calibrated at one effect size is miscalibrated at
    another", which does not follow.

    They are separated because they have different consequences:

      A  variance moves with theta   -> the LIKELIHOOD is heteroskedastic, so
                                        a constant-sigma model of p(y|theta)
                                        is wrong. This is what
                                        `continuous_ladder.py --mode smooth`
                                        currently assumes, so A decides
                                        whether that assumption is admissible.
      B  coverage moves with theta   -> a CALIBRATION problem in the tool.
    """
    print("\n== Q3a: does estimator variance move with theta? ==")
    print("   consequence: a constant-sigma likelihood model is inadmissible\n")
    for tool, g in s.groupby("tool_label"):
        g = g.sort_values("theta_pct")
        sd = g.sd.to_numpy()
        if len(sd) < 2 or not np.isfinite(sd).all():
            continue
        rng = sd.max() / sd.min() if sd.min() > 0 else np.inf
        flag = ("flat -- constant sigma admissible" if rng < 1.15
                else "MOVES -- model s(theta)")
        print(f"  {tool:18s} SD {sd.min():.3f}-{sd.max():.3f}pp  "
              f"ratio {rng:.2f}  {flag}")

    print("\n== Q3b: does INTERVAL COVERAGE move with theta? ==")
    print("   a different question: heteroskedasticity is not miscalibration.")
    print("   An estimator whose SD grows with theta can still hold 95%\n"
          "   coverage everywhere, if its interval adapts.\n")
    if "coverage" not in s.columns or s.coverage.isna().all():
        print("   coverage not available in this dataset")
        return
    for tool, g in s.groupby("tool_label"):
        g = g.sort_values("theta_pct")
        cov = g.coverage.to_numpy(dtype=float)
        if len(cov) < 2 or not np.isfinite(cov).all():
            continue
        spread = cov.max() - cov.min()
        flag = ("stable" if spread < 5 else "MOVES -- calibration depends on "
                "the truth")
        print(f"  {tool:18s} coverage {cov.min():.1f}-{cov.max():.1f}%  "
              f"spread {spread:.1f}pp  {flag}")


def report_sign_dependence(d: pd.DataFrame, s: pd.DataFrame) -> None:
    """Sign-dependent behaviour, NOT symmetry.

    An earlier version averaged bias over all negative theta and over all
    positive theta and called the comparison a symmetry test. It is not one:
    the grid is {-10, -5} against {+2, +5, +7.5, +15}, and those halves are
    not mirror images, so a difference between their averages says as much
    about which magnitudes were simulated as about the estimator.

    Symmetry needs MATCHED PAIRS, +x against -x. Where such pairs exist in
    the grid they are tested; where they do not, the weaker sign-dependence
    question is reported and labelled as such.
    """
    print("\n== Q4: sign-dependent behaviour ==")
    neg = sorted(t for t in d.theta_pct.unique() if t < 0)
    pos = sorted(t for t in d.theta_pct.unique() if t > 0)
    if not neg:
        print("   NO NEGATIVE THETA IN THIS DATA -- the question cannot be\n"
              "   asked. A marketing decision cares most about the negative\n"
              "   half, so this is a gap, not an absence of evidence.")
        return
    print(f"   negative theta: {neg}   positive: {pos}")

    pairs = [(n, p) for n in neg for p in pos if abs(abs(n) - p) < 1e-9]
    if pairs:
        print(f"\n   MATCHED PAIRS present: "
              f"{[(f'{n:+.1f}', f'{p:+.1f}') for n, p in pairs]}")
        print("   a true symmetry test is available on these.\n")
        for tool, g in s.groupby("tool_label"):
            for n, p in pairs:
                rn = g[np.isclose(g.theta_pct, n)]
                rp = g[np.isclose(g.theta_pct, p)]
                if rn.empty or rp.empty:
                    continue
                bn, bp = float(rn.bias.iloc[0]), float(rp.bias.iloc[0])
                en = float(rn.se_bias.iloc[0]); ep = float(rp.se_bias.iloc[0])
                se = np.hypot(en, ep)
                # Symmetric estimator: bias(-x) = -bias(+x), so bias sums to 0.
                z = (bn + bp) / se if se > 0 else np.nan
                flag = ("symmetric" if abs(z) < 2 else
                        "ASYMMETRIC -- bias does not mirror")
                print(f"  {tool:18s} {n:+.1f}/{p:+.1f}  bias {bn:+.3f} / "
                      f"{bp:+.3f}  sum {bn+bp:+.3f} (z={z:+.2f})  {flag}")
    else:
        print("\n   no matched +x / -x pairs in this grid, so SYMMETRY CANNOT\n"
              "   BE TESTED. Reporting the weaker sign-dependence comparison,\n"
              "   which confounds sign with the magnitudes that were "
              "simulated.\n")

    print("\n   sign-dependence (weaker: the halves are not mirror images)")
    for tool, g in s.groupby("tool_label"):
        gn, gp = g[g.theta_pct < 0], g[g.theta_pct > 0]
        if gn.empty or gp.empty:
            continue
        print(f"  {tool:18s} bias neg {gn.bias.mean():+.3f} / "
              f"pos {gp.bias.mean():+.3f}   "
              f"SD neg {gn.sd.mean():.3f} / pos {gp.sd.mean():.3f}   "
              f"skew {g.skew.mean():+.2f}")


def report_pathology(p: pd.DataFrame) -> None:
    print("== Q1: does any tool fail at some theta and not others? ==\n")
    bad = p[(p.nan_pct > 0) | (p.nonconv_pct > 0)]
    if bad.empty:
        thetas = sorted(p.theta_pct.unique())
        print(f"  no failures anywhere: {len(p)} (tool, theta) cells, "
              f"theta in {thetas}")
    else:
        print(bad.to_string(index=False))
        print("\n  A tool failing at some theta makes every pooled comparison\n"
              "  conditional on the truth. Treat those cells separately.")


def report_significance_curve(s: pd.DataFrame) -> None:
    """The power curve, which at theta=0 is the false positive rate."""
    print("\n== the power curve: P(significant | theta) ==")
    print("   at theta = 0 this is the false positive rate.\n")
    piv = s.pivot_table(index="tool_label", columns="theta_pct",
                        values="sig_rate")
    print(piv.round(1).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--scenario", default=None,
                    help="restrict to one scenario; default pools all")
    args = ap.parse_args()

    d = load(args.results)
    if args.scenario:
        d = d[d.scenario == args.scenario]
    thetas = sorted(d.theta_pct.unique())

    print(f"rows {len(d):,} | tools {d.tool_label.nunique()} | "
          f"scenarios {sorted(d.scenario.unique())}")
    print(f"theta values present: {thetas}\n")

    if len(thetas) < 3:
        print("!! Fewer than three theta values. This script exists to test\n"
              "   what two points cannot show, so most of it will be vacuous.\n"
              "   Run the mutation first -- see donor-repro.md S5.\n")

    report_pathology(q1_pathology(d))
    s = q2_q3_q4(d)

    print("\n== per-(tool, theta) summary ==")
    disp = s.copy()
    for c in ("bias", "se_bias", "sd", "ci_width"):
        disp[c] = disp[c].round(3)
    disp["skew"] = disp["skew"].round(2)
    print(disp.to_string(index=False))

    report_bias_shape(s)
    report_variance_shape(s)
    report_sign_dependence(d, s)
    report_significance_curve(s)

    out = Path("theta_atlas_results.json")
    out.write_text(json.dumps({
        "thetas": thetas,
        "summary": s.to_dict(orient="records"),
    }, indent=2, default=float))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
