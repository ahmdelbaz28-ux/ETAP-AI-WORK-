"""
api/approvals.py — Approval Gateway (P2).

Central gate through which every mutating / critical tool invocation must
pass before execution. Provides:

* ``PendingAction`` ORM model — one row per proposed action, carrying the
  full maker-checker identity trail (who requested, who decided).
* ``IdempotencyKey`` ORM model — prevents double execution of the same
  logical operation when clients retry with the same ``Idempotency-Key``.
* Lifecycle: ``pending → approved | rejected | expired → executing →
  completed | failed`` with a hard TTL of 300 s (5 minutes) from creation.
* Maker-checker (dual control): a ``critical`` action can never be approved
  by the same user who requested it — self-approval is rejected with
  ``MAKER_CHECKER_VIOLATION`` and audited.
* Idempotency on both ``POST /api/v1/approvals`` and
  ``POST /api/v1/approvals/{id}/resolve``: replaying a key returns the
  original response instead of creating/deciding twice.
* Full audit coverage via :func:`api.dual_control.record_approval_event`
  (PROPOSED, PENDING, APPROVED, REJECTED, EXPIRED, AUTO_APPROVED,
  MAKER_CHECKER_VIOLATION).

Endpoints (prefix ``/api/v1``):
* ``POST /api/v1/approvals``                    — propose an action
* ``GET  /api/v1/approvals/pending``            — list pending for a session
* ``POST /api/v1/approvals/{id}/resolve``       — approve / reject
* ``PUT  /api/v1/session/auto-approve``         — toggle per-session auto-run
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, DateTime, Index, String, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.dual_control import (
    APPROVAL_EVENT_APPROVED,
    APPROVAL_EVENT_AUTO_APPROVED,
    APPROVAL_EVENT_EXPIRED,
    APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
    APPROVAL_EVENT_PENDING,
    APPROVAL_EVENT_PROPOSED,
    APPROVAL_EVENT_REJECTED,
    MAKER_CHECKER_VIOLATION,
    record_approval_event,
)
from api.tool_policy import TOOL_ALIASES, TOOL_POLICIES, evaluate_tool_policy

# Reason code raised when the authenticated user's tenant does not match the
# tenant stamped on a pending action (Security Gate — P2 tenant isolation).
CROSS_TENANT_FORBIDDEN = "CROSS_TENANT_FORBIDDEN"


def _norm_tenant(tenant_id: Optional[str]) -> str:
    """Normalise a tenant id for equality checks ('' for unscoped/None)."""
    return tenant_id or ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APPROVAL_TTL_SECONDS = 300  # 5 minutes — matches dual_control.AUTO_REJECT_SECONDS
IDEMPOTENCY_TTL_SECONDS = 86400  # replay window: 24 h

_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"
_STATUS_EXPIRED = "expired"
_STATUS_EXECUTING = "executing"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"

_RISK_READ = "read"
_RISK_MUTATING = "mutating"
_RISK_CRITICAL = "critical"

_IDEMPOTENCY_REPLAY_FLAG = "idempotent_replay"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def compute_args_hash(args: Dict[str, Any]) -> str:
    """Stable SHA-256 over canonical JSON of the tool arguments."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_tool(tool_name: str) -> str:
    """Resolve a tool's risk class via the Tool Policy Engine registry.

    Mirrors ``api.tool_policy._resolve_policy`` using its *public* constants:
    alias first, then canonical table, then deny-by-default ``critical``.
    """
    canonical = TOOL_ALIASES.get(tool_name, tool_name)
    return TOOL_POLICIES.get(canonical, {}).get("classification", _RISK_CRITICAL)


# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class PendingAction(Base):
    """A proposed tool action awaiting approval (or already decided).

    Lifecycle: pending → approved | rejected | expired → executing →
    completed | failed. The maker-checker columns capture *who* requested
    and *who* decided so dual-control can be proven after the fact.
    """

    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, default=_STATUS_PENDING)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Maker-checker identity trail
    requested_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_role: Mapped[str] = mapped_column(String(32), nullable=False, default="engineer")
    decided_by_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decided_by_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Original arguments (for the executor once approved)
    args: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("ix_pending_actions_session_status", "session_id", "status"),)


class IdempotencyKey(Base):
    """Stored response for an ``Idempotency-Key`` so retries are safe.

    A retry of POST /approvals or POST /approvals/{id}/resolve with the same
    key returns the stored ``response_data`` instead of executing again.
    """

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    response_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------


