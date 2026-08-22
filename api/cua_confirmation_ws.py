"""
api/cua_confirmation_ws.py — WebSocket endpoint for CUA dual confirmation

Provides real-time, two-human confirmation for life-safety-critical CUA
actions (protection setting changes, breaker operations, etc.).

PROTOCOL:
    1. CUA Loop encounters a dual-confirmation-required action
    2. on_confirmation_request callback → calls ConfirmationBroker.request()
    3. Broker broadcasts the request to all connected WebSocket clients
    4. Two different humans (tracked by session_id) must reply "CONFIRM"
    5. Broker returns True to the CUA Loop → action proceeds
    6. If timeout (default 120s) or anyone replies "CANCEL" → returns False

USAGE (server-side, in FastAPI app):
    from api.cua_confirmation_ws import confirmation_broker, cua_confirmation_ws

    @app.websocket("/ws/cua/confirmation")
    async def cua_confirmation_endpoint(websocket: WebSocket):
        await cua_confirmation_ws(websocket)

USAGE (CUA Loop side):
    from api.cua_confirmation_ws import confirmation_broker

    def my_confirmation_callback(action):
        return confirmation_broker.request(
            action=action,
            timeout_seconds=120,
            require_two_humans=True,
        )

    result = agent.execute_cua_loop(
        question="...",
        on_confirmation_request=my_confirmation_callback,
    )

References:
    - agents/life_safety.py (DUAL_CONFIRMATION_PATTERNS)
    - agents/cua_executor.py (on_confirmation_request callback)
"""
# ─── Module status ────────────────────────────────────────────────────────
# INTERNAL — this module is NOT registered as an ``APIRouter`` in routes.py.
# It is consumed indirectly by middleware, websocket handlers, CLI tools, or
# other services. Do not add ``app.include_router`` for this module without a
# corresponding audit of the consumers below.

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("api.cua_confirmation_ws")


# ─── Authentication helper ─────────────────────────────────────────────────
#
# CONDITION E (Phase-2 P0 backend bug fix — see worklog Task ID 5):
# The /ws/cua/confirmation endpoint was registered in TWO places
# (api/routes.py:457 and hf-space/app.py:1218) with DIVERGENT auth logic:
#   - routes.py: header-only, hard-fail
#   - hf-space/app.py: header OR query-param, BUT silently skipped auth
#     entirely when ENGINEERING_SERVICE_API_KEY was unset (a security
#     weakness on a life-safety endpoint).
#
# This shared helper eliminates the duplication, fixes the silent-skip
# bug (fail-closed when env var is unset), and ensures both deployment
# apps (engineering-service FastAPI app and HF Space FastAPI app) apply
# IDENTICAL auth to /ws/cua/confirmation.


# WebSocket close codes (RFC 6455 §7.4.1)
_WS_CODE_POLICY_VIOLATION = 1008
_WS_CODE_INTERNAL_ERROR = 1011


async def authenticate_cua_confirmation_ws(websocket: WebSocket) -> bool:
    """Authenticate an inbound /ws/cua/confirmation WebSocket connection.

    Returns ``True`` if the caller is authenticated and the connection
    should proceed; returns ``False`` (after closing the socket) if not.

    Security properties
    -------------------
    * Reads the expected key from the ``ENGINEERING_SERVICE_API_KEY``
      environment variable.
    * Accepts the key via either the ``x-api-key`` header OR the
      ``?token=`` query parameter. The query-param fallback exists
      because browser WebSocket clients cannot set arbitrary headers
      on the upgrade request — mobile / web clients rely on the
      query-param form.
    * Uses :func:`hmac.compare_digest` for constant-time comparison
      to prevent timing-side-channel attacks.
    * **Fail-closed**: if ``ENGINEERING_SERVICE_API_KEY`` is NOT set,
      the connection is closed with code 1011 (Internal Error).
      Life-safety endpoints must NEVER silently allow unauthenticated
      access. (This fixes the silent-skip bug that previously existed
      in hf-space/app.py.)
    * Closes with code 1008 (Policy Violation) on missing/incorrect
      key.
    """
    expected_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
    if not expected_key:
        # Fail-closed: life-safety endpoint must never be open.
        logger.error(
            "cua_confirmation_ws rejected: ENGINEERING_SERVICE_API_KEY not set "
            "(life-safety endpoint cannot operate without auth)"
        )
        await websocket.close(
            code=_WS_CODE_INTERNAL_ERROR,
            reason="Server misconfiguration: ENGINEERING_SERVICE_API_KEY not set",
        )
        return False

    provided_key = websocket.headers.get("x-api-key") or websocket.query_params.get("token", "")
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        await websocket.close(
            code=_WS_CODE_POLICY_VIOLATION,
            reason="Invalid or missing API key",
        )
        return False

    return True


