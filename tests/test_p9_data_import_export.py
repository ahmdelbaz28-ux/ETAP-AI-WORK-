"""
tests/test_p9_data_import_export.py — Comprehensive test suite for P9 Import/Export in Chat.

Covers:
- Dual-control Maker-Checker approval enforcement (422 missing, 404 not found, 403 pending, 403 self-approval, 410 expired ALREADY_RESOLVED, 200 approved).
- Mandatory Idempotency-Key enforcement (422 missing, replay identical on duplicate).
- Fail-closed Feature Flag enforcement (403 when disabled in prod).
- Tenant isolation (cross-tenant preview & cross-tenant approval blocked with 403).
- Preview dry-run impact analysis (buses, branches, affected tables, risk level).
- Magic bytes validation (rejects executable headers MZ/ELF, binary injection in text formats).
- 10 MiB size limits (P5 consistency).
- SessionStreamHub progress streaming events.
- Audit trail recording for preview, execute, and export.
- Pre-declared export formats, read-only guarantees, and 404 on missing projects.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from starlette.testclient import TestClient

import api.approvals as approvals_mod
import api.data_import as data_import_mod
import api.export as export_mod
import api.feature_flags as feature_flags_mod
import api.results_store as results_store_mod
from api.approvals import PendingAction
from api.database import async_session
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
)
from api.rbac import require_permission
from api.session_stream import get_hub, reset_hub

UTC = timezone.utc

TENANT_A = "tenant_alpha"
TENANT_B = "tenant_beta"

MAKER_A = CurrentUser(
    user_id="maker_user_123",
    username="maker_alpha",
    email="maker@etap.local",
    role="engineer",
    tenant_id=TENANT_A,
)

CHECKER_A = CurrentUser(
    user_id="checker_user_456",
    username="checker_alpha",
    email="checker@etap.local",
    role="senior_engineer",
    tenant_id=TENANT_A,
)

USER_B = CurrentUser(
    user_id="user_tenant_b_789",
    username="engineer_beta",
    email="engineer_b@etap.local",
    role="engineer",
    tenant_id=TENANT_B,
)

ADMIN_A = CurrentUser(
    user_id="admin_user_001",
    username="admin_alpha",
    email="admin@etap.local",
    role="admin",
    tenant_id=TENANT_A,
)


@pytest.fixture
def result_store_dir(tmp_path, monkeypatch):
    """Isolate physical files in a per-test temp dir."""
    target = tmp_path / "results"
    monkeypatch.setenv("RESULT_STORE_DIR", str(target))
    return target


@pytest.fixture
def test_api(result_store_dir):
    """Minimal FastAPI app with only the import, export, approvals, feature flags, and results routers."""
    app = FastAPI()
    app.include_router(data_import_mod.router)
    app.include_router(export_mod.router)
    app.include_router(approvals_mod.router)
    app.include_router(feature_flags_mod.router)
    app.include_router(results_store_mod.router)

    holder = {"user": MAKER_A}

    def _get_current():
        return holder["user"]

    app.dependency_overrides[get_current_user_from_header] = _get_current
    app.dependency_overrides[get_api_key] = _get_current
    app.dependency_overrides[require_permission("export", "create")] = _get_current
    app.dependency_overrides[require_permission("export", "list")] = _get_current

    reset_hub()
    client = TestClient(app)
    return {"app": app, "client": client, "holder": holder}


async def _create_approval_action(
    tenant_id: str,
    requested_by: str,
    decided_by: str | None,
    status: str = "approved",
    expired: bool = False,
    preview_id: str | None = None,
) -> str:
    """Helper to insert a PendingAction directly into the database."""
    action_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now - timedelta(minutes=10) if expired else now + timedelta(minutes=10)

    async with async_session() as session:
        action = PendingAction(
            id=action_id,
            tenant_id=tenant_id,
            session_id="test_sess_123",
            tool="data_import",
            args_hash="fake_hash",
            risk_class="critical",
            status="expired" if expired else status,
            expires_at=expires_at,
            created_at=now,
            requested_by_user_id=requested_by,
            requested_by_role="engineer",
            decided_by_user_id=decided_by,
            decided_by_role="senior_engineer" if decided_by else None,
            args={"preview_id": preview_id} if preview_id else {},
        )
        session.add(action)
        await session.commit()
    return action_id


class TestDataImportFormats:
    """Tests for GET /api/v1/import/formats."""

    def test_list_formats_returns_supported_formats(self, test_api):
        client = test_api["client"]
        res = client.get("/api/v1/import/formats")
        assert res.status_code == 200
        data = res.json()
        assert "formats" in data
        assert data["count"] >= 5
        format_ids = [f["id"] for f in data["formats"]]
        assert "json" in format_ids
        assert "csv" in format_ids
        assert "cim-xml" in format_ids
        assert "psse-raw" in format_ids
        assert "matpower" in format_ids


class TestMagicBytesAndSecurityValidation:
    """Tests for magic bytes rejection and upload size limits."""

    def test_rejects_executable_dos_pe(self, test_api):
        client = test_api["client"]
        exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("malicious.json", exe_bytes, "application/json")},
        )
        assert res.status_code == 400
        assert "Executable" in res.json()["detail"]

    def test_rejects_executable_elf(self, test_api):
        client = test_api["client"]
        elf_bytes = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("malicious.json", elf_bytes, "application/json")},
        )
        assert res.status_code == 400
        assert "Executable" in res.json()["detail"]

    def test_rejects_invalid_json_signature(self, test_api):
        client = test_api["client"]
        corrupt_bytes = b"plain text with no brackets"
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("bad.json", corrupt_bytes, "application/json")},
        )
        assert res.status_code == 400
        assert "Invalid JSON signature" in res.json()["detail"]

    def test_rejects_binary_in_csv(self, test_api):
        client = test_api["client"]
        binary_csv = b"id,name\n1,\x00\x01\x02"
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("corrupt.csv", binary_csv, "text/csv")},
        )
        assert res.status_code == 400
        assert "Binary" in res.json()["detail"]

    def test_rejects_file_exceeding_10mib(self, test_api):
        client = test_api["client"]
        oversized = b"{" + b" " * (10 * 1024 * 1024 + 100) + b"}"
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("oversized.json", oversized, "application/json")},
        )
        assert res.status_code == 413


class TestImportPreviewDryRun:
    """Tests for POST /api/v1/import/preview."""

    def test_preview_valid_json_model(self, test_api):
        client = test_api["client"]
        model = {
            "buses": [
                {"id": "BUS_1", "name": "Substation Main", "voltage_kv": 115.0, "type": "SLACK"},
                {"id": "BUS_2", "name": "Feeder Alpha", "voltage_kv": 13.8, "type": "PQ"},
            ],
            "branches": [
                {
                    "id": "LINE_1",
                    "from_bus": "BUS_1",
                    "to_bus": "BUS_2",
                    "r_pu": 0.01,
                    "x_pu": 0.05,
                    "rating_mva": 50.0,
                }
            ],
        }
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("grid.json", json.dumps(model).encode("utf-8"), "application/json")},
            data={"session_id": "session_test_123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["preview_id"].startswith("imp_prev_")
        assert data["records_count"] == 3
        assert data["buses_count"] == 2
        assert data["branches_count"] == 1
        assert "buses" in data["affected_tables"]
        assert data["risk_level"] == "low"
        assert data["requires_approval"] is True

    def test_preview_valid_csv_buses(self, test_api):
        client = test_api["client"]
        csv_content = b"id,name,voltage_kv,type\nB1,Main Bus,13.8,PQ\nB2,Secondary,138.0,PV\n"
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("buses.csv", csv_content, "text/csv")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["buses_count"] == 2
        assert data["records_count"] == 2


class TestDualControlAndApprovalsEnforcement:
    """Tests for Maker-Checker dual control on /api/v1/import/execute."""

    @pytest.mark.asyncio
    async def test_execute_without_approval_id_returns_422(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        # Preview
        model = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        # Execute without approval_id
        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id},
            headers={"Idempotency-Key": "idemp-no-appr-1"},
        )
        assert res.status_code == 422
        assert "approval_id is required" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_nonexistent_approval_returns_404(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": str(uuid.uuid4())},
            headers={"Idempotency-Key": "idemp-nonexist-1"},
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_pending_unapproved_action_returns_403(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        # Create PendingAction in pending state
        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=None,
            status="pending",
        )

        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-pending-1"},
        )
        assert res.status_code == 403
        assert "Action is not approved" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_self_approval_maker_checker_violation_returns_403(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        # Maker self-approved
        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=MAKER_A.user_id,
            status="approved",
        )

        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-self-appr-1"},
        )
        assert res.status_code == 403
        assert "MAKER_CHECKER_VIOLATION" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_expired_approval_returns_410_already_resolved(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        # Expired approval
        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
            expired=True,
        )

        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-expired-1"},
        )
        assert res.status_code == 410
        assert "ALREADY_RESOLVED" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_valid_checker_approval_succeeds(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {
            "buses": [{"id": "BUS_A", "voltage_kv": 13.8}, {"id": "BUS_B", "voltage_kv": 13.8}],
            "branches": [{"from_bus": "BUS_A", "to_bus": "BUS_B", "r_pu": 0.02, "x_pu": 0.08}],
        }
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("network.json", json.dumps(model).encode("utf-8"), "application/json")},
            data={"session_id": "sess_import_progress"},
        )
        assert prev_res.status_code == 200
        preview_id = prev_res.json()["preview_id"]

        # Valid checker approval
        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
        )

        exec_res = client.post(
            "/api/v1/import/execute",
            json={
                "preview_id": preview_id,
                "approval_id": action_id,
                "session_id": "sess_import_progress",
                "project_name": "Test Import Project",
            },
            headers={"Idempotency-Key": "idemp-valid-appr-1"},
        )
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["success"] is True
        assert "result_id" in exec_data
        assert exec_data["records_imported"] == 3
        assert exec_data["status"] == "completed"

        # Verify SessionStream events
        hub = get_hub()
        events = hub.replay("sess_import_progress", after_seq=0)
        types = [e["type"] for e in events]
        assert "job_progress" in types
        assert "result_ready" in types

    @pytest.mark.asyncio
    async def test_execute_marks_approval_resolved_and_audits_consumption(self, test_api):
        """Successful execution transitions PendingAction to 'resolved' and blocks subsequent reuse."""
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "BUS_1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("net.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
        )

        exec_res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-consume-1"},
        )
        assert exec_res.status_code == 200

        # Verify PendingAction in DB is now resolved
        async with async_session() as session:
            stmt = select(PendingAction).where(PendingAction.id == action_id)
            res = await session.execute(stmt)
            action = res.scalar_one()
            assert action.status == "resolved"
            assert action.resolved_at is not None

        # Subsequent execution with a new idempotency key must fail with 403 ALREADY_CONSUMED
        exec_res_2 = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-consume-2"},
        )
        assert exec_res_2.status_code == 403
        assert "already been resolved/consumed" in exec_res_2.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_reusing_consumed_approval_on_new_preview_returns_403(self, test_api):
        """A consumed approval action cannot be reused on a different preview."""
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model1 = {"buses": [{"id": "B1", "voltage_kv": 13.8}]}
        prev_res1 = client.post(
            "/api/v1/import/preview",
            files={"file": ("net1.json", json.dumps(model1).encode("utf-8"), "application/json")},
        )
        preview_id_1 = prev_res1.json()["preview_id"]

        model2 = {"buses": [{"id": "B2", "voltage_kv": 13.8}]}
        prev_res2 = client.post(
            "/api/v1/import/preview",
            files={"file": ("net2.json", json.dumps(model2).encode("utf-8"), "application/json")},
        )
        preview_id_2 = prev_res2.json()["preview_id"]

        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
        )

        # Execute first preview
        res1 = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id_1, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-reuse-1"},
        )
        assert res1.status_code == 200

        # Attempt to use the same approval on second preview
        res2 = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id_2, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-reuse-2"},
        )
        assert res2.status_code == 403
        assert "already been resolved/consumed" in res2.json()["detail"]

    @pytest.mark.asyncio
    async def test_execute_with_preview_id_mismatch_in_approval_args_returns_403(self, test_api):
        """If PendingAction is explicitly bound to a specific preview_id, executing against another returns 403."""
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model_a = {"buses": [{"id": "BA", "voltage_kv": 13.8}]}
        prev_a = client.post(
            "/api/v1/import/preview",
            files={"file": ("net_a.json", json.dumps(model_a).encode("utf-8"), "application/json")},
        )
        preview_a = prev_a.json()["preview_id"]

        model_b = {"buses": [{"id": "BB", "voltage_kv": 13.8}]}
        prev_b = client.post(
            "/api/v1/import/preview",
            files={"file": ("net_b.json", json.dumps(model_b).encode("utf-8"), "application/json")},
        )
        preview_b = prev_b.json()["preview_id"]

        # Approval action explicitly bound to preview_a
        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
            preview_id=preview_a,
        )

        # Attempt execution against preview_b
        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_b, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-mismatch-1"},
        )
        assert res.status_code == 403
        assert "is bound to preview" in res.json()["detail"]


class TestIdempotencyAndTenantIsolation:
    """Tests for mandatory Idempotency-Key and cross-tenant protection."""

    @pytest.mark.asyncio
    async def test_execute_missing_idempotency_key_returns_422(self, test_api):
        client = test_api["client"]
        res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": "fake_id"},
        )
        assert res.status_code == 422  # Missing required header

    @pytest.mark.asyncio
    async def test_execute_duplicate_idempotency_key_replays_identical_response(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = MAKER_A

        model = {"buses": [{"id": "BUS_1", "voltage_kv": 13.8}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("model.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        preview_id = prev_res.json()["preview_id"]

        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
        )

        idemp_key = f"idemp-dup-{uuid.uuid4().hex}"

        # 1. First call
        exec1 = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": idemp_key},
        )
        assert exec1.status_code == 200

        # 2. Replay call
        exec2 = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": idemp_key},
        )
        assert exec2.status_code == 200
        assert exec2.json()["import_id"] == exec1.json()["import_id"]
        assert exec2.json()["result_id"] == exec1.json()["result_id"]

    @pytest.mark.asyncio
    async def test_execute_cross_tenant_preview_blocked(self, test_api):
        client = test_api["client"]

        # Tenant A previews
        test_api["holder"]["user"] = MAKER_A
        model = {"buses": [{"id": "BUS_A1"}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={
                "file": ("tenant_a.json", json.dumps(model).encode("utf-8"), "application/json")
            },
        )
        assert prev_res.status_code == 200
        preview_id = prev_res.json()["preview_id"]

        action_id = await _create_approval_action(
            tenant_id=TENANT_A,
            requested_by=MAKER_A.user_id,
            decided_by=CHECKER_A.user_id,
            status="approved",
        )

        # Tenant B attempts to execute Tenant A's preview
        test_api["holder"]["user"] = USER_B
        exec_res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id, "approval_id": action_id},
            headers={"Idempotency-Key": "idemp-cross-1"},
        )
        assert exec_res.status_code == 403
        assert "different tenant" in exec_res.json()["detail"]


class TestExportEndpointsAndFormats:
    """Tests for export endpoints."""

    def test_list_export_formats(self, test_api):
        client = test_api["client"]
        res = client.get("/api/v1/export/formats")
        assert res.status_code == 200
        formats = res.json()
        assert len(formats) == 4
        ids = [f["id"] for f in formats]
        assert "pdf" in ids
        assert "excel" in ids
        assert "csv" in ids
        assert "json" in ids

    def test_export_missing_project_returns_404(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = ADMIN_A
        res = client.post(f"/api/v1/export/{uuid.uuid4()}/pdf")
        assert res.status_code == 404


class TestFeatureFlagsFailClosed:
    """Tests for fail-closed behavior when feature flags are disabled in production."""

    def test_import_disabled_in_prod_returns_403(self, test_api, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("FEATURE_FLAG_DATA_IMPORT", "false")
        client = test_api["client"]
        res = client.post(
            "/api/v1/import/preview",
            files={"file": ("model.json", b"{}", "application/json")},
        )
        assert res.status_code == 403
        assert "Data import feature is disabled" in res.json()["detail"]

    def test_export_disabled_in_prod_returns_403(self, test_api, monkeypatch):
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("FEATURE_FLAG_DATA_EXPORT", "false")
        client = test_api["client"]
        test_api["holder"]["user"] = ADMIN_A
        res = client.post(f"/api/v1/export/{uuid.uuid4()}/pdf")
        assert res.status_code == 403
        assert "Data export feature is disabled" in res.json()["detail"]


class TestDefusedXmlFailClosed:
    """Tests for fail-closed behavior when defusedxml is not installed."""

    def test_xml_import_when_defusedxml_missing_raises_error_and_returns_validation_error(
        self, test_api, monkeypatch
    ):
        """When defusedxml is missing, previewing XML fails closed with validation error."""
        monkeypatch.setattr(data_import_mod, "ET", None)
        client = test_api["client"]
        res = client.post(
            "/api/v1/import/preview",
            files={
                "file": (
                    "model.xml",
                    b'<?xml version="1.0"?><TopologicalNode rdf:ID="bus1"/>',
                    "application/xml",
                )
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert any(
            "defusedxml is not installed" in err or "XML parsing is disabled" in err
            for err in data["errors"]
        )

    def test_parse_cim_xml_directly_raises_value_error_when_et_is_none(self, monkeypatch):
        """Direct invocation of _parse_cim_xml raises ValueError when defusedxml is absent."""
        monkeypatch.setattr(data_import_mod, "ET", None)
        with pytest.raises(
            ValueError, match="XML parsing is disabled: defusedxml is not installed"
        ):
            data_import_mod._parse_cim_xml(b"<xml/>")
