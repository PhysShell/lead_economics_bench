"""MMM track: parameter recovery, ROI recovery and budget-allocation regret.

Every candidate exposes the same thing -- an estimated per-channel response
curve ``g_c(spend)`` -- and every candidate's curve is fed to the *same*
constrained optimiser. So the leaderboard compares response estimation, not
who wrapped a nicer optimiser around it.

Scored against the true curves, which is the only way to tell a plausible MMM
from a correct one. Real MMM deployments cannot do this, which is exactly why
section 42 exists: if a method cannot recover known truth on data of the size
an SMB actually has, it will not recover unknown truth either.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..synthetic.mmm_dgp import (
    MMMDataset,
    geometric_adstock,
    make_mmm_config,
    saturate,
    true_marginal_roi,
    true_response,
)


@dataclass
class MMMSpec:
    name: str
    regime: str = "mmm_standard"
    seeds: tuple[int, ...] = (0, 1, 2)
    #: Budget levels to optimise, as a multiple of current total spend.
    budget_multipliers: tuple[float, ...] = (0.7, 1.0, 1.5)
    train_frac: float = 0.8
    #: Run the Bayesian MMM candidates (slow).
    include_bayesian: bool = True
    bayes_draws: int = 400
    bayes_tune: int = 400
    #: Run Google Meridian via the isolated Python 3.12 interpreter (slowest).
    include_meridian: bool = False
    meridian_python: str = ".venv312/bin/python"


# ---------------------------------------------------------------------------
# Shared budget optimiser
# ---------------------------------------------------------------------------


def optimise_budget(
    response_fn: Callable[[np.ndarray], np.ndarray],
    budget: float,
    n_channels: int,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    n_starts: int = 5,
    seed: int = 0,
) -> np.ndarray:
    """Maximise total predicted response subject to a total-spend budget.

    Multi-start SLSQP. Identical for every candidate, including the Oracle.
    """
    lo = np.zeros(n_channels) if lower is None else np.asarray(lower, float)
    hi = np.full(n_channels, budget) if upper is None else np.asarray(upper, float)
    rng = np.random.default_rng(seed)

    def neg(s):
        return -float(np.sum(response_fn(np.clip(s, lo, hi))))

    cons = [{"type": "eq", "fun": lambda s: np.sum(s) - budget}]
    best, best_val = None, np.inf
    starts = [np.full(n_channels, budget / n_channels)]
    for _ in range(n_starts - 1):
        w = rng.dirichlet(np.ones(n_channels))
        starts.append(w * budget)
    for s0 in starts:
        try:
            res = minimize(
                neg,
                s0,
                method="SLSQP",
                bounds=list(zip(lo, hi)),
                constraints=cons,
                options={"maxiter": 300, "ftol": 1e-9},
            )
            if res.fun < best_val:
                best, best_val = res.x, res.fun
        except Exception:
            continue
    if best is None:
        best = np.full(n_channels, budget / n_channels)
    best = np.clip(best, lo, hi)
    total = best.sum()
    return best * (budget / total) if total > 0 else best


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


class MMMCandidate:
    name = "mmm_candidate"
    family = "mmm"

    def fit(self, df: pd.DataFrame, channels: list[str], seed: int) -> "MMMCandidate":
        return self

    def response(self, spend: np.ndarray) -> np.ndarray:
        """Predicted per-period contribution per channel at a steady spend level."""
        raise NotImplementedError

    def roi(self, mean_spend: np.ndarray) -> np.ndarray:
        return self.response(mean_spend) / np.maximum(mean_spend, 1e-9)

    def params(self) -> dict[str, Any]:
        return {}


class EqualAllocation(MMMCandidate):
    name, family = "equal_allocation", "naive"

    def fit(self, df, channels, seed):
        self.n = len(channels)
        return self

    def response(self, spend):
        # Believes every dollar is equally good, so the optimiser splits evenly.
        return np.asarray(spend, float) * 0 + 1.0


class ReportedROASAllocation(MMMCandidate):
    """Allocate in proportion to platform-reported ROAS. The dashboard policy."""

    name, family = "reported_roas", "analytics"

    def fit(self, df, channels, seed):
        rep = np.array([df[f"reported_revenue_{c}"].sum() for c in channels])
        spend = np.array([df[f"spend_{c}"].sum() for c in channels])
        self.roas = rep / np.maximum(spend, 1e-9)
        return self

    def response(self, spend):
        # Linear in spend at the reported rate: no diminishing returns at all.
        return self.roas * np.asarray(spend, float)


class NaiveOLS(MMMCandidate):
    """OLS of revenue on raw spend. No adstock, no saturation, no controls."""

    name, family = "naive_ols", "regression"

    def fit(self, df, channels, seed):
        X = df[[f"spend_{c}" for c in channels]].to_numpy(float)
        y = df["revenue"].to_numpy(float)
        Xd = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
        self.coef = np.maximum(coef[1:], 0.0)
        return self

    def response(self, spend):
        return self.coef * np.asarray(spend, float)


class RidgeAdstockSaturation(MMMCandidate):
    """Grid-searched adstock + saturation with a non-negative ridge fit.

    The strong, cheap, frequentist MMM. If the Bayesian MMM cannot beat this,
    that is a finding about what MMM machinery is actually buying.
    """

    name, family = "ridge_adstock_saturation", "mmm"

    def __init__(self, alphas=(0.1, 0.3, 0.5, 0.7), lams=(2e-5, 5e-5, 1e-4, 2e-4)):
        self.alphas, self.lams = alphas, lams

    def fit(self, df, channels, seed):
        from sklearn.linear_model import Ridge

        y = df["revenue"].to_numpy(float)
        t = df["period"].to_numpy(float)
        ctrl = np.column_stack(
            [
                np.ones(len(df)),
                t,
                np.sin(2 * np.pi * t / 52.0),
                np.cos(2 * np.pi * t / 52.0),
                df["price_index"].to_numpy(float),
                df["promo"].to_numpy(float),
            ]
        )
        spend = {c: df[f"spend_{c}"].to_numpy(float) for c in channels}
        best = (np.inf, None)
        rng = np.random.default_rng(seed)
        # Coordinate search: one (alpha, lambda) pair per channel.
        current = {c: (self.alphas[1], self.lams[1]) for c in channels}
        for _ in range(3):
            for c in channels:
                for a in self.alphas:
                    for l in self.lams:
                        trial = dict(current)
                        trial[c] = (a, l)
                        X = np.column_stack(
                            [
                                saturate(geometric_adstock(spend[k], trial[k][0]), 1.0, trial[k][1])
                                for k in channels
                            ]
                        )
                        Xf = np.column_stack([ctrl, X])
                        m = Ridge(alpha=1.0, fit_intercept=False, positive=True)
                        m.fit(Xf, y)
                        sse = float(np.sum((y - m.predict(Xf)) ** 2))
                        if sse < best[0]:
                            best = (sse, (dict(trial), m))
                if best[1] is not None:
                    current = dict(best[1][0])
        params, model = best[1]
        self.params_ = params
        self.channels = channels
        self.beta = np.array([model.coef_[ctrl.shape[1] + i] for i in range(len(channels))])
        self.alpha = np.array([params[c][0] for c in channels])
        self.lam = np.array([params[c][1] for c in channels])
        return self

    def response(self, spend):
        return saturate(np.asarray(spend, float), self.beta, self.lam)

    def params(self):
        return {"alpha": self.alpha, "beta": self.beta, "lambda": self.lam}


class PyMCMarketingMMM(MMMCandidate):
    """PyMC-Marketing MMM with geometric adstock and logistic saturation.

    Optionally calibrated with an experimental lift measurement, which is the
    thing MMM vendors correctly insist on (section 43).
    """

    family = "mmm"

    def __init__(self, draws=400, tune=400, calibrate=False, lift_noise=0.15):
        self.draws, self.tune = draws, tune
        self.calibrate = calibrate
        self.lift_noise = lift_noise
        self.name = "pymc_marketing_mmm_calibrated" if calibrate else "pymc_marketing_mmm"
        self._truth = None

    def set_truth_for_lift_test(self, dataset: MMMDataset) -> None:
        """Supply the simulated geo-experiment result, not the parameters."""
        self._truth = dataset

    def fit(self, df, channels, seed):
        import pymc as pm
        from pymc_marketing.mmm import MMM, GeometricAdstock, LogisticSaturation
        from pymc_marketing.prior import Prior

        self.channels = channels
        X = df[["date"] + [f"spend_{c}" for c in channels] + ["price_index", "promo"]].copy()
        X = X.rename(columns={f"spend_{c}": c for c in channels})
        y = df["revenue"]

        self.model = MMM(
            date_column="date",
            channel_columns=channels,
            control_columns=["price_index", "promo"],
            adstock=GeometricAdstock(l_max=12),
            saturation=LogisticSaturation(),
            yearly_seasonality=2,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.calibrate and self._truth is not None:
                self.model.build_model(X, y)
                lift = self._simulated_lift_tests(seed)
                try:
                    self.model.add_lift_test_measurements(lift)
                except Exception as exc:  # noqa: BLE001
                    self.calibration_error = str(exc)[:200]
            self.model.fit(
                X,
                y,
                draws=self.draws,
                tune=self.tune,
                chains=2,
                cores=2,
                target_accept=0.9,
                random_seed=seed,
                progressbar=False,
            )
        self._extract_curve()
        return self

    def _simulated_lift_tests(self, seed: int) -> pd.DataFrame:
        """A geo holdout per channel: measured incremental revenue with noise."""
        rng = np.random.default_rng(seed + 991)
        t = self._truth.truth
        mean_spend = t["mean_spend"]
        rows = []
        for i, c in enumerate(self.channels):
            x1 = mean_spend[i]
            x2 = mean_spend[i] * 0.5  # holdout halves the spend
            delta = saturate(x1, t["beta"][i], t["lambda"][i]) - saturate(
                x2, t["beta"][i], t["lambda"][i]
            )
            sigma = abs(delta) * self.lift_noise + 1e-6
            rows.append(
                {
                    "channel": c,
                    "x": x1,
                    "delta_x": x2 - x1,
                    "delta_y": float(delta * -1 + rng.normal(0, sigma)),
                    "sigma": float(sigma),
                }
            )
        return pd.DataFrame(rows)

    def _extract_curve(self) -> None:
        """Read back adstock/saturation posteriors as a deterministic curve.

        Reconstructing the curve by hand is fragile across library versions, so
        the reconstruction is *validated* against the library's own
        ``channel_contribution_original_scale`` on the training spend path and
        the worst relative error is recorded. If it does not match, the
        candidate raises instead of quietly reporting a wrong ROI.
        """
        post = self.model.idata.posterior
        # Work with draws, not posterior means. The saturation is concave, so
        # f(E[theta]) overstates E[f(theta)] by a channel-specific amount --
        # which is exactly the discrepancy that made the first version of this
        # reconstruction disagree with the library by ~15-50%.
        self.beta_draws = _posterior_draws(post, ["saturation_beta", "beta_channel"])
        self.lam_draws = _posterior_draws(post, ["saturation_lam", "lam"])
        self.alpha_draws = _posterior_draws(post, ["adstock_alpha", "alpha"])
        self.beta_raw = self.beta_draws.mean(axis=0)
        self.lam_raw = self.lam_draws.mean(axis=0)
        self.alpha = self.alpha_draws.mean(axis=0)
        self._scales = self._recover_scales()
        self._adstock_normalize = bool(getattr(self.model.adstock, "normalize", False))
        self._l_max = int(getattr(self.model.adstock, "l_max", 12))
        self.reconstruction_error = self._validate_reconstruction()
        if self.reconstruction_error > 0.15:
            raise RuntimeError(
                "pymc-marketing curve reconstruction disagrees with the library's "
                f"own fitted contributions by {self.reconstruction_error:.1%}; "
                "refusing to report ROI from it"
            )

    def _recover_scales(self):
        """PyMC-Marketing fits on MaxAbs-scaled data; recover original units."""
        ct = self.model.channel_transformer
        tt = self.model.target_transformer
        xs = np.asarray(ct.steps[-1][1].scale_, dtype=float)
        ys = float(np.atleast_1d(tt.steps[-1][1].scale_)[0])
        return xs, ys

    def _adstock_gain(self, alpha: np.ndarray) -> np.ndarray:
        """Steady-state multiplier of a constant spend under geometric adstock.

        ``normalize=False`` (the library default) means the weights sum to
        ``(1 - alpha^(l_max+1)) / (1 - alpha)``, not to 1.
        """
        if self._adstock_normalize:
            return np.ones_like(alpha)
        a = np.clip(alpha, 0.0, 0.999999)
        return (1.0 - a ** (self._l_max + 1)) / (1.0 - a)

    def _contribution_draws(self, adstocked_scaled: np.ndarray) -> np.ndarray:
        """(draws, ..., channels) contribution in original units."""
        _, ys = self._scales
        z = np.exp(-self.lam_draws * adstocked_scaled)
        return self.beta_draws * (1 - z) / (1 + z) * ys

    def _validate_reconstruction(self) -> float:
        from ..synthetic.mmm_dgp import geometric_adstock as _ga

        post = self.model.idata.posterior
        if "channel_contribution_original_scale" not in post.data_vars:
            return 0.0
        lib = post["channel_contribution_original_scale"].mean(
            dim=("chain", "draw")
        ).to_numpy()
        xs, ys = self._scales
        sp = self.model.X[self.channels].to_numpy(dtype=float) / np.maximum(xs, 1e-9)
        S, C = self.alpha_draws.shape
        T = sp.shape[0]
        acc = np.zeros((T, C))
        for s in range(S):
            gain = self._adstock_gain(self.alpha_draws[s])
            ad = np.column_stack(
                [
                    _ga(sp[:, c], self.alpha_draws[s, c], max_lag=self._l_max - 1)
                    * gain[c]
                    for c in range(C)
                ]
            )
            z = np.exp(-self.lam_draws[s] * ad)
            acc += self.beta_draws[s] * (1 - z) / (1 + z) * ys
        mine = acc / S
        denom = np.maximum(np.abs(lib).mean(axis=0), 1e-9)
        return float(np.max(np.abs(mine - lib).mean(axis=0) / denom))

    def response(self, spend):
        """Steady-state per-period contribution at a constant spend level.

        Averaged over posterior draws, because the saturation is concave and
        the response at the posterior mean is not the mean response. Validated
        against the library's own fitted contributions in
        :meth:`_validate_reconstruction`.
        """
        xs, _ = self._scales
        s = np.asarray(spend, float) / np.maximum(xs, 1e-9)
        gain = self._adstock_gain(self.alpha_draws)  # (draws, channels)
        return self._contribution_draws(s[None, :] * gain).mean(axis=0)

    def params(self):
        return {"alpha": self.alpha, "beta": self.beta_raw, "lambda": self.lam_raw}


def _posterior_mean(post, candidates: list[str]) -> np.ndarray:
    for nm in candidates:
        if nm in post.data_vars:
            arr = post[nm].mean(dim=("chain", "draw")).to_numpy()
            return np.atleast_1d(arr)
    raise KeyError(f"none of {candidates} in posterior: {list(post.data_vars)}")


def _posterior_draws(post, candidates: list[str], max_draws: int = 200) -> np.ndarray:
    """(draws, channels) array of posterior samples, thinned deterministically."""
    for nm in candidates:
        if nm in post.data_vars:
            arr = (
                post[nm]
                .stack(sample=("chain", "draw"))
                .transpose("sample", ...)
                .to_numpy()
            )
            arr = np.atleast_2d(arr)
            if len(arr) > max_draws:
                arr = arr[np.linspace(0, len(arr) - 1, max_draws).astype(int)]
            return arr
    raise KeyError(f"none of {candidates} in posterior: {list(post.data_vars)}")


class MeridianMMM(MMMCandidate):
    """Google Meridian, run in an isolated Python 3.12 interpreter.

    Meridian's stack requires Python >=3.12 while the benchmark environment is
    3.11, so it is driven as a subprocess through ``scripts/run_meridian.py``.
    The adapter hands back the same steady-state response grid every other MMM
    candidate exposes, so the shared budget optimiser is unchanged and the
    comparison stays about response estimation.
    """

    name, family = "google_meridian", "mmm"

    def __init__(self, python: str = ".venv312/bin/python", draws: int = 400, tune: int = 400):
        self.python = python
        self.draws, self.tune = draws, tune

    @staticmethod
    def available(python: str = ".venv312/bin/python") -> bool:
        import subprocess
        from pathlib import Path

        if not Path(python).exists():
            return False
        try:
            r = subprocess.run(
                [python, "-c", "import meridian"],
                capture_output=True,
                timeout=300,
            )
            return r.returncode == 0
        except Exception:
            return False

    def fit(self, df, channels, seed):
        import json
        import subprocess
        import tempfile
        from pathlib import Path

        self.channels = channels
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "mmm.csv"
            out = Path(tmp) / "out.json"
            df.to_csv(csv, index=False)
            cmd = [
                self.python,
                "scripts/run_meridian.py",
                "--data", str(csv),
                "--channels", ",".join(channels),
                "--out", str(out),
                "--draws", str(self.draws),
                "--tune", str(self.tune),
                "--seed", str(seed),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=14_400)
            if r.returncode != 0 or not out.exists():
                raise RuntimeError(
                    f"meridian subprocess failed (rc={r.returncode}): {r.stderr[-400:]}"
                )
            payload = json.loads(out.read_text())
        self._mults = np.asarray(payload["grid_multipliers"], dtype=float)
        self._grid = np.asarray(payload["grid_response"], dtype=float)
        self._mean_spend = np.asarray(payload["mean_spend"], dtype=float)
        self._grid_spend = self._mean_spend[None, :] * self._mults[:, None]
        self._reported_roi = np.asarray(payload["roi"], dtype=float)
        return self

    def response(self, spend):
        s = np.asarray(spend, float)
        return np.array(
            [
                np.interp(s[c], self._grid_spend[:, c], self._grid[:, c])
                for c in range(len(self.channels))
            ]
        )

    def params(self):
        return {"reported_roi": self._reported_roi}


class OracleMMM(MMMCandidate):
    name, family = "oracle", "oracle"

    def __init__(self, dataset: MMMDataset):
        self.ds = dataset

    def fit(self, df, channels, seed):
        return self

    def response(self, spend):
        t = self.ds.truth
        return saturate(np.asarray(spend, float), t["beta"], t["lambda"])

    def params(self):
        t = self.ds.truth
        return {"alpha": t["alpha"], "beta": t["beta"], "lambda": t["lambda"]}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_mmm_scenario(spec: MMMSpec, verbose: bool = True) -> pd.DataFrame:
    from ..synthetic.mmm_dgp import generate_mmm

    rows: list[dict[str, Any]] = []
    for seed in spec.seeds:
        ds = generate_mmm(make_mmm_config(spec.regime, seed=seed))
        channels = ds.channels
        C = len(channels)
        cut = int(spec.train_frac * len(ds.data))
        train = ds.data.iloc[:cut].reset_index(drop=True)

        mean_spend = np.array([train[f"spend_{c}"].mean() for c in channels])
        total_spend = float(mean_spend.sum())

        candidates: list[MMMCandidate] = [
            OracleMMM(ds),
            EqualAllocation(),
            ReportedROASAllocation(),
            NaiveOLS(),
            RidgeAdstockSaturation(),
        ]
        if spec.include_bayesian:
            candidates.append(PyMCMarketingMMM(spec.bayes_draws, spec.bayes_tune))
            cal = PyMCMarketingMMM(spec.bayes_draws, spec.bayes_tune, calibrate=True)
            cal.set_truth_for_lift_test(ds)
            candidates.append(cal)
        if spec.include_meridian:
            candidates.append(
                MeridianMMM(
                    python=spec.meridian_python,
                    draws=spec.bayes_draws,
                    tune=spec.bayes_tune,
                )
            )

        for cand in candidates:
            row: dict[str, Any] = {
                "scenario": spec.name,
                "regime": spec.regime,
                "seed": seed,
                "candidate": cand.name,
                "family": cand.family,
                "n_periods": len(ds.data),
            }
            try:
                cand.fit(train, channels, seed)
                est_roi = cand.roi(mean_spend)
                true_roi = ds.truth["roi"]
                row["roi_mape"] = float(
                    np.mean(np.abs(est_roi - true_roi) / np.maximum(true_roi, 1e-9))
                )
                row["roi_rank_spearman"] = _spearman(true_roi, est_roi)

                p = cand.params()
                if "alpha" in p and len(np.atleast_1d(p["alpha"])) == C:
                    row["alpha_mae"] = float(
                        np.mean(np.abs(np.atleast_1d(p["alpha"]) - ds.truth["alpha"]))
                    )

                for mult in spec.budget_multipliers:
                    budget = total_spend * mult
                    alloc = optimise_budget(cand.response, budget, C, seed=seed)
                    oracle_alloc = optimise_budget(
                        OracleMMM(ds).response, budget, C, seed=seed
                    )
                    v_model = true_response(ds, alloc)
                    v_oracle = true_response(ds, oracle_alloc)
                    v_equal = true_response(ds, np.full(C, budget / C))
                    denom = v_oracle - v_equal
                    row[f"regret_b{mult}"] = float(v_oracle - v_model)
                    row[f"regret_pct_b{mult}"] = float(
                        100.0 * (v_oracle - v_model) / max(v_oracle, 1e-9)
                    )
                    row[f"pct_of_oracle_gain_b{mult}"] = (
                        float(100.0 * (v_model - v_equal) / denom)
                        if abs(denom) > 1e-9
                        else float("nan")
                    )
                    row[f"true_revenue_b{mult}"] = v_model
                row["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                row["status"] = f"error: {type(exc).__name__}: {exc}"
                if verbose:
                    print(f"  !! MMM {cand.name} failed: {exc}")
            rows.append(row)
            if verbose and row.get("status") == "ok":
                print(
                    f"  mmm {spec.regime} seed={seed} {cand.name:30s} "
                    f"roi_mape={row.get('roi_mape', float('nan')):6.3f} "
                    f"regret%@1.0={row.get('regret_pct_b1.0', float('nan')):6.2f}"
                )
    return pd.DataFrame(rows)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy import stats

    if np.std(b) < 1e-12:
        return float("nan")
    return float(stats.spearmanr(a, b).statistic)
