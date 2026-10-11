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
from typing import Any, Optional

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


@router.post(
    "/propose",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "Bad request"},
        403: {
            "description": "Forbidden — insufficient role, tenant not allowlisted, or feature disabled"
        },
        422: {"description": "Validation error — invalid draw plan"},
    },
)
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


@router.get(
    "/pending",
    responses={
        403: {"description": "Forbidden — insufficient role or feature disabled"},
    },
)
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


@router.post(
    "/{action_id}/resolve",
    responses={
        400: {"description": "Bad request"},
        403: {
            "description": "Forbidden — insufficient role, cross-tenant, or maker-checker violation"
        },
        404: {"description": "Draw action not found"},
    },
)
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


@router.get(
    "/{action_id}/status",
    responses={
        403: {"description": "Forbidden — cross-tenant access"},
        404: {"description": "Draw action not found"},
    },
)
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


# ---------------------------------------------------------------------------
# Phase 3: Full-Network Draw from Project Topology (Dual-Control)
# ---------------------------------------------------------------------------

FLAG_FULL_NETWORK = "etap_draw_full_network"
ENV_FLAG_FULL_NETWORK_OVERRIDE = "FEATURE_FLAG_ETAP_DRAW_FULL_NETWORK"


def is_full_network_draw_enabled() -> bool:
    """Stored-flag gate with env override. Default deny in EVERY environment."""
    override = os.getenv(ENV_FLAG_FULL_NETWORK_OVERRIDE)
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on")
    try:
        from api.feature_flags import _load_flags

        stored = _load_flags().get(FLAG_FULL_NETWORK, {})
        return bool(stored.get("enabled", False))
    except Exception:
        return False


def _require_full_network_draw_enabled() -> None:
    if not is_full_network_draw_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "Full network ETAP drawing is disabled (flag etap_draw_full_network OFF).",
            },
        )


class EtapDrawFromProjectRequest(BaseModel):
    """Request model for proposing a full network draw from stored project topology."""

    model_config = ConfigDict(strict=False, extra="forbid")

    project_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=5, max_length=1000)
    max_items_per_chunk: int = Field(default=50, ge=1, le=50)


