"""
integrations/_observability_base.py — Shared helpers for observability integration modules.

Extracted from integrations/langfuse_integration.py and integrations/langwatch_integration.py
to eliminate code duplication (both modules had near-identical _NoOpContext class).

This module provides:
  - NoOpContext — silent context manager used when the observability SDK is disabled
  - build_health_check — standardized health_check dict builder
  - env_truthy — read a boolean from an env var (LOCAL COPY; see note below)

Both LangfuseTracker and LangWatchTracker can import from this shared base,
keeping their public API identical while removing duplicated utility classes.

NOTE on ``env_truthy``:
----------------------
The canonical implementation lives in ``core.utils.env_truthy``. However,
importing ``core.utils`` triggers ``core/__init__.py`` which side-effect-imports
``core.tracing`` (which requires ``opentelemetry.sdk``). This makes every
observability integration fail to import in minimal environments (CI, tests,
local dev) where ``opentelemetry`` is not yet installed.

The root-cause fix is to keep a self-contained copy of ``env_truthy`` here
in the observability base — a 4-line function with no dependencies beyond
``os``. This decouples the integrations layer from the application core's
import-time side effects, while preserving identical behavior.

If ``core.utils.env_truthy`` ever changes, mirror the change here too.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── env_truthy (local self-contained copy — see module docstring) ─────────


def env_truthy(var: str, default: bool = False) -> bool:
    """Read a boolean from an environment variable, or return the default.

    Returns True if the env var value (lowercased) is one of:
    ``"1"``, ``"true"``, ``"yes"``, ``"on"``.
    Returns False if the value is any other non-empty string.
    Returns ``default`` if the variable is not set (None).

    Parameters
    ----------
    var : str
        Environment variable name to read.
    default : bool
        Value to return when the variable is not set.

    Examples
    --------
    >>> env_truthy("LANGFUSE_ENABLED", default=True)   # var not set → True
    >>> env_truthy("DEBUG_MODE", default=False)         # var="1" → True
    >>> env_truthy("VERBOSE", default=False)            # var="no" → False
    """
    val = os.environ.get(var)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class NoOpContext:
    """Silent no-op context manager used when an observability SDK is disabled.

    Provides stub methods matching the Langfuse/LangWatch trace/span API
    so callers can use the same interface regardless of whether the SDK
    is available. All methods return self or None, allowing chaining patterns
    like ``trace.update(...).end()`` to work silently.
    """

    def __enter__(self) -> NoOpContext:
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def update(self, *args: Any, **kwargs: Any) -> NoOpContext:
        """No-op update — returns self for chaining compatibility."""
        return self

    def end(self, *args: Any, **kwargs: Any) -> None:
        """No-op end call."""
        # NOSONAR intentional no-op (protocol stub / test fixture)

    def send(self, *args: Any, **kwargs: Any) -> None:
        """No-op send call."""
        # NOSONAR intentional no-op (protocol stub / test fixture)

    def record_exception(self, exc: Any) -> None:
        """No-op exception recording."""
        # NOSONAR intentional no-op (protocol stub / test fixture)


def build_health_check(
    enabled: bool,
    provider_name: str,
    project: str,
    sdk_available: bool,
    dashboard_url: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a standardized health_check response for observability trackers.

    Args:
        enabled: Whether the tracker is currently active.
        provider_name: Name of the observability provider (e.g., "Langfuse", "LangWatch").
        project: Project name configured for the provider.
        sdk_available: Whether the SDK is installed.
        dashboard_url: URL to the provider's dashboard (None if disabled).
        **extra: Additional fields to include in the health check dict.

    Returns:
        Dict with standard observability health check fields.
    """
    result: dict[str, Any] = {
        "enabled": enabled,
        "provider": provider_name,
        "project": project,
        "sdk_available": sdk_available,
        "dashboard": dashboard_url if enabled else None,
    }
    result.update(extra)
    return result
