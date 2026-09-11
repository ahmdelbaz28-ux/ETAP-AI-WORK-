"""api/session_ownership.py — Unified authority for session ownership and auto-approval.

Provides a single in-process seam for managing session ownership and auto-approval toggles.
Enforces first-claim invariants, role gates, admin overrides, and fail-closed security.
"""

import threading
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

ALLOWED_ROLES: Set[str] = {"admin", "lead_engineer", "senior_engineer", "engineer"}
DISALLOWED_ROLES: Set[str] = {"viewer", "guest", "readonly"}


@dataclass(frozen=True)
class Actor:
    """Representation of an acting principal in the session ownership domain.

    Attributes:
        user_id: Unique identifier for the user.
        role: Security role assigned to the user.
        is_admin: Whether the user possesses administrative privileges.
        tenant_id: Optional tenant identifier for multi-tenant isolation.
    """

    user_id: str
    role: str
    is_admin: bool
    tenant_id: str = ""


class OwnershipDenied(Exception):
    """Raised when session ownership verification or mutation is rejected."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# Redis adapter note: Currently implemented in-process for single-replica deployment.
# A Redis-backed store can be introduced later behind this exact same Interface
# at this internal seam without altering any caller contracts or API signatures.

_lock = threading.Lock()
_owners: Dict[Tuple[str, str], str] = {}
_flags: Dict[str, bool] = {}


def _check_role(role: str) -> None:
    clean_role = str(role or "").strip()
    if clean_role in DISALLOWED_ROLES or (clean_role and clean_role not in ALLOWED_ROLES):
        raise OwnershipDenied(
            "INSUFFICIENT_ROLE",
            "Only engineering and admin roles can toggle session auto-approval.",
        )


def set_auto_approve(session_id: str, actor: Actor, enabled: bool) -> bool:
    """Enable or disable auto-approval for a session.

    Args:
        session_id: Session identifier.
        actor: Principal requesting the mutation.
        enabled: Target toggle state.

    Returns:
        True if the toggle was successfully set.

    Raises:
        OwnershipDenied: If principal is invalid, role is insufficient, or caller
            is not the session owner.
    """
    if not session_id or not str(session_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "Session ID cannot be empty.")
    if not actor.user_id or not str(actor.user_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "User ID cannot be empty.")

    _check_role(actor.role)

    sid = str(session_id).strip()
    uid = str(actor.user_id).strip()
    tid = str(getattr(actor, "tenant_id", "") or "").strip()
    key = (tid, sid)

    if actor.is_admin:
        # Admin bypasses ownership and never writes ownership
        with _lock:
            _flags[sid] = bool(enabled)
        return True

    with _lock:
        existing = _owners.get(key)
        if existing is None and not tid:
            for (_, s), owner in _owners.items():
                if s == sid:
                    existing = owner
                    break

        if existing is None:
            # First claim wins
            _owners[key] = uid
        elif existing != uid:
            raise OwnershipDenied(
                "FORBIDDEN",
                "Cannot modify another user's session auto-approval.",
            )

        _flags[sid] = bool(enabled)
        return True


def is_auto_approve(session_id: str) -> bool:
    """Hot read for session auto-approval toggle. Never claims, never raises.

    Args:
        session_id: Session identifier.

    Returns:
        True if auto-approval is enabled for the session, False otherwise.
    """
    try:
        if not session_id or not isinstance(session_id, str):
            return False
        return bool(_flags.get(session_id.strip(), False))
    except Exception:
        return False


def admin_set(session_id: str, actor: Actor, enabled: bool, *, reason: str) -> bool:
    """Admin override to set session auto-approval with an audit reason.

    Args:
        session_id: Session identifier.
        actor: Admin principal requesting the override.
        enabled: Target toggle state.
        reason: Mandatory justification for the administrative override.

    Returns:
        True if the override was successfully applied.

    Raises:
        OwnershipDenied: If actor lacks admin role, principals are empty, or reason is empty.
    """
    if not actor.is_admin or str(actor.role).strip() != "admin":
        raise OwnershipDenied(
            "INSUFFICIENT_ROLE",
            "Admin privileges required for admin_set.",
        )
    if not reason or not str(reason).strip():
        raise OwnershipDenied(
            "INVALID_PRINCIPAL",
            "Admin override requires a non-empty reason.",
        )
    if not session_id or not str(session_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "Session ID cannot be empty.")
    if not actor.user_id or not str(actor.user_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "User ID cannot be empty.")

    sid = str(session_id).strip()
    with _lock:
        _flags[sid] = bool(enabled)
    return True


def get_owner(session_id: str, tenant_id: str = "") -> Optional[str]:
    """Retrieve the owner user_id for session_id, or None if unclaimed."""
    if not session_id or not str(session_id).strip():
        return None
    sid = str(session_id).strip()
    tid = str(tenant_id or "").strip()
    with _lock:
        if tid and (tid, sid) in _owners:
            return _owners[(tid, sid)]
        if ("", sid) in _owners:
            return _owners[("", sid)]
        for (_, s), owner in _owners.items():
            if s == sid:
                return owner
        return None


def verify_ownership(
    session_id: str,
    user_id: str,
    is_admin: bool = False,
    tenant_id: str = "",
) -> bool:
    """Verify or claim initial ownership of session_id by user_id.

    Raises OwnershipDenied on conflict, empty principals, or forbidden access.
    """
    if not session_id or not str(session_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "Session ID cannot be empty.")
    if not user_id or not str(user_id).strip():
        raise OwnershipDenied("INVALID_PRINCIPAL", "User ID cannot be empty.")

    if is_admin:
        return True

    sid = str(session_id).strip()
    uid = str(user_id).strip()
    tid = str(tenant_id or "").strip()
    key = (tid, sid)

    with _lock:
        existing = _owners.get(key)
        if existing is None and not tid:
            for (_, s), owner in _owners.items():
                if s == sid:
                    existing = owner
                    break

        if existing is None:
            _owners[key] = uid
            return True

        if existing != uid:
            raise OwnershipDenied("FORBIDDEN", "Cannot access another user's session.")

        return True


def reset_session_ownership() -> None:
    """Clear all session ownership and auto-approve registries (for testing)."""
    with _lock:
        _owners.clear()
        _flags.clear()
