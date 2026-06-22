"""Tests for the unified CLI entrypoint.

Covers:
    * Argument parsing for stdio, uds, and websocket subcommands
    * Handler loading from a module path
    * Router + Runtime construction from CLI args
    * Environment variable fallback
    * Stdio transport start (with mocked stdin/stdout)
    * Error handling: missing handlers, bad module, no capability classes
    * Auth, audit, observability wiring from CLI flags
"""

from __future__ import annotations

import io
from unittest.mock import patch

import anyio
import pytest
from acp.cli import (
    _build_observability,
    _build_parser,
    _build_router,
    _build_runtime,
    _load_handlers,
    _split_scopes,
    main,
)
from acp.config import env_bool as _env_bool
from acp.config import env_int as _env_int
from acp.runtime import capability

# ------------------------------------------------------- test handlers module


class FakeHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        return a + b


# ------------------------------------------------------- unit helpers


class TestSplitScopes:
    def test_empty(self):
        assert _split_scopes(None) == set()
        assert _split_scopes("") == set()
        assert _split_scopes("  ") == set()

    def test_single(self):
        assert _split_scopes("math.read") == {"math.read"}

    def test_multiple(self):
        assert _split_scopes("math.read,math.write") == {"math.read", "math.write"}

    def test_whitespace(self):
        assert _split_scopes(" a , b ") == {"a", "b"}


class TestEnvInt:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("ACP_TEST_INT", raising=False)
        assert _env_int("ACP_TEST_INT", 42) == 42

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("ACP_TEST_INT", "99")
        assert _env_int("ACP_TEST_INT", 42) == 99

    def test_bad_value(self, monkeypatch):
        monkeypatch.setenv("ACP_TEST_INT", "not-a-number")
        with pytest.raises(SystemExit):
            _env_int("ACP_TEST_INT", 42)


class TestEnvBool:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("ACP_TEST_BOOL", raising=False)
        assert _env_bool("ACP_TEST_BOOL", True) is True
        assert _env_bool("ACP_TEST_BOOL", False) is False

    def test_true_values(self, monkeypatch):
        for val in ("1", "true", "True", "yes", "on"):
            monkeypatch.setenv("ACP_TEST_BOOL", val)
            assert _env_bool("ACP_TEST_BOOL", False) is True

    def test_false_values(self, monkeypatch):
        for val in ("0", "false", "False", "no", "off", "random"):
            monkeypatch.setenv("ACP_TEST_BOOL", val)
            assert _env_bool("ACP_TEST_BOOL", True) is False


# ------------------------------------------------------- argparse


