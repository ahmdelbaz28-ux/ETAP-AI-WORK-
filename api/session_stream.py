"""
api/session_stream.py — Session Stream Hub (P3)
================================================

Secure real-time event streaming per engineering session over WebSocket,
with short-lived single-use tickets and a JobProgress bridge used by
``agents/orchestrator.py``.

Endpoints / protocol
--------------------
* ``POST /api/v1/ws-ticket``          — issue a short-lived (60 s), single-use,
  HMAC-signed ticket bound to ``(session_id, user_id)``. Avoids putting a
  long-lived JWT access token into the WS query string.
* ``WS   /ws/sessions/{session_id}``  — authenticated via ``?ticket=...``
  (preferred) or ``?token=<jwt_access_token>`` (same checks as
  ``/ws/notifications``: access-type token, blacklist check, active user).

Event types published on the stream: ``session_init`` (once on connect),
``token`` (LLM reply chunk), ``action_proposed``, ``approval_result``,
``job_progress`` (phase + pct from the orchestrator bridge),
``result_ready``, and ``decision_request``.

Reconnect / missed events
-------------------------
Every event carries a monotonically increasing ``seq`` per session and is
appended to a bounded in-memory history. A reconnecting client passes its
last seen sequence either as ``?after_seq=<n>`` on the upgrade request or as
a ``{"type": "resume", "after_seq": <n>}`` text frame; all buffered events
with ``seq > n`` are replayed immediately after ``session_init``.

Ticket design note
------------------
Tickets are signed (HMAC-SHA256 over a compact JSON payload) using
``JWT_SECRET_KEY``, so no database table / migration is required.
Single-use enforcement keeps a small in-memory ``{ticket_id: expires_at}``
map that self-prunes. If multi-replica deployments need shared ticket state
later, this module is the single place to swap in Redis/DB backing.

This module follows the "INTERNAL" pattern of ``api/websocket.py`` /
``api/cua_confirmation_ws.py``: the router it exposes is registered once in
``api/routes.py``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, List, Optional
from typing_extensions import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# Safe top-level import: api.dependencies does not import this module.
from api.dependencies import CurrentUser, get_current_user_from_header

logger = logging.getLogger("api.session_stream")

# WebSocket close codes (RFC 6455 §7.4.1)
_WS_CODE_POLICY_VIOLATION = 1008

# ─── Event types ───────────────────────────────────────────────────────────
EVENT_SESSION_INIT = "session_init"
EVENT_TOKEN = "token"
EVENT_ACTION_PROPOSED = "action_proposed"
EVENT_APPROVAL_RESULT = "approval_result"
EVENT_JOB_PROGRESS = "job_progress"
EVENT_RESULT_READY = "result_ready"
EVENT_DECISION_REQUEST = "decision_request"

KNOWN_EVENT_TYPES = frozenset(
    {
        EVENT_SESSION_INIT,
        EVENT_TOKEN,
        EVENT_ACTION_PROPOSED,
        EVENT_APPROVAL_RESULT,
        EVENT_JOB_PROGRESS,
        EVENT_RESULT_READY,
        EVENT_DECISION_REQUEST,
    }
)

# ─── Hub configuration ─────────────────────────────────────────────────────
HISTORY_LIMIT_PER_SESSION = 500  # bounded replay buffer per session
SEND_QUEUE_MAXSIZE = 256  # per-connection outbound queue
JOB_PROGRESS_PHASES = ("parsing", "solving", "validating")

# ─── Ticket configuration ──────────────────────────────────────────────────
WS_TICKET_TTL_SECONDS = 60  # requirement: tickets live for one minute
_MAX_CONSUMED_TRACKED = 4096  # self-prune threshold for consumed-ticket map


@dataclass
class _Connection:
    """One subscribed WebSocket plus its outbound queue and writer task."""

    websocket: WebSocket
    queue: asyncio.Queue[Dict[str, Any]]
    writer_task: Optional[asyncio.Task[None]] = None


class SessionStreamHub:
    """Registry of WebSocket subscribers per session with bounded replay.

    Delivery model: each connection owns an :class:`asyncio.Queue`; a single
    writer task drains the queue and serializes frames onto the socket, so
    producers never write concurrently to the same WebSocket.

    Producers may call :meth:`publish` from *any* thread:
    - when called on the hub's event loop, events are enqueued directly;
    - otherwise they are scheduled via ``loop.call_soon_threadsafe``.
    Events are always recorded to the replay history first, so even if no
    listener is attached yet the event remains recoverable by reconnecting
    clients.
    """

    def __init__(self, history_limit: int = HISTORY_LIMIT_PER_SESSION) -> None:
        self._history_limit = history_limit
        self._connections: Dict[str, List[_Connection]] = {}
        self._history: Dict[str, deque] = {}
        self._seq: Dict[str, int] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -- lifecycle ----------------------------------------------------------

    async def connect(self, websocket: WebSocket, session_id: str) -> _Connection:
        conn = _Connection(websocket, asyncio.Queue(maxsize=SEND_QUEUE_MAXSIZE))
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self._connections.setdefault(session_id, []).append(conn)
        conn.writer_task = asyncio.create_task(self._writer_loop(conn))
        return conn

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(session_id, [])
        remaining: List[_Connection] = []
        for conn in conns:
            if conn.websocket is websocket:
                if conn.writer_task is not None:
                    conn.writer_task.cancel()
            else:
                remaining.append(conn)
        if remaining:
            self._connections[session_id] = remaining
        else:
            self._connections.pop(session_id, None)

    @staticmethod
    async def _writer_loop(conn: _Connection) -> None:
        try:
            while True:
                event = await conn.queue.get()
                await conn.websocket.send_text(json.dumps(event))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - socket died; drop quietly
            logger.debug("session_stream writer terminated", exc_info=True)

    # -- publish ------------------------------------------------------------

    def _record(
        self, session_id: str, event_type: str, payload: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        next_seq = self._seq.get(session_id, 0) + 1
        self._seq[session_id] = next_seq
        event: Dict[str, Any] = {
            "seq": next_seq,
            "type": event_type,
            "session_id": session_id,
            "ts": datetime.now(UTC).isoformat(),
            "payload": payload or {},
        }
        history = self._history.setdefault(session_id, deque(maxlen=self._history_limit))
        history.append(event)
        return event

    @staticmethod
    def _offer(conn: _Connection, event: Dict[str, Any]) -> None:
        try:
            conn.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("session_stream send queue full — event dropped")

    def publish(
        self,
        session_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an event and fan it out to every subscriber of the session.

        Thread-safe: callable from the app's event loop (direct enqueue) or
        from any other thread (scheduled on the captured loop).
        """
        event = self._record(session_id, event_type, payload)
        conns = list(self._connections.get(session_id, []))
        if not conns:
            return event

        try:
            running_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            # Called from a non-async thread (e.g. a TestClient's main thread).
            running_loop = None

        on_hub_loop = running_loop is not None and running_loop is self._loop
        if on_hub_loop:
            # Same loop as the hub: enqueue directly.
            for conn in conns:
                self._offer(conn, event)
            return event

        # Cross-thread / no-loop producer: schedule delivery on the hub's loop
        # via call_soon_threadsafe so the asyncio.Queue is only touched from
        # the loop that owns it.
        target_loop = self._loop
        if target_loop is not None and target_loop.is_running():
            for conn in conns:
                target_loop.call_soon_threadsafe(self._offer, conn, event)
        return event

    # -- introspection / replay ----------------------------------------------

    def last_seq(self, session_id: str) -> int:
        return self._seq.get(session_id, 0)

    def status(self, session_id: str) -> Dict[str, Any]:
        history = self._history.get(session_id) or deque()
        last_event: Dict[str, Any] = history[-1] if history else {}
        return {
            "connected_clients": len(self._connections.get(session_id, [])),
            "last_seq": self.last_seq(session_id),
            "last_event_type": last_event.get("type"),
        }

    def replay(self, session_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        """Return buffered events with ``seq > after_seq`` (oldest first)."""
        history = self._history.get(session_id)
        if not history:
            return []
        return [ev for ev in history if ev["seq"] > after_seq]

    def latest_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Most recent buffered event for the session."""
        history = self._history.get(session_id)
        if not history:
            return None
        return dict(history[-1])

    def client_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, []))


_hub: Optional[SessionStreamHub] = None


def get_hub() -> SessionStreamHub:
    """Process-wide hub singleton."""
    global _hub
    if _hub is None:
        _hub = SessionStreamHub()
    return _hub


def reset_hub() -> None:
    """Test helper — drop the singleton so each test starts clean."""
    global _hub
    _hub = None


# ---------------------------------------------------------------------------
# Short-lived single-use WS tickets
# ---------------------------------------------------------------------------


def _ticket_secret() -> bytes:
    from api.dependencies import JWT_SECRET_KEY

    return JWT_SECRET_KEY.encode()


def _sign(payload_compact: str) -> str:
    return hmac.new(_ticket_secret(), payload_compact.encode(), hashlib.sha256).hexdigest()


# Consumed ticket ids: {ticket_id: expires_at_epoch}. In-memory by design —
# see module docstring for the multi-replica migration path.
_consumed_tickets: Dict[str, float] = {}


def issue_ws_ticket(
    session_id: str, user_id: str, ttl_seconds: int = WS_TICKET_TTL_SECONDS
) -> Dict[str, Any]:
    """Mint a short-lived, single-use, HMAC-signed WebSocket ticket.

    Returns ``{"ticket", "expires_at", "ttl_seconds"}``.
    """
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    payload_compact = json.dumps(
        {
            "tid": uuid.uuid4().hex,
            "sid": session_id,
            "uid": user_id,
            "exp": expires_at.timestamp(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    token = (
        base64.urlsafe_b64encode(payload_compact.encode()).decode().rstrip("=")
        + "."
        + _sign(payload_compact)
    )
    return {
        "ticket": token,
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": ttl_seconds,
    }


def consume_ws_ticket(ticket: str, session_id: str) -> Optional[Dict[str, str]]:
    """Validate and burn a ticket (single-use).

    Returns ``{"session_id", "user_id"}`` on success, or ``None`` when the
    ticket is malformed, forged, expired, bound to another session, or was
    already used.
    """
    now = time.time()

    # Opportunistic pruning of the consumed-tickets map.
    if len(_consumed_tickets) > _MAX_CONSUMED_TRACKED:
        for tid in [t for t, exp in _consumed_tickets.items() if exp <= now]:
            _consumed_tickets.pop(tid, None)

    try:
        payload_b64, _, signature = ticket.partition(".")
        if not payload_b64 or not signature:
            return None
        padding = "=" * (-len(payload_b64) % 4)
        payload_compact = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        if not hmac.compare_digest(signature, _sign(payload_compact)):
            return None
        claims = json.loads(payload_compact)
        tid = claims["tid"]
        sid = claims["sid"]
        uid = claims["uid"]
        exp = float(claims["exp"])
    except Exception:  # noqa: BLE001 - any parse/verify failure rejects
        return None

    if exp <= now:
        return None
    if tid in _consumed_tickets:
        return None
    if session_id != sid:
        return None

    _consumed_tickets[tid] = exp
    return {"session_id": sid, "user_id": uid}


def reset_ws_tickets() -> None:
    """Test helper — clear consumed-ticket state."""
    _consumed_tickets.clear()


class WsTicketRequest(BaseModel):
    """Body of ``POST /api/v1/ws-ticket``."""

    session_id: str = Field(min_length=1, max_length=128)


router = APIRouter(tags=["session-stream"])


@router.post(
    "/api/v1/ws-ticket",
    summary="Issue a short-lived single-use WebSocket ticket",
)
async def create_ws_ticket(
    body: WsTicketRequest,
    user: Annotated[CurrentUser, Depends(get_current_user_from_header)],
) -> Dict[str, Any]:
    """Exchange a valid Bearer JWT for a 60-second single-use WS ticket.

    The returned ticket authenticates exactly ONE connection to
    ``/ws/sessions/{body.session_id}`` and expires after 60 seconds, keeping
    long-lived credentials out of WebSocket query strings.
    """
    issued = issue_ws_ticket(body.session_id, user.user_id)
    logger.info(
        "ws-ticket issued user=%.24s session=%.24s ttl=%ss",
        user.user_id,
        body.session_id,
        issued["ttl_seconds"],
    )
    return issued


# ---------------------------------------------------------------------------
# WebSocket endpoint implementation (/ws/sessions/{session_id})
# ---------------------------------------------------------------------------


async def _validate_ws_ticket(websocket: WebSocket, ticket: str) -> Optional[str]:
    session_id = str(websocket.path_params.get("session_id", ""))
    claims = consume_ws_ticket(ticket, session_id)
    if claims is None:
        await websocket.close(
            code=_WS_CODE_POLICY_VIOLATION,
            reason="Invalid, expired, already used, or mismatched ticket",
        )
        return None
    return claims["user_id"]


async def _validate_ws_token(websocket: WebSocket, token: str) -> Optional[str]:
    import jwt
    from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except Exception:
        await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid token")
        return None

    user_id = payload.get("sub")
    if not user_id or payload.get("type") != "access":
        await websocket.close(code=_WS_CODE_POLICY_VIOLATION, reason="Invalid or expired token")
        return None

    jti = payload.get("jti")
    if jti:
        try:
            from api.auth import _is_token_blacklisted
            if await _is_token_blacklisted(jti):
                await websocket.close(
                    code=_WS_CODE_POLICY_VIOLATION, reason="Token has been revoked"
                )
                return None
        except ImportError:
            pass
    return str(user_id)


async def _authenticate_user_id(websocket: WebSocket) -> Optional[str]:
    """Resolve the caller identity from ``?ticket=`` or ``?token=``."""
    ticket = websocket.query_params.get("ticket", "")
    if ticket:
        return await _validate_ws_ticket(websocket, ticket)

    token = websocket.query_params.get("token", "")
    if token:
        return await _validate_ws_token(websocket, token)

    await websocket.close(
        code=_WS_CODE_POLICY_VIOLATION,
        reason="Missing authentication — provide ?ticket= or ?token=",
    )
    return None


async def _verify_active_user(user_id: str) -> bool:
    from api.database import async_session
    from sqlalchemy import select
    from api.auth import User

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return bool(user and user.is_active)


def _dispatch_ws_message(
    hub: SessionStreamHub, conn: _Connection, session_id: str, message: dict[str, Any]
) -> None:
    msg_type = message.get("type")
    if msg_type == "resume":
        resume_after = message.get("after_seq", 0)
        if isinstance(resume_after, int) and resume_after >= 0:
            for ev in hub.replay(session_id, resume_after):
                hub._offer(conn, ev)
    elif msg_type == "ping":
        hub._offer(conn, {"type": "pong", "ts": datetime.now(UTC).isoformat()})


async def _handle_ws_messages(
    hub: SessionStreamHub, conn: _Connection, session_id: str, websocket: WebSocket
) -> None:
    while True:
        raw = await websocket.receive_text()
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(message, dict):
            _dispatch_ws_message(hub, conn, session_id, message)


def _send_initial_ws_events(
    hub: SessionStreamHub,
    conn: _Connection,
    session_id: str,
    user_id: str,
    websocket: WebSocket,
) -> None:
    """Send session initialization and replay events on websocket connect."""
    init_payload = {
        "status": hub.status(session_id),
        "authenticated_as": user_id,
    }
    if hub.last_seq(session_id) == 0:
        init_event = hub._record(session_id, EVENT_SESSION_INIT, init_payload)
        for subscriber in hub._connections.get(session_id, []):
            hub._offer(subscriber, init_event)
    else:
        hub._offer(
            conn,
            {
                "seq": hub.last_seq(session_id),
                "type": EVENT_SESSION_INIT,
                "session_id": session_id,
                "ts": datetime.now(UTC).isoformat(),
                "payload": init_payload,
            },
        )

    after_seq_raw = websocket.query_params.get("after_seq", "")
    replay_events = (
        hub.replay(session_id, int(after_seq_raw)) if after_seq_raw.isdigit() else []
    )
    for ev in replay_events:
        hub._offer(conn, ev)


async def session_stream_ws(websocket: WebSocket, session_id: str) -> None:
    """Handle one connection to ``/ws/sessions/{session_id}``."""
    user_id = await _authenticate_user_id(websocket)
    if user_id is None:
        return

    if not await _verify_active_user(user_id):
        await websocket.close(
            code=_WS_CODE_POLICY_VIOLATION, reason="User not found or inactive"
        )
        return

    hub = get_hub()
    await websocket.accept()
    conn = await hub.connect(websocket, session_id)

    try:
        _send_initial_ws_events(hub, conn, session_id, user_id, websocket)
        await _handle_ws_messages(hub, conn, session_id, websocket)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - never let socket errors escape
        logger.debug("session_stream reader terminated", exc_info=True)
    finally:
        hub.disconnect(session_id, websocket)
