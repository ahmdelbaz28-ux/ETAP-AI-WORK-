"""Tests for api/approvals.py — Approval Gateway (P2).

Covers:
- mutating + session auto-approve ON  -> auto_approved
- critical + session auto-approve ON  -> still pending
- maker-checker: critical self-approval blocked (MAKER_CHECKER_VIOLATION),
  approval by a different engineer succeeds
- TTL expiry: overdue pending -> expired; execution refused
- Idempotency-Key on create: same key twice -> exactly one action
- Idempotency-Key on resolve: same decision twice -> identical result
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import api.approvals as approvals_mod
from api.approvals import APPROVAL_TTL_SECONDS, PendingAction
from api.dependencies import CurrentUser, get_current_user_from_header
from api.dual_control import MAKER_CHECKER_VIOLATION

MAKER = CurrentUser(
    user_id="maker-user-id",
    username="maker",
    email="maker@example.com",
    role="engineer",
)
CHECKER = CurrentUser(
    user_id="checker-user-id",
    username="checker",
    email="checker@example.com",
    role="senior_engineer",
)


@pytest.fixture()
def client():
    """Minimal FastAPI app with only the approvals + session routers."""
    app = FastAPI()
    app.include_router(approvals_mod.router)
    app.include_router(approvals_mod.session_router)

    # Default authenticated user = maker; tests override to CHECKER as needed.
    app.dependency_overrides[get_current_user_from_header] = lambda: MAKER

    # Fresh in-memory auto-approve registry per test.
    approvals_mod._session_auto_approve.clear()

    with TestClient(app) as c:
        yield c


def _propose(client: TestClient, tool: str = "run_python", session_id: str = "sess-1", **kw):
    return client.post(
        "/api/v1/approvals",
        json={"session_id": session_id, "tool": tool, "args": kw.pop("args", {"code": "x=1"})},
        **kw,
    )


# ---------------------------------------------------------------------------
# Classification / auto-approve behaviour
# ---------------------------------------------------------------------------


class TestAutoApprove:
    def test_mutating_with_auto_approve_on_is_auto_approved(self, client):
        r = client.put("/api/v1/session/auto-approve", json={"session_id": "s1", "enabled": True})
        assert r.status_code == 200 and r.json()["data"]["enabled"] is True

        resp = _propose(client, tool="run_python", session_id="s1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["risk_class"] == "mutating"
        assert data["status"] == "approved"  # auto-approved straight through

    def test_critical_with_auto_approve_on_still_pending(self, client):
        client.put("/api/v1/session/auto-approve", json={"session_id": "s2", "enabled": True})
        resp = _propose(client, tool="provider-settings-tool", session_id="s2")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["risk_class"] == "critical"
        assert data["status"] == "pending"

    def test_mutating_without_auto_approve_is_pending(self, client):
        resp = _propose(client, tool="run_python", session_id="s3")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "pending"

    def test_read_tool_auto_approved_without_toggle(self, client):
        resp = _propose(client, tool="weather-tool", session_id="s4")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["risk_class"] == "read"
        assert data["status"] == "approved"


class TestMakerChecker:
    def _create_critical_pending(self, client) -> str:
        resp = _propose(client, tool="provider-settings-tool", session_id="mc")
        assert resp.json()["data"]["status"] == "pending"
        return resp.json()["data"]["id"]

    def test_self_approval_of_critical_blocked(self, client):
        action_id = self._create_critical_pending(client)
        # Same user (MAKER via default override) tries to approve own request.
        resp = client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "approve"})
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["code"] == MAKER_CHECKER_VIOLATION

    def test_second_engineer_can_approve_critical(self, client):
        action_id = self._create_critical_pending(client)
        client.app.dependency_overrides[get_current_user_from_header] = lambda: CHECKER
        resp = client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "approve"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "approved"
        assert data["decided_by_user_id"] == CHECKER.user_id
        assert data["requested_by_user_id"] == MAKER.user_id


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


class TestTtlExpiry:
    def test_ttl_is_five_minutes(self):
        assert APPROVAL_TTL_SECONDS == 300

    @pytest.mark.asyncio
    async def test_expired_action_refuses_execution(self, client):
        resp = _propose(client, tool="provider-settings-tool", session_id="ttl")
        action_id = resp.json()["data"]["id"]

        # Force the TTL deadline into the past (simulate elapsed 5 minutes).
        from sqlalchemy import select

        from api.database import async_session

        past = datetime.now(UTC) - timedelta(seconds=1)
        async with async_session() as session:
            res = await session.execute(select(PendingAction).where(PendingAction.id == action_id))
            action = res.scalar_one()
            action.expires_at = past
            await session.commit()

        # Listing pending must sweep it into 'expired'...
        listing = client.get("/api/v1/approvals/pending", params={"session_id": "ttl"})
        assert listing.status_code == 200
        assert listing.json()["total"] == 0

        # ...and resolving it must refuse execution.
        resolve = client.post(
            f"/api/v1/approvals/{action_id}/resolve", json={"decision": "approve"}
        )
        assert resolve.status_code == 200
        body = resolve.json()
        assert body["success"] is False
        assert body["error"]["code"] == "ALREADY_RESOLVED"
        assert body["error"]["status"] == "expired"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_same_create_key_twice_creates_one_action(self, client):
        key = "idem-create-001"
        first = _propose(
            client,
            tool="run_python",
            session_id="idem",
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 200
        second = _propose(
            client,
            tool="run_python",
            session_id="idem",
            headers={"Idempotency-Key": key},
        )
        assert second.status_code == 200

        body = second.json()
        assert body.get("idempotent_replay") is True
        assert body["data"]["id"] == first.json()["data"]["id"]

        # Exactly one row persisted.
        from sqlalchemy import func, select

        from api.database import async_session

        async with async_session() as session:
            total = (
                await session.execute(
                    select(func.count())
                    .select_from(PendingAction)
                    .where(PendingAction.session_id == "idem")
                )
            ).scalar()
        assert total == 1

    def test_same_resolve_decision_twice_is_idempotent(self, client):
        resp = _propose(client, tool="run_python", session_id="idem-r")
        action_id = resp.json()["data"]["id"]

        key = "idem-resolve-001"
        first = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 200
        assert first.json()["data"]["status"] == "approved"

        second = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"Idempotency-Key": key},
        )
        assert second.status_code == 200
        body = second.json()
        assert body.get("idempotent_replay") is True
        assert body["data"] == first.json()["data"]

    def test_resolve_without_key_twice_reports_already_resolved(self, client):
        """Without an Idempotency-Key the guard still prevents double-decide."""
        resp = _propose(client, tool="weather-tool", session_id="nokey")
        action_id = resp.json()["data"]["id"]
        first = client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "reject"})
        second = client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "reject"})
        assert first.status_code == 200
        assert second.json()["success"] is False
        assert second.json()["error"]["code"] == "ALREADY_RESOLVED"


# ---------------------------------------------------------------------------
# Audit trail integration
# ---------------------------------------------------------------------------


class TestAuditIntegration:
    def test_lifecycle_events_reach_dual_control_audit_trail(self, client):
        from api.dual_control import _audit_trail

        before = len(_audit_trail)
        resp = _propose(client, tool="provider-settings-tool", session_id="audit")
        action_id = resp.json()["data"]["id"]
        client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "reject"})

        events = [e["event_type"] for e in _audit_trail[before:]]
        assert "PROPOSED" in events
        assert "PENDING" in events
        assert "REJECTED" in events


# ---------------------------------------------------------------------------
# Security Gate (P2): tenant isolation on the Approval Gateway
#
# Users A and B belong to different tenants. The tenant travels ONLY with
# the authenticated user (server-stamped), never from the request body.
# ---------------------------------------------------------------------------

TENANT_A_USER = CurrentUser(
    user_id="maker-a",
    username="maker_a",
    email="maker_a@example.com",
    role="engineer",
    tenant_id="tenant-A",
)
TENANT_B_INTRUDER = CurrentUser(
    user_id="intruder-b",
    username="intruder_b",
    email="intruder_b@example.com",
    role="engineer",
    tenant_id="tenant-B",
)


class TestTenantIsolation:
    def test_cross_tenant_pending_isolation(self, client):
        """GET /pending must never disclose another tenant's actions."""
        # Propose as tenant-A...
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        resp = _propose(client, tool="run_python", session_id="iso")
        assert resp.status_code == 200
        action_id = resp.json()["data"]["id"]

        # ...owner sees it in their pending list...
        listing_a = client.get("/api/v1/approvals/pending", params={"session_id": "iso"})
        assert listing_a.status_code == 200
        assert listing_a.json()["total"] == 1
        assert [a["id"] for a in listing_a.json()["data"]] == [action_id]

        # ...while tenant-B sees NOTHING for the very same session id.
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_B_INTRUDER
        listing_b = client.get("/api/v1/approvals/pending", params={"session_id": "iso"})
        assert listing_b.status_code == 200
        assert listing_b.json()["total"] == 0
        assert listing_b.json()["data"] == []

    def test_cross_tenant_resolve_denied(self, client):
        """POST /resolve from another tenant -> 403 CROSS_TENANT_FORBIDDEN,
        audited, and the action stays pending for its rightful owner."""
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        resp = _propose(client, tool="provider-settings-tool", session_id="xres")
        action_id = resp.json()["data"]["id"]

        from api.dual_control import _audit_trail

        marker = len(_audit_trail)

        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_B_INTRUDER
        denied = client.post(f"/api/v1/approvals/{action_id}/resolve", json={"decision": "approve"})
        assert denied.status_code == 403
        detail = denied.json()["detail"]
        assert detail["code"] == approvals_mod.CROSS_TENANT_FORBIDDEN == "CROSS_TENANT_FORBIDDEN"

        events = [e["event_type"] for e in _audit_trail[marker:]]
        assert "CROSS_TENANT_RESOLVE_DENIED" in events

        # No partial state was disclosed or written: owner still sees 'pending'.
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        back = client.get("/api/v1/approvals/pending", params={"session_id": "xres"})
        assert back.json()["total"] == 1
        assert back.json()["data"][0]["status"] == "pending"

    def test_create_is_tenant_scoped_against_body_spoofing(self, client):
        """A caller cannot forge another tenant onto a proposed action."""
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        resp = client.post(
            "/api/v1/approvals",
            json={
                "session_id": "spoof",
                "tool": "run_python",
                "args": {"code": "x=1"},
                "tenant_id": "tenant-B",  # spoofed — must be ignored
            },
        )
        assert resp.status_code == 200
        # Tenant is stamped exclusively from the authenticated caller.
        assert resp.json()["data"]["tenant_id"] == TENANT_A_USER.tenant_id

    def test_idempotent_resolve_replay_is_tenant_scoped(self, client):
        """A stored resolve-response may only be replayed within the SAME
        tenant; another tenant reusing the key gets 403, not the payload."""
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        # mutating tool -> action stays 'pending' until the explicit resolve
        action_id = _propose(client, tool="run_python", session_id="treplay").json()["data"]["id"]
        key = "resolve-key-TS"
        first = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 200
        assert first.json()["success"] is True
        assert first.json()["data"]["status"] == "approved"

        # Same tenant: legitimate replay.
        replay = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"Idempotency-Key": key},
        )
        assert replay.json().get("idempotent_replay") is True

        # Different tenant: NEVER replays across the boundary.
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_B_INTRUDER
        foreign = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"Idempotency-Key": key},
        )
        assert foreign.status_code == 403
        assert foreign.json()["detail"]["code"] == approvals_mod.CROSS_TENANT_FORBIDDEN
        assert "idempotent_replay" not in foreign.json()

    @pytest.mark.asyncio
    async def test_same_key_creates_two_tenant_separate_actions(self, client):
        """Create-replay is tenant-scoped: the same key reused by tenant B
        results in a NEW action under B, not a replay of A's action."""
        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_A_USER
        key = "create-key-TS"
        a_resp = client.post(
            "/api/v1/approvals",
            json={
                "session_id": "ts-create",
                "tool": "weather-tool",
                "args": {"city": "Riyadh"},
            },
            headers={"Idempotency-Key": key},
        )
        assert a_resp.status_code == 200
        a_id = a_resp.json()["data"]["id"]

        client.app.dependency_overrides[get_current_user_from_header] = lambda: TENANT_B_INTRUDER
        b_resp = client.post(
            "/api/v1/approvals",
            json={
                "session_id": "ts-create",
                "tool": "weather-tool",
                "args": {"city": "Riyadh"},
            },
            headers={"Idempotency-Key": key},
        )
        assert b_resp.status_code == 200
        b_body = b_resp.json()
        assert b_body.get("idempotent_replay") is not True  # no cross-tenant replay
        assert b_body["data"]["id"] != a_id
        assert b_body["data"]["tenant_id"] == TENANT_B_INTRUDER.tenant_id
