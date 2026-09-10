"""GIS Edits API Router — /api/v1/gis/edits/*

Safe real-time transactional write and control operations for ArcGIS Online/Enterprise.
Provides:
- POST /api/v1/gis/edits/propose        — Propose edit batch (Maker / Engineer)
- GET  /api/v1/gis/edits/pending        — List pending approvals for tenant
- POST /api/v1/gis/edits/{id}/resolve   — Approve/Reject & Execute (Checker / Admin)
- GET  /api/v1/gis/edits/{id}/status    — Check status and readback verification

Security & Compliance:
- Dual-control Maker-Checker enforcement (HTTP 403 MAKER_CHECKER_VIOLATION)
- Multi-tenant isolation and per-tenant GIS_SERVICE_ALLOWLIST
- Pre-flight geometry validation (fail-closed before DB record creation)
- Idempotency replay guard and transactional rollback (rollbackOnFailure=true)
- Verify-by-requery confirmation and append-only audit logging
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

UTC = timezone.utc

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.approvals import (
    APPROVAL_TTL_SECONDS,
    PendingAction,
    _norm_tenant,
    _replay_idempotent,
    _store_idempotent,
    compute_args_hash,
    expire_stale_actions,
)
from api.database import get_db
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
)
from api.dual_control import (
    APPROVAL_EVENT_APPROVED,
    APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
    APPROVAL_EVENT_PROPOSED,
    APPROVAL_EVENT_REJECTED,
    record_approval_event,
)
from api.feature_flags import is_feature_enabled
from gis_integration.exceptions import GISCapabilityError, GISWriteError
from gis_integration.providers.arcgis_provider import ArcGISOnlineProvider
from gis_integration.utils import safe_parse_geojson, validate_geometry_dict

logger = logging.getLogger("engineering_service.gis_edits")

# SECURITY: S5145 - strip control characters from user-controlled values
# before they reach the logger. Prevents log injection / CRLF spoofing.
# Mirrors the helper in api/copilot_config.py (SonarCloud S5145 batch 5).
_SAFE_LOG_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled input before writing to logs.

    Strips control characters and truncates to prevent log-flooding / injection.
    """
    if value is None:
        return "None"
    s = _SAFE_LOG_RE.sub("_", str(value))
    if len(s) > max_len:
        s = s[:max_len] + "...[truncated]"
    return s


router = APIRouter(
    prefix="/api/v1/gis/edits",
    tags=["GIS Edits"],
    dependencies=[Depends(get_api_key)],
)


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class GISEditProposeRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    service_url: str = Field(min_length=1, max_length=1024)
    layer_id: str = Field(min_length=1, max_length=128)
    adds: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    updates: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    deletes: Optional[List[Union[int, str]]] = Field(default_factory=list)
    reason: str = Field(min_length=5, max_length=1000)


class GISEditResolveRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    decision: str = Field(pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _check_allowlist(service_url: str, tenant_id: Optional[str]) -> None:
    """Verify that service_url matches the configured GIS_SERVICE_ALLOWLIST."""
    allowlist_env = os.getenv("GIS_SERVICE_ALLOWLIST", "").strip()
    if not allowlist_env:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SERVICE_NOT_ALLOWLISTED",
                "message": "GIS service allowlist is empty or not configured. Write operations are blocked.",
            },
        )

    clean_url = service_url.rstrip("/").lower()
    allowed_urls = [u.strip().rstrip("/").lower() for u in allowlist_env.split(",") if u.strip()]

    if not any(clean_url.startswith(allowed) for allowed in allowed_urls):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SERVICE_NOT_ALLOWLISTED",
                "message": f"Service URL '{service_url}' is not in the allowed GIS service list.",
            },
        )


