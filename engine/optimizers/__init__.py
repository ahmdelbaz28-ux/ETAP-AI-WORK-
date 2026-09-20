"""
engine/optimizers — Metaheuristic and numerical optimization package for AhmedETAP.

Provides derivative-free swarm intelligence (PSO), warm-start caching,
capacitor/DER placement, harmonic filter design, and Pareto frontier exploration.
"""

from engine.optimizers.pso_core import ParticleSwarmOptimizer, PSOConfig, PSOResult

__all__ = [
    "ParticleSwarmOptimizer",
    "PSOConfig",
    "PSOResult",
]
