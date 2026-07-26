"""
integrations/_observability_base.py — Shared helpers for observability integration modules.

Extracted from integrations/langfuse_integration.py and integrations/langwatch_integration.py
to eliminate code duplication (both modules had near-identical _NoOpContext class).

This module provides:
  - NoOpContext — silent context manager used when the observability SDK is disabled
  - NoOpSpan — silent span used when SDK is disabled
  - Common health_check pattern for observability trackers

Both LangfuseTracker and LangWatchTracker can import from this shared base,
keeping their public API identical while removing duplicated utility classes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
        # NOSONAR — S1186: intentional no-op (protocol stub / test fixture)

    def send(self, *args: Any, **kwargs: Any) -> None:
        """No-op send call."""
        # NOSONAR — S1186: intentional no-op (protocol stub / test fixture)

    def record_exception(self, exc: Any) -> None:
        """No-op exception recording."""
        # NOSONAR — S1186: intentional no-op (protocol stub / test fixture)


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
