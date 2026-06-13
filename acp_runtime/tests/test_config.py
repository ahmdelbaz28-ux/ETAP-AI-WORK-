"""Tests for the configuration file loader.

Covers:
    * JSON config loading
    * YAML config loading
    * Missing file error
    * Unknown format error
    * Invalid YAML/JSON error
    * merge_config precedence: CLI > env > config > defaults
    * Config integration with CLI main()
"""
from __future__ import annotations
import json

import pytest

from acp.config import load_config, merge_config


# ------------------------------------------------------- helpers

class DummyArgs:
    """Simple argparse-like namespace for testing."""

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ------------------------------------------------------- load_config

class TestLoadConfig:
    def test_load_json(self, tmp_path):
        config = {"handlers": "myapp.handlers", "scopes": "math.read", "metrics": True}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        loaded = load_config(str(path))
        assert loaded == config

    def test_load_yaml(self, tmp_path):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        text = """handlers: myapp.handlers
scopes: math.read
metrics: true
"""
        path = tmp_path / "config.yaml"
        path.write_text(text)
        loaded = load_config(str(path))
        assert loaded == {"handlers": "myapp.handlers", "scopes": "math.read", "metrics": True}

    def test_load_yml_suffix(self, tmp_path):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        path = tmp_path / "config.yml"
        path.write_text("handlers: myapp.handlers\n")
        loaded = load_config(str(path))
        assert loaded["handlers"] == "myapp.handlers"

    def test_missing_file(self, tmp_path):
        path = tmp_path / "missing.json"
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(path))
        assert "not found" in str(exc_info.value)

    def test_unknown_format(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("[section]\nkey = value\n")
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(path))
        assert "Unsupported config file format" in str(exc_info.value)

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not json")
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(path))
        assert "Failed to parse" in str(exc_info.value)

    def test_invalid_yaml(self, tmp_path):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        path = tmp_path / "config.yaml"
        # This is actually valid YAML (just a string), but not a dict
        path.write_text("just a string\n")
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(path))
        assert "must contain a top-level mapping" in str(exc_info.value)

    def test_yaml_not_installed(self, tmp_path, monkeypatch):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed — can't test without it")
        # Make import yaml fail
        monkeypatch.setitem(__import__("sys").modules, "yaml", None)
        path = tmp_path / "config.yaml"
        path.write_text("handlers: myapp.handlers\n")
        with pytest.raises(SystemExit) as exc_info:
            load_config(str(path))
        assert "PyYAML" in str(exc_info.value)


# ------------------------------------------------------- merge_config

class TestMergeConfig:
    def test_cli_takes_precedence(self):
        """Explicit CLI values are never overwritten."""
        args = DummyArgs(
            handlers="cli.handlers",
            scopes="cli.scope",
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        config = {"handlers": "config.handlers", "scopes": "config.scope"}
        merge_config(args, config)
        assert args.handlers == "cli.handlers"
        assert args.scopes == "cli.scope"

    def test_config_fills_missing(self):
        """Config values are used when CLI didn't provide them."""
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        config = {
            "handlers": "config.handlers",
            "scopes": "config.scope",
            "metrics": True,
        }
        merge_config(args, config)
        assert args.handlers == "config.handlers"
        assert args.scopes == "config.scope"
        assert args.metrics is True

    def test_env_takes_precedence_over_config(self, monkeypatch):
        """Env vars override config but not CLI."""
        monkeypatch.setenv("ACP_HANDLERS", "env.handlers")
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        config = {"handlers": "config.handlers"}
        merge_config(args, config)
        assert args.handlers == "env.handlers"

    def test_env_int_conversion(self, monkeypatch):
        monkeypatch.setenv("ACP_AUTH_TTL", "7200")
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        merge_config(args, {})
        assert args.auth_ttl == 7200

    def test_env_bool_conversion(self, monkeypatch):
        monkeypatch.setenv("ACP_METRICS", "true")
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        merge_config(args, {})
        assert args.metrics is True

    def test_env_int_bad_value(self, monkeypatch):
        monkeypatch.setenv("ACP_AUTH_TTL", "not-a-number")
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        with pytest.raises(SystemExit):
            merge_config(args, {})

    def test_config_none(self):
        """merge_config with None config is a no-op."""
        args = DummyArgs(
            handlers=None,
            scopes=None,
            auth_secret=None,
            auth_ttl=None,
            require_auth=False,
            audit_log=None,
            trace_file=None,
            metrics=False,
            verbose=False,
            quiet=False,
            path=None,
            host=None,
            port=None,
        )
        merge_config(args, None)
        assert args.handlers is None


# ------------------------------------------------------- CLI integration

class TestConfigCliIntegration:
    def test_cli_with_json_config(self, monkeypatch, tmp_path):
        config = {
            "handlers": "tests.test_cli",
            "scopes": "math.read",
            "metrics": True,
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        monkeypatch.setenv("ACP_HANDLERS", "")  # clear env
        monkeypatch.delenv("ACP_HANDLERS", raising=False)

        from acp.cli import _build_parser, _build_observability, _build_runtime
        from acp.config import load_config, merge_config

        parser = _build_parser()
        args = parser.parse_args(["stdio", "--config", str(config_path)])
        config = load_config(args.config)
        args = merge_config(args, config)
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        assert "math.sum" in runtime.capability_names
        assert metrics is not None

    def test_cli_flag_overrides_config(self, monkeypatch, tmp_path):
        config = {"handlers": "tests.test_cli", "scopes": "math.read"}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        monkeypatch.delenv("ACP_HANDLERS", raising=False)
        monkeypatch.delenv("ACP_SCOPES", raising=False)

        from acp.cli import _build_parser, _build_router, _build_runtime, _build_observability
        from acp.config import load_config, merge_config

        parser = _build_parser()
        args = parser.parse_args(["stdio", "--config", str(config_path), "--scopes", "math.write"])
        config = load_config(args.config)
        args = merge_config(args, config)
        tracer, metrics, logger = _build_observability(args)
        runtime, _ = _build_runtime(args, tracer, metrics, logger)
        router = _build_router(args, runtime, tracer, metrics, logger)
        # CLI --scopes math.write overrides config scopes math.read
        assert router._config.caller_scopes == {"math.write"}

    def test_main_with_config(self, monkeypatch, tmp_path):
        """Test main() entrypoint with --config via mocked _run_stdio."""
        config = {"handlers": "tests.test_cli", "scopes": "math.read"}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        monkeypatch.delenv("ACP_HANDLERS", raising=False)
        monkeypatch.delenv("ACP_SCOPES", raising=False)

        from acp.cli import main
        from unittest.mock import patch

        async def _noop_run_stdio(args, tracer, metrics, logger):
            assert args.handlers == "tests.test_cli"
            assert args.scopes == "math.read"
            return

        with patch("acp.cli._run_stdio", _noop_run_stdio):
            main(["stdio", "--config", str(config_path)])