def _extract_network_from_project_config(
    system_config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Extracts normalized network elements from project.system_config."""
    if not isinstance(system_config, dict):
        return {"buses": []}

    # 1. Zenon network export format
    if "zenon_network" in system_config:
        from integrations.zenon_network_export.reader import parse_zenon_export

        raw_zn = system_config["zenon_network"]
        res = parse_zenon_export(raw_zn)
        if res.is_valid:
            return {
                "buses": [b.model_dump() for b in res.contract.buses],
                "transformers": [xf.model_dump() for xf in res.contract.transformers],
                "lines": [l.model_dump() for l in res.contract.lines],
                "cables": [c.model_dump() for c in res.contract.cables],
                "breakers": [brk.model_dump() for brk in res.contract.breakers],
                "switches": [sw.model_dump() for sw in res.contract.switches],
                "loads": [ld.model_dump() for ld in res.contract.loads],
                "generators": [g.model_dump() for g in res.contract.generators],
                "motors": [m.model_dump() for m in res.contract.motors],
                "relays": [r.model_dump() for r in res.contract.relays],
                "capacitors": [cp.model_dump() for cp in res.contract.capacitors],
                "reactors": [rc.model_dump() for rc in res.contract.reactors],
            }

    # 2. Direct objects / components dict
    if "objects" in system_config and isinstance(system_config["objects"], dict):
        return system_config["objects"]
    if "buses" in system_config and isinstance(system_config["buses"], list):
        return system_config

    # 3. ADMS assets format (adms_assets or assets)
    raw_assets = system_config.get("adms_assets") or system_config.get("assets")
    if isinstance(raw_assets, list) and len(raw_assets) > 0:
        parsed: dict[str, list[dict[str, Any]]] = {
            "buses": [],
            "transformers": [],
            "lines": [],
            "cables": [],
            "breakers": [],
            "switches": [],
            "loads": [],
            "generators": [],
        }
        for item in raw_assets:
            if not isinstance(item, dict):
                continue
            atype = str(item.get("asset_type", "")).upper()
            aid = str(item.get("asset_id") or "")
            meta = dict(item.get("metadata") or {})
            name = str(meta.get("name") or aid)

            if atype in ("BUSBAR", "SUBSTATION", "BUS"):
                kv = meta.get("nominal_voltage_kv") or meta.get("voltage_kv") or 11.0
                parsed["buses"].append({"id": aid, "name": name, "base_kv": float(kv)})
            elif atype == "TRANSFORMER":
                parsed["transformers"].append({
                    "id": aid,
                    "name": name,
                    "from_bus": meta.get("from_bus"),
                    "to_bus": meta.get("to_bus"),
                    "rating_mva": meta.get("rating_mva"),
                })
            elif atype == "LINE":
                parsed["lines"].append({
                    "id": aid,
                    "name": name,
                    "from_bus": meta.get("from_bus"),
                    "to_bus": meta.get("to_bus"),
                    "r_pu": meta.get("r_pu"),
                    "x_pu": meta.get("x_pu"),
                    "rating_mva": meta.get("rating_mva"),
                })
            elif atype == "CABLE":
                parsed["cables"].append({
                    "id": aid,
                    "name": name,
                    "from_bus": meta.get("from_bus"),
                    "to_bus": meta.get("to_bus"),
                })
            elif atype == "BREAKER":
                parsed["breakers"].append({
                    "id": aid,
                    "name": name,
                    "from_bus": meta.get("from_bus") or meta.get("bus"),
                    "to_bus": meta.get("to_bus") or meta.get("bus"),
                })
            elif atype in ("DISCONNECTOR", "SWITCH"):
                parsed["switches"].append({
                    "id": aid,
                    "name": name,
                    "from_bus": meta.get("from_bus") or meta.get("bus"),
                    "to_bus": meta.get("to_bus") or meta.get("bus"),
                })
            elif atype == "LOAD":
                parsed["loads"].append({
                    "id": aid,
                    "name": name,
                    "bus": meta.get("bus") or meta.get("from_bus"),
                    "p_mw": meta.get("active_power_mw"),
                    "q_mvar": meta.get("reactive_power_mvar"),
                })
            elif atype == "GENERATOR":
                parsed["generators"].append({
                    "id": aid,
                    "name": name,
                    "bus": meta.get("bus") or meta.get("from_bus"),
                })
        return parsed

    return {"buses": []}


@router.post(
    "/from-project",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "Bad request"},
        403: {
            "description": "Forbidden — insufficient role, tenant not allowlisted, or feature disabled"
        },
        404: {"description": "Project not found"},
        422: {"description": "Validation error — invalid network topology or empty plan"},
    },
)
async def propose_draw_from_project(
    body: EtapDrawFromProjectRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user_from_header),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Propose an automatic full network ETAP drawing from stored project topology (Maker action)."""
    _require_draw_enabled()
    _require_full_network_draw_enabled()

    endpoint = "POST /api/v1/etap/draw/from-project"
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

    # 3. Query Project from database
    from api.projects import Project

    result = await db.execute(select(Project).where(Project.id == body.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if _norm_tenant(project.tenant_id) != _norm_tenant(user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CROSS_TENANT_FORBIDDEN,
                "message": "This project belongs to another tenant.",
            },
        )

    # 4. Extract network data from project system_config
    network_data = _extract_network_from_project_config(project.system_config or {})
    if not network_data.get("buses"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_NETWORK_DATA",
                "message": "Project system_config does not contain valid network topology (assets or zenon_network).",
            },
        )

    # 5. Build draw plan chunks
    from etap_integration.draw_plan_builder import build_draw_plan

    try:
        plans = build_draw_plan(
            network_data,
            project_id=body.project_id,
            max_items=body.max_items_per_chunk,
        )
    except ETAPRestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    if not plans:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_PLAN", "message": "No drawable items generated."},
        )

    # 6. Create PendingAction per chunk
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    action_ids: list[str] = []

    for idx, plan in enumerate(plans):
        plan_dict = plan.model_dump()
        action = PendingAction(
            tenant_id=user.tenant_id,
            session_id=f"etap_draw_{body.project_id}",
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
        action_ids.append(action.id)

        record_approval_event(
            APPROVAL_EVENT_PROPOSED,
            action.id,
            user.user_id,
            {
                "project_id": body.project_id,
                "chunk_index": idx + 1,
                "total_chunks": len(plans),
                "elements": len(plan.items),
                "reason": plan.reason,
            },
        )

    total_elements = sum(len(p.items) for p in plans)
    response_data = {
        "success": True,
        "project_id": body.project_id,
        "total_chunks": len(plans),
        "total_elements": total_elements,
        "action_ids": action_ids,
        "status": "pending_approval",
        "expires_at": expires_at.isoformat(),
        "message": f"Proposed full network draw with {len(plans)} chunk(s) held for dual-control approval.",
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id, response_data)
    await db.commit()

    return response_data

