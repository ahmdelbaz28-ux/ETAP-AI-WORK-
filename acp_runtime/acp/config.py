"""ACP configuration file loader.

Supports both YAML and JSON.  Config keys are the same as the CLI flag
names (without leading dashes) so the mapping is trivial.

Precedence (highest → lowest):
    1. CLI arguments
    2. Environment variables
    3. Config file
    4. Built-in defaults
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

__all__ = ["load_config", "merge_config", "env_int", "env_bool"]


def env_int(key: str, default: int) -> int:
    """Read an integer from an environment variable, or return the default."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError as err:
        raise SystemExit(f"{key} must be an integer, got: {val!r}") from err


def env_bool(key: str, default: bool) -> bool:
    """Read a boolean from an environment variable, or return the default."""
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def load_config(path: str) -> dict[str, Any]:
    """Load a YAML or JSON config file.

    Args:
        path: filesystem path to the config file.

    Returns:
        A dict of configuration values.

    Raises:
        SystemExit: if the file is missing, the format is unknown, or
        parsing fails.
    """
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Config file not found: {path!r}")

    data = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()

    try:
        if suffix in (".yaml", ".yml"):
            return _load_yaml(data)
        if suffix == ".json":
            return json.loads(data)
    except Exception as exc:
        raise SystemExit(f"Failed to parse config file {path!r}: {exc}") from exc

    raise SystemExit(
        f"Unsupported config file format: {suffix!r}. "
        "Use .yaml, .yml, or .json."
    )


def _load_yaml(text: str) -> dict[str, Any]:
    """Import PyYAML lazily and parse the text."""
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "YAML config files require PyYAML. "
            "Install it:  pip install pyyaml"
        ) from exc
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise SystemExit("YAML config file must contain a top-level mapping.")
    return parsed


def merge_config(
    args: Any,
    config: dict[str, Any] | None,
    env_prefix: str = "ACP_",
) -> Any:
    """Merge config-file and env values into the argparse namespace.

    Precedence: CLI args > env vars > config file > defaults.
    Only missing / default values are overwritten.

    Args:
        args: the argparse namespace produced by ``parse_args``.
        config: dict loaded from ``load_config``, or ``None``.
        env_prefix: prefix for environment variables (default ``ACP_``).

    Returns:
        The same namespace, possibly mutated.
    """
    if config is None:
        config = {}

    # Mapping: CLI dest name -> (env var name, type conversion)
    mapping: dict[str, tuple[str, Any]] = {
        "handlers": (f"{env_prefix}HANDLERS", None),
        "scopes": (f"{env_prefix}SCOPES", None),
        "auth_secret": (f"{env_prefix}AUTH_SECRET", None),
        "auth_ttl": (f"{env_prefix}AUTH_TTL", int),
        "require_auth": (f"{env_prefix}REQUIRE_AUTH", bool),
        "audit_log": (f"{env_prefix}AUDIT_LOG", None),
        "trace_file": (f"{env_prefix}TRACE_FILE", None),
        "metrics": (f"{env_prefix}METRICS", bool),
        "verbose": (f"{env_prefix}VERBOSE", bool),
        "quiet": (f"{env_prefix}QUIET", bool),
        "path": (f"{env_prefix}UDS_PATH", None),
        "host": (f"{env_prefix}WS_HOST", None),
        "port": (f"{env_prefix}WS_PORT", int),
    }

    for dest, (env_key, convert) in mapping.items():
        # Skip if the CLI already provided a value (not the default)
        if hasattr(args, dest) and _is_set(args, dest):
            continue

        # Try env var next
        if convert is bool:
            env_val = env_bool(env_key, False)
            if env_val is not False:
                setattr(args, dest, env_val)
                continue
        elif convert is int:
            env_val = env_int(env_key, 0)
            if env_val != 0:
                setattr(args, dest, env_val)
                continue
        else:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                setattr(args, dest, env_val)
                continue

        # Fall back to config file
        if dest in config:
            setattr(args, dest, config[dest])

    return args


def _is_set(args: Any, dest: str) -> bool:
    """Return True if the user explicitly set the value on the CLI."""
    val = getattr(args, dest, None)
    # For store_true flags, argparse sets them to False by default.
    # A value of True means the flag was present on the CLI.
    if isinstance(val, bool):
        return val is True
    # For strings / ints, ``None`` is the argparse default.
    return val is not None
