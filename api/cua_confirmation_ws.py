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

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("api.cua_confirmation_ws")


# ─── Data classes ──────────────────────────────────────────────────────────


@dataclass
class ConfirmationRequest:
    """A pending confirmation request from the CUA Loop."""

    request_id: str
    action_type: str
    action_target: str
    action_x: Optional[int] = None
    action_y: Optional[int] = None
    action_text: Optional[str] = None
    action_keys: list = field(default_factory=list)
    requires_dual_confirmation: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Tracking who has confirmed
    confirmations: list = field(default_factory=list)  # list of session_ids
    rejections: list = field(default_factory=list)
    # Internal
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _result: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
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
        self._pending: Dict[str, ConfirmationRequest] = {}
        self._connected_clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        # Default: 2 humans required for dual-confirmation actions
        self.required_confirmations = 2

    # ─── WebSocket client management ──────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connected_clients.add(websocket)
        logger.info("Confirmation WS client connected (total: %d)", len(self._connected_clients))

        # Send any pending requests to the new client
        async with self._lock:
            for req in self._pending.values():
                try:
                    await websocket.send_json({"type": "pending_request", "data": req.to_dict()})
                except Exception:  # noqa: BLE001
                    pass

    def disconnect(self, websocket: WebSocket) -> None:
        self._connected_clients.discard(websocket)
        logger.info("Confirmation WS client disconnected (total: %d)", len(self._connected_clients))

    # ─── Broadcast a request to all connected clients ─────────────────────

    async def _broadcast(self, message: Dict[str, Any]) -> None:
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
            loop = asyncio.get_event_loop()
            loop.create_task(
                self._broadcast({"type": "confirmation_request", "data": req.to_dict()})
            )
        except RuntimeError:
            # No event loop running (sync context) — use asyncio.run for broadcast
            try:
                asyncio.run(
                    self._broadcast({"type": "confirmation_request", "data": req.to_dict()})
                )
            except Exception:  # noqa: BLE001
                pass

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
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context — but request() is sync.
                    # This is a design limitation: the CUA executors are sync.
                    # Workaround: use a thread to wait for the event.
                    import threading

                    result_holder: Dict[str, Optional[bool]] = {"result": None}

                    def wait_in_thread():
                        try:
                            asyncio.run(
                                asyncio.wait_for(req._event.wait(), timeout=timeout_seconds)
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
                else:
                    asyncio.run(asyncio.wait_for(req._event.wait(), timeout=timeout_seconds))
                    result = req._result
            except RuntimeError:
                asyncio.run(asyncio.wait_for(req._event.wait(), timeout=timeout_seconds))
                result = req._result
        except TimeoutError:
            result = False
            logger.warning(
                "Confirmation request %s TIMED OUT after %ds", request_id, timeout_seconds
            )
        except Exception as exc:  # noqa: BLE001
            result = False
            logger.error("Confirmation request %s failed: %s", request_id, exc)

        # Clean up
        self._pending.pop(request_id, None)
        return bool(result)

    # ─── WebSocket client side: confirm / reject ──────────────────────────

    async def confirm(self, request_id: str, session_id: str) -> Dict[str, Any]:
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
                    {"type": "confirmation_resolved", "data": req.to_dict(), "approved": True}
                )
                logger.info(
                    "Confirmation %s APPROVED by %d humans", request_id, len(req.confirmations)
                )

            return {"success": True, "data": req.to_dict()}

    async def reject(self, request_id: str, session_id: str, reason: str = "") -> Dict[str, Any]:
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
                }
            )
            logger.warning("Confirmation %s REJECTED by %s: %s", request_id, session_id, reason)
            return {"success": True, "data": req.to_dict()}

    # ─── Health / status ─────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        return {
            "connected_clients": len(self._connected_clients),
            "pending_requests": len(self._pending),
            "required_confirmations": self.required_confirmations,
            "pending_request_ids": list(self._pending.keys()),
        }


# ─── Singleton broker ──────────────────────────────────────────────────────

confirmation_broker = ConfirmationBroker()


# ─── WebSocket endpoint handler ────────────────────────────────────────────


async def cua_confirmation_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint handler for /ws/cua/confirmation.

    Message protocol (JSON):

      Client → Server:
        {"action": "confirm", "request_id": "...", "session_id": "..."}
        {"action": "reject", "request_id": "...", "session_id": "...", "reason": "..."}

      Server → Client:
        {"type": "confirmation_request", "data": {...}}
        {"type": "confirmation_resolved", "data": {...}, "approved": true/false}
        {"type": "pending_request", "data": {...}}  (on connect)
        {"type": "error", "message": "..."}
    """
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
            session_id = data.get("session_id", str(id(websocket)))

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
        logger.error("Confirmation WS error: %s", exc)
        confirmation_broker.disconnect(websocket)


__all__ = [
    "ConfirmationBroker",
    "ConfirmationRequest",
    "confirmation_broker",
    "cua_confirmation_ws",
]
