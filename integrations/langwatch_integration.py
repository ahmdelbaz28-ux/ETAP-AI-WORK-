"""
LangWatch Integration for AhmedETAP
Provides LLM observability, tracing, and monitoring for all AI agent calls.

Usage:
    from integrations.langwatch_integration import langwatch_tracker, track_llm_call

    @track_llm_call(name="etap_expert_response")
    async def my_agent_function(prompt: str) -> str:
        ...
"""

import os
import functools
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ─── LangWatch SDK (optional dependency) ─────────────────────────────────────
try:
    import langwatch

    LANGWATCH_AVAILABLE = True
    logger.info("LangWatch SDK loaded successfully")
except ImportError:
    LANGWATCH_AVAILABLE = False
    logger.warning("LangWatch SDK not installed. Run: pip install langwatch")


class LangWatchTracker:
    """
    Central LangWatch observability tracker for AhmedETAP.
    Wraps all LLM calls with automatic tracing and metrics.
    """

    def __init__(self):
        self.api_key = os.getenv("LANGWATCH_API_KEY", "")
        self.project = os.getenv("LANGWATCH_PROJECT", "AhmedETAP")
        self.enabled = bool(self.api_key and LANGWATCH_AVAILABLE)

        if self.enabled:
            langwatch.api_key = self.api_key
            langwatch.endpoint = os.getenv("LANGWATCH_ENDPOINT", "https://app.langwatch.ai")
            logger.info(f"✅ LangWatch initialized — project: {self.project}")
        else:
            if not self.api_key:
                logger.info("LangWatch disabled: LANGWATCH_API_KEY not set")
            elif not LANGWATCH_AVAILABLE:
                logger.info("LangWatch disabled: SDK not installed")

    def track(
        self,
        name: str,
        input_text: Optional[str] = None,
        output_text: Optional[str] = None,
        metadata: Optional[dict] = None,
        model: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> None:
        """Manually log a single LLM interaction."""
        if not self.enabled:
            return
        try:
            trace = langwatch.trace(
                name=name,
                metadata={
                    "project": self.project,
                    "agent": agent or "unknown",
                    "model": model or "unknown",
                    **(metadata or {}),
                },
            )
            if input_text:
                trace.update(input=input_text)
            if output_text:
                trace.update(output=output_text)
            trace.send()
        except Exception as e:
            logger.warning(f"LangWatch track error (non-critical): {e}")

    def get_context_manager(self, name: str, **kwargs):
        """Return a LangWatch trace context manager."""
        if not self.enabled or not LANGWATCH_AVAILABLE:
            return _NoOpContext()
        try:
            return langwatch.trace(name=name, **kwargs)
        except Exception as e:
            logger.warning(f"LangWatch context error (non-critical): {e}")
            return _NoOpContext()

    @property
    def dashboard_url(self) -> str:
        """URL to the LangWatch dashboard."""
        return "https://app.langwatch.ai"

    def health_check(self) -> dict:
        """Return LangWatch integration status."""
        return {
            "enabled": self.enabled,
            "project": self.project,
            "sdk_available": LANGWATCH_AVAILABLE,
            "dashboard": self.dashboard_url if self.enabled else None,
        }


class _NoOpContext:
    """Silent no-op context manager when LangWatch is disabled."""
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def update(self, **kwargs): pass
    def send(self): pass


# ─── Module-level singleton ───────────────────────────────────────────────────
langwatch_tracker = LangWatchTracker()


def track_llm_call(
    name: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable:
    """
    Decorator to automatically track LLM calls via LangWatch.

    Example:
        @track_llm_call(name="fault_analysis", agent="ShortCircuitAgent")
        async def analyze_fault(prompt: str) -> str:
            return await llm.complete(prompt)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            input_text = str(args[0]) if capture_input and args else None
            with langwatch_tracker.get_context_manager(
                name=name,
                metadata={"agent": agent, "model": model},
            ):
                result = await func(*args, **kwargs)
                if capture_output and langwatch_tracker.enabled:
                    pass  # output captured by SDK context
                return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with langwatch_tracker.get_context_manager(
                name=name,
                metadata={"agent": agent, "model": model},
            ):
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
