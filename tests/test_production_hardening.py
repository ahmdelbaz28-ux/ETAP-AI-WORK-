"""Tests for Production Hardening.

Covers:
1. Solver parameters persistence in SQLite/PostgreSQL (no in-memory store)
2. No hardcoded baselines (404 on nonexistent projects/studies, empty lists)
3. Export generator functions (PDF, Excel, CSV, JSON)
4. SCADA 503 response when IEC 61850 bridge is not configured
5. Edit & Re-run execution workflow with revision tracking
"""

from __future__ import annotations

import json
from typing import AsyncGenerator
import pytest
from fastapi.testclient import TestClient

from api.models.solver_parameters import ProjectSolverParameters
from api.projects import Project
from api.routes import app
from api.services.export_generator import (
    generate_csv_export,
    generate_excel_export,
    generate_json_export,
    generate_pdf_export,
)
from api.feature_flags import is_feature_enabled


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_auth_headers() -> dict[str, str]:
    from api.auth import _create_access_token
    from api.csrf import generate_csrf_token

    token = _create_access_token("test-admin-id", role="admin")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


class TestSolverParametersPersistence:
    """Test solver parameters are persisted to database and retrieved correctly."""

    def test_global_solver_parameters_flow(self, client: TestClient):
        # Update global parameters
        payload = {
            "convergence_tolerance": 0.0001,
            "max_iterations": 75,
            "acceleration_factor": 1.4,
        }
        resp = client.put("/api/v1/studies/parameters/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["convergence_tolerance"] == 0.0001
        assert data["max_iterations"] == 75
        assert data["acceleration_factor"] == 1.4

        # Read back
        get_resp = client.get("/api/v1/studies/parameters/")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["convergence_tolerance"] == 0.0001
        assert get_data["max_iterations"] == 75

    def test_project_scoped_solver_parameters_flow(self, client: TestClient):
        proj_id = "test-project-db-persistence"
        payload = {
            "convergence_tolerance": 0.00002,
            "max_iterations": 90,
            "acceleration_factor": 1.25,
        }
        # PUT project parameters
        put_resp = client.put(f"/api/v1/studies/parameters/{proj_id}", json=payload)
        assert put_resp.status_code == 200
        put_data = put_resp.json()
        assert put_data["convergence_tolerance"] == 0.00002
        assert put_data["max_iterations"] == 90

        # GET project parameters
        get_resp = client.get(f"/api/v1/studies/parameters/{proj_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["convergence_tolerance"] == 0.00002
        assert get_data["max_iterations"] == 90
        assert get_data["acceleration_factor"] == 1.25


class TestNoHardcodedBaselines:
    """Verify that no fake baselines are returned."""

    def test_nonexistent_project_returns_404(self, client: TestClient, auth_headers: dict[str, str]):
        # Both removed baselines should return 404
        resp1 = client.get("/api/v1/projects/proj_cairo_west_132kv", headers=auth_headers)
        assert resp1.status_code == 404

        resp2 = client.get("/api/v1/projects/proj_helwan_industrial", headers=auth_headers)
        assert resp2.status_code == 404

    def test_empty_export_history(self, client: TestClient, admin_auth_headers: dict[str, str]):
        # Create a real project first
        create_resp = client.post(
            "/api/v1/projects/",
            json={"name": "Export Test Project", "description": "Testing exports"},
            headers=admin_auth_headers,
        )
        assert create_resp.status_code == 201
        proj_id = create_resp.json()["id"]

        # Export history should return 0 items (no fake exp-baseline-01)
        hist_resp = client.get(f"/api/v1/export/{proj_id}/history", headers=admin_auth_headers)
        assert hist_resp.status_code == 200
        data = hist_resp.json()
        assert data["total"] == 0
        assert data["exports"] == []


class TestExportGenerators:
    """Verify export generators produce valid file binaries and structures."""

    def test_pdf_export_generator(self):
        studies = [
            {
                "study_type": "load_flow",
                "status": "completed",
                "created_at": "2026-09-16T12:00:00Z",
                "results": {"converged": True, "buses": 5},
            }
        ]
        pdf_bytes = generate_pdf_export("Substation Alpha", studies)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 50
        # Must start with standard PDF magic number
        assert pdf_bytes.startswith(b"%PDF")

    def test_excel_export_generator(self):
        studies = [
            {
                "study_type": "short_circuit",
                "status": "completed",
                "created_at": "2026-09-16T12:00:00Z",
                "results": {"ikss_ka": 25.4},
            }
        ]
        excel_bytes = generate_excel_export("Industrial Ring", studies)
        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 50
        # If openpyxl is installed, it is a valid zip (.xlsx) starting with PK
        assert excel_bytes.startswith(b"PK") or b"Industrial Ring" in excel_bytes

    def test_csv_export_generator(self):
        studies = [
            {
                "study_type": "=DDE(command)",  # Formula injection attempt
                "status": "completed",
                "created_at": "2026-09-16T12:00:00Z",
                "results": {"losses": 10},
            }
        ]
        csv_bytes = generate_csv_export("Grid Project", studies)
        csv_text = csv_bytes.decode("utf-8")
        assert "project_name,study_type,status,created_at,results" in csv_text
        # Injected formula character must be sanitized with leading single quote
        assert "'=DDE(command)" in csv_text

    def test_json_export_generator(self):
        studies = [
            {
                "study_type": "arc_flash",
                "status": "completed",
                "created_at": "2026-09-16T12:00:00Z",
                "results": {"incident_energy_cal_cm2": 3.8},
            }
        ]
        json_bytes = generate_json_export("Solar Farm 1", studies)
        data = json.loads(json_bytes.decode("utf-8"))
        assert data["project_name"] == "Solar Farm 1"
        assert len(data["studies"]) == 1
        assert data["studies"][0]["study_type"] == "arc_flash"


class TestSCADABridgeEnforcement:
    """Verify SCADA live endpoint enforces bridge configuration in production_hardening mode."""

    def test_scada_live_without_bridge_returns_503(self, client: TestClient):
        # With production_hardening enabled, live telemetry should return 503 if no live bridge
        assert is_feature_enabled("production_hardening") is True
        resp = client.get("/api/v1/scada/live")
        assert resp.status_code == 503
        data = resp.json()
        assert data["success"] is False
        assert "SCADA bridge not configured" in data["error"]


class TestStudyReRunWorkflow:
    """Verify Edit & Re-run execution creates real study results and revisions."""

    def test_re_run_execution_flow(self, client: TestClient, auth_headers: dict[str, str]):
        # 1. Create a project
        create_resp = client.post(
            "/api/v1/projects/",
            json={"name": "Re-run Test Project", "description": "Testing Re-run pipeline"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        # 2. Re-run study (Revision 1)
        rerun_payload_1 = {
            "project_id": project_id,
            "tool": "load_flow",
            "parameters": {
                "convergence_tolerance": 1e-4,
                "max_iterations": 40,
                "bus_voltage": 1.02,
            },
        }
        res1 = client.post("/api/v1/studies/re-run", json=rerun_payload_1, headers=auth_headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["project_id"] == project_id
        assert data1["version"] == 1
        assert data1["parameters"]["convergence_tolerance"] == 1e-4
        assert data1["parameters"]["max_iterations"] == 40

        # 3. Re-run study again with tightened tolerance (Revision 2)
        rerun_payload_2 = {
            "project_id": project_id,
            "tool": "load_flow",
            "parameters": {
                "convergence_tolerance": 1e-6,
                "max_iterations": 60,
                "bus_voltage": 1.05,
            },
        }
        res2 = client.post("/api/v1/studies/re-run", json=rerun_payload_2, headers=auth_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["success"] is True
        assert data2["version"] == 2
        assert data2["parameters"]["convergence_tolerance"] == 1e-6
        assert data2["parameters"]["max_iterations"] == 60

        # 4. Check solver parameters persisted for project
        params_resp = client.get(f"/api/v1/studies/parameters/{project_id}")
        assert params_resp.status_code == 200
        saved_params = params_resp.json()
        assert saved_params["convergence_tolerance"] == 1e-6
        assert saved_params["max_iterations"] == 60

    def test_revision_concurrency(self, client: TestClient, auth_headers: dict[str, str]):
        """Verify 5 sequential/consecutive re-runs produce strictly incrementing revisions 1-5."""
        create_resp = client.post(
            "/api/v1/projects/",
            json={"name": "Concurrency Project", "description": "Testing revision ordering"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        versions = []
        for i in range(1, 6):
            resp = client.post(
                "/api/v1/studies/re-run",
                json={
                    "project_id": project_id,
                    "tool": "load_flow",
                    "parameters": {"max_iterations": 20 + i},
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            versions.append(resp.json()["version"])

        assert versions == [1, 2, 3, 4, 5]

    def test_rerun_idempotency(self, client: TestClient, auth_headers: dict[str, str]):
        """Verify re-run endpoint is idempotent when using Idempotency-Key header."""
        create_resp = client.post(
            "/api/v1/projects/",
            json={"name": "Idempotent Project", "description": "Testing idempotency"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["id"]

        headers_with_key = {**auth_headers, "Idempotency-Key": "smoke-test-key-001"}
        payload = {
            "project_id": project_id,
            "tool": "load_flow",
            "parameters": {"convergence_tolerance": 1e-5},
        }

        resp1 = client.post("/api/v1/studies/re-run", json=payload, headers=headers_with_key)
        assert resp1.status_code == 200
        data1 = resp1.json()

        resp2 = client.post("/api/v1/studies/re-run", json=payload, headers=headers_with_key)
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["study_id"] == data2["study_id"]
        assert data1["version"] == data2["version"]