class CreateApprovalRequest(BaseModel):
    """Body for proposing an action through the gateway."""

    model_config = ConfigDict(strict=False)

    session_id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=128)
    args: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: Optional[str] = Field(default=None, max_length=36)


class ResolveRequest(BaseModel):
    """Body for approving / rejecting a pending action."""

    decision: str = Field(pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=2000)


class AutoApproveRequest(BaseModel):
    """Body for toggling per-session auto-approval."""

    session_id: str = Field(min_length=1, max_length=64)
    enabled: bool


class ApprovalResponse(BaseModel):
    """Public representation of a pending action."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: Optional[str] = None
    session_id: str
    tool: str
    args_hash: str
    risk_class: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    requested_by_user_id: Optional[str] = None
    requested_by_role: Optional[str] = None
    decided_by_user_id: Optional[str] = None
    decided_by_role: Optional[str] = None


# ---------------------------------------------------------------------------
# Session auto-approve registry
# ---------------------------------------------------------------------------

# Per-session auto-run toggle. Kept in-memory (single-replica HF Space);
# a Redis-backed store would be a drop-in replacement.
_session_auto_approve: Dict[str, bool] = {}


def set_session_auto_approve(session_id: str, enabled: bool) -> None:
    _session_auto_approve[session_id] = bool(enabled)


def get_session_auto_approve(session_id: str) -> bool:
    return bool(_session_auto_approve.get(session_id, False))


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------


async def _replay_idempotent(
    db: AsyncSession,
    key: Optional[str],
    endpoint: str,
    tenant_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Return the stored response for *key*, or ``None`` on miss/no key.

    A stored key only replays for the SAME endpoint AND the SAME tenant it
    was minted under (Security Gate — P2 tenant isolation). Expired keys are
    ignored (treated as a miss) so the replay window is bounded by
    ``IDEMPOTENCY_TTL_SECONDS``.
    """
    if not key:
        return None
    result = await db.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    # Tenant isolation: a key minted by one tenant must never replay into
    # another tenant's context, and an endpoint-scoped key must never replay
    # across endpoints (e.g. propose-key replaying a resolve call).
    if _norm_tenant(record.tenant_id) != _norm_tenant(tenant_id):
        return None
    if record.endpoint != endpoint:
        return None
    expires_at = record.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if record.expires_at is not None and expires_at <= _utc_now():
        return None
    payload = dict(record.response_data or {})
    payload[_IDEMPOTENCY_REPLAY_FLAG] = True
    return payload


async def _store_idempotent(
    db: AsyncSession,
    key: Optional[str],
    endpoint: str,
    tenant_id: Optional[str],
    response_data: Dict[str, Any],
) -> None:
    """Persist a response under *key*. Best-effort: races collapse to a no-op.

    A key owned by another endpoint/tenant is left untouched (its owner keeps
    it) — this handler simply skips storing, keeping the current operation's
    own side effects intact.
    """
    if not key:
        return
    # Sequential guard: if the key is already claimed (same or different
    # endpoint/tenant), do not attempt an insert that would only end in an
    # IntegrityError whose rollback would discard the caller's work.
    existing = await db.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    if existing.scalar_one_or_none() is not None:
        return
    now = _utc_now()
    record = IdempotencyKey(
        key=key,
        tenant_id=tenant_id,
        endpoint=endpoint,
        response_data=response_data,
        created_at=now,
        expires_at=now + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS),
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent request stored the same key first — keep theirs.
        await db.rollback()


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def expire_stale_actions(db: AsyncSession) -> int:
    """Mark every overdue ``pending`` action as ``expired``; audit each one.

    Returns the number of actions expired. Called before any read/resolve so
    the TTL is enforced lazily without needing a background sweeper.
    """
    now = _utc_now()
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.status == _STATUS_PENDING,
            PendingAction.expires_at <= now,
        )
    )
    stale = result.scalars().all()
    for action in stale:
        action.status = _STATUS_EXPIRED
        action.resolved_at = now
        db.add(action)
        record_approval_event(
            APPROVAL_EVENT_EXPIRED,
            action.id,
            action.requested_by_user_id,
            {"tool": action.tool, "reason": "TTL_EXPIRED"},
        )
    return len(stale)


