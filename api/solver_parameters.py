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

from api.dependencies import get_api_key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default solver parameters
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, float | int] = {
    "solver_convergence_tolerance": 1e-5,
    "max_iterations": 50,
    "acceleration_factor": 1.6,
}

# In-memory store — persists across requests for the lifetime of the process.
_solver_parameters: dict[str, float | int] = dict(_DEFAULTS)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SolverParametersBase(BaseModel):
    """Base model with shared solver-parameter field definitions.

    Each field declares its default value and validation constraints so
    that both the full-create and partial-update models can reuse them.
    """

    solver_convergence_tolerance: float = Field(
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


class SolverParametersCreate(SolverParametersBase):
    """Request body for creating/overwriting all solver parameters.

    All fields are required when performing a full replacement (POST).
    """

    solver_convergence_tolerance: float = SolverParametersBase.model_fields[
        "solver_convergence_tolerance"
    ].default  # type: ignore[assignment]
    max_iterations: int = SolverParametersBase.model_fields[
        "max_iterations"
    ].default  # type: ignore[assignment]
    acceleration_factor: float = SolverParametersBase.model_fields[
        "acceleration_factor"
    ].default  # type: ignore[assignment]


class SolverParametersUpdate(BaseModel):
    """Request body for partially updating solver parameters.

    Only fields that are explicitly provided will be updated; omitted
    fields retain their current values.
    """

    model_config = ConfigDict(extra="forbid")

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


class SolverParametersResponse(SolverParametersBase):
    """Response model returned by all solver-parameter endpoints."""

    model_config = ConfigDict(from_attributes=True)


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


@router.get(
    "/",
    response_model=SolverParametersResponse,
    summary="Get current solver parameters",
    description="Returns the current solver parameters stored in memory.",
)
async def get_solver_parameters() -> SolverParametersResponse:
    """Retrieve the current solver parameters.

    Returns:
        SolverParametersResponse: The active solver parameter values.
    """
    return SolverParametersResponse(**_solver_parameters)


@router.post(
    "/",
    response_model=SolverParametersResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create / overwrite solver parameters",
    description=(
        "Creates or completely replaces all solver parameters. "
        "Every field must be provided."
    ),
)
async def create_solver_parameters(
    body: SolverParametersCreate,
) -> SolverParametersResponse:
    """Create or overwrite all solver parameters at once.

    Args:
        body: Full set of solver parameters to store.

    Returns:
        SolverParametersResponse: The newly stored parameter values.
    """
    _solver_parameters.update(body.model_dump())
    logger.info(
        "Solver parameters overwritten: convergence_tolerance=%s, "
        "max_iterations=%s, acceleration_factor=%s",
        _solver_parameters["solver_convergence_tolerance"],
        _solver_parameters["max_iterations"],
        _solver_parameters["acceleration_factor"],
    )
    return SolverParametersResponse(**_solver_parameters)


@router.put(
    "/",
    response_model=SolverParametersResponse,
    summary="Partially update solver parameters",
    description=(
        "Updates only the solver parameters provided in the request body. "
        "Omitted fields retain their current values."
    ),
)
async def update_solver_parameters(
    body: SolverParametersUpdate,
) -> SolverParametersResponse:
    """Partially update individual solver parameters.

    Only fields that are explicitly set (non-None) in the request body
    will be applied; all other fields remain unchanged.

    Args:
        body: Partial set of solver parameters to update.

    Returns:
        SolverParametersResponse: The updated parameter values.

    Raises:
        HTTPException 422: If no fields are provided for update.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one parameter must be provided for update.",
        )
    _solver_parameters.update(updates)
    logger.info("Solver parameters updated: %s", updates)
    return SolverParametersResponse(**_solver_parameters)
