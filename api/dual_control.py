"""
Dual-control approval system for critical protection operations.
Provides WebSocket-based real-time approval from a second engineer,
QR code fallback for mobile, and auto-reject after 5-minute timeout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger("api.dual_control")

# In-memory store for pending approvals
# In production this should use Redis, but for HF Space we use memory
_pending_approvals: dict[str, dict[str, Any]] = {}
_websocket_clients: dict[str, list] = {}  # session_id -> [websocket connections]

AUTO_REJECT_SECONDS = 300  # 5 minutes

def create_approval_request(
    action: dict[str, Any],
    operator_id: str,
) -> dict[str, Any]:
    """Create a new dual-control approval request."""
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

    _pending_approvals[request_id] = request
    logger.info(
        "Dual-control request %s: %s by %s (expires in %ds)",
        request_id, action.get("type", "unknown"), operator_id, AUTO_REJECT_SECONDS,
    )

    return request

def approve_request(request_id: str, approver_id: str, secret: Optional[str] = None) -> dict[str, Any]:
    """Approve a dual-control request."""
    request = _pending_approvals.get(request_id)
    if not request:
        return {"success": False, "error": "Approval request not found"}

    if request["status"] != "pending":
        return {"success": False, "error": f"Request is already {request['status']}"}

    if time.time() > request["expires_at"]:
        request["status"] = "expired"
        return {"success": False, "error": "Approval request has expired (5 min timeout)"}

    # If QR secret provided, validate it
    if secret and secret != request["qr_secret"]:
        return {"success": False, "error": "Invalid QR secret"}

    request["status"] = "approved"
    request["approved_by"] = approver_id
    request["approved_at"] = datetime.now(UTC).isoformat()

    logger.info("Dual-control request %s APPROVED by %s", request_id, approver_id)

    # Notify WebSocket clients
    _notify_clients(request_id, request)

    return {"success": True, "request": request}

def reject_request(request_id: str, rejector_id: str, reason: str) -> dict[str, Any]:
    """Reject a dual-control request."""
    request = _pending_approvals.get(request_id)
    if not request:
        return {"success": False, "error": "Approval request not found"}

    if request["status"] != "pending":
        return {"success": False, "error": f"Request is already {request['status']}"}

    request["status"] = "rejected"
    request["rejected_by"] = rejector_id
    request["rejected_reason"] = reason

    logger.info("Dual-control request %s REJECTED by %s: %s", request_id, rejector_id, reason)

    _notify_clients(request_id, request)

    return {"success": True, "request": request}

def get_pending_approvals() -> list[dict[str, Any]]:
    """Get all pending approvals (non-expired)."""
    now = time.time()
    results = []
    expired_ids = []

    for req_id, req in _pending_approvals.items():
        if now > req["expires_at"] and req["status"] == "pending":
            req["status"] = "expired"
            expired_ids.append(req_id)
        if req["status"] == "pending":
            results.append(req)

    return results

def register_websocket(session_id: str, websocket) -> None:
    """Register a WebSocket client for real-time approval updates."""
    if session_id not in _websocket_clients:
        _websocket_clients[session_id] = []
    _websocket_clients[session_id].append(websocket)

def _notify_clients(request_id: str, request: dict) -> None:
    """Notify all WebSocket clients about an approval update."""
    # This is async - in real implementation use asyncio
    pass
