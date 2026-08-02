"""
Feature flags for incomplete/unverified study types.
Studies behind feature flags are disabled in production/staging
and shown as 'Coming Soon' in the UI.

Also provides a REST API for runtime toggling of feature flags
without requiring server restarts.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_api_key

logger = logging.getLogger(__name__)

FEATURE_FLAGS = {
    "harmonic_analysis": {
        "enabled": False,
        "status": "beta",
        "description": "Harmonic analysis (IEEE 519) - in development",
    },
    "motor_starting": {
        "enabled": False,
        "status": "beta",
        "description": "Motor starting analysis (IEEE 399) - in development",
    },
    "transient_stability": {
        "enabled": False,
        "status": "alpha",
        "description": "Transient stability (swing equation) - experimental",
    },
    "optimal_power_flow": {
        "enabled": False,
        "status": "alpha",
        "description": "OPF (economic dispatch) - experimental",
    },
}


def is_feature_enabled(study_type: str) -> bool:
    """Check if a study type is enabled, considering environment."""
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return True
    flag = FEATURE_FLAGS.get(study_type)
    if flag is None:
        return True
    return flag["enabled"]


def get_disabled_studies() -> list[dict]:
    """Return list of disabled studies with their status for UI display."""
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return []
    return [
        {"study_type": k, "status": v["status"], "description": v["description"]}
        for k, v in FEATURE_FLAGS.items()
        if not v["enabled"]
    ]


# ---------------------------------------------------------------------------
# Feature Flags REST API
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/feature-flags",
    tags=["feature-flags"],
    dependencies=[Depends(get_api_key)],
)


class FeatureFlagResponse(BaseModel):
    """Single feature flag with its current state."""

    flag_id: str = Field(..., description="Unique identifier for the feature flag")
    enabled: bool = Field(..., description="Whether the feature is currently enabled")
    status: str = Field(..., description="Release status: alpha, beta, stable")
    description: str = Field(..., description="Human-readable description of the feature")


class FeatureFlagUpdateRequest(BaseModel):
    """Request body for updating a feature flag."""

    enabled: Optional[bool] = Field(None, description="Enable or disable the feature")
    status: Optional[str] = Field(None, description="Update release status")
    description: Optional[str] = Field(None, description="Update description")


class FeatureFlagListResponse(BaseModel):
    """List of all feature flags."""

    flags: list[FeatureFlagResponse] = Field(..., description="All feature flags")
    total: int = Field(..., description="Total number of flags")
    enabled_count: int = Field(..., description="Number of enabled flags")


@router.get("", summary="List all feature flags")
async def list_feature_flags() -> FeatureFlagListResponse:
    """List all feature flags with their current state.

    Returns all feature flags including their enabled status, release
    stage, and description. This allows administrators to review which
    beta and experimental features are currently active.
    """
    flags = [
        FeatureFlagResponse(
            flag_id=k,
            enabled=v["enabled"],
            status=v["status"],
            description=v["description"],
        )
        for k, v in FEATURE_FLAGS.items()
    ]
    return FeatureFlagListResponse(
        flags=flags,
        total=len(flags),
        enabled_count=sum(1 for f in flags if f.enabled),
    )


@router.get("/{flag_id}", summary="Get a specific feature flag")
async def get_feature_flag(flag_id: str) -> FeatureFlagResponse:
    """Get the current state of a specific feature flag.

    Args:
        flag_id: The unique identifier of the feature flag.

    Returns:
        The feature flag details including enabled status and description.
    """
    if flag_id not in FEATURE_FLAGS:
        raise HTTPException(status_code=404, detail=f"Feature flag '{flag_id}' not found")
    v = FEATURE_FLAGS[flag_id]
    return FeatureFlagResponse(
        flag_id=flag_id,
        enabled=v["enabled"],
        status=v["status"],
        description=v["description"],
    )


@router.put("/{flag_id}", summary="Update a feature flag")
async def update_feature_flag(
    flag_id: str,
    body: FeatureFlagUpdateRequest,
) -> FeatureFlagResponse:
    """Update a feature flag's enabled status, release stage, or description.

    This allows runtime toggling of beta features and experimental
    modules without requiring a server restart. Changes take effect
    immediately for subsequent API calls.

    Args:
        flag_id: The unique identifier of the feature flag to update.
        body: The fields to update (partial update supported).

    Returns:
        The updated feature flag details.
    """
    if flag_id not in FEATURE_FLAGS:
        raise HTTPException(status_code=404, detail=f"Feature flag '{flag_id}' not found")

    flag = FEATURE_FLAGS[flag_id]
    if body.enabled is not None:
        flag["enabled"] = body.enabled
    if body.status is not None:
        valid_statuses = {"alpha", "beta", "stable", "deprecated"}
        if body.status not in valid_statuses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{body.status}'. Must be one of: {valid_statuses}",
            )
        flag["status"] = body.status
    if body.description is not None:
        flag["description"] = body.description

    logger.info(
        "feature_flag_updated flag_id=%s enabled=%s status=%s",
        flag_id,
        flag["enabled"],
        flag["status"],
    )

    return FeatureFlagResponse(
        flag_id=flag_id,
        enabled=flag["enabled"],
        status=flag["status"],
        description=flag["description"],
    )
