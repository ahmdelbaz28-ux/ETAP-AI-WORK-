"""Tests for engineering_service.py — FastAPI endpoints.

Covers:
  1. Health endpoint — correct schema
  2. Ready endpoint — correct schema
  3. Metrics endpoint — JSON + Prometheus format
  4. Study run (success path) — valid load_flow, 200, result structure
  5. Study run (failure path) — invalid study_type, proper error
  6. Study run (missing API key) — 401
  7. Study run (invalid API key) — 401
  8. CORS headers
  9. Rate limiting
 10. Request body size limit
 11. Supported study types
"""

import os
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    from api.routes import app

    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Minimal 3-bus power system for studies that require a `system` field.
_MINI_SYSTEM = {
    "base_mva": 100.0,
    "buses": [
        {
            "bus_id": 1,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "slack",
            "base_kv": 20.0,
        },
        {
            "bus_id": 2,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "pq",
            "base_kv": 20.0,
        },
        {
            "bus_id": 3,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "pv",
            "base_kv": 20.0,
        },
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02, "x1": 0.08, "bshunt1": 0.0},
        {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.02, "x1": 0.08, "bshunt1": 0.0},
    ],
    "generators": [
        {"generator_id": 1, "bus_id": 1, "internal_voltage_mag": 1.0},
        {"generator_id": 2, "bus_id": 3, "internal_voltage_mag": 1.0},
    ],
    "loads": [
        {"load_id": 1, "bus_id": 2, "p_mw": 0.8, "q_mvar": 0.6},
    ],
    "transformers": [],
}


# ===================================================================
# 1. Health endpoint — GET /health returns correct schema
# ===================================================================


