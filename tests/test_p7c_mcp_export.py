"""
tests/test_p7c_mcp_export.py — P7c security & regression tests.

Covers:
- MCP server health probe (api/agents.py, P7c):
  * SSRF guard: restricted IPs (loopback/private/link-local/etc.) are blocked.
  * SSRF destination pinning: the HTTP client connects to the VALIDATED IP
    addresses; a DNS change between validation and connection cannot redirect
    the probe (DNS-rebinding/TOCTOU guard), while Host/TLS SNI semantics keep
    using the original hostname.
  * Redirects (301/302/307/308) are never followed and never mark the server
    as connected — only a verified 2xx does.
  * HTTP transport is blocked unless MCP_HEALTH_ALLOW_HTTP is explicitly set.
  * stdio servers are resolved on PATH but NEVER spawned.
  * Invalid / missing configurations report status ``invalid``.
  * Endpoint authorization: missing/invalid API keys are rejected with 401;
    unknown servers yield a uniform 404 (no existence oracle).
- Export ownership scoping (api/export.py, P7c):
  * ``_load_owned_project`` returns the project for the owner and for admins.
  * Non-owner (non-admin) access yields a uniform 404 (no existence oracle).
  * Regression: ``import api.export`` must succeed (guards against the
    SyntaxError that previously broke the module at import time).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB_URL = "sqlite+aiosqlite:///./data/test_p7c_export.db"

os.makedirs("data", exist_ok=True)
if os.path.exists("./data/test_p7c_export.db"):
    os.remove("./data/test_p7c_export.db")


# ── MCP health probe: SSRF guard ─────────────────────────────────────────────


class TestRestrictedIpGuard:
    """_is_restricted_ip must block every non-public destination."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",  # loopback
            "::1",  # IPv6 loopback
            "10.1.2.3",  # RFC1918
            "192.168.1.1",  # RFC1918
            "172.16.0.9",  # RFC1918
            "169.254.169.254",  # link-local (cloud metadata!)
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
            "0.0.0.0",  # unspecified
            "::ffff:127.0.0.1",  # IPv4-mapped loopback
            "::ffff:10.0.0.7",  # IPv4-mapped RFC1918
            "::ffff:169.254.169.254",  # IPv4-mapped link-local (metadata!)
            "not-an-ip",  # garbage input fails closed
            "",  # empty input fails closed
        ],
    )
    def test_restricted_ips_are_blocked(self, ip: str) -> None:
        from api.agents import _is_restricted_ip

        assert _is_restricted_ip(ip) is True

    @pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
    def test_public_ips_are_allowed(self, ip: str) -> None:
        from api.agents import _is_restricted_ip

        assert _is_restricted_ip(ip) is False


class TestRemoteMcpProbe:
    """_probe_remote_mcp pre-flight branches (no real network egress)."""

    def test_missing_url_is_invalid(self) -> None:
        from api.agents import _probe_remote_mcp

        result = _probe_remote_mcp("srv", {}, "http")
        assert result["status"] == "invalid"
        assert result["connected"] is False

    def test_bad_scheme_is_invalid(self) -> None:
        from api.agents import _probe_remote_mcp

        result = _probe_remote_mcp("srv", {"url": "ftp://example.com"}, "ftp")
        assert result["status"] == "invalid"

    def test_http_blocked_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from api.agents import _HTTP_BLOCKED_MSG, _probe_remote_mcp

        monkeypatch.delenv("MCP_HEALTH_ALLOW_HTTP", raising=False)
        result = _probe_remote_mcp("srv", {"url": "http://example.com"}, "http")
        assert result["status"] == "blocked"
        assert result["message"] == _HTTP_BLOCKED_MSG
        assert result["connected"] is False

    def test_loopback_blocked_even_over_https(self) -> None:
        # HTTPS does not bypass the SSRF guard: loopback must stay blocked.
        from api.agents import _RESTRICTED_IP_MSG, _probe_remote_mcp

        result = _probe_remote_mcp("srv", {"url": "https://127.0.0.1/x"}, "https")
        assert result["status"] == "blocked"
        assert result["message"] == _RESTRICTED_IP_MSG

    def test_unresolvable_host_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.agents import _probe_remote_mcp

        monkeypatch.setenv("MCP_HEALTH_ALLOW_HTTP", "1")
        result = _probe_remote_mcp(
            "srv", {"url": "http://256.256.256.256/x"}, "http"
        )
        assert result["status"] == "unreachable"
        assert result["connected"] is False