async def transition_status(db: AsyncSession, action: PendingAction, new_status: str) -> None:
    """Advance an action along its lifecycle and persist it.

    Valid transitions follow ``pending → approved|rejected|expired →
    executing → completed|failed``; anything else raises ValueError so
    executors cannot skip states silently.
    """
    allowed: Dict[str, tuple] = {
        _STATUS_PENDING: (_STATUS_APPROVED, _STATUS_REJECTED, _STATUS_EXPIRED),
        _STATUS_APPROVED: (_STATUS_EXECUTING,),
        _STATUS_EXECUTING: (_STATUS_COMPLETED, _STATUS_FAILED),
    }
    if new_status not in allowed.get(action.status, ()):
        raise ValueError(f"invalid transition {action.status} -> {new_status}")
    action.status = new_status
    if new_status in (_STATUS_REJECTED, _STATUS_EXPIRED, _STATUS_COMPLETED, _STATUS_FAILED):
        action.resolved_at = _utc_now()
    db.add(action)
    await db.flush()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _action_to_response(action: PendingAction) -> Dict[str, Any]:
    return {
        "id": action.id,
        "tenant_id": action.tenant_id,
        "session_id": action.session_id,
        "tool": action.tool,
        "args_hash": action.args_hash,
        "risk_class": action.risk_class,
        "status": action.status,
        "expires_at": action.expires_at.isoformat() if action.expires_at else None,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "resolved_at": action.resolved_at.isoformat() if action.resolved_at else None,
        "requested_by_user_id": action.requested_by_user_id,
        "requested_by_role": action.requested_by_role,
        "decided_by_user_id": action.decided_by_user_id,
        "decided_by_role": action.decided_by_role,
    }


@router.post("", summary="Propose an action for approval")
async def create_approval(
    body: CreateApprovalRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """Evaluate a tool invocation and open a pending action when needed.

    Risk classification comes from the Tool Policy Engine (deny-by-default).
    ``read`` actions are auto-approved immediately; ``mutating`` follow the
    session auto-approve toggle; ``critical`` always require a human decision
    from a *different* user (maker-checker enforced at resolve time).
    """
    replay = await _replay_idempotent(db, idempotency_key, "POST /api/v1/approvals", user.tenant_id)
    if replay is not None:
        return replay

    policy_decision = evaluate_tool_policy(body.tool, args=body.args, auto_approve_enabled=False)
    if policy_decision.get("decision") == "rejected":
        # e.g. UNSOURCED_ENGINEERING_VALUE — the gateway must not even queue it.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": policy_decision.get("reason"),
                "message": "Tool invocation rejected by the Tool Policy Engine.",
            },
        )
    risk_class = classify_tool(body.tool)

    now = _utc_now()
    args_hash = compute_args_hash(body.args)
    action_id = str(uuid.uuid4())

    auto_approved = False
    if risk_class == _RISK_READ or (
        risk_class == _RISK_MUTATING and get_session_auto_approve(body.session_id)
    ):
        decision_status = _STATUS_APPROVED
        auto_approved = True
    else:
        decision_status = _STATUS_PENDING

    action = PendingAction(
        id=action_id,
        # Security Gate (P2): the tenant stamped on the action ALWAYS comes
        # from the authenticated user, never from the request body. A caller
        # without a tenant cannot stamp an arbitrary tenant onto the record.
        tenant_id=user.tenant_id or None,
        session_id=body.session_id,
        tool=body.tool,
        args_hash=args_hash,
        risk_class=risk_class,
        status=decision_status,
        expires_at=now + timedelta(seconds=APPROVAL_TTL_SECONDS),
        created_at=now,
        requested_by_user_id=user.user_id,
        requested_by_role=user.role,
        args=body.args,
    )
    db.add(action)
    await db.flush()

    record_approval_event(
        APPROVAL_EVENT_PROPOSED,
        action.id,
        user.user_id,
        {"tool": body.tool, "risk_class": risk_class, "args_hash": args_hash},
    )
    record_approval_event(
        APPROVAL_EVENT_AUTO_APPROVED if auto_approved else APPROVAL_EVENT_PENDING,
        action.id,
        user.user_id,
        {"tool": body.tool, "risk_class": risk_class},
    )

    payload = {"success": True, "data": _action_to_response(action)}
    await _store_idempotent(db, idempotency_key, "POST /api/v1/approvals", user.tenant_id, payload)
    return payload


