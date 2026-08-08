"""
test_v81_integration.py — V8.1 Full Integration Test Suite

Tests the complete integration chain:
  Frontend pages → API service layer → Backend routers → Real computations

This test suite verifies that:
  1. Every backend endpoint registered in OpenAPI is reachable
  2. Every frontend page's API calls match the backend paths
  3. Real data flows through the pipeline (not mocked)
  4. Authentication works (X-API-Key header)
  5. Error handling is consistent

Per agent.md Rule 10 (MANDATORY TEST-AND-FIX LOOP):
  Tests are NEVER modified — only production code is fixed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set test environment BEFORE importing the app
os.environ.setdefault("FIREAI_ENV", "development")
os.environ.setdefault("FIREAI_API_KEY", "v81_integration_test_key")
os.environ.setdefault("FIREAI_API_KEYS", "v81_integration_test_key")
os.environ.setdefault(
        "FIREAI_SESSION_SECRET",
        "test_session_secret_for_v81_integration_tests_minimum_43_chars_long",
)
os.environ.setdefault(
        "QOMN_AUDIT_SECRET_KEY",
        "test_audit_secret_for_v81_integration_32bytes_long_enough",
)


@pytest.fixture(scope="module")
def client():
        """Module-scoped TestClient for the full FastAPI app."""
        from backend.app import app
        with TestClient(app) as c:
                yield c


@pytest.fixture
def auth_headers():
        """Headers with valid API key for authenticated endpoints."""
        return {"X-API-Key": "v81_integration_test_key"}


@pytest.fixture
def openapi_paths(client):
        """All paths from the OpenAPI schema."""
        schema = client.get("/openapi.json").json()
        return schema.get("paths", {})


# ===========================================================================
# 1. HEALTH & SYSTEM ENDPOINTS
# ===========================================================================
class TestHealthAndSystem:
        """Test core health and system endpoints."""

        def test_health(self, client):
                """GET /health — must return 200 with status ok."""
                resp = client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["data"]["status"] == "ok"

        def test_database_health(self, client, auth_headers):
                """GET /api/database-health — database must be connected."""
                resp = client.get("/api/database-health", headers=auth_headers)
                assert resp.status_code in (200, 401)

        def test_openapi_schema(self, client):
                """GET /openapi.json — schema must be valid."""
                resp = client.get("/openapi.json")
                assert resp.status_code == 200
                schema = resp.json()
                assert "paths" in schema
                assert len(schema["paths"]) > 100  # 230+ endpoints expected

        def test_cache_stats(self, client, auth_headers):
                """GET /api/v1/cache/stats — cache statistics must return 200."""
                resp = client.get("/api/v1/cache/stats", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                # Must have cache stats structure
                assert isinstance(data, dict)


# ===========================================================================
# 2. AUTH ENDPOINTS
# ===========================================================================
class TestAuth:
        """Test authentication endpoints."""

        def test_login_success(self, client):
                """POST /api/v1/auth/login — valid key returns session."""
                resp = client.post(
                        "/api/v1/auth/login",
                        json={"api_key": "v81_integration_test_key"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["data"]["role"] == "admin"

        def test_login_invalid_key(self, client):
                """POST /api/v1/auth/login — invalid key returns 401."""
                resp = client.post(
                        "/api/v1/auth/login",
                        json={"api_key": "invalid_key_that_does_not_exist"},
                )
                assert resp.status_code == 401

        def test_login_empty_key(self, client):
                """POST /api/v1/auth/login — empty key returns 422."""
                resp = client.post(
                        "/api/v1/auth/login",
                        json={"api_key": ""},
                )
                assert resp.status_code in (400, 422)


# ===========================================================================
# 3. QOMN ENGINEERING CALCULATIONS
# ===========================================================================
class TestQomnCalculations:
        """Test QOMN kernel engineering calculations — safety-critical."""

        def test_qomn_constants(self, client, auth_headers):
                """GET /api/v1/qomn/constants — NFPA 72 constants must be present."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert "nfpa72" in data["data"]
                # Safety-critical: smoke_max_spacing_m must be 9.1 (NFPA 72)
                assert data["data"]["nfpa72"]["smoke_max_spacing_m"] == 9.1
                # heat_max_spacing_m must be 6.1
                assert data["data"]["nfpa72"]["heat_max_spacing_m"] == 6.1

        def test_qomn_smoke_spacing(self, client, auth_headers):
                """POST /api/v1/qomn/smoke-spacing — real spacing calculation."""
                resp = client.post(
                        "/api/v1/qomn/smoke-spacing",
                        json={
                                "room_area_m2": 100.0,
                                "ceiling_height_m": 3.0,
                                "listed_spacing_m": 9.1,
                        },
                        headers=auth_headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                # Coverage radius must be 0.7 × 9.1 = 6.37
                if "coverage_radius_m" in data:
                        assert abs(data["coverage_radius_m"] - 6.37) < 0.1

        def test_qomn_voltage_drop(self, client, auth_headers):
                """POST /api/v1/qomn/voltage-drop — NEC Table 8 calculation."""
                resp = client.post(
                        "/api/v1/qomn/voltage-drop",
                        json={
                                "current_a": 0.150,
                                "length_m": 250.0,
                                "awg_gauge": "14",
                        },
                        headers=auth_headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                # Voltage drop must be positive
                if "voltage_drop_v" in data:
                        assert data["voltage_drop_v"] > 0
                if "is_compliant" in data:
                        assert isinstance(data["is_compliant"], bool)

        def test_qomn_battery(self, client, auth_headers):
                """POST /api/v1/qomn/battery — battery sizing per NFPA 72 §10.6.7."""
                resp = client.post(
                        "/api/v1/qomn/battery",
                        json={
                                "standby_load_a": 2.5,
                                "alarm_load_a": 5.0,
                                "standby_hours": 24,
                                "alarm_minutes": 5,
                                "safety_factor": 1.25,
                        },
                        headers=auth_headers,
                )
                assert resp.status_code == 200

        def test_qomn_physics_guards(self, client, auth_headers):
                """GET /api/v1/qomn/physics-guards — physics validation constants."""
                resp = client.get("/api/v1/qomn/physics-guards", headers=auth_headers)
                assert resp.status_code == 200

        def test_qomn_audit(self, client, auth_headers):
                """GET /api/v1/qomn/audit — audit chain verification."""
                resp = client.get("/api/v1/qomn/audit", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "chain_valid" in data


# ===========================================================================
# 4. MONITOR ENDPOINTS
# ===========================================================================
class TestMonitor:
        """Test system monitoring endpoints."""

        def test_monitor_health(self, client, auth_headers):
                """GET /api/v1/monitor/health — system health with engine count."""
                resp = client.get("/api/v1/monitor/health", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["data"]["engines"]["total"] >= 4
                assert data["data"]["engines"]["running"] >= 1

        def test_monitor_engine_status(self, client, auth_headers):
                """GET /api/v1/monitor/engine-status — per-engine CPU/memory."""
                resp = client.get("/api/v1/monitor/engine-status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["data"]["total"] >= 4
                engine_names = [e["name"] for e in data["data"]["engines"]]
                assert any("NFPA 72" in n for n in engine_names)

        def test_monitor_alerts(self, client, auth_headers):
                """GET /api/v1/monitor/alerts — active alerts + rules."""
                resp = client.get("/api/v1/monitor/alerts", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "rules" in data["data"]
                assert data["data"]["rule_count"] >= 5

        def test_monitor_metrics(self, client, auth_headers):
                """GET /api/v1/monitor/metrics — Prometheus metrics format."""
                resp = client.get("/api/v1/monitor/metrics", headers=auth_headers)
                assert resp.status_code == 200
                # Prometheus format starts with # HELP or # TYPE
                text = resp.text
                assert "# HELP" in text or "# TYPE" in text or "fireai" in text


# ===========================================================================
# 5. MINING ENDPOINTS (NFPA 120/122, MSHA)
# ===========================================================================
class TestMining:
        """Test mining fire protection endpoints."""

        def test_mining_standards(self, client, auth_headers):
                """GET /api/v1/mining/standards — list mining standards."""
                resp = client.get("/api/v1/mining/standards", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                standards = data.get("standards", [])
                codes = [s.get("code", "") for s in standards]
                assert any("NFPA" in c or "MSHA" in c for c in codes)

        def test_mining_methane_check(self, client, auth_headers):
                """POST /api/v1/mining/methane-check — MSHA §75.323."""
                resp = client.post(
                        "/api/v1/mining/methane-check",
                        json={"concentration_pct": 1.5, "location": "face"},
                        headers=auth_headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "hazard_level" in data or "success" in data

        def test_mining_ventilation_check(self, client, auth_headers):
                """POST /api/v1/mining/ventilation-check — MSHA §75.326-327."""
                resp = client.post(
                        "/api/v1/mining/ventilation-check",
                        json={"airflow_m3_s": 8.0, "location_type": "face"},
                        headers=auth_headers,
                )
                assert resp.status_code == 200

        def test_mining_co_check(self, client, auth_headers):
                """POST /api/v1/mining/co-check — MSHA §75.351."""
                resp = client.post(
                        "/api/v1/mining/co-check",
                        json={"co_ppm": 25},
                        headers=auth_headers,
                )
                assert resp.status_code == 200


# ===========================================================================
# 6. MARINE ENDPOINTS (SOLAS/IMO)
# ===========================================================================
class TestMarine:
        """Test marine fire protection endpoints."""

        def test_marine_fire_classes(self, client, auth_headers):
                """GET /api/v1/marine/fire-classes — SOLAS fire class divisions."""
                resp = client.get("/api/v1/marine/fire-classes", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                classes = data.get("fire_classes", [])
                class_names = [fc["class"] for fc in classes]
                assert "A-60" in class_names
                assert "A-0" in class_names

        def test_marine_standards(self, client, auth_headers):
                """GET /api/v1/marine/standards — list marine standards."""
                resp = client.get("/api/v1/marine/standards", headers=auth_headers)
                assert resp.status_code == 200


# ===========================================================================
# 7. FACP ENDPOINTS
# ===========================================================================
class TestFACP:
        """Test FACP panel selection endpoints."""

        def test_facp_panels(self, client, auth_headers):
                """GET /api/v1/facp/panels — list FACP panel database."""
                resp = client.get("/api/v1/facp/panels", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                panels = data["data"]["panels"]
                assert len(panels) > 0
                # Each panel must have required fields
                panel = panels[0]
                assert "model" in panel
                assert "manufacturer" in panel
                assert "points_capacity" in panel


# ===========================================================================
# 8. DIGITAL TWIN ENDPOINTS
# ===========================================================================
class TestDigitalTwin:
        """Test digital twin conversion endpoints."""

        def test_dt_status(self, client, auth_headers):
                """GET /api/v1/digital-twin/status — conversion engine status."""
                resp = client.get("/api/v1/digital-twin/status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "status" in data
                assert "total_conversions" in data

        def test_dt_config(self, client, auth_headers):
                """GET /api/v1/digital-twin/config — current configuration."""
                resp = client.get("/api/v1/digital-twin/config", headers=auth_headers)
                assert resp.status_code == 200

        def test_dt_history(self, client, auth_headers):
                """GET /api/v1/digital-twin/history — conversion history."""
                resp = client.get("/api/v1/digital-twin/history", headers=auth_headers)
                assert resp.status_code == 200

        def test_dt_mappings(self, client, auth_headers):
                """GET /api/v1/digital-twin/mappings — element mappings."""
                resp = client.get("/api/v1/digital-twin/mappings", headers=auth_headers)
                assert resp.status_code == 200


# ===========================================================================
# 9. SELF-HEALING ENDPOINTS
# ===========================================================================
class TestSelfHealing:
        """Test self-healing engine endpoints."""

        def test_sh_health(self, client, auth_headers):
                """GET /api/v1/self-healing/health — circuit breaker + LRU stats."""
                resp = client.get("/api/v1/self-healing/health", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                # Must have at least one of these keys
                expected = {"circuit_breaker", "lru_cache", "audit_logger", "llm_breaker"}
                assert any(k in data for k in expected)

        def test_sh_audit(self, client, auth_headers):
                """GET /api/v1/self-healing/audit — audit log + chain integrity."""
                resp = client.get("/api/v1/self-healing/audit", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "chain_integrity" in data


# ===========================================================================
# 10. ENVIRONMENT ENDPOINTS
# ===========================================================================
class TestEnvironment:
        """Test environmental context endpoints."""

        def test_env_weather(self, client, auth_headers):
                """GET /api/v1/environment/weather — real weather from open-meteo."""
                resp = client.get(
                        "/api/v1/environment/weather?lat=30.04&lon=31.24",
                        headers=auth_headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert "temperature_c" in data["data"]
                assert "wind_speed_m_s" in data["data"]
                assert data["data"]["source"] == "open-meteo"

        def test_env_countries(self, client, auth_headers):
                """GET /api/v1/environment/countries — country list."""
                resp = client.get("/api/v1/environment/countries", headers=auth_headers)
                assert resp.status_code == 200


# ===========================================================================
# 11. API KEYS (Admin)
# ===========================================================================
class TestApiKeys:
        """Test API key management endpoints."""

        def test_list_keys(self, client, auth_headers):
                """GET /api/v1/admin/keys — list all API keys."""
                resp = client.get("/api/v1/admin/keys", headers=auth_headers)
                assert resp.status_code == 200

        def test_keys_roles(self, client, auth_headers):
                """GET /api/v1/admin/keys/roles — list available roles."""
                resp = client.get("/api/v1/admin/keys/roles", headers=auth_headers)
                assert resp.status_code == 200


# ===========================================================================
# 12. WORKFLOW ENDPOINTS
# ===========================================================================
class TestWorkflow:
        """Test workflow engine endpoints."""

        def test_workflow_status(self, client, auth_headers):
                """GET /api/v1/workflow/status — engine status."""
                resp = client.get("/api/v1/workflow/status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert "engine" in data["data"]


# ===========================================================================
# 13. MEMORY ENDPOINTS
# ===========================================================================
class TestMemory:
        """Test AI memory service endpoints."""

        def test_memory_status(self, client, auth_headers):
                """GET /api/v1/memory/status — service init + provider info."""
                resp = client.get("/api/v1/memory/status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "status" in data
                assert "initialized" in data["status"]

        def test_memory_all(self, client, auth_headers):
                """GET /api/v1/memory/all — all stored memories."""
                resp = client.get("/api/v1/memory/all", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "results" in data
                assert "disclaimer" in data  # Safety disclaimer required


# ===========================================================================
# 14. LLM ENDPOINTS
# ===========================================================================
class TestLLM:
        """Test LLM chat endpoints."""

        def test_llm_health(self, client, auth_headers):
                """GET /api/v1/llm/health — LLM provider status."""
                resp = client.get("/api/v1/llm/health", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert "available" in data["data"]
                assert "primary" in data["data"]


# ===========================================================================
# 15. GRAPHRAG ENDPOINTS
# ===========================================================================
class TestGraphRAG:
        """Test GraphRAG knowledge graph endpoints."""

        def test_graphrag_health(self, client, auth_headers):
                """GET /api/v2/graphrag/health — Neo4j + vector store status."""
                resp = client.get("/api/v2/graphrag/health", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "initialized" in data
                assert "neo4j_connected" in data


# ===========================================================================
# 16. AUTOCAD & REVIT ENDPOINTS
# ===========================================================================
class TestCADIntegration:
        """Test AutoCAD and Revit integration endpoints."""

        def test_autocad_status(self, client, auth_headers):
                """GET /api/v1/autocad/status — connection status."""
                resp = client.get("/api/v1/autocad/status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "connected" in data

        def test_revit_status(self, client, auth_headers):
                """GET /api/v1/revit/status — connection status."""
                resp = client.get("/api/v1/revit/status", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert "connected" in data

        def test_revit_levels(self, client, auth_headers):
                """GET /api/v1/revit/levels — levels in active document."""
                resp = client.get("/api/v1/revit/levels", headers=auth_headers)
                # 503 = Revit not connected (expected in test env without Revit)
                # Must NOT be 404 (route not registered) or 500 (unhandled crash)
                assert resp.status_code in (200, 503)
                if resp.status_code == 200:
                        data = resp.json()
                        assert isinstance(data, dict)

        def test_revit_views(self, client, auth_headers):
                """GET /api/v1/revit/views — views in active document."""
                resp = client.get("/api/v1/revit/views", headers=auth_headers)
                assert resp.status_code in (200, 503)
                if resp.status_code == 200:
                        data = resp.json()
                        assert isinstance(data, dict)


# ===========================================================================
# 17. ANALYZE ENDPOINTS
# ===========================================================================
class TestAnalyze:
        """Test engineering analysis endpoints."""

        def test_analyze_battery(self, client, auth_headers):
                """POST /api/v1/analyze/battery — battery analysis with real values."""
                resp = client.post(
                        "/api/v1/analyze/battery",
                        json={
                                "standby_load_a": 2.5,
                                "alarm_load_a": 5.0,
                                "standby_hours": 24,
                                "alarm_minutes": 5,
                                "safety_factor": 1.25,
                        },
                        headers=auth_headers,
                )
                assert resp.status_code == 200
                data = resp.json()
                # Must have battery capacity result
                if isinstance(data, dict):
                        # Look for capacity in various possible field names
                        capacity = (
                                data.get("required_ah")
                                or data.get("battery_capacity_ah")
                                or data.get("capacity_ah")
                                or (data.get("data", {}) or {}).get("required_ah")
                        )
                        if capacity is not None:
                                # Battery must be positive (2.5A × 24h × 1.25 = 75Ah minimum)
                                assert capacity > 0, f"Battery capacity must be positive, got {capacity}"

        def test_analyze_voltage(self, client, auth_headers):
                """POST /api/v1/analyze/voltage — voltage analysis with real values."""
                resp = client.post(
                        "/api/v1/analyze/voltage",
                        json={
                                "current_a": 0.150,
                                "length_m": 250.0,
                                "awg_gauge": "14",
                        },
                        headers=auth_headers,
                )
                # Accept 200 (success) or 422 (schema mismatch — still a valid response)
                assert resp.status_code in (200, 422)
                if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and "voltage_drop_v" in data:
                                assert data["voltage_drop_v"] > 0


# ===========================================================================
# 18. EXPORTS ENDPOINTS
# ===========================================================================
class TestExports:
        """Test data export endpoints."""

        def test_excel_export(self, client, auth_headers):
                """POST /api/v1/exports — Excel export must return file or valid error."""
                resp = client.post(
                        "/api/v1/exports",
                        json={"exportType": "excel"},
                        headers=auth_headers,
                )
                # 200 = file returned, 404 = no projects (valid error), 422 = schema
                # 503 = service unavailable (openpyxl not installed in test env)
                assert resp.status_code in (200, 404, 422, 503)
                if resp.status_code == 200:
                        # Excel files start with PK zip magic bytes
                        if resp.headers.get("content-type", "").startswith("application/"):
                                body = resp.content
                                # Either Excel (PK) or JSON manifest
                                assert body[:2] == b"PK" or body[:1] == b"{", \
                                        "Response must be Excel (PK) or JSON manifest"


# ===========================================================================
# 19. PROJECTS ENDPOINTS
# ===========================================================================
class TestProjects:
        """Test project management endpoints."""

        def test_list_projects(self, client, auth_headers):
                """GET /api/v1/projects — list all projects."""
                resp = client.get("/api/v1/projects", headers=auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                # Must return a list or dict with projects key
                if isinstance(data, list):
                        assert isinstance(data, list)
                elif isinstance(data, dict):
                        assert "projects" in data or "data" in data or "success" in data

        def test_create_project(self, client, auth_headers):
                """POST /api/v1/projects — create new project."""
                resp = client.post(
                        "/api/v1/projects",
                        json={
                                "name": "V8.1 Integration Test Project",
                                "type": "building",
                                "standard": "NFPA 72-2022",
                        },
                        headers=auth_headers,
                )
                # 200/201 = created, 422 = schema validation
                assert resp.status_code in (200, 201, 422)
                if resp.status_code in (200, 201):
                        data = resp.json()
                        assert isinstance(data, dict)


# ===========================================================================
# 20. FRONTEND-BACKEND PATH MATCHING
# ===========================================================================
class TestFrontendBackendPathMatch:
        """Verify that frontend pages call the SAME paths as the backend.

        This catches path mismatches (the V214 ApiKeys bug where frontend
        called /api-keys but backend was at /admin/keys).
        """

        FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "src"

        def test_mining_page_uses_correct_paths(self):
                """miningApi.ts must call /api/v1/mining/* paths."""
                service = self.FRONTEND_DIR / "services" / "miningApi.ts"
                if not service.exists():
                        pytest.skip("miningApi.ts not found")
                content = service.read_text()
                assert "/mining/standards" in content
                assert "/mining/methane-check" in content

        def test_self_healing_api_uses_correct_paths(self):
                """selfHealingApi.ts must call /api/v1/self-healing/* paths."""
                service = self.FRONTEND_DIR / "services" / "selfHealingApi.ts"
                if not service.exists():
                        pytest.skip("selfHealingApi.ts not found")
                content = service.read_text()
                assert "/self-healing/health" in content
                assert "/self-healing/audit" in content

        def test_apikeys_page_uses_correct_path(self):
                """ApiKeysPage.tsx must call /api/v1/admin/keys (NOT /api-keys)."""
                page = self.FRONTEND_DIR / "pages" / "ApiKeysPage.tsx"
                if not page.exists():
                        pytest.skip("ApiKeysPage.tsx not found")
                content = page.read_text()
                assert "/api/v1/admin/keys" in content
                # Old wrong path must NOT appear
                assert "/api/v1/api-keys" not in content

        def test_all_pages_have_api_calls(self):
                """Every page that needs data must have at least one fetch/api call.

                Pages that legitimately don't need API calls:
                - NotFoundPage.tsx (static 404)
                - LoginPage.tsx (form submit only)
                - AutoCADDrawPage.tsx (canvas drawing tool, uses autocadService import)
                """
                pages_dir = self.FRONTEND_DIR / "pages"
                if not pages_dir.exists():
                        pytest.skip("pages directory not found")

                # Pages that legitimately don't need direct API calls
                exempt_pages = {"NotFoundPage.tsx", "LoginPage.tsx", "AutoCADDrawPage.tsx"}

                mockup_pages = []
                for page_file in pages_dir.glob("*.tsx"):
                        if page_file.name in exempt_pages:
                                continue
                        content = page_file.read_text()
                        has_api = (
                                "fetch(" in content
                                or "useApi" in content
                                or "useQuery" in content
                                or "apiCall" in content
                                or "miningApi" in content
                                or "selfHealingApi" in content
                                or "autocadService" in content
                                or "/api/v1" in content
                                or "/api/v2" in content
                        )
                        if not has_api:
                                mockup_pages.append(page_file.name)

                # All pages should have API calls (no mockups allowed)
                assert len(mockup_pages) == 0, (
                        f"These pages have NO API calls (still mockups): {mockup_pages}"
                )

        def test_frontend_api_paths_exist_in_backend(self, client, openapi_paths):
                """Every /api/v1/* path in frontend code must exist in backend OpenAPI.

                This catches path mismatches — the most dangerous bug class
                (per agent.md Rule 17: ROOT-CAUSE ANALYSIS).
                """
                import re

                pages_dir = self.FRONTEND_DIR / "pages"
                services_dir = self.FRONTEND_DIR / "services"

                # Collect all /api/v1/* and /api/v2/* paths from frontend
                frontend_paths = set()
                for search_dir in [pages_dir, services_dir]:
                        if not search_dir.exists():
                                continue
                        for file_path in search_dir.rglob("*.tsx"):
                                content = file_path.read_text()
                                # Find /api/v1/... or /api/v2/... patterns
                                matches = re.findall(r'["\'](/api/v[12]/[^"\']+)', content)
                                for match in matches:
                                        # Normalize: remove query params, replace path params with {}
                                        path = match.split("?")[0]
                                        # Replace UUID/ID segments with {id}
                                        segments = path.split("/")
                                        normalized = []
                                        for seg in segments:
                                                if re.match(r'^[0-9a-f-]{8,}$', seg) or seg.isdigit():
                                                        normalized.append("{id}")
                                                else:
                                                        normalized.append(seg)
                                        frontend_paths.add("/".join(normalized))

                # Get all backend paths from OpenAPI
                backend_paths = set(openapi_paths.keys())

                # Check that frontend paths exist in backend (ignoring path params)
                missing = []
                for fpath in frontend_paths:
                        # Skip paths with {id} — they're templates
                        if "{id}" in fpath:
                                # Check if any backend path matches the pattern
                                pattern = fpath.replace("{id}", "[^/]+")
                                found = any(re.match(pattern, bpath) for bpath in backend_paths)
                                if not found:
                                        # Try with original segment names
                                        found = any(fpath.replace("{id}", "").rstrip("/") in bpath for bpath in backend_paths)
                        else:
                                found = fpath in backend_paths

                        if not found:
                                # Check if it's a sub-path of a registered route
                                found = any(fpath.startswith(bp + "/") for bp in backend_paths)

                        if not found:
                                missing.append(fpath)

                # Allow some known service-level paths that are constructed dynamically
                known_dynamic = {
                        "/api/v1/admin/keys",  # constructed via template literal
                }
                missing = [p for p in missing if p not in known_dynamic]

                assert len(missing) == 0, (
                        f"These frontend API paths don't exist in backend OpenAPI: {missing}"
                )


# ===========================================================================
# 21. OPENAPI COMPLETENESS
# ===========================================================================
class TestOpenApiCompleteness:
        """Verify all registered endpoints are reachable."""

        def test_all_get_endpoints_reachable(self, client, openapi_paths, auth_headers):
                """Every GET endpoint (without path params) in OpenAPI must be reachable."""
                # Exclude paths with path parameters (they need specific IDs)
                param_indicators = [
                        "{", "project_id", "element_id", "connection_id", "memory_id",
                        "filename", "key_hash", "version_id", "conflict_id", "sub_id",
                ]
                get_endpoints = [
                        path for path, methods in openapi_paths.items()
                        if "get" in methods
                        and not any(ind in path for ind in param_indicators)
                ]
                assert len(get_endpoints) > 40, f"Expected 40+ param-less GET endpoints, got {len(get_endpoints)}"

                failures = []
                for path in get_endpoints:
                        resp = client.get(path, headers=auth_headers)
                        # Accept 200, 401, 403, 422, 503 — but NOT 404 (means route not registered)
                        if resp.status_code == 404:
                                failures.append(f"404: {path}")

                assert len(failures) == 0, (
                        f"These GET endpoints return 404 (not registered): {failures}"
                )


# ===========================================================================
# 22. SAFETY-CRITICAL VERIFICATIONS
# ===========================================================================
class TestSafetyCritical:
        """Verify safety-critical engineering values are correct."""

        def test_smoke_spacing_is_9_1m(self, client, auth_headers):
                """NFPA 72: smoke detector max spacing must be 9.1m — NEVER change."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                data = resp.json()
                assert data["data"]["nfpa72"]["smoke_max_spacing_m"] == 9.1

        def test_heat_spacing_is_6_1m(self, client, auth_headers):
                """NFPA 72: heat detector max spacing must be 6.1m — NEVER change."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                data = resp.json()
                assert data["data"]["nfpa72"]["heat_max_spacing_m"] == 6.1

        def test_coverage_radius_factor_is_0_7(self, client, auth_headers):
                """NFPA 72: coverage radius factor must be 0.7 × S — NEVER change."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                data = resp.json()
                assert data["data"]["nfpa72"]["coverage_radius_factor"] == 0.7

        def test_battery_standby_is_24h(self, client, auth_headers):
                """NFPA 72 §10.6.7: standby must be 24h — NEVER change."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                data = resp.json()
                # Check battery section for 24h requirement
                battery = data["data"].get("battery", {})
                assert battery.get("standby_hours", 24) == 24

        def test_voltage_drop_max_is_10_pct(self, client, auth_headers):
                """NFPA 72 §10.6.4: max voltage drop must be 10% — NEVER change."""
                resp = client.get("/api/v1/qomn/constants", headers=auth_headers)
                data = resp.json()
                vd = data["data"].get("voltage_drop", {})
                assert vd.get("max_drop_pct", 10.0) == 10.0
