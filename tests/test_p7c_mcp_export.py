"""
tests/test_p7c_mcp_export.py — P7c security & regression tests.

Covers:
- MCP server health probe (api/agents.py, P7c):
  * SSRF guard: restricted IPs (loopback/private/link-local/etc.) are blocked.
  * HTTP transport is blocked unless MCP_HEALTH_ALLOW_HTTP is explicitly set.
  * stdio servers are resolved on PATH but NEVER spawned.
  * Invalid / missing configurations report status ``invalid``.
- Export ownership scoping (api/export.py, P7c):
  * ``_load_owned_project`` returns the project for the owner and for admins.
  * Non-owner (non-admin) access yields a uniform 404 (no existence oracle).
  * Regression: ``import api.export`` must succeed (guards against the
    SyntaxError that previously broke the module at import time).
"""

from __future__ import annotations

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
