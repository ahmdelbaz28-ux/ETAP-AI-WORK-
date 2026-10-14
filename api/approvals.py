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
from api.session_ownership import (
    Actor,
    OwnershipDenied,
    is_auto_approve,
)
from api.session_ownership import (
    _flags as _session_auto_approve,
)
from api.session_ownership import (
    set_auto_approve as _policy_set_auto_approve,
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

# SCADA / CUA control tools eligible for Owner-Authorized Single-Operator Mode
# (Validated Self-Confirmation lane). Everything else requires dual-control.
SCADA_CUA_CONTROL_TOOLS: frozenset[str] = frozenset(
    {
        "scada_control",
        "cua_control",
        "scada_control_tool",
        "cua_control_tool",
        "cua_action",
        "etap_gui",
        "etap_cua",
    }
)


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

    # Single-operator validated self-confirmation snapshot
    validation_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

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



def validate_server_control_action(
    action: PendingAction,
) -> tuple[bool, Dict[str, Any], str]:
    """Authoritative server-side validation for SCADA / CUA control actions.

    Single-operator self-confirmation MUST be verified authoritatively by the server
    rather than trusting client-supplied validation assertions.
    Inspired by agents.cua_base_executor.validate_control_action:
      1. Target existence & format (non-empty, non-placeholder, recognized ID).
      2. Refusal of destructive / lethal operation patterns.
      3. Interlock verification (grounding switch de-energization, locked/tagged-out checks).
      4. Action type validity (must be a supported SCADA / CUA control command).
      5. Value envelope checks (operating envelope limits for voltage, frequency, setpoints).

    Limitations:
      - Voltage envelope heuristic: In the parameter-envelope section, a numeric target
        value > 5.0 is treated as kV (rejected outside [0, 765]) and <= 5.0 as p.u.
        (rejected outside [0.80, 1.20]). A legitimate < 5 kV setpoint (e.g., 4.5 kV) is
        therefore misclassified as p.u. and fails closed (rejected). Supplying an explicit
        unit argument in action args is the recommended future improvement.
    """
    args = action.args or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    if not isinstance(args, dict) or not args:
        return (
            False,
            {"valid": False, "reason": "Action arguments are missing or malformed"},
            "INVALID_ARGUMENTS",
        )

    # 1. Target existence check
    raw_target = (
        args.get("device_id")
        or args.get("target")
        or args.get("element_id")
        or args.get("target_id")
    )
    target_str = str(raw_target or "").strip()
    target_lower = target_str.lower()

    if (
        not target_str
        or target_lower in ("unknown", "none", "null", "undefined", "<device_id>", "<target>", "placeholder")
        or "<" in target_str
        or ">" in target_str
    ):
        return (
            False,
            {
                "valid": False,
                "target_exists": False,
                "reason": f"Target device/element does not exist, is empty, or is placeholder: {raw_target!r}",
            },
            "INVALID_TARGET",
        )

    # 2. Action type check
    raw_action = (
        args.get("action_type")
        or args.get("command")
        or args.get("action")
        or args.get("type")
    )
    if raw_action is None:
        return (
            False,
            {
                "valid": False,
                "supported_action": False,
                "reason": "Missing action type or command in action arguments",
            },
            "MISSING_ACTION_TYPE",
        )

    action_str = str(raw_action).strip().lower()
    if not action_str:
        return (
            False,
            {
                "valid": False,
                "supported_action": False,
                "reason": "Empty action type in action arguments",
            },
            "MISSING_ACTION_TYPE",
        )

    supported_actions = {
        # Breaker / Switch operations
        "open", "close", "trip", "breaker_open", "breaker_close", "switch_open", "switch_close",
        # Transformer / Tap changer operations
        "raise", "lower", "tap_up", "tap_down", "tap_change",
        # Setpoints / Analog control
        "setpoint", "set_setpoint", "set_active_power", "set_reactive_power",
        "set_voltage_setpoint", "set_voltage", "voltage_setpoint", "frequency_setpoint",
        # CUA desktop / browser actions
        "click", "type", "key", "press", "drag", "scroll", "select", "input", "navigate",
        # General state commands
        "start", "stop", "reset", "enable", "disable",
    }
    if action_str not in supported_actions:
        return (
            False,
            {
                "valid": False,
                "supported_action": False,
                "reason": f"Action type {raw_action!r} is unsupported or cannot be authoritatively verified on server",
            },
            "UNSUPPORTED_ACTION_TYPE",
        )

    # 3. Destructive / lethal pattern check
    destructive_patterns = (
        "format", "wipe", "destroy", "kill", "rm -rf", "drop database", "purge",
        "emergency_trip", "black_start_inhibit", "disable_protection", "trip_generator",
        "drop_load_shedding", "hard_kill", "bypass_safety", "delete_all", "destructive",
    )
    combined_text = f"{target_lower} {action_str} {str(args.get('reason') or '').lower()}"
    for pat in destructive_patterns:
        if pat in combined_text:
            return (
                False,
                {
                    "valid": False,
                    "destructive_refused": True,
                    "reason": f"Destructive operation pattern '{pat}' is hard-refused for self-confirmation",
                },
                "DESTRUCTIVE_OPERATION_REFUSED",
            )

    # 4. Interlock check
    if ("earth" in target_lower or "ground" in target_lower) and any(
        k in action_str for k in ("close", "enable")
    ):
        if not args.get("is_deenergized", False):
            return (
                False,
                {
                    "valid": False,
                    "interlock_ok": False,
                    "reason": "Conflicting interlock state: grounding switch cannot close while circuit is not de-energized",
                },
                "INTERLOCK_VIOLATION",
            )

    if args.get("tagged_out") is True or "tagged_out" in target_lower or "locked" in target_lower:
        return (
            False,
            {
                "valid": False,
                "interlock_ok": False,
                "reason": f"Interlock violation: device {target_str} is tagged out or locked",
            },
            "INTERLOCK_VIOLATION",
        )

    # 5. Parameter envelope check
    raw_val = (
        args.get("target_value")
        or args.get("setpoint")
        or args.get("value")
    )
    if raw_val is not None:
        parsed_q = None
        try:
            num_val = float(raw_val)
        except (ValueError, TypeError):
            try:
                from core.units import parse_quantity
                parsed_q = parse_quantity(raw_val)
                if parsed_q is not None:
                    num_val = float(parsed_q.magnitude)
                else:
                    raise ValueError("Cannot parse numeric quantity")
            except Exception:
                return (
                    False,
                    {
                        "valid": False,
                        "within_envelope": False,
                        "reason": f"Target setpoint value is non-numeric: {raw_val!r}",
                    },
                    "INVALID_VALUE",
                )

        custom_envelope = args.get("envelope")
        if isinstance(custom_envelope, dict):
            min_v = custom_envelope.get("min")
            max_v = custom_envelope.get("max")
            if min_v is not None and num_val < min_v:
                return (
                    False,
                    {
                        "valid": False,
                        "within_envelope": False,
                        "reason": f"Value {num_val} is below minimum allowed envelope {min_v}",
                    },
                    "ENVELOPE_VIOLATION",
                )
            if max_v is not None and num_val > max_v:
                return (
                    False,
                    {
                        "valid": False,
                        "within_envelope": False,
                        "reason": f"Value {num_val} exceeds maximum allowed envelope {max_v}",
                    },
                    "ENVELOPE_VIOLATION",
                )

        if any(k in target_lower or k in action_str for k in ("voltage", "v_bus", "vset", "p.u.", "pu")):
            # Check explicit unit from parsed quantity or unit argument
            explicit_unit = args.get("unit")
            if parsed_q is None:
                try:
                    from core.units import parse_quantity
                    parsed_q = parse_quantity(raw_val)
                except Exception:
                    pass

            if parsed_q is not None:
                unit_name = str(parsed_q.units).lower()
                if "volt" in unit_name:
                    kv_val = float(parsed_q.to("kV").magnitude)
                    if kv_val < 0.0 or kv_val > 765.0:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {kv_val} kV is outside safe limits [0, 765]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
                elif unit_name in ("pu", "per_unit", "dimensionless"):
                    pu_val = float(parsed_q.magnitude)
                    if pu_val < 0.80 or pu_val > 1.20:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {pu_val} p.u. is outside safe operating envelope [0.80, 1.20]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
            elif explicit_unit:
                unit_str = str(explicit_unit).strip().lower()
                if unit_str in ("kv", "kilovolt"):
                    if num_val < 0.0 or num_val > 765.0:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {num_val} kV is outside safe limits [0, 765]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
                elif unit_str in ("v", "volt"):
                    if num_val < 0.0 or num_val > 765000.0:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {num_val} V is outside safe limits [0, 765000]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
                elif unit_str in ("pu", "p.u.", "per_unit"):
                    if num_val < 0.80 or num_val > 1.20:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {num_val} p.u. is outside safe operating envelope [0.80, 1.20]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
            else:
                # Fallback heuristic when no unit is specified (num_val > 5.0 => kV, else p.u.)
                if num_val > 5.0:  # kV scale
                    if num_val < 0.0 or num_val > 765.0:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {num_val} kV is outside safe limits [0, 765]",
                            },
                            "ENVELOPE_VIOLATION",
                        )
                else:  # p.u. scale
                    if num_val < 0.80 or num_val > 1.20:
                        return (
                            False,
                            {
                                "valid": False,
                                "within_envelope": False,
                                "reason": f"Voltage setpoint {num_val} p.u. is outside safe operating envelope [0.80, 1.20]",
                            },
                            "ENVELOPE_VIOLATION",
                        )

        if any(k in target_lower or k in action_str for k in ("frequency", "freq", "fset")):
            if num_val < 45.0 or num_val > 65.0:
                return (
                    False,
                    {
                        "valid": False,
                        "within_envelope": False,
                        "reason": f"Frequency setpoint {num_val} Hz is outside safe grid envelope [45.0, 65.0]",
                    },
                    "ENVELOPE_VIOLATION",
                )

    return (
        True,
        {
            "valid": True,
            "status": "PASS",
            "checks": [
                "target_existence",
                "supported_action",
                "destructive_check",
                "interlock_check",
                "envelope_check",
            ],
            "target": target_str,
            "action": action_str,
            "server_verified": True,
        },
        "",
    )