class TestStdioMcpProbe:
    """stdio servers must be resolved on PATH but NEVER executed."""

    def test_empty_command_is_invalid(self) -> None:
        from api.agents import _probe_stdio_mcp

        result = _probe_stdio_mcp("srv", {})
        assert result["status"] == "invalid"
        assert result["connected"] is False

    def test_resolvable_command_not_spawned(self) -> None:
        from api.agents import _probe_stdio_mcp

        # sys.executable always exists on the test host; the probe must only
        # resolve it via shutil.which and never launch it.
        result = _probe_stdio_mcp("srv", {"command": sys.executable})
        assert result["transport"] == "stdio"
        assert result["command_resolvable"] is True
        assert result["status"] == "ready"
        assert result["connected"] is False
        assert "NOT spawned" in result["message"]

    def test_unresolvable_command_is_unreachable(self) -> None:
        from api.agents import _probe_stdio_mcp

        result = _probe_stdio_mcp(
            "srv", {"command": "definitely-not-a-real-command-p7c-xyz"}
        )
        assert result["status"] == "unreachable"
        assert result["command_resolvable"] is False

    def test_transport_routing(self) -> None:
        from api.agents import _probe_mcp_server

        # Remote transports route to the remote probe (missing url -> invalid).
        assert _probe_mcp_server("srv", {"type": "http", "url": ""})["status"] == (
            "invalid"
        )
        # Default (no type) routes to the stdio probe.
        assert _probe_mcp_server("srv", {})["transport"] == "stdio"


# ── MCP health probe: SSRF destination pinning & redirect semantics ─────────


def _addrinfo(ip: str, port: int) -> list:
    """One IPv4 getaddrinfo result tuple for ``ip:port``."""
    import socket as _socket

    return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", (ip, port))]


class _FakeNetworkStream:
    """Minimal httpcore NetworkStream stand-in serving one canned response."""

    def __init__(self, response_bytes: bytes) -> None:
        self._response_bytes = response_bytes
        self._read_done = False
        self.tls_servername: Any = None

    def read(self, max_bytes: int, timeout: Any = None) -> bytes:
        if self._read_done:
            return b""
        self._read_done = True
        return self._response_bytes

    def write(self, data: bytes, timeout: Any = None) -> int:
        return len(data)

    def close(self) -> None:
        pass

    def start_tls(
        self, ssl_context: Any, server_hostname: Any = None, timeout: Any = None
    ) -> "_FakeNetworkStream":
        # Record the SNI/verification hostname: TLS semantics must keep using
        # the ORIGINAL hostname even though TCP is pinned to the validated IP.
        self.tls_servername = server_hostname
        return self

    def get_extra_info(self, info: str) -> Any:
        return None


class _RecordingBackend:
    """Fake httpcore backend that records the destinations actually used."""

    def __init__(self, response_bytes: bytes, naive_resolve: bool = False) -> None:
        self.attempts: list = []
        self.stream = _FakeNetworkStream(response_bytes)
        self._naive_resolve = naive_resolve

    def connect_tcp(
        self, host: str, port: int, timeout: Any = None,
        local_address: Any = None, socket_options: Any = None,
    ) -> _FakeNetworkStream:
        import ipaddress as _ipaddress
        import socket as _socket

        target = host
        if self._naive_resolve:
            try:
                _ipaddress.ip_address(host)
            except ValueError:
                # Simulate an HTTP client that re-resolves the hostname at
                # connect time (the vulnerable pre-hardening behaviour).
                target = _socket.getaddrinfo(host, port)[0][4][0]
        self.attempts.append((str(target), port))
        return self.stream


class _StubResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def read(self) -> bytes:
        return b""


