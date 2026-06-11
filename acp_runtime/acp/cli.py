"""Unified CLI entrypoint for ACP.

Usage::

    python -m acp stdio --handlers myapp.handlers
    python -m acp uds --handlers myapp.handlers --path /tmp/acp.sock
    python -m acp websocket --handlers myapp.handlers --host 0.0.0.0 --port 8765

With a config file::

    python -m acp stdio --config acp.yaml

Environment variables (all optional)::

    ACP_HANDLERS          -- Python module path for handler classes
    ACP_SCOPES            -- Comma-separated caller scopes
    ACP_AUTH_SECRET       -- HMAC secret for bearer-token auth
    ACP_AUTH_TTL          -- Token TTL in seconds (default 3600)
    ACP_REQUIRE_AUTH      -- Require auth for public capabilities (default false)
    ACP_AUDIT_LOG         -- Path to NDJSON audit log file
    ACP_TRACE_FILE        -- Path to JSON trace output file
    ACP_DEADLINE_MS       -- Default deadline in ms (default 30000)
    ACP_UDS_PATH          -- UDS socket path (default /tmp/acp.sock)
    ACP_WS_HOST           -- WebSocket bind host (default localhost)
    ACP_WS_PORT           -- WebSocket bind port (default 8765)
"""

from __future__ import annotations
import argparse
import importlib
import os
import sys
from typing import Any

import anyio

from acp import __version__
from acp.runtime import AcpRuntime
from acp.runtime.handler import discover_capabilities
from acp.router import Router, RouterConfig
from acp.transport import (
    StdioTransport,
    UDSListener,
    WebSocketListener,
    Server,
)
from acp.security import (
    AuthConfig,
    HmacTokenValidator,
    NDJSONAuditLogger,
)
from acp.observability import (
    JsonTracer,
    InMemoryMetricsRegistry,
    ConsoleStructuredLogger,
    LogLevel,
)
from acp.config import load_config, merge_config, env_int, env_bool
from acp.health import HealthHandler
from acp.http_server import start_http_server

__all__ = ["main"]


def _split_scopes(text: str | None) -> set[str]:
    if not text:
        return set()
    return {s.strip() for s in text.split(",") if s.strip()}


def _parse_labels(text: str | None) -> dict[str, str]:
    """Parse a comma-separated ``key=value`` string into a dict.

    Example: ``"transport=stdio,env=prod"`` → ``{"transport": "stdio", "env": "prod"}``
    """
    if not text:
        return {}
    result: dict[str, str] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"Invalid label format {part!r}. Expected key=value.")
        k, v = part.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def _load_handlers(module_path: str) -> list[Any]:
    """Import a module and instantiate all classes with @capability methods."""
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise SystemExit(f"Cannot import handlers module {module_path!r}: {e}") from e

    instances = []
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if isinstance(obj, type):
            # Use the same discovery mechanism as the runtime
            caps = discover_capabilities(obj)
            if caps:
                try:
                    instances.append(obj())
                except TypeError as e:
                    raise SystemExit(
                        f"Handler class {obj.__name__!r} requires constructor arguments: {e}"
                    ) from e
    return instances


def _build_observability(
    args: argparse.Namespace,
    transport_name: str = "unknown",
) -> tuple[Any, Any, Any]:
    """Build shared observability objects once.

    Returns (tracer, metrics, logger).
    """
    tracer = None
    if args.trace_file or os.environ.get("ACP_TRACE_FILE"):
        trace_path = args.trace_file or os.environ.get("ACP_TRACE_FILE")
        tracer = JsonTracer(trace_path)

    metrics = None
    if args.metrics or env_bool("ACP_METRICS", False):
        default_labels = _parse_labels(
            args.default_labels or os.environ.get("ACP_DEFAULT_LABELS")
        )
        if transport_name:
            default_labels["transport"] = transport_name
        metrics = InMemoryMetricsRegistry(default_labels=default_labels)

    if args.verbose:
        logger = ConsoleStructuredLogger("acp.cli", min_level=LogLevel.DEBUG)
    elif args.quiet:
        logger = ConsoleStructuredLogger("acp.cli", min_level=LogLevel.ERROR)
    else:
        logger = ConsoleStructuredLogger("acp.cli", min_level=LogLevel.INFO)

    return tracer, metrics, logger


