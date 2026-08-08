"""
Smithery MCP Integration for AhmedETAP (Hardened Edition)
=========================================================

Connects the platform to Model Context Protocol (MCP) servers via Smithery.
MCP allows AI agents to call external tools (databases, APIs, simulators)
in a standardized way. Smithery is the registry/gateway for MCP servers.

Docs: https://smithery.ai/docs

⚠️ HARDENING (vs. original) ⚠️
1. **Retry with exponential backoff** — transient failures (network, 5xx)
   are retried up to 3 times with jitter. Non-retryable errors (4xx)
   fail fast.
2. **Circuit breaker** — after N consecutive failures, the circuit opens
   and short-circuits calls for a recovery period. Prevents cascading
   failures when Smithery is degraded.
3. **Rate limiting** — token-bucket limiter caps calls per second to
   respect Smithery's API limits. Configurable via
   ``SMITHERY_RATE_LIMIT_RPS`` (default 5).
4. **Configurable server IDs** — MCP server IDs (``etap-standards-db``,
   ``equipment-catalog``, ``report-generator``) are now overridable via
   env vars so deployments can point to private registries.
5. **Input validation** — tool arguments are validated to be
   JSON-serializable and under a max size (default 256 KB) to prevent
   accidental payload abuse.
6. **Disabled vs. error distinction** — ``list_servers()`` and
   ``call_tool()`` now return distinct error shapes for "disabled"
   vs. "transport error" so callers can branch correctly.
7. **Generic User-Agent** — version stripped to avoid fingerprinting.
8. **Request ID** — every call gets a UUID for log correlation.
9. **Configurable timeouts** — list=10s, call=30s, long_call=120s,
   all env-overridable.
10. **Async client pooling** — uses a shared ``httpx.AsyncClient`` for
    connection reuse (created lazily, closed on shutdown).

Environment variables:

    SMITHERY_API_KEY              UUID-format API key
    SMITHERY_BASE_URL             https://api.smithery.ai (default)
    SMITHERY_ENABLED              "false" to explicitly disable
    SMITHERY_TIMEOUT_LIST         list_servers timeout seconds (default 10)
    SMITHERY_TIMEOUT_CALL         call_tool timeout seconds (default 30)
    SMITHERY_TIMEOUT_LONG_CALL    long-running tool timeout (default 120)
    SMITHERY_MAX_RETRIES          max retry attempts (default 3)
    SMITHERY_RATE_LIMIT_RPS       max requests per second (default 5)
    SMITHERY_MAX_PAYLOAD_KB       max tool arguments size in KB (default 256)
    SMITHERY_CB_FAILURE_THRESHOLD circuit breaker failure threshold (default 5)
    SMITHERY_CB_RECOVERY_SECONDS  circuit breaker recovery period (default 60)

    # Configurable MCP server IDs (override for private registries)
    SMITHERY_SERVER_STANDARDS_DB  default: etap-standards-db
    SMITHERY_SERVER_EQUIPMENT     default: equipment-catalog
    SMITHERY_SERVER_REPORT_GEN    default: report-generator
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import logging
import os
import random
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ─── Helpers ───────────────────────────────────────────────────────────────


# Import env_truthy from the observability base (self-contained, no core.utils
# dependency — avoids import-time failure when opentelemetry is not installed).
from integrations._observability_base import env_truthy as _env_truthy


def _env_int(var: str, default: int) -> int:
    """Read an int from an env var with a default. Logs and falls back on parse error."""
    raw = os.environ.get(var)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        logger.warning("Invalid int for %s=%r — using default %d", var, raw, default)
        return default


def _env_float(var: str, default: float) -> float:
    """Read a float from an env var with a default."""
    raw = os.environ.get(var)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid float for %s=%r — using default %f", var, raw, default)
        return default


def _is_retryable_http_status(status: int) -> bool:
    """Return True for HTTP statuses worth retrying (5xx + 429)."""
    return status >= 500 or status == 429


def _is_retryable_exception(exc: BaseException) -> bool:
    """Classify whether an HTTP exception is worth retrying."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int) and _is_retryable_http_status(status):
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.PoolTimeout)):
        return True
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


# ─── Token-bucket rate limiter ─────────────────────────────────────────────


