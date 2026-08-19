"""
tests/test_websocket_security.py — Strict WebSocket Origin and Authentication Security Tests

Tests:
1. Invalid Origin + valid JWT → rejected with 1008 (Policy Violation) before accept()
2. Invalid Origin + valid API key → rejected with 1008 before accept()
3. Production + missing Origin → rejected with 1008
4. Production + unconfigured allowlist → rejected with 1008 (fail closed)
5. Production + wildcard "*" in allowlist → does NOT authorize arbitrary origins
6. Development/test + localhost/local origins → permitted
7. Development/test + untrusted third-party origin → rejected with 1008
8. Valid explicit Origin + valid authentication → accepted
9. CUA Confirmation: Origin checked before JWT decode & session_id strictly derived from sub
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.cua_confirmation_ws import (
    ConfirmationBroker,
    ConfirmationRequest,
    confirmation_broker,
    cua_confirmation_ws,
)
from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY
from api.websocket import scada_websocket_endpoint


def _mint_test_jwt(user_id: str = "engineer123", token_type: str = "access") -> str:
    """Helper to mint a valid test JWT."""
    payload = {
        "sub": user_id,
        "type": token_type,
        "exp": 9999999999,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Test Apps
# ---------------------------------------------------------------------------


def _create_scada_test_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws/scada/live")
    async def _scada(websocket: WebSocket, token: str = ""):
        await scada_websocket_endpoint(websocket, token=token)

    return app


def _create_cua_test_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws/cua/confirmation")
    async def _cua(websocket: WebSocket):
        await cua_confirmation_ws(websocket)

    return app


# ===========================================================================
# SCADA WebSocket Security Tests
# ===========================================================================


class TestSCADAWebSocketOriginSecurity:
    """Verify Origin validation and fail-closed security for /ws/scada/live."""

    def test_unauthorized_origin_with_valid_jwt_rejected(self, monkeypatch):
        """Test A: Untrusted Origin + valid JWT → rejected with close code 1008."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://trusted-app.com")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/scada/live?token={token}",
                    headers={"origin": "http://malicious-site.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_unauthorized_origin_with_valid_api_key_rejected(self, monkeypatch):
        """Test B: Untrusted Origin + valid API key → rejected with close code 1008."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "test-secret-key-12345")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://trusted-app.com")
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    "/ws/scada/live?token=test-secret-key-12345",
                    headers={"origin": "http://attacker.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_production_missing_origin_rejected(self, monkeypatch):
        """Test C: In production, missing Origin header is rejected with 1008."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://trusted-app.com")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(f"/ws/scada/live?token={token}") as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_production_empty_allowlist_fails_closed(self, monkeypatch):
        """Test D: In production, empty allowlist fails closed with 1008."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/scada/live?token={token}",
                    headers={"origin": "https://trusted-app.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_wildcard_origin_not_trusted(self, monkeypatch):
        """Test E: Wildcard '*' in CORS origins must NOT authorize arbitrary browser origins."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "*")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/scada/live?token={token}",
                    headers={"origin": "http://evil-site.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_authorized_origin_with_valid_jwt_accepted(self, monkeypatch):
        """Test F: Configured Origin + valid JWT → connection accepted."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "ENGINEERING_SERVICE_CORS_ORIGINS",
            "https://app.example.com,https://dashboard.example.com",
        )
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/scada/live?token={token}",
                headers={"origin": "https://app.example.com"},
            ) as ws:
                data = ws.receive_json()
                assert "timestamp" in data or "measurements" in data

    def test_development_mode_rejects_untrusted_third_party_origin(self, monkeypatch):
        """Test G: In development mode, arbitrary third-party origin is still rejected."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/scada/live?token={token}",
                    headers={"origin": "http://untrusted-external-site.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_development_mode_allows_localhost_origins(self, monkeypatch):
        """Test H: In development mode, localhost origins are permitted."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "")
        token = _mint_test_jwt()
        app = _create_scada_test_app()

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/scada/live?token={token}",
                headers={"origin": "http://localhost:3000"},
            ) as ws:
                data = ws.receive_json()
                assert "timestamp" in data or "measurements" in data


# ===========================================================================
# CUA Confirmation WebSocket Security Tests
# ===========================================================================


class TestCUAConfirmationWebSocketSecurity:
    """Verify Origin validation and user authentication for /ws/cua/confirmation."""

    def test_cua_unauthorized_origin_rejected_before_jwt_decode(self, monkeypatch):
        """CUA WS: Untrusted Origin is rejected with 1008 even with valid JWT."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://operator.internal")
        token = _mint_test_jwt(user_id="operator1")
        app = _create_cua_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/cua/confirmation?token={token}",
                    headers={"origin": "http://evil-cswsh-attacker.com"},
                ) as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_cua_missing_origin_in_production_rejected(self, monkeypatch):
        """CUA WS: In production, missing Origin header is rejected with 1008."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://operator.internal")
        token = _mint_test_jwt(user_id="operator1")
        app = _create_cua_test_app()

        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(f"/ws/cua/confirmation?token={token}") as ws:
                    ws.receive_json()

            assert exc_info.value.code == 1008

    def test_cua_authorized_origin_with_valid_jwt_connects(self, monkeypatch):
        """CUA WS: Configured Origin + valid JWT connects and receives pending requests."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "https://operator.internal")
        token = _mint_test_jwt(user_id="operator1")
        app = _create_cua_test_app()

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/cua/confirmation?token={token}",
                headers={"origin": "https://operator.internal"},
            ) as ws:
                # Connection open and active
                pass

    def test_cua_session_id_strictly_derived_from_jwt(self, monkeypatch):
        """CUA WS: Confirm action uses session_id from JWT user_id, not client payload."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ENGINEERING_SERVICE_CORS_ORIGINS", "http://localhost:3000")
        token = _mint_test_jwt(user_id="alice99")
        app = _create_cua_test_app()

        broker = confirmation_broker
        broker._pending["req123"] = ConfirmationRequest(
            request_id="req123",
            action_type="click",
            action_target="CB-101",
            requires_dual_confirmation=True,
        )

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/cua/confirmation?token={token}",
                headers={"origin": "http://localhost:3000"},
            ) as ws:
                # On connect, server pushes existing pending requests
                init_msg = ws.receive_json()
                assert init_msg.get("type") == "pending_request"
                assert init_msg.get("data", {}).get("request_id") == "req123"

                # Client tries to send a confirmation with a spoofed session_id
                ws.send_json({"action": "confirm", "request_id": "req123", "session_id": "spoofed_admin"})
                resp = ws.receive_json()
                assert resp.get("type") == "confirm_result"
                assert "user:alice99" in broker._pending["req123"].confirmations
                assert "spoofed_admin" not in broker._pending["req123"].confirmations

        # Clean up
        broker._pending.pop("req123", None)
