"""
tests/test_scada_control_gateway.py — Tests for SCADA Dual-Control & Interlock Gateway.

Verifies:
- Operator/Viewer cannot propose control commands (403 INSUFFICIENT_PERMISSIONS)
- Engineer can propose control command (202 Accepted, status=pending_approval)
- Anti-Self-Approval: Requester cannot approve their own action (403 MAKER_CHECKER_VIOLATION)
- Admin can approve and execute command with Verify-by-Readback
- Admin can reject command
- Cross-tenant actions are strictly forbidden (403 CROSS_TENANT_FORBIDDEN)
- Idempotency-Key guarantees safe retry replays
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.dependencies import CurrentUser, get_current_user_from_header
from api.projects import Project
from api.scada import router as scada_router
from scada.control_executor import scada_executor
from scada.models import BreakerState, SignalQuality

UTC = timezone.utc

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(scada_router)
    return test_app


@pytest.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Seed an active default project with branches for What-If interlock pre-flight analysis
        default_proj = Project(
            id="proj_default_ot",
            tenant_id=None,
            name="Substation Grid",
            description="Default electrical network for SCADA What-If analysis",
            created_by="system",
            status="active",
            system_config={
                "buses": [
                    {"id": "BUS_1", "nominal_kv": 11.0, "type": "slack"},
                    {"id": "BUS_2", "nominal_kv": 11.0, "type": "pq"},
                ],
                "branches": [
                    {
                        "id": "CB_001",
                        "name": "CB_001",
                        "status": 1,
                        "from_bus": "BUS_1",
                        "to_bus": "BUS_2",
                        "r_ohm": 0.01,
                        "x_ohm": 0.05,
                        "rated_current_a": 630.0,
                    }
                ],
            },
        )
        session.add(default_proj)
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client(app: FastAPI, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-api-key")
    import api.dependencies as deps

    monkeypatch.setattr(deps, "API_KEY", "test-api-key")

    async def _override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = _override_get_db

    # Default to engineer role
    app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="user_eng_1",
        username="engineer1",
        email="eng1@substation.ot",
        role="engineer",
        tenant_id="tenant_substation_north",
    )

    # Reset simulated device states
    scada_executor.set_device_state(
        "CB_001",
        status=BreakerState.CLOSED.value,
        quality=SignalQuality.GOOD.value,
        control_mode="REMOTE",
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestSCADAControlGateway:
    def test_operator_cannot_propose_control(self, client: TestClient, app: FastAPI) -> None:
        """Operators have view-only access; control proposals must be 403."""
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="user_op_1",
            username="operator1",
            email="op1@substation.ot",
            role="operator",
            tenant_id="tenant_substation_north",
        )

        payload = {
            "device_id": "CB_001",
            "protocol": "opc_ua",
            "action_type": "breaker_open",
            "target_value": 0,
            "reason": "Routine isolation",
        }
        resp = client.post("/api/v1/scada/control/propose", json=payload, headers={"X-API-Key": "test-api-key"})
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "INSUFFICIENT_PERMISSIONS"

    def test_engineer_propose_control_success(self, client: TestClient) -> None:
        """Engineer can propose control command and receives 202 with action_id."""
        payload = {
            "device_id": "CB_001",
            "protocol": "opc_ua",
            "action_type": "breaker_open",
            "target_value": 0,
            "reason": "Scheduled feeder maintenance",
        }
        resp = client.post(
            "/api/v1/scada/control/propose",
            json=payload,
            headers={"X-API-Key": "test-api-key", "Idempotency-Key": "idemp_prop_01"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "pending_approval"
        assert "action_id" in data
        action_id = data["action_id"]

        # Check pending list
        pending_resp = client.get("/api/v1/scada/control/pending", headers={"X-API-Key": "test-api-key"})
        assert pending_resp.status_code == 200
        pending_data = pending_resp.json()
        assert pending_data["total"] >= 1
        assert any(item["action_id"] == action_id for item in pending_data["data"])

    def test_maker_checker_anti_self_approval(self, client: TestClient, app: FastAPI) -> None:
        """Admin cannot approve their own proposed action (MAKER_CHECKER_VIOLATION)."""
        # Admin proposes an action
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_john",
            username="admin_john",
            email="john@substation.ot",
            role="admin",
            tenant_id="tenant_substation_north",
        )

        payload = {
            "device_id": "CB_001",
            "protocol": "opc_ua",
            "action_type": "breaker_open",
            "target_value": 0,
            "reason": "Emergency bus de-energization",
        }
        prop_resp = client.post("/api/v1/scada/control/propose", json=payload, headers={"X-API-Key": "test-api-key"})
        assert prop_resp.status_code == 202
        action_id = prop_resp.json()["action_id"]

        # Same admin tries to approve
        resolve_payload = {"decision": "approve", "reason": "Self approving my command"}
        resolve_resp = client.post(
            f"/api/v1/scada/control/{action_id}/resolve",
            json=resolve_payload,
            headers={"X-API-Key": "test-api-key"},
        )
        assert resolve_resp.status_code == 403
        data = resolve_resp.json()
        assert data["detail"]["code"] == "MAKER_CHECKER_VIOLATION"

    def test_independent_admin_approves_and_executes(self, client: TestClient, app: FastAPI) -> None:
        """Independent admin approves: command executes and verifies readback."""
        # 1. Engineer proposes
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="engineer_sarah",
            username="sarah_eng",
            email="sarah@substation.ot",
            role="engineer",
            tenant_id="tenant_substation_north",
        )
        payload = {
            "device_id": "CB_001",
            "protocol": "opc_ua",
            "action_type": "breaker_open",
            "target_value": 0,
            "reason": "Isolate line L1",
        }
        prop_resp = client.post("/api/v1/scada/control/propose", json=payload, headers={"X-API-Key": "test-api-key"})
        assert prop_resp.status_code == 202
        action_id = prop_resp.json()["action_id"]

        # 2. Independent Admin approves
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_michael",
            username="michael_adm",
            email="michael@substation.ot",
            role="admin",
            tenant_id="tenant_substation_north",
        )
        resolve_payload = {"decision": "approve", "reason": "Approved after peer check"}
        resolve_resp = client.post(
            f"/api/v1/scada/control/{action_id}/resolve",
            json=resolve_payload,
            headers={"X-API-Key": "test-api-key"},
        )
        assert resolve_resp.status_code == 200
        res_data = resolve_resp.json()
        assert res_data["success"] is True
        assert res_data["status"] == "completed"
        assert res_data["result"]["readback_verified"] is True
        assert res_data["result"]["final_state"] == "OPEN"

        # 3. Status endpoint reflects completed
        status_resp = client.get(f"/api/v1/scada/control/{action_id}/status", headers={"X-API-Key": "test-api-key"})
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] == "completed"

    def test_admin_rejects_control_action(self, client: TestClient, app: FastAPI) -> None:
        """Admin rejects proposed control command."""
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="eng_user", username="eng", email="eng@ot.local", role="engineer", tenant_id="tenant_test"
        )
        prop_resp = client.post(
            "/api/v1/scada/control/propose",
            json={
                "device_id": "CB_001",
                "protocol": "opc_ua",
                "action_type": "breaker_open",
                "target_value": 0,
                "reason": "Test proposal",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        action_id = prop_resp.json()["action_id"]

        # Admin rejects
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_user", username="adm", email="adm@ot.local", role="admin", tenant_id="tenant_test"
        )
        resolve_resp = client.post(
            f"/api/v1/scada/control/{action_id}/resolve",
            json={"decision": "reject", "reason": "Network load too high right now"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert resolve_resp.status_code == 200
        data = resolve_resp.json()
        assert data["status"] == "rejected"

    def test_cross_tenant_control_blocked(self, client: TestClient, app: FastAPI) -> None:
        """Admin from Tenant B cannot resolve or see action from Tenant A."""
        # Tenant A engineer proposes
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="eng_tenant_a", username="eng_a", email="a@ot.local", role="engineer", tenant_id="tenant_A"
        )
        prop_resp = client.post(
            "/api/v1/scada/control/propose",
            json={
                "device_id": "CB_001",
                "protocol": "opc_ua",
                "action_type": "breaker_open",
                "target_value": 0,
                "reason": "Tenant A maintenance",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        action_id = prop_resp.json()["action_id"]

        # Tenant B admin attempts to resolve
        app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
            user_id="admin_tenant_b", username="admin_b", email="b@ot.local", role="admin", tenant_id="tenant_B"
        )
        resolve_resp = client.post(
            f"/api/v1/scada/control/{action_id}/resolve",
            json={"decision": "approve"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert resolve_resp.status_code == 403
        assert resolve_resp.json()["detail"]["code"] == "CROSS_TENANT_FORBIDDEN"

    def test_idempotency_replay_propose(self, client: TestClient) -> None:
        """Retrying propose with same Idempotency-Key returns identical action_id."""
        payload = {
            "device_id": "CB_001",
            "protocol": "opc_ua",
            "action_type": "breaker_open",
            "target_value": 0,
            "reason": "Idempotency verification",
        }
        headers = {"X-API-Key": "test-api-key", "Idempotency-Key": "fixed-idemp-key-123"}
        resp1 = client.post("/api/v1/scada/control/propose", json=payload, headers=headers)
        assert resp1.status_code == 202
        action_id_1 = resp1.json()["action_id"]

        resp2 = client.post("/api/v1/scada/control/propose", json=payload, headers=headers)
        assert resp2.status_code == 200 or resp2.status_code == 202
        assert resp2.json()["action_id"] == action_id_1