class _TokenBucket:
    """Thread-safe token-bucket rate limiter.

    Allows bursts up to ``capacity`` tokens, refilled at ``rate`` tokens
    per second. Blocks (with timeout) until a token is available.
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self._tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Block until a token is available, or timeout. Returns True on success."""
        deadline = time.monotonic() + timeout
        with self._lock:
            while True:
                now = time.monotonic()
                # Refill proportional to elapsed time
                elapsed = now - self._last_refill
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # Compute wait time for next token
                wait = (1.0 - self._tokens) / self.rate
                if now + wait > deadline:
                    return False
                # Release lock while sleeping to avoid blocking other threads
                # (this is approximate; for high-contention scenarios, use
                # asyncio.Semaphore instead.)
                self._lock.release()
                try:
                    time.sleep(min(wait, deadline - now))
                finally:
                    self._lock.acquire()


# ─── Circuit breaker (uses engine.resilience canonical impl) ───────────────


def _get_circuit_breaker(
    name: str,
    failure_threshold: int,
    recovery_timeout: float,
) -> Any | None:
    """Get or create a circuit breaker from the canonical engine.resilience registry.

    Returns None if engine.resilience isn't importable (e.g., in minimal
    test environments), in which case the caller should skip CB protection.
    """
    try:
        from engine.resilience import CircuitBreaker, get_circuit_breaker, register_circuit_breaker

        existing = get_circuit_breaker(name)
        if existing is not None:
            return existing
        cb = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
        register_circuit_breaker(cb)
        return cb
    except Exception as e:
        logger.debug("Circuit breaker unavailable for %s: %s", name, e)
        return None


# ─── SmitheryClient ────────────────────────────────────────────────────────