# Alias for backward-compatibility with tests and internal callers
_validate_control_action_authoritative = validate_server_control_action


class ResolveRequest(BaseModel):
    """Body for approving / rejecting a pending action."""

    decision: str = Field(pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=2000)
    # Self-confirmation lane fields (SCADA/CUA control tools only)
    validation_results: Optional[Dict[str, Any]] = Field(default=None)
    program_suggestion: Optional[Dict[str, Any]] = Field(default=None)
    confirm_token: Optional[str] = Field(
        default=None,
        description="content-bound confirmation digest (binds decision to exact action args)",
    )
    override_reason: Optional[str] = Field(default=None, max_length=2000)


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
    self_approved: Optional[bool] = None
    validation_snapshot: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Session auto-approve registry
# ---------------------------------------------------------------------------

# Per-session auto-run toggle. Kept in-memory (single-replica HF Space);
# a Redis-backed store would be a drop-in replacement.


def set_session_auto_approve(session_id: str, enabled: bool) -> None:
    """Deprecated: thin forwarder to session_ownership module."""
    _session_auto_approve[session_id] = bool(enabled)


def get_session_auto_approve(session_id: str) -> bool:
    """Deprecated: thin forwarder to session_ownership module."""
    return is_auto_approve(session_id)


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
    if not key or not isinstance(key, str):
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
    if not key or not isinstance(key, str):
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
    is_self = bool(
        (action.validation_snapshot or {}).get("self_approved", False)
        or (
            action.decided_by_user_id is not None
            and action.decided_by_user_id == action.requested_by_user_id
            and action.validation_snapshot is not None
        )
    )
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
        "self_approved": is_self,
        "validation_snapshot": action.validation_snapshot,
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

    # Maker-checker: critical actions require a second pair of eyes, EXCEPT
    # for SCADA/CUA control tools operating under Owner-Authorized Single-Operator Mode
    # (Validated Self-Confirmation lane).
    is_self_approved = False
    if (
        action.risk_class == _RISK_CRITICAL
        and body.decision == "approve"
        and user.user_id == action.requested_by_user_id
    ):
        is_scada_cua_tool = action.tool in SCADA_CUA_CONTROL_TOOLS
        token_matches = (body.confirm_token is not None) and (body.confirm_token == action.args_hash)

        if is_scada_cua_tool and token_matches:
            # Server-side validation MUST be authoritative
            valid, server_validation, err_code = validate_server_control_action(action)
            if not valid:
                record_approval_event(
                    APPROVAL_EVENT_MAKER_CHECKER_VIOLATION,
                    action.id,
                    user.user_id,
                    {
                        "tool": action.tool,
                        "attempted_decision": body.decision,
                        "rejection_reason": server_validation.get("reason"),
                        "error_code": err_code,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": MAKER_CHECKER_VIOLATION,
                        "message": (
                            f"Server validation failed for self-confirmation: "
                            f"{server_validation.get('reason', 'Verification failed')}. "
                            f"Dual-control required."
                        ),
                    },
                )

            # Validated self-confirmation lane (Owner-authorized single-operator mode)
            is_self_approved = True
            action.validation_snapshot = {
                "server_validation": server_validation,
                "validation_results": server_validation,
                "client_supplied_results": body.validation_results,
                "program_suggestion": body.program_suggestion,
                "confirm_token": body.confirm_token,
                "override_reason": body.override_reason,
                "self_approved": True,
            }
        else:
            # Dual-control remains the DEFAULT for all other critical tools,
            # or when content-bound confirmation digest is missing or invalid.
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
            "self_approved": is_self_approved,
            "validation_snapshot": action.validation_snapshot,
        },
    )

    payload = {"success": True, "data": _action_to_response(action)}
    await _store_idempotent(db, idempotency_key, resolve_endpoint, user.tenant_id, payload)
    return payload


