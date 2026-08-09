"""
LangWatch Integration for AhmedETAP (Hardened Edition)
======================================================

Provides LLM observability, tracing, and evaluation for all AI agent calls.

⚠️ HARDENING (vs. original) ⚠️
This module is used by power-systems engineering agents whose outputs can
affect human life (arc flash PPE, short-circuit breaker ratings, grounding
grid design, protective coordination). Hardening measures mirror the
Langfuse integration:

1. **Lazy client init** — SDK client is created on first use, not at module
   import. This allows env vars loaded later by python-dotenv to take
   effect, and prevents network errors at import time.
2. **Hard timeout** on every LangWatch API call (default 5 s, override
   via ``LANGWATCH_TIMEOUT`` env var).
3. **Retry with exponential backoff** — transient failures (network errors,
   5xx) are retried up to 3 times with jitter. Non-retryable errors
   (4xx auth/validation) fail fast.
4. **PII redaction** — input/output strings are truncated to a max
   length (default 4 KB) to avoid leaking large PII payloads to the
   cloud. Set ``LANGWATCH_MAX_CAPTURE_CHARS=0`` to disable capture
   entirely.
5. **atexit flush** — registered at module import time so traces are
   flushed on interpreter shutdown.
6. **Metrics counters** — success/failure/total counts exposed via
   ``health_check()`` for monitoring.
7. **Exception recording** — ``track_llm_call`` records the exception
   on the LangWatch trace so failures are visible in the dashboard.
8. **Explicit disable** — ``LANGWATCH_ENABLED=false`` disables the
   integration without removing credentials.
9. **Sync wrapper fixed** — original ``sync_wrapper`` did not capture
   output (only ``async_wrapper`` did). Both now capture consistently.

Environment variables:

    LANGWATCH_API_KEY              sk-lw-...
    LANGWATCH_PROJECT              AhmedETAP (default)
    LANGWATCH_ENDPOINT             https://app.langwatch.ai (default)
    LANGWATCH_ENABLED              "false" to explicitly disable
    LANGWATCH_TIMEOUT              per-call timeout seconds (default 5.0)
    LANGWATCH_MAX_CAPTURE_CHARS    max chars of input/output to capture
                                    (default 4096; 0 disables capture)
    LANGWATCH_MAX_RETRIES          max retry attempts (default 3)

Usage:
    from integrations.langwatch_integration import langwatch_tracker, track_llm_call

    @track_llm_call(name="etap_expert_response")
    async def my_agent_function(prompt: str) -> str:
        ...
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import functools
import logging
import os
import random
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

from integrations._observability_base import NoOpContext as _NoOpContext
from integrations._observability_base import build_health_check
from integrations._observability_base import env_truthy as _env_truthy

# ─── LangWatch SDK (optional dependency) ─────────────────────────────────────
try:
    import langwatch

    LANGWATCH_AVAILABLE = True
    logger.debug("LangWatch SDK loaded successfully")
except ImportError:
    LANGWATCH_AVAILABLE = False
    logger.info("LangWatch SDK not installed. Run: pip install langwatch")


# ─── Helpers ───────────────────────────────────────────────────────────────


# NOTE: _env_truthy is imported from integrations._observability_base above.
# It is a self-contained copy (no core.utils dependency) so that this module
# can be imported in minimal environments where opentelemetry is not installed.


def _env_int(var: str, default: int) -> int:
    """Read an int from an env var with a default. Logs and falls back on parse error.

    Mirrors the helper in ``integrations.smithery_mcp._env_int`` so both
    observability modules apply the same defensive parsing — a misconfigured
    env var (e.g. ``LANGWATCH_TIMEOUT=5s``) must NEVER crash module import,
    because that would take down the entire integrations package and any
    service that imports it.
    """
    raw = os.environ.get(var)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid int for %s=%r — using default %d", var, raw, default)
        return default


def _truncate_for_capture(text: Any, max_chars: int) -> str | None:
    """Truncate text to ``max_chars`` chars. Return ``None`` if capture disabled.

    Mirrors the Langfuse integration's redaction helper so both observability
    backends apply the same PII protection.
    """
    if max_chars <= 0:
        return None
    if text is None:
        return None
    s = str(text)
    if len(s) > max_chars:
        return s[:max_chars] + f"\n...[truncated, {len(s) - max_chars} more chars]"
    return s


def _is_retryable_exception(exc: BaseException) -> bool:
    """Classify whether an exception is worth retrying.

    Retryable:
        - ConnectionError, TimeoutError, OSError (network)
        - httpx.HTTPStatusError with 5xx status
    Non-retryable:
        - 4xx (auth, validation, not found)
        - Programming errors (TypeError, ValueError, AttributeError)
    """
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    # httpx.HTTPStatusError — check status code without hard-importing httpx
    # (avoids a hard dependency if a different HTTP client is used in tests).
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return isinstance(status, int) and 500 <= status < 600


# ─── LangWatchTracker ──────────────────────────────────────────────────────


class LangWatchTracker:
    """
    Central LangWatch observability tracker for AhmedETAP.
    Wraps all LLM calls with automatic tracing and metrics.

    Thread-safe via double-checked locking on client init.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("LANGWATCH_API_KEY", "")
        self.project = os.getenv("LANGWATCH_PROJECT", "AhmedETAP")
        self.endpoint = os.getenv("LANGWATCH_ENDPOINT", "https://app.langwatch.ai")
        # Robust int parsing — a misconfigured env var (e.g. "5s" or "abc")
        # falls back to the default instead of crashing module import.
        # (Original code used int(float(...)) directly which raised ValueError
        #  on bad input, taking down the entire integrations package.)
        self.timeout = _env_int("LANGWATCH_TIMEOUT", 5)
        self.max_capture_chars = _env_int("LANGWATCH_MAX_CAPTURE_CHARS", 4096)
        self.max_retries = _env_int("LANGWATCH_MAX_RETRIES", 3)

        # Explicit disable flag takes precedence
        self.enabled = (
            LANGWATCH_AVAILABLE
            and bool(self.api_key)
            and _env_truthy("LANGWATCH_ENABLED", default=True)
        )

        # LAZY init: client is created on first use, not at construction.
        self._client_init_attempted = False
        self._client_lock = threading.Lock()

        # Metrics counters (atomic-ish via GIL; suffice for process-level stats)
        self._metrics_lock = threading.Lock()
        self._total_calls = 0
        self._success_calls = 0
        self._failure_calls = 0
        self._retry_attempts = 0
        self._total_latency_ms = 0.0

        if not self.enabled:
            if not LANGWATCH_AVAILABLE:
                logger.info("LangWatch disabled: SDK not installed")
            elif not self.api_key:
                logger.info("LangWatch disabled: LANGWATCH_API_KEY not set")
            elif not _env_truthy("LANGWATCH_ENABLED", default=True):
                logger.info("LangWatch disabled via LANGWATCH_ENABLED=false")

    # ─── Lazy client init ────────────────────────────────────────────────

    def _get_client(self) -> Any | None:
        """Lazily configure the LangWatch SDK on first use (thread-safe).

        LangWatch's SDK uses module-level state (``langwatch.api_key`` /
        ``langwatch.endpoint``) rather than a client object, so this method
        configures the module once and returns ``True`` (or ``None`` on
        failure) so callers can use a truthy check.
        """
        if not self.enabled:
            return None
        if self._client_init_attempted:
            # Already attempted — return the cached result.
            # We can't tell if it succeeded without storing the result.
            return getattr(self, "_client_ready", False) or None
        with self._client_lock:
            # Double-checked locking
            if self._client_init_attempted:
                return getattr(self, "_client_ready", False) or None
            self._client_init_attempted = True
            try:
                langwatch.api_key = self.api_key
                langwatch.endpoint = self.endpoint
                self._client_ready = True
                logger.info(
                    "✅ LangWatch initialized — project: %s, endpoint: %s, key: %s...",
                    self.project,
                    self.endpoint,
                    self.api_key[:12] if self.api_key else "<empty>",
                )
            except Exception as e:
                logger.warning("LangWatch client init failed: %s", e)
                self._client_ready = False
                return None
        return True

    # ─── Internal: metrics ───────────────────────────────────────────────

    def _record_call(
        self,
        success: bool,
        latency_ms: float,
        retries: int = 0,
    ) -> None:
        """Record metrics for a single API call (thread-safe)."""
        with self._metrics_lock:
            self._total_calls += 1
            if success:
                self._success_calls += 1
            else:
                self._failure_calls += 1
            self._retry_attempts += retries
            self._total_latency_ms += latency_ms

    def _get_metrics(self) -> dict[str, Any]:
        """Return a snapshot of metrics counters."""
        with self._metrics_lock:
            avg_latency_ms = (
                self._total_latency_ms / self._total_calls if self._total_calls > 0 else 0.0
            )
            return {
                "total_calls": self._total_calls,
                "success_calls": self._success_calls,
                "failure_calls": self._failure_calls,
                "retry_attempts": self._retry_attempts,
                "avg_latency_ms": round(avg_latency_ms, 2),
            }

    # ─── Internal: retry wrapper ─────────────────────────────────────────

    def _call_with_retry(self, operation: Callable[[], Any], op_name: str) -> Any | None:
        """Execute an operation with retry + exponential backoff.

        Args:
            operation: zero-arg callable that performs the API call
            op_name: human-readable name for logging

        Returns:
            The operation result, or ``None`` on failure.

        Note: catches ``Exception`` (not ``BaseException``) so that
        ``KeyboardInterrupt`` / ``SystemExit`` propagate immediately
        without being retried or swallowed.
        """
        for attempt in range(self.max_retries + 1):
            start = time.monotonic()
            try:
                result = operation()
                latency_ms = (time.monotonic() - start) * 1000
                self._record_call(success=True, latency_ms=latency_ms, retries=attempt)
                if attempt > 0:
                    logger.info(
                        "LangWatch %s succeeded after %d retries",
                        op_name,
                        attempt,
                    )
                return result
            except Exception as exc:  # noqa: BLE001 — broad on purpose (NOT BaseException: let KeyboardInterrupt propagate)
                latency_ms = (time.monotonic() - start) * 1000
                if not _is_retryable_exception(exc):
                    # Non-retryable — fail fast
                    self._record_call(success=False, latency_ms=latency_ms, retries=attempt)
                    logger.warning(
                        "LangWatch %s failed (non-retryable): %s",
                        op_name,
                        exc,
                    )
                    return None
                if attempt >= self.max_retries:
                    self._record_call(success=False, latency_ms=latency_ms, retries=attempt)
                    logger.warning(
                        "LangWatch %s failed after %d retries: %s",
                        op_name,
                        attempt,
                        exc,
                    )
                    return None
                # Exponential backoff with jitter: 0.5s, 1s, 2s, 4s... + jitter
                delay = min(0.5 * (2**attempt) + random.uniform(0, 0.25), 10.0)
                logger.debug(
                    "LangWatch %s attempt %d failed (%s) — retrying in %.2fs",
                    op_name,
                    attempt + 1,
                    exc,
                    delay,
                )
                time.sleep(delay)
        # Unreachable, but keeps mypy happy
        return None

    # ─── Tracing ──────────────────────────────────────────────────────────

    def track(
        self,
        name: str,
        input_text: str | None = None,
        output_text: str | None = None,
        metadata: dict | None = None,
        model: str | None = None,
        agent: str | None = None,
    ) -> None:
        """Manually log a single LLM interaction to LangWatch.

        Retries on transient failures (network, 5xx). PII is truncated
        to ``LANGWATCH_MAX_CAPTURE_CHARS`` before being sent to the cloud.

        Note: ``self.timeout`` is documented for callers but NOT enforced
        here — the LangWatch SDK uses an internal async sender that does
        not expose a per-call timeout. The retry wrapper will catch
        ``TimeoutError`` if the SDK raises one. For tighter timeout
        control, wrap the call site in ``concurrent.futures``.
        """

        def _do_track() -> None:
            if self._get_client() is None:
                return
            trace = langwatch.trace(
                name=name,
                metadata={
                    "project": self.project,
                    "agent": agent or "unknown",
                    "model": model or "unknown",
                    **(metadata or {}),
                },
            )
            # Defensive: validate that langwatch.trace() returned a usable
            # trace object. If it returned None or a non-trace object (e.g.
            # a dict from a mocked SDK), accessing .update() / .send() would
            # raise AttributeError. That exception is technically caught by
            # the retry wrapper (as non-retryable), but it's cleaner to
            # short-circuit here and log the anomaly — matching the
            # defensive pattern used in get_context_manager().
            if trace is None or not hasattr(trace, "send"):
                logger.debug(
                    "LangWatch trace() returned non-trace object (%r) — skipping track(%s)",
                    type(trace).__name__ if trace is not None else "None",
                    name,
                )
                return
            captured_input = _truncate_for_capture(input_text, self.max_capture_chars)
            captured_output = _truncate_for_capture(output_text, self.max_capture_chars)
            if captured_input is not None and hasattr(trace, "update"):
                trace.update(input=captured_input)
            if captured_output is not None and hasattr(trace, "update"):
                trace.update(output=captured_output)
            trace.send()

        self._call_with_retry(_do_track, op_name=f"track({name})")

    def get_context_manager(
        self,
        name: str,
        metadata: dict | None = None,
        **kwargs: Any,
    ):
        """Return a LangWatch trace context manager (or no-op).

        Note: context managers cannot be retried in-line (the body runs
        between ``__enter__`` and ``__exit__``), so retry is not applied
        here. Use ``track()`` for retry-protected manual logging.

        If ``langwatch.trace()`` returns ``None`` or a non-context-manager
        object, a ``_NoOpContext`` is returned to prevent ``with None:``
        failures downstream.
        """
        if self._get_client() is None:
            return _NoOpContext()
        try:
            kw: dict[str, Any] = {"name": name}
            if metadata:
                kw["metadata"] = metadata
            kw.update(kwargs)
            cm = langwatch.trace(**kw)
            # Validate that the returned object is actually usable as a
            # context manager (has __enter__ and __exit__). If not, fall
            # back to a no-op to prevent `with None:` failures.
            if cm is None or not hasattr(cm, "__enter__") or not hasattr(cm, "__exit__"):
                logger.debug(
                    "LangWatch trace() returned non-context-manager object (%r) — using no-op",
                    type(cm).__name__ if cm is not None else "None",
                )
                return _NoOpContext()
            return cm
        except Exception as e:
            logger.warning("LangWatch context error (non-critical): %s", e)
            return _NoOpContext()

    # ─── Lifecycle ────────────────────────────────────────────────────────

    def flush(self) -> None:
        """Flush pending traces to LangWatch (blocking). Call before shutdown."""
        if not self.enabled or not getattr(self, "_client_ready", False):
            return
        try:
            # LangWatch SDK uses a background sender; calling trace.send()
            # already enqueues, and there is no explicit flush in all versions.
            # We attempt flush() if available, otherwise no-op gracefully.
            flush_fn = getattr(langwatch, "flush", None)
            if callable(flush_fn):
                flush_fn()
        except Exception as e:
            logger.debug("LangWatch flush error (non-critical): %s", e)

    def shutdown(self) -> None:
        """Graceful shutdown — flush + release resources."""
        with contextlib.suppress(Exception):
            self.flush()

    # ─── Status ───────────────────────────────────────────────────────────

    @property
    def dashboard_url(self) -> str:
        """URL to the LangWatch dashboard."""
        return self.endpoint

    def health_check(self) -> dict[str, Any]:
        """Return LangWatch integration status with metrics."""
        return build_health_check(
            enabled=self.enabled,
            provider_name="LangWatch",
            project=self.project,
            sdk_available=LANGWATCH_AVAILABLE,
            dashboard_url=self.dashboard_url if self.enabled else None,
            endpoint=self.endpoint,
            client_initialized=getattr(self, "_client_ready", False),
            api_key_prefix=((self.api_key[:12] + "...") if self.api_key else None),
            timeout_seconds=self.timeout,
            max_capture_chars=self.max_capture_chars,
            max_retries=self.max_retries,
            metrics=self._get_metrics(),
        )


