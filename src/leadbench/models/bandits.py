"""Contextual bandits for the online track.

These are linear (disjoint-arm) bandits over the shared feature encoding. They
model the *outcome probability* rather than the dollar reward directly, because
deal value is lognormal with a fat tail and a linear bandit on raw dollars is
mostly estimating noise. The probability is then combined with the same deal
value and effort models every offline candidate uses, so the online-vs-offline
comparison is about the learning loop and nothing else.

All three are warm-started on the identical historical training data the
offline models get. The bandit's only advantage is that it keeps learning.
"""

from __future__ import annotations

import numpy as np


class OnlineLearner:
    """Per-arm linear model with an exploration rule."""

    name = "online"
    explores = True

    def __init__(self, n_actions: int, n_features: int, seed: int = 0, ridge: float = 1.0):
        self.n_actions = n_actions
        self.d = n_features + 1  # +1 for the intercept
        self.rng = np.random.default_rng(seed)
        self.A = [np.eye(self.d) * ridge for _ in range(n_actions)]
        self.b = [np.zeros(self.d) for _ in range(n_actions)]
        self._Ainv = [np.eye(self.d) / ridge for _ in range(n_actions)]
        self._n_seen = np.zeros(n_actions)

    @staticmethod
    def _aug(X: np.ndarray) -> np.ndarray:
        return np.column_stack([np.ones(len(X)), X])

    def update(self, X: np.ndarray, actions: np.ndarray, rewards: np.ndarray) -> None:
        Z = self._aug(X)
        for a in range(self.n_actions):
            m = actions == a
            if not m.any():
                continue
            Za, ra = Z[m], np.asarray(rewards, float)[m]
            self.A[a] += Za.T @ Za
            self.b[a] += Za.T @ ra
            self._Ainv[a] = np.linalg.pinv(self.A[a])
            self._n_seen[a] += m.sum()

    def warm_start(self, X, actions, rewards) -> None:
        self.update(X, actions, rewards)

    def _theta(self, a: int) -> np.ndarray:
        return self._Ainv[a] @ self.b[a]

    def _mean(self, Z: np.ndarray) -> np.ndarray:
        return np.column_stack([Z @ self._theta(a) for a in range(self.n_actions)])

    def _sigma(self, Z: np.ndarray) -> np.ndarray:
        out = np.zeros((len(Z), self.n_actions))
        for a in range(self.n_actions):
            out[:, a] = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", Z, self._Ainv[a], Z), 0))
        return out

    def score(self, X: np.ndarray) -> np.ndarray:
        """Optimistic / sampled probability estimate per arm, shape (n, A)."""
        raise NotImplementedError

    def mean_probability(self, X: np.ndarray) -> np.ndarray:
        return np.clip(self._mean(self._aug(X)), 0.0, 1.0)


class LinUCB(OnlineLearner):
    """Disjoint LinUCB (Li et al., 2010). Optimism in the face of uncertainty."""

    name = "linucb"

    def __init__(self, *args, alpha: float = 0.5, **kw):
        super().__init__(*args, **kw)
        self.alpha = alpha

    def score(self, X: np.ndarray) -> np.ndarray:
        Z = self._aug(X)
        return np.clip(self._mean(Z) + self.alpha * self._sigma(Z), 0.0, 1.0)


class ThompsonSampling(OnlineLearner):
    """Linear Thompson sampling: draw a coefficient vector, act greedily on it."""

    name = "thompson"

    def __init__(self, *args, v: float = 0.25, **kw):
        super().__init__(*args, **kw)
        self.v = v

    def score(self, X: np.ndarray) -> np.ndarray:
        Z = self._aug(X)
        out = np.zeros((len(Z), self.n_actions))
        for a in range(self.n_actions):
            cov = (self.v**2) * self._Ainv[a]
            cov = 0.5 * (cov + cov.T) + 1e-9 * np.eye(self.d)
            theta = self.rng.multivariate_normal(self._theta(a), cov, method="cholesky")
            out[:, a] = Z @ theta
        return np.clip(out, 0.0, 1.0)


class EpsilonGreedy(OnlineLearner):
    """The baseline every bandit paper should have to beat and usually does not."""

    name = "epsilon_greedy"

    def __init__(self, *args, epsilon: float = 0.10, **kw):
        super().__init__(*args, **kw)
        self.epsilon = epsilon

    def score(self, X: np.ndarray) -> np.ndarray:
        Z = self._aug(X)
        mean = np.clip(self._mean(Z), 0.0, 1.0)
        explore = self.rng.random(len(Z)) < self.epsilon
        if explore.any():
            # Randomise the arm ordering for the exploring leads.
            noise = self.rng.random((explore.sum(), self.n_actions))
            mean[explore] = noise
        return mean


class GreedyLinear(OnlineLearner):
    """No exploration at all. Isolates how much of the bandit's edge is learning
    online versus exploring (section 37: 'without exploration')."""

    name = "greedy_online"
    explores = False

    def score(self, X: np.ndarray) -> np.ndarray:
        return np.clip(self._mean(self._aug(X)), 0.0, 1.0)


ONLINE_LEARNERS = {
    "linucb": LinUCB,
    "thompson": ThompsonSampling,
    "epsilon_greedy": EpsilonGreedy,
    "greedy_online": GreedyLinear,
}
