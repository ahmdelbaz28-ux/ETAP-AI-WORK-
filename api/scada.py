"""SCADA Endpoints API Router — /api/v1/scada/*

Modular home for SCADA data and safe real-time control operations.
Provides:
- GET  /api/v1/scada/live                   — Real-time telemetry snapshot
- GET  /api/v1/scada/devices                — Substation bays and device states
- POST /api/v1/scada/control/propose        — Propose control action (Maker / Engineer)
- GET  /api/v1/scada/control/pending        — List pending approvals for tenant
- POST /api/v1/scada/control/{id}/resolve   — Approve/Reject & Execute (Checker / Admin)
- GET  /api/v1/scada/control/{id}/status    — Check status and readback verification

Security & Compliance:
- Dual-control Maker-Checker enforcement (HTTP 403 MAKER_CHECKER_VIOLATION)
- Engineering Interlock validation (HTTP 422 InterlockViolation)
- Multi-tenant isolation (HTTP 403/404 CROSS_TENANT_FORBIDDEN)
- Idempotency & Verify-by-Readback
- Append-only audit logging
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

UTC = timezone.utc

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api._messages import ISO_8601_UTC_FMT, MSG_INTERNAL_ERROR
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
from api.projects import Project
from scada.control_executor import _SIMULATED_DEVICES, scada_executor
from scada.interlock_engine import InterlockViolation, SCADAInterlockEngine
from scada.models import (
    CommandStatus,
    ControlActionType,
    ControlCommandRequest,
)

logger = logging.getLogger("engineering_service.scada")

MSG_CONTROL_ACTION_NOT_FOUND = "Control action not found"

router = APIRouter(
    prefix="/api/v1/scada",
    tags=["SCADA"],
    dependencies=[Depends(get_api_key)],
)

_interlock_engine = SCADAInterlockEngine()


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 'Z' timestamp."""
    return time.strftime(ISO_8601_UTC_FMT, time.gmtime())


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------


class SCADAResolveRequest(BaseModel):
    """Payload for admin decision on pending SCADA control action."""

    model_config = ConfigDict(strict=False)

    decision: str = Field(..., pattern="^(approve|reject)$", description="'approve' or 'reject'")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Reason for decision")


# ---------------------------------------------------------------------------
# Telemetry Endpoints
# ---------------------------------------------------------------------------


def _get_wired_scada_db():
    try:
        from scada_protocols.wiring import get_wired_manager
        mgr = get_wired_manager()
        if mgr is not None and mgr.is_started():
            return mgr.bridge.has_scada_db() and mgr.bridge._resolve_scada_db()
    except Exception:
        pass
    return None


