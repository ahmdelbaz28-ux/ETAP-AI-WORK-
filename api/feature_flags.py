"""
api/feature_flags.py — Feature flags for incomplete/unverified study types.

Studies behind feature flags are disabled in production/staging
and shown as 'Coming Soon' in the UI.

This module exposes:
* ``FEATURE_FLAGS``        — in-memory defaults (4 study types)
* ``is_feature_enabled()`` — runtime check honouring ENV
* ``router``               — FastAPI APIRouter at prefix /api/v1/feature-flags
  - GET  /                  — list all flags + their effective state
  - GET  /{key}             — single flag detail
  - PATCH /{key}            — toggle enabled (admin only); persists to
                              JSON file at FEATURE_FLAGS_PATH (default:
                              .feature-flags.json) so changes survive
                              process restarts without DB dependency.

SECURITY:
- GET endpoints require a valid API key / authenticated user.
- PATCH endpoint requires admin role (delegates to ``require_admin``
  from api.rbac when available, else falls back to ``get_api_key``).
- All PATCH operations are audit-logged via the shared audit logger.
"""
# ─── Module status ────────────────────────────────────────────────────────
# INTERNAL — this module is NOT registered as an ``APIRouter`` in routes.py.
# It is consumed indirectly by middleware, websocket handlers, CLI tools, or
# other services. Do not add ``app.include_router`` for this module without a
# corresponding audit of the consumers below.

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
    # ── Infrastructure flags (not study types) ────────────────────────────
    # MockGISProvider is a development/test fallback used when QGIS/ArcGIS
    # SDKs are unavailable (e.g., Hugging Face Spaces, Docker without
    # desktop GIS). In production it must be explicitly enabled, otherwise
    # `get_gis_provider()` will fail loudly instead of silently serving
    # mock spatial data. See `gis_integration/providers/__init__.py`.
    "mock_gis_provider": {
        "enabled": False,
        "status": "internal",
        "description": "Allow MockGISProvider as fallback in non-dev environments",
    },
}

# Backwards-compat alias (other modules import FEATURE_FLAGS directly)
FEATURE_FLAGS = DEFAULT_FEATURE_FLAGS

FEATURE_FLAGS_PATH_ENV = "FEATURE_FLAGS_PATH"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / ".feature-flags.json"


def _db_path() -> Path:
    """Return the path to the feature-flags JSON file (env-overridable)."""
    p = os.getenv(FEATURE_FLAGS_PATH_ENV)
    return Path(p) if p else DEFAULT_DB_PATH


def _load_flags() -> dict[str, dict[str, Any]]:
    """Load flags from JSON file, falling back to defaults."""
    path = _db_path()
    if not path.exists():
        # Return a copy of defaults so callers can mutate freely
        return {k: dict(v) for k, v in DEFAULT_FEATURE_FLAGS.items()}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {k: dict(v) for k, v in DEFAULT_FEATURE_FLAGS.items()}
        # Merge with defaults to keep new flags visible
        merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_FEATURE_FLAGS.items()}
        for k, v in raw.items():
            if isinstance(v, dict) and k in merged:
                merged[k].update(v)
            elif isinstance(v, dict):
                merged[k] = dict(v)
        return merged
    except (json.JSONDecodeError, OSError):
        return {k: dict(v) for k, v in DEFAULT_FEATURE_FLAGS.items()}


