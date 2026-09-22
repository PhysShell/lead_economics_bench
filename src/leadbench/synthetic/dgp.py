"""Lead-level data generating process with known potential outcomes.

Design notes that matter for the validity of the benchmark:

1. **Common random numbers.** Each lead carries one uniform draw per funnel
   stage. A potential outcome under action ``a`` is
   ``1[u_stage < p_stage(a)]``. Counterfactuals are therefore coherent and
   monotone in the stage probabilities: the same lead cannot "get lucky" under
   one action and unlucky under another for reasons unrelated to the action.

2. **Oracle is not clairvoyant.** The Oracle knows the true probabilities and
   the true *expected* net contribution; it does not know the realized uniform
   draws, the realized refund, or the realized deal value noise. It is the best
   policy measurable with respect to the lead's characteristics, not a
   fortune-teller. Realized evaluation uses the drawn outcomes.

3. **Truth is quarantined.** :class:`LeadDataset` keeps ``observed`` and
   ``truth`` in separate frames. Models receive only ``observed`` (and only the
   declared ``feature_columns`` of it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .config import ACTIONS, CONTROL_ACTION, DGPConfig, action_probs_for

_EPS = 1e-6
_STAGES = ("contact", "qualified", "application", "funded")
# How much of a stage-level random effect / action effect reaches each stage.
_STAGE_RE_WEIGHTS = (1.0, 0.70, 0.50, 0.30)


def _logit(p: np.ndarray | float) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -35, 35)))


@dataclass
class LeadDataset:
    """A generated lead economy.

    Attributes
    ----------
    observed:
        Everything a real CRM/ad-platform integration could plausibly hand a
        model, including the decision log.
    truth:
        Potential outcomes, true probabilities, true treatment effects and true
        expected values. Benchmark-framework only.
    """

    observed: pd.DataFrame
    truth: pd.DataFrame
    config: DGPConfig
    feature_columns: list[str]
    categorical_columns: list[str]
    actions: tuple[str, ...] = ACTIONS
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.observed)

    @property
    def n_actions(self) -> int:
        return len(self.actions)

    def X(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        df = self.observed if df is None else df
        return df[self.feature_columns]

    def subset(self, mask: np.ndarray | pd.Series) -> "LeadDataset":
        mask = np.asarray(mask)
        return LeadDataset(
            observed=self.observed.loc[mask].reset_index(drop=True),
            truth=self.truth.loc[mask].reset_index(drop=True),
            config=self.config,
            feature_columns=list(self.feature_columns),
            categorical_columns=list(self.categorical_columns),
            actions=self.actions,
            meta=dict(self.meta),
        )

    def describe(self) -> dict[str, Any]:
        obs, tr = self.observed, self.truth
        call = self.n_actions - 1
        out: dict[str, Any] = {
            "regime": self.config.name,
            "n_leads": int(len(obs)),
            "n_actions": self.n_actions,
            "logging_policy": self.config.logging_policy,
            "observed_funded_rate": float(np.nanmean(obs["funded"])),
            "censored_share": float(obs["censored"].mean()),
        }
        for a, nm in enumerate(self.actions):
            out[f"true_p_funded_{nm}"] = float(tr[f"p_funded_a{a}"].mean())
            out[f"true_ev_{nm}"] = float(tr[f"ev_a{a}"].mean())
        out["true_ate_call_on_funded"] = float(
            (tr[f"p_funded_a{call}"] - tr["p_funded_a0"]).mean()
        )
        out["share_negative_ite"] = float(
            (tr[f"p_funded_a{call}"] < tr["p_funded_a0"]).mean()
        )
        return out


def _draw_features(rng: np.random.Generator, cfg: DGPConfig) -> np.ndarray:
    """Correlated numeric covariates via a low-rank factor model."""
    n, k, f = cfg.n_leads, cfg.n_numeric_features, cfg.n_factors
    factors = rng.standard_normal((n, f))
    loadings = rng.uniform(-1.0, 1.0, size=(f, k))
    idio = rng.standard_normal((n, k))
    x = factors @ loadings + idio
    x = (x - x.mean(axis=0)) / (x.std(axis=0) + _EPS)
    return x


def generate(cfg: DGPConfig) -> LeadDataset:
    """Generate a lead dataset with full ground truth."""
    rng = np.random.default_rng(cfg.seed)
    n = cfg.n_leads
    action_names = tuple(cfg.action_set)
    n_actions = len(action_names)
    if action_names[0] != "none" or action_names[-1] != "call":
        raise ValueError("action_set must start with 'none' and end with 'call'")

    # ---------------- structure -------------------------------------------
    campaign = rng.integers(0, cfg.n_campaigns, n)
    geo = rng.integers(0, cfg.n_geos, n)
    product = rng.integers(0, cfg.n_products, n)
    agent = rng.integers(0, cfg.n_agents, n)
    created_day = rng.integers(0, cfg.n_periods, n)
    device = rng.integers(0, 3, n)
    hour = rng.integers(0, 24, n)

    x = _draw_features(rng, cfg)

    # Latent purchase intent: partly recoverable from X, partly irreducible.
    w = rng.normal(size=cfg.n_numeric_features)
    w /= np.linalg.norm(w)
    signal = x @ w
    signal = (signal - signal.mean()) / (signal.std() + _EPS)
    rho = 0.75
    intent = np.sqrt(rho) * signal + np.sqrt(1 - rho) * rng.standard_normal(n)

    # Confounder: drives both the historical action choice and the outcome.
    u_conf = rng.standard_normal(n)

    # ---------------- hierarchy -------------------------------------------
    camp_eff = rng.normal(0, cfg.sd_campaign, cfg.n_campaigns)[campaign]
    geo_eff = rng.normal(0, cfg.sd_geo, cfg.n_geos)[geo]
    prod_eff = rng.normal(0, cfg.sd_product, cfg.n_products)[product]
    agent_eff = rng.normal(0, cfg.sd_agent, cfg.n_agents)[agent]
    camp_tau = rng.normal(0, cfg.sd_campaign_tau, cfg.n_campaigns)[campaign]

    # Nuisance covariate effects (the part of the outcome that is predictable
    # from X but has nothing to do with intent).
    noise_coefs = rng.normal(0, cfg.beta_noise_scale, cfg.n_numeric_features)
    nuisance = x @ noise_coefs

    # ---------------- time -------------------------------------------------
    season = cfg.seasonality_amplitude * np.sin(
        2 * np.pi * created_day / cfg.seasonality_period
    )
    trend = cfg.trend_per_period * created_day

    drift_mask = np.zeros(n, dtype=bool)
    if cfg.drift_start_frac is not None:
        drift_day = cfg.drift_start_frac * cfg.n_periods
        drift_mask = created_day >= drift_day

    # ---------------- attribution -----------------------------------------
    # True originating channel is a deterministic function of the campaign.
    channel_names = np.array(
        ["paid_search", "paid_social", "display", "retargeting", "organic"]
    )
    true_channel_idx = campaign % len(channel_names)
    attributed_idx = true_channel_idx.copy()
    if cfg.misleading_attribution:
        grab = rng.random(n) < cfg.retargeting_lasttouch_share
        attributed_idx = np.where(grab, 3, true_channel_idx)  # 3 == retargeting
    # A genuinely retargeting-sourced lead gets a tiny real lift; last-touch
    # credit gets handed out far more widely than that.
    channel_true_effect = np.zeros(len(channel_names))
    channel_true_effect[3] = cfg.retargeting_true_effect
    chan_eff = channel_true_effect[true_channel_idx]

    # ---------------- control-arm stage logits -----------------------------
    base_p = (
        cfg.p_contact_base,
        cfg.p_qualified_base,
        cfg.p_application_base,
        cfg.p_funded_base,
    )
    beta_intent = (
        cfg.beta_intent_contact,
        cfg.beta_intent_qualified,
        cfg.beta_intent_application,
        cfg.beta_intent_funded,
    )

    intent_eff = intent.copy()
    if drift_mask.any():
        intent_eff = intent + drift_mask * cfg.drift_intent_shift

    control_logits = np.zeros((n, 4))
    for s in range(4):
        w_s = _STAGE_RE_WEIGHTS[s]
        control_logits[:, s] = (
            _logit(base_p[s])
            + beta_intent[s] * intent_eff
            + w_s * (camp_eff + geo_eff + prod_eff + nuisance)
            + w_s * chan_eff
            + (agent_eff if s in (1, 2) else 0.0)
            + w_s * (season + trend)
            + cfg.confounder_outcome_strength * w_s * u_conf
        )

    # ---------------- treatment effects ------------------------------------
    bump = np.exp(-0.5 * ((intent - cfg.tau_center) / cfg.tau_width) ** 2)
    het_mult = 1.0 + cfg.het_coef * x[:, cfg.het_feature % cfg.n_numeric_features]
    het_mult = np.clip(het_mult, -1.0, 3.0)
    tau_scale = np.ones(n)
    if drift_mask.any():
        tau_scale = 1.0 + drift_mask * cfg.drift_tau_shift

    tau_by_name = {"none": 0.0, "sms": cfg.tau_max_sms, "call": cfg.tau_max_call}
    # tau[a] is the total logit-scale effect of action a for each lead.
    tau = np.zeros((n, n_actions))
    if not cfg.null_effect:
        for a, nm in enumerate(action_names):
            if a == CONTROL_ACTION:
                continue
            is_call = nm == "call"
            tau[:, a] = (
                tau_by_name[nm] * bump * het_mult + camp_tau * is_call
            ) * tau_scale

    # ---------------- stage probabilities per action ------------------------
    # p_stage[a][:, s]
    p_stage = np.zeros((n_actions, n, 4))
    for a in range(n_actions):
        for s in range(4):
            lg = control_logits[:, s] + tau[:, a] * cfg.tau_stage_weights[s]
            p_stage[a, :, s] = np.clip(_sigmoid(lg), _EPS, 1 - _EPS)

    # ---------------- common random numbers ---------------------------------
    u_stage = rng.random((n, 4))

    # Potential outcomes for every action.
    po_stage = np.zeros((n_actions, n, 4), dtype=bool)
    for a in range(n_actions):
        reached = np.ones(n, dtype=bool)
        for s in range(4):
            reached = reached & (u_stage[:, s] < p_stage[a, :, s])
            po_stage[a, :, s] = reached

    p_funded = np.prod(p_stage, axis=2)  # (n_actions, n)
    p_funded = p_funded.T  # (n, n_actions)

    # ---------------- deal economics ----------------------------------------
    value_shift = np.asarray(cfg.value_product_shift)[product]
    gross_value = np.exp(
        cfg.value_mu_log
        + value_shift
        + cfg.value_intent_coef * intent
        + cfg.value_sigma_log * rng.standard_normal(n)
    )
    net_if_kept = gross_value * cfg.margin_rate - cfg.servicing_cost_per_funded
    refunded = rng.random(n) < cfg.refund_rate
    # On a clawback you lose the revenue but keep the servicing cost.
    net_contribution = np.where(refunded, -cfg.servicing_cost_per_funded, net_if_kept)
    expected_net_contribution = (
        1 - cfg.refund_rate
    ) * net_if_kept - cfg.refund_rate * cfg.servicing_cost_per_funded

    # ---------------- effort -------------------------------------------------
    call_minutes = np.exp(
        cfg.call_minutes_mu_log
        + cfg.effort_intent_coef * intent
        + cfg.call_minutes_sigma_log * rng.standard_normal(n)
    )
    call_minutes = np.clip(call_minutes, 1.0, 90.0)
    minutes = np.zeros((n, n_actions))
    direct_cost = np.zeros((n, n_actions))
    for a, nm in enumerate(action_names):
        if nm == "sms":
            minutes[:, a] = cfg.sms_minutes
            direct_cost[:, a] = cfg.sms_direct_cost
        elif nm == "call":
            minutes[:, a] = call_minutes
            direct_cost[:, a] = cfg.call_direct_cost

    cost_per_min = cfg.agent_cost_per_hour / 60.0
    action_cost = direct_cost + minutes * cost_per_min

    # True expected net value of each action (sunk acquisition cost excluded —
    # see docs/methodology.md on when CPL is and is not sunk).
    ev = p_funded * expected_net_contribution[:, None] - action_cost

    # ---------------- acquisition cost ---------------------------------------
    cpl_by_campaign = np.clip(
        rng.normal(cfg.cpl_mu, cfg.cpl_sd, cfg.n_campaigns), 5.0, None
    )
    cpl = cpl_by_campaign[campaign]

    # ---------------- logging policy ------------------------------------------
    propensities = _logging_propensities(rng, cfg, intent, u_conf, x, action_names)
    cum = propensities.cumsum(axis=1)
    draw = rng.random(n)[:, None]
    logged_action = (draw > cum).sum(axis=1)
    logged_action = np.clip(logged_action, 0, n_actions - 1)
    logged_propensity = propensities[np.arange(n), logged_action]

    # ---------------- realized observations ------------------------------------
    idx = np.arange(n)
    obs_stage = po_stage[logged_action, idx, :]  # (n, 4)
    obs_minutes = minutes[idx, logged_action]
    obs_direct_cost = direct_cost[idx, logged_action]
    realized_funded = obs_stage[:, 3]

    # ---------------- delays and censoring --------------------------------------
    delays = np.zeros((n, 4))
    for s in range(4):
        delays[:, s] = rng.exponential(cfg.delay_mean_days[s], n)
    cum_delay = delays.cumsum(axis=1)
    # A lead resolves at the day it reaches its deepest stage; leads that stall
    # resolve when the stage they failed at would have resolved.
    depth = obs_stage.sum(axis=1)  # 0..4
    resolution_offset = cum_delay[idx, np.clip(depth, 0, 3)]
    resolution_day = created_day + resolution_offset

    censored = np.zeros(n, dtype=bool)
    if cfg.observation_cutoff_frac is not None:
        cutoff = cfg.observation_cutoff_frac * cfg.n_periods
        censored = resolution_day > cutoff

    # ---------------- assemble observed frame -------------------------------------
    feat_cols = [f"x{i}" for i in range(cfg.n_numeric_features)]
    obs = pd.DataFrame({f"x{i}": x[:, i] for i in range(cfg.n_numeric_features)})
    obs.insert(0, "lead_id", np.arange(n))
    obs.insert(1, "person_id", np.arange(n))
    obs["campaign_id"] = campaign
    obs["geo_id"] = geo
    obs["product_id"] = product
    obs["agent_id"] = agent
    obs["device"] = device
    obs["hour_of_day"] = hour
    obs["created_day"] = created_day
    obs["attributed_channel"] = channel_names[attributed_idx]
    obs["cpl"] = cpl

    if cfg.confounder_observed and cfg.confounder_outcome_strength > 0:
        obs["x_conf"] = u_conf
        feat_cols = feat_cols + ["x_conf"]

    obs["action"] = logged_action
    obs["action_name"] = np.asarray(action_names)[logged_action]
    for a, nm in enumerate(action_names):
        obs[f"propensity_{nm}"] = propensities[:, a]
    obs["propensity"] = logged_propensity
    obs["policy_version"] = f"logging::{cfg.logging_policy}"

    obs["minutes_spent"] = obs_minutes
    obs["action_direct_cost"] = obs_direct_cost
    obs["contacted"] = obs_stage[:, 0].astype(float)
    obs["qualified"] = obs_stage[:, 1].astype(float)
    obs["applied"] = obs_stage[:, 2].astype(float)
    obs["funded"] = obs_stage[:, 3].astype(float)
    obs["realized_gross_value"] = np.where(realized_funded, gross_value, 0.0)
    obs["refunded"] = np.where(realized_funded, refunded, False)
    obs["realized_net_contribution"] = np.where(realized_funded, net_contribution, 0.0)
    obs["resolution_day"] = resolution_day
    obs["censored"] = censored

    # Censoring blanks the outcomes that have not resolved yet.
    if censored.any():
        stage_day = created_day[:, None] + cum_delay
        cutoff = cfg.observation_cutoff_frac * cfg.n_periods
        for s, col in enumerate(["contacted", "qualified", "applied", "funded"]):
            unknown = (stage_day[:, s] > cutoff) & censored
            obs.loc[unknown, col] = np.nan
        obs.loc[censored, "realized_net_contribution"] = np.where(
            obs.loc[censored, "funded"].isna(),
            np.nan,
            obs.loc[censored, "realized_net_contribution"],
        )

    cat_cols = [
        "campaign_id",
        "geo_id",
        "product_id",
        "agent_id",
        "device",
        "attributed_channel",
    ]
    feature_columns = feat_cols + cat_cols + ["hour_of_day"]

    # ---------------- CRM noise -------------------------------------------------
    obs = _apply_crm_noise(obs, cfg, rng, feat_cols, channel_names)

    # ---------------- truth frame -------------------------------------------------
    truth = pd.DataFrame(
        {
            "lead_id": obs["lead_id"].to_numpy()[: len(obs)],
            "intent": _pad(intent, len(obs)),
            "u_conf": _pad(u_conf, len(obs)),
            "true_channel": _pad(channel_names[true_channel_idx], len(obs)),
            "gross_value": _pad(gross_value, len(obs)),
            "net_contribution": _pad(net_contribution, len(obs)),
            "expected_net_contribution": _pad(expected_net_contribution, len(obs)),
            "refunded_draw": _pad(refunded, len(obs)),
            "cpl": _pad(cpl, len(obs)),
            "resolution_day": _pad(resolution_day, len(obs)),
            "logged_action": _pad(logged_action, len(obs)),
            "logged_propensity": _pad(logged_propensity, len(obs)),
        }
    )
    for a, nm in enumerate(action_names):
        truth[f"p_funded_a{a}"] = _pad(p_funded[:, a], len(obs))
        truth[f"y_funded_a{a}"] = _pad(po_stage[a, :, 3].astype(float), len(obs))
        truth[f"y_qualified_a{a}"] = _pad(po_stage[a, :, 1].astype(float), len(obs))
        truth[f"minutes_a{a}"] = _pad(minutes[:, a], len(obs))
        truth[f"action_cost_a{a}"] = _pad(action_cost[:, a], len(obs))
        truth[f"ev_a{a}"] = _pad(ev[:, a], len(obs))
        truth[f"cate_a{a}"] = _pad(p_funded[:, a] - p_funded[:, CONTROL_ACTION], len(obs))
        truth[f"ev_uplift_a{a}"] = _pad(ev[:, a] - ev[:, CONTROL_ACTION], len(obs))
        # NB: prefixed, because the last stage is also called "funded" and an
        # unprefixed name would overwrite the overall funnel probability above.
        for s, sname in enumerate(_STAGES):
            truth[f"p_stage_{sname}_a{a}"] = _pad(p_stage[a, :, s], len(obs))

    truth = truth.reset_index(drop=True)
    obs = obs.reset_index(drop=True)

    return LeadDataset(
        observed=obs,
        truth=truth,
        config=cfg,
        feature_columns=feature_columns,
        categorical_columns=cat_cols,
        actions=action_names,
        meta={"channel_names": list(channel_names)},
    )


def _pad(arr: np.ndarray, target_len: int) -> np.ndarray:
    """Repeat-pad ground truth for duplicated rows introduced by CRM noise."""
    arr = np.asarray(arr)
    if len(arr) == target_len:
        return arr
    if len(arr) > target_len:
        return arr[:target_len]
    extra = target_len - len(arr)
    return np.concatenate([arr, arr[:extra]])


def _logging_propensities(
    rng: np.random.Generator,
    cfg: DGPConfig,
    intent: np.ndarray,
    u_conf: np.ndarray,
    x: np.ndarray,
    action_names: tuple[str, ...],
) -> np.ndarray:
    """Action probabilities of the historical policy, per lead."""
    n = len(intent)
    n_actions = len(action_names)
    if cfg.logging_policy == "randomized":
        p = np.asarray(action_probs_for(cfg), dtype=float)
        return np.tile(p, (n, 1))

    if cfg.logging_policy == "propensity_biased":
        # A plain CRM lead score: the observable part of intent.
        score = (intent - intent.mean()) / (intent.std() + _EPS)
        strength = cfg.logging_bias_strength
    elif cfg.logging_policy == "confounded":
        score = intent + cfg.logging_confounder_strength * u_conf
        score = (score - score.mean()) / (score.std() + _EPS)
        strength = cfg.logging_bias_strength
    elif cfg.logging_policy == "feedback":
        # A previous-generation model that only saw a few features, applied
        # nearly deterministically. This is how support gets destroyed.
        prev = x[:, :3] @ np.array([0.8, 0.5, -0.3]) + 0.3 * rng.standard_normal(n)
        score = (prev - prev.mean()) / (prev.std() + _EPS)
        strength = cfg.feedback_sharpness
    else:
        raise ValueError(f"unknown logging_policy {cfg.logging_policy!r}")

    # Action preference grows with the score: better leads get more expensive
    # treatment, which is exactly what a sensible sales floor does.
    tilt_by_name = {"none": 0.0, "sms": 0.4, "call": 1.0}
    tilt = np.array([tilt_by_name[nm] for nm in action_names])
    logits = strength * score[:, None] * tilt[None, :]
    logits = logits - logits.max(axis=1, keepdims=True)
    p = np.exp(logits)
    p = p / p.sum(axis=1, keepdims=True)
    p = np.clip(p, cfg.logging_min_propensity, None)
    return p / p.sum(axis=1, keepdims=True)


def _apply_crm_noise(
    obs: pd.DataFrame,
    cfg: DGPConfig,
    rng: np.random.Generator,
    feat_cols: list[str],
    channel_names: np.ndarray,
) -> pd.DataFrame:
    """Missing values, dropped stage transitions, bad source labels, dupes."""
    n = len(obs)

    if cfg.missing_rate > 0:
        for c in feat_cols:
            m = rng.random(n) < cfg.missing_rate
            obs.loc[m, c] = np.nan

    if cfg.crm_dropped_transition_rate > 0:
        # Intermediate stage flags go missing from the event log even though
        # the downstream stage fired. Real CRMs do this constantly.
        for col in ["contacted", "qualified", "applied"]:
            m = (rng.random(n) < cfg.crm_dropped_transition_rate) & (obs[col] == 1)
            obs.loc[m, col] = 0.0

    if cfg.crm_source_corruption_rate > 0:
        m = rng.random(n) < cfg.crm_source_corruption_rate
        obs.loc[m, "attributed_channel"] = rng.choice(channel_names, m.sum())
        obs.loc[m, "campaign_id"] = rng.integers(0, cfg.n_campaigns, m.sum())

    if cfg.duplicate_rate > 0:
        k = int(n * cfg.duplicate_rate)
        if k > 0:
            dup_idx = rng.choice(n, k, replace=False)
            dup = obs.iloc[dup_idx].copy()
            dup["lead_id"] = np.arange(n, n + k)
            # person_id is kept: the same human, entered twice. Split hygiene
            # checks rely on this.
            obs = pd.concat([obs, dup], ignore_index=True)

    return obs


def generate_regime(regime: str, **overrides: Any) -> LeadDataset:
    from .config import make_config

    return generate(make_config(regime, **overrides))