def _build_runtime(
    args: argparse.Namespace,
    tracer: Any,
    metrics: Any,
    logger: Any,
    transport_name: str = "unknown",
) -> tuple[AcpRuntime, HealthHandler | None]:
    """Build an AcpRuntime from CLI args / env.

    Returns the runtime and the optional ``HealthHandler`` so callers
    can start the HTTP probe server.
    """
    handler_module = args.handlers or os.environ.get("ACP_HANDLERS")
    if handler_module is None:
        raise SystemExit("No handlers specified. Use --handlers or set ACP_HANDLERS.")

    handlers = _load_handlers(handler_module)
    if not handlers:
        raise SystemExit(f"Module {handler_module!r} contains no @capability classes.")

    # Auto-register built-in health handler unless opted out
    health_handler: HealthHandler | None = None
    if not getattr(args, "no_health", False):
        health_handler = HealthHandler(
            transport_name=transport_name,
            metrics=metrics,
            user_handler_count=len(handlers),
        )
        handlers.insert(0, health_handler)

    runtime = AcpRuntime(
        handlers,
        tracer=tracer,
        metrics=metrics,
        logger=logger,
    )

    # Two-phase init: give the health handler a reference to the runtime
    # so it can inspect the registry for readiness checks.
    if health_handler is not None:
        health_handler.set_runtime(runtime)

    return runtime, health_handler


def _build_router(args: argparse.Namespace, runtime: AcpRuntime, tracer: Any, metrics: Any, logger: Any) -> Router:
    """Build a Router from CLI args / env."""
    scopes = _split_scopes(args.scopes) or _split_scopes(os.environ.get("ACP_SCOPES"))

    # Optional auth
    auth_validator = None
    secret = args.auth_secret or os.environ.get("ACP_AUTH_SECRET")
    if secret:
        ttl = args.auth_ttl if args.auth_ttl is not None else env_int("ACP_AUTH_TTL", 3600)
        config = AuthConfig(secret_key=secret, token_ttl_seconds=ttl)
        auth_validator = HmacTokenValidator(config).validate

    # Optional audit
    audit_logger = None
    audit_path = args.audit_log or os.environ.get("ACP_AUDIT_LOG")
    if audit_path:
        audit_logger = NDJSONAuditLogger(audit_path)

    require_auth = args.require_auth if args.require_auth is not None else env_bool("ACP_REQUIRE_AUTH", False)

    return Router(
        runtime,
        RouterConfig(
            caller_scopes=scopes,
            auth_validator=auth_validator,
            audit_logger=audit_logger,
            require_auth_for_public=require_auth,
            tracer=tracer,
            metrics=metrics,
            logger=logger,
        ),
    )


# ------------------------------------------------------------------ stdio

async def _run_stdio(args: argparse.Namespace, tracer: Any, metrics: Any, logger: Any) -> None:
    runtime, health_handler = _build_runtime(args, tracer, metrics, logger, transport_name="stdio")
    router = _build_router(args, runtime, tracer, metrics, logger)
    transport = StdioTransport()
    server = Server(router, transport)
    if logger is not None:
        logger.info("ACP stdio server started")
    http_port = getattr(args, "http_port", None)
    metrics_path = getattr(args, "metrics_path", "/metrics")
    if http_port is not None and health_handler is not None:
        async with anyio.create_task_group() as tg:
            tg.start_soon(start_http_server, health_handler, http_port, metrics_path)
            tg.start_soon(server.run)
    else:
        await server.run()


# ------------------------------------------------------------------ uds

async def _run_uds(args: argparse.Namespace, tracer: Any, metrics: Any, logger: Any) -> None:
    runtime, health_handler = _build_runtime(args, tracer, metrics, logger, transport_name="uds")
    router = _build_router(args, runtime, tracer, metrics, logger)
    path = args.path or os.environ.get("ACP_UDS_PATH", "/tmp/acp.sock")
    listener = UDSListener(path)
    if logger is not None:
        logger.info("ACP UDS server started", path=path)
    http_port = getattr(args, "http_port", None)
    metrics_path = getattr(args, "metrics_path", "/metrics")
    try:
        if http_port is not None and health_handler is not None:
            async with anyio.create_task_group() as tg:
                tg.start_soon(start_http_server, health_handler, http_port, metrics_path)
                tg.start_soon(listener.serve, router)
        else:
            await listener.serve(router)
    except OSError as e:
        raise SystemExit(f"Cannot start UDS listener on {path!r}: {e}") from e


# ------------------------------------------------------------------ websocket