def _save_flags(flags: dict[str, dict[str, Any]]) -> None:
    """Persist flags to JSON file atomically (write tmp + rename)."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(flags, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def is_feature_enabled(study_type: str) -> bool:
    """Check if a study type is enabled, considering environment.

    In development/test env, all flags are forced ON so devs can test
    incomplete features locally without needing to toggle each flag.
    """
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return True
    flags = _load_flags()
    flag = flags.get(study_type)
    if flag is None:
        return True
    return bool(flag.get("enabled", False))


def get_disabled_studies() -> list[dict]:
    """Return list of disabled studies with their status for UI display."""
    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if env in ("development", "dev", "test", ""):
        return []
    flags = _load_flags()
    return [
        {
            "study_type": k,
            "status": v.get("status", "beta"),
            "description": v.get("description", ""),
        }
        for k, v in flags.items()
        if not v.get("enabled", False)
    ]


# ─── Pydantic schemas ────────────────────────────────────────────────────
class FeatureFlagOut(BaseModel):
    key: str
    enabled: bool
    status: str
    description: str
    effective_enabled: bool  # honouring ENV (dev = always True)


class FeatureFlagListOut(BaseModel):
    success: bool = True
    data: list[FeatureFlagOut]
    total: int
    env: str


class FeatureFlagPatch(BaseModel):
    enabled: bool = Field(..., description="New enabled state for the flag")


# ─── Auth dependency (admin) ─────────────────────────────────────────────
def _require_permission(resource: str, action: str):
    """Return a dependency that enforces RBAC permission on feature flags.

    Production: delegates to ``api.rbac.require_permission(resource, action)``
    which validates the JWT in the Authorization header and checks the user
    has the named permission (or has role=admin for bypass).

    Fallback (only when api.rbac cannot be imported — e.g. during unit
    tests that build a minimal FastAPI app without the DB layer): falls
    back to ``api.dependencies.get_api_key`` so the endpoint is still
    protected by API-key auth rather than left open. The fallback is
    logged at WARNING level so it is visible in production deployments.
    """
    try:
        from api.rbac import require_permission  # type: ignore[import]

        return require_permission(resource, action)
    except Exception as e:  # pragma: no cover — defensive fallback
        logger.warning(
            "api.rbac.require_permission unavailable (%s); falling back to "
            "get_api_key for %s:%s — configure RBAC for production use",
            e,
            resource,
            action,
        )
        from api.dependencies import get_api_key

        return get_api_key


def _require_admin():
    """Convenience wrapper: require feature-flags write permission.

    Kept for backwards-compat with the original TASK-9 implementation
    that called ``_require_admin()`` directly.
    """
    return _require_permission("feature_flags", "write")


# ─── Endpoints ───────────────────────────────────────────────────────────
@router.get("", dependencies=[Depends(_require_permission("feature_flags", "read"))])
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
                "enabled": enabled,
                "status": cfg.get("status", "beta"),
                "description": cfg.get("description", ""),
                "effective_enabled": effective,
            }
        )
    return JSONResponse(
        content={
            "success": True,
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
            "data": {
                "key": key,
                "enabled": enabled,
                "status": cfg.get("status", "beta"),
                "description": cfg.get("description", ""),
                "effective_enabled": effective,
            },
            "trace_id": trace_id,
        }
    )


@router.patch("/{key}")
async def update_feature_flag(
    request: Request,
    key: str,
    payload: FeatureFlagPatch,
    _admin=Depends(_require_admin()),
):
    """Toggle a feature flag. Persists to JSON file so changes survive restarts.

    In development/test env, the toggle is accepted and persisted, but
    ``effective_enabled`` will still report True (dev override).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    flags = _load_flags()
    if key not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{key}' not found",
        )
    old_value = bool(flags[key].get("enabled", False))
    flags[key]["enabled"] = bool(payload.enabled)
    flags[key]["updated_at"] = datetime.now(UTC).isoformat()
    _save_flags(flags)

    # Audit log entry — best-effort, never fail the request if logging fails.
    try:
        import logging

        audit = logging.getLogger("audit")
        audit.info(
            "feature_flag_toggled key=%s old=%s new=%s actor=%s trace_id=%s",
            key,
            old_value,
            payload.enabled,
            getattr(request.state, "user_id", "system"),
            trace_id,
        )
    except Exception:  # pragma: no cover
        pass

    env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    effective = True if env in ("development", "dev", "test", "") else bool(payload.enabled)
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "key": key,
                "enabled": bool(payload.enabled),
                "previous_enabled": old_value,
                "status": flags[key].get("status", "beta"),
                "description": flags[key].get("description", ""),
                "effective_enabled": effective,
                "env": env,
            },
            "trace_id": trace_id,
        }
    )