def _preflight_validate_features(
    adds: Optional[List[Dict[str, Any]]],
    updates: Optional[List[Dict[str, Any]]],
    deletes: Optional[List[Union[int, str]]],
) -> None:
    """Fail-closed pre-flight validation of geometries and delete identifiers."""
    for idx, item in enumerate(adds or []):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PAYLOAD", "message": f"Add feature {idx} must be a dict."},
            )
        raw_geom = item.get("geometry")
        if not raw_geom:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MISSING_GEOMETRY",
                    "message": f"Add feature {idx} missing geometry.",
                },
            )
        try:
            parsed = safe_parse_geojson(raw_geom)
            is_valid, reason = validate_geometry_dict(parsed)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "INVALID_GEOMETRY",
                        "message": f"Add feature {idx} invalid geometry: {reason}",
                    },
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_GEOMETRY",
                    "message": f"Add feature {idx} geometry parse failure: {exc}",
                },
            ) from exc

    for idx, item in enumerate(updates or []):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_PAYLOAD",
                    "message": f"Update feature {idx} must be a dict.",
                },
            )
        attrs = item.get("attributes") or item.get("properties") or {}
        oid = (
            attrs.get("OBJECTID")
            or attrs.get("ObjectId")
            or attrs.get("objectId")
            or item.get("id")
        )
        if oid is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MISSING_OBJECTID",
                    "message": f"Update feature {idx} missing required OBJECTID.",
                },
            )
        raw_geom = item.get("geometry")
        if raw_geom:
            try:
                parsed = safe_parse_geojson(raw_geom)
                is_valid, reason = validate_geometry_dict(parsed)
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "INVALID_GEOMETRY",
                            "message": f"Update feature {idx} invalid geometry: {reason}",
                        },
                    )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "INVALID_GEOMETRY",
                        "message": f"Update feature {idx} geometry parse failure: {exc}",
                    },
                ) from exc

    for idx, d in enumerate(deletes or []):
        s = str(d).strip()
        if not s or s in ("*", "1=1") or "where" in s.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_DELETE",
                    "message": "Mass delete is forbidden; explicit OBJECTIDs are required.",
                },
            )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/propose", status_code=status.HTTP_202_ACCEPTED)
