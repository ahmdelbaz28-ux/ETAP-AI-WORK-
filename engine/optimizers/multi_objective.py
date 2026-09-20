"""
engine/optimizers/multi_objective.py — Multi-Objective Particle Swarm Optimization (MOPSO).

Computes the Pareto Optimal Frontier for multi-criteria power engineering decisions
(e.g., Generation Cost vs Transmission Losses vs Voltage Reliability vs Capex).
Employs an external Pareto Archive with crowding distance diversity preservation
to equip engineers with interactive design trade-offs rather than a single black-box output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Union

import numpy as np

from engine.optimizers.pso_core import PSOConfig

logger = logging.getLogger(__name__)


@dataclass
class ParetoPoint:
    """A non-dominated engineering design on the Pareto frontier."""

    decision_vector: np.ndarray
    objectives: np.ndarray  # [f1, f2, ...]
    crowding_distance: float = 0.0
    tag: str = ""


@dataclass
class ParetoFrontierResult:
    """Full Pareto frontier of non-dominated solutions."""

    pareto_points: List[ParetoPoint]
    n_points: int
    objective_names: List[str]
    n_evaluations: int
    trade_off_summary: str = ""

    def get_objective_matrix(self) -> np.ndarray:
        """Return (N x M) matrix of objective values for all Pareto points."""
        if not self.pareto_points:
            return np.empty((0, len(self.objective_names)))
        return np.array([pt.objectives for pt in self.pareto_points])


class MultiObjectivePSO:
    """Multi-Objective Particle Swarm Optimizer (MOPSO) with External Archive."""

    def __init__(
        self,
        n_objectives: int = 2,
        objective_names: Optional[List[str]] = None,
        archive_size: int = 50,
        swarm_size: int = 40,
        max_iter: int = 60,
        seed: int = 42,
    ) -> None:
        self.m = n_objectives
        self.objective_names = objective_names or [f"Objective_{i+1}" for i in range(n_objectives)]
        self.archive_size = archive_size
        self.swarm_size = swarm_size
        self.max_iter = max_iter
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def _dominates(self, obj_a: np.ndarray, obj_b: np.ndarray) -> bool:
        """Return True if obj_a Pareto-dominates obj_b (all objectives minimized)."""
        return bool(np.all(obj_a <= obj_b) and np.any(obj_a < obj_b))

    def _update_archive(
        self,
        archive: List[ParetoPoint],
        new_point: ParetoPoint,
    ) -> List[ParetoPoint]:
        """Update non-dominated archive with a candidate point."""
        # Check if new point is dominated by any point in the archive
        for member in archive:
            if self._dominates(member.objectives, new_point.objectives):
                return archive

        # Filter out points in the archive dominated by new_point
        filtered = [pt for pt in archive if not self._dominates(new_point.objectives, pt.objectives)]
        filtered.append(new_point)

        # Prune if archive exceeds capacity based on crowding distance
        if len(filtered) > self.archive_size:
            filtered = self._prune_archive(filtered, self.archive_size)

        return filtered

    def _prune_archive(self, points: List[ParetoPoint], target_size: int) -> List[ParetoPoint]:
        """Prune archive to target_size using crowding distance to maximize diversity."""
        n = len(points)
        for pt in points:
            pt.crowding_distance = 0.0

        for m_idx in range(self.m):
            points.sort(key=lambda p: p.objectives[m_idx])
            points[0].crowding_distance = float("inf")
            points[-1].crowding_distance = float("inf")

            span = points[-1].objectives[m_idx] - points[0].objectives[m_idx]
            if abs(span) > 1e-9:
                for i in range(1, n - 1):
                    dist = (points[i + 1].objectives[m_idx] - points[i - 1].objectives[m_idx]) / span
                    points[i].crowding_distance += dist

        # Keep points with largest crowding distance (most diverse)
        points.sort(key=lambda p: p.crowding_distance, reverse=True)
        return points[:target_size]

    def optimize(
        self,
        vector_fitness_fn: Callable[[np.ndarray], np.ndarray],
        lb: Union[List[float], np.ndarray],
        ub: Union[List[float], np.ndarray],
    ) -> ParetoFrontierResult:
        """Compute the Pareto frontier for vector_fitness_fn(x) -> [f1, f2, ...]."""
        lb_arr = np.asarray(lb, dtype=np.float64)
        ub_arr = np.asarray(ub, dtype=np.float64)
        n_dim = len(lb_arr)
        span = ub_arr - lb_arr
        v_max = 0.2 * span

        # Initialize particles
        positions = lb_arr + self.rng.uniform(0.0, 1.0, size=(self.swarm_size, n_dim)) * span
        velocities = self.rng.uniform(-1.0, 1.0, size=(self.swarm_size, n_dim)) * v_max

        pbest_positions = np.copy(positions)
        pbest_objs = np.zeros((self.swarm_size, self.m), dtype=np.float64)

        archive: List[ParetoPoint] = []
        n_evals = 0

        for i in range(self.swarm_size):
            objs = np.asarray(vector_fitness_fn(positions[i]), dtype=np.float64)
            n_evals += 1
            pbest_objs[i] = objs
            archive = self._update_archive(archive, ParetoPoint(np.copy(positions[i]), objs))

        # Iteration loop
        for iteration in range(self.max_iter):
            w = 0.9 - 0.5 * (iteration / max(1, self.max_iter - 1))

            for i in range(self.swarm_size):
                # Leader selection: pick uniformly from the diverse archive
                leader = archive[self.rng.integers(0, len(archive))]
                gbest_pos = leader.decision_vector

                r1 = self.rng.uniform(0.0, 1.0, size=n_dim)
                r2 = self.rng.uniform(0.0, 1.0, size=n_dim)

                velocities[i] = (
                    w * velocities[i]
                    + 1.8 * r1 * (pbest_positions[i] - positions[i])
                    + 1.8 * r2 * (gbest_pos - positions[i])
                )
                velocities[i] = np.clip(velocities[i], -v_max, v_max)

                # Update position
                positions[i] = np.clip(positions[i] + velocities[i], lb_arr, ub_arr)

                # Evaluate objectives
                objs = np.asarray(vector_fitness_fn(positions[i]), dtype=np.float64)
                n_evals += 1

                # Update personal best if candidate dominates previous pbest
                if self._dominates(objs, pbest_objs[i]):
                    pbest_objs[i] = objs
                    pbest_positions[i] = np.copy(positions[i])
                elif not self._dominates(pbest_objs[i], objs):
                    # Incomparable: randomly replace with 50% probability
                    if self.rng.uniform() < 0.5:
                        pbest_objs[i] = objs
                        pbest_positions[i] = np.copy(positions[i])

                # Update archive
                archive = self._update_archive(archive, ParetoPoint(np.copy(positions[i]), objs))

        # Sort archive by first objective for clean plotting and inspection
        archive.sort(key=lambda p: p.objectives[0])

        summary = (
            f"Discovered {len(archive)} Pareto-optimal non-dominated trade-off solutions "
            f"across {self.m} criteria ({', '.join(self.objective_names)}) in {n_evals} evaluations."
        )

        return ParetoFrontierResult(
            pareto_points=archive,
            n_points=len(archive),
            objective_names=self.objective_names,
            n_evaluations=n_evals,
            trade_off_summary=summary,
        )
