"""
tests/test_p7c_mcp_route_precedence.py — P7c MCP list route precedence regression.

ROOT CAUSE (P7c route defect):
    FastAPI (Starlette) matches routes in registration order. In
    ``api/agents.py`` the parameterized catch-all ``GET /{agent_id}`` was
    declared BEFORE the static ``GET /mcp-servers`` route, so
    ``GET /api/v1/agents/mcp-servers`` matched the catch-all with
    ``agent_id="mcp-servers"`` and returned 404 "Agent not found" — even
    with a valid API key. The MCP list handler was unreachable.

FIX:
    The static ``/mcp-servers`` route is now registered BEFORE the
    ``/{agent_id}`` catch-all, so the specific route wins
    (specific-over-parameterized precedence). The handler body is unchanged.

REGRESSION:
    These tests exercise REAL routing behavior through the FastAPI
    application (no source-string inspection):

    - authorized GET /api/v1/agents/mcp-servers -> 200 with the MCP list
      response shape (NOT the catch-all 404 "Agent not found")
    - missing API key -> 401 (auth boundary preserved)
    - invalid API key -> 401 (auth boundary preserved)
    - GET /api/v1/agents/{real-agent-id} -> still resolves the agent (200)
    - GET /api/v1/agents/{unknown-id} -> still the catch-all 404
      "Agent not found"
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_API_KEY = "p7c-route-test-api-key-0123456789abcdef"


@pytest.fixture
def route_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api import dependencies
    from api.agents import router as agents_router

    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", TEST_API_KEY)
    monkeypatch.setattr(dependencies, "API_KEY", TEST_API_KEY)
    monkeypatch.delenv("ENGINEERING_SERVICE_AUTH_DISABLED", raising=False)

    cfg = tmp_path / ".mcp.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "@modelcontextprotocol/server-filesystem",
                            "/tmp",
                        ],
                        "env": {"FS_TOKEN": "s3cret-value"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MCP_CONFIG_PATH", str(cfg))

    app = FastAPI()
    app.include_router(agents_router)
    return TestClient(app, raise_server_exceptions=False)


class TestMcpListRoutePrecedence:
    """GET /api/v1/agents/mcp-servers must resolve to the MCP list handler."""

    def test_authorized_mcp_list_resolves_to_mcp_handler(
        self, route_client: Any
    ) -> None:
        resp = route_client.get(
            "/api/v1/agents/mcp-servers", headers={"X-API-Key": TEST_API_KEY}
        )
        # Must NOT be answered by the /{agent_id} catch-all...
        assert resp.status_code != 404
        assert resp.status_code == 200
        body = resp.json()
        # ...and must be the MCP list response shape, not agent metadata.
        assert body.get("success") is True
        assert body.get("error") != "Agent not found"
        data = body["data"]
        assert isinstance(data["servers"], list)
        assert data["total"] == 1
        assert data["servers"][0]["id"] == "filesystem"
        assert data["config_path"].endswith(".mcp.json")
        # Secrets stay redacted server-side.
        assert "s3cret-value" not in json.dumps(body)
        assert data["servers"][0]["env_redacted"]["FS_TOKEN"] == "***REDACTED***"

    def test_missing_api_key_is_401(self, route_client: Any) -> None:
        resp = route_client.get("/api/v1/agents/mcp-servers")
        assert resp.status_code == 401

    def test_invalid_api_key_is_401(self, route_client: Any) -> None:
        resp = route_client.get(
            "/api/v1/agents/mcp-servers", headers={"X-API-Key": "wrong-key"}
        )
        assert resp.status_code == 401


class TestAgentLookupUnchanged:
    """The fix must not break ordinary /{agent_id} lookup behavior."""

    def test_real_agent_id_still_resolves(self, route_client: Any) -> None:
        resp = route_client.get("/api/v1/agents/load-flow-agent")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert body["agent"]["id"] == "load-flow-agent"
        assert "capabilities" in body["agent"]

    def test_unknown_agent_id_still_catch_all_404(self, route_client: Any) -> None:
        resp = route_client.get("/api/v1/agents/definitely-not-an-agent")
        assert resp.status_code == 404
        assert resp.json().get("error") == "Agent not found"
