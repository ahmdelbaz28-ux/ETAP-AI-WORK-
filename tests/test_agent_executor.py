"""
tests/test_agent_executor.py — P4a secure agent-exec path tests.

Covers (per phase requirements):
* ToolPlan carrying an engineering parameter without ``source``
  -> 422 UNSOURCED_ENGINEERING_VALUE.
* ToolPlan with a valid ``source`` -> accepted (auto_approved under
  session auto-approve).
* ``powershell-tool`` -> 403 TOOL_DENIED_IN_AGENT_EXEC (and can never
  execute even via a forged plan record).
* Same Idempotency-Key twice -> exactly ONE execution; the second
  response carries ``idempotent_replay: true``.
* Expired plan (TTL 300 s) -> 410 PLAN_EXPIRED.
* Read-only tool -> straight ``auto_approved`` (never pending).
* Streaming bridge: executions publish job_progress/result_ready on the
  SessionStreamHub for the plan's session.

These tests exercise the real FastAPI app (``api.routes.app``) through the
Starlette TestClient; the seeded ``test-user-id`` user comes from
``tests/conftest.py``.
"""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

import api.agent_executor as agent_exec
from api.agent_executor import register_executor, reset_agent_exec_state
from api.approvals import _session_auto_approve as SESSION_AUTO_APPROVE
from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY


def _auth(user_id: str = "test-user-id") -> dict:
    """Auth header carrying a valid access JWT like /api/v1/auth/login."""
    now = time.time()
    token = pyjwt.encode(
        {"sub": user_id, "type": "access", "iat": int(now), "exp": int(now + 600)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    """Module-scoped app client (starts FastAPI lifespan ONCE)."""
    from api.routes import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_executor_state():
    """Reset plans/executions/idempotency around every test, keeping the
    built-in run_python executor registered."""
    reset_agent_exec_state()
    register_executor("run_python", agent_exec._run_python_executor)
    SESSION_AUTO_APPROVE.clear()
    yield
    SESSION_AUTO_APPROVE.clear()
    reset_agent_exec_state()
    register_executor("run_python", agent_exec._run_python_executor)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _post_plan(client: TestClient, body: dict):
    return client.post("/api/v1/agent-exec/plan", json=body, headers=_auth())


# ─── 1. Engineering-source enforcement ─────────────────────────────────────


def test_plan_unsourced_engineering_value_422(client):
    resp = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {"goal": "arc flash check", "bolted_fault_current": 18.5},
            "session_id": "sess-p4a-unsourced",
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "UNSOURCED_ENGINEERING_VALUE"


def test_plan_with_valid_source_accepted_and_auto_approved(client):
    sid = "sess-p4a-sourced"
    SESSION_AUTO_APPROVE[sid] = True  # mutating tool -> auto_approved here
    resp = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {"goal": "arc flash check"},
            "source": {
                "kind": "project_data",
                "ref": "etap://project/transmission-2026/bus-7",
            },
            "session_id": sid,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decision"] == "auto_approved"
    assert data["plan_id"].startswith("plan_")


# ─── 2. Denied tools ───────────────────────────────────────────────────────


def test_powershell_tool_denied_403(client):
    resp = _post_plan(
        client,
        {
            "tool": "powershell-tool",
            "args": {"script": "Get-Process"},
            "session_id": "sess-p4a-ps",
        },
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "TOOL_DENIED_IN_AGENT_EXEC"


def test_forged_plan_record_for_denied_tool_still_cannot_execute(client):
    """Belt-and-braces: even a forged PlanRecord in the registry must never
    execute a hard-denied tool."""
    rec = agent_exec.PlanRecord(
        plan_id="plan_forged",
        tool="node-tool",
        requested_tool="node-tool",
        args={},
        session_id=None,
        decision="auto_approved",
        reason="forged",
        created_at=time.time(),
        expires_at=time.time() + 300,
    )
    agent_exec._PLANS[rec.plan_id] = rec

    class _Boom(Exception):
        pass

    def _must_not_run(args, ctx):  # pragma: no cover — must never be reached
        raise _Boom("denied executor must never run")

    register_executor("node-tool", _must_not_run)
    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": "plan_forged"},
        headers={**_auth(), "Idempotency-Key": "key-forged-node"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "TOOL_DENIED_IN_AGENT_EXEC"


# ─── 3. Idempotent execution ───────────────────────────────────────────────


def test_execute_idempotency_same_key_executes_once(client):
    sid = "sess-p4a-idem"
    SESSION_AUTO_APPROVE[sid] = True
    plan_resp = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {"goal": "load flow sanity"},
            "session_id": sid,
        },
    )
    assert plan_resp.json()["decision"] == "auto_approved"
    plan_id = plan_resp.json()["plan_id"]

    calls: list[str] = []

    async def _counting_executor(args, ctx):
        calls.append(ctx["execution_id"])
        return {"studies": [{"type": "LOAD_FLOW", "converged": True}]}

    register_executor("run_python", _counting_executor)

    headers = {**_auth(), "Idempotency-Key": "idem-key-42"}
    first = client.post(
        "/api/v1/agent-exec/execute", json={"plan_id": plan_id}, headers=headers
    )
    second = client.post(
        "/api/v1/agent-exec/execute", json={"plan_id": plan_id}, headers=headers
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert len(calls) == 1  # exactly ONE logical execution
    data1, data2 = first.json()["data"], second.json()["data"]
    assert data2["execution_id"] == data1["execution_id"]
    assert not first.json().get("idempotent_replay", False)
    assert second.json()["idempotent_replay"] is True


def test_execute_requires_idempotency_key(client):
    sid = "sess-p4a-nokey"
    SESSION_AUTO_APPROVE[sid] = True
    plan_id = _post_plan(
        client,
        {"tool": "run_python", "args": {}, "session_id": sid},
    ).json()["plan_id"]
    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id},
        headers=_auth(),  # no Idempotency-Key header
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MISSING_IDEMPOTENCY_KEY"

# ─── 4. Plan TTL ───────────────────────────────────────────────────────────


def test_execute_expired_plan_rejected_410(client):
    sid = "sess-p4a-expired"
    SESSION_AUTO_APPROVE[sid] = True
    plan_id = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {"goal": "short circuit"},
            "session_id": sid,
        },
    ).json()["plan_id"]

    # Force the plan past its 300 s TTL.
    agent_exec._PLANS[plan_id].expires_at = time.time() - 1

    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id},
        headers={**_auth(), "Idempotency-Key": "key-expired-plan"},
    )
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "PLAN_EXPIRED"


