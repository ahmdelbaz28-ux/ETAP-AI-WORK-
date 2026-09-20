"""
engine/optimizers/pso_core.py — Vectorized Particle Swarm Optimization (PSO) Engine.

High-performance, derivative-free metaheuristic optimization engine implemented
purely in NumPy. Provides robust global search with adaptive inertia weight decay,
Clerc-Kennedy constriction factor, Latin Hypercube initialization, velocity
clamping, boundary constraint projection, and deterministic seed repeatability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PSOConfig:
    """Configuration hyperparameters for Particle Swarm Optimization."""

    swarm_size: int = 40
    max_iter: int = 100
    w_max: float = 0.9  # Initial inertia weight
    w_min: float = 0.4  # Final inertia weight
    c1: float = 2.05  # Cognitive parameter (self-best attraction)
    c2: float = 2.05  # Social parameter (global-best attraction)
    use_constriction: bool = True  # Clerc-Kennedy constriction factor
    v_max_ratio: float = 0.2  # Max velocity as fraction of search range
    use_latin_hypercube: bool = True  # Latin Hypercube sampling for initial positions
    seed: Optional[int] = 42  # Seed for repeatable, auditable engineering results
    tol: float = 1e-7  # Convergence tolerance on objective improvement
    patience: int = 15  # Iterations without improvement before early stopping


@dataclass
class PSOResult:
    """Optimization outcome containing optimal decision vector and convergence telemetry."""

    best_position: np.ndarray
    best_fitness: float
    convergence_history: list[float] = field(default_factory=list)
    n_iterations: int = 0
    n_evaluations: int = 0
    converged: bool = False
    status_message: str = "Optimization completed successfully"


class ParticleSwarmOptimizer:
    """Vectorized, multi-dimensional Particle Swarm Optimizer.

    Supports continuous variable optimization with box constraints:
        minimize f(x)
        subject to: lb <= x <= ub
    """

    def __init__(self, config: Optional[PSOConfig] = None) -> None:
        self.config = config or PSOConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def _latin_hypercube_sample(
        self, n_samples: int, n_dim: int, lb: np.ndarray, ub: np.ndarray
    ) -> np.ndarray:
        """Generate Latin Hypercube samples across the search space."""
        # Divide each dimension into n_samples intervals
        intervals = np.linspace(0.0, 1.0, n_samples + 1)
        samples = np.zeros((n_samples, n_dim))

        for d in range(n_dim):
            # Draw random uniform points in each interval
            points = intervals[:-1] + self.rng.uniform(0.0, 1.0 / n_samples, size=n_samples)
            # Permute points across the dimension
            samples[:, d] = self.rng.permutation(points)

        # Scale to bounds [lb, ub]
        return lb + samples * (ub - lb)

    def optimize(
        self,
        fitness_fn: Callable[[np.ndarray], float],
        lb: Union[list[float], np.ndarray],
        ub: Union[list[float], np.ndarray],
        initial_guess: Optional[np.ndarray] = None,
    ) -> PSOResult:
        """Run PSO to find the global minimum of ``fitness_fn(x)``.

        Parameters
        ----------
        fitness_fn : Callable[[np.ndarray], float]
            Scalar objective function taking a 1D vector x and returning a real fitness value.
        lb : array_like
            Lower bounds for each decision variable.
        ub : array_like
            Upper bounds for each decision variable.
        initial_guess : Optional[np.ndarray]
            Optional seed vector injected into the first particle (e.g. from warm start).

        Returns
        -------
        PSOResult
            Result object containing the best position, best fitness, and telemetry.
        """
        lb_arr = np.asarray(lb, dtype=np.float64)
        ub_arr = np.asarray(ub, dtype=np.float64)

        if lb_arr.shape != ub_arr.shape:
            raise ValueError(f"Bounds shape mismatch: lb {lb_arr.shape} vs ub {ub_arr.shape}")
        if np.any(lb_arr > ub_arr):
            raise ValueError("Lower bounds must be less than or equal to upper bounds")

        n_dim = lb_arr.shape[0]
        n_particles = self.config.swarm_size
        span = ub_arr - lb_arr
        v_max = self.config.v_max_ratio * span

        # Constriction factor calculation
        phi = self.config.c1 + self.config.c2
        if self.config.use_constriction and phi > 4.0:
            chi = 2.0 / np.abs(2.0 - phi - np.sqrt(phi**2 - 4.0 * phi))
        else:
            chi = 1.0

        # Initialize particle positions
        if self.config.use_latin_hypercube and n_particles > 1:
            positions = self._latin_hypercube_sample(n_particles, n_dim, lb_arr, ub_arr)
        else:
            positions = lb_arr + self.rng.uniform(0.0, 1.0, size=(n_particles, n_dim)) * span

        # If an initial guess is provided, inject it into particle 0
        if initial_guess is not None:
            clamped_guess = np.clip(np.asarray(initial_guess, dtype=np.float64), lb_arr, ub_arr)
            positions[0] = clamped_guess

        # Initialize velocities uniformly within [-v_max, v_max]
        velocities = self.rng.uniform(-1.0, 1.0, size=(n_particles, n_dim)) * v_max

        # Evaluate initial fitness
        pbest_positions = np.copy(positions)
        pbest_fitness = np.zeros(n_particles, dtype=np.float64)
        n_evals = 0

        for i in range(n_particles):
            fit = float(fitness_fn(positions[i]))
            pbest_fitness[i] = fit
            n_evals += 1

        # Global best
        gbest_idx = int(np.argmin(pbest_fitness))
        gbest_pos = np.copy(pbest_positions[gbest_idx])
        gbest_fit = float(pbest_fitness[gbest_idx])

        history: list[float] = [gbest_fit]
        no_improve_count = 0
        converged = False

        # Main swarm iteration loop
        for iteration in range(self.config.max_iter):
            # Dynamic inertia weight linear decay
            w = self.config.w_max - (self.config.w_max - self.config.w_min) * (
                iteration / max(1, self.config.max_iter - 1)
            )

            # Stochastic random acceleration matrices
            r1 = self.rng.uniform(0.0, 1.0, size=(n_particles, n_dim))
            r2 = self.rng.uniform(0.0, 1.0, size=(n_particles, n_dim))

            # Velocity update
            cognitive = self.config.c1 * r1 * (pbest_positions - positions)
            social = self.config.c2 * r2 * (gbest_pos - positions)
            velocities = chi * (w * velocities + cognitive + social)

            # Velocity clamping
            velocities = np.clip(velocities, -v_max, v_max)

            # Position update with reflective boundary handling
            new_positions = positions + velocities

            # Handle lower bound violations (reflect)
            low_mask = new_positions < lb_arr
            new_positions[low_mask] = lb_arr[np.where(low_mask)[1]] + (
                lb_arr[np.where(low_mask)[1]] - new_positions[low_mask]
            )
            velocities[low_mask] *= -0.5  # Dampen and reverse velocity

            # Handle upper bound violations (reflect)
            high_mask = new_positions > ub_arr
            new_positions[high_mask] = ub_arr[np.where(high_mask)[1]] - (
                new_positions[high_mask] - ub_arr[np.where(high_mask)[1]]
            )
            velocities[high_mask] *= -0.5

            # Final safety clip to ensure precision within [lb, ub]
            positions = np.clip(new_positions, lb_arr, ub_arr)

            # Evaluate fitness of each particle
            iter_improved = False
            for i in range(n_particles):
                fitness = float(fitness_fn(positions[i]))
                n_evals += 1

                if fitness < pbest_fitness[i]:
                    pbest_fitness[i] = fitness
                    pbest_positions[i] = np.copy(positions[i])

                    if fitness < gbest_fit:
                        rel_improvement = (gbest_fit - fitness) / (abs(gbest_fit) + 1e-12)
                        gbest_fit = fitness
                        gbest_pos = np.copy(positions[i])
                        iter_improved = rel_improvement > self.config.tol

            history.append(gbest_fit)

            if iter_improved:
                no_improve_count = 0
            else:
                no_improve_count += 1

            if no_improve_count >= self.config.patience:
                converged = True
                logger.debug(
                    "PSO early stopping triggered at iteration %d (patience reached)",
                    iteration + 1,
                )
                break

        return PSOResult(
            best_position=gbest_pos,
            best_fitness=gbest_fit,
            convergence_history=history,
            n_iterations=iteration + 1,
            n_evaluations=n_evals,
            converged=converged,
            status_message=(
                f"Converged to tolerance {self.config.tol} at iteration {iteration + 1}"
                if converged
                else f"Reached maximum iterations ({self.config.max_iter})"
            ),
        )