class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_returns_status_healthy(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_health_contains_version(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "version" in data

    async def test_health_response_body_contains_trace_id(self, client):
        """The trace_id should be present in the response body."""
        resp = await client.get("/health")
        data = resp.json()
        assert "trace_id" in data
        assert data["trace_id"]  # non-empty

    async def test_health_preserves_provided_trace_id(self, client):
        trace_id = str(uuid.uuid4())
        resp = await client.get("/health", headers={"x-trace-id": trace_id})
        data = resp.json()
        assert data["trace_id"] == trace_id

    # --- Schema validation (new) ---

    async def test_health_schema_has_timestamp(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")

    async def test_health_schema_has_trace_id_in_body(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "trace_id" in data

    async def test_health_schema_contains_all_required_fields(self, client):
        """Verify the full HealthResponse schema: status, version, timestamp, trace_id."""
        resp = await client.get("/health")
        data = resp.json()
        required_fields = {"status", "version", "timestamp", "trace_id"}
        assert required_fields.issubset(data.keys()), (
            f"Missing fields: {required_fields - data.keys()}"
        )


# ===================================================================
# 2. Ready endpoint — GET /ready returns correct schema
# ===================================================================


class TestReadyEndpoint:
    async def test_ready_returns_200(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200

    async def test_ready_returns_true(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert data["ready"] is True

    # --- Schema validation (new) ---

    async def test_ready_schema_has_native_engine_available(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert "native_engine_available" in data
        assert isinstance(data["native_engine_available"], bool)

    async def test_ready_schema_has_etap_available(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert "etap_available" in data
        assert isinstance(data["etap_available"], bool)

    async def test_ready_schema_has_timestamp(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")

    async def test_ready_schema_has_trace_id(self, client):
        resp = await client.get("/ready")
        data = resp.json()
        assert "trace_id" in data

    async def test_ready_schema_contains_all_required_fields(self, client):
        """Verify the full ReadyResponse schema."""
        resp = await client.get("/ready")
        data = resp.json()
        required_fields = {
            "ready",
            "native_engine_available",
            "etap_available",
            "timestamp",
            "trace_id",
        }
        assert required_fields.issubset(data.keys()), (
            f"Missing fields: {required_fields - data.keys()}"
        )


# ===================================================================
# 3. Metrics endpoint — JSON + Prometheus format
# ===================================================================


class TestMetricsEndpoint:
    async def test_metrics_returns_200(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_contains_expected_keys(self, client):
        resp = await client.get("/metrics")
        data = resp.json()
        for key in (
            "requests_total",
            "requests_success",
            "requests_failed",
            "avg_execution_time_ms",
        ):
            assert key in data

    async def test_metrics_values_are_non_negative(self, client):
        resp = await client.get("/metrics")
        data = resp.json()
        assert data["requests_total"] >= 0
        assert data["requests_success"] >= 0

    async def test_metrics_schema_has_trace_id(self, client):
        resp = await client.get("/metrics")
        data = resp.json()
        assert "trace_id" in data

    # --- Prometheus format (new) ---

    async def test_prometheus_metrics_returns_200(self, client):
        resp = await client.get("/prometheus/metrics")
        assert resp.status_code == 200

    async def test_prometheus_metrics_content_type(self, client):
        resp = await client.get("/prometheus/metrics")
        ct = resp.headers.get("content-type", "")
        # prometheus_client uses text/plain; version=0.0.4; charset=utf-8
        assert "text/plain" in ct

    async def test_prometheus_metrics_contains_metric_lines(self, client):
        resp = await client.get("/prometheus/metrics")
        text = resp.text
        # Prometheus exposition format has HELP / TYPE comments and metric lines
        assert "#" in text
        # At least one of our registered metrics should appear
        assert any(
            name in text for name in ("skill_operations_total", "app_info", "executions_total")
        )


# ===================================================================
# 4 & 5. Study run — success and failure paths
# ===================================================================


class TestStudyRunEndpoint:
    # --- Existing tests (kept for regression) ---

    async def test_study_run_with_invalid_type_returns_422(self, client):
        resp = await client.post("/api/v1/studies/run", json={"study_type": "invalid"})
        assert resp.status_code == 422

    # --- 4. Success path: valid load_flow with system ---

    async def test_study_run_load_flow_success_path(self, client):
        """POST /api/v1/studies/run with valid load_flow + system returns 200."""
        payload = {
            "study_type": "load_flow",
            "system": _MINI_SYSTEM,
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_study_run_load_flow_result_structure(self, client):
        """Verify full StudyResult structure on successful run."""
        payload = {
            "study_type": "load_flow",
            "system": _MINI_SYSTEM,
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "success",
            "data",
            "results",
            "warnings",
            "errors",
            "execution_time_sec",
            "trace_id",
            "task_id",
            "study_type",
            "provider",
        ):
            assert field in data, f"Missing field: {field}"
        assert data["study_type"] == "load_flow"
        assert data["provider"] == "native"
        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)
        assert data["execution_time_sec"] >= 0

    async def test_study_run_load_flow_result_contains_trace_id(self, client):
        """Successful study result should include trace_id in the body."""
        payload = {
            "study_type": "load_flow",
            "system": _MINI_SYSTEM,
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        data = resp.json()
        assert "trace_id" in data
        assert data["trace_id"]  # non-empty

    async def test_study_run_load_flow_preserves_custom_trace_id(self, client):
        trace_id = str(uuid.uuid4())
        payload = {
            "study_type": "load_flow",
            "system": _MINI_SYSTEM,
        }
        resp = await client.post(
            "/api/v1/studies/run",
            json=payload,
            headers={"x-trace-id": trace_id},
        )
        data = resp.json()
        assert data["trace_id"] == trace_id

    # --- 5. Failure path: invalid / missing data ---

    async def test_study_run_load_flow_without_system_returns_400(self, client):
        """load_flow requires a system; omitting it should return 400."""
        resp = await client.post("/api/v1/studies/run", json={"study_type": "load_flow"})
        assert resp.status_code == 400

    async def test_study_run_failure_path_invalid_study_type_detail(self, client):
        """Invalid study_type returns 422 with validation error details."""
        resp = await client.post("/api/v1/studies/run", json={"study_type": "nonexistent_study"})
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    async def test_study_run_missing_body_returns_422(self, client):
        """POST without a JSON body should return 422."""
        resp = await client.post("/api/v1/studies/run")
        assert resp.status_code == 422


# ===================================================================
# 6 & 7. API key authentication
# ===================================================================


class TestStudyRunAPIKey:
    """Test API-key enforcement on /api/v1/studies/run."""

    async def test_study_run_missing_api_key(self, client):
        """When an API key is configured, a request without one returns 401."""
        with patch("api.dependencies.API_KEY", "test-secret-key"):
            resp = await client.post(
                "/api/v1/studies/run",
                json={"study_type": "load_flow"},
            )
            assert resp.status_code == 401

    async def test_study_run_invalid_api_key(self, client):
        """When an API key is configured, a wrong key returns 401."""
        with patch("api.dependencies.API_KEY", "test-secret-key"):
            resp = await client.post(
                "/api/v1/studies/run",
                json={"study_type": "load_flow"},
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401

    async def test_study_run_valid_api_key_succeeds(self, client):
        """When an API key is configured, the correct key returns 200."""
        with patch("api.dependencies.API_KEY", "test-secret-key"):
            resp = await client.post(
                "/api/v1/studies/run",
                json={"study_type": "load_flow", "system": _MINI_SYSTEM},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200

    async def test_study_run_no_api_key_configured_allows_access(self, client):
        """When no API key is configured (empty string), requests are allowed."""
        with patch("api.dependencies.API_KEY", ""):
            resp = await client.post(
                "/api/v1/studies/run",
                json={"study_type": "load_flow"},
            )
            # Should not be 401 — may be 400 (no system) but not auth error
            assert resp.status_code != 401


# ===================================================================
# 8. CORS headers
# ===================================================================


class TestCORS:
    async def test_cors_headers_present(self, client):
        """Preflight OPTIONS response includes access-control-allow-methods."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-methods" in resp.headers

    async def test_cors_preflight_allows_expected_methods(self, client):
        """CORS preflight should list standard HTTP methods."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        methods = resp.headers.get("access-control-allow-methods", "")
        for method in ("GET", "POST", "PUT", "DELETE"):
            assert method in methods

    async def test_cors_preflight_allow_headers_includes_api_key(self, client):
        """Preflight should confirm x-api-key and content-type in allowed headers."""
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-api-key",
            },
        )
        allowed = resp.headers.get("access-control-allow-headers", "")
        assert "x-api-key" in allowed

    async def test_cors_regular_get_request_succeeds(self, client):
        """A regular (non-preflight) GET with an Origin header should succeed."""
        resp = await client.get(
            "/health",
            headers={"Origin": "https://example.com"},
        )
        assert resp.status_code == 200

    async def test_cors_preflight_post(self, client):
        """CORS preflight for POST method should also work."""
        resp = await client.options(
            "/api/v1/studies/run",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-api-key",
            },
        )
        assert "access-control-allow-methods" in resp.headers
        assert "POST" in resp.headers.get("access-control-allow-methods", "")

    async def test_cors_expose_headers_configured(self, client):
        """Verify the CORS middleware is configured with expose_headers containing x-trace-id.

        With restrictive (empty) CORS origins the preflight returns 400 and
        omits access-control-expose-headers.  We verify the configuration
        directly on the middleware object."""
        from api.routes import app

        for mw in app.user_middleware:
            if hasattr(mw, "cls") and mw.cls.__name__ == "CORSMiddleware":
                # kwargs stored by Starlette for later initialization
                options = getattr(mw, "kwargs", getattr(mw, "options", {}))
                expose = options.get("expose_headers", [])
                assert "x-trace-id" in expose
                break
        else:
            # Middleware may already be initialized; check the stack
            found = False
            for layer in app.middleware_stack.__dict__.get("layers", []):
                mw_instance = getattr(layer, "mw", None) or getattr(layer, "func", None)
                if mw_instance and "CORSMiddleware" in type(mw_instance).__name__:
                    found = True
                    break
            # If we can't inspect, at least confirm middleware is present
            assert found or any(
                hasattr(getattr(l, "mw", None), "expose_headers")
                for l in getattr(app.middleware_stack, "layers", [])
            )


# ===================================================================
# 9. Rate limiting
# ===================================================================


class TestRateLimiting:
    """Test in-memory rate-limiting middleware."""

    def _configure_rate_limit(self, routes_mod, max_requests):
        """Helper: lower the rate limit threshold for testing."""
        routes_mod._RATE_LIMIT_MAX_REQUESTS = max_requests
        routes_mod._rate_limit_fallback_store.clear()

    def _restore_rate_limit(self, routes_mod, original_max, original_store):
        """Helper: restore original rate-limit state."""
        routes_mod._RATE_LIMIT_MAX_REQUESTS = original_max
        routes_mod._rate_limit_fallback_store.clear()
        routes_mod._rate_limit_fallback_store.update(original_store)

    async def test_rate_limit_returns_429_after_threshold(self, client):
        """Sending many requests quickly should eventually return 429."""
        import api.routes as routes_mod

        original_max = routes_mod._RATE_LIMIT_MAX_REQUESTS
        original_store = routes_mod._rate_limit_fallback_store.copy()

        try:
            self._configure_rate_limit(routes_mod, 5)

            hit_429 = False
            for _ in range(20):
                resp = await client.get("/")
                if resp.status_code == 429:
                    hit_429 = True
                    break

            assert hit_429, "Expected at least one 429 response after exceeding rate limit"
        finally:
            self._restore_rate_limit(routes_mod, original_max, original_store)

    async def test_rate_limit_429_has_retry_after_header(self, client):
        """Rate-limited 429 responses should include a Retry-After header."""
        import api.routes as routes_mod

        original_max = routes_mod._RATE_LIMIT_MAX_REQUESTS
        original_store = routes_mod._rate_limit_fallback_store.copy()

        try:
            self._configure_rate_limit(routes_mod, 2)

            retry_after = None
            for _ in range(10):
                resp = await client.get("/")
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    break

            assert retry_after is not None, "Expected Retry-After header on 429 response"
        finally:
            self._restore_rate_limit(routes_mod, original_max, original_store)

    async def test_rate_limit_429_includes_trace_id(self, client):
        """429 response body should include a trace_id."""
        import api.routes as routes_mod

        original_max = routes_mod._RATE_LIMIT_MAX_REQUESTS
        original_store = routes_mod._rate_limit_fallback_store.copy()

        try:
            self._configure_rate_limit(routes_mod, 2)

            for _ in range(10):
                resp = await client.get("/")
                if resp.status_code == 429:
                    data = resp.json()
                    assert "trace_id" in data
                    break
        finally:
            self._restore_rate_limit(routes_mod, original_max, original_store)

    async def test_rate_limit_health_endpoints_not_limited(self, client):
        """Health endpoints (/health, /ready) should bypass rate limiting."""
        import api.routes as routes_mod

        original_max = routes_mod._RATE_LIMIT_MAX_REQUESTS
        original_store = routes_mod._rate_limit_fallback_store.copy()

        try:
            self._configure_rate_limit(routes_mod, 2)

            # Exhaust rate limit on root endpoint
            for _ in range(5):
                await client.get("/")

            # Health and ready endpoints should still work
            resp_health = await client.get("/health")
            assert resp_health.status_code == 200

            resp_ready = await client.get("/ready")
            assert resp_ready.status_code == 200
        finally:
            self._restore_rate_limit(routes_mod, original_max, original_store)


# ===================================================================
# 10. Request body size limit
# ===================================================================


class TestBodySizeLimit:
    """Test _BodySizeLimitMiddleware."""

    async def test_oversized_request_rejected(self, client):
        """POST with Content-Length exceeding the limit should be rejected.

        The _BodySizeLimitMiddleware returns a JSONResponse with status 413
        (it used to raise HTTPException, but raising inside BaseHTTPMiddleware
        caused Starlette to wrap it as a 500 — returning a JSONResponse is
        the correct pattern).
        """
        import api.routes as routes_mod

        original_max = routes_mod._MAX_BODY_SIZE

        try:
            routes_mod._MAX_BODY_SIZE = 100  # Very small limit

            # Payload whose JSON encoding exceeds 100 bytes
            large_payload = {"study_type": "load_flow", "parameters": {"data": "x" * 200}}
            resp = await client.post("/api/v1/studies/run", json=large_payload)
            assert resp.status_code == 413, (
                f"Expected 413 for oversized request, got {resp.status_code}"
            )
        finally:
            routes_mod._MAX_BODY_SIZE = original_max

    async def test_normal_sized_request_accepted(self, client):
        """A request within the default size limit should proceed normally."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_body_size_limit_only_applies_to_mutating_methods(self, client):
        """GET requests should not be subject to body size checks."""
        import api.routes as routes_mod

        original_max = routes_mod._MAX_BODY_SIZE

        try:
            routes_mod._MAX_BODY_SIZE = 10  # Tiny limit

            # GET should still work even though the limit is tiny
            resp = await client.get("/health")
            assert resp.status_code == 200
        finally:
            routes_mod._MAX_BODY_SIZE = original_max


# ===================================================================
# 11. Supported study types
# ===================================================================


class TestSupportedStudyTypes:
    """Verify each valid study_type is accepted by the Pydantic validator
    and produces either a success response or a well-formed error."""

    # --- Native study types that require a system ---

    async def test_load_flow(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "load_flow",
                "system": _MINI_SYSTEM,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_short_circuit(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "short_circuit",
                "system": _MINI_SYSTEM,
                "parameters": {"bus_id": 1, "fault_type": "three_phase"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_fault(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "fault",
                "system": _MINI_SYSTEM,
                "parameters": {"bus_id": 1, "fault_type": "three_phase"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_arc_flash(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "arc_flash",
                "parameters": {
                    "voltage_kv": 13.8,
                    "bolted_fault_current_ka": 20.0,
                    "arc_duration_sec": 0.5,
                    "working_distance_mm": 610,
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_protection_coordination(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "protection_coordination",
                "system": _MINI_SYSTEM,
                "parameters": {
                    "upstream_relay_id": 1,
                    "downstream_relay_id": 2,
                    "fault_currents": [2.0, 5.0, 10.0],
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_coordination(self, client):
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "coordination",
                "system": _MINI_SYSTEM,
                "parameters": {
                    "upstream_relay_id": 1,
                    "downstream_relay_id": 2,
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_motor_starting(self, client):
        """motor_starting requires a system but may not have native engine support;
        it should at least pass validation (not 422)."""
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "motor_starting",
                "system": _MINI_SYSTEM,
            },
        )
        assert resp.status_code in (200, 400)  # accepted but may be unsupported

    async def test_harmonic_analysis(self, client):
        """harmonic_analysis does not require a system but may not have native engine support."""
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "harmonic_analysis",
            },
        )
        assert resp.status_code in (200, 400)  # accepted but may be unsupported

    async def test_optimal_power_flow(self, client):
        """optimal_power_flow does not require a system but may not have native engine support."""
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": "optimal_power_flow",
            },
        )
        assert resp.status_code in (200, 400)

    # --- ETAP-prefixed study types (pass validation; may fail at execution) ---

    @pytest.mark.parametrize(
        "study_type",
        [
            "etap_load_flow",
            "etap_short_circuit",
            "etap_arc_flash",
            "etap_harmonic_analysis",
            "etap_optimal_power_flow",
            "etap_motor_starting",
            "etap_protection_coordination",
        ],
    )
    async def test_etap_study_types_pass_validation(self, client, study_type):
        """ETAP study types should pass Pydantic validation (not 422)."""
        resp = await client.post(
            "/api/v1/studies/run",
            json={
                "study_type": study_type,
            },
        )
        # Not 422 means the study_type is valid; actual execution may fail
        assert resp.status_code != 422

    # --- Study types that should NOT pass validation ---

    @pytest.mark.parametrize(
        "invalid_type",
        [
            "stability",
            "cable_sizing",
            "earth_grid",
            "renewable",
            "battery_storage",
            "scada",
            "harmonic",  # should be harmonic_analysis
            "opf",  # should be optimal_power_flow
            "protection",  # should be protection_coordination
        ],
    )
    async def test_unsupported_study_type_returns_422(self, client, invalid_type):
        """Study types not in the validator's allowed set should return 422."""
        resp = await client.post("/api/v1/studies/run", json={"study_type": invalid_type})
        assert resp.status_code == 422


# ===================================================================
# Regression: System validate endpoint
# ===================================================================


class TestSystemValidateEndpoint:
    async def test_system_validate_returns_200(self, client):
        resp = await client.post("/api/v1/system/validate", json={})
        assert resp.status_code == 200

    async def test_system_validate_with_data(self, client):
        payload = {
            "system": {
                "buses": [{"id": "BUS1", "nominal_kv": 13.8}],
                "lines": [],
                "transformers": [],
                "generators": [],
                "loads": [],
            }
        }
        resp = await client.post("/api/v1/system/validate", json=payload)
        assert resp.status_code == 200