async def propose_gis_edit(
    command: GISEditProposeRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Propose a GIS transactional edit operation (Maker action)."""
    endpoint = "POST /api/v1/gis/edits/propose"
    replay = await _replay_idempotent(db, idempotency_key, endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: Engineer or Admin role required
    if user.role not in ("engineer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": f"User with role '{user.role}' cannot propose GIS edits. Engineer or Admin role required.",
            },
        )

    # 2. Feature Flags Gating
    if not is_feature_enabled("gis_write", default=False) or not is_feature_enabled(
        "arcgis_provider", default=False
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "GIS write capability is disabled by system feature flags ('gis_write', 'arcgis_provider').",
            },
        )

    # 3. Allowlist validation
    _check_allowlist(command.service_url, user.tenant_id)

    # 4. Limits and validation
    max_features = int(os.getenv("GIS_MAX_FEATURES_PER_EDIT", "100"))
    total_count = len(command.adds or []) + len(command.updates or []) + len(command.deletes or [])
    if total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "At least one add, update, or delete feature must be specified.",
            },
        )
    if total_count > max_features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "LIMIT_EXCEEDED",
                "message": f"Total features ({total_count}) exceeds maximum allowed ({max_features}).",
            },
        )

    _preflight_validate_features(command.adds, command.updates, command.deletes)

    # 5. Create PendingAction record
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    cmd_dict = command.model_dump()

    action = PendingAction(
        tenant_id=user.tenant_id,
        session_id=f"gis_{command.layer_id}",
        tool="gis_edit",
        args_hash=compute_args_hash(cmd_dict),
        risk_class="critical",
        status="pending",
        expires_at=expires_at,
        created_at=now,
        requested_by_user_id=user.user_id,
        requested_by_role=user.role,
        args=cmd_dict,
    )
    db.add(action)
    await db.flush()

    record_approval_event(
        APPROVAL_EVENT_PROPOSED,
        action.id,
        user.user_id,
        {
            "service_url": command.service_url,
            "layer_id": command.layer_id,
            "counts": {
                "adds": len(command.adds or []),
                "updates": len(command.updates or []),
                "deletes": len(command.deletes or []),
            },
            "reason": command.reason,
        },
    )

    response_data = {
        "success": True,
        "action_id": action.id,
        "status": "pending_approval",
        "service_url": command.service_url,
        "layer_id": command.layer_id,
        "expires_at": expires_at.isoformat(),
        "message": "GIS edit proposed and held for dual-control approval by an independent admin.",
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id, response_data)
    await db.commit()

    logger.info(
        "GIS edit proposed: action_id=%s layer=%s by user=%s",
        action.id,
        _sanitize_for_log(command.layer_id),
        _sanitize_for_log(user.user_id),
    )
    return response_data


@router.get("/pending")
async def list_pending_gis_edits(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """List pending GIS edits scoped strictly to the current tenant."""
    await expire_stale_actions(db)

    result = await db.execute(
        select(PendingAction).where(
            PendingAction.tool == "gis_edit",
            PendingAction.status == "pending",
            func.coalesce(PendingAction.tenant_id, "") == _norm_tenant(user.tenant_id),
        )
    )
    pending = result.scalars().all()

    items = []
    for a in pending:
        items.append(
            {
                "action_id": a.id,
                "session_id": a.session_id,
                "service_url": (a.args or {}).get("service_url"),
                "layer_id": (a.args or {}).get("layer_id"),
                "reason": (a.args or {}).get("reason"),
                "requested_by_user_id": a.requested_by_user_id,
                "requested_by_role": a.requested_by_role,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
        )

    return {
        "success": True,
        "total": len(items),
        "data": items,
    }


@router.post("/{action_id}/resolve")
async def resolve_gis_edit(
    action_id: str,
    body: GISEditResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Approve or reject a pending GIS edit (Checker action)."""
    resolve_endpoint = f"POST /api/v1/gis/edits/{action_id}/resolve"
    replay = await _replay_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: Admin role required
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ADMIN_ROLE_REQUIRED",
                "message": "Only users with the 'admin' role can approve or reject GIS edit actions.",
            },
        )

    await expire_stale_actions(db)

    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="GIS edit action not found"
        )

    # 2. Multi-tenant isolation
    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_TENANT_FORBIDDEN",
                "message": "This GIS edit action belongs to another tenant.",
            },
        )

    # 3. Status check
    if action.status != "pending":
        return {
            "success": False,
            "error": {
                "code": "ALREADY_RESOLVED",
                "status": action.status,
                "message": f"Action is already '{action.status}'",
            },
        }

    # 4. Maker-Checker enforcement (Anti-Self-Approval)
    if body.decision == "approve" and user.user_id == action.requested_by_user_id:
        record_approval_event(
            APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
            action.id,
            user.user_id,
            {"action_id": action.id, "attempted_decision": body.decision},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MAKER_CHECKER_VIOLATION",
                "message": "Self-approval is forbidden. A different authorized admin must approve this GIS edit.",
            },
        )

    now = datetime.now(UTC)
    action.decided_by_user_id = user.user_id
    action.decided_by_role = user.role
    action.resolved_at = now

    if body.decision == "reject":
        action.status = "rejected"
        record_approval_event(
            APPROVAL_EVENT_REJECTED,
            action.id,
            user.user_id,
            {"reason": body.reason or "Rejected by administrator"},
        )
        await db.commit()
        return {
            "success": True,
            "action_id": action.id,
            "status": "rejected",
            "message": "GIS edit action was rejected.",
        }

    # 5. Approved -> Dispatch execution & verify by readback
    action.status = "executing"
    record_approval_event(
        APPROVAL_EVENT_APPROVED,
        action.id,
        user.user_id,
        {"reason": body.reason or "Approved by administrator"},
    )
    await db.flush()

    args = action.args or {}
    service_url = args.get("service_url", "")
    layer_id = args.get("layer_id", "")
    adds = args.get("adds")
    updates = args.get("updates")
    deletes = args.get("deletes")

    provider = ArcGISOnlineProvider()
    try:
        provider.load_project(service_url)
        exec_res = provider.apply_edits(
            layer_id=layer_id,
            adds=adds,
            updates=updates,
            deletes=deletes,
        )
        action.status = "completed" if exec_res.get("readback_verified") else "failed"
    except (GISCapabilityError, GISWriteError) as exc:
        logger.error("GIS applyEdits failed for action %s: %s", action.id, exc)
        action.status = "failed"
        exec_res = {"success": False, "error": str(exc), "readback_verified": False}
    except Exception as exc:
        logger.exception(
            "Unexpected error executing GIS applyEdits for action %s: %s", action.id, exc
        )
        action.status = "failed"
        exec_res = {"success": False, "error": str(exc), "readback_verified": False}

    response_data = {
        "success": exec_res.get("readback_verified", False),
        "action_id": action.id,
        "status": action.status,
        "result": exec_res,
    }

    await _store_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id, response_data)
    await db.commit()

    return response_data


@router.get("/{action_id}/status")
async def get_gis_edit_status(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """Retrieve detailed status of a proposed/executed GIS edit."""
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="GIS edit action not found"
        )

    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="GIS edit action not found"
        )

    return {
        "success": True,
        "data": {
            "action_id": action.id,
            "status": action.status,
            "service_url": (action.args or {}).get("service_url"),
            "layer_id": (action.args or {}).get("layer_id"),
            "requested_by_user_id": action.requested_by_user_id,
            "decided_by_user_id": action.decided_by_user_id,
            "created_at": action.created_at.isoformat() if action.created_at else None,
            "resolved_at": action.resolved_at.isoformat() if action.resolved_at else None,
        },
    }