@router.get("/pending", summary="List pending approvals for a session")
async def list_pending(
    session_id: str = Query(min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Dict[str, Any]:
    """Return all still-valid pending actions for *session_id* (TTL applied).

    Security Gate (P2 tenant isolation): the query is scoped by
    ``session_id AND tenant_id == authenticated_user.tenant_id`` — a user in
    one tenant can never enumerate another tenant's pending actions even
    when the session id is shared.
    """
    await expire_stale_actions(db)
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.session_id == session_id,
            PendingAction.status == _STATUS_PENDING,
            func.coalesce(PendingAction.tenant_id, "") == _norm_tenant(user.tenant_id),
        )
    )
    pending = result.scalars().all()
    return {
        "success": True,
        "total": len(pending),
        "data": [_action_to_response(a) for a in pending],
    }


@router.post("/{action_id}/resolve", summary="Approve or reject a pending action")
async def resolve_action(
    action_id: str,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """Apply an approve/reject decision with maker-checker enforcement.

    For ``critical`` actions the deciding user MUST differ from the requesting
    user; self-approval is rejected with ``MAKER_CHECKER_VIOLATION`` (HTTP 403)
    and audited.

    Security Gate (P2 tenant isolation): the action must belong to the
    authenticated user's tenant before any decision (or state disclosure)
    happens — the lookup/authorization is always tenant-scoped.
    """
    resolve_endpoint = f"POST /api/v1/approvals/{action_id}/resolve"
    replay = await _replay_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id)
    if replay is not None:
        return replay

    await expire_stale_actions(db)

    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    # ── Tenant isolation gate (before ANY state disclosure/decision) ──────
    if _norm_tenant(action.tenant_id) != _norm_tenant(user.tenant_id):
        record_approval_event(
            "CROSS_TENANT_RESOLVE_DENIED",
            action.id,
            user.user_id,
            {"tool": action.tool, "action_tenant_id": action.tenant_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CROSS_TENANT_FORBIDDEN,
                "message": (
                    "This approval belongs to a different tenant and cannot "
                    "be resolved by the requesting user."
                ),
            },
        )

    if action.status != _STATUS_PENDING:
        return {
            "success": False,
            "error": {
                "code": "ALREADY_RESOLVED",
                "status": action.status,
                "message": f"Action already resolved as '{action.status}'",
            },
        }

    # Maker-checker: critical actions require a second pair of eyes.
    if (
        action.risk_class == _RISK_CRITICAL
        and body.decision == "approve"
        and user.user_id == action.requested_by_user_id
    ):
        record_approval_event(
            APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
            action.id,
            user.user_id,
            {"tool": action.tool, "attempted_decision": body.decision},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": MAKER_CHECKER_VIOLATION,
                "message": (
                    "Critical actions cannot be approved by their requester — "
                    "a second engineer must decide."
                ),
            },
        )

    action.decided_by_user_id = user.user_id
    action.decided_by_role = user.role
    action.resolved_at = _utc_now()
    if body.decision == "approve":
        action.status = _STATUS_APPROVED
        event_type = APPROVAL_EVENT_APPROVED
    else:
        action.status = _STATUS_REJECTED
        event_type = APPROVAL_EVENT_REJECTED
    db.add(action)
    await db.flush()

    record_approval_event(
        event_type,
        action.id,
        user.user_id,
        {
            "tool": action.tool,
            "decision": body.decision,
            "reason": body.reason,
            "requested_by": action.requested_by_user_id,
        },
    )

    payload = {"success": True, "data": _action_to_response(action)}
    await _store_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id, payload)
    return payload


# ---------------------------------------------------------------------------
# Session auto-approve toggle (registered under /api/v1/session/*)
# ---------------------------------------------------------------------------

session_router = APIRouter(prefix="/api/v1/session", tags=["approvals"])


@session_router.put("/auto-approve", summary="Toggle per-session auto-approval")
async def set_auto_approve(
    body: AutoApproveRequest,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Dict[str, Any]:
    """Enable/disable automatic approval of mutating tools for a session.

    Critical tools are NEVER auto-approved regardless of this toggle.
    """
    set_session_auto_approve(body.session_id, body.enabled)
    return {
        "success": True,
        "data": {
            "session_id": body.session_id,
            "enabled": get_session_auto_approve(body.session_id),
            "note": "critical tools always require manual approval",
        },
    }