def test_execute_unknown_plan_404(client):
    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": "plan_does_not_exist"},
        headers={**_auth(), "Idempotency-Key": "key-unknown-plan"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PLAN_NOT_FOUND"


# ─── 5. Read tools & pending plans ─────────────────────────────────────────


def test_read_tool_plan_auto_approved_without_pending(client):
    resp = _post_plan(
        client,
        {
            "tool": "weather-tool",
            "args": {"city": "Riyadh"},
            "session_id": "sess-p4a-read",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decision"] == "auto_approved"
    assert data["reason"] == "read-only tool auto-approved"


def test_pending_plan_cannot_execute(client):
    """Mutating tool without session auto-approve -> pending; executing a
    pending plan is refused until it goes through the Approval Gateway."""
    sid = "sess-p4a-pending"
    plan_id = _post_plan(
        client,
        {"tool": "run_python", "args": {"goal": "coordination run"}, "session_id": sid},
    ).json()
    assert plan_id["decision"] == "pending"

    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id["plan_id"]},
        headers={**_auth(), "Idempotency-Key": "key-pending-plan"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "APPROVAL_REQUIRED"


# ─── 6. Session-stream bridge ──────────────────────────────────────────────


def test_execution_streams_job_progress_and_result_ready(client, monkeypatch):
    """Executions publish job_progress + result_ready on the hub for the
    plan's session (recorded via the real hub singleton)."""
    events: list[tuple] = []

    from api import session_stream as ss_module

    real_get_hub = ss_module.get_hub
    hub = real_get_hub()
    original_publish = hub.publish

    def _recording_publish(session_id, event_type, payload=None):
        if session_id == "sess-p4a-stream":
            events.append((event_type, dict(payload or {})))
        return original_publish(session_id, event_type, payload)

    monkeypatch.setattr(hub, "publish", _recording_publish)

    sid = "sess-p4a-stream"
    SESSION_AUTO_APPROVE[sid] = True
    plan_id = _post_plan(
        client,
        {"tool": "run_python", "args": {"goal": "streaming check"}, "session_id": sid},
    ).json()["plan_id"]

    async def _ok_executor(args, ctx):
        return {"studies": [{"type": "LOAD_FLOW"}]}

    register_executor("run_python", _ok_executor)

    resp = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id},
        headers={**_auth(), "Idempotency-Key": "key-stream-events"},
    )
    assert resp.status_code == 200, resp.text

    types = [t for t, _ in events]
    assert "job_progress" in types
    assert "result_ready" in types
    ready = next(p for t, p in events if t == "result_ready")
    assert ready["execution_id"] == resp.json()["data"]["execution_id"]
    assert ready["tool"] == "run_python"