class TestParser:
    def test_stdio_subcommand(self):
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "myapp.handlers"])
        assert args.command == "stdio"
        assert args.handlers == "myapp.handlers"

    def test_uds_subcommand(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["uds", "--handlers", "myapp.handlers", "--path", "/tmp/test.sock"]
        )
        assert args.command == "uds"
        assert args.path == "/tmp/test.sock"

    def test_websocket_subcommand(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["websocket", "--handlers", "myapp.handlers", "--host", "0.0.0.0", "--port", "9999"]
        )
        assert args.command == "websocket"
        assert args.host == "0.0.0.0"
        assert args.port == 9999

    def test_common_flags(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "stdio",
                "--handlers",
                "myapp.handlers",
                "--scopes",
                "math.read,math.write",
                "--auth-secret",
                "secret123",
                "--auth-ttl",
                "7200",
                "--require-auth",
                "--audit-log",
                "/tmp/audit.ndjson",
                "--trace-file",
                "/tmp/trace.json",
                "--metrics",
                "--verbose",
            ]
        )
        assert args.scopes == "math.read,math.write"
        assert args.auth_secret == "secret123"
        assert args.auth_ttl == 7200
        assert args.require_auth is True
        assert args.audit_log == "/tmp/audit.ndjson"
        assert args.trace_file == "/tmp/trace.json"
        assert args.metrics is True
        assert args.verbose is True

    def test_no_command_fails(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ------------------------------------------------------- handler loading


class TestLoadHandlers:
    def test_load_this_module(self):
        # Load the test module itself
        handlers = _load_handlers("tests.test_cli")
        assert len(handlers) >= 1
        assert any(isinstance(h, FakeHandler) for h in handlers)

    def test_bad_module(self):
        with pytest.raises(SystemExit):
            _load_handlers("nonexistent.module.xyz")

    def test_handler_with_required_args(self):
        # _cli_bad_handler.BadHandler requires a constructor argument
        with pytest.raises(SystemExit) as exc_info:
            _load_handlers("tests._cli_bad_handler")
        assert "BadHandler" in str(exc_info.value)

    def test_no_capabilities(self):
        handlers = _load_handlers("json")  # stdlib module with no @capability classes
        assert handlers == []


# ------------------------------------------------------- runtime / router construction


class TestBuildRuntime:
    def test_build_runtime(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(["stdio"])
        tracer, metrics, logger = _build_observability(args)
        runtime, health_handler = _build_runtime(args, tracer, metrics, logger)
        assert "math.sum" in runtime.capability_names
        assert health_handler is not None

    def test_trace_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        trace_file = tmp_path / "trace.ndjson"
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--trace-file", str(trace_file)])
        tracer, metrics, logger = _build_observability(args)
        runtime, health_handler = _build_runtime(args, tracer, metrics, logger)
        assert runtime._tracer is not None
        assert health_handler is not None

    def test_metrics(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--metrics"])
        tracer, metrics, logger = _build_observability(args)
        runtime, health_handler = _build_runtime(args, tracer, metrics, logger)
        assert runtime._metrics is not None
        assert health_handler is not None


class TestBuildRouter:
    def test_build_router_basic(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(["stdio"])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        assert router._config.caller_scopes == set()

    def test_build_router_with_scopes(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--scopes", "math.read"])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        assert router._config.caller_scopes == {"math.read"}

    def test_build_router_with_auth(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--auth-secret", "secret123"])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        assert router._config.auth_validator is not None

    def test_build_router_with_audit(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        audit_path = tmp_path / "audit.ndjson"
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--audit-log", str(audit_path)])
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        assert router._config.audit_logger is not None


# ------------------------------------------------------- stdio transport integration


@pytest.mark.anyio
async def test_stdio_transport_start():
    stdin = io.StringIO(
        '{"jsonrpc":"2.0","id":"r1","method":"math.sum","params":{"a":1,"b":2},"capability":"math.sum"}\n'
    )
    stdout = io.StringIO()
    parser = _build_parser()
    args = parser.parse_args(["stdio", "--handlers", "tests.test_cli", "--scopes", "math.read"])
    tracer, metrics, logger = _build_observability(args)
    runtime, _ = _build_runtime(args, tracer, metrics, logger)
    router = _build_router(args, runtime, tracer, metrics, logger)
    from acp.transport import Server, StdioTransport

    transport = StdioTransport(stdin, stdout)
    Server(router, transport)
    # Don't run forever — just process one message
    raw = await transport.read_message()
    assert raw is not None
    envelope = __import__("json").loads(raw)
    resp = await router.handle(envelope)
    assert resp["result"] == 3


# ------------------------------------------------------- env var fallback


class TestEnvVarFallback:
    def test_handlers_from_env(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        monkeypatch.setenv("ACP_SCOPES", "math.read,math.write")
        monkeypatch.setenv("ACP_AUTH_SECRET", "env-secret")
        monkeypatch.setenv("ACP_AUTH_TTL", "1800")
        monkeypatch.setenv("ACP_REQUIRE_AUTH", "true")
        parser = _build_parser()
        args = parser.parse_args(["stdio"])
        from acp.config import merge_config

        args = merge_config(args, {})
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        assert router._config.caller_scopes == {"math.read", "math.write"}
        assert router._config.auth_validator is not None
        assert router._config.require_auth_for_public is True


# ------------------------------------------------------- error cases


class TestCliErrors:
    def test_missing_handlers(self, monkeypatch):
        monkeypatch.delenv("ACP_HANDLERS", raising=False)
        parser = _build_parser()
        args = parser.parse_args(["stdio"])
        tracer, metrics, logger = _build_observability(args)
        with pytest.raises(SystemExit):
            _build_runtime(args, tracer, metrics, logger)

    def test_main_bad_command(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["stdio"])  # no handlers, no env
        assert exc_info.value.code != 0

    def test_version_flag(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0


class TestUdsArgs:
    def test_uds_args(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["uds", "--handlers", "tests.test_cli", "--path", "/tmp/test.sock"]
        )
        assert args.command == "uds"
        assert args.path == "/tmp/test.sock"


class TestWebSocketArgs:
    def test_websocket_args(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["websocket", "--handlers", "tests.test_cli", "--host", "0.0.0.0", "--port", "9999"]
        )
        assert args.command == "websocket"
        assert args.host == "0.0.0.0"
        assert args.port == 9999


class TestHttpPortFlag:
    def test_http_port_parsed(self):
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "tests.test_cli", "--http-port", "8080"])
        assert args.http_port == 8080

    def test_http_port_with_uds(self):
        parser = _build_parser()
        args = parser.parse_args(["uds", "--handlers", "tests.test_cli", "--http-port", "8081"])
        assert args.http_port == 8081

    def test_http_port_with_websocket(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["websocket", "--handlers", "tests.test_cli", "--http-port", "8082"]
        )
        assert args.http_port == 8082


class TestMetricsPathFlag:
    def test_default_metrics_path(self):
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "tests.test_cli"])
        assert args.metrics_path == "/metrics"

    def test_custom_metrics_path(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["stdio", "--handlers", "tests.test_cli", "--metrics-path", "/custom-metrics"]
        )
        assert args.metrics_path == "/custom-metrics"

    def test_custom_metrics_path_with_uds(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["uds", "--handlers", "tests.test_cli", "--metrics-path", "/probe/metrics"]
        )
        assert args.metrics_path == "/probe/metrics"

    def test_custom_metrics_path_with_websocket(self):
        parser = _build_parser()
        args = parser.parse_args(
            ["websocket", "--handlers", "tests.test_cli", "--metrics-path", "/app/prometheus"]
        )
        assert args.metrics_path == "/app/prometheus"


class TestDefaultLabelsFlag:
    def test_default_labels_parsed(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "stdio",
                "--handlers",
                "tests.test_cli",
                "--default-labels",
                "transport=stdio,env=prod",
            ]
        )
        assert args.default_labels == "transport=stdio,env=prod"

    def test_default_labels_empty(self):
        parser = _build_parser()
        args = parser.parse_args(["stdio", "--handlers", "tests.test_cli"])
        assert args.default_labels is None

    def test_parse_labels_helper(self):
        from acp.cli import _parse_labels

        assert _parse_labels("transport=stdio") == {"transport": "stdio"}
        assert _parse_labels("transport=stdio,env=prod") == {"transport": "stdio", "env": "prod"}
        assert _parse_labels("") == {}
        assert _parse_labels(None) == {}

    def test_parse_labels_invalid(self):
        from acp.cli import _parse_labels

        with pytest.raises(SystemExit):
            _parse_labels("bad_format")


# ------------------------------------------------------- transport error paths


class TestTransportErrorPaths:
    def test_uds_serve_oserror(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(
            ["uds", "--handlers", "tests.test_cli", "--path", "/tmp/test.sock"]
        )
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        _build_router(args, runtime, tracer, metrics, logger)
        from acp.transport import UDSListener

        async def _broken_serve(self, router):
            raise OSError("Address already in use")

        with patch.object(UDSListener, "serve", _broken_serve):
            from acp.cli import _run_uds

            with pytest.raises(SystemExit) as exc_info:
                anyio.run(_run_uds, args, tracer, metrics, logger)
        assert "Cannot start UDS listener" in str(exc_info.value)

    def test_websocket_serve_import_error(self, monkeypatch):
        monkeypatch.setenv("ACP_HANDLERS", "tests.test_cli")
        parser = _build_parser()
        args = parser.parse_args(
            ["websocket", "--handlers", "tests.test_cli", "--host", "localhost", "--port", "8765"]
        )
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        _build_router(args, runtime, tracer, metrics, logger)
        from acp.transport import WebSocketListener

        async def _broken_serve(self, router):
            raise ImportError("No module named 'websockets'")

        with patch.object(WebSocketListener, "serve", _broken_serve):
            from acp.cli import _run_websocket

            with pytest.raises(SystemExit) as exc_info:
                anyio.run(_run_websocket, args, tracer, metrics, logger)
        assert "Cannot start WebSocket listener" in str(exc_info.value)
