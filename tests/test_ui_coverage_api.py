"""
Unit tests for new UI coverage API endpoints.
Tests all newly exposed API endpoints from Steps 1-8 of the
Complete UI Coverage & Configuration Exposure Implementation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Step 1: Solver Parameters API
# ---------------------------------------------------------------------------


class TestSolverParametersAPI:
    """Tests for /api/v1/studies/parameters endpoint."""

    def test_get_solver_parameters(self, client: TestClient) -> None:
        """GET /api/v1/studies/parameters returns default parameters."""
        response = client.get("/api/v1/studies/parameters")
        assert response.status_code == 200
        data = response.json()
        assert "convergence_tolerance" in data
        assert "max_iterations" in data
        assert "acceleration_factor" in data

    def test_put_solver_parameters(self, client: TestClient) -> None:
        """PUT /api/v1/studies/parameters updates parameters."""
        response = client.put(
            "/api/v1/studies/parameters",
            json={
                "convergence_tolerance": 1e-4,
                "max_iterations": 100,
                "acceleration_factor": 1.4,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["convergence_tolerance"] == 1e-4
        assert data["max_iterations"] == 100
        assert data["acceleration_factor"] == 1.4

    def test_post_solver_parameters(self, client: TestClient) -> None:
        """POST /api/v1/studies/parameters creates/overwrites all parameters."""
        response = client.post(
            "/api/v1/studies/parameters",
            json={
                "convergence_tolerance": 1e-6,
                "max_iterations": 200,
                "acceleration_factor": 1.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["convergence_tolerance"] == 1e-6
        assert data["max_iterations"] == 200

    def test_put_solver_parameters_validation(self, client: TestClient) -> None:
        """PUT with invalid values returns validation error."""
        response = client.put(
            "/api/v1/studies/parameters",
            json={"max_iterations": 5},  # Below minimum of 10
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Step 2: ZIP Load & Generator Config API
# ---------------------------------------------------------------------------


class TestZIPLoadGeneratorAPI:
    """Tests for /api/v1/equipment/zip-generators endpoints."""

    def test_list_zip_presets(self, client: TestClient) -> None:
        """GET /zip-presets returns available ZIP presets."""
        response = client.get("/api/v1/equipment/zip-generators/zip-presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert len(data["presets"]) > 0

    def test_list_zip_loads(self, client: TestClient) -> None:
        """GET /zip-loads returns all configured ZIP loads."""
        response = client.get("/api/v1/equipment/zip-generators/zip-loads")
        assert response.status_code == 200

    def test_create_zip_load(self, client: TestClient) -> None:
        """POST /zip-loads creates a new ZIP load configuration."""
        response = client.post(
            "/api/v1/equipment/zip-generators/zip-loads",
            json={
                "name": "Test Load",
                "p0": 1.0,
                "q0": 0.5,
                "aZ": 0.25,
                "aI": 0.15,
                "aP": 0.60,
                "bZ": 0.25,
                "bI": 0.15,
                "bP": 0.60,
            },
        )
        assert response.status_code in (200, 201)

    def test_list_generators(self, client: TestClient) -> None:
        """GET /generators returns all generator capability configs."""
        response = client.get("/api/v1/equipment/zip-generators/generators")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Step 3: Copilot Config API
# ---------------------------------------------------------------------------


class TestCopilotConfigAPI:
    """Tests for /api/v1/copilot/config endpoint."""

    def test_get_copilot_config(self, client: TestClient) -> None:
        """GET /api/v1/copilot/config returns current config."""
        response = client.get("/api/v1/copilot/config")
        assert response.status_code == 200
        data = response.json()
        assert "llm_temperature" in data
        assert "max_tokens" in data

    def test_put_copilot_config(self, client: TestClient) -> None:
        """PUT /api/v1/copilot/config updates config."""
        response = client.put(
            "/api/v1/copilot/config",
            json={"llm_temperature": 0.5, "max_tokens": 8192},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["llm_temperature"] == 0.5
        assert data["max_tokens"] == 8192


# ---------------------------------------------------------------------------
# Step 4: Storage Management API
# ---------------------------------------------------------------------------


class TestStorageManagementAPI:
    """Tests for /api/v1/storage endpoints."""

    def test_get_storage_metrics(self, client: TestClient) -> None:
        """GET /api/v1/storage/metrics returns storage usage."""
        response = client.get("/api/v1/storage/metrics")
        # May return 503 if R2 not configured in test env
        assert response.status_code in (200, 503)

    def test_get_retention_policy(self, client: TestClient) -> None:
        """GET /api/v1/storage/retention returns retention policy."""
        response = client.get("/api/v1/storage/retention")
        assert response.status_code == 200
        data = response.json()
        assert "retention_days" in data


# ---------------------------------------------------------------------------
# Step 5: Notification Config API
# ---------------------------------------------------------------------------


class TestNotificationConfigAPI:
    """Tests for /api/v1/notifications/digest/config endpoint."""

    def test_get_notification_config(self, client: TestClient) -> None:
        """GET /api/v1/notifications/digest/config returns config."""
        response = client.get("/api/v1/notifications/digest/config")
        assert response.status_code == 200
        data = response.json()
        assert "digest" in data or "alerts" in data

    def test_get_alerts(self, client: TestClient) -> None:
        """GET /alerts returns all alert type configurations."""
        response = client.get("/api/v1/notifications/digest/config/alerts")
        assert response.status_code == 200

    def test_get_webhooks(self, client: TestClient) -> None:
        """GET /webhooks returns registered webhooks."""
        response = client.get("/api/v1/notifications/digest/config/webhooks")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Step 6: Autodesk Connector API
# ---------------------------------------------------------------------------


class TestAutodeskConnectorAPI:
    """Tests for /api/v1/connectors/autodesk endpoints."""

    def test_get_connector_status(self, client: TestClient) -> None:
        """GET /status returns health status of all connectors."""
        response = client.get("/api/v1/connectors/autodesk/status")
        assert response.status_code == 200
        data = response.json()
        assert "autocad_status" in data or "overall_healthy" in data

    def test_get_timeouts(self, client: TestClient) -> None:
        """GET /timeouts returns current timeout configuration."""
        response = client.get("/api/v1/connectors/autodesk/timeouts")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Step 7: Audit Logs API
# ---------------------------------------------------------------------------


class TestAuditLogsAPI:
    """Tests for /api/v1/security/audit-logs endpoint."""

    def test_list_audit_logs(self, client: TestClient) -> None:
        """GET /api/v1/security/audit-logs returns paginated logs."""
        response = client.get("/api/v1/security/audit-logs")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data

    def test_list_audit_logs_with_filters(self, client: TestClient) -> None:
        """GET with query parameters filters logs."""
        response = client.get("/api/v1/security/audit-logs?severity=high&page=1&page_size=10")
        assert response.status_code == 200

    def test_get_audit_log_stats(self, client: TestClient) -> None:
        """GET /stats returns audit log statistics."""
        response = client.get("/api/v1/security/audit-logs/stats")
        assert response.status_code == 200

    def test_export_audit_logs_csv(self, client: TestClient) -> None:
        """GET /export/csv returns CSV data."""
        response = client.get("/api/v1/security/audit-logs/export/csv")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Step 8: Feature Flags API
# ---------------------------------------------------------------------------


class TestFeatureFlagsAPI:
    """Tests for /api/v1/feature-flags endpoint."""

    def test_list_feature_flags(self, client: TestClient) -> None:
        """GET /api/v1/feature-flags returns all flags."""
        response = client.get("/api/v1/feature-flags")
        assert response.status_code == 200
        data = response.json()
        assert "flags" in data
        assert len(data["flags"]) > 0

    def test_get_feature_flag(self, client: TestClient) -> None:
        """GET /api/v1/feature-flags/{flag_id} returns a specific flag."""
        response = client.get("/api/v1/feature-flags/harmonic_analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["flag_id"] == "harmonic_analysis"

    def test_update_feature_flag(self, client: TestClient) -> None:
        """PUT /api/v1/feature-flags/{flag_id} updates a flag."""
        response = client.put(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

        # Reset
        client.put(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"enabled": False},
        )

    def test_get_nonexistent_feature_flag(self, client: TestClient) -> None:
        """GET /api/v1/feature-flags/{nonexistent} returns 404."""
        response = client.get("/api/v1/feature-flags/nonexistent_flag")
        assert response.status_code == 404

    def test_update_feature_flag_invalid_status(self, client: TestClient) -> None:
        """PUT with invalid status returns 422."""
        response = client.put(
            "/api/v1/feature-flags/harmonic_analysis",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 422
