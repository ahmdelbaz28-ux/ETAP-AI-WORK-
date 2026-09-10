"""ETAP Draw Endpoints API Router — /api/v1/etap/draw/*

Safe automatic ETAP drawing via DataHub etapAPI REST (server-side Auto-Build).
Mirrors the SCADA dual-control gateway pattern (api/scada.py @ HEAD):

- POST /api/v1/etap/draw/propose        — Propose draw (Maker / Engineer)
- GET  /api/v1/etap/draw/pending        — List pending approvals for tenant
- POST /api/v1/etap/draw/{id}/resolve   — Approve/Reject & Execute (Checker / Admin)
- GET  /api/v1/etap/draw/{id}/status    — Check status and readback verification

Security & Compliance:
- Feature-flag gate OFF by default (stored flag, NOT the dev-bypass helper)
- Dual-control Maker-Checker enforcement (HTTP 403 MAKER_CHECKER_VIOLATION)
- Multi-tenant isolation (404 unknown / 403 CROSS_TENANT_FORBIDDEN)
- Idempotency & Verify-by-Readback (delegated to etap_integration.etap_rest)
- Append-only audit logging
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

UTC = timezone.utc

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.approvals import (
    APPROVAL_TTL_SECONDS,
    CROSS_TENANT_FORBIDDEN,
    PendingAction,
    _norm_tenant,
    _replay_idempotent,
    _store_idempotent,
    compute_args_hash,
    expire_stale_actions,
)
from api.database import get_db
from api.dependencies import get_api_key

# isort: split
from api.dependencies import (
    CurrentUser,
    get_current_user_from_header,
)
from api.dual_control import (
    APPROVAL_EVENT_APPROVED,
    APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
    APPROVAL_EVENT_PROPOSED,
    APPROVAL_EVENT_REJECTED,
    record_approval_event,
)
from etap_integration.etap_rest import (
    EtapDrawPlan,
    ETAPRestError,
    _tenant_allowed,
    get_rest_client_from_env,
)

logger = logging.getLogger("engineering_service.etap_draw")

router = APIRouter(
    prefix="/api/v1/etap/draw",
    tags=["etap-draw"],
    dependencies=[Depends(get_api_key)],
)

TOOL_NAME = "etap_draw"
RISK_CLASS = "high"
FLAG_KEY = "etap_rest_draw"
ENV_FLAG_OVERRIDE = "FEATURE_FLAG_ETAP_REST_DRAW"


def is_draw_enabled() -> bool:
    """Stored-flag gate with env override. Default deny in EVERY environment.

    NOTE: deliberately NOT using ``is_feature_enabled`` — that helper returns
    True in dev/test regardless of the stored value, which would leave this
    high-risk draw path open wherever tests run.
    """
    override = os.getenv(ENV_FLAG_OVERRIDE)
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on")
    try:
        from api.feature_flags import _load_flags

        stored = _load_flags().get(FLAG_KEY, {})
        return bool(stored.get("enabled", False))
    except Exception:
        return False


def _require_draw_enabled() -> None:
    if not is_draw_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "Automatic ETAP drawing is disabled (flag etap_rest_draw OFF).",
            },
        )


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------


class EtapDrawProposeRequest(EtapDrawPlan):
    """Propose body: full draw plan (validated locally, no HTTP yet)."""


class EtapDrawResolveRequest(BaseModel):
    """Payload for admin decision on a pending draw."""

    model_config = ConfigDict(strict=False)

    decision: str = Field(..., pattern="^(approve|reject)$", description="'approve' or 'reject'")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Reason for decision")


# ---------------------------------------------------------------------------
# Maker endpoint
# ---------------------------------------------------------------------------


@router.post("/propose", status_code=status.HTTP_202_ACCEPTED)
async def propose_draw(
    plan: EtapDrawProposeRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Propose an automatic ETAP drawing (Maker action)."""
    _require_draw_enabled()
    endpoint = "POST /api/v1/etap/draw/propose"
    replay = await _replay_idempotent(db, idempotency_key, endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: engineer or admin only
    if user.role not in ("engineer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": f"User with role '{user.role}' cannot propose ETAP drawings. Engineer or Admin role required.",
            },
        )

    # 2. Tenant allowlist (fail-closed)
    if not _tenant_allowed(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_NOT_ALLOWLISTED",
                "message": "This tenant is not allowlisted for automatic ETAP drawing.",
            },
        )

    # 3. Create PendingAction record (plan already validated by pydantic)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    plan_dict = plan.model_dump()

    action = PendingAction(
        tenant_id=user.tenant_id,
        session_id=f"etap_draw_{plan.project_id}",
        tool=TOOL_NAME,
        args_hash=compute_args_hash(plan_dict),
        risk_class=RISK_CLASS,
        status="pending",
        expires_at=expires_at,
        created_at=now,
        requested_by_user_id=user.user_id,
        requested_by_role=user.role,
        args=plan_dict,
    )
    db.add(action)
    await db.flush()

    record_approval_event(
        APPROVAL_EVENT_PROPOSED,
        action.id,
        user.user_id,
        {
            "project_id": plan.project_id,
            "elements": len(plan.items),
            "reason": plan.reason,
        },
    )

    response_data = {
        "success": True,
        "action_id": action.id,
        "status": "pending_approval",
        "project_id": plan.project_id,
        "elements": len(plan.items),
        "expires_at": expires_at.isoformat(),
        "message": "ETAP drawing proposed and held for dual-control approval by an independent admin.",
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id, response_data)
    await db.commit()

    logger.info(
        "ETAP draw proposed: action_id=%s project=%s by user=%s",
        action.id,
        plan.project_id,
        user.user_id,
    )
    return response_data


