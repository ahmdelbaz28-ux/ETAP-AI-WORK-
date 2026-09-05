"""
Consolidated Load Flow Solver
=============================

This module provides backward-compatibility re-exports from the canonical
`load_flow.load_flow` implementation to eliminate code duplication.
"""

from load_flow.load_flow import LoadFlowSolver

__all__ = ["LoadFlowSolver"]
