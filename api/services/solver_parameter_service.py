"""Solver parameters service with database persistence.

Replaces in-memory dictionaries with real database storage (PostgreSQL/SQLite).
Supports project-scoped and global default parameters.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.solver_parameters import ProjectSolverParameters

DEFAULT_CONVERGENCE_TOLERANCE = 1e-5
DEFAULT_MAX_ITERATIONS = 50

GLOBAL_SCOPE_KEY = "__global__"


def get_default_parameters() -> Dict[str, Any]:
    """Return default Newton-Raphson solver parameters."""
    return {
        "convergence_tolerance": DEFAULT_CONVERGENCE_TOLERANCE,
        "solver_convergence_tolerance": DEFAULT_CONVERGENCE_TOLERANCE,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
    }


async def load_solver_params(
    project_id: Optional[str],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Retrieve solver parameters from the database for a given project or global scope.

    Falls back to global scope or system defaults if no project record exists.
    """
    key = project_id.strip() if project_id and project_id.strip() else GLOBAL_SCOPE_KEY

    stmt = select(ProjectSolverParameters).where(ProjectSolverParameters.project_id == key)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if record is not None:
        return {
            "convergence_tolerance": record.convergence_tolerance,
            "solver_convergence_tolerance": record.convergence_tolerance,
            "max_iterations": record.max_iterations,
        }

    # If scoped and not found, check global scope
    if key != GLOBAL_SCOPE_KEY:
        stmt_global = select(ProjectSolverParameters).where(
            ProjectSolverParameters.project_id == GLOBAL_SCOPE_KEY
        )
        res_global = await db.execute(stmt_global)
        record_global = res_global.scalar_one_or_none()
        if record_global is not None:
            return {
                "convergence_tolerance": record_global.convergence_tolerance,
                "solver_convergence_tolerance": record_global.convergence_tolerance,
                "max_iterations": record_global.max_iterations,
            }

    return get_default_parameters()


async def save_solver_params(
    project_id: Optional[str],
    params: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Persist solver parameters to the database for a given project or global scope."""
    key = project_id.strip() if project_id and project_id.strip() else GLOBAL_SCOPE_KEY

    stmt = select(ProjectSolverParameters).where(ProjectSolverParameters.project_id == key)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    tol = float(
        params.get(
            "convergence_tolerance",
            params.get("solver_convergence_tolerance", DEFAULT_CONVERGENCE_TOLERANCE),
        )
    )
    max_iter = int(params.get("max_iterations", DEFAULT_MAX_ITERATIONS))

    if record is None:
        record = ProjectSolverParameters(
            project_id=key,
            convergence_tolerance=tol,
            max_iterations=max_iter,
            acceleration_factor=1.6,
        )
        db.add(record)
    else:
        record.convergence_tolerance = tol
        record.max_iterations = max_iter
        db.add(record)

    await db.commit()
    await db.refresh(record)

    return {
        "convergence_tolerance": record.convergence_tolerance,
        "solver_convergence_tolerance": record.convergence_tolerance,
        "max_iterations": record.max_iterations,
    }