@router.get("/live")
async def scada_live(request: Request):
    """Return a snapshot of the latest SCADA telemetry.

    Preserves 100% backward compatibility with existing consumers.
    Reports ``is_simulated=false`` only when running in production mode.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        is_prod = os.getenv("SCADA_MODE", "simulation").lower() == "production"
        points = []

        if is_prod:
            db = _get_wired_scada_db()
            if db is not None and db.measurements:
                unit_map = {
                    "VOLTAGE_MAGNITUDE": "kV",
                    "CURRENT_MAGNITUDE": "A",
                    "ACTIVE_POWER": "MW",
                    "REACTIVE_POWER": "MVar",
                    "FREQUENCY": "Hz",
                    "BREAKER_STATUS": "state",
                    "TAP_POSITION": "step",
                }
                for m in db.measurements.values():
                    mtype_name = m.measurement_type.name if hasattr(m.measurement_type, "name") else str(m.measurement_type)
                    q_name = m.quality.name if hasattr(m.quality, "name") else str(m.quality)
                    points.append({
                        "tag": f"{m.element_id}.{mtype_name}",
                        "value": float(m.value),
                        "unit": unit_map.get(mtype_name, "unit"),
                        "quality": q_name,
                        "source_timestamp": getattr(m, "source_timestamp", m.timestamp),
                    })
        else:
            # Build live points from executor's device telemetry
            for dev_id, dev in _SIMULATED_DEVICES.items():
                if "status" in dev:
                    points.append({
                        "tag": f"{dev_id}.STATUS",
                        "value": 1.0 if dev["status"] == "CLOSED" else 0.0,
                        "unit": "state",
                        "quality": dev.get("quality", "GOOD"),
                    })
                if "current_A" in dev:
                    points.append({
                        "tag": f"{dev_id}.I",
                        "value": float(dev["current_A"]),
                        "unit": "A",
                        "quality": dev.get("quality", "GOOD"),
                    })
                if "voltage_kV" in dev:
                    points.append({
                        "tag": f"{dev_id}.V",
                        "value": float(dev["voltage_kV"]),
                        "unit": "kV",
                        "quality": dev.get("quality", "GOOD"),
                    })
                if "voltage_setpoint" in dev:
                    points.append({
                        "tag": f"{dev_id}.V_SP",
                        "value": float(dev["voltage_setpoint"]),
                        "unit": "pu",
                        "quality": dev.get("quality", "GOOD"),
                    })

            # Ensure standard baseline tags exist
            if not any(p["tag"] == "BUS1.V" for p in points):
                points.insert(0, {"tag": "BUS1.V", "value": 1.02, "unit": "pu", "quality": "GOOD"})
                points.insert(1, {"tag": "BUS1.F", "value": 50.0, "unit": "Hz", "quality": "GOOD"})

        return {
            "success": True,
            "is_simulated": not is_prod,
            "data": {
                "timestamp": _utc_now_iso(),
                "source": "production_ot" if is_prod else "synthetic",
                "points": points,
            },
        }
    except Exception as exc:
        logger.exception("scada_live_failed error=%s", exc, extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [MSG_INTERNAL_ERROR], "trace_id": trace_id},
        )


@router.get("/devices")
async def scada_devices(
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """List substation bays and physical devices with their current operational states."""
    is_prod = os.getenv("SCADA_MODE", "simulation").lower() == "production"
    devices = []
    if is_prod:
        db = _get_wired_scada_db()
        if db is not None and db.switch_devices:
            for dev_id, sw in db.switch_devices.items():
                devices.append({
                    "device_id": dev_id,
                    "status": sw.status.name if hasattr(sw.status, "name") else str(sw.status),
                    "quality": "GOOD",
                    "control_mode": "REMOTE",
                    "voltage_kV": db.get_latest_voltage(sw.from_element) or db.get_latest_voltage(sw.to_element),
                    "current_A": None,
                    "tap_position": None,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
    else:
        for dev_id, dev_data in _SIMULATED_DEVICES.items():
            devices.append({
                "device_id": dev_id,
                "status": dev_data.get("status", "NORMAL"),
                "quality": dev_data.get("quality", "GOOD"),
                "control_mode": dev_data.get("control_mode", "REMOTE"),
                "voltage_kV": dev_data.get("voltage_kV"),
                "current_A": dev_data.get("current_A"),
                "tap_position": dev_data.get("tap_position"),
                "timestamp": dev_data.get("timestamp"),
            })

    return {
        "success": True,
        "tenant_id": user.tenant_id,
        "data": devices,
    }


# ---------------------------------------------------------------------------
# Control & Interlock Endpoints (Dual-Control Protected)
# ---------------------------------------------------------------------------


@router.post("/control/propose", status_code=status.HTTP_202_ACCEPTED)
async def propose_control_action(
    command: ControlCommandRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Propose a SCADA control operation (Maker action).

    Enforces:
    - Role authorization (engineer or admin required; operators/viewers are rejected)
    - Pre-flight Engineering Interlock checks (load flow overload & protection coordination)
    - Storing in database-backed ``PendingAction`` table with 300s TTL
    - Idempotency replay guard
    """
    endpoint = "POST /api/v1/scada/control/propose"
    replay = await _replay_idempotent(db, idempotency_key, endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: Only engineer or admin can propose control commands
    if user.role not in ("engineer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": f"User with role '{user.role}' cannot propose control commands. Engineer or Admin role required.",
            },
        )

    # 2. Pre-flight Engineering Interlock validation
    telemetry = {command.device_id: scada_executor.get_device_telemetry(command.device_id)}

    network_data = None
    coordination_data = None

    proj = None
    if command.project_id:
        proj_res = await db.execute(select(Project).where(Project.id == command.project_id))
        proj = proj_res.scalar_one_or_none()
    else:
        proj_res = await db.execute(
            select(Project).where(Project.tenant_id == user.tenant_id, Project.status == "active").order_by(Project.updated_at.desc())
        )
        proj = proj_res.scalars().first()
        if not proj:
            proj_res = await db.execute(
                select(Project).where(Project.tenant_id.is_(None), Project.status == "active").order_by(Project.updated_at.desc())
            )
            proj = proj_res.scalars().first()

    if proj and proj.system_config:
        network_data = proj.system_config
        prot_settings = network_data.get("protection_settings", {}) or network_data.get("coordination", {})
        bay_prot = prot_settings.get(command.bay_id or command.device_id) or prot_settings.get("default")
        if bay_prot:
            coordination_data = bay_prot

    # Fail-closed for breaker switching if no network model with branches is available
    if command.action_type in (ControlActionType.BREAKER_OPEN, ControlActionType.BREAKER_CLOSE):
        if not network_data or "branches" not in network_data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MISSING_NETWORK_MODEL",
                    "message": "Breaker switching requires an active network model with branches for What-If contingency analysis.",
                },
            )

    try:
        _interlock_engine.pre_flight_check(
            command=command,
            telemetry=telemetry,
            network_data=network_data,
            coordination_data=coordination_data,
        )
    except InterlockViolation as violation:
        logger.warning(
            "SCADA control proposal blocked by interlock: device=%s code=%s msg=%s",
            command.device_id,
            violation.code,
            violation.message,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": violation.code,
                "message": violation.message,
                "details": violation.details,
            },
        )

    # 3. Create PendingAction record
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    cmd_dict = command.model_dump()

    action = PendingAction(
        tenant_id=user.tenant_id,
        session_id=f"bay_{command.device_id}",
        tool="scada_control",
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
            "device_id": command.device_id,
            "action_type": command.action_type.value,
            "target_value": command.target_value,
            "reason": command.reason,
        },
    )

    response_data = {
        "success": True,
        "action_id": action.id,
        "status": "pending_approval",
        "device_id": command.device_id,
        "action_type": command.action_type.value,
        "expires_at": expires_at.isoformat(),
        "message": "Control command proposed and held for dual-control approval by an independent admin.",
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id, response_data)
    await db.commit()

    logger.info("SCADA command proposed: action_id=%s device=%s by user=%s", action.id, command.device_id, user.user_id)
    return response_data


