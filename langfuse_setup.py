"""
langfuse_setup.py — Langfuse Observability Integration for AhmedETAP.

Provides fail-safe callback handlers, score logging, health checks, and flushing.
All public operations are non-blocking and fail-safe.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_langfuse_available: bool | None = None
_langfuse_client: Any = None


def _check_langfuse_available() -> bool:
    """Return True if Langfuse is importable and configured with host and keys."""
    global _langfuse_available
    if _langfuse_available is not None:
        return _langfuse_available

    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not (host and public_key and secret_key):
        _langfuse_available = False
        return False

    try:
        import langfuse  # noqa: F401

        _langfuse_available = True
    except Exception:
        _langfuse_available = False

    return _langfuse_available


def get_langfuse() -> Any | None:
    """Return Langfuse client instance or None if not configured/available."""
    global _langfuse_client
    if not _check_langfuse_available():
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL"),
        )
        return _langfuse_client
    except Exception as e:
        logger.debug("Failed to initialize Langfuse client: %s", e)
        return None


def get_langfuse_callback_handler(trace_id: str | None = None, **kwargs: Any) -> Any | None:
    """Return Langfuse callback handler for LangChain or None if unavailable."""
    if not _check_langfuse_available():
        return None

    try:
        from langfuse.callback import CallbackHandler

        return CallbackHandler(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL"),
            trace_id=trace_id,
            **kwargs,
        )
    except Exception as e:
        logger.debug("Failed to initialize Langfuse callback handler: %s", e)
        return None


def log_verification_score(
    handler: Any = None,
    name: str = "verification_score",
    value: float | None = 1.0,
    comment: str | None = None,
) -> None:
    """Fail-safe logging of verification scores to Langfuse."""
    try:
        if handler is None or not name:
            return
        if hasattr(handler, "score"):
            handler.score(name=name, value=value, comment=comment)
    except Exception as e:
        logger.debug("log_verification_score failed silently: %s", e)


def log_workflow_scores(result: Any = None, handler: Any = None) -> None:
    """Fail-safe logging of all workflow scores."""
    try:
        if result is None or handler is None:
            return
        scores = getattr(result, "scores", None)
        if isinstance(scores, dict):
            for k, v in scores.items():
                log_verification_score(handler, name=str(k), value=v)
    except Exception as e:
        logger.debug("log_workflow_scores failed silently: %s", e)


def flush_langfuse() -> None:
    """Flush pending Langfuse observations fail-safely."""
    global _langfuse_client
    try:
        if _langfuse_client is not None and hasattr(_langfuse_client, "flush"):
            _langfuse_client.flush()
    except Exception as e:
        logger.debug("flush_langfuse failed silently: %s", e)


def langfuse_health_check() -> dict[str, Any]:
    """Return health check status dict for Langfuse."""
    available = _check_langfuse_available()
    if available:
        return {"enabled": True, "status": "healthy"}
    return {
        "enabled": False,
        "error": "Langfuse unconfigured or dependencies missing (LANGFUSE_HOST/KEYS unset)",
    }
