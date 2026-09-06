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
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.agent_executor as agent_exec
from api.agent_executor import register_executor, reset_agent_exec_state
from api.approvals import _session_auto_approve as _session_auto_approve
from api.dependencies import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    CurrentUser,
    get_current_user_from_header,
)

# Stub user returned by the overridden auth dependency.
# The module-scoped client installs this override so the real JWT/DB lookup
# is bypassed — identical pattern to test_approvals.py and the security-gate
# section below.
_TEST_USER = CurrentUser(
    user_id="test-user-id",
    username="test_user",
    email="test@example.com",
    role="engineer",
    tenant_id="tenant-test",
    is_active=True,
)


def _auth(user_id: str = "test-user-id") -> dict:
    """Auth header carrying a valid access JWT and CSRF token."""
    now = time.time()
    token = pyjwt.encode(
        {"sub": user_id, "type": "access", "iat": int(now), "exp": int(now + 600)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    from api.csrf import generate_csrf_token

    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


@pytest.fixture(scope="module")
def client():
    """Module-scoped app client (starts FastAPI lifespan ONCE).

    The ``get_current_user_from_header`` dependency is overridden here to
    return ``_TEST_USER`` directly, bypassing JWT decoding and the DB user
    lookup (which would fail because ``test-user-id`` is not seeded in the
    test SQLite DB).  This mirrors the approach in ``test_approvals.py`` and
    the security-gate section below.
    """
    from api.csrf import generate_csrf_token
    from api.routes import app

    app.dependency_overrides[get_current_user_from_header] = lambda: _TEST_USER
    with TestClient(app) as c:
        c.headers.update({"x-csrf-token": generate_csrf_token()})
        yield c
    app.dependency_overrides.pop(get_current_user_from_header, None)


@pytest.fixture(autouse=True)
def _clean_executor_state():
    """Reset plans/executions/idempotency around every test, keeping the
    built-in run_python executor registered."""
    reset_agent_exec_state()
    register_executor("run_python", agent_exec._run_python_executor)
    _session_auto_approve.clear()
    yield
    _session_auto_approve.clear()
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
    _session_auto_approve[sid] = True  # mutating tool -> auto_approved here
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
    _session_auto_approve[sid] = True
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
    first = client.post("/api/v1/agent-exec/execute", json={"plan_id": plan_id}, headers=headers)
    second = client.post("/api/v1/agent-exec/execute", json={"plan_id": plan_id}, headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert len(calls) == 1  # exactly ONE logical execution
    data1, data2 = first.json()["data"], second.json()["data"]
    assert data2["execution_id"] == data1["execution_id"]
    assert not first.json().get("idempotent_replay", False)
    assert second.json()["idempotent_replay"] is True


def test_execute_requires_idempotency_key(client):
    sid = "sess-p4a-nokey"
    _session_auto_approve[sid] = True
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


def test_execute_expired_plan_rejected_410(client, monkeypatch):
    sid = "sess-p4a-expired"
    _session_auto_approve[sid] = True
    plan_id = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {"goal": "short circuit"},
            "session_id": sid,
        },
    ).json()["plan_id"]

    # Force the plan past its 300 s TTL.
    monkeypatch.setattr(agent_exec._PLANS[plan_id], "expires_at", time.time() - 1)

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
    _session_auto_approve[sid] = True
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


# ---------------------------------------------------------------------------
# Security Gate — isolated end-to-end rig (plan -> gateway -> execute)
#
# A function-scoped FastAPI app exposes BOTH the agent-exec router and the
# Approval Gateway router so approval->execution binding can be proven
# without touching the module-scoped routes.app client above.
# ---------------------------------------------------------------------------

EXEC_TENANT_A = CurrentUser(
    user_id="exec-a",
    username="exec_a",
    email="exec_a@example.com",
    role="engineer",
    tenant_id="tenant-A",
)
EXEC_TENANT_B = CurrentUser(
    user_id="exec-b",
    username="exec_b",
    email="exec_b@example.com",
    role="engineer",
    tenant_id="tenant-B",
)


async def _stub_executor(args, ctx):  # deterministic exec target
    return {"studies": [{"type": "LOAD_FLOW", "converged": True}]}


@pytest.fixture
def gate_client():
    """Fresh combined agent-exec + approvals app bound to tenant-A user."""
    from api import approvals as approvals_module

    app = FastAPI()
    app.include_router(agent_exec.router)
    app.include_router(approvals_module.router)
    app.dependency_overrides[get_current_user_from_header] = lambda: EXEC_TENANT_A

    _session_auto_approve.clear()
    reset_agent_exec_state()
    register_executor("run_python", agent_exec._run_python_executor)

    with TestClient(app) as c:
        yield c

    _session_auto_approve.clear()
    reset_agent_exec_state()
    register_executor("run_python", agent_exec._run_python_executor)


def _switch(client: TestClient, user: CurrentUser) -> None:
    client.app.dependency_overrides[get_current_user_from_header] = lambda: user


# ─── Security Gate: source enforcement on nested payloads ──────────────────


def test_node_tool_denied_at_plan_level(client):
    """node-tool is hard-denied exactly like powershell-tool."""
    resp = _post_plan(
        client,
        {
            "tool": "node-tool",
            "args": {"script": "console.log(1)"},
            "session_id": "sess-p4a-node",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "TOOL_DENIED_IN_AGENT_EXEC"


def test_nested_engineering_value_rejected_without_source(client):
    """A nested unsourced parameter must NOT escape source enforcement."""
    resp = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {
                "goal": "coordination check",
                "parameters": {"ct_ratio": "1200/5"},
            },
            "session_id": "sess-p4a-nested",
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "UNSOURCED_ENGINEERING_VALUE"


def test_nested_engineering_value_with_valid_source_accepted(client):
    """Provenance covering nested engineering values satisfies Gate 2."""
    sid = "sess-p4a-nested-ok"
    _session_auto_approve[sid] = True
    resp = _post_plan(
        client,
        {
            "tool": "run_python",
            "args": {
                "goal": "coordination check",
                "parameters": {"ct_ratio": "1200/5"},
            },
            "source": {
                "kind": "project_data",
                "ref": "etap://project/transmission-2026/protection/ct-7",
            },
            "session_id": sid,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "auto_approved"


def test_critical_never_auto_approved(client):
    """Even with session auto-approve ON, a critical tool stays pending."""
    sid = "sess-p4a-critical"
    _session_auto_approve[sid] = True
    resp = _post_plan(
        client,
        {
            "tool": "provider-settings-tool",
            "args": {"setting": "relay_mode"},
            "session_id": sid,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "pending"

    # And executing that pending plan is refused outright.
    denied = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": resp.json()["plan_id"]},
        headers={**_auth(), "Idempotency-Key": "key-critical-plan"},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "APPROVAL_REQUIRED"


# ─── Security Gate: approval ⇄ plan binding on /execute ────────────────────

BIND_ARGS = {"goal": "bind check"}


def _submit_bound_plan(gate: TestClient, session_id: str, args: dict):
    resp = gate.post(
        "/api/v1/agent-exec/plan",
        json={"tool": "run_python", "args": args, "session_id": session_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _propose_and_resolve(
    gate: TestClient, session_id: str, args: dict, decision: str = "approve"
) -> dict:
    """Drive the real Approval Gateway: propose the identical tool+args
    identity that the plan carries, then resolve it."""
    prop = gate.post(
        "/api/v1/approvals",
        json={"session_id": session_id, "tool": "run_python", "args": args},
    )
    assert prop.status_code == 200, prop.text
    action_id = prop.json()["data"]["id"]
    res = gate.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": decision})
    assert res.status_code == 200, res.text
    return res.json()


def test_approval_binds_to_plan(gate_client):
    """Full P4a happy path: pending plan -> gateway APPROVE -> executable."""
    plan = _submit_bound_plan(gate_client, "bind-sess", BIND_ARGS)
    assert plan["decision"] == "pending"

    resolved = _propose_and_resolve(gate_client, "bind-sess", BIND_ARGS)
    assert resolved["data"]["status"] == "approved"

    resp = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan["plan_id"]},
        headers={"Idempotency-Key": "key-bind-ok"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["execution_id"]
    assert data["tool"] == "run_python"


def test_gateway_approved_execution_runs_exactly_once(gate_client):
    """Idempotent execute AFTER a gateway approval: two posts, one run."""
    plan = _submit_bound_plan(gate_client, "once-sess", BIND_ARGS)
    _propose_and_resolve(gate_client, "once-sess", BIND_ARGS)

    calls: list[str] = []

    async def _counting(args, ctx):
        calls.append(ctx["execution_id"])
        return {"ok": True}

    register_executor("run_python", _counting)

    headers = {"Idempotency-Key": "key-once-gw"}
    first = gate_client.post(
        "/api/v1/agent-exec/execute", json={"plan_id": plan["plan_id"]}, headers=headers
    )
    second = gate_client.post(
        "/api/v1/agent-exec/execute", json={"plan_id": plan["plan_id"]}, headers=headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
    assert second.json()["idempotent_replay"] is True
    assert second.json()["data"]["execution_id"] == first.json()["data"]["execution_id"]


def test_rejected_approval_cannot_execute(gate_client):
    plan = _submit_bound_plan(gate_client, "rej-sess", BIND_ARGS)
    _propose_and_resolve(gate_client, "rej-sess", BIND_ARGS, decision="reject")

    resp = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan["plan_id"]},
        headers={"Idempotency-Key": "key-rej-plan"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "APPROVAL_REQUIRED"


@pytest.mark.asyncio
async def test_expired_approval_cannot_execute(gate_client):
    plan = _submit_bound_plan(gate_client, "exp-sess", BIND_ARGS)
    approved = _propose_and_resolve(gate_client, "exp-sess", BIND_ARGS)
    action_id = approved["data"]["id"]

    # Force the approval past its 300 s TTL — an expired approval can never
    # authorise execution even though its row is still 'approved'.
    from sqlalchemy import select

    from api.approvals import PendingAction as PA
    from api.database import async_session

    past = datetime.now(UTC) - timedelta(seconds=1)
    async with async_session() as session:
        row = (await session.execute(select(PA).where(PA.id == action_id))).scalar_one()
        row.expires_at = past
        await session.commit()

    resp = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan["plan_id"]},
        headers={"Idempotency-Key": "key-expired-approval"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "APPROVAL_REQUIRED"


def test_substituted_args_do_not_satisfy_binding(gate_client):
    """Approving OTHER arguments never unlocks THIS plan (no substitution)."""
    plan = _submit_bound_plan(gate_client, "sub-sess", BIND_ARGS)
    _propose_and_resolve(gate_client, "sub-sess", {"goal": "completely OTHER task"})

    resp = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan["plan_id"]},
        headers={"Idempotency-Key": "key-sub-args"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "APPROVAL_REQUIRED"


def test_other_session_approval_does_not_bind(gate_client):
    plan = _submit_bound_plan(gate_client, "my-sess", BIND_ARGS)
    _propose_and_resolve(gate_client, "another-session", BIND_ARGS)

    resp = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan["plan_id"]},
        headers={"Idempotency-Key": "key-x-sess"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "APPROVAL_REQUIRED"


def test_cross_tenant_execute_denied_and_owner_unaffected(gate_client):
    """Tenant-B caller cannot execute tenant-A's auto-approved plan, while
    the legitimate owner still can."""
    sid = "xten"
    _session_auto_approve[sid] = True
    plan_resp = gate_client.post(
        "/api/v1/agent-exec/plan",
        json={"tool": "run_python", "args": {"goal": "tenant scope"}, "session_id": sid},
    )
    assert plan_resp.json()["decision"] == "auto_approved"
    plan_id = plan_resp.json()["plan_id"]

    register_executor("run_python", _stub_executor)

    # Intruder from tenant-B -> 403 CROSS_TENANT_DENIED ...
    _switch(gate_client, EXEC_TENANT_B)
    intruder = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id},
        headers={"Idempotency-Key": "key-intruder"},
    )
    assert intruder.status_code == 403
    assert intruder.json()["detail"]["code"] == agent_exec.CROSS_TENANT_DENIED

    # ...and the owner's later execution proves nothing was poisoned.
    _switch(gate_client, EXEC_TENANT_A)
    owner = gate_client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": plan_id},
        headers={"Idempotency-Key": "key-owner-after"},
    )
    assert owner.status_code == 200, owner.text
    assert owner.json()["data"]["execution_id"]


def test_idempotency_key_cannot_cross_plans(client):
    """A key reserved for plan A refuses to authorise execution of plan B."""
    s1, s2 = "sess-cross-a", "sess-cross-b"
    _session_auto_approve[s1] = True
    _session_auto_approve[s2] = True
    p1 = _post_plan(
        client, {"tool": "run_python", "args": {"goal": "one"}, "session_id": s1}
    ).json()
    p2 = _post_plan(
        client, {"tool": "run_python", "args": {"goal": "two"}, "session_id": s2}
    ).json()

    calls: list[str] = []

    async def _counting(args, ctx):
        calls.append(ctx["execution_id"])
        return {"ok": True}

    register_executor("run_python", _counting)

    shared_key = "key-cross-plans"
    first = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": p1["plan_id"]},
        headers={**_auth(), "Idempotency-Key": shared_key},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/agent-exec/execute",
        json={"plan_id": p2["plan_id"]},
        headers={**_auth(), "Idempotency-Key": shared_key},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert len(calls) == 1  # plan B was NEVER executed