# ─── Data classes ──────────────────────────────────────────────────────────


@dataclass
class ConfirmationRequest:
    """A pending confirmation request from the CUA Loop."""

    request_id: str
    action_type: str
    action_target: str
    action_x: int | None = None
    action_y: int | None = None
    action_text: str | None = None
    action_keys: list = field(default_factory=list)
    requires_dual_confirmation: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Tracking who has confirmed
    confirmations: list = field(default_factory=list)  # list of session_ids
    rejections: list = field(default_factory=list)
    # Internal
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _result: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the confirmation request to a JSON-encodable dict."""
        return {
            "request_id": self.request_id,
            "action": {
                "type": self.action_type,
                "target": self.action_target,
                "x": self.action_x,
                "y": self.action_y,
                "text": self.action_text,
                "keys": self.action_keys,
            },
            "requires_dual_confirmation": self.requires_dual_confirmation,
            "timestamp": self.timestamp,
            "confirmations_count": len(self.confirmations),
            "rejections_count": len(self.rejections),
            "confirmations": self.confirmations,
            "rejections": self.rejections,
        }


# ─── Confirmation Broker — singleton ───────────────────────────────────────


class ConfirmationBroker:
    """Singleton broker that manages pending confirmation requests.

    The CUA Loop calls request() (synchronous, blocks until resolved).
    WebSocket clients call confirm() / reject() (async).
    """

    def __init__(self) -> None:
        self._pending: dict[str, ConfirmationRequest] = {}
        self._connected_clients: set[WebSocket] = set()
        self._async_lock: asyncio.Lock | None = None
        # Default: 2 humans required for dual-confirmation actions
        self.required_confirmations = 2

    @property
    def _lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    # ─── WebSocket client management ──────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it for confirmation events."""
        await websocket.accept()
        self._connected_clients.add(websocket)
        logger.info("Confirmation WS client connected (total: %d)", len(self._connected_clients))

        # Send any pending requests to the new client — best effort, never
        # fail the connect() because a single send failed.
        async with self._lock:
            for req in self._pending.values():
                with contextlib.suppress(Exception):
                    await websocket.send_json({"type": "pending_request", "data": req.to_dict()})

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active set."""
        self._connected_clients.discard(websocket)
        logger.info("Confirmation WS client disconnected (total: %d)", len(self._connected_clients))

    # ─── Broadcast a request to all connected clients ─────────────────────

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected WebSocket clients."""
        dead: list[WebSocket] = []
        for ws in self._connected_clients:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self._connected_clients.discard(ws)

    # ─── CUA Loop side: request a confirmation ────────────────────────────

    def request(
        self,
        action,  # CUAAction
        timeout_seconds: int = 120,
        require_two_humans: bool = True,
    ) -> bool:
        """Block until the action is confirmed or rejected/timed out.

        Args:
            action: the CUAAction requiring confirmation
            timeout_seconds: max time to wait (default 120s)
            require_two_humans: if True, need 2 distinct session_ids to confirm

        Returns:
            True if confirmed (by 2 humans if required), False otherwise.
        """
        request_id = uuid.uuid4().hex[:12]
        req = ConfirmationRequest(
            request_id=request_id,
            action_type=action.type,
            action_target=action.target or "unknown",
            action_x=action.x,
            action_y=action.y,
            action_text=action.text,
            action_keys=action.keys,
            requires_dual_confirmation=require_two_humans,
        )
        self._pending[request_id] = req

        # Broadcast to all connected clients (async, but we're sync here)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._broadcast({"type": "confirmation_request", "data": req.to_dict()}),
            )
        except RuntimeError:
            # No event loop running (sync context) — use asyncio.run for
            # broadcast. Best effort: never fail the request_confirmation
            # call because the broadcast failed (the request is still logged).
            with contextlib.suppress(Exception):
                asyncio.run(
                    self._broadcast({"type": "confirmation_request", "data": req.to_dict()}),
                )

        logger.info(
            "Confirmation request %s: %s on %s (need %d humans)",
            request_id,
            action.type,
            action.target,
            self.required_confirmations if require_two_humans else 1,
        )

        # Wait for the event to be set (by confirm() or reject())
        try:
            # Run the async wait in a sync context
            try:
                loop = asyncio.get_running_loop()
                # A running loop exists — but request() is sync.
                # This is a design limitation: the CUA executors are sync.
                # Workaround: use a thread to wait for the event.
                import threading

                result_holder: dict[str, bool | None] = {"result": None}

                def wait_in_thread():
                    try:
                        asyncio.run(
                            asyncio.wait_for(req._event.wait(), timeout=timeout_seconds),
                        )
                        result_holder["result"] = req._result
                    except TimeoutError:
                        result_holder["result"] = False
                    except Exception:  # noqa: BLE001
                        result_holder["result"] = False

                t = threading.Thread(target=wait_in_thread, daemon=True)
                t.start()
                t.join(timeout=timeout_seconds + 5)
                result = result_holder["result"]
            except RuntimeError:
                # No running loop — safe to use asyncio.run() directly.
                asyncio.run(asyncio.wait_for(req._event.wait(), timeout=timeout_seconds))
                result = req._result
        except TimeoutError:
            result = False
            logger.warning(
                "Confirmation request %s TIMED OUT after %ds",
                request_id,
                timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            result = False
            logger.exception("Confirmation request %s failed: %s", request_id, exc)

        # Clean up
        self._pending.pop(request_id, None)
        return bool(result)

    # ─── WebSocket client side: confirm / reject ──────────────────────────

    async def confirm(self, request_id: str, session_id: str) -> dict[str, Any]:
        """A WebSocket client confirms a request.

        Returns the updated request state. If enough confirmations are
        received, the request is resolved and the CUA Loop unblocks.
        """
        async with self._lock:
            req = self._pending.get(request_id)
            if not req:
                return {"error": "request_not_found", "request_id": request_id}

            if session_id in req.confirmations:
                return {
                    "error": "already_confirmed",
                    "message": "This session already confirmed",
                    "data": req.to_dict(),
                }

            req.confirmations.append(session_id)

            required = self.required_confirmations if req.requires_dual_confirmation else 1

            if len(req.confirmations) >= required:
                req._result = True
                req._event.set()
                # Broadcast resolution
                await self._broadcast(
                    {"type": "confirmation_resolved", "data": req.to_dict(), "approved": True},
                )
                logger.info(
                    "Confirmation %s APPROVED by %d humans",
                    request_id,
                    len(req.confirmations),
                )

            return {"success": True, "data": req.to_dict()}

    async def reject(self, request_id: str, session_id: str, reason: str = "") -> dict[str, Any]:
        """A WebSocket client rejects a request. Immediately fails the request."""
        async with self._lock:
            req = self._pending.get(request_id)
            if not req:
                return {"error": "request_not_found", "request_id": request_id}

            req.rejections.append(session_id)
            req._result = False
            req._event.set()
            # Broadcast rejection
            await self._broadcast(
                {
                    "type": "confirmation_resolved",
                    "data": req.to_dict(),
                    "approved": False,
                    "rejected_by": session_id,
                    "reason": reason,
                },
            )
            logger.warning("Confirmation %s REJECTED by %s: %s", request_id, session_id, reason)
            return {"success": True, "data": req.to_dict()}

    # ─── Health / status ─────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Return a health snapshot for the CUA confirmation WebSocket manager."""
        return {
            "connected_clients": len(self._connected_clients),
            "pending_requests": len(self._pending),
            "required_confirmations": self.required_confirmations,
            "pending_request_ids": list(self._pending.keys()),
        }


# ─── Singleton broker ──────────────────────────────────────────────────────

confirmation_broker = ConfirmationBroker()


# ─── WebSocket endpoint handler ────────────────────────────────────────────


_DEFAULT_DEV_ORIGINS = {
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
    "http://testserver",
    "https://testserver",
}


def _is_local_dev_origin(origin: str) -> bool:
    """Check if an origin is a standard local development/testing origin."""
    if origin in _DEFAULT_DEV_ORIGINS:
        return True
    from urllib.parse import urlparse

    try:
        parsed = urlparse(origin)
        if parsed.scheme in ("http", "https") and parsed.hostname in (
            "localhost",
            "127.0.0.1",
            "testserver",
        ):
            return True
    except Exception:
        pass
    return False


def _validate_origin(websocket: WebSocket) -> bool:
    """Validate WebSocket Origin header against configured CORS origins.

    Security properties:
    - Exact match only against configured ENGINEERING_SERVICE_CORS_ORIGINS.
    - Wildcard '*' is NEVER treated as a trusted origin.
    - Fail-closed: in production/staging, missing Origin or empty allowlist rejects.
    - Development/test: permits documented local development/testing origins
      (localhost, 127.0.0.1, testserver), but arbitrary third-party origins
      remain rejected.
    """
    from api.environment import is_dev_environment, is_production_environment

    origin = websocket.headers.get("origin")
    allowed_origins_env = os.environ.get("ENGINEERING_SERVICE_CORS_ORIGINS", "").strip()
    # Exact matches only; discard any wildcard '*' or whitespace-only entries
    allowed = [o.strip() for o in allowed_origins_env.split(",") if o.strip() and o.strip() != "*"]

    if origin:
        if allowed:
            if origin in allowed:
                return True
            logger.warning("CUA confirmation WS origin rejected: %s not in allowed origins", origin)
            return False

        # No explicit allowlist configured
        if is_production_environment():
            logger.warning(
                "CUA confirmation WS origin rejected: origin %s provided but CORS origins not configured in production",
                origin,
            )
            return False

        # In dev/test without explicit allowlist: permit ONLY documented local dev/test origins
        if is_dev_environment() and _is_local_dev_origin(origin):
            return True

        logger.warning(
            "CUA confirmation WS origin rejected in dev: untrusted non-local origin %s", origin
        )
        return False

    # Missing Origin header
    if is_production_environment():
        logger.warning(
            "CUA confirmation WS origin rejected: missing Origin header in production environment"
        )
        return False

    # In dev/test, permit missing Origin for non-browser/test clients
    return bool(is_dev_environment())


async def cua_confirmation_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint handler for /ws/cua/confirmation.

    SECURITY (CR-NEW-02 & RSK-02):
    1. Origin validation: reject untrusted browser origins before acceptance (code 1008)
    2. Authentication: requires valid JWT in the 'token' query param or Authorization header
    3. Session ID: derived strictly from the JWT user_id (user:{user_id}), NOT from client
    4. Each confirmation is tied to a real authenticated user (two-person rule)

    Message protocol (JSON):

      Client → Server:
        {"action": "confirm", "request_id": "..."}
        {"action": "reject", "request_id": "...", "reason": "..."}

      Server → Client:
        {"type": "confirmation_request", "data": {...}}
        {"type": "confirmation_resolved", "data": {...}, "approved": true/false}
        {"type": "pending_request", "data": {...}}  (on connect)
        {"type": "error", "message": "..."}
    """
    # SECURITY (RSK-02): Origin validation first (prevent CSWSH)
    if not _validate_origin(websocket):
        await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Origin not allowed")
        return

    # SECURITY: Authentication required
    import jwt as _jwt

    from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

    # Extract token from query param or Authorization header
    token = websocket.query_params.get("token", "")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Authentication required")
        return

    # Validate JWT
    try:
        payload = _jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid token type")
            return
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid token payload")
            return
        # SECURITY: Validate user_id format before deriving session_id.
        # A non-alphanumeric (attacker-controlled) sub could be spoofed to
        # collide with or impersonate another user and bypass the
        # dual-confirmation requirement.
        if not isinstance(user_id, str) or not user_id.isalnum():
            logger.error("Invalid user_id in JWT: %r", user_id)
            await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid user_id")
            return
    except _jwt.PyJWTError:
        await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    await confirmation_broker.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid JSON"})
                continue

            action = data.get("action")
            request_id = data.get("request_id", "")
            session_id = f"user:{user_id}"

            if action == "confirm":
                result = await confirmation_broker.confirm(request_id, session_id)
                await websocket.send_json({"type": "confirm_result", "data": result})
            elif action == "reject":
                reason = data.get("reason", "")
                result = await confirmation_broker.reject(request_id, session_id, reason)
                await websocket.send_json({"type": "reject_result", "data": result})
            else:
                await websocket.send_json({"type": "error", "message": f"unknown action: {action}"})

    except WebSocketDisconnect:
        confirmation_broker.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Confirmation WS error: %s", exc)
        confirmation_broker.disconnect(websocket)


__all__ = [
    "ConfirmationBroker",
    "ConfirmationRequest",
    "authenticate_cua_confirmation_ws",
    "confirmation_broker",
    "cua_confirmation_ws",
]