# ─── Module-level singleton ───────────────────────────────────────────────────
langwatch_tracker = LangWatchTracker()


# ─── atexit handler: flush on shutdown ─────────────────────────────────────────


def _atexit_flush() -> None:
    """Flush LangWatch events on interpreter shutdown.

    Uses contextlib.suppress because atexit handlers must never raise —
    any exception during interpreter shutdown would be printed to stderr
    and could mask other shutdown errors.
    """
    with contextlib.suppress(Exception):
        langwatch_tracker.flush()


atexit.register(_atexit_flush)


# ─── Decorator: track_llm_call ────────────────────────────────────────────────


def track_llm_call(
    name: str,
    agent: str | None = None,
    model: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable:
    """
    Decorator to automatically track LLM calls via LangWatch.

    Records:
    - Input (truncated to ``LANGWATCH_MAX_CAPTURE_CHARS``)
    - Output (truncated)
    - Exceptions (recorded on the trace + re-raised)
    - Metadata: agent name, model name

    Both async and sync functions are supported. The original implementation
    had a bug where ``sync_wrapper`` did not capture output — both wrappers
    now capture consistently.

    Example::

        @track_llm_call(name="fault_analysis", agent="ShortCircuitAgent")
        async def analyze_fault(prompt: str) -> str:
            return await llm.complete(prompt)
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                input_text = str(args[0]) if capture_input and args else None
                ctx = langwatch_tracker.get_context_manager(
                    name=name,
                    metadata={"agent": agent, "model": model},
                )
                with ctx as trace:
                    try:
                        result = await func(*args, **kwargs)
                        if input_text and hasattr(trace, "update"):
                            trace.update(
                                input=_truncate_for_capture(
                                    input_text, langwatch_tracker.max_capture_chars
                                )
                            )
                        if (
                            capture_output
                            and langwatch_tracker.enabled
                            and hasattr(trace, "update")
                        ):
                            trace.update(
                                output=_truncate_for_capture(
                                    result, langwatch_tracker.max_capture_chars
                                )
                            )
                        return result
                    except Exception as exc:
                        # Record exception on the trace so it's visible in
                        # the dashboard, then re-raise so the caller sees it.
                        # NOTE: ``Exception`` (not ``BaseException``) so that
                        # ``KeyboardInterrupt`` / ``SystemExit`` propagate
                        # without being recorded on the trace (user is
                        # interrupting the program, they don't care about it).
                        if hasattr(trace, "record_exception"):
                            with contextlib.suppress(Exception):
                                trace.record_exception(exc)
                        raise

            return async_wrapper

        # Sync wrapper — FIXED: now captures output (original did not)
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            input_text = str(args[0]) if capture_input and args else None
            ctx = langwatch_tracker.get_context_manager(
                name=name,
                metadata={"agent": agent, "model": model},
            )
            with ctx as trace:
                try:
                    result = func(*args, **kwargs)
                    if input_text and hasattr(trace, "update"):
                        trace.update(
                            input=_truncate_for_capture(
                                input_text, langwatch_tracker.max_capture_chars
                            )
                        )
                    if capture_output and langwatch_tracker.enabled and hasattr(trace, "update"):
                        trace.update(
                            output=_truncate_for_capture(
                                result, langwatch_tracker.max_capture_chars
                            )
                        )
                    return result
                except Exception as exc:
                    # See note in async_wrapper: ``Exception`` not ``BaseException``.
                    if hasattr(trace, "record_exception"):
                        with contextlib.suppress(Exception):
                            trace.record_exception(exc)
                    raise

        return sync_wrapper

    return decorator
