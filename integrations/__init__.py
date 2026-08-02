"""Integrations package for AhmedETAP external service connections.

Aggregates all external integrations (Langfuse, LangWatch, Smithery, Supabase)
into a single import surface, plus provides:

- ``health_check_all()`` — aggregated health of all integrations
- ``flush_all()`` / ``aclose_all()`` — graceful shutdown helpers
- ``__version__`` — package version (mirrors pyproject.toml)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

__version__ = "2.1.0"

# Supabase (managed Postgres + Storage + optional Auth)
# Primary observability — Langfuse (unlimited prompts on free Hobby plan)
from integrations.langfuse_evals import (
    ci_gate_block_unsafe_prompts,
    ensure_safety_dataset,
    eval_helpfulness,
    eval_safety,
    eval_standards_compliance,
    run_safety_eval,
    score_trace,
    seed_safety_datasets,
)
from integrations.langfuse_integration import (
    LangfuseTracker,
    get_prompt_from_langfuse,
    langfuse_tracker,
    track_llm_call,
)
from integrations.langfuse_llm import (
    SafetyValidationError,
    anthropic,
    estimate_cost_usd,
    openai,
    safe_anthropic_message,
    safe_openai_chat,
)
from integrations.langfuse_llm import (
    health_check as llm_health_check,
)
from integrations.langfuse_middleware import (
    LangfuseMiddleware,
    install_langfuse_middleware,
)
from integrations.langfuse_sessions import (
    EngineeringSession,
    add_trace_comment,
    alert_on_unsafe_trace,
    end_engineering_session,
    get_trace_share_url,
    record_user_feedback,
    start_engineering_session,
)

# Legacy fallback — LangWatch (free plan capped at 3 prompts)
from integrations.langwatch_integration import (
    langwatch_tracker,
)
from integrations.langwatch_integration import (
    track_llm_call as track_llm_call_langwatch,
)

# Smithery MCP
from integrations.smithery_mcp import mcp_registry, smithery_client
from integrations.supabase_auth import (
    SupabaseAuthError,
    link_or_create_local_user,
    send_magic_link,
    verify_supabase_token,
)
from integrations.supabase_auth import (
    get_oauth_url as supabase_get_oauth_url,
)
from integrations.supabase_auth import (
    health_check as supabase_auth_health_check,
)
from integrations.supabase_integration import (
    PRIVATE_BUCKET_REPORTS,
    PRIVATE_BUCKET_SCREENSHOTS,
    PRIVATE_BUCKET_UPLOADS,
    PUBLIC_BUCKET_MANUALS,
    SupabaseUploadError,
    delete_file,
    ensure_buckets_exist,
    get_public_url,
    get_signed_url,
    list_files,
    upload_bytes,
    upload_file,
)
from integrations.supabase_integration import (
    health_check as supabase_health_check,
)

__all__ = [
    # Langfuse core (integration.py)
    "LangfuseTracker",
    "langfuse_tracker",
    "track_llm_call",
    "get_prompt_from_langfuse",
    # Langfuse LLM wrappers (langfuse_llm.py)
    "openai",
    "anthropic",
    "safe_openai_chat",
    "safe_anthropic_message",
    "estimate_cost_usd",
    "llm_health_check",
    "SafetyValidationError",
    # Langfuse evals (langfuse_evals.py)
    "ensure_safety_dataset",
    "eval_safety",
    "eval_standards_compliance",
    "eval_helpfulness",
    "run_safety_eval",
    "ci_gate_block_unsafe_prompts",
    "seed_safety_datasets",
    "score_trace",
    # Langfuse sessions/feedback/alerts (langfuse_sessions.py)
    "EngineeringSession",
    "start_engineering_session",
    "end_engineering_session",
    "record_user_feedback",
    "get_trace_share_url",
    "alert_on_unsafe_trace",
    "add_trace_comment",
    # Langfuse middleware (langfuse_middleware.py)
    "LangfuseMiddleware",
    "install_langfuse_middleware",
    # LangWatch (legacy)
    "langwatch_tracker",
    "track_llm_call_langwatch",
    # Smithery MCP
    "smithery_client",
    "mcp_registry",
    # Supabase (Postgres + Storage + Auth)
    "PUBLIC_BUCKET_MANUALS",
    "PRIVATE_BUCKET_REPORTS",
    "PRIVATE_BUCKET_SCREENSHOTS",
    "PRIVATE_BUCKET_UPLOADS",
    "SupabaseUploadError",
    "SupabaseAuthError",
    "upload_bytes",
    "upload_file",
    "get_public_url",
    "get_signed_url",
    "delete_file",
    "list_files",
    "ensure_buckets_exist",
    "supabase_health_check",
    "verify_supabase_token",
    "supabase_get_oauth_url",
    "send_magic_link",
    "link_or_create_local_user",
    "supabase_auth_health_check",
    # Package-level helpers
    "__version__",
    "health_check_all",
    "flush_all",
    "aclose_all",
]


# ─── Aggregated health-check & shutdown helpers ─────────────────────────────


def health_check_all() -> dict[str, Any]:
    """Aggregate health_check() output from all integrations.

    Returns a dict keyed by integration name. Each value is the
    integration's own ``health_check()`` output. Failures during a
    health_check call are caught and recorded as ``{"error": "..."}``
    so one broken integration doesn't break the aggregate.

    Example::

        >>> from integrations import health_check_all
        >>> health_check_all()
        {
            "langfuse": {"enabled": True, ...},
            "langwatch": {"enabled": False, ...},
            "smithery": {"enabled": True, ...},
            "supabase": {"enabled": True, ...},
            "supabase_auth": {"enabled": True, ...},
        }
    """
    results: dict[str, Any] = {}

    # Each (name, callable) — callable takes no args and returns a dict.
    checks: list[tuple[str, Any]] = [
        ("langfuse", lambda: langfuse_tracker.health_check()),
        ("langwatch", lambda: langwatch_tracker.health_check()),
        ("smithery", lambda: smithery_client.health_check()),
        ("supabase", lambda: supabase_health_check()),
        ("supabase_auth", lambda: supabase_auth_health_check()),
    ]

    for name, check in checks:
        try:
            results[name] = check()
        except Exception as e:
            logger.warning("health_check failed for %s: %s", name, e)
            results[name] = {"enabled": False, "error": str(e)}

    # Overall status: "healthy" if all enabled integrations are healthy,
    # "degraded" if some are unhealthy, "down" if all are.
    enabled_count = sum(1 for v in results.values() if v.get("enabled"))
    error_count = sum(1 for v in results.values() if "error" in v)
    if enabled_count == 0:
        overall = "down"
    elif error_count == 0:
        overall = "healthy"
    else:
        overall = "degraded"

    return {
        "overall": overall,
        "integrations": results,
        "version": __version__,
    }


def flush_all() -> None:
    """Flush pending events from all observability integrations (blocking).

    Safe to call from an atexit handler or before shutdown. All exceptions
    are suppressed — one integration's flush failure must not block others.
    """
    for name, flush_fn in [
        ("langfuse", lambda: langfuse_tracker.flush()),
        ("langwatch", lambda: langwatch_tracker.flush()),
    ]:
        with contextlib.suppress(Exception):
            flush_fn()
            logger.debug("Flushed %s", name)


async def aclose_all() -> None:
    """Async close for all integrations that hold resources (HTTP clients, etc.).

    Call from FastAPI's shutdown event. Flushes observability buffers
    and closes HTTP connection pools.
    """
    # Sync flush first
    flush_all()

    # Close async resources
    for name, close_coro in [
        ("smithery", smithery_client.aclose()),
    ]:
        try:
            await close_coro
            logger.debug("Closed %s", name)
        except Exception as e:
            logger.warning("Close failed for %s: %s", name, e)


def _atexit_flush_all() -> None:
    """Module-level atexit handler — flushes all integrations on shutdown.

    For async resources (e.g., Smithery's HTTP client), each integration
    registers its own atexit handler that creates a fresh event loop if
    needed. This function only handles sync flushes.
    """
    with contextlib.suppress(Exception):
        flush_all()


atexit_handler_registered = False
try:
    import atexit as _atexit

    _atexit.register(_atexit_flush_all)
    atexit_handler_registered = True
except Exception:  # pragma: no cover — atexit always available in CPython
    pass


logger.debug(
    "integrations package initialized (version=%s, atexit=%s)",
    __version__,
    atexit_handler_registered,
)
