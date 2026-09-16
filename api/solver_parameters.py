"""
api/solver_parameters.py — Solver Parameters Management API.

Provides CRUD endpoints for managing power-flow solver parameters that
control convergence behaviour, iteration limits, and acceleration.

Exposes endpoints under the ``/api/v1/studies/parameters`` prefix:

* ``GET  /``  — Retrieve current solver parameters
* ``POST /``  — Create / overwrite all solver parameters
* ``PUT  /``  — Partially update individual solver parameters

Parameters are held in an in-memory store (module-level dict) and
persist across requests for the lifetime of the process.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key
from api.services.solver_parameter_service import (
    DEFAULT_CONVERGENCE_TOLERANCE,
    load_solver_params,
    save_solver_params,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SolverParametersBase(BaseModel):
    """Base model with shared solver-parameter field definitions."""

    model_config = ConfigDict(populate_by_name=True)

    convergence_tolerance: float = Field(
        default=1e-5,
        ge=1e-6,
        le=1e-3,
        description=(
            "Convergence tolerance for the power-flow solver. "
            "Smaller values yield more precise results at the cost of "
            "additional iterations. Range: 1e-6 to 1e-3."
        ),
    )
    max_iterations: int = Field(
        default=50,
        ge=10,
        le=200,
        description=(
            "Maximum number of iterations the solver will attempt before "
            "declaring non-convergence. Range: 10 to 200."
        ),
    )
    acceleration_factor: float = Field(
        default=1.6,
        ge=1.0,
        le=2.0,
        description=(
            "Acceleration (relaxation) factor applied during the iterative "
            "solve. Values closer to 2.0 speed up convergence but may "
            "cause oscillation. Range: 1.0 to 2.0."
        ),
    )


class SolverParametersCreate(BaseModel):
    """Request body for creating/overwriting all solver parameters."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    convergence_tolerance: Optional[float] = Field(default=None, ge=1e-6, le=1e-3)
    solver_convergence_tolerance: Optional[float] = Field(default=None, ge=1e-6, le=1e-3)
    max_iterations: int = Field(default=50, ge=10, le=200)
    acceleration_factor: float = Field(default=1.6, ge=1.0, le=2.0)


class SolverParametersUpdate(BaseModel):
    """Request body for partially updating solver parameters."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    convergence_tolerance: Optional[float] = Field(
        default=None,
        ge=1e-6,
        le=1e-3,
        description="Updated convergence tolerance (1e-6 to 1e-3).",
    )
    solver_convergence_tolerance: Optional[float] = Field(
        default=None,
        ge=1e-6,
        le=1e-3,
        description="Updated convergence tolerance (1e-6 to 1e-3).",
    )
    max_iterations: Optional[int] = Field(
        default=None,
        ge=10,
        le=200,
        description="Updated maximum iterations (10 to 200).",
    )
    acceleration_factor: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=2.0,
        description="Updated acceleration factor (1.0 to 2.0).",
    )


class SolverParametersResponse(BaseModel):
    """Response model returned by all solver-parameter endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    convergence_tolerance: float = Field(default=1e-5, ge=1e-6, le=1e-3)
    solver_convergence_tolerance: float = Field(default=1e-5, ge=1e-6, le=1e-3)
    max_iterations: int = Field(default=50, ge=10, le=200)
    acceleration_factor: float = Field(default=1.6, ge=1.0, le=2.0)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/studies/parameters",
    tags=["studies", "parameters"],
    dependencies=[Depends(get_api_key)],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=SolverParametersResponse, include_in_schema=False)
@router.get(
    "/",
    response_model=SolverParametersResponse,
    summary="Get current solver parameters",
    description="Returns the current solver parameters from the database.",
)
async def fetch_global_parameters(
    db: AsyncSession = Depends(get_db),
) -> SolverParametersResponse:
    """Retrieve the current solver parameters."""
    data = await load_solver_params(None, db)
    return SolverParametersResponse(**data)


@router.post("", response_model=SolverParametersResponse, include_in_schema=False)
@router.post(
    "/",
    response_model=SolverParametersResponse,
    status_code=status.HTTP_200_OK,
    summary="Create / overwrite solver parameters",
    description="Creates or completely replaces all solver parameters in the database.",
)
async def create_global_parameters(
    body: SolverParametersCreate,
    db: AsyncSession = Depends(get_db),
) -> SolverParametersResponse:
    """Create or overwrite all solver parameters at once."""
    tol = (
        body.convergence_tolerance
        if body.convergence_tolerance is not None
        else body.solver_convergence_tolerance
    )
    payload = {
        "convergence_tolerance": tol if tol is not None else DEFAULT_CONVERGENCE_TOLERANCE,
        "max_iterations": body.max_iterations,
        "acceleration_factor": body.acceleration_factor,
    }
    data = await save_solver_params(None, payload, db)
    logger.info("Solver parameters overwritten in DB: %s", data)
    return SolverParametersResponse(**data)


@router.put("", response_model=SolverParametersResponse, include_in_schema=False)
@router.put(
    "/",
    response_model=SolverParametersResponse,
    summary="Partially update solver parameters",
    description=(
        "Updates only the solver parameters provided in the request body. "
        "Omitted fields retain their current values."
    ),
)
async def update_global_parameters(
    body: SolverParametersUpdate,
    db: AsyncSession = Depends(get_db),
) -> SolverParametersResponse:
    """Partially update individual solver parameters."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one parameter must be provided for update.",
        )
    current = await load_solver_params(None, db)
    tol = updates.get("convergence_tolerance") or updates.get("solver_convergence_tolerance")
    if tol is not None:
        current["convergence_tolerance"] = tol
        current["solver_convergence_tolerance"] = tol
    if "max_iterations" in updates:
        current["max_iterations"] = updates["max_iterations"]
    if "acceleration_factor" in updates:
        current["acceleration_factor"] = updates["acceleration_factor"]

    data = await save_solver_params(None, current, db)
    logger.info("Solver parameters updated in DB: %s", data)
    return SolverParametersResponse(**data)


@router.get(
    "/{project_id}",
    response_model=SolverParametersResponse,
    summary="Get solver parameters for a specific project",
    description="Returns the solver parameters stored for a specific project ID, falling back to defaults.",
)
async def fetch_project_parameters(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> SolverParametersResponse:
    """Retrieve solver parameters scoped to a specific project."""
    data = await load_solver_params(project_id, db)
    return SolverParametersResponse(**data)


@router.put(
    "/{project_id}",
    response_model=SolverParametersResponse,
    summary="Partially update solver parameters for a specific project",
    description="Updates only the solver parameters provided for a specific project.",
)
async def update_project_parameters(
    project_id: str,
    body: SolverParametersUpdate,
    db: AsyncSession = Depends(get_db),
) -> SolverParametersResponse:
    """Partially update solver parameters for a specific project."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one parameter must be provided for update.",
        )
    current = await load_solver_params(project_id, db)
    tol = updates.get("convergence_tolerance") or updates.get("solver_convergence_tolerance")
    if tol is not None:
        current["convergence_tolerance"] = tol
        current["solver_convergence_tolerance"] = tol
    if "max_iterations" in updates:
        current["max_iterations"] = updates["max_iterations"]
    if "acceleration_factor" in updates:
        current["acceleration_factor"] = updates["acceleration_factor"]

    data = await save_solver_params(project_id, current, db)
    logger.info("Project %s solver parameters updated in DB: %s", project_id, data)
    return SolverParametersResponse(**data)

