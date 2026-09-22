"""Configuration for the lead-level data generating process.

Every knob that any benchmark regime needs lives here. Regimes are expressed as
*overrides* on top of :class:`DGPConfig` so that two regimes differ only in the
fields they name — no hidden divergence between scenarios.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

# Action space. Index order is fixed and load-bearing: index 0 is always the
# "do nothing" control arm (every treatment effect is measured against it) and
# the LAST index is always the expensive human action that consumes agent time.
#
# The primary lead track is binary -- "who gets scarce human sales time?" --
# because that is the actual product question, it keeps every model family
# directly comparable, and it lets the standard uplift metrics (Qini, AUUC)
# apply natively. The three-action set is a secondary track.
ACTIONS: tuple[str, ...] = ("none", "call")
ACTIONS_WITH_SMS: tuple[str, ...] = ("none", "sms", "call")
CONTROL_ACTION = 0


@dataclass
class DGPConfig:
    """Parameters of the synthetic lead economy.

    The defaults describe a mid-ticket, human-sales funnel: a lead costs real
    money to acquire, a call costs real agent minutes, most leads never fund,
    and deal value is heavily right-skewed.
    """

    name: str = "base"
    seed: int = 0
    n_leads: int = 20_000
    #: Which arms exist. Index 0 is control, the last index is the human action.
    action_set: tuple[str, ...] = ACTIONS

    # ---- structure ----------------------------------------------------
    n_campaigns: int = 12
    n_geos: int = 8
    n_products: int = 3
    n_agents: int = 20
    n_periods: int = 180  # days of lead flow
    n_numeric_features: int = 8
    n_factors: int = 3  # latent factors inducing feature correlation

    # ---- funnel base rates (probability scale, before covariates) ------
    # P(contact | action), P(qualified | contact), P(application | qualified),
    # P(funded | application). Base values are for the control arm.
    p_contact_base: float = 0.12
    p_qualified_base: float = 0.45
    p_application_base: float = 0.40
    p_funded_base: float = 0.45

    # ---- covariate effects (logit scale) ------------------------------
    beta_intent_contact: float = 1.10
    beta_intent_qualified: float = 0.90
    beta_intent_application: float = 0.70
    beta_intent_funded: float = 0.35
    beta_noise_scale: float = 0.35  # coefficients on the non-intent features

    # ---- treatment effects (logit scale, added to control logits) -----
    # tau_max is the peak effect; the effect is a Gaussian bump in the latent
    # intent variable centred at ``tau_center`` with width ``tau_width``.
    tau_max_sms: float = 0.55
    tau_max_call: float = 1.70
    tau_center: float = 0.0
    tau_width: float = 1.20
    # Fraction of the action effect that lands on each stage. Actions mostly
    # buy you *contact*; they nudge qualification and barely move funding.
    tau_stage_weights: tuple[float, float, float, float] = (1.0, 0.45, 0.20, 0.05)
    # Heterogeneity in treatment response driven by an observable feature.
    het_coef: float = 0.0
    het_feature: int = 1
    null_effect: bool = False  # negative control: actions do literally nothing

    # ---- hierarchy / random effects (logit scale sd) ------------------
    sd_campaign: float = 0.45
    sd_geo: float = 0.25
    sd_product: float = 0.35
    sd_agent: float = 0.20
    # Campaign-level modulation of the treatment effect (what partial pooling
    # is supposed to help with when campaigns are small).
    sd_campaign_tau: float = 0.35

    # ---- deal economics -----------------------------------------------
    value_mu_log: float = 8.6  # ~ $5.4k median gross deal value
    value_sigma_log: float = 0.85
    value_product_shift: tuple[float, ...] = (-0.45, 0.0, 0.55)
    value_intent_coef: float = 0.12
    margin_rate: float = 0.32
    servicing_cost_per_funded: float = 240.0
    refund_rate: float = 0.04  # clawback probability on funded deals

    # ---- effort and action costs --------------------------------------
    agent_cost_per_hour: float = 38.0
    call_minutes_mu_log: float = 2.05  # ~7.8 min median incl. wrap-up
    call_minutes_sigma_log: float = 0.55
    sms_minutes: float = 0.25
    # Correlation between required effort and conversion propensity. Positive
    # means the good leads are also the expensive ones.
    effort_intent_coef: float = 0.0
    #: Campaign-level random effect on handle time (log scale).
    #:
    #: Default 0.0 keeps the original sweep reproducible. It matters because
    #: with no campaign-level effort variation, a campaign-aggregated
    #: "profit per agent-hour" metric is a monotone transform of
    #: "profit per lead", so the two analytics baselines coincide by
    #: construction and RQ4 cannot be tested at the analytics level. The
    #: `campaign_effort_heterogeneity` regime turns it on.
    sd_campaign_effort: float = 0.0
    sms_direct_cost: float = 0.03
    call_direct_cost: float = 0.06  # telephony only; agent time is separate

    # ---- acquisition ----------------------------------------------------
    cpl_mu: float = 42.0
    cpl_sd: float = 14.0

    # ---- logging policy (how the historical data was collected) -------
    # one of: randomized | propensity_biased | confounded | feedback
    logging_policy: str = "randomized"
    #: Per-arm probabilities under randomized logging. Truncated/renormalised to
    #: ``len(action_set)``, so the same regime table works for both tracks.
    logging_action_probs: tuple[float, ...] = (0.5, 0.25, 0.5)
    logging_bias_strength: float = 1.5
    logging_confounder_strength: float = 1.2
    logging_min_propensity: float = 0.02
    # feedback loop: sharpness of the previous-generation model's thresholding
    feedback_sharpness: float = 6.0

    # ---- confounding ----------------------------------------------------
    confounder_outcome_strength: float = 0.0
    confounder_observed: bool = True  # if False the column is stripped

    # ---- time -----------------------------------------------------------
    seasonality_amplitude: float = 0.0
    seasonality_period: float = 30.0
    trend_per_period: float = 0.0
    drift_start_frac: float | None = None  # e.g. 0.7 => drift in last 30%
    drift_intent_shift: float = -0.8
    drift_tau_shift: float = -0.9

    # ---- observation quality --------------------------------------------
    delay_mean_days: tuple[float, float, float, float] = (0.5, 1.5, 4.0, 9.0)
    observation_cutoff_frac: float | None = None  # censor after this fraction
    missing_rate: float = 0.0
    crm_dropped_transition_rate: float = 0.0
    crm_source_corruption_rate: float = 0.0
    duplicate_rate: float = 0.0

    # ---- attribution -----------------------------------------------------
    # A channel that grabs last-touch credit far more often than it deserves.
    misleading_attribution: bool = False
    retargeting_lasttouch_share: float = 0.55
    retargeting_true_effect: float = 0.02

    def replace(self, **kwargs: Any) -> "DGPConfig":
        return dataclasses.replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Regimes. Each entry is a dict of overrides on top of DGPConfig defaults.
# ---------------------------------------------------------------------------
REGIMES: dict[str, dict[str, Any]] = {
    # -- the clean case: randomized treatment, no hidden confounding -------
    "easy_randomized": dict(
        logging_policy="randomized",
        het_coef=0.0,
    ),
    # -- many small segments, few observations each ------------------------
    "sparse": dict(
        n_campaigns=60,
        n_geos=20,
        sd_campaign=0.7,
        sd_campaign_tau=0.6,
        logging_policy="randomized",
    ),
    # -- rare outcomes ------------------------------------------------------
    "rare_outcome": dict(
        p_contact_base=0.09,
        p_qualified_base=0.25,
        p_application_base=0.22,
        p_funded_base=0.30,
        logging_policy="randomized",
    ),
    "very_rare_outcome": dict(
        p_contact_base=0.07,
        p_qualified_base=0.18,
        p_application_base=0.14,
        p_funded_base=0.22,
        logging_policy="randomized",
    ),
    # -- strongly heterogeneous treatment effect ---------------------------
    "strong_heterogeneity": dict(
        het_coef=1.30,
        tau_max_call=1.9,
        logging_policy="randomized",
    ),
    # -- THE central scenario: propensity ranking != uplift ranking --------
    # High-intent leads convert on their own (ceiling), so the action buys
    # nothing there; the incremental effect peaks in the middle of the
    # intent distribution.
    "propensity_not_uplift": dict(
        p_contact_base=0.30,
        beta_intent_contact=2.0,
        beta_intent_qualified=1.4,
        tau_center=-0.7,
        tau_width=0.75,
        tau_max_call=2.2,
        tau_max_sms=0.7,
        logging_policy="randomized",
    ),
    # -- agent-time heterogeneity: good leads are expensive to work --------
    "agent_time_heterogeneity": dict(
        effort_intent_coef=0.70,
        call_minutes_sigma_log=0.75,
        logging_policy="randomized",
    ),
    # -- handle time varies by SOURCE, not just by lead --------------------
    # Some campaigns produce leads that take three times as long to work.
    # This is the regime in which a campaign-level "profit per agent-hour"
    # report can differ from a campaign-level "profit per lead" report, and
    # therefore the only one where RQ4 is testable at the analytics level.
    "campaign_effort_heterogeneity": dict(
        sd_campaign_effort=0.55,
        effort_intent_coef=0.50,
        call_minutes_sigma_log=0.65,
        value_sigma_log=1.20,
        logging_policy="randomized",
    ),
    # -- heterogeneous deal value ------------------------------------------
    "value_heterogeneity": dict(
        value_sigma_log=1.35,
        value_intent_coef=0.0,
        logging_policy="randomized",
    ),
    # -- the product hypothesis's best case, all three at once --------------
    "capacity_value_heterogeneity": dict(
        het_coef=1.2,
        effort_intent_coef=0.6,
        value_sigma_log=1.25,
        tau_center=-0.6,
        tau_width=0.9,
        tau_max_call=2.0,
        p_contact_base=0.25,
        beta_intent_contact=1.7,
        logging_policy="randomized",
    ),
    # -- delayed outcomes + right censoring --------------------------------
    "delayed_censored": dict(
        delay_mean_days=(1.0, 3.0, 8.0, 18.0),
        observation_cutoff_frac=0.85,
        logging_policy="randomized",
    ),
    # -- seasonality and trend ---------------------------------------------
    "seasonality_trend": dict(
        seasonality_amplitude=0.45,
        trend_per_period=0.0025,
        logging_policy="randomized",
    ),
    # -- concept drift between train and test -------------------------------
    "concept_drift": dict(
        drift_start_frac=0.7,
        logging_policy="randomized",
    ),
    # -- observed confounding: the confounder is in X -----------------------
    "observed_confounding": dict(
        logging_policy="confounded",
        confounder_outcome_strength=1.1,
        confounder_observed=True,
    ),
    # -- hidden confounding: it is not -------------------------------------
    "hidden_confounding": dict(
        logging_policy="confounded",
        confounder_outcome_strength=1.1,
        confounder_observed=False,
    ),
    # -- historical policy picks treatment on observables -------------------
    "selection_bias": dict(
        logging_policy="propensity_biased",
        logging_bias_strength=2.2,
    ),
    # -- previous-generation model decides who gets contacted ---------------
    "policy_feedback_loop": dict(
        logging_policy="feedback",
        feedback_sharpness=7.0,
        logging_min_propensity=0.005,
    ),
    # -- dirty CRM ----------------------------------------------------------
    "noisy_crm": dict(
        missing_rate=0.12,
        crm_dropped_transition_rate=0.10,
        crm_source_corruption_rate=0.08,
        duplicate_rate=0.03,
        logging_policy="randomized",
    ),
    # -- last-touch credit goes to a channel that does nothing --------------
    "misleading_attribution": dict(
        misleading_attribution=True,
        logging_policy="randomized",
    ),
    # -- negative control: actions have zero effect -------------------------
    "negative_control_null_effect": dict(
        null_effect=True,
        logging_policy="randomized",
    ),
}


def make_config(regime: str, **overrides: Any) -> DGPConfig:
    """Build a :class:`DGPConfig` for a named regime."""
    if regime not in REGIMES:
        raise KeyError(f"unknown regime {regime!r}; known: {sorted(REGIMES)}")
    cfg = DGPConfig(name=regime, **REGIMES[regime])
    if overrides:
        cfg = cfg.replace(**overrides)
    return cfg


def action_probs_for(cfg: DGPConfig) -> tuple[float, ...]:
    """Randomized-logging probabilities matched to the configured action set."""
    names = cfg.action_set
    full = {"none": 0, "sms": 1, "call": 2}
    raw = [cfg.logging_action_probs[full[n]] for n in names]
    total = sum(raw)
    return tuple(p / total for p in raw)


def regime_names() -> list[str]:
    return list(REGIMES)
