"""Decision-theoretic core: EVPI, EVSI, and the invariants that catch bugs.

Why this module exists
----------------------
The first Layer 3 pass reported that a *free* experiment was not worth running
over 70% of the business-loss plane. That is impossible, and it is impossible
for a reason worth writing down: if information costs nothing, you can always
look at the result and then do exactly what you would have done anyway. So

    EVSI >= 0   whenever  C_experiment = 0

always. A model that violates it is not measuring the value of an experiment.

What the first pass actually measured was a **significance gate**:

    significant     -> take the action
    not significant -> do not take the action

That policy is *forced to obey the gate*, and a forced policy can easily be
worse than acting on the prior -- which is what produced the violation. The
gate discards everything except one bit, and then makes that bit binding.

Both policies are kept here. The gate is not a strawman: it is what most
experimentation practice actually does, so the gap between it and the optimal
policy is itself a finding rather than an error to be hidden.

Vocabulary follows the health-economics VOI literature, which is where this
machinery is most carefully worked out:

    EVPI  expected value of perfect information
    EVSI  expected value of sample information (this experiment, this method)
    ENBS  expected net benefit of sampling = EVSI - C_experiment

and the ordering `0 <= EVSI <= EVPI` must hold for any honest implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DecisionProblem:
    """A marketing budget decision under uncertainty about the true lift.

    ``theta`` is a grid of possible true effects (as a fraction, so 0.075 is
    a 7.5% lift). ``prior`` is the belief over that grid. ``utility`` is
    (n_actions, n_theta): the business outcome in currency of taking each
    action when each effect is the truth.

    Keeping utility as a full matrix rather than a false-positive /
    false-negative pair is deliberate: it lets the action set grow beyond
    act/don't-act (cut, hold, raise moderately, raise hard) without touching
    any of the machinery below.
    """

    theta: np.ndarray
    prior: np.ndarray
    utility: np.ndarray
    action_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not np.isclose(self.prior.sum(), 1.0):
            raise ValueError(f"prior must sum to 1, got {self.prior.sum()}")
        if self.utility.shape != (len(self.action_names), len(self.theta)):
            raise ValueError(
                f"utility must be (n_actions, n_theta) = "
                f"({len(self.action_names)}, {len(self.theta)}), "
                f"got {self.utility.shape}"
            )

    # -- baselines --------------------------------------------------------
    def value_no_experiment(self) -> float:
        """Best action under the prior alone. The opponent to beat."""
        return float((self.utility @ self.prior).max())

    def best_action_no_experiment(self) -> str:
        return self.action_names[int((self.utility @ self.prior).argmax())]

    def value_perfect_information(self) -> float:
        """Value if an oracle revealed theta before you chose."""
        return float((self.utility.max(axis=0) * self.prior).sum())

    def evpi(self) -> float:
        """Ceiling on what any experiment can be worth."""
        return self.value_perfect_information() - self.value_no_experiment()


def posterior(prior: np.ndarray, likelihood: np.ndarray) -> np.ndarray:
    """p(theta | y) for one observation. ``likelihood`` is p(y | theta)."""
    unnorm = prior * likelihood
    total = unnorm.sum()
    if total <= 0 or not np.isfinite(total):
        # An observation impossible under every theta tells you nothing;
        # falling back to the prior is the only defensible answer.
        return prior.copy()
    return unnorm / total


def value_of_signal(
    problem: DecisionProblem,
    likelihoods: np.ndarray,
    signal_probs: np.ndarray,
) -> float:
    """Expected value when the decision may *use* the signal optimally.

    ``likelihoods`` is (n_signals, n_theta) = p(y | theta).
    ``signal_probs`` is (n_signals,) = p(y), the marginal.

    The crucial difference from a gate: for every possible observation we
    re-derive the posterior and then pick the best action *for that
    posterior*. Ignoring the signal is always available, which is exactly why
    the result can never be worse than acting on the prior.
    """
    total = 0.0
    for y in range(likelihoods.shape[0]):
        post = posterior(problem.prior, likelihoods[y])
        total += signal_probs[y] * float((problem.utility @ post).max())
    return total


def evsi(problem: DecisionProblem, likelihoods: np.ndarray,
         signal_probs: np.ndarray) -> float:
    """Expected value of this experiment, before paying for it."""
    return value_of_signal(problem, likelihoods, signal_probs) - \
        problem.value_no_experiment()


def enbs(problem: DecisionProblem, likelihoods: np.ndarray,
         signal_probs: np.ndarray, experiment_cost: float) -> float:
    """Expected net benefit of sampling. Positive means RUN."""
    return evsi(problem, likelihoods, signal_probs) - experiment_cost


def value_of_significance_gate(
    problem: DecisionProblem,
    p_significant: np.ndarray,
    act_action: str,
    abstain_action: str,
) -> float:
    """Value of the policy the industry actually runs.

    ``p_significant`` is (n_theta,) = P(declare significant | theta).

    The action is *determined* by the gate rather than chosen to maximise
    posterior value. This is the whole difference, and it is why this quantity
    can fall below `value_no_experiment` -- an outcome that is a property of
    the policy, not a bug in the arithmetic.
    """
    act = problem.action_names.index(act_action)
    abstain = problem.action_names.index(abstain_action)
    value = (
        problem.prior * (
            p_significant * problem.utility[act]
            + (1.0 - p_significant) * problem.utility[abstain]
        )
    ).sum()
    return float(value)


def gate_information_loss(
    problem: DecisionProblem,
    likelihoods: np.ndarray,
    signal_probs: np.ndarray,
    p_significant: np.ndarray,
    act_action: str,
    abstain_action: str,
) -> float:
    """How much value the significance gate throws away, in currency.

    This is the number the research question now turns on: not "is the
    experiment worth running" but "how much of a worthwhile experiment does
    conventional practice discard at the last step".
    """
    return value_of_signal(problem, likelihoods, signal_probs) - \
        value_of_significance_gate(problem, p_significant, act_action,
                                   abstain_action)


# ---------------------------------------------------------------------------
# Invariants. These are asserted in tests, and also callable at runtime so a
# reported number can never quietly violate them.
# ---------------------------------------------------------------------------

def check_invariants(problem: DecisionProblem, likelihoods: np.ndarray,
                     signal_probs: np.ndarray, tol: float = 1e-6) -> dict:
    """0 <= EVSI <= EVPI, and free information never hurts."""
    v = evsi(problem, likelihoods, signal_probs)
    ceiling = problem.evpi()
    scale = max(abs(ceiling), 1.0)
    out = {
        "evsi": v,
        "evpi": ceiling,
        "evsi_non_negative": v >= -tol * scale,
        "evsi_below_evpi": v <= ceiling + tol * scale,
    }
    out["ok"] = bool(out["evsi_non_negative"] and out["evsi_below_evpi"])
    return out


def two_point_problem(
    pi: float, c_fp: float, c_fn: float, effect: float = 0.075
) -> DecisionProblem:
    """The simplest marketing decision: scale a channel, or don't.

    theta is either 0 (the channel does nothing) or `effect`. Scaling a dud
    costs `c_fp`; failing to scale a winner costs `c_fn`. Utilities are
    negative costs so that "maximise" is the right direction everywhere.

    This is the two-point prior the published data can support. It is a
    limitation, not a modelling choice -- see docs for why a real prior over
    effect *size* needs simulations at more than two true effects.
    """
    theta = np.array([0.0, effect])
    prior = np.array([1.0 - pi, pi])
    utility = np.array([
        [0.0, -c_fn],   # don't scale: fine if dud, costly if winner
        [-c_fp, 0.0],   # scale: costly if dud, fine if winner
    ])
    return DecisionProblem(theta, prior, utility, ("hold", "scale"))


# ---------------------------------------------------------------------------
# A budget decision with more than two answers.
#
# `two_point_problem` asks "act or don't". A marketing team does not face that
# question; it faces "how much". With two actions an experiment only has to
# say which side of a threshold theta falls on, so most of its precision is
# wasted. With five, the answer has to be located.
#
# A CORRECTION. An earlier version of this comment said that therefore
# "information is worth more" with a richer action set, and a test asserted it
# for nested sets. **That is false as a general claim.** Adding an action can
# raise the no-information baseline more than it raises the
# perfect-information value, and EVPI falls. Two equiprobable states:
#
#     a1 = (10, 0), a2 = (0, 10)   ->  no info 5, perfect 10, EVPI 5
#     add h = (6, 6), removing nothing
#                                  ->  no info 6, perfect 10, EVPI 4
#
# A strictly richer set with strictly lower EVPI. So `A subset of B` does not
# imply `EVPI(B) >= EVPI(A)`; see `test_nesting_does_not_guarantee_higher_evpi`.
#
# EVPI *is* monotone along the nested sequence used below, but that is a
# property of this payoff and this prior -- specifically, `hold` is in the
# smallest set and prior-optimal throughout, so the baseline never moves. The
# test asserts that condition rather than assuming it.
# ---------------------------------------------------------------------------

#: Spend multipliers for the default action set. Deliberately asymmetric:
#: cutting is cheap and reversible, raising hard commits inventory and
#: headcount, and real teams do not treat those as mirror images.
DEFAULT_MULTIPLIERS: tuple[float, ...] = (0.5, 0.8, 1.0, 1.25, 1.6)
DEFAULT_ACTIONS: tuple[str, ...] = (
    "cut hard", "cut", "hold", "increase", "increase hard",
)


def budget_problem(
    theta: np.ndarray,
    prior: np.ndarray,
    spend: float = 1_000_000.0,
    breakeven: float = 0.03,
    adjust_cost: float = 0.35,
    profit_per_lift: float = 4.0,
    multipliers: tuple[float, ...] = DEFAULT_MULTIPLIERS,
    action_names: tuple[str, ...] = DEFAULT_ACTIONS,
) -> DecisionProblem:
    """A five-action budget decision over a grid of true lifts.

    The payoff for moving spend by a fraction ``d = m - 1`` when the true
    lift is ``theta``::

        U(m, theta) = spend * d * profit_per_lift * (theta - breakeven)
                      - spend * adjust_cost * d**2

    The first term is the obvious one: spending more into a channel whose
    true lift clears breakeven earns money, and spending more into one that
    does not loses it, in proportion to how far off breakeven it is. The
    second is the part that makes the problem interesting -- a **quadratic
    adjustment cost**, so the optimal move is finite rather than "all in"
    whenever theta > breakeven. Without it the optimum is always the most
    extreme available action and the action set adds nothing.

    That makes the optimal action a monotone, non-degenerate function of
    theta, which is exactly what a two-point / two-action problem cannot
    represent: there, knowing *whether* theta clears a threshold is
    sufficient, so a significance bit is nearly a sufficient statistic. Here
    it is not, and the gap between S0 and S1 should widen.

    ``breakeven`` is where the economics live. A channel is not worth more
    money because its lift is "significant"; it is worth more money because
    its lift exceeds what the spend costs. Those are different questions and
    the whole track is about the distance between them.
    """
    theta = np.asarray(theta, dtype=float)
    prior = np.asarray(prior, dtype=float)
    if len(multipliers) != len(action_names):
        raise ValueError(
            f"{len(multipliers)} multipliers but {len(action_names)} names")

    d = np.asarray(multipliers, dtype=float) - 1.0
    gain = spend * profit_per_lift * np.outer(d, theta - breakeven)
    cost = (spend * adjust_cost * d**2)[:, None]
    return DecisionProblem(theta, prior, gain - cost, tuple(action_names))


def theta_grid(lo: float = -0.15, hi: float = 0.25, n: int = 81) -> np.ndarray:
    """A grid of true lifts, from a channel that destroys money to one that
    works very well. The negative half is not decoration: the question a
    business most needs answered is often whether to stop."""
    return np.linspace(lo, hi, n)


def spike_slab_prior(
    theta: np.ndarray, p_null: float = 0.45, mu: float = 0.04,
    sigma: float = 0.06, null_width: float = 0.005,
) -> np.ndarray:
    """Most channels do roughly nothing; the rest are spread around a modest
    positive lift with a real negative tail.

    A point mass at exactly zero cannot be represented on a grid, so the
    "spike" is a narrow normal of width ``null_width``. ``p_null`` is the
    share of prior mass on it.
    """
    theta = np.asarray(theta, dtype=float)
    spike = np.exp(-0.5 * (theta / null_width) ** 2)
    slab = np.exp(-0.5 * ((theta - mu) / sigma) ** 2)
    spike = spike / spike.sum()
    slab = slab / slab.sum()
    p = p_null * spike + (1.0 - p_null) * slab
    return p / p.sum()


def action_boundaries(
    breakeven: float = 0.03,
    adjust_cost: float = 0.35,
    profit_per_lift: float = 4.0,
    multipliers: tuple[float, ...] = DEFAULT_MULTIPLIERS,
) -> np.ndarray:
    """The true lifts at which the optimal budget action changes.

    Setting `U(d_i, theta) = U(d_j, theta)` for two adjacent actions::

        d_i k (theta - b) - c d_i^2  =  d_j k (theta - b) - c d_j^2
        k (theta - b)(d_i - d_j)     =  c (d_i - d_j)(d_i + d_j)
        theta*                       =  b + c (d_i + d_j) / k

    **`breakeven` is not a decision boundary.** It is where the linear gain
    term changes sign, and with a quadratic adjustment cost that is not where
    the optimal action changes. For the defaults -- b = 3%, c = 0.35, k = 4,
    multipliers (0.5, 0.8, 1.0, 1.25, 1.6) -- the four boundaries are

        cut hard | cut            -3.1250%
        cut      | hold           +1.2500%
        hold     | increase       +5.1875%
        increase | increase hard  +10.4375%

    and +3% sits between the second and third, where nothing happens.

    This matters for where to spend simulator time: a theta grid dense at the
    economic breakeven is dense in the wrong place. Densify at the boundaries,
    because that is where a small change in belief changes what the business
    does -- which is the only thing EVSI is measuring.
    """
    d = np.asarray(multipliers, dtype=float) - 1.0
    if np.any(np.diff(d) <= 0):
        raise ValueError("multipliers must be strictly increasing")
    return breakeven + adjust_cost * (d[:-1] + d[1:]) / profit_per_lift
