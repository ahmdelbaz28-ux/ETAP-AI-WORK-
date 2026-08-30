"""
api/feature_flags.py — Feature Flags Management API.

Exposes endpoints for listing, viewing, and toggling runtime feature flags
for AhmedETAP modules (e.g. harmonic analysis, motor starting, stability).

Endpoints:
* ``GET   /api/v1/feature-flags``         — List all feature flags
* ``GET   /api/v1/feature-flags/{key}``    — Get a single feature flag
* ``PUT   /api/v1/feature-flags/{key}``    — Update / toggle a feature flag
* ``PATCH /api/v1/feature-flags/{key}``    — Toggle a feature flag
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

UTC = timezone.utc  # noqa: UP017

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies import get_api_key

router = APIRouter(prefix="/api/v1/feature-flags", tags=["feature-flags"])

logger = logging.getLogger(__name__)


# ─── Defaults (loaded on first import or when DB file is missing) ────────
DEFAULT_FEATURE_FLAGS: dict[str, dict[str, Any]] = {
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

FEATURE_FLAGS = DEFAULT_FEATURE_FLAGS
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / ".feature-flags.json"


def _db_path() -> Path:
    """Return the path to the feature-flags JSON file (env-overridable)."""
    p = os.getenv("FEATURE_FLAGS_PATH") or os.getenv("FEATURE_FLAGS_DB_PATH")
    if p:
        return Path(p)
    return DEFAULT_DB_PATH


def _load_flags() -> dict[str, dict[str, Any]]:
    """Load flags from disk, falling back to defaults if the file is missing/corrupt."""
    path = _db_path()
    if not path.exists():
        return dict(DEFAULT_FEATURE_FLAGS)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                merged = dict(DEFAULT_FEATURE_FLAGS)
                for k, v in data.items():
                    if isinstance(v, dict):
                        merged[k] = v
                return merged
    except Exception as e:
        logger.warning("Failed to read feature flags from %s: %s; using defaults", path, e)
    return dict(DEFAULT_FEATURE_FLAGS)


def _save_flags(flags: dict[str, dict[str, Any]]) -> None:
    """Persist flags to disk."""
    path = _db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(flags, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except Exception as e:
        logger.error("Failed to persist feature flags to %s: %s", path, e)


def is_enabled(key: str, default: bool = True) -> bool:
    """Check if a feature flag is enabled."""
    return is_feature_enabled(key, default)


def is_feature_enabled(key: str, default: bool = True) -> bool:
    """Check if a feature flag is enabled.

    In development/testing environments (ENV=development/test or APP_ENV=dev),
    all flags return True unless explicitly disabled via the ENV override:
      FEATURE_FLAG_<KEY_UPPERCASE>=false
    """
    env_override = os.getenv(f"FEATURE_FLAG_{key.upper()}")
    if env_override is not None:
        return env_override.strip().lower() in ("1", "true", "yes", "on")

    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return True

    flags = _load_flags()
    if key in flags:
        return bool(flags[key].get("enabled", default))
    return default


def get_disabled_studies() -> list[str]:
    """Return a list of study types that are currently disabled by feature flags.

    In dev/test environments, returns an empty list (all studies enabled).
    """
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return []

    flags = _load_flags()
    disabled = []
    for key, cfg in flags.items():
        if not cfg.get("enabled", False):
            disabled.append(key)
    return disabled


def get_flag_metadata(key: str) -> dict[str, Any] | None:
    """Return flag metadata dictionary or None if not found."""
    flags = _load_flags()
    return flags.get(key)


# ─── Pydantic schemas ────────────────────────────────────────────────────
class FeatureFlagOut(BaseModel):
    key: str
    flag_id: str
    enabled: bool
    status: str
    description: str
    effective_enabled: bool


class FeatureFlagListOut(BaseModel):
    success: bool = True
    flags: list[dict[str, Any]]
    data: list[dict[str, Any]]
    total: int
    env: str


class FeatureFlagPatch(BaseModel):
    enabled: Optional[bool] = Field(default=None, description="New enabled state for the flag")
    status: Optional[str] = Field(
        default=None,
        pattern=r"^(alpha|beta|stable|deprecated|experimental)$",
        description="New status for the flag",
    )


# ─── Auth dependency ─────────────────────────────────────────────────────
def _require_permission(resource: str, action: str):
    return get_api_key


def _require_admin():
    return get_api_key


# ─── Endpoints ───────────────────────────────────────────────────────────
@router.get("", dependencies=[Depends(_require_permission("feature_flags", "read"))])
@router.get("/", dependencies=[Depends(_require_permission("feature_flags", "read"))], include_in_schema=False)
async def list_feature_flags(request: Request):
    """List all feature flags with their effective state for the current ENV."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    flags = _load_flags()
    items: list[dict[str, Any]] = []
    for key, cfg in flags.items():
        enabled = bool(cfg.get("enabled", False))
        effective = True if env in ("development", "dev", "test", "") else enabled
        items.append(
            {
                "key": key,
                "flag_id": key,
                "enabled": enabled,
                "status": cfg.get("status", "beta"),
                "description": cfg.get("description", ""),
                "effective_enabled": effective,
            }
        )
    return JSONResponse(
        content={
            "success": True,
            "flags": items,
            "data": items,
            "total": len(items),
            "env": env,
            "trace_id": trace_id,
        }
    )


@router.get("/{key}", dependencies=[Depends(_require_permission("feature_flags", "read"))])
async def get_feature_flag(request: Request, key: str):
    """Return a single feature flag by key."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    flags = _load_flags()
    if key not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{key}' not found",
        )
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    cfg = flags[key]
    enabled = bool(cfg.get("enabled", False))
    effective = True if env in ("development", "dev", "test", "") else enabled
    return JSONResponse(
        content={
            "success": True,
            "flag_id": key,
            "key": key,
            "enabled": enabled,
            "status": cfg.get("status", "beta"),
            "description": cfg.get("description", ""),
            "effective_enabled": effective,
            "data": {
                "key": key,
                "flag_id": key,
                "enabled": enabled,
                "status": cfg.get("status", "beta"),
                "description": cfg.get("description", ""),
                "effective_enabled": effective,
            },
            "trace_id": trace_id,
        }
    )


@router.put("/{key}")
@router.patch("/{key}")
async def update_feature_flag(
    request: Request,
    key: str,
    payload: FeatureFlagPatch,
    _admin=Depends(_require_admin()),
):
    """Toggle or update a feature flag."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    flags = _load_flags()
    if key not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{key}' not found",
        )
    old_value = bool(flags[key].get("enabled", False))
    if payload.enabled is not None:
        flags[key]["enabled"] = bool(payload.enabled)
    if payload.status is not None:
        flags[key]["status"] = payload.status
    flags[key]["updated_at"] = datetime.now(UTC).isoformat()
    _save_flags(flags)

    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    effective = True if env in ("development", "dev", "test", "") else bool(flags[key]["enabled"])
    return JSONResponse(
        content={
            "success": True,
            "flag_id": key,
            "key": key,
            "enabled": bool(flags[key]["enabled"]),
            "status": flags[key].get("status", "beta"),
            "data": {
                "key": key,
                "flag_id": key,
                "enabled": bool(flags[key]["enabled"]),
                "previous_enabled": old_value,
                "status": flags[key].get("status", "beta"),
                "description": flags[key].get("description", ""),
                "effective_enabled": effective,
                "env": env,
            },
            "trace_id": trace_id,
        }
    )
