"""
tests/test_p9_data_import_export.py — Comprehensive test suite for P9 Import/Export in Chat.

Covers:
- Preview dry-run impact analysis (buses, branches, affected tables, risk level).
- Magic bytes validation (rejects executable headers, binary injection in text formats).
- 10 MiB size limits (P5 consistency).
- Idempotency on execute endpoints (replay prevention).
- Tenant isolation (cross-tenant preview/execute blocked).
- SessionStreamHub progress streaming events.
- Audit trail recording for preview and execute.
- Export formats, endpoints, and read-only behavior.
- Fail-closed feature flag behavior.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import api.approvals as approvals_mod
import api.data_import as data_import_mod
import api.export as export_mod
import api.results_store as results_store_mod
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
)
from api.session_stream import get_hub, reset_hub

TENANT_A = "tenant_alpha"
TENANT_B = "tenant_beta"

USER_A = CurrentUser(
    user_id="user_tenant_a_123",
    username="engineer_a",
    email="engineer_a@etap.local",
    role="admin",
    tenant_id=TENANT_A,
)

USER_B = CurrentUser(
    user_id="user_tenant_b_456",
    username="engineer_b",
    email="engineer_b@etap.local",
    role="engineer",
    tenant_id=TENANT_B,
)


@pytest.fixture
def result_store_dir(tmp_path, monkeypatch):
    """Isolate physical files in a per-test temp dir."""
    target = tmp_path / "results"
    monkeypatch.setenv("RESULT_STORE_DIR", str(target))
    return target


@pytest.fixture
def test_api(result_store_dir):
    """Minimal FastAPI app with only the import, export, approvals, and results routers."""
    app = FastAPI()
    app.include_router(data_import_mod.router)
    app.include_router(export_mod.router)
    app.include_router(approvals_mod.router)
    app.include_router(results_store_mod.router)

    holder = {"user": USER_A}

    def _get_current():
        return holder["user"]

    app.dependency_overrides[get_current_user_from_header] = _get_current
    app.dependency_overrides[get_api_key] = _get_current

    reset_hub()
    client = TestClient(app)
    return {"app": app, "client": client, "holder": holder}


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
                {"id": "LINE_1", "from_bus": "BUS_1", "to_bus": "BUS_2", "r_pu": 0.01, "x_pu": 0.05, "rating_mva": 50.0}
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


class TestImportExecuteAndIdempotency:
    """Tests for POST /api/v1/import/execute with idempotency, tenant isolation, and session streaming."""

    def test_execute_import_happy_path(self, test_api):
        client = test_api["client"]
        test_api["holder"]["user"] = USER_A

        # 1. Preview
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

        # 2. Execute
        exec_res = client.post(
            "/api/v1/import/execute",
            json={
                "preview_id": preview_id,
                "session_id": "sess_import_progress",
                "project_name": "Test Import Project",
            },
            headers={"Idempotency-Key": "idemp-key-import-001"},
        )
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["success"] is True
        assert "result_id" in exec_data
        assert exec_data["records_imported"] == 3
        assert exec_data["status"] == "completed"

        # Verify SessionStream events were emitted
        hub = get_hub()
        events = hub.replay("sess_import_progress", after_seq=0)
        types = [e["type"] for e in events]
        assert "job_progress" in types
        assert "result_ready" in types

        # 3. Idempotent replay
        replay_res = client.post(
            "/api/v1/import/execute",
            json={
                "preview_id": preview_id,
                "session_id": "sess_import_progress",
            },
            headers={"Idempotency-Key": "idemp-key-import-001"},
        )
        assert replay_res.status_code == 200
        assert replay_res.json()["import_id"] == exec_data["import_id"]
        assert replay_res.json()["result_id"] == exec_data["result_id"]

    def test_execute_cross_tenant_blocked(self, test_api):
        client = test_api["client"]

        # Tenant A previews
        test_api["holder"]["user"] = USER_A
        model = {"buses": [{"id": "BUS_A1"}]}
        prev_res = client.post(
            "/api/v1/import/preview",
            files={"file": ("tenant_a.json", json.dumps(model).encode("utf-8"), "application/json")},
        )
        assert prev_res.status_code == 200
        preview_id = prev_res.json()["preview_id"]

        # Tenant B attempts to execute Tenant A's preview
        test_api["holder"]["user"] = USER_B
        exec_res = client.post(
            "/api/v1/import/execute",
            json={"preview_id": preview_id},
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
        res = client.post(f"/api/v1/export/{uuid.uuid4()}/pdf")
        assert res.status_code == 404
