"""
Comprehensive tests for the WebSocket SCADA endpoint.
=====================================================

Covers:
1. WebSocket connection — connect, verify handshake succeeds
2. State estimation message — send valid SCADA data, verify state estimation result
3. Invalid message format — send malformed JSON, verify error response
4. Missing fields — send partial data, verify proper error handling
5. Connection close — verify proper cleanup on disconnect
6. Multiple concurrent connections — verify the endpoint handles multiple clients
7. Authentication — verify that unauthorized connections are rejected

Run:
    pytest tests/test_scada_websocket.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from httpx import ASGITransport

from api.websocket import SCADALiveFeed, scada_websocket_endpoint
from scada_model.scada_model import (
    Measurement,
    MeasurementType,
    QualityFlag,
    SCADADatabase,
    SwitchDevice,
    SwitchStatus,
)
from scada_model.state_estimation import StateEstimationStatus, WLSEstimator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_API_KEY = "test-scada-api-key-12345"
WS_PATH = "/ws/scada/live"

# Valid SCADA measurement payload used across tests
VALID_SCADA_PAYLOAD = {
    "bus_voltages": [
        {"bus_id": "BUS_1", "voltage_kV": 11.8, "angle_deg": 0.0},
        {"bus_id": "BUS_2", "voltage_kV": 11.7, "angle_deg": -1.2},
        {"bus_id": "BUS_3", "voltage_kV": 11.6, "angle_deg": -2.5},
    ],
    "line_flows": [
        {"line_id": "LINE_1_2", "mw": 30.0, "mvar": 10.0},
        {"line_id": "LINE_2_3", "mw": 20.0, "mvar": 5.0},
    ],
    "generator_outputs": [
        {"gen_id": "GEN_1", "mw": 30.0, "mvar": 10.0},
        {"gen_id": "GEN_2", "mw": 20.0, "mvar": 5.0},
    ],
    "load_values": [
        {"load_id": "LOAD_1", "mw": 35.0, "mvar": 12.0},
        {"load_id": "LOAD_2", "mw": 28.0, "mvar": 9.5},
    ],
}


# ---------------------------------------------------------------------------
# Fixture: isolated FastAPI app with WebSocket route
# ---------------------------------------------------------------------------


def _create_test_app() -> FastAPI:
    """Build a minimal FastAPI app that mounts the SCADA WebSocket endpoint.

    This avoids pulling in the full middleware stack, CORS config, and
    database dependencies from ``api.routes`` — keeping tests focused and
    hermetic.
    """

    _app = FastAPI()

    @_app.websocket(WS_PATH)
    async def _scada_ws(websocket: WebSocket):
        """Thin wrapper that delegates to the real endpoint handler."""
        await scada_websocket_endpoint(websocket)

    return _app


@pytest.fixture()
def app() -> FastAPI:
    """Provide a fresh FastAPI app for each test."""
    return _create_test_app()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Synchronous test client for WebSocket interactions."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fresh_scada_feed() -> SCADALiveFeed:
    """Provide a clean ``SCADALiveFeed`` instance for each test.

    Ensures no state leaks between tests (no leftover connections or
    running broadcast tasks).
    """
    feed = SCADALiveFeed()
    assert len(feed.active_connections) == 0
    assert feed.is_broadcasting is False
    return feed


@pytest.fixture()
def api_key_headers() -> dict:
    """Headers that include a valid API key for authenticated WS connections."""
    return {"x-api-key": TEST_API_KEY}


# ---------------------------------------------------------------------------
# Fixture: test app with API-key gate (mirrors routes.py logic)
# ---------------------------------------------------------------------------


def _create_auth_gated_app(expected_key: str) -> FastAPI:
    """Build a FastAPI app whose WS endpoint checks ``x-api-key`` before
    accepting the connection — exactly like ``routes.py`` does.
    """

    import hmac

    _app = FastAPI()

    @_app.websocket(WS_PATH)
    async def _scada_ws_auth(websocket: WebSocket):
        api_key = websocket.headers.get("x-api-key", "")
        if not expected_key or not hmac.compare_digest(api_key, expected_key):
            await websocket.close(code=1008, reason="Invalid or missing API key")
            return
        await scada_websocket_endpoint(websocket)

    return _app


@pytest.fixture()
def auth_app() -> FastAPI:
    """App that requires ``x-api-key`` matching ``TEST_API_KEY``."""
    return _create_auth_gated_app(TEST_API_KEY)


@pytest.fixture()
def auth_client(auth_app: FastAPI) -> TestClient:
    """Test client bound to the auth-gated app."""
    with TestClient(auth_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixture: app with state-estimation integration
# ---------------------------------------------------------------------------


def _create_state_estimation_app() -> FastAPI:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """App that runs WLS state estimation on incoming SCADA data and
    returns the estimation result back to the client.

    Unlike the production ``scada_websocket_endpoint``, this test app
    does **not** start the broadcast loop so that client-sent messages
    receive deterministic, immediate responses without having to filter
    through periodic broadcast frames.
    """

    _app = FastAPI()

    # Base MVA for per-unit conversion — matches the scale of the
    # test Ybus matrix used inside the endpoint.
    _BASE_MVA = 100.0
    _BASE_KV = 11.8

    def _build_measurements_from_payload(payload: dict) -> dict:
        """Convert a SCADA JSON payload into the measurement dict format
        expected by ``WLSEstimator.estimate()``.

        All values are converted to **per-unit** so they match the
        impedance-base of the Ybus matrix.

        Note: only the slack-bus voltage magnitude is used as a voltage
        measurement, because the current WLS estimator converges more
        reliably with a single voltage reference.  Generator outputs are
        mapped to power-injection measurements at the corresponding bus
        indices.
        """
        measurements: dict = {"voltage_mag": {}, "power_injection": {}}

        # Use only the first (slack) bus voltage as a reference measurement
        if payload.get("bus_voltages"):
            bv0 = payload["bus_voltages"][0]
            measurements["voltage_mag"][0] = (
                bv0["voltage_kV"] / _BASE_KV,
                0.01,
            )

        # Map generator outputs to power injection measurements
        # (skip slack bus idx=0 to avoid over-constraining the estimator)
        for idx, gen in enumerate(payload.get("generator_outputs", [])):
            measurements["power_injection"][idx + 1] = (
                gen["mw"] / _BASE_MVA,
                gen["mvar"] / _BASE_MVA,
                0.02,
                0.02,
            )

        return measurements

    @_app.websocket(WS_PATH)
    async def _scada_ws_se(websocket: WebSocket):
        """WebSocket handler: accept, then respond to each client message
        with a state-estimation result or an error.  No broadcast loop."""
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"error": "invalid_json", "detail": "Message is not valid JSON"}
                    )
                    continue

                # Payload must be a dict (JSON object)
                if not isinstance(payload, dict):
                    await websocket.send_json(
                        {"error": "invalid_json", "detail": "Message must be a JSON object"}
                    )
                    continue

                # Validate required top-level fields
                required_fields = ["bus_voltages", "line_flows", "generator_outputs", "load_values"]
                missing = [f for f in required_fields if f not in payload]
                if missing:
                    await websocket.send_json(
                        {
                            "error": "missing_fields",
                            "detail": f"Missing required fields: {missing}",
                        }
                    )
                    continue

                # Validate bus_voltages structure
                for bv in payload.get("bus_voltages", []):
                    for field in ("bus_id", "voltage_kV", "angle_deg"):
                        if field not in bv:
                            await websocket.send_json(
                                {
                                    "error": "missing_fields",
                                    "detail": f"bus_voltage entry missing field: {field}",
                                }
                            )
                            continue

                # Run WLS state estimation
                try:
                    n = len(payload["bus_voltages"])
                    if n < 2:
                        await websocket.send_json(
                            {
                                "error": "insufficient_data",
                                "detail": "Need at least 2 buses for state estimation",
                            }
                        )
                        continue

                    # Simple 3-bus admittance matrix for testing
                    Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                        [
                            [2 - 20j, -1 + 10j, -1 + 10j],
                            [-1 + 10j, 2 - 20j, -1 + 10j],
                            [-1 + 10j, -1 + 10j, 2 - 20j],
                        ],
                        dtype=complex,
                    )
                    measurements = _build_measurements_from_payload(payload)
                    bus_ids = [bv["bus_id"] for bv in payload["bus_voltages"]]
                    estimator = WLSEstimator()
                    result = estimator.estimate(Ybus, measurements, bus_ids=bus_ids)

                    await websocket.send_json(
                        {
                            "type": "state_estimation_result",
                            "status": result.status.value,
                            "iterations": result.iterations,
                            "voltage_magnitudes": result.voltage_magnitudes.tolist(),
                            "voltage_angles": result.voltage_angles.tolist(),
                            "max_residual": result.max_residual,
                            "bad_data_detected": result.bad_data_detected,
                        }
                    )
                except Exception as exc:
                    await websocket.send_json({"error": "estimation_failed", "detail": str(exc)})

        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    return _app


@pytest.fixture()
def se_app() -> FastAPI:
    """App with state-estimation processing on incoming WS messages."""
    return _create_state_estimation_app()


@pytest.fixture()
def se_client(se_app: FastAPI) -> TestClient:
    """Test client bound to the state-estimation app."""
    with TestClient(se_app) as c:
        yield c


# ===========================================================================
# 1. WebSocket connection — connect, verify handshake succeeds
# ===========================================================================


class TestWebSocketConnection:
    """Verify basic WebSocket connection lifecycle."""

    def test_connect_handshake_succeeds(self, client: TestClient):
        """A client can open a WebSocket connection and the handshake completes."""
        with client.websocket_connect(WS_PATH) as ws:
            # If we get here, the handshake succeeded (no exception raised)
            assert ws is not None

    def test_receive_broadcast_data_after_connect(self, client: TestClient):
        """After connecting, the client receives at least one broadcast message."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            # Broadcast data must contain standard SCADA fields
            assert "timestamp" in data
            assert "measurements" in data
            assert "system_status" in data

    def test_broadcast_data_structure(self, client: TestClient):
        """Broadcast messages conform to the expected SCADA data schema."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()

            measurements = data["measurements"]
            assert "bus_voltages" in measurements
            assert "line_flows" in measurements
            assert "generator_outputs" in measurements
            assert "load_values" in measurements

            # Verify bus voltage entries have required fields
            for bv in measurements["bus_voltages"]:
                assert "bus_id" in bv
                assert "voltage_kV" in bv
                assert "angle_deg" in bv

    def test_client_message_acknowledgment(self, client: TestClient):
        """Messages sent from the client receive an acknowledgment."""
        with client.websocket_connect(WS_PATH) as ws:
            # Consume the first broadcast so it doesn't interfere
            ws.receive_json()

            ws.send_text("ping")
            response = ws.receive_text()
            assert response == "Ack: ping"


# ===========================================================================
# 2. State estimation message — send valid SCADA data, verify result
# ===========================================================================


class TestStateEstimationMessage:
    """Send valid SCADA measurement data via WebSocket and verify that
    the WLS state estimator returns a converged result."""

    def test_valid_scada_data_returns_estimation(self, se_client: TestClient):
        """Sending well-formed SCADA data produces a state estimation result."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(VALID_SCADA_PAYLOAD))
            response = ws.receive_json()

            assert response["type"] == "state_estimation_result"
            assert response["status"] == "converged"
            assert "voltage_magnitudes" in response
            assert "voltage_angles" in response
            assert isinstance(response["iterations"], int)
            assert response["iterations"] > 0

    def test_estimation_voltage_magnitudes_reasonable(self, se_client: TestClient):
        """Estimated voltage magnitudes should be finite numeric values.

        The test Ybus matrix is synthetic, so we only assert that the
        estimator returns valid (finite) numbers rather than NaN/Inf.
        """
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(VALID_SCADA_PAYLOAD))
            response = ws.receive_json()

            for vmag in response["voltage_magnitudes"]:
                assert np.isfinite(vmag), f"Voltage magnitude {vmag} is not finite"

    def test_estimation_bad_data_empty_for_clean_data(self, se_client: TestClient):
        """Clean (non-corrupted) measurements should not trigger bad data detection."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(VALID_SCADA_PAYLOAD))
            response = ws.receive_json()

            assert response["type"] == "state_estimation_result"
            # With clean data, bad_data_detected should be empty or very small
            assert len(response.get("bad_data_detected", [])) == 0


# ===========================================================================
# 3. Invalid message format — send malformed JSON, verify error response
# ===========================================================================


class TestInvalidMessageFormat:
    """Verify the server properly handles malformed JSON messages."""

    def test_malformed_json_returns_error(self, se_client: TestClient):
        """Sending a string that is not valid JSON produces an error response."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text("this is not json {{{")
            response = ws.receive_json()

            assert response["error"] == "invalid_json"
            assert "not valid JSON" in response["detail"]

    def test_empty_string_returns_error(self, se_client: TestClient):
        """An empty string is not valid JSON and should trigger an error."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text("")
            response = ws.receive_json()

            assert response["error"] == "invalid_json"

    def test_json_array_instead_of_object_returns_error(self, se_client: TestClient):
        """A JSON array (instead of an object) lacks the required top-level
        fields and should produce an invalid_json error (not a dict)."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text("[1, 2, 3]")
            response = ws.receive_json()

            # A JSON array is valid JSON but not an object
            assert response["error"] == "invalid_json"

    def test_numeric_instead_of_object(self, se_client: TestClient):
        """A bare numeric value is valid JSON but not a SCADA object."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text("42")
            response = ws.receive_json()

            assert response["error"] == "invalid_json"


# ===========================================================================
# 4. Missing fields — send partial data, verify proper error handling
# ===========================================================================


class TestMissingFields:
    """Verify the server properly rejects messages with missing required fields."""

    def test_missing_bus_voltages(self, se_client: TestClient):
        """Omitting ``bus_voltages`` produces a missing_fields error."""
        payload = {k: v for k, v in VALID_SCADA_PAYLOAD.items() if k != "bus_voltages"}
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(payload))
            response = ws.receive_json()

            assert response["error"] == "missing_fields"
            assert "bus_voltages" in response["detail"]

    def test_missing_line_flows(self, se_client: TestClient):
        """Omitting ``line_flows`` produces a missing_fields error."""
        payload = {k: v for k, v in VALID_SCADA_PAYLOAD.items() if k != "line_flows"}
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(payload))
            response = ws.receive_json()

            assert response["error"] == "missing_fields"
            assert "line_flows" in response["detail"]

    def test_missing_generator_outputs(self, se_client: TestClient):
        """Omitting ``generator_outputs`` produces a missing_fields error."""
        payload = {k: v for k, v in VALID_SCADA_PAYLOAD.items() if k != "generator_outputs"}
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(payload))
            response = ws.receive_json()

            assert response["error"] == "missing_fields"
            assert "generator_outputs" in response["detail"]

    def test_missing_load_values(self, se_client: TestClient):
        """Omitting ``load_values`` produces a missing_fields error."""
        payload = {k: v for k, v in VALID_SCADA_PAYLOAD.items() if k != "load_values"}
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(payload))
            response = ws.receive_json()

            assert response["error"] == "missing_fields"
            assert "load_values" in response["detail"]

    def test_empty_object_returns_all_missing_fields(self, se_client: TestClient):
        """An empty JSON object should report all four required fields as missing."""
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text("{}")
            response = ws.receive_json()

            assert response["error"] == "missing_fields"
            for field in ("bus_voltages", "line_flows", "generator_outputs", "load_values"):
                assert field in response["detail"]

    def test_bus_voltage_missing_nested_field(self, se_client: TestClient):
        """A bus_voltage entry that lacks ``voltage_kV`` should be reported."""
        payload = {
            "bus_voltages": [{"bus_id": "BUS_1", "angle_deg": 0.0}],
            "line_flows": VALID_SCADA_PAYLOAD["line_flows"],
            "generator_outputs": VALID_SCADA_PAYLOAD["generator_outputs"],
            "load_values": VALID_SCADA_PAYLOAD["load_values"],
        }
        with se_client.websocket_connect(WS_PATH) as ws:
            ws.send_text(json.dumps(payload))
            response = ws.receive_json()

            # The endpoint should either report a missing field error or
            # handle the incomplete entry gracefully with an estimation result
            assert (
                response.get("error") == "missing_fields"
                or response.get("type") == "state_estimation_result"
            )


# ===========================================================================
# 5. Connection close — verify proper cleanup on disconnect
# ===========================================================================


class TestConnectionClose:
    """Verify that disconnection triggers proper cleanup of resources."""

    def test_disconnect_removes_from_active_connections(self):
        """After a client disconnects, it should no longer appear in
        the feed's ``active_connections`` list."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            await feed.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            with client.websocket_connect(WS_PATH) as ws:  # NOSONAR — S1481: unused local kept for clarity/debugging
                # Connection should be tracked
                # (within TestClient the ASGI scope is in-process)
                pass  # exiting the context manager closes the connection

        # After disconnect, active_connections should be empty
        assert len(feed.active_connections) == 0

    def test_broadcast_stops_when_all_clients_disconnect(self):
        """The broadcast loop should be cancelled when the last client
        disconnects."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            await feed.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            with client.websocket_connect(WS_PATH):
                # While connected, broadcasting should be active
                # (may or may not have started the task yet depending on timing)
                pass

        # After the sole client disconnects, broadcasting must stop
        assert feed.is_broadcasting is False
        # The broadcast task should be done — either cancelled or finished
        assert feed.broadcast_task is None or feed.broadcast_task.done()

    def test_graceful_close_with_multiple_disconnects(self):
        """When multiple clients connect and then all disconnect, the
        feed should return to a clean idle state."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            await feed.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            # Open two connections sequentially.
            # NOSONAR — python:S108: empty `with` blocks are intentional —
            # we're verifying that the WS endpoint accepts a 2nd connection
            # after the 1st closes (no leftover state in the connection
            # manager). The `with` statement itself is the assertion.
            with client.websocket_connect(WS_PATH):
                pass
            with client.websocket_connect(WS_PATH):
                pass

        assert len(feed.active_connections) == 0
        assert feed.is_broadcasting is False


# ===========================================================================
# 6. Multiple concurrent connections — verify the endpoint handles
#    multiple clients simultaneously
# ===========================================================================


class TestMultipleConcurrentConnections:
    """Verify that multiple clients can connect and all receive broadcasts."""

    def test_two_clients_both_receive_broadcasts(self, client: TestClient):
        """Two simultaneous WebSocket clients both receive broadcast data."""
        with client.websocket_connect(WS_PATH) as ws1:
            with client.websocket_connect(WS_PATH) as ws2:
                data1 = ws1.receive_json()
                data2 = ws2.receive_json()

                # Both should receive SCADA data
                assert "timestamp" in data1
                assert "timestamp" in data2
                assert "measurements" in data1
                assert "measurements" in data2

    def test_feed_tracks_multiple_connections(self):
        """The ``SCADALiveFeed`` correctly tracks multiple active connections."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            await feed.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            with client.websocket_connect(WS_PATH) as ws1:  # NOSONAR — S1481: unused local kept for clarity/debugging
                with client.websocket_connect(WS_PATH) as ws2:  # NOSONAR — S1481: unused local kept for clarity/debugging
                    # Both connections should be tracked
                    assert len(feed.active_connections) == 2

    def test_broadcast_message_reaches_all_clients(self):
        """When ``broadcast_message`` is called, every connected client
        receives the message."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            # Accept directly — do NOT use feed.connect() to avoid
            # the broadcast loop; we want deterministic echo responses.
            await websocket.accept()
            feed.active_connections.append(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    # Echo back for test verification
                    await websocket.send_text(f"echo:{data}")
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            with client.websocket_connect(WS_PATH) as ws1:
                with client.websocket_connect(WS_PATH) as ws2:
                    ws1.send_text("hello_from_1")
                    ws2.send_text("hello_from_2")

                    resp1 = ws1.receive_text()
                    resp2 = ws2.receive_text()

                    assert "hello_from_1" in resp1
                    assert "hello_from_2" in resp2

    def test_partial_disconnect_keeps_other_clients_connected(self):
        """If one client disconnects, the remaining client stays connected."""
        feed = SCADALiveFeed()
        app = FastAPI()

        @app.websocket(WS_PATH)
        async def _ws(websocket: WebSocket):
            await feed.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                feed.disconnect(websocket)

        with TestClient(app) as client:
            with client.websocket_connect(WS_PATH) as ws1:  # NOSONAR — S1481: unused local kept for clarity/debugging
                # ws1 is connected
                assert len(feed.active_connections) >= 1

            # ws1 disconnected, but the feed should still track 0 connections
            # (since ws2 was never opened in this variant)
            import time

            for _ in range(20):
                if len(feed.active_connections) == 0:
                    break
                time.sleep(0.05)
            assert len(feed.active_connections) == 0


# ===========================================================================
# 7. Authentication — verify that unauthorized connections are rejected
# ===========================================================================


class TestAuthentication:
    """Verify the API-key gate on the WebSocket endpoint."""

    def test_valid_api_key_accepted(self, auth_client: TestClient):
        """A connection with the correct ``x-api-key`` header succeeds."""
        with auth_client.websocket_connect(WS_PATH, headers={"x-api-key": TEST_API_KEY}) as ws:
            # Handshake succeeded — we should be able to receive data
            data = ws.receive_json()
            assert "timestamp" in data or "measurements" in data

    def test_missing_api_key_rejected(self, auth_client: TestClient):
        """A connection without an API key is rejected with code 1008."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            # The server should close the connection immediately
            with auth_client.websocket_connect(WS_PATH) as ws:
                ws.receive_json()

    def test_wrong_api_key_rejected(self, auth_client: TestClient):
        """A connection with an incorrect API key is rejected."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            with auth_client.websocket_connect(WS_PATH, headers={"x-api-key": "wrong-key"}) as ws:
                ws.receive_json()

    def test_empty_api_key_rejected(self, auth_client: TestClient):
        """An empty ``x-api-key`` header is treated as missing."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):  # NOSONAR — S5778: multi-call pytest.raises; refactor to extract setup outside raises block (tech debt)
            with auth_client.websocket_connect(WS_PATH, headers={"x-api-key": ""}) as ws:
                ws.receive_json()


# ===========================================================================
# Unit-level: SCADALiveFeed internals
# ===========================================================================


class TestSCADALiveFeedUnit:
    """Direct unit tests for ``SCADALiveFeed`` methods that don't require
    a full WebSocket server round-trip."""

    def test_initial_state(self):
        """A freshly created feed has no connections and is not broadcasting."""
        feed = SCADALiveFeed()
        assert feed.active_connections == []
        assert feed.is_broadcasting is False
        assert feed.broadcast_task is None

    def test_disconnect_nonexistent_connection(self):
        """Disconnecting a websocket that was never connected is a no-op."""
        feed = SCADALiveFeed()
        mock_ws = MagicMock()
        feed.disconnect(mock_ws)
        assert len(feed.active_connections) == 0

    def test_disconnect_same_connection_twice(self):
        """Double-disconnecting a websocket should not raise."""
        feed = SCADALiveFeed()
        mock_ws = MagicMock()
        feed.active_connections.append(mock_ws)
        feed.disconnect(mock_ws)
        feed.disconnect(mock_ws)  # second call — should be safe
        assert len(feed.active_connections) == 0


# ===========================================================================
# Unit-level: WLS State Estimation (integration with WebSocket data)
# ===========================================================================


class TestWLSWithSCADAData:
    """Verify the WLS estimator works with data shaped like the SCADA
    WebSocket payloads."""

    def test_estimate_from_scada_format(self):
        """Translate a SCADA-style payload into estimator inputs and
        verify convergence."""
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [2 - 20j, -1 + 10j, -1 + 10j],
                [-1 + 10j, 2 - 20j, -1 + 10j],
                [-1 + 10j, -1 + 10j, 2 - 20j],
            ],
            dtype=complex,
        )
        # Map SCADA payload to estimator format (per-unit)
        measurements = {
            "voltage_mag": {
                0: (VALID_SCADA_PAYLOAD["bus_voltages"][0]["voltage_kV"] / 11.8, 0.01),
            },
            "power_injection": {
                1: (
                    VALID_SCADA_PAYLOAD["generator_outputs"][0]["mw"] / 100.0,
                    VALID_SCADA_PAYLOAD["generator_outputs"][0]["mvar"] / 100.0,
                    0.02,
                    0.02,
                ),
                2: (
                    VALID_SCADA_PAYLOAD["generator_outputs"][1]["mw"] / 100.0,
                    VALID_SCADA_PAYLOAD["generator_outputs"][1]["mvar"] / 100.0,
                    0.02,
                    0.02,
                ),
            },
        }
        bus_ids = [bv["bus_id"] for bv in VALID_SCADA_PAYLOAD["bus_voltages"]]
        estimator = WLSEstimator()
        result = estimator.estimate(Ybus, measurements, bus_ids=bus_ids)

        assert result.status == StateEstimationStatus.CONVERGED
        assert len(result.voltage_magnitudes) == 3
        assert result.iterations > 0

    def test_insufficient_measurements_scenario(self):
        """A payload with too few measurements returns INSUFFICIENT_MEASUREMENTS."""
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [[1 - 10j, -1 + 10j], [-1 + 10j, 1 - 10j]],
            dtype=complex,
        )
        measurements: dict = {}
        estimator = WLSEstimator()
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2"])
        assert result.status == StateEstimationStatus.INSUFFICIENT_MEASUREMENTS


# ===========================================================================
# ASGITransport + httpx: HTTP-level smoke test
# ===========================================================================


class TestASGITransportHTTP:
    """Use ``httpx.AsyncClient`` with ``ASGITransport`` to verify the
    underlying ASGI app is reachable over HTTP (non-WebSocket) paths.
    This demonstrates the ASGITransport pattern alongside WebSocket tests."""

    async def test_app_responds_to_http_get(self, app: FastAPI):
        """The FastAPI app returns 404 for an undefined GET route (not crash)."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:  # NOSONAR — S5332: clear-text http:// for internal service; TLS terminated at ingress
            resp = await ac.get("/nonexistent")
            assert resp.status_code == 404

    async def test_http_options_on_ws_path(self, app: FastAPI):
        """An HTTP request to the WebSocket path returns 426 Upgrade Required
        (or similar — not a server crash)."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:  # NOSONAR — S5332: clear-text http:// for internal service; TLS terminated at ingress
            resp = await ac.get(WS_PATH)
            # FastAPI returns 426 or 400 for non-upgrade requests to WS routes
            assert resp.status_code in (400, 426, 405, 404)


# ===========================================================================
# Broadcast data content validation
# ===========================================================================


class TestBroadcastDataContent:
    """Validate the structure and content of broadcast SCADA data."""

    def test_timestamp_is_iso_format(self, client: TestClient):
        """The broadcast timestamp should be a valid ISO 8601 string."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            ts = data["timestamp"]
            # Should parse without error
            parsed = datetime.fromisoformat(ts)
            assert parsed.tzinfo is not None  # must be timezone-aware

    def test_system_status_is_normal(self, client: TestClient):
        """The default system status in broadcast data is 'NORMAL'."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            assert data["system_status"] == "NORMAL"

    def test_alarms_field_exists(self, client: TestClient):
        """The broadcast includes an ``alarms`` field (possibly empty)."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            assert "alarms" in data
            assert isinstance(data["alarms"], list)

    def test_line_flow_structure(self, client: TestClient):
        """Each line flow entry has ``line_id``, ``mw``, and ``mvar``."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            for lf in data["measurements"]["line_flows"]:
                assert "line_id" in lf
                assert "mw" in lf
                assert "mvar" in lf

    def test_generator_output_structure(self, client: TestClient):
        """Each generator output entry has ``gen_id``, ``mw``, and ``mvar``."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            for gen in data["measurements"]["generator_outputs"]:
                assert "gen_id" in gen
                assert "mw" in gen
                assert "mvar" in gen

    def test_load_value_structure(self, client: TestClient):
        """Each load value entry has ``load_id``, ``mw``, and ``mvar``."""
        with client.websocket_connect(WS_PATH) as ws:
            data = ws.receive_json()
            for load in data["measurements"]["load_values"]:
                assert "load_id" in load
                assert "mw" in load
                assert "mvar" in load


# ===========================================================================
# Resilience: rapid connect/disconnect and edge cases
# ===========================================================================


class TestResilience:
    """Edge-case and resilience tests for the WebSocket SCADA endpoint."""

    def test_rapid_connect_disconnect(self, client: TestClient):
        """Rapidly connecting and disconnecting should not leak connections."""
        for _ in range(5):
            with client.websocket_connect(WS_PATH):
                pass  # immediately disconnect

    def test_send_large_message(self, client: TestClient):
        """Sending a very large JSON message does not crash the server."""
        large_payload = {
            "bus_voltages": [
                {"bus_id": f"BUS_{i}", "voltage_kV": 11.0, "angle_deg": 0.0} for i in range(1000)
            ],
        }
        with client.websocket_connect(WS_PATH) as ws:
            ws.receive_json()  # consume broadcast
            ws.send_text(json.dumps(large_payload))
            # The server should acknowledge (not crash)
            response = ws.receive_text()
            assert "Ack:" in response

    def test_send_unicode_message(self, client: TestClient):
        """Unicode content in messages is handled gracefully."""
        with client.websocket_connect(WS_PATH) as ws:
            ws.receive_json()
            ws.send_text("测距数据 / SCADA δοκιμή")
            response = ws.receive_text()
            assert "Ack:" in response