@router.get("/pending")
async def list_pending_draws(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """List pending ETAP draw actions scoped strictly to current tenant."""
    _require_draw_enabled()
    await expire_stale_actions(db)

    result = await db.execute(
        select(PendingAction).where(
            PendingAction.tool == TOOL_NAME,
            PendingAction.status == "pending",
            func.coalesce(PendingAction.tenant_id, "") == _norm_tenant(user.tenant_id),
        )
    )
    pending = result.scalars().all()

    items = []
    for a in pending:
        args = a.args or {}
        items.append(
            {
                "action_id": a.id,
                "session_id": a.session_id,
                "project_id": args.get("project_id"),
                "elements": len(args.get("items") or []),
                "reason": args.get("reason"),
                "requested_by_user_id": a.requested_by_user_id,
                "requested_by_role": a.requested_by_role,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
        )

    return {"success": True, "total": len(items), "data": items}


@router.post("/{action_id}/resolve")
async def resolve_draw(
    action_id: str,
    body: EtapDrawResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Approve or reject a pending ETAP drawing (Checker action)."""
    _require_draw_enabled()
    resolve_endpoint = f"POST /api/v1/etap/draw/{action_id}/resolve"
    replay = await _replay_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: admin only
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ADMIN_ROLE_REQUIRED",
                "message": "Only users with the 'admin' role can approve or reject ETAP drawings.",
            },
        )

    await expire_stale_actions(db)

    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None or action.tool != TOOL_NAME:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draw action not found")

    # 2. Tenant isolation (repo convention: 403 on mismatch, mirroring scada)
    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CROSS_TENANT_FORBIDDEN,
                "message": "This draw action belongs to another tenant.",
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

    # 4. Anti-self-approval
    if body.decision == "approve" and user.user_id == action.requested_by_user_id:
        record_approval_event(
            APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
            action.id,
            user.user_id,
            {
                "project_id": (action.args or {}).get("project_id"),
                "attempted_decision": body.decision,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MAKER_CHECKER_VIOLATION",
                "message": "Self-approval is forbidden. A different authorized admin must approve this draw.",
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
            "message": "Draw was rejected.",
        }

    # 5. Approved -> allowlist re-check, then execute with verify-by-readback
    if not _tenant_allowed(user.tenant_id):
        action.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_NOT_ALLOWLISTED",
                "message": "Tenant allowlist revoked before execution.",
            },
        )

    action.status = "executing"
    record_approval_event(
        APPROVAL_EVENT_APPROVED,
        action.id,
        user.user_id,
        {"reason": body.reason or "Approved by administrator"},
    )
    await db.flush()

    try:
        plan = EtapDrawPlan(**(action.args or {}))
    except Exception as exc:
        action.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_PLAN", "message": f"Stored draw plan is invalid: {exc}"},
        )

    try:
        client = get_rest_client_from_env()
        draw_res = await client.apply_draw(plan)
    except ETAPRestError as exc:
        action.status = "failed"
        await db.commit()
        code = 503 if exc.code in ("MISSING_CONFIG", "UNAVAILABLE", "AUTH_FAILED") else 502
        raise HTTPException(
            status_code=code,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    action.status = "completed"
    response_data = {
        "success": draw_res.readback_verified,
        "action_id": action.id,
        "status": action.status,
        "result": draw_res.model_dump(),
    }

    await _store_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id, response_data)
    await db.commit()

    logger.info("ETAP draw completed: action_id=%s drawing=%s", action.id, draw_res.drawing_id)
    return response_data


@router.get("/{action_id}/status")
async def get_draw_status(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """Check status and readback verification of a draw action."""
    _require_draw_enabled()
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None or action.tool != TOOL_NAME:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draw action not found")
    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CROSS_TENANT_FORBIDDEN,
                "message": "This draw action belongs to another tenant.",
            },
        )
    return {
        "success": True,
        "action_id": action.id,
        "status": action.status,
        "project_id": (action.args or {}).get("project_id"),
        "requested_by_user_id": action.requested_by_user_id,
        "decided_by_user_id": action.decided_by_user_id,
        "resolved_at": action.resolved_at.isoformat() if action.resolved_at else None,
    }