class _StubPool:
    """Records requests; never follows redirects (one request per probe)."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.requests: list = []

    def request(self, method: str, url: str, headers: Any = None,
                extensions: Any = None) -> _StubResponse:
        self.requests.append((method, url))
        return _StubResponse(self.status)

    def close(self) -> None:
        pass


class TestSsrfDestinationPinning:
    """The HTTP client must connect to the validated IP, never re-resolve."""

    def test_connection_pinned_to_validated_ip_despite_dns_rebinding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpcore

        from api import agents as agents_mod

        monkeypatch.setenv("MCP_HEALTH_ALLOW_HTTP", "1")
        resolution_state = {"n": 0}

        def fake_getaddrinfo(host: str, port: int, family: int = 0,
                             type: int = 0, proto: int = 0, flags: int = 0):
            resolution_state["n"] += 1
            if resolution_state["n"] == 1:
                # First resolution (validation): public IP.
                return _addrinfo("93.184.216.34", port)
            # Later resolutions ("rebounded" DNS): loopback.
            return _addrinfo("127.0.0.1", port)

        monkeypatch.setattr(agents_mod.socket, "getaddrinfo", fake_getaddrinfo)

        backend = _RecordingBackend(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", naive_resolve=True
        )

        def factory(pinned_ips: list):
            return httpcore.ConnectionPool(
                network_backend=agents_mod._PinnedAddressBackend(
                    pinned_ips, delegate=backend
                )
            )

        monkeypatch.setattr(agents_mod, "_open_pinned_connection_pool", factory)

        result = agents_mod._probe_remote_mcp(
            "srv", {"url": "http://rebind.example.com/health"}, "http"
        )

        assert result["connected"] is True
        assert result["status"] == "ok"
        # The TCP connection went to the VALIDATED destination only — even
        # though "DNS" changed to 127.0.0.1 between validation and connect.
        assert backend.attempts == [("93.184.216.34", 80)]
        assert all(ip != "127.0.0.1" for ip, _ in backend.attempts)

    def test_https_pins_ip_but_keeps_original_tls_hostname(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpcore

        from api import agents as agents_mod

        monkeypatch.delenv("MCP_HEALTH_ALLOW_HTTP", raising=False)
        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                "93.184.216.34", port
            ),
        )
        backend = _RecordingBackend(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")

        def factory(pinned_ips: list):
            return httpcore.ConnectionPool(
                network_backend=agents_mod._PinnedAddressBackend(
                    pinned_ips, delegate=backend
                )
            )

        monkeypatch.setattr(agents_mod, "_open_pinned_connection_pool", factory)

        result = agents_mod._probe_remote_mcp(
            "srv", {"url": "https://tls.example.com/health"}, "https"
        )

        assert result["connected"] is True
        assert result["status"] == "ok"
        assert backend.attempts == [("93.184.216.34", 443)]
        # TLS/SNI/certificate verification still target the ORIGINAL hostname.
        assert backend.stream.tls_servername == "tls.example.com"


class TestProbeRestrictedDestinationMatrix:
    """Full-probe matrix: restricted resolutions are blocked pre-connect."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "::1",
            "10.0.0.7",
            "172.16.5.5",
            "192.168.1.10",
            "169.254.169.254",
            "224.0.0.5",  # multicast
            "240.0.0.3",  # reserved
            "0.0.0.0",  # unspecified
            "::ffff:10.0.0.7",  # IPv4-mapped private
        ],
    )
    def test_probe_blocks_restricted_resolutions(
        self, monkeypatch: pytest.MonkeyPatch, ip: str
    ) -> None:
        from api import agents as agents_mod

        monkeypatch.setenv("MCP_HEALTH_ALLOW_HTTP", "1")
        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                ip, port
            ),
        )

        def factory(pinned_ips: list):
            raise AssertionError(
                "connection pool must never be created for restricted targets"
            )

        monkeypatch.setattr(agents_mod, "_open_pinned_connection_pool", factory)

        # IPv6 literals must be bracketed in URLs.
        host = f"[{ip}]" if ":" in ip else ip
        result = agents_mod._probe_remote_mcp(
            "srv", {"url": f"http://{host}/health"}, "http"
        )

        assert result["connected"] is False
        assert result["status"] == "blocked"
        assert result["message"] == agents_mod._RESTRICTED_IP_MSG

    def test_probe_reports_unreachable_when_dns_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import socket as _socket

        from api import agents as agents_mod

        monkeypatch.setenv("MCP_HEALTH_ALLOW_HTTP", "1")

        def failing_getaddrinfo(*args: Any, **kwargs: Any):
            raise _socket.gaierror(8, "nodename nor servname provided")

        monkeypatch.setattr(agents_mod.socket, "getaddrinfo", failing_getaddrinfo)
        result = agents_mod._probe_remote_mcp(
            "srv", {"url": "http://no-such-host.invalid/health"}, "http"
        )
        assert result["connected"] is False
        assert result["status"] == "unreachable"


