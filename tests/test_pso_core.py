"""
tests/test_pso_core.py — Unit Tests for the Vectorized Particle Swarm Optimization Core.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig, PSOResult


def test_pso_config_defaults():
    config = PSOConfig()
    assert config.swarm_size == 40
    assert config.max_iter == 100
    assert config.w_max == 0.9
    assert config.w_min == 0.4
    assert config.c1 == 2.05
    assert config.c2 == 2.05
    assert config.use_constriction is True
    assert config.seed == 42


def test_pso_sphere_optimization():
    """Verify convergence on n-dimensional convex Sphere function f(x) = sum(x^2)."""
    pso = ParticleSwarmOptimizer(PSOConfig(swarm_size=30, max_iter=60, seed=42))
    lb = [-5.0, -5.0, -5.0]
    ub = [5.0, 5.0, 5.0]

    result = pso.optimize(lambda x: np.sum(x**2), lb=lb, ub=ub)

    assert isinstance(result, PSOResult)
    assert result.best_fitness < 1e-5
    assert np.all(np.abs(result.best_position) < 1e-2)
    assert len(result.convergence_history) > 0
    assert result.n_evaluations > 0


def test_pso_rastrigin_multimodal():
    """Verify global search on non-convex Rastrigin function with multiple local minima."""
    def rastrigin(x):
        return 10.0 * len(x) + np.sum(x**2 - 10.0 * np.cos(2.0 * np.pi * x))

    pso = ParticleSwarmOptimizer(PSOConfig(swarm_size=40, max_iter=80, seed=42))
    lb = [-5.12, -5.12]
    ub = [5.12, 5.12]

    result = pso.optimize(rastrigin, lb=lb, ub=ub)
    assert result.best_fitness < 1e-2
    assert np.all(np.abs(result.best_position) < 0.05)


def test_pso_deterministic_repeatability():
    """Verify that identical seed guarantees exact 100% numerical repeatability."""
    cfg = PSOConfig(swarm_size=25, max_iter=30, seed=123)
    pso1 = ParticleSwarmOptimizer(cfg)
    res1 = pso1.optimize(lambda x: np.sum((x - 1.5)**2), lb=[-3.0]*2, ub=[3.0]*2)

    pso2 = ParticleSwarmOptimizer(cfg)
    res2 = pso2.optimize(lambda x: np.sum((x - 1.5)**2), lb=[-3.0]*2, ub=[3.0]*2)

    assert res1.best_fitness == res2.best_fitness
    np.testing.assert_array_equal(res1.best_position, res2.best_position)


def test_pso_boundary_clamping():
    """Verify that particles never violate decision vector box constraints."""
    pso = ParticleSwarmOptimizer(PSOConfig(swarm_size=20, max_iter=25, seed=42))
    lb = np.array([2.0, 3.0])
    ub = np.array([4.0, 5.0])

    # Objective pushes towards negative infinity (far below lb)
    result = pso.optimize(lambda x: np.sum(x), lb=lb, ub=ub)

    assert np.all(result.best_position >= lb - 1e-9)
    assert np.all(result.best_position <= ub + 1e-9)


def test_pso_initial_guess_injection():
    """Verify that a warm-start initial guess can be injected into the swarm."""
    guess = np.array([1.234, 2.345])
    pso = ParticleSwarmOptimizer(PSOConfig(swarm_size=20, max_iter=10, seed=42))

    res = pso.optimize(
        lambda x: np.sum((x - guess)**2),
        lb=[0.0, 0.0],
        ub=[5.0, 5.0],
        initial_guess=guess,
    )
    # With exact guess injected, initial fitness is 0.0
    assert res.best_fitness < 1e-6