async def _run_websocket(args: argparse.Namespace, tracer: Any, metrics: Any, logger: Any) -> None:
    runtime, health_handler = _build_runtime(args, tracer, metrics, logger, transport_name="websocket")
    router = _build_router(args, runtime, tracer, metrics, logger)
    host = args.host or os.environ.get("ACP_WS_HOST", "localhost")
    port = args.port if args.port is not None else env_int("ACP_WS_PORT", 8765)
    listener = WebSocketListener(host, port)
    if logger is not None:
        logger.info("ACP WebSocket server started", host=host, port=port)
    http_port = getattr(args, "http_port", None)
    metrics_path = getattr(args, "metrics_path", "/metrics")
    try:
        if http_port is not None and health_handler is not None:
            async with anyio.create_task_group() as tg:
                tg.start_soon(start_http_server, health_handler, http_port, metrics_path)
                tg.start_soon(listener.serve, router)
        else:
            await listener.serve(router)
    except ImportError as e:
        raise SystemExit(
            f"Cannot start WebSocket listener: {e}. Install the optional dependency: pip install acp-runtime[websocket]"
        ) from e


# ------------------------------------------------------------------ argparse

def _build_parser() -> argparse.ArgumentParser:
    # Common arguments shared by all subcommands
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--version",
        action="version",
        version=f"acp {__version__}",
    )
    common.add_argument(
        "--config",
        help="Path to a YAML or JSON config file (settings overridden by CLI flags)",
    )
    common.add_argument(
        "--handlers",
        help="Python module path that contains @capability handler classes",
    )
    common.add_argument(
        "--scopes",
        help="Comma-separated caller scopes (e.g. 'math.read,math.write')",
    )
    common.add_argument(
        "--auth-secret",
        help="HMAC secret for bearer-token authentication",
    )
    common.add_argument(
        "--auth-ttl",
        type=int,
        help="Token TTL in seconds (default 3600)",
    )
    common.add_argument(
        "--require-auth",
        action="store_true",
        help="Require authentication even for public capabilities",
    )
    common.add_argument(
        "--audit-log",
        help="Path to NDJSON audit log file",
    )
    common.add_argument(
        "--trace-file",
        help="Path to JSON trace output file",
    )
    common.add_argument(
        "--metrics",
        action="store_true",
        help="Enable metrics collection",
    )
    common.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    common.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error logging",
    )
    common.add_argument(
        "--no-health",
        action="store_true",
        help="Disable the built-in system.health / system.metrics capabilities",
    )
    common.add_argument(
        "--http-port",
        type=int,
        help="Start a lightweight HTTP health server on this port (for K8s probes)",
    )
    common.add_argument(
        "--metrics-path",
        default="/metrics",
        help="HTTP path for the metrics endpoint (default /metrics)",
    )
    common.add_argument(
        "--default-labels",
        help="Comma-separated key=value labels applied to all metrics (e.g. transport=stdio,env=prod)",
    )

    parser = argparse.ArgumentParser(
        prog="acp",
        description="Agent Communication Protocol — Unified CLI",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # stdio
    sub.add_parser("stdio", help="Run the stdio transport (LSP-style)", parents=[common])

    # uds
    uds_parser = sub.add_parser("uds", help="Run the Unix Domain Socket transport", parents=[common])
    uds_parser.add_argument(
        "--path",
        help="UDS socket path (default /tmp/acp.sock, or ACP_UDS_PATH env)",
    )

    # websocket
    ws_parser = sub.add_parser("websocket", help="Run the WebSocket transport", parents=[common])
    ws_parser.add_argument(
        "--host",
        help="WebSocket bind host (default localhost, or ACP_WS_HOST env)",
    )
    ws_parser.add_argument(
        "--port",
        type=int,
        help="WebSocket bind port (default 8765, or ACP_WS_PORT env)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Load and merge config file (lowest precedence after defaults)
    if args.config:
        config = load_config(args.config)
        args = merge_config(args, config)

    tracer, metrics, logger = _build_observability(args, transport_name=args.command)

    try:
        if args.command == "stdio":
            anyio.run(_run_stdio, args, tracer, metrics, logger)
        elif args.command == "uds":
            anyio.run(_run_uds, args, tracer, metrics, logger)
        elif args.command == "websocket":
            anyio.run(_run_websocket, args, tracer, metrics, logger)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        if logger is not None:
            logger.info("Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