class TestRedirectSemantics:
    """``connected`` is True only after a verified 2xx; redirects never follow."""

    @pytest.mark.parametrize("code", [301, 302, 307, 308])
    def test_redirect_is_not_connected_and_not_followed(
        self, monkeypatch: pytest.MonkeyPatch, code: int
    ) -> None:
        from api import agents as agents_mod

        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                "93.184.216.34", port
            ),
        )
        pool = _StubPool(code)
        monkeypatch.setattr(
            agents_mod, "_open_pinned_connection_pool", lambda ips: pool
        )
        url = f"https://redirect.example.com/{code}"

        result = agents_mod._probe_remote_mcp("srv", {"url": url}, "https")

        assert result["connected"] is False
        assert result["status"] != "ok"
        assert result["reachable"] is True
        assert "redirect NOT followed" in result["message"]
        # Exactly ONE request — the redirect target was never requested.
        assert pool.requests == [("GET", url)]

    def test_2xx_is_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from api import agents as agents_mod

        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                "93.184.216.34", port
            ),
        )
        pool = _StubPool(200)
        monkeypatch.setattr(
            agents_mod, "_open_pinned_connection_pool", lambda ips: pool
        )

        result = agents_mod._probe_remote_mcp(
            "srv", {"url": "https://ok.example.com/health"}, "https"
        )

        assert result["connected"] is True
        assert result["status"] == "ok"
        assert result["http_status"] == 200

    def test_4xx_is_reachable_but_not_connected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api import agents as agents_mod

        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                "93.184.216.34", port
            ),
        )
        pool = _StubPool(404)
        monkeypatch.setattr(
            agents_mod, "_open_pinned_connection_pool", lambda ips: pool
        )

        result = agents_mod._probe_remote_mcp(
            "srv", {"url": "https://missing.example.com/health"}, "https"
        )

        assert result["connected"] is False
        assert result["status"] == "degraded"
        assert result["reachable"] is True


# ── Export ownership scoping ─────────────────────────────────────────────────


class _StubUser:
    """Minimal CurrentUser stand-in (only user_id/role are consulted)."""

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


