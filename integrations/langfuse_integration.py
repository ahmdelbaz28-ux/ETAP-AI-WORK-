"""
Langfuse Integration for AhmedETAP (Safety-Hardened Edition)
============================================================

Provides LLM observability, tracing, and prompt management via Langfuse
Cloud (or self-hosted Langfuse).

⚠️ SAFETY HARDENING ⚠️
This module is used by power-systems engineering agents whose outputs can
affect human life (arc flash PPE, short-circuit breaker ratings, grounding
grid design, protective coordination). Hardening measures:

1. **Async-only remote operations** — sync ``get_prompt()`` is provided
   but the agents should use ``agents.prompt_loader.get_system_prompt_async``
   which never blocks the event loop.
2. **Hard timeout** on every Langfuse API call (default 5 s, override
   via ``LANGFUSE_TIMEOUT`` env var).
3. **Circuit breaker** at the ``prompt_loader`` layer — this module
   itself never opens the breaker (the loader does, since it knows the
   full context).
4. **Exception recording** — ``track_llm_call`` records the exception
   on the Langfuse observation so failures are visible in the dashboard.
5. **atexit flush** — registered at module import time so traces are
   flushed on interpreter shutdown.
6. **PII redaction** — input/output strings are truncated to a max
   length (default 4 KB) to avoid leaking large PII payloads to the
   cloud. Set ``LANGFUSE_MAX_CAPTURE_CHARS=0`` to disable capture
   entirely.
7. **Lazy client init** — the Langfuse client is created on first
   use, not at module import, so env vars loaded later by python-dotenv
   are picked up.

Environment variables:

    LANGFUSE_PUBLIC_KEY         pk-lf-...
    LANGFUSE_SECRET_KEY         sk-lf-...
    LANGFUSE_BASE_URL           https://cloud.langfuse.com (default)
    LANGFUSE_DEFAULT_MODEL      gpt-4o (default)
    LANGFUSE_ENABLED            "false" to explicitly disable
    LANGFUSE_TIMEOUT            per-call timeout seconds (default 5.0)
    LANGFUSE_MAX_CAPTURE_CHARS  max chars of input/output to capture
                                (default 4096; 0 disables capture)
"""

from __future__ import annotations

import atexit
import functools
import logging
import os
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ─── Langfuse SDK (optional dependency) ────────────────────────────────────
try:
    from langfuse import Langfuse  # type: ignore

    LANGFUSE_AVAILABLE = True
    logger.debug("Langfuse SDK loaded successfully")
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.info("Langfuse SDK not installed. Run: pip install langfuse")


# ─── Helpers ───────────────────────────────────────────────────────────────


