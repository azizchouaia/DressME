"""Linear Thompson Sampling, one model per user (adapted from dressme_bandit.py). Only numpy.

Bayesian linear regression: reward ~ x . theta, precision A, b; mean theta = A^-1 b.
Choosing draws ONE theta ~ N(mean, v^2 A^-1) per batch and orders the candidates by x . theta:
uncertain directions vary more -> natural exploration. Everything goes through a Cholesky factor of A.
"""

import numpy as np


class LinearTS:
    def __init__(self, dim: int, prior_mean=None, prior_strength: float = 1.0, v: float = 0.3):
        self.dim = dim
        self.v = float(v)
        self.prior_strength = float(prior_strength)
        self.prior_mean = np.zeros(dim) if prior_mean is None else np.asarray(prior_mean, dtype=float).copy()
        if self.prior_mean.shape != (dim,):
            raise ValueError(f"prior_mean has shape {self.prior_mean.shape}, expected ({dim},)")
        self.A = self.prior_strength * np.eye(dim)
        self.b = self.A @ self.prior_mean  # warm start: the prior counts like prior_strength swipes
        self.n_updates = 0

    # --- linear algebra ------------------------------------------------------------------------------
    def _chol(self) -> np.ndarray:
        try:
            return np.linalg.cholesky(self.A)
        except np.linalg.LinAlgError:  # A is SPD by construction; guard against round-off
            return np.linalg.cholesky(self.A + 1e-9 * np.trace(self.A) / self.dim * np.eye(self.dim))

    @property
    def mean(self) -> np.ndarray:
        L = self._chol()
        return np.linalg.solve(L.T, np.linalg.solve(L, self.b))

    def std(self) -> np.ndarray:
        """Posterior std of each weight: v * sqrt(diag(A^-1))."""
        L_inv = np.linalg.inv(self._chol())
        return self.v * np.sqrt(np.sum(L_inv * L_inv, axis=0))

    def sample_theta(self, rng: np.random.Generator) -> np.ndarray:
        """theta ~ N(mean, v^2 A^-1): with A = L L^T, mean + v * L^-T z has exactly this covariance."""
        L = self._chol()
        mean = np.linalg.solve(L.T, np.linalg.solve(L, self.b))
        return mean + self.v * np.linalg.solve(L.T, rng.standard_normal(self.dim))

    # --- decisions -----------------------------------------------------------------------------------
    def choose(self, X, k: int | None = None, rng: np.random.Generator | None = None):
        """One theta draw for the whole batch. Returns (order of the top-k rows, scores of every row)."""
        X = np.asarray(X, dtype=float)
        theta = self.sample_theta(rng or np.random.default_rng())
        scores = X @ theta
        order = np.argsort(-scores, kind="stable")
        return order[: k or len(order)], scores

    def rank(self, X, k: int | None = None):
        """Ranking by the mean model, no exploration (for 'other suggestions' lists)."""
        scores = np.asarray(X, dtype=float) @ self.mean
        order = np.argsort(-scores, kind="stable")
        return order[: k or len(order)], scores

    def update(self, x, reward: float, weight: float = 1.0) -> None:
        x = np.asarray(x, dtype=float)
        self.A += weight * np.outer(x, x)
        self.b += weight * reward * x
        self.n_updates += 1

    def shift_prior(self, new_prior) -> None:
        """Replaces the prior, keeping every update: b = s * prior + sum(w r x), so only s * delta moves."""
        new_prior = np.asarray(new_prior, dtype=float)
        self.b += self.prior_strength * (new_prior - self.prior_mean)
        self.prior_mean = new_prior.copy()

    # --- persistence -----------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "dim": self.dim,
            "A": self.A.tolist(),
            "b": self.b.tolist(),
            "v": self.v,
            "prior_mean": self.prior_mean.tolist(),
            "prior_strength": self.prior_strength,
            "n_updates": self.n_updates,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LinearTS":
        m = cls(
            dim=int(d["dim"]),
            prior_mean=d.get("prior_mean"),
            prior_strength=d.get("prior_strength", 1.0),
            v=d["v"],
        )
        m.A, m.b = np.array(d["A"], dtype=float), np.array(d["b"], dtype=float)
        m.n_updates = int(d.get("n_updates", 0))
        return m

    def to_bytes(self) -> tuple[bytes, bytes, bytes]:
        """(A, b, prior_mean) as float64 bytes, for the bytea columns of bandit_state."""
        return (
            self.A.astype("<f8").tobytes(),
            self.b.astype("<f8").tobytes(),
            self.prior_mean.astype("<f8").tobytes(),
        )

    @classmethod
    def from_bytes(
        cls,
        dim: int,
        A: bytes,
        b: bytes,
        prior_mean: bytes,
        prior_strength: float,
        v: float,
        n_updates: int = 0,
    ) -> "LinearTS":
        m = cls(
            dim=dim, prior_mean=np.frombuffer(prior_mean, dtype="<f8"), prior_strength=prior_strength, v=v
        )
        m.A = np.frombuffer(A, dtype="<f8").reshape(dim, dim).copy()
        m.b = np.frombuffer(b, dtype="<f8").copy()
        m.n_updates = n_updates
        return m
