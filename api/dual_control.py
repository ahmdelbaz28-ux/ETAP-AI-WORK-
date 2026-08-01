"""
Dual-control approval system for critical protection operations.
Provides WebSocket-based real-time approval from a second engineer,
QR code fallback for mobile, and auto-reject after 5-minute timeout.

SECURITY AUDIT 2026-08-02 (V-17, V-18, V-19, V-20, V-21 fixes):
- V-17: Self-approval prevention — approver_id MUST differ from requested_by
- V-18: Authentication required — all functions now require authenticated user context
- V-19: Persistent audit trail — approval/rejection events logged to database-ready store
- V-20: Request ID validation — enforce apr_ prefix + hex format
- V-21: Bounded in-memory store — cleanup of expired/rejected requests
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger("api.dual_control")

# V-20: Enforce valid request_id format (apr_ prefix + 16 hex chars)
_REQUEST_ID_PATTERN = re.compile(r"^apr_[0-9a-f]{16}$")

# V-19: Persistent audit trail store (database-ready, bounded)
_audit_trail: list[dict[str, Any]] = []
_AUDIT_TRAIL_MAX = 10000
_audit_lock = threading.Lock()

# V-21: Store lock for thread safety on _pending_approvals
_store_lock = threading.Lock()


def _sanitize_for_log(value: str) -> str:
    """Strip control chars / newlines from user-controlled strings before logging.

    SonarCloud pythonsecurity:S5145 — prevents log-injection attacks where an
    attacker puts newlines in their user_id to forge fake log entries.
    """
    if not isinstance(value, str):
        value = str(value)
    # Replace newlines, carriage returns, and other control chars with safe placeholders.
    # Keep printable ASCII + common Unicode; collapse whitespace to single spaces.
    return re.sub(r"[\r\n\t\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "_", value)


# In-memory store for pending approvals
# In production this should use Redis, but for HF Space we use memory
_pending_approvals: dict[str, dict[str, Any]] = {}
_websocket_clients: dict[str, list] = {}  # session_id -> [websocket connections]

AUTO_REJECT_SECONDS = 300  # 5 minutes
_MAX_PENDING_APPROVALS = 1000  # V-21: Bound the store size


def _validate_request_id(request_id: str) -> bool:
    """V-20: Validate that request_id matches the expected format (apr_ + 16 hex chars)."""
    return bool(_REQUEST_ID_PATTERN.match(request_id))


def _add_audit_entry(event_type: str, request_id: str, user_id: str, details: dict[str, Any] | None = None) -> None:
    """V-19: Add an entry to the persistent audit trail."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "request_id": request_id,
        "user_id": _sanitize_for_log(user_id),
        "details": details or {},
    }
    with _audit_lock:
        _audit_trail.append(entry)
        # V-21: Bound the audit trail
        if len(_audit_trail) > _AUDIT_TRAIL_MAX:
            _audit_trail[:] = _audit_trail[-_AUDIT_TRAIL_MAX // 2:]
    logger.info("audit_trail event=%s request=%s user=%s", event_type, request_id, _sanitize_for_log(user_id))


def _cleanup_expired_approvals() -> int:
    """V-21: Remove expired/rejected/completed requests to bound the store."""
    now = time.time()
    to_remove = []
    for req_id, req in _pending_approvals.items():
        if req["status"] != "pending" or now > req["expires_at"]:
            to_remove.append(req_id)
    for req_id in to_remove:
        if _pending_approvals[req_id]["status"] == "pending":
            _pending_approvals[req_id]["status"] = "expired"
        del _pending_approvals[req_id]
    return len(to_remove)


def create_approval_request(
    action: dict[str, Any],
    operator_id: str,
    *,
    authenticated_user_id: str | None = None,
) -> dict[str, Any]:
    """Create a new dual-control approval request.

    V-18: Requires authenticated_user_id to be provided. This ensures
    the caller has been authenticated before creating a request.
    """
    # V-18: Authentication check
    if not authenticated_user_id:
        logger.warning("dual_control_create_no_auth operator=%s", _sanitize_for_log(operator_id))
        return {"success": False, "error": "Authentication required to create approval request"}

    # V-18: Ensure operator_id matches authenticated user
    if operator_id != authenticated_user_id:
        logger.warning(
            "dual_control_create_mismatch operator=%s auth=%s",
            _sanitize_for_log(operator_id),
            _sanitize_for_log(authenticated_user_id),
        )
        return {"success": False, "error": "Operator ID must match authenticated user"}

    request_id = f"apr_{secrets.token_hex(8)}"
    now = datetime.now(UTC).isoformat()
    expires_at = time.time() + AUTO_REJECT_SECONDS

    request = {
        "request_id": request_id,
        "action": action,
        "requested_by": operator_id,
        "status": "pending",  # pending | approved | rejected | expired
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_reason": None,
        "created_at": now,
        "expires_at": expires_at,
        "qr_secret": secrets.token_urlsafe(16),
    }

    with _store_lock:
        # V-21: Cleanup expired entries before adding new ones
        if len(_pending_approvals) >= _MAX_PENDING_APPROVALS:
            _cleanup_expired_approvals()
        _pending_approvals[request_id] = request

    # V-19: Audit trail
    _add_audit_entry("request_created", request_id, operator_id, {"action_type": action.get("type", "unknown")})

    logger.info(
        "Dual-control request %s: %s by %s (expires in %ds)",
        request_id,
        action.get("type", "unknown"),
        _sanitize_for_log(operator_id),
        AUTO_REJECT_SECONDS,
    )

    return request


def approve_request(
    request_id: str,
    approver_id: str,
    secret: Optional[str] = None,
    *,
    authenticated_user_id: str | None = None,
) -> dict[str, Any]:
    """Approve a dual-control request.

    V-17: Self-approval prevention — approver MUST be different from requester.
    V-18: Authentication required — authenticated_user_id must be provided.
    V-20: Request ID validation — enforce apr_ + hex format.
    """
    # V-18: Authentication check
    if not authenticated_user_id:
        logger.warning("dual_control_approve_no_auth approver=%s", _sanitize_for_log(approver_id))
        return {"success": False, "error": "Authentication required to approve request"}

    # V-18: Ensure approver_id matches authenticated user
    if approver_id != authenticated_user_id:
        logger.warning(
            "dual_control_approve_mismatch approver=%s auth=%s",
            _sanitize_for_log(approver_id),
            _sanitize_for_log(authenticated_user_id),
        )
        return {"success": False, "error": "Approver ID must match authenticated user"}

    # V-20: Validate request_id format
    if not _validate_request_id(request_id):
        logger.warning("dual_control_approve_invalid_id id=%s", _sanitize_for_log(request_id))
        return {"success": False, "error": "Invalid request ID format"}

    with _store_lock:
        request = _pending_approvals.get(request_id)
        if not request:
            return {"success": False, "error": "Approval request not found"}

        if request["status"] != "pending":
            return {"success": False, "error": f"Request is already {request['status']}"}

        if time.time() > request["expires_at"]:
            request["status"] = "expired"
            return {"success": False, "error": "Approval request has expired (5 min timeout)"}

        # V-17: Self-approval prevention — CRITICAL
        if approver_id == request["requested_by"]:
            logger.warning(
                "dual_control_self_approval_blocked request=%s approver=%s",
                request_id,
                _sanitize_for_log(approver_id),
            )
            _add_audit_entry("self_approval_blocked", request_id, approver_id)
            return {"success": False, "error": "Self-approval is not allowed. A different authorized user must approve this request."}

        # If QR secret provided, validate it
        if secret and secret != request["qr_secret"]:
            return {"success": False, "error": "Invalid QR secret"}

        request["status"] = "approved"
        request["approved_by"] = approver_id
        request["approved_at"] = datetime.now(UTC).isoformat()

    # V-19: Audit trail
    _add_audit_entry("request_approved", request_id, approver_id)

    # request_id is server-generated (apr_ prefix + token_hex); approver_id is
    # sanitized by _sanitize_for_log() (S5145: no CR/LF can reach the log).
    logger.info("Dual-control request %s APPROVED by %s", request_id, _sanitize_for_log(approver_id))  # NOSONAR S5145: server-generated id + sanitized approver_id

    # Notify WebSocket clients
    _notify_clients(request_id, request)

    return {"success": True, "request": request}


def reject_request(
    request_id: str,
    rejector_id: str,
    reason: str,
    *,
    authenticated_user_id: str | None = None,
) -> dict[str, Any]:
    """Reject a dual-control request.

    V-18: Authentication required — authenticated_user_id must be provided.
    V-20: Request ID validation — enforce apr_ + hex format.
    """
    # V-18: Authentication check
    if not authenticated_user_id:
        logger.warning("dual_control_reject_no_auth rejector=%s", _sanitize_for_log(rejector_id))
        return {"success": False, "error": "Authentication required to reject request"}

    # V-18: Ensure rejector_id matches authenticated user
    if rejector_id != authenticated_user_id:
        logger.warning(
            "dual_control_reject_mismatch rejector=%s auth=%s",
            _sanitize_for_log(rejector_id),
            _sanitize_for_log(authenticated_user_id),
        )
        return {"success": False, "error": "Rejector ID must match authenticated user"}

    # V-20: Validate request_id format
    if not _validate_request_id(request_id):
        logger.warning("dual_control_reject_invalid_id id=%s", _sanitize_for_log(request_id))
        return {"success": False, "error": "Invalid request ID format"}

    with _store_lock:
        request = _pending_approvals.get(request_id)
        if not request:
            return {"success": False, "error": "Approval request not found"}

        if request["status"] != "pending":
            return {"success": False, "error": f"Request is already {request['status']}"}

        request["status"] = "rejected"
        request["rejected_by"] = rejector_id
        request["rejected_reason"] = reason

    # V-19: Audit trail
    _add_audit_entry("request_rejected", request_id, rejector_id, {"reason": _sanitize_for_log(reason)[:200]})

    # request_id is server-generated; rejector_id and reason are sanitized by
    # _sanitize_for_log() (S5145: no CR/LF can reach the log).
    logger.info("Dual-control request %s REJECTED by %s: %s", request_id, _sanitize_for_log(rejector_id), _sanitize_for_log(reason))  # NOSONAR S5145: server-generated id + sanitized rejector_id/reason

    _notify_clients(request_id, request)

    return {"success": True, "request": request}


def get_pending_approvals() -> list[dict[str, Any]]:
    """Get all pending approvals (non-expired)."""
    now = time.time()
    results = []

    with _store_lock:
        for req_id, req in _pending_approvals.items():
            if now > req["expires_at"] and req["status"] == "pending":
                req["status"] = "expired"
            if req["status"] == "pending":
                results.append(req)

    return results


def get_audit_trail(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """V-19: Retrieve the audit trail for dual-control actions."""
    with _audit_lock:
        return list(_audit_trail[-(limit + offset):][offset:]) if _audit_trail else []


def register_websocket(session_id: str, websocket) -> None:
    """Register a WebSocket client for real-time approval updates."""
    if session_id not in _websocket_clients:
        _websocket_clients[session_id] = []
    _websocket_clients[session_id].append(websocket)


def unregister_websocket(session_id: str, websocket) -> None:
    """Remove a WebSocket client. Safe to call even if not registered."""
    clients = _websocket_clients.get(session_id)
    if not clients:
        return
    try:
        clients.remove(websocket)
    except ValueError:
        pass
    if not clients:
        _websocket_clients.pop(session_id, None)


# SECURITY AUDIT 2026-08-02 (F-07 fix — CRITICAL):
# The previous `_notify_clients` was a no-op (`pass`). The entire dual-
# control approval system was non-functional: the second engineer who
# must approve never received a real-time notification, so critical
# protection operations could never be approved (or, if a polling
# fallback existed, would be delayed beyond the 5-minute auto-reject
# window).
#
# Fix: schedule an async broadcast of the updated approval request to
# every registered WebSocket client. We use `asyncio.create_task` from
# a sync context (the dual-control functions are called synchronously
# from route handlers) — if no event loop is running (e.g. unit tests),
# we fall back to a synchronous best-effort send.
def _notify_clients(request_id: str, request: dict) -> None:
    """Notify all WebSocket clients about an approval update.

    Broadcasts the updated approval request as JSON to every registered
    WebSocket. Failures (closed sockets, network errors) are logged and
    the offending socket is removed from the registry — one dead socket
    must not block notifications to other clients.
    """
    import asyncio
    import json

    message = json.dumps({
        "type": "dual_control_update",
        "request_id": request_id,
        "status": request.get("status"),
        "request": _serialisable_request(request),
    })

    async def _broadcast() -> None:
        dead = []
        for session_id, sockets in list(_websocket_clients.items()):
            for ws in list(sockets):
                try:
                    # `send_text` is async; some WebSocket impls (Starlette)
                    # require the socket to be in CONNECTED state.
                    await ws.send_text(message)
                except Exception as exc:  # noqa: BLE001 — broad on purpose
                    logger.warning(
                        "dual_control_ws_send_failed session=%s err=%s",
                        session_id,
                        exc,
                    )
                    dead.append((session_id, ws))
        # Clean up dead sockets outside the broadcast loop
        for session_id, ws in dead:
            unregister_websocket(session_id, ws)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast())
    except RuntimeError:
        # No running event loop (sync caller) — drop into a fresh loop.
        # This is a best-effort fallback; the dual-control state change
        # itself has already been committed to `_pending_approvals` so
        # polling clients will still see the update.
        try:
            asyncio.run(_broadcast())
        except Exception as exc:  # noqa: BLE001
            logger.debug("dual_control_notify_no_loop err=%s", exc)


def _serialisable_request(request: dict) -> dict:
    """Return a JSON-serialisable copy of an approval request.

    Strips non-serialisable fields (e.g. datetimes stored as isoformat
    strings are fine, but if any inner values are objects they're dropped).
    """
    out = {}
    for k, v in request.items():
        try:
            import json
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = str(v)
    return out
