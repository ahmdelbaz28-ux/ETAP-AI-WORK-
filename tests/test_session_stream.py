"""
tests/test_session_stream.py — P3 Session Stream Hub tests.

Covers:
* Successful authenticated WebSocket connect (``/ws/sessions/{id}?token=``)
  and the ``session_init`` handshake.
* ``job_progress`` delivery while a (simulated) job emits events.
* Short-lived WS tickets: valid use succeeds, second use is REJECTED
  (single-use), and expired tickets are rejected.
* Reconnect replays missed events from the bounded hub history
  (``?after_seq=N`` / ``hub.latest_state`` fallback).

These tests exercise the real FastAPI app (``api.routes.app``) through the
Starlette TestClient; the seeded ``test-user-id`` user comes from
``tests/conftest.py``.
"""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY
from api.session_stream import (
    get_hub,
    issue_ws_ticket,
    reset_hub,
    reset_ws_tickets,
)

SESSION_PATH = "/ws/sessions"
WS_TICKET_PATH = "/api/v1/ws-ticket"


# ─── Helpers / fixtures ────────────────────────────────────────────────────


def _make_access_token(user_id: str = "test-user-id") -> str:
    """Craft a valid access JWT exactly like /api/v1/auth/login does."""
    now = time.time()
    return pyjwt.encode(
        {"sub": user_id, "type": "access", "iat": int(now), "exp": int(now + 600)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


@pytest.fixture(scope="module")
def client():
    """Module-scoped app client: the FastAPI app starts ONCE, then every
    test reuses it (huge speedup vs. per-test lifespan). Hub/ticket state is
    reset per-test inside each test via reset_hub()/reset_ws_tickets().
    """
    from api.csrf import generate_csrf_token
    from api.routes import app

    with TestClient(app) as c:
        c.headers.update({"x-csrf-token": generate_csrf_token()})
        yield c


@pytest.fixture(autouse=True)
def _clean_stream_state():
    """Reset the hub + consumed-ticket map before AND after every test so
    sequence numbers and single-use ticket state never leak across tests."""
    reset_hub()
    reset_ws_tickets()
    yield
    reset_hub()
    reset_ws_tickets()


# ─── 1. Successful connection ──────────────────────────────────────────────


def test_ws_connect_success_with_token(client):
    """Authenticated connect receives a session_init handshake."""
    sid = "sess-connect"
    token = _make_access_token()

    with client.websocket_connect(f"{SESSION_PATH}/{sid}?token={token}") as ws:
        init = ws.receive_json()
        assert init["type"] == "session_init"
        assert init["session_id"] == sid
        assert init["payload"]["authenticated_as"] == "test-user-id"
        assert "status" in init["payload"]
        # The init event itself occupies seq 1 of this fresh session.
        assert init["seq"] == 1


def test_ws_connect_rejected_without_auth(client):
    """No ticket and no token → closed with policy-violation code 1008."""
    sid = "sess-noauth"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{SESSION_PATH}/{sid}"):
            pass


# ─── 2. job_progress received while a simulated job runs ──────────────────


def test_job_progress_received_during_simulated_job(client):
    """Events published by the JobProgress bridge reach live subscribers."""
    sid = "sess-progress"
    hub = get_hub()
    token = _make_access_token()

    with client.websocket_connect(f"{SESSION_PATH}/{sid}?token={token}") as ws:
        init = ws.receive_json()
        assert init["type"] == "session_init"

        # Simulate the orchestrator emitting bridge events mid-job.
        ev_parsing = hub.publish(sid, "job_progress", {"phase": "parsing", "pct": 5})
        ev_solving = hub.publish(sid, "job_progress", {"phase": "solving", "pct": 45})

        got_parsing = ws.receive_json()
        assert got_parsing["type"] == "job_progress"
        assert got_parsing["payload"] == {"phase": "parsing", "pct": 5}

        got_solving = ws.receive_json()
        assert got_solving["type"] == "job_progress"
        assert got_solving["payload"]["phase"] == "solving"

        # Sequence numbers increase monotonically.
        assert got_parsing["seq"] == ev_parsing["seq"]
        assert got_solving["seq"] == ev_solving["seq"] > got_parsing["seq"]


# ─── 3. Tickets: REST issuance + single-use enforcement ───────────────────


def test_ws_ticket_valid_then_single_use(client):
    """A ticket works exactly once: 1st connect OK, 2nd connect rejected."""
    sid = "sess-ticket"
    token = _make_access_token()

    # Issue a ticket via the REST endpoint (Bearer JWT → short-lived ticket).
    resp = client.post(
        WS_TICKET_PATH,
        json={"session_id": sid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ttl_seconds"] == 60
    assert "ticket" in body and "expires_at" in body
    ticket = body["ticket"]

    # FIRST use: accepted.
    with client.websocket_connect(f"{SESSION_PATH}/{sid}?ticket={ticket}") as ws:
        init = ws.receive_json()
        assert init["type"] == "session_init"
        assert init["payload"]["authenticated_as"] == "test-user-id"

    # SECOND use of the SAME ticket: rejected with code 1008.
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{SESSION_PATH}/{sid}?ticket={ticket}"):
            pass


def test_ws_ticket_bound_to_other_session_rejected(client):
    """A ticket minted for session A cannot open session B."""
    token = _make_access_token()
    issued = issue_ws_ticket("sess-a", "test-user-id")

    from api.session_stream import consume_ws_ticket

    # Direct consumption against the wrong session id fails…
    assert consume_ws_ticket(issued["ticket"], "sess-b") is None
    # …while the server-side WS path rejects it too.
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{SESSION_PATH}/sess-b?ticket={issued['ticket']}"):
            pass


# ─── 4. Ticket expiry ──────────────────────────────────────────────────────


def test_ws_ticket_expiry_rejected(client):
    """An expired ticket is rejected even on its very first use."""
    sid = "sess-expired"
    issued = issue_ws_ticket(sid, "test-user-id", ttl_seconds=-1)  # already stale

    assert issued["ttl_seconds"] == -1
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{SESSION_PATH}/{sid}?ticket={issued['ticket']}"):
            pass


# ─── 5. Reconnect replays missed events ────────────────────────────────────


def test_reconnect_replays_missed_events(client):
    """After a drop, reconnecting with after_seq=N recovers events N+1…"""
    sid = "sess-replay"
    hub = get_hub()
    token = _make_access_token()

    # First connection: consume init + one live event.
    with client.websocket_connect(f"{SESSION_PATH}/{sid}?token={token}") as ws1:
        init1 = ws1.receive_json()
        assert init1["type"] == "session_init"
        missed_marker = hub.publish(sid, "job_progress", {"phase": "solving", "pct": 30})
        got = ws1.receive_json()
        assert got["seq"] == missed_marker["seq"]

    # Connection dropped. Events published while offline are still recorded.
    # The TestClient closes the WS synchronously, but the async endpoint's
    # `finally: hub.disconnect(...)` runs on the event loop; give it a moment.
    deadline = time.monotonic() + 3.0
    while hub.client_count(sid) != 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    offline_event = hub.publish(
        sid, "result_ready", {"task_id": "workflow_1", "all_validated": True}
    )
    assert hub.client_count(sid) == 0

    # Reconnect asking for everything after the last seq we saw.
    last_seen = missed_marker["seq"]
    with client.websocket_connect(
        f"{SESSION_PATH}/{sid}?token={token}&after_seq={last_seen}"
    ) as ws2:
        init2 = ws2.receive_json()
        assert init2["type"] == "session_init"

        replayed = ws2.receive_json()
        assert replayed["seq"] > last_seen
        assert replayed["type"] == "result_ready"
        assert replayed["payload"]["task_id"] == "workflow_1"
        assert replayed["payload"] == offline_event["payload"]

    # latest_state() gives the same recovery answer without a socket.
    latest = hub.latest_state(sid)
    assert latest is not None
    assert latest["type"] == "result_ready"


def test_resume_message_replays_history(client):
    """The in-band ``{"type":"resume","after_seq":n}`` frame also replays."""
    sid = "sess-resume"
    hub = get_hub()
    token = _make_access_token()

    hub.publish(sid, "job_progress", {"phase": "parsing", "pct": 5})  # seq 1
    hub.publish(sid, "job_progress", {"phase": "solving", "pct": 50})  # seq 2

    with client.websocket_connect(f"{SESSION_PATH}/{sid}?token={token}") as ws:
        init = ws.receive_json()  # session_init (recorded at connect time)
        assert init["type"] == "session_init"

        ws.send_json({"type": "resume", "after_seq": 0})
        first = ws.receive_json()
        second = ws.receive_json()
        assert [first["seq"], second["seq"]] == [1, 2]
        assert all(e["type"] == "job_progress" for e in (first, second))
