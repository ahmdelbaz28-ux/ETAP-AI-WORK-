"""Tests for user_id validation in cua_confirmation_ws.py (P1 security fix).

Regression tests for the JWT ``user_id`` (sub) validation that prevents an
attacker-controlled / spoofed ``sub`` from bypassing the dual-confirmation
requirement on the life-safety CUA confirmation endpoint.
"""
import os
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import WebSocketDisconnect

import api.cua_confirmation_ws as cua_mod


def _make_websocket(token: str):
    """Build a mock WebSocket that supplies `token` via the query param."""
    ws = AsyncMock()
    ws.query_params.get = lambda key, default="": token if key == "token" else default
    ws.headers.get = lambda key, default="": default
    return ws


@pytest.mark.asyncio
async def test_invalid_user_id_rejected():
    """A non-alphanumeric JWT sub must close the socket with 1008 Invalid user_id."""
    ws = _make_websocket("fake.jwt.token")
    payload = {"type": "access", "sub": "user@123", "exp": 9999999999}

    with patch.object(jwt, "decode", return_value=payload), patch(
        "api.dependencies.JWT_SECRET_KEY", "secret"
    ), patch("api.dependencies.JWT_ALGORITHM", "HS256"):
        await cua_mod.cua_confirmation_ws(ws)

    ws.close.assert_called_once_with(code=1008, reason="Invalid user_id")


@pytest.mark.asyncio
async def test_valid_user_id_accepted():
    """A valid alphanumeric JWT sub must NOT be rejected for an invalid user_id."""
    ws = _make_websocket("fake.jwt.token")
    payload = {"type": "access", "sub": "user123", "exp": 9999999999}

    # Break the message loop immediately after connect via WebSocketDisconnect.
    ws.receive_text.side_effect = WebSocketDisconnect()

    with patch.object(jwt, "decode", return_value=payload), patch(
        "api.dependencies.JWT_SECRET_KEY", "secret"
    ), patch("api.dependencies.JWT_ALGORITHM", "HS256"), patch.object(
        cua_mod, "confirmation_broker"
    ) as broker:
        broker.connect = AsyncMock()
        broker.disconnect = AsyncMock()
        await cua_mod.cua_confirmation_ws(ws)

    # Session id derived from a valid user_id; never closed with Invalid user_id.
    close_calls = [c.kwargs for c in ws.close.call_args_list]
    assert not any(c.get("reason") == "Invalid user_id" for c in close_calls)
    broker.connect.assert_awaited_once()