@router.get("/control/pending")
async def list_pending_control_actions(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """List pending SCADA control actions scoped strictly to current tenant."""
    await expire_stale_actions(db)

    result = await db.execute(
        select(PendingAction).where(
            PendingAction.tool == "scada_control",
            PendingAction.status == "pending",
            func.coalesce(PendingAction.tenant_id, "") == _norm_tenant(user.tenant_id),
        )
    )
    pending = result.scalars().all()

    items = []
    for a in pending:
        items.append({
            "action_id": a.id,
            "session_id": a.session_id,
            "device_id": (a.args or {}).get("device_id"),
            "action_type": (a.args or {}).get("action_type"),
            "target_value": (a.args or {}).get("target_value"),
            "reason": (a.args or {}).get("reason"),
            "requested_by_user_id": a.requested_by_user_id,
            "requested_by_role": a.requested_by_role,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        })

    return {
        "success": True,
        "total": len(items),
        "data": items,
    }


@router.post("/control/{action_id}/resolve")
async def resolve_control_action(
    action_id: str,
    body: SCADAResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Approve or reject a pending SCADA control action (Checker action).

    Enforces:
    - Admin role requirement
    - Anti-self-approval (MAKER_CHECKER_VIOLATION HTTP 403)
    - Multi-tenant scoping
    - Live protocol execution with verify-by-readback
    - Full immutable audit record
    """
    resolve_endpoint = f"POST /api/v1/scada/control/{action_id}/resolve"
    replay = await _replay_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id)
    if replay is not None:
        return replay

    # 1. RBAC: Only admin can approve/reject
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ADMIN_ROLE_REQUIRED",
                "message": "Only users with the 'admin' role can approve or reject SCADA control actions.",
            },
        )

    await expire_stale_actions(db)

    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_CONTROL_ACTION_NOT_FOUND)

    # 2. Tenant isolation
    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_TENANT_FORBIDDEN",
                "message": "This control action belongs to another tenant.",
            },
        )

    # 3. Action status check
    if action.status != "pending":
        return {
            "success": False,
            "error": {
                "code": "ALREADY_RESOLVED",
                "status": action.status,
                "message": f"Action is already '{action.status}'",
            },
        }

    # 4. Anti-Self-Approval (Maker-Checker violation)
    if body.decision == "approve" and user.user_id == action.requested_by_user_id:
        record_approval_event(
            APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
            action.id,
            user.user_id,
            {"device_id": (action.args or {}).get("device_id"), "attempted_decision": body.decision},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MAKER_CHECKER_VIOLATION",
                "message": "Self-approval is forbidden. A different authorized admin must approve this critical control action.",
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
            "message": "Control action was rejected.",
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

    cmd_req = ControlCommandRequest(**(action.args or {}))
    exec_res = await scada_executor.execute_command(cmd_req, action_id=action.id)

    if exec_res.status == CommandStatus.COMPLETED:
        action.status = "completed"
    else:
        action.status = "failed"

    response_data = {
        "success": exec_res.readback_verified,
        "action_id": action.id,
        "status": action.status,
        "result": exec_res.model_dump(),
    }

    await _store_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id, response_data)
    await db.commit()

    return response_data


@router.get("/control/{action_id}/status")
async def get_control_action_status(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
):
    """Retrieve detailed status of a proposed/executed control action."""
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_CONTROL_ACTION_NOT_FOUND)

    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_CONTROL_ACTION_NOT_FOUND)

    return {
        "success": True,
        "data": {
            "action_id": action.id,
            "status": action.status,
            "device_id": (action.args or {}).get("device_id"),
            "action_type": (action.args or {}).get("action_type"),
            "target_value": (action.args or {}).get("target_value"),
            "requested_by_user_id": action.requested_by_user_id,
            "decided_by_user_id": action.decided_by_user_id,
            "created_at": action.created_at.isoformat() if action.created_at else None,
            "resolved_at": action.resolved_at.isoformat() if action.resolved_at else None,
        },
    }
