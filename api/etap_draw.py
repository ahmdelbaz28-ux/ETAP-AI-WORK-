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

    plan_kind = (action.args or {}).get("plan_kind")
    if plan_kind == "full_network":
        raw_chunks = (action.args or {}).get("chunks") or []
        if not raw_chunks:
            action.status = "failed"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PLAN", "message": "No chunks found in full_network plan"},
            )

        try:
            plans = [EtapDrawPlan(**c) for c in raw_chunks]
        except Exception as exc:
            action.status = "failed"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_PLAN", "message": f"Stored chunk plan is invalid: {exc}"},
            )

        client = get_rest_client_from_env()

        async def _on_chunk(chunk_idx: int, res: Any, created_ids: list[str]) -> None:
            curr = dict(action.args or {})
            curr["completed_chunks"] = chunk_idx + 1
            curr["total_chunks"] = len(plans)
            curr["created_element_ids"] = created_ids
            action.args = curr

        try:
            from etap_integration.draw_plan_builder import execute_draw_plans_atomic

            executed = await execute_draw_plans_atomic(
                client,
                plans,
                on_chunk_completed=_on_chunk,
            )
        except ETAPRestError as exc:
            action.status = "failed"
            curr = dict(action.args or {})
            curr["error"] = {"code": exc.code, "message": exc.message, "details": exc.details}
            action.args = curr
            record_approval_event(
                "EXECUTION_FAILED",
                action.id,
                user.user_id,
                {"error": exc.code, "message": exc.message},
            )
            await db.commit()
            code = 503 if exc.code in ("MISSING_CONFIG", "UNAVAILABLE", "AUTH_FAILED") else 502
            raise HTTPException(
                status_code=code,
                detail={"code": exc.code, "message": exc.message, "details": exc.details},
            )

        # Post-draw Load Flow verification
        from api.projects import Project
        from etap_integration.post_draw_verifier import dispatch_load_flow_verification

        project_id = str((action.args or {}).get("project_id") or "")
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        proj = proj_res.scalar_one_or_none()
        baseline_model = (proj.system_config or {}) if proj else {}

        verification_result = await dispatch_load_flow_verification(
            project_path=project_id,
            baseline_model=baseline_model,
        )

        curr = dict(action.args or {})
        curr["verification"] = verification_result.model_dump()
        action.args = curr
        action.status = "completed"

        response_data = {
            "success": True,
            "action_id": action.id,
            "status": action.status,
            "plan_kind": "full_network",
            "project_id": project_id,
            "total_chunks": len(plans),
            "executed_chunks": len(executed),
            "verification": verification_result.model_dump(),
        }

        await _store_idempotent(
            db, idempotency_key, resolve_endpoint, user.tenant_id, response_data
        )
        await db.commit()
        logger.info(
            "ETAP full network draw completed: action_id=%s project=%s", action.id, project_id
        )
        return response_data

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
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Extracts normalized network elements from project.system_config.

    Returns:
        (network_dict, problems_list)
        where problems_list tracks incomplete, unmapped, or missing items.
    """
    problems: list[dict[str, Any]] = []
    if not isinstance(system_config, dict):
        return {"buses": []}, [{"error": "system_config_not_dict"}]

    # 1. Zenon network export format
    if "zenon_network" in system_config:
        from integrations.zenon_network_export.reader import parse_zenon_export

        raw_zn = system_config["zenon_network"]
        res = parse_zenon_export(raw_zn)
        if not res.is_valid:
            problems.append({"error": "zenon_parse_failed", "details": res.errors})
            return {"buses": []}, problems

        for inc in res.incomplete:
            problems.append(inc)
        for warn in res.warnings:
            problems.append({"warning": warn})

        network = {
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
        return network, problems

    # 2. Direct objects / components dict
    if "objects" in system_config and isinstance(system_config["objects"], dict):
        return system_config["objects"], problems
    if "buses" in system_config and isinstance(system_config["buses"], list):
        return system_config, problems

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
                raw_kv = (
                    meta.get("nominal_voltage_kv")
                    if meta.get("nominal_voltage_kv") is not None
                    else meta.get("voltage_kv")
                )
                if raw_kv is None:
                    problems.append(
                        {
                            "element": aid,
                            "missing": "nominal_voltage_kv",
                            "reason": "missing_voltage",
                        }
                    )
                    continue
                try:
                    kv = float(raw_kv)
                except (ValueError, TypeError):
                    problems.append(
                        {"element": aid, "invalid": "nominal_voltage_kv", "value": raw_kv}
                    )
                    continue
                parsed["buses"].append({"id": aid, "name": name, "base_kv": kv})
            elif atype == "TRANSFORMER":
                fb = meta.get("from_bus")
                tb = meta.get("to_bus")
                if not fb or not tb:
                    problems.append(
                        {"element": aid, "missing": "terminals", "from_bus": fb, "to_bus": tb}
                    )
                entry: dict[str, Any] = {
                    "id": aid,
                    "name": name,
                    "from_bus": fb,
                    "to_bus": tb,
                }
                if meta.get("rating_mva") is not None:
                    try:
                        entry["rating_mva"] = float(meta["rating_mva"])
                    except (ValueError, TypeError):
                        pass
                parsed["transformers"].append(entry)
            elif atype == "LINE":
                fb = meta.get("from_bus")
                tb = meta.get("to_bus")
                if not fb or not tb:
                    problems.append(
                        {"element": aid, "missing": "terminals", "from_bus": fb, "to_bus": tb}
                    )
                entry = {
                    "id": aid,
                    "name": name,
                    "from_bus": fb,
                    "to_bus": tb,
                }
                for f in ("r_pu", "x_pu", "rating_mva"):
                    if meta.get(f) is not None:
                        try:
                            entry[f] = float(meta[f])
                        except (ValueError, TypeError):
                            pass
                parsed["lines"].append(entry)
            elif atype == "CABLE":
                fb = meta.get("from_bus")
                tb = meta.get("to_bus")
                if not fb or not tb:
                    problems.append(
                        {"element": aid, "missing": "terminals", "from_bus": fb, "to_bus": tb}
                    )
                parsed["cables"].append(
                    {
                        "id": aid,
                        "name": name,
                        "from_bus": fb,
                        "to_bus": tb,
                    }
                )
            elif atype == "BREAKER":
                fb = meta.get("from_bus")
                tb = meta.get("to_bus")
                if not fb or not tb:
                    problems.append(
                        {"element": aid, "missing": "terminals", "from_bus": fb, "to_bus": tb}
                    )
                parsed["breakers"].append(
                    {
                        "id": aid,
                        "name": name,
                        "from_bus": fb,
                        "to_bus": tb,
                    }
                )
            elif atype in ("DISCONNECTOR", "SWITCH"):
                fb = meta.get("from_bus")
                tb = meta.get("to_bus")
                if not fb or not tb:
                    problems.append(
                        {"element": aid, "missing": "terminals", "from_bus": fb, "to_bus": tb}
                    )
                parsed["switches"].append(
                    {
                        "id": aid,
                        "name": name,
                        "from_bus": fb,
                        "to_bus": tb,
                    }
                )
            elif atype == "LOAD":
                bus = meta.get("bus") or meta.get("from_bus")
                if not bus:
                    problems.append({"element": aid, "missing": "bus"})
                entry = {
                    "id": aid,
                    "name": name,
                    "bus": bus,
                }
                if meta.get("active_power_mw") is not None:
                    try:
                        entry["p_mw"] = float(meta["active_power_mw"])
                    except (ValueError, TypeError):
                        pass
                if meta.get("reactive_power_mvar") is not None:
                    try:
                        entry["q_mvar"] = float(meta["reactive_power_mvar"])
                    except (ValueError, TypeError):
                        pass
                parsed["loads"].append(entry)
            elif atype == "GENERATOR":
                bus = meta.get("bus") or meta.get("from_bus")
                if not bus:
                    problems.append({"element": aid, "missing": "bus"})
                parsed["generators"].append(
                    {
                        "id": aid,
                        "name": name,
                        "bus": bus,
                    }
                )
        return parsed, problems

    return {"buses": []}, problems


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
    network_data, problems = _extract_network_from_project_config(project.system_config or {})
    if any(p.get("error") == "zenon_parse_failed" for p in problems):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ZENON_PARSE_FAILED",
                "message": "Zenon network export failed parsing or validation.",
                "details": [p for p in problems if p.get("error") == "zenon_parse_failed"],
            },
        )

    if not network_data.get("buses"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_NETWORK_DATA",
                "message": "Project system_config does not contain valid network topology (assets or zenon_network).",
                "problems": problems,
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

    # 6. Create single parent PendingAction with plan_kind="full_network"
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    total_elements = sum(len(p.items) for p in plans)

    parent_args = {
        "plan_kind": "full_network",
        "project_id": body.project_id,
        "reason": body.reason,
        "total_chunks": len(plans),
        "total_elements": total_elements,
        "chunks": [p.model_dump() for p in plans],
    }

    action = PendingAction(
        tenant_id=user.tenant_id,
        session_id=f"etap_draw_{body.project_id}",
        tool=TOOL_NAME,
        args_hash=compute_args_hash(parent_args),
        risk_class=RISK_CLASS,
        status="pending",
        expires_at=expires_at,
        created_at=now,
        requested_by_user_id=user.user_id,
        requested_by_role=user.role,
        args=parent_args,
    )
    db.add(action)
    await db.flush()

    record_approval_event(
        APPROVAL_EVENT_PROPOSED,
        action.id,
        user.user_id,
        {
            "project_id": body.project_id,
            "plan_kind": "full_network",
            "total_chunks": len(plans),
            "elements": total_elements,
            "reason": body.reason,
        },
    )

    response_data = {
        "success": True,
        "project_id": body.project_id,
        "action_id": action.id,
        "action_ids": [action.id],
        "total_chunks": len(plans),
        "total_elements": total_elements,
        "status": "pending_approval",
        "expires_at": expires_at.isoformat(),
        "message": f"Proposed full network draw with {len(plans)} chunk(s) held for dual-control approval.",
    }

    await _store_idempotent(db, idempotency_key, endpoint, user.tenant_id, response_data)
    await db.commit()

    return response_data
