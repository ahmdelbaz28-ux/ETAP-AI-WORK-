"""
Langfuse Integration for AhmedETAP
==================================

Provides LLM observability, tracing, and prompt management via Langfuse
Cloud (or self-hosted Langfuse). Replaces the LangWatch integration with
a service whose free Hobby plan supports an UNLIMITED number of prompts.

This module mirrors the public API of ``integrations.langwatch_integration``
so it can be used as a drop-in replacement:

    from integrations.langfuse_integration import langfuse_tracker, track_llm_call

    @track_llm_call(name="etap_expert_response", agent="EtapExpertAgent")
    async def my_agent_function(prompt: str) -> str:
        ...

It also offers:

- ``get_prompt(name)`` → fetch a production prompt from Langfuse with
  local-YAML fallback (used by ``agents/prompt_loader.py``).
- ``flush()`` → blocking flush of pending traces (call before shutdown).

Langfuse v4 SDK note
--------------------
Langfuse v4 deprecated the legacy ``langwatch.trace()``-style API in
favour of native OpenTelemetry spans. This module uses
``Langfuse.start_as_current_observation()`` which returns an OTel-based
span that supports ``__enter__`` / ``__exit__`` and ``.update()``.

Environment variables:

    LANGFUSE_PUBLIC_KEY     pk-lf-...
    LANGFUSE_SECRET_KEY     sk-lf-...
    LANGFUSE_BASE_URL       https://cloud.langfuse.com (default)
    LANGFUSE_DEFAULT_MODEL  gpt-4o (default)
    LANGFUSE_ENABLED        "false" to explicitly disable
"""

from __future__ import annotations

import functools
import logging
import os
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

    # Langfuse v4 observation-like API (so callers can use `.update()` / `.end()`)
    def update(self, *args, **kwargs):
        return self

    def end(self, *args, **kwargs):
        pass


def _env_truthy(var: str, default: bool = False) -> bool:
    val = os.environ.get(var)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


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

        # Explicit disable flag takes precedence
        self.enabled = (
            LANGFUSE_AVAILABLE
            and bool(self.public_key)
            and bool(self.secret_key)
            and _env_truthy("LANGFUSE_ENABLED", default=True)
        )

        self._client: Optional[Langfuse] = None
        if self.enabled:
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.base_url,
                )
                logger.info(
                    "✅ Langfuse initialized — endpoint: %s, public_key: %s...",
                    self.base_url,
                    self.public_key[:12],
                )
            except Exception as e:
                logger.warning("Langfuse client init failed: %s", e)
                self.enabled = False
                self._client = None
        else:
            if not LANGFUSE_AVAILABLE:
                logger.info("Langfuse disabled: SDK not installed")
            elif not self.public_key or not self.secret_key:
                logger.info("Langfuse disabled: credentials not set")
            elif not _env_truthy("LANGFUSE_ENABLED", default=True):
                logger.info("Langfuse disabled via LANGFUSE_ENABLED=false")

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
        """Manually log a single LLM interaction as a Langfuse trace.

        Uses ``start_as_current_observation`` which is the Langfuse v4
        native API for creating a top-level observation (trace + span).
        """
        if not self.enabled or self._client is None:
            return
        try:
            # In Langfuse v4, a top-level observation is created via
            # ``start_as_current_observation`` with name + metadata. We
            # then update it with input/output and end it.
            obs = self._client.start_as_current_observation(
                name=name,
                metadata={
                    "agent": agent or "unknown",
                    "model": model or self.default_model,
                    **(metadata or {}),
                },
            )
            if input_text is not None:
                obs.update(input=input_text)
            if output_text is not None:
                obs.update(output=output_text)
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
        """Return a Langfuse observation context manager.

        Returns a Langfuse v4 observation (OTel-based) that supports
        ``__enter__`` / ``__exit__`` / ``.update()`` / ``.end()``.

        Falls back to a no-op context manager if disabled or on error.
        """
        if not self.enabled or self._client is None:
            return _NoOpContext()
        try:
            # ``start_as_current_observation`` returns a context-manager
            # observation in Langfuse v4.
            kwargs: dict[str, Any] = {
                "name": name,
                "metadata": metadata or {},
            }
            if user_id:
                kwargs["user_id"] = user_id
            if session_id:
                kwargs["session_id"] = session_id
            return self._client.start_as_current_observation(**kwargs)
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
        if not self.enabled or self._client is None:
            return fallback

        try:
            lf_prompt = self._client.get_prompt(name, label=label, type="chat")
            if lf_prompt is None:
                return fallback

            # Langfuse ChatPrompt client exposes `.prompt` as a list of
            # {role, content} dicts
            messages = getattr(lf_prompt, "prompt", None) or []
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        content = msg.get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.strip()

            # Some Langfuse versions return a `.prompt` string for text prompts
            if isinstance(messages, str) and messages.strip():
                return messages.strip()

            return fallback
        except Exception as e:
            logger.debug("Langfuse prompt lookup failed for '%s': %s", name, e)
            return fallback

    def get_prompt_config(self, name: str, label: str = "production") -> dict[str, Any]:
        """Fetch a prompt's full config (model, temperature) from Langfuse.

        Returns an empty dict if unavailable.
        """
        if not self.enabled or self._client is None:
            return {}
        try:
            lf_prompt = self._client.get_prompt(name, label=label, type="chat")
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
        if not self.enabled or self._client is None:
            return
        try:
            self._client.flush()
        except Exception as e:
            logger.debug("Langfuse flush error (non-critical): %s", e)

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
            "public_key_prefix": (self.public_key[:12] + "...") if self.public_key else None,
            "dashboard": self.dashboard_url if self.enabled else None,
        }


# ─── Module-level singleton ────────────────────────────────────────────────
langfuse_tracker = LangfuseTracker()


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

    Mirrors the signature of ``integrations.langwatch_integration.track_llm_call``
    so it can be used as a drop-in replacement.

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
                        if input_text is not None and hasattr(obs, "update"):
                            obs.update(input=input_text)
                        if capture_output and hasattr(obs, "update"):
                            obs.update(output=str(result))
                        return result
                    finally:
                        if hasattr(obs, "end"):
                            obs.end()

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
                    if input_text is not None and hasattr(obs, "update"):
                        obs.update(input=input_text)
                    if capture_output and hasattr(obs, "update"):
                        obs.update(output=str(result))
                    return result
                finally:
                    if hasattr(obs, "end"):
                        obs.end()

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