@pytest.fixture
async def test_engine() -> AsyncGenerator[Any, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def setup_db(test_engine: Any) -> AsyncGenerator[None, None]:
    from api.database import Base
    from api.projects import Project  # noqa: F401 — register the model

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def owned_project(db_session: AsyncSession) -> dict[str, str]:
    from api.projects import Project

    project = Project(
        id=str(uuid.uuid4()), name="P7c Owner Project", created_by="user-1"
    )
    db_session.add(project)
    await db_session.commit()
    return {"id": project.id, "created_by": "user-1"}


class TestLoadOwnedProject:
    async def test_owner_can_load(
        self, db_session: AsyncSession, owned_project: dict
    ) -> None:
        from api.export import _load_owned_project

        project = await _load_owned_project(
            owned_project["id"], _StubUser("user-1", "engineer"), db_session
        )
        assert project.id == owned_project["id"]

    async def test_admin_can_load_any(
        self, db_session: AsyncSession, owned_project: dict
    ) -> None:
        from api.export import _load_owned_project

        project = await _load_owned_project(
            owned_project["id"], _StubUser("admin-9", "admin"), db_session
        )
        assert project.id == owned_project["id"]

    async def test_non_owner_gets_uniform_404(
        self, db_session: AsyncSession, owned_project: dict
    ) -> None:
        from fastapi import HTTPException

        from api.export import _load_owned_project

        with pytest.raises(HTTPException) as exc_info:
            await _load_owned_project(
                owned_project["id"], _StubUser("user-2", "engineer"), db_session
            )
        # Uniform 404 — must NOT be a 403 (existence-oracle prevention).
        assert exc_info.value.status_code == 404

    async def test_missing_project_is_404(self, db_session: AsyncSession) -> None:
        from fastapi import HTTPException

        from api.export import _load_owned_project

        with pytest.raises(HTTPException) as exc_info:
            await _load_owned_project(
                str(uuid.uuid4()), _StubUser("user-1", "engineer"), db_session
            )
        assert exc_info.value.status_code == 404


class TestExportImportRegression:
    """Regression: api/export.py previously failed at import time (SyntaxError)."""

    def test_import_api_export_succeeds(self) -> None:
        # The module-level import itself is the regression check: it fails
        # immediately on any SyntaxError (as previously happened on line 274).
        # NOTE: importlib.reload is intentionally avoided — it would re-execute
        # the SQLAlchemy declarative models and raise InvalidRequestError.
        import api.export as export_module

        assert hasattr(export_module, "export_pdf")
        assert hasattr(export_module, "export_excel")
        assert hasattr(export_module, "export_history")
        assert hasattr(export_module, "_load_owned_project")
        assert hasattr(export_module, "_sanitize_filename")


# ── MCP health endpoint authorization (P7c RBAC evidence) ────────────────────


class TestMcpHealthEndpointAuthorization:
    """Authorization boundary evidence for the MCP health endpoint.

    Architecture note: MCP servers live in ONE platform-global ``.mcp.json``
    with no per-tenant dimension, so tenant-scoped RBAC does not apply to the
    resource itself. The API-wide ``get_api_key`` dependency is the shared
    authorization boundary; these tests prove it is actually enforced on the
    health endpoint (401 without/with-bad key, uniform 404 for unknown
    servers).

    Historical finding (identified during P7c hardening, FIXED in the
    subsequent route-precedence commit): the ``GET /mcp-servers`` listing
    route was shadowed by the earlier-registered ``GET /{agent_id}``
    catch-all in ``api/agents.py``, answering 404 "Agent not found"
    regardless of authorization.

    ROOT CAUSE: FastAPI matches routes in registration order; the
    parameterized ``/{agent_id}`` route was declared before the static
    ``/mcp-servers`` route, so every one-segment GET path under
    ``/api/v1/agents`` hit the catch-all first.

    FIX: the static ``/mcp-servers`` route is now registered BEFORE
    ``/{agent_id}`` (specific-over-parameterized precedence).

    REGRESSION: ``tests/test_p7c_mcp_route_precedence.py`` proves, through
    real request routing, that the MCP list handler now serves
    ``GET /mcp-servers`` (authorized 200 with the MCP list shape; 401
    without/with-bad key) while ordinary ``/{agent_id}`` lookup still
    behaves as before.
    """

    @pytest.fixture
    def health_client(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api import dependencies
        from api.agents import router as agents_router

        monkeypatch.setattr(
            dependencies, "API_KEY", "p7c-test-api-key-0123456789abcdef"
        )
        monkeypatch.delenv("ENGINEERING_SERVICE_AUTH_DISABLED", raising=False)

        cfg = tmp_path / ".mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "remote_ok": {"type": "http", "url": "https://mcp.example.com"}
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("MCP_CONFIG_PATH", str(cfg))

        app = FastAPI()
        app.include_router(agents_router)
        return TestClient(app, raise_server_exceptions=False)

    def test_missing_api_key_is_401(self, health_client: Any) -> None:
        resp = health_client.post("/api/v1/agents/mcp-servers/remote_ok/health")
        assert resp.status_code == 401

    def test_invalid_api_key_is_401(self, health_client: Any) -> None:
        resp = health_client.post(
            "/api/v1/agents/mcp-servers/remote_ok/health",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_unknown_server_is_uniform_404(self, health_client: Any) -> None:
        resp = health_client.post(
            "/api/v1/agents/mcp-servers/does-not-exist/health",
            headers={"X-API-Key": "p7c-test-api-key-0123456789abcdef"},
        )
        assert resp.status_code == 404
        body = resp.json()
        # Uniform response — no oracle about configured server names.
        assert body.get("errors") == ["MCP server not found"]
        assert "does-not-exist" not in json.dumps(body)

    def test_authorized_health_probe_returns_result(
        self, health_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api import agents as agents_mod

        monkeypatch.setattr(
            agents_mod.socket,
            "getaddrinfo",
            lambda host, port, family=0, type=0, proto=0, flags=0: _addrinfo(
                "93.184.216.34", port
            ),
        )
        pool = _StubPool(200)
        monkeypatch.setattr(
            agents_mod, "_open_pinned_connection_pool", lambda ips: pool
        )

        resp = health_client.post(
            "/api/v1/agents/mcp-servers/remote_ok/health",
            headers={"X-API-Key": "p7c-test-api-key-0123456789abcdef"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["connected"] is True
        assert data["status"] == "ok"
