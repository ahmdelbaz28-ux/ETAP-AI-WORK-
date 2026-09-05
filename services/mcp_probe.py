"""
MCP Health Probe Service
========================
SSRF-guarded health probing for Model Context Protocol (MCP) servers.

Provides:
- Destination IP pinning to prevent TOCTOU DNS-rebinding attacks
- Loopback, private, link-local, multicast, and IPv4-mapped IPv6 IP rejection
- HTTPS-only transport enforcement by default
- Stdio command verification without execution
"""

from __future__ import annotations

import ipaddress
import logging
import os
import shutil
import socket
import urllib.parse
from typing import Any, Optional

logger = logging.getLogger(__name__)

_RESTRICTED_IP_MSG = "Target resolves to a restricted network destination (SSRF guard)."
_HTTP_BLOCKED_MSG = "Remote MCP endpoints must use HTTPS (HTTP transport is disabled)."


def _is_restricted_ip(ip: str) -> bool:
    """True for loopback/private/link-local/multicast/reserved/unspecified IPs.

    IPv4-mapped IPv6 addresses (e.g. ``::ffff:127.0.0.1``) are unwrapped to
    their IPv4 form first so mapped restricted addresses cannot slip through
    on Python versions whose ``ipaddress`` properties do not account for
    IPv4-mapped IPv6.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _probe_headers() -> dict[str, str]:
    """Minimal headers — NO auth, NO cookies, NO secrets."""
    return {
        "User-Agent": "ETAP-AI-mcp-health-probe/1.0",
        "Accept": "application/json",
    }


class _PinnedAddressBackend:
    """httpcore network-backend adapter that pins TCP connections to
    pre-validated IP addresses (SSRF anti-DNS-rebinding guard).

    ``socket.getaddrinfo()`` in :func:`_probe_remote_mcp` decides WHERE the
    probe is allowed to go, but a plain ``httpx.Client().get(url)`` would let
    the HTTP client resolve the hostname a second time when it opens the
    socket — a TOCTOU / DNS-rebinding gap (first resolution -> public IP,
    second resolution -> private IP). This adapter closes that gap: every TCP
    connection is opened to one of the already-validated IP addresses, while
    the request URL keeps the original hostname so the ``Host`` header, TLS
    SNI, and certificate-verification semantics are preserved exactly.

    Duck-types the ``httpcore.NetworkBackend`` interface (only
    ``connect_tcp`` is needed for sync TCP connections).
    """

    def __init__(
        self,
        pinned_ips: list,
        delegate: Any = None,
    ) -> None:
        self._pinned_ips = [ip for ip in pinned_ips if ip]
        self._delegate = delegate  # None -> real httpcore.SyncBackend

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Any = None,
        local_address: Any = None,
        socket_options: Any = None,
    ) -> Any:
        _ = host  # deliberate: connections must be made to validated destination only
        if not self._pinned_ips:
            raise OSError("No validated IP address available for connection")
        import httpcore

        delegate = self._delegate
        if delegate is None:
            delegate = httpcore.SyncBackend()
        last_exc: Any = None
        for pinned_ip in self._pinned_ips:
            try:
                return delegate.connect_tcp(pinned_ip, port, timeout, local_address, socket_options)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if last_exc is not None:
            raise last_exc
        raise OSError("Connection to validated destination failed")


def _open_pinned_connection_pool(pinned_ips: list) -> Any:
    """Create an httpcore connection pool pinned to the validated IPs."""
    import httpcore

    return httpcore.ConnectionPool(network_backend=_PinnedAddressBackend(pinned_ips))


def _resolve_mcp_config_path() -> str:
    """Resolve the configured MCP config path (same source as list_mcp_servers)."""
    from pathlib import Path as _Path

    return os.getenv(
        "MCP_CONFIG_PATH",
        str(_Path(__file__).resolve().parent.parent / ".mcp.json"),
    )


def _probe_stdio_mcp(server_id: str, server_config: dict) -> dict[str, Any]:
    """Resolve a stdio launch command WITHOUT executing it."""
    command = str(server_config.get("command", "") or "").strip()
    if not command:
        return {
            "id": server_id,
            "transport": "stdio",
            "connected": False,
            "status": "invalid",
            "message": "MCP server has no launch command configured.",
        }
    resolvable = shutil.which(command) is not None
    return {
        "id": server_id,
        "transport": "stdio",
        "connected": False,
        "command_resolvable": resolvable,
        "status": "ready" if resolvable else "unreachable",
        "message": (
            "Local command is resolvable; the server is NOT spawned by this probe."
            if resolvable
            else "Local command is not resolvable on this host."
        ),
    }


def _validate_remote_url(
    server_id: str, url: str, transport: str
) -> tuple[Optional[urllib.parse.ParseResult], Optional[dict[str, Any]]]:
    if not url:
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP server has no url/endpoint configured.",
        }

    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL is not parseable.",
        }

    if parsed.scheme not in ("http", "https"):
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL scheme must be http/https.",
        }

    allow_http = os.getenv("MCP_HEALTH_ALLOW_HTTP", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if parsed.scheme == "http" and not allow_http:
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "blocked",
            "message": _HTTP_BLOCKED_MSG,
        }

    if not (parsed.hostname or ""):
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "invalid",
            "message": "Remote MCP endpoint URL has no host.",
        }
    return parsed, None


def _resolve_and_validate_remote_ips(
    server_id: str, transport: str, host: str, port: Optional[int], scheme: str
) -> tuple[Optional[list[str]], Optional[dict[str, Any]]]:
    fallback_port = 443 if scheme == "https" else 80
    try:
        addrinfos = socket.getaddrinfo(
            host, port if port else fallback_port, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        return None, {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "status": "unreachable",
            "message": "Remote MCP endpoint host could not be resolved.",
        }

    pinned_ips: list[str] = []
    for addr_info in addrinfos:
        candidate_ip = str(addr_info[4][0])
        if _is_restricted_ip(candidate_ip):
            return None, {
                "id": server_id,
                "transport": transport,
                "connected": False,
                "status": "blocked",
                "message": _RESTRICTED_IP_MSG,
            }
        if candidate_ip not in pinned_ips:
            pinned_ips.append(candidate_ip)
    return pinned_ips, None


def _probe_remote_mcp(
    server_id: str,
    server_config: dict,
    transport: str,
    pool_factory: Any = None,
) -> dict[str, Any]:
    """SSRF-guarded bare-GET health probe for remote MCP endpoints."""
    url = str(server_config.get("url") or server_config.get("endpoint") or "").strip()
    parsed, err_resp = _validate_remote_url(server_id, url, transport)
    if err_resp is not None or parsed is None:
        return err_resp or {}

    host = parsed.hostname or ""
    pinned_ips, ip_err = _resolve_and_validate_remote_ips(
        server_id, transport, host, parsed.port, parsed.scheme
    )
    if ip_err is not None or pinned_ips is None:
        return ip_err or {}

    try:
        open_pool = pool_factory if pool_factory is not None else _open_pinned_connection_pool
        pool = open_pool(pinned_ips)
        try:
            core_resp = pool.request(
                "GET",
                url,
                headers=_probe_headers(),
                extensions={
                    "timeout": {
                        "connect": 5.0,
                        "read": 5.0,
                        "write": 5.0,
                        "pool": 5.0,
                    }
                },
            )
            core_resp.read()
            status_code = int(core_resp.status)
        finally:
            pool.close()
        if 200 <= status_code < 300:
            status = "ok"
            message = f"Remote MCP endpoint responded with HTTP {status_code}."
        elif 300 <= status_code < 400:
            status = "degraded"
            message = (
                f"Remote MCP endpoint responded with HTTP {status_code} (redirect NOT followed)."
            )
        else:
            status = "degraded"
            message = f"Remote MCP endpoint responded with HTTP {status_code}."
        return {
            "id": server_id,
            "transport": transport,
            "connected": 200 <= status_code < 300,
            "reachable": True,
            "status": status,
            "http_status": status_code,
            "message": message,
        }
    except Exception:  # noqa: BLE001
        return {
            "id": server_id,
            "transport": transport,
            "connected": False,
            "reachable": False,
            "status": "unreachable",
            "message": "Remote MCP endpoint did not respond.",
        }


def _probe_mcp_server(
    server_id: str,
    server_config: dict,
    pool_factory: Any = None,
) -> dict[str, Any]:
    """Probe a single configured MCP server (never spawns it)."""
    transport = str(server_config.get("type", "stdio")).lower()
    if transport in ("http", "https", "sse", "websocket", "ws", "wss"):
        return _probe_remote_mcp(server_id, server_config, transport, pool_factory=pool_factory)
    return _probe_stdio_mcp(server_id, server_config)
