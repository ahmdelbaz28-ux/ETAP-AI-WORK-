"""
Load flow entrypoint.

The repository keeps two solvers:
- load_flow_solver_fixed.py: the corrected Newton-Raphson implementation
- this file: compatibility wrapper for imports (e.g., validation_suite.py)

Validation suite imports:
    from load_flow.load_flow import LoadFlowSolver

So we re-export the fixed solver to ensure correctness.
"""

from load_flow.load_flow_solver_fixed import LoadFlowSolver  # noqa: F401