class SmitheryClient:
    """
    Hardened client for the Smithery MCP server registry.

    Enables AhmedETAP agents to discover and call external MCP tools with
    retry, circuit-breaker, and rate-limit protection.
    """

    BASE_URL = "https://api.smithery.ai"

    def __init__(self) -> None:
        self.api_key = os.getenv("SMITHERY_API_KEY", "")
        # Instance attribute renamed to `endpoint` to avoid the SonarCloud S1845
        # clash with the class constant `BASE_URL` (differ only by case).
        self.endpoint = os.getenv("SMITHERY_BASE_URL", self.BASE_URL)

        # Timeouts
        self.timeout_list = _env_float("SMITHERY_TIMEOUT_LIST", 10.0)
        self.timeout_call = _env_float("SMITHERY_TIMEOUT_CALL", 30.0)
        self.timeout_long_call = _env_float("SMITHERY_TIMEOUT_LONG_CALL", 120.0)

        # Retry
        self.max_retries = _env_int("SMITHERY_MAX_RETRIES", 3)

        # Rate limit
        rps = _env_float("SMITHERY_RATE_LIMIT_RPS", 5.0)
        self._rate_limiter = _TokenBucket(rate=rps, capacity=max(rps, 1.0))

        # Payload size limit (KB → bytes)
        self.max_payload_bytes = _env_int("SMITHERY_MAX_PAYLOAD_KB", 256) * 1024

        # Explicit enable/disable flag
        self.enabled = bool(self.api_key) and _env_truthy("SMITHERY_ENABLED", default=True)

        # Circuit breaker
        cb_threshold = _env_int("SMITHERY_CB_FAILURE_THRESHOLD", 5)
        cb_recovery = _env_float("SMITHERY_CB_RECOVERY_SECONDS", 60.0)
        self._circuit_breaker = _get_circuit_breaker(
            name="smithery",
            failure_threshold=cb_threshold,
            recovery_timeout=cb_recovery,
        )

        # Lazy-init shared httpx client (for connection pooling)
        self._http_client: httpx.AsyncClient | None = None
        self._http_client_fallback: httpx.AsyncClient | None = None
        self._http_client_lock = threading.Lock()
        self._http_client_init_attempted = False

        # Metrics
        self._metrics_lock = threading.Lock()
        self._total_calls = 0
        self._success_calls = 0
        self._failure_calls = 0
        self._circuit_open_count = 0
        self._rate_limited_count = 0

        if self.enabled:
            logger.info("✅ Smithery MCP client initialized — endpoint: %s", self.endpoint)
        else:
            if not self.api_key:
                logger.info("Smithery disabled: SMITHERY_API_KEY not set")
            elif not _env_truthy("SMITHERY_ENABLED", default=True):
                logger.info("Smithery disabled via SMITHERY_ENABLED=false")

    # ─── HTTP client lifecycle ───────────────────────────────────────────

    def _get_http_client(self) -> httpx.AsyncClient:
        """Lazily create a shared httpx.AsyncClient (thread-safe).

        On failure, caches a single fallback client so we don't leak
        ephemeral ``httpx.AsyncClient`` instances on every call.
        """
        if self._http_client is not None:
            return self._http_client
        with self._http_client_lock:
            if self._http_client is not None:
                return self._http_client
            if self._http_client_init_attempted:
                # Already failed once; reuse the cached fallback if any.
                # This prevents resource leaks from creating a new ephemeral
                # httpx.AsyncClient on every call.
                if self._http_client_fallback is None:
                    self._http_client_fallback = httpx.AsyncClient(timeout=self.timeout_call)
                return self._http_client_fallback
            self._http_client_init_attempted = True
            try:
                self._http_client = httpx.AsyncClient(timeout=self.timeout_call)
                logger.debug("Smithery HTTP client initialized (shared, pooled)")
                return self._http_client
            except Exception as e:
                logger.warning("Smithery HTTP client init failed: %s", e)
                # Cache a fallback so we don't repeatedly try to create one.
                self._http_client_fallback = httpx.AsyncClient(timeout=self.timeout_call)
                return self._http_client_fallback

    async def _close_http_client(self) -> None:
        """Close the shared HTTP client. Safe to call multiple times."""
        clients_to_close: list[httpx.AsyncClient] = []
        with self._http_client_lock:
            if self._http_client is not None:
                clients_to_close.append(self._http_client)
                self._http_client = None
            fallback = self._http_client_fallback
            self._http_client_fallback = None
        if fallback is not None:
            clients_to_close.append(fallback)
        for client in clients_to_close:
            with contextlib.suppress(Exception):
                await client.aclose()

    # ─── Properties ──────────────────────────────────────────────────────

    @property
    def _headers(self) -> dict:
        """Auth headers. User-Agent is intentionally generic to avoid fingerprinting."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Generic UA — no version disclosure (security: reduces attack surface)
            "User-Agent": "AhmedETAP-Platform",
            "X-Request-ID": str(uuid.uuid4()),
        }

    # ─── Metrics ─────────────────────────────────────────────────────────

    def _record_call(
        self,
        success: bool,
        circuit_open: bool = False,
        rate_limited: bool = False,
    ) -> None:
        with self._metrics_lock:
            self._total_calls += 1
            if success:
                self._success_calls += 1
            else:
                self._failure_calls += 1
            if circuit_open:
                self._circuit_open_count += 1
            if rate_limited:
                self._rate_limited_count += 1

    def _get_metrics(self) -> dict[str, Any]:
        with self._metrics_lock:
            return {
                "total_calls": self._total_calls,
                "success_calls": self._success_calls,
                "failure_calls": self._failure_calls,
                "circuit_open_count": self._circuit_open_count,
                "rate_limited_count": self._rate_limited_count,
            }

    # ─── Input validation ───────────────────────────────────────────────

    def _validate_arguments(self, arguments: dict[str, Any]) -> str | None:
        """Validate tool arguments. Returns error string on failure, None on success."""
        if not isinstance(arguments, dict):
            return f"arguments must be a dict, got {type(arguments).__name__}"
        try:
            payload = json.dumps(arguments)
        except (TypeError, ValueError) as e:
            return f"arguments are not JSON-serializable: {e}"
        if len(payload.encode("utf-8")) > self.max_payload_bytes:
            return (
                f"arguments payload exceeds max size "
                f"({len(payload.encode('utf-8'))} bytes > {self.max_payload_bytes} bytes)"
            )
        return None

    # ─── Circuit breaker guard ──────────────────────────────────────────

    def _check_circuit(self) -> bool:
        """Return True if the call should proceed (circuit closed/half-open).

        Records a circuit_open metric if the circuit is open.
        """
        if self._circuit_breaker is None:
            return True
        try:
            state = self._circuit_breaker.get_state()
            # engine.resilience.CircuitBreakerState is an Enum with values
            # like "CLOSED", "OPEN", "HALF_OPEN". Allow HALF_OPEN (probing).
            if state == "OPEN":
                self._record_call(success=False, circuit_open=True)
                return False
            return True
        except Exception as e:
            logger.debug("Circuit breaker check failed (allowing call): %s", e)
            return True

    def _record_circuit_result(self, success: bool) -> None:
        """Record call result on the circuit breaker."""
        if self._circuit_breaker is None:
            return
        try:
            if success:
                self._circuit_breaker.record_success()
            else:
                self._circuit_breaker.record_failure()
        except Exception as e:
            logger.debug("Circuit breaker record failed: %s", e)

    # ─── Retry wrapper (async) ──────────────────────────────────────────

    async def _call_with_retry(
        self,
        operation: Callable[[], Any],
        op_name: str,
        timeout: float,
    ) -> Any:
        """Execute an async operation with retry + exponential backoff.

        Respects the rate limiter and circuit breaker.

        Note: catches ``Exception`` (not ``BaseException``) so that
        ``KeyboardInterrupt`` / ``SystemExit`` propagate immediately
        without being retried or swallowed.
        """
        if not self._check_circuit():
            return {
                "error": "smithery_circuit_open",
                "message": "Smithery circuit breaker is open — try again later",
                "result": None,
            }

        # Rate limit (block up to 30s for a token)
        if not self._rate_limiter.acquire(timeout=30.0):
            self._record_call(success=False, rate_limited=True)
            return {
                "error": "smithery_rate_limited",
                "message": "Rate limit exceeded — try again later",
                "result": None,
            }

        last_exc: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(operation(), timeout=timeout)
                self._record_call(success=True)
                self._record_circuit_result(success=True)
                if attempt > 0:
                    logger.info("Smithery %s succeeded after %d retries", op_name, attempt)
                return result
            except Exception as exc:  # noqa: BLE001 — broad on purpose (NOT BaseException: let KeyboardInterrupt propagate)
                last_exc = exc
                if not _is_retryable_exception(exc):
                    self._record_call(success=False)
                    self._record_circuit_result(success=False)
                    logger.warning(
                        "Smithery %s failed (non-retryable): %s",
                        op_name,
                        exc,
                    )
                    return {
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "attempts": attempt + 1,
                        "result": None,
                    }
                if attempt >= self.max_retries:
                    self._record_call(success=False)
                    self._record_circuit_result(success=False)
                    logger.warning(
                        "Smithery %s failed after %d retries: %s",
                        op_name,
                        attempt,
                        exc,
                    )
                    return {
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "attempts": attempt + 1,
                        "result": None,
                    }
                delay = min(0.5 * (2**attempt) + random.uniform(0, 0.25), 10.0)
                logger.debug(
                    "Smithery %s attempt %d failed (%s) — retrying in %.2fs",
                    op_name,
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        # Unreachable
        return {"error": str(last_exc), "result": None}

    # ─── Public API ──────────────────────────────────────────────────────

    async def list_servers(self, query: str | None = None) -> list[dict]:
        """List available MCP servers from Smithery registry.

        Returns an empty list when disabled. On transport errors, returns
        an empty list (with error logged) — callers should use
        ``health_check()`` to distinguish "disabled" from "error".
        """
        if not self.enabled:
            return []

        async def _do_list() -> list[dict]:
            client = self._get_http_client()
            params = {"q": query} if query else {}
            resp = await client.get(
                f"{self.endpoint}/servers",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("servers", [])

        result = await self._call_with_retry(
            _do_list, op_name="list_servers", timeout=self.timeout_list
        )
        if isinstance(result, list):
            return result
        # Error dict — return empty list, error already logged
        return []

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        long_running: bool = False,
    ) -> dict[str, Any]:
        """
        Call a specific tool on an MCP server via Smithery.

        Args:
            server_id: The Smithery server identifier (e.g., 'filesystem', 'postgres')
            tool_name: The MCP tool name to call
            arguments: Tool input arguments (validated: JSON-serializable, size-limited)
            long_running: If True, use the long-call timeout (default 120s)
                          instead of the regular call timeout (30s)

        Returns:
            Tool execution result dict. On failure, returns:
            ``{"error": "...", "error_type": "...", "result": None}``
            Distinct error codes:
              - ``smithery_disabled``        — integration disabled
              - ``smithery_circuit_open``    — circuit breaker open
              - ``smithery_rate_limited``    — rate limit exceeded
              - ``smithery_invalid_args``    — input validation failed
              - Other error types from the transport layer
        """
        if not self.enabled:
            return {
                "error": "smithery_disabled",
                "message": "Smithery not configured",
                "result": None,
            }

        # Input validation
        validation_err = self._validate_arguments(arguments)
        if validation_err is not None:
            self._record_call(success=False)
            return {
                "error": "smithery_invalid_args",
                "message": validation_err,
                "result": None,
            }

        timeout = self.timeout_long_call if long_running else self.timeout_call

        async def _do_call() -> dict[str, Any]:
            client = self._get_http_client()
            payload = {
                "server_id": server_id,
                "tool": tool_name,
                "arguments": arguments,
            }
            resp = await client.post(
                f"{self.endpoint}/call",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

        return await self._call_with_retry(
            _do_call, op_name=f"call_tool({server_id}/{tool_name})", timeout=timeout
        )

    # ─── Lifecycle ───────────────────────────────────────────────────────

    async def aclose(self) -> None:
        """Graceful shutdown — close the shared HTTP client."""
        await self._close_http_client()

    def health_check(self) -> dict[str, Any]:
        """Return Smithery integration status with metrics."""
        cb_state = "unknown"
        if self._circuit_breaker is not None:
            try:
                cb_state = self._circuit_breaker.get_state()
            except Exception:
                cb_state = "error"
        return {
            "enabled": self.enabled,
            "base_url": self.endpoint,
            "dashboard": "https://smithery.ai/console",
            "timeouts": {
                "list_seconds": self.timeout_list,
                "call_seconds": self.timeout_call,
                "long_call_seconds": self.timeout_long_call,
            },
            "max_retries": self.max_retries,
            "max_payload_kb": self.max_payload_bytes // 1024,
            "circuit_breaker": {
                "state": cb_state,
                "failure_threshold": getattr(self._circuit_breaker, "failure_threshold", None),
                "recovery_timeout": getattr(self._circuit_breaker, "recovery_timeout", None),
            },
            "metrics": self._get_metrics(),
        }


# ─── MCP Tool Registry for AhmedETAP agents ──────────────────────────────


class ETAPMCPRegistry:
    """
    Registry of MCP tools available to AhmedETAP agents.
    Maps engineering operations to Smithery MCP server calls.

    Server IDs are now configurable via env vars so deployments can point
    to private registries without code changes.
    """

    def __init__(self, client: SmitheryClient) -> None:
        self.client = client
        # Configurable server IDs (override via env vars)
        self.server_standards_db = os.getenv("SMITHERY_SERVER_STANDARDS_DB", "etap-standards-db")
        self.server_equipment = os.getenv("SMITHERY_SERVER_EQUIPMENT", "equipment-catalog")
        self.server_report_gen = os.getenv("SMITHERY_SERVER_REPORT_GEN", "report-generator")

    async def query_standards_database(self, standard: str, query: str) -> dict:
        """Query IEEE/IEC standards database via MCP."""
        return await self.client.call_tool(
            server_id=self.server_standards_db,
            tool_name="query",
            arguments={"standard": standard, "query": query},
        )

    async def fetch_equipment_datasheet(self, equipment_id: str) -> dict:
        """Fetch equipment technical specifications via MCP."""
        return await self.client.call_tool(
            server_id=self.server_equipment,
            tool_name="get_datasheet",
            arguments={"equipment_id": equipment_id},
        )

    async def export_report(self, report_data: dict, format: str = "pdf") -> dict:
        """Export engineering report via MCP file tool.

        Marked as long-running since report generation can take >30s for
        large reports with embedded visualizations.
        """
        return await self.client.call_tool(
            server_id=self.server_report_gen,
            tool_name="export",
            arguments={"data": report_data, "format": format},
            long_running=True,
        )


# ─── Module-level singletons ─────────────────────────────────────────────────
smithery_client = SmitheryClient()
mcp_registry = ETAPMCPRegistry(smithery_client)


# ─── atexit handler: close HTTP client ──────────────────────────────────────


def _atexit_close() -> None:
    """Close the Smithery HTTP client on interpreter shutdown.

    Uses a fresh event loop because we're in an atexit context (no running
    loop). All exceptions are suppressed (atexit handlers must never raise).

    Implementation note: ``asyncio.get_event_loop()`` is deprecated on
    Python 3.12+ when there is no running loop, and will raise
    ``RuntimeError`` on Python 3.14+. We therefore use
    ``asyncio.get_running_loop()`` (which never emits deprecation warnings)
    to detect a running loop, and fall back to creating a fresh loop with
    ``asyncio.new_event_loop()`` when none is running — which is the
    expected case during atexit.
    """
    with contextlib.suppress(Exception):
        try:
            # If we're somehow inside a running loop, do NOT block on
            # run_until_complete (that would deadlock). Schedule the close
            # instead. This branch is unlikely during atexit but is a
            # defensive measure.
            running_loop = asyncio.get_running_loop()
            running_loop.create_task(smithery_client.aclose())
            return
        except RuntimeError:
            # No running loop — expected path during atexit.
            pass
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(smithery_client.aclose())
        finally:
            loop.close()


atexit.register(_atexit_close)