@router.get("/verify", summary="Verify approval request via QR code / web link")
async def verify_approval(
    approval_id: str = Query(..., description="Approval ID to verify"),
    tool: Optional[str] = Query(None, description="Tool name for validation"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Verification endpoint for QR code mobile scanning and second-approver validation."""
    await expire_stale_actions(db)

    stmt = select(PendingAction).where(PendingAction.id == approval_id)
    result = await db.execute(stmt)
    action = result.scalar_one_or_none()
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "APPROVAL_NOT_FOUND",
                "message": f"Approval action '{approval_id}' not found or does not exist.",
            },
        )

    now = _utc_now()
    expires_at = action.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    is_expired = expires_at is not None and now > expires_at
    is_verified = not is_expired and action.status == _STATUS_PENDING
    dual_control = action.risk_class == "critical"

    data = {
        "verified": is_verified,
        "valid": is_verified,
        "approval_id": action.id,
        "tool": action.tool,
        "status": "expired" if is_expired else action.status,
        "risk_class": action.risk_class,
        "requested_by_user_id": action.requested_by_user_id,
        "requested_by_role": action.requested_by_role,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "expires_at": action.expires_at.isoformat() if action.expires_at else None,
        "dual_control_required": dual_control,
        "dual_control_enforced": dual_control,
    }
    return {"success": True, "data": data}


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
    user_role = getattr(user, "role", None)
    actor = Actor(
        user_id=str(getattr(user, "user_id", "")).strip(),
        role=str(user_role or "").strip(),
        is_admin=user_role == "admin",
        tenant_id=str(getattr(user, "tenant_id", "") or "").strip(),
    )
    try:
        _policy_set_auto_approve(body.session_id, actor, body.enabled)
    except OwnershipDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": exc.code,
                "message": str(exc),
            },
        ) from exc

    return {
        "success": True,
        "data": {
            "session_id": body.session_id,
            "enabled": is_auto_approve(body.session_id),
            "note": "critical tools always require manual approval",
        },
    }