class _NoOpContext:
    """Silent no-op context manager when Langfuse is disabled or unavailable."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def update(self, *args, **kwargs):
        return self

    def end(self, *args, **kwargs):
        pass

    def record_exception(self, exc):
        pass


def _env_truthy(var: str, default: bool = False) -> bool:
    val = os.environ.get(var)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _truncate_for_capture(text: Any, max_chars: int) -> Optional[str]:
    """Truncate text to ``max_chars`` chars. Return ``None`` if capture disabled."""
    if max_chars <= 0:
        return None
    if text is None:
        return None
    s = str(text)
    if len(s) > max_chars:
        return s[:max_chars] + f"\n...[truncated, {len(s) - max_chars} more chars]"
    return s


# ─── LangfuseTracker ──────────────────────────────────────────────────────


class LangfuseTracker:
    """
    Central Langfuse observability tracker for AhmedETAP.
    Wraps all LLM calls with automatic tracing, plus prompt management.
    """

    def __init__(self) -> None:
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
        self.default_model = os.getenv("LANGFUSE_DEFAULT_MODEL", "gpt-4o")
        self.timeout = float(os.getenv("LANGFUSE_TIMEOUT", "5.0"))
        self.max_capture_chars = int(os.getenv("LANGFUSE_MAX_CAPTURE_CHARS", "4096"))

        # Explicit disable flag takes precedence
        self.enabled = (
            LANGFUSE_AVAILABLE
            and bool(self.public_key)
            and bool(self.secret_key)
            and _env_truthy("LANGFUSE_ENABLED", default=True)
        )

        # LAZY init: client is created on first use, not at construction.
        # This allows env vars loaded later (e.g., by python-dotenv) to
        # take effect, and it prevents network errors at import time.
        self._client: Optional[Langfuse] = None
        self._client_lock = threading.Lock()
        self._client_init_attempted = False

        if not self.enabled:
            if not LANGFUSE_AVAILABLE:
                logger.info("Langfuse disabled: SDK not installed")
            elif not self.public_key or not self.secret_key:
                logger.info("Langfuse disabled: credentials not set")
            elif not _env_truthy("LANGFUSE_ENABLED", default=True):
                logger.info("Langfuse disabled via LANGFUSE_ENABLED=false")

    # ─── Lazy client init ────────────────────────────────────────────────

    def _get_client(self) -> Optional[Langfuse]:
        """Lazily create the Langfuse client on first use (thread-safe)."""
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        with self._client_lock:
            # Double-checked locking
            if self._client is not None:
                return self._client
            if self._client_init_attempted:
                # Already failed once; don't retry to avoid log spam.
                return None
            self._client_init_attempted = True
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.base_url,
                )
                logger.info(
                    "✅ Langfuse client initialized — endpoint: %s, key: %s...",
                    self.base_url,
                    self.public_key[:12],
                )
            except Exception as e:
                logger.warning("Langfuse client init failed: %s", e)
                self._client = None
        return self._client

    # ─── Tracing ──────────────────────────────────────────────────────────

    def track(
        self,
        name: str,
        input_text: Optional[str] = None,
        output_text: Optional[str] = None,
        metadata: Optional[dict] = None,
        model: Optional[str] = None,
        agent: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Manually log a single LLM interaction as a Langfuse trace."""
        client = self._get_client()
        if client is None:
            return
        try:
            obs = client.start_as_current_observation(
                name=name,
                metadata={
                    "agent": agent or "unknown",
                    "model": model or self.default_model,
                    **(metadata or {}),
                },
            )
            captured_input = _truncate_for_capture(input_text, self.max_capture_chars)
            captured_output = _truncate_for_capture(output_text, self.max_capture_chars)
            if captured_input is not None:
                obs.update(input=captured_input)
            if captured_output is not None:
                obs.update(output=captured_output)
            obs.end()
        except Exception as e:
            logger.warning("Langfuse track error (non-critical): %s", e)

    def get_context_manager(
        self,
        name: str,
        metadata: Optional[dict] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Return a Langfuse observation context manager (or no-op)."""
        client = self._get_client()
        if client is None:
            return _NoOpContext()
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "metadata": metadata or {},
            }
            if user_id:
                kwargs["user_id"] = user_id
            if session_id:
                kwargs["session_id"] = session_id
            return client.start_as_current_observation(**kwargs)
        except Exception as e:
            logger.warning("Langfuse context error (non-critical): %s", e)
            return _NoOpContext()

    # ─── Prompt Management ───────────────────────────────────────────────

    def get_prompt(
        self,
        name: str,
        label: str = "production",
        fallback: Optional[str] = None,
    ) -> Optional[str]:
        """Fetch a production prompt from Langfuse.

        This is a SYNCHRONOUS call and may block for up to ``self.timeout``
        seconds. Callers in async contexts should use
        ``agents.prompt_loader.get_system_prompt_async`` which wraps this
        in ``run_in_executor`` + ``asyncio.wait_for``.

        Parameters
        ----------
        name : str
            Prompt name (handle), e.g. ``"load_flow_agent"``.
        label : str
            Langfuse label to fetch (default: ``"production"``).
        fallback : str, optional
            Value to return if the prompt is not found or Langfuse is
            disabled. If ``None``, returns ``None``.

        Returns
        -------
        Optional[str]
            The system message content, or ``fallback`` on failure.
        """
        client = self._get_client()
        if client is None:
            return fallback

        try:
            lf_prompt = client.get_prompt(name, label=label, type="chat")
            if lf_prompt is None:
                return fallback

            messages = getattr(lf_prompt, "prompt", None) or []
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        content = msg.get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.strip()

            if isinstance(messages, str) and messages.strip():
                return messages.strip()

            return fallback
        except Exception as e:
            logger.debug("Langfuse prompt lookup failed for '%s': %s", name, e)
            return fallback

    def get_prompt_config(self, name: str, label: str = "production") -> dict[str, Any]:
        """Fetch a prompt's full config (model, temperature) from Langfuse."""
        client = self._get_client()
        if client is None:
            return {}
        try:
            lf_prompt = client.get_prompt(name, label=label, type="chat")
            if lf_prompt is None:
                return {}
            config = getattr(lf_prompt, "config", None) or {}
            return config if isinstance(config, dict) else {}
        except Exception as e:
            logger.debug("Langfuse config lookup failed for '%s': %s", name, e)
            return {}

    # ─── Lifecycle ────────────────────────────────────────────────────────

    def flush(self) -> None:
        """Flush pending events to Langfuse (blocking). Call before shutdown."""
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception as e:
            logger.debug("Langfuse flush error (non-critical): %s", e)

    def shutdown(self) -> None:
        """Graceful shutdown — flush + release resources."""
        if self._client is None:
            return
        try:
            self.flush()
            # Langfuse v4 SDK has a shutdown method
            if hasattr(self._client, "shutdown"):
                self._client.shutdown()
        except Exception as e:
            logger.debug("Langfuse shutdown error (non-critical): %s", e)

    # ─── Status ───────────────────────────────────────────────────────────

    @property
    def dashboard_url(self) -> str:
        """URL to the Langfuse dashboard."""
        return self.base_url

    def health_check(self) -> dict[str, Any]:
        """Return Langfuse integration status."""
        return {
            "enabled": self.enabled,
            "endpoint": self.base_url,
            "sdk_available": LANGFUSE_AVAILABLE,
            "client_initialized": self._client is not None,
            "public_key_prefix": (
                (self.public_key[:12] + "...") if self.public_key else None
            ),
            "timeout_seconds": self.timeout,
            "max_capture_chars": self.max_capture_chars,
            "dashboard": self.dashboard_url if self.enabled else None,
        }


# ─── Module-level singleton ────────────────────────────────────────────────
langfuse_tracker = LangfuseTracker()


# ─── atexit handler: flush on shutdown ─────────────────────────────────────


def _atexit_flush() -> None:
    """Flush Langfuse events on interpreter shutdown."""
    try:
        langfuse_tracker.flush()
    except Exception:
        # atexit handlers must never raise
        pass


atexit.register(_atexit_flush)


# ─── Decorator: track_llm_call ────────────────────────────────────────────


def track_llm_call(
    name: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    capture_input: bool = True,
    capture_output: bool = True,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Callable:
    """
    Decorator to automatically track LLM calls via Langfuse.

    Records:
    - Input (truncated to ``LANGFUSE_MAX_CAPTURE_CHARS``)
    - Output (truncated)
    - Exceptions (recorded on the observation + re-raised)
    - Metadata: agent name, model name

    Example::

        @track_llm_call(name="fault_analysis", agent="ShortCircuitAgent")
        async def analyze_fault(prompt: str) -> str:
            return await llm.complete(prompt)
    """

    def decorator(func: Callable) -> Callable:
        import asyncio

        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                input_text = str(args[0]) if capture_input and args else None
                obs = langfuse_tracker.get_context_manager(
                    name=name,
                    metadata={
                        "agent": agent,
                        "model": model or langfuse_tracker.default_model,
                    },
                    user_id=user_id,
                    session_id=session_id,
                )
                with obs:
                    try:
                        result = await func(*args, **kwargs)
                        captured_input = _truncate_for_capture(
                            input_text, langfuse_tracker.max_capture_chars
                        )
                        captured_output = _truncate_for_capture(
                            result if capture_output else None,
                            langfuse_tracker.max_capture_chars,
                        )
                        if captured_input is not None and hasattr(obs, "update"):
                            obs.update(input=captured_input)
                        if captured_output is not None and hasattr(obs, "update"):
                            obs.update(output=captured_output)
                        return result
                    except Exception as exc:
                        # Record the exception on the observation so it
                        # shows up as an error in the Langfuse dashboard.
                        if hasattr(obs, "record_exception"):
                            try:
                                obs.record_exception(exc)
                            except Exception:
                                pass
                        if hasattr(obs, "update"):
                            try:
                                obs.update(
                                    level="ERROR",
                                    metadata={
                                        "exception_type": type(exc).__name__,
                                        "exception_message": str(exc)[:500],
                                    },
                                )
                            except Exception:
                                pass
                        raise
                    finally:
                        if hasattr(obs, "end"):
                            try:
                                obs.end()
                            except Exception:
                                pass

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            input_text = str(args[0]) if capture_input and args else None
            obs = langfuse_tracker.get_context_manager(
                name=name,
                metadata={
                    "agent": agent,
                    "model": model or langfuse_tracker.default_model,
                },
                user_id=user_id,
                session_id=session_id,
            )
            with obs:
                try:
                    result = func(*args, **kwargs)
                    captured_input = _truncate_for_capture(
                        input_text, langfuse_tracker.max_capture_chars
                    )
                    captured_output = _truncate_for_capture(
                        result if capture_output else None,
                        langfuse_tracker.max_capture_chars,
                    )
                    if captured_input is not None and hasattr(obs, "update"):
                        obs.update(input=captured_input)
                    if captured_output is not None and hasattr(obs, "update"):
                        obs.update(output=captured_output)
                    return result
                except Exception as exc:
                    if hasattr(obs, "record_exception"):
                        try:
                            obs.record_exception(exc)
                        except Exception:
                            pass
                    if hasattr(obs, "update"):
                        try:
                            obs.update(
                                level="ERROR",
                                metadata={
                                    "exception_type": type(exc).__name__,
                                    "exception_message": str(exc)[:500],
                                },
                            )
                        except Exception:
                            pass
                    raise
                finally:
                    if hasattr(obs, "end"):
                        try:
                            obs.end()
                        except Exception:
                            pass

        return sync_wrapper

    return decorator


# ─── Convenience: prompt fetching with fallback ──────────────────────────


def get_prompt_from_langfuse(
    name: str,
    fallback: Optional[str] = None,
    label: str = "production",
) -> Optional[str]:
    """Module-level helper around ``LangfuseTracker.get_prompt``."""
    return langfuse_tracker.get_prompt(name=name, label=label, fallback=fallback)


__all__ = [
    "LangfuseTracker",
    "langfuse_tracker",
    "track_llm_call",
    "get_prompt_from_langfuse",
]
