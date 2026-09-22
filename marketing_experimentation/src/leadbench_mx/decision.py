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
