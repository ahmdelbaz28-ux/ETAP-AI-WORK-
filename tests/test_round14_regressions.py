"""tests/test_round14_regressions.py — Round 14 Verification and Regression Gates (G1–G7).

Covers:
1. Q5: Unrecognized parameter warnings propagated to top-level, data.warnings, and result.warnings.
2. R1: Duplicate load rejected with HTTP 422 (never 500/503).
3. R1: short_circuit missing lines rejected with HTTP 422 and MISSING_REQUIRED_SYSTEM_DATA (never 503, no is_simulated).
4. R1: short_circuit bus_id 999 rejected with HTTP 422 (never 500).
5. Pre-flight units: Bare floats 10.0 and -22.0 degrees pass _pre_flight_units.
6. Physical operating bounds: Start voltages 0.9 and 1.1 pass 0.5-2.0 p.u. envelope.
7. Feature flags fail-closed: All non-GA flags default to False in clean environment.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from api.csrf import generate_csrf_token
from api.feature_flags import DEFAULT_FEATURE_FLAGS
from core_model.specs import BusSpec, SystemSpec
from services.study_executor import StudyExecutor


@pytest.fixture
def app():
    from api.routes import app

    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    headers = {"x-csrf-token": generate_csrf_token()}
    api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


_VALID_SYSTEM = {
    "base_mva": 100.0,
    "buses": [
        {"bus_id": 1, "name": "Bus-1", "base_kv": 115.0, "bus_type": "slack", "voltage_magnitude": 1.0, "voltage_angle": 0.0},
        {"bus_id": 2, "name": "Bus-2", "base_kv": 115.0, "bus_type": "pq", "voltage_magnitude": 1.0, "voltage_angle": 0.0},
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
    ],
}


class TestRound14Regressions:
    @pytest.mark.asyncio
    async def test_q5_unrecognized_param_propagates_warnings(self, client):
        """Unrecognized parameter 'totally_bogus_param_xyz' produces warning on top-level, data, and result."""
        payload = {
            "study_type": "load_flow",
            "system": _VALID_SYSTEM,
            "parameters": {
                "max_iterations": 20,
                "tolerance": 1e-5,
                "totally_bogus_param_xyz": 42,
            },
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("success") is True

        expected_msg = "Ignored unrecognized parameter in load_flow study: 'totally_bogus_param_xyz'"

        top_warnings = body.get("warnings", [])
        assert any(expected_msg in str(w) for w in top_warnings), f"Missing in top-level warnings: {top_warnings}"

        data_warnings = body.get("data", {}).get("warnings", [])
        assert any(expected_msg in str(w) for w in data_warnings), f"Missing in data.warnings: {data_warnings}"

        result_warnings = body.get("result", {}).get("warnings", [])
        assert any(expected_msg in str(w) for w in result_warnings), f"Missing in result.warnings: {result_warnings}"

    @pytest.mark.asyncio
    async def test_duplicate_load_rejected_with_422(self, client):
        """Duplicate load definition (in bus fields and loads array) must return 422, not 500."""
        payload = {
            "study_type": "load_flow",
            "system": {
                "base_mva": 100.0,
                "buses": [
                    {
                        "bus_id": 1,
                        "name": "Bus-1",
                        "base_kv": 115.0,
                        "bus_type": "slack",
                        "voltage_magnitude": 1.0,
                        "voltage_angle": 0.0,
                    },
                    {
                        "bus_id": 2,
                        "name": "Bus-2",
                        "base_kv": 115.0,
                        "bus_type": "pq",
                        "voltage_magnitude": 1.0,
                        "voltage_angle": 0.0,
                        "load_power_real": 10.0,
                        "load_power_imag": 5.0,
                    },
                ],
                "lines": [
                    {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
                ],
                "loads": [
                    {"load_id": 1, "bus_id": 2, "p_mw": 10.0, "q_mvar": 5.0},
                ],
            },
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 422, f"Expected 422 for duplicate load but got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("is_simulated") is not True
        detail_or_err = str(body)
        assert "Duplicate load definition is rejected" in detail_or_err or "duplicate" in detail_or_err.lower()

    @pytest.mark.asyncio
    async def test_short_circuit_without_lines_rejected_with_422(self, client):
        """short_circuit without lines must return 422 with MISSING_REQUIRED_SYSTEM_DATA and no is_simulated."""
        payload = {
            "study_type": "short_circuit",
            "system": {
                "base_mva": 100.0,
                "buses": [
                    {"bus_id": 1, "name": "Bus-1", "base_kv": 115.0, "bus_type": "slack"},
                    {"bus_id": 2, "name": "Bus-2", "base_kv": 115.0, "bus_type": "pq"},
                ],
                "lines": [],
            },
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 422, f"Expected 422 for missing lines but got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("is_simulated") is not True
        detail_or_err = str(body)
        assert "MISSING_REQUIRED_SYSTEM_DATA" in detail_or_err or "lines" in detail_or_err

    @pytest.mark.asyncio
    async def test_short_circuit_bus_999_rejected_with_422(self, client):
        """short_circuit on non-existent bus 999 must return 422, not 500."""
        payload = {
            "study_type": "short_circuit",
            "system": _VALID_SYSTEM,
            "parameters": {
                "bus_id": 999,
                "fault_type": "three_phase",
            },
        }
        resp = await client.post("/api/v1/studies/run", json=payload)
        assert resp.status_code == 422, f"Expected 422 for bus 999 not found but got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("is_simulated") is not True
        detail_or_err = str(body)
        assert "999" in detail_or_err or "not found" in detail_or_err.lower()

    def test_pre_flight_units_bare_floats_pass(self):
        """Bare degree floats (10.0 and -22.0) pass _pre_flight_units."""
        executor = StudyExecutor()
        sys = SystemSpec(
            base_mva=100.0,
            buses=[
                BusSpec(bus_id=1, base_kv=115.0, voltage_angle=10.0, bus_type="slack"),
                BusSpec(bus_id=2, base_kv=115.0, voltage_angle=-22.0, bus_type="pq"),
            ],
            lines=[
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
            ],
        )
        # Should return None (no error)
        err = executor._pre_flight_units(sys)
        assert err is None, f"Expected None but got: {err}"

    def test_start_voltages_in_envelope(self):
        """Initial voltages 0.9 and 1.1 pass the 0.5-2.0 p.u. envelope."""
        executor = StudyExecutor()
        sys = SystemSpec(
            base_mva=100.0,
            buses=[
                BusSpec(bus_id=1, base_kv=115.0, voltage_magnitude=0.9, bus_type="slack"),
                BusSpec(bus_id=2, base_kv=115.0, voltage_magnitude=1.1, bus_type="pq"),
            ],
            lines=[
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.0},
            ],
        )
        # Should return None (no error)
        err = executor._pre_flight_voltage_bounds(sys.buses)
        assert err is None, f"Expected None but got: {err}"

    def test_clean_environment_feature_flags_fail_closed(self):
        """All non-GA registry flags must be disabled (fail-closed)."""
        ga_flags = {"production_hardening", "chat_first_ui"}
        for key, cfg in DEFAULT_FEATURE_FLAGS.items():
            if key in ga_flags:
                assert cfg.get("enabled") is True
            else:
                assert cfg.get("enabled") is False, f"Flag '{key}' must default to False (fail-closed)"
                assert cfg.get("rollout_percentage") == 0, f"Flag '{key}' rollout_percentage must be 0"
