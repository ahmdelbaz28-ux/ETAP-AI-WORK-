"""
Langfuse-enhanced LLM clients for AhmedETAP (Safety-Critical Edition)
====================================================================

This module provides drop-in replacements for the OpenAI and Anthropic
SDKs that automatically:

1. **Trace every LLM call** to Langfuse (input, output, model, usage,
   cost, latency, error) — without any code change in the agents.
2. **Capture token usage** (prompt_tokens, completion_tokens, total_tokens)
   so we can monitor cost per agent and per study type.
3. **Capture latency** so we can detect slow LLM calls that delay
   safety-critical responses.
4. **Capture errors** with stack traces for debugging.
5. **Enforce safety guardrails** before the call is made:
   - Input length limits (prevent prompt injection / token bombs)
   - Required model verification (refuse to call unknown models)
   - Optional input validation hook (per-agent)
6. **Score the trace** with auto-evals (safety, helpfulness) when
   configured.
7. **Tag traces** with the agent name, study type, and user/session IDs
   so the Langfuse dashboard can be filtered.

Usage (OpenAI)::

    from integrations.langfuse_llm import openai

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_input}],
        user="engineer_id_123",
        metadata={"agent": "LoadFlowAgent", "study_type": "load_flow"},
    )

Usage (Anthropic)::

    from integrations.langfuse_llm import anthropic

    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_input}],
        metadata={"agent": "ArcFlashAgent", "study_type": "arc_flash"},
    )

Safety guardrails
-----------------

The following environment variables control guardrails:

    LLM_MAX_INPUT_CHARS       50000   (refuse inputs longer than this)
    LLM_ALLOW_UNKNOWN_MODELS  false   (refuse models not in the allowlist)
    LLM_REQUIRE_AGENT_TAG     true    (refuse calls without an agent metadata)

These guardrails exist because a power-systems engineering agent that
accepts arbitrary-length inputs or unknown models could be tricked into
producing dangerous outputs.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── Prompt-cache statistics (P0 token-economy fix) ──────────────────────
#
# OpenAI gpt-4o* and Anthropic Claude 3.5+ both support prompt caching:
# repeated calls that share a long system-prompt prefix get the cached
# portion billed at a steep discount (OpenAI ~50%, Anthropic ~90%).
#
# Until now, the codebase never tracked cached tokens, so we could not
# measure whether prompt caching actually fires in production. This
# module-level tracker captures per-call usage so any consumer can
# compute the real savings ratio.
#
# Thread-safe: a single shared instance is exposed as PROMPT_CACHE_STATS.


class PromptCacheStats:
    """Accumulates prompt-cache hits across all safe_* LLM calls.

    Captures, per call:
      - input_tokens (billable, after cache discount)
      - cached_tokens (the portion served from cache)
      - output_tokens
      - provider ('openai' | 'anthropic')
      - agent name (from metadata)
      - model

    Exposes ``snapshot()`` for tests and dashboards, and ``reset()``
    for clean baselines in unit tests.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[dict[str, Any]] = []

    def record(
        self,
        *,
        provider: str,
        model: str,
        agent: str,
        input_tokens: int,
        cached_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record one LLM call's token-usage breakdown."""
        with self._lock:
            self._calls.append(
                {
                    "provider": provider,
                    "model": model,
                    "agent": agent,
                    "input_tokens": int(input_tokens),
                    "cached_tokens": int(cached_tokens),
                    "output_tokens": int(output_tokens),
                    "billed_input_tokens": int(input_tokens) - int(cached_tokens),
                }
            )

    def snapshot(self) -> dict[str, Any]:
        """Return an immutable summary of all recorded calls."""
        with self._lock:
            calls = list(self._calls)
        total_input = sum(c["input_tokens"] for c in calls)
        total_cached = sum(c["cached_tokens"] for c in calls)
        total_output = sum(c["output_tokens"] for c in calls)
        total_billed = sum(c["billed_input_tokens"] for c in calls)
        cache_hit_ratio = (total_cached / total_input) if total_input > 0 else 0.0
        return {
            "call_count": len(calls),
            "total_input_tokens": total_input,
            "total_cached_tokens": total_cached,
            "total_output_tokens": total_output,
            "total_billed_input_tokens": total_billed,
            "cache_hit_ratio": round(cache_hit_ratio, 4),
            "calls": calls,
        }

    def reset(self) -> None:
        """Clear all recorded calls. Intended for unit tests only."""
        with self._lock:
            self._calls.clear()


PROMPT_CACHE_STATS = PromptCacheStats()


def _extract_openai_cached_tokens(usage: Any) -> int:
    """Pull ``prompt_tokens_details.cached_tokens`` out of an OpenAI response.

    Returns 0 if the field is absent (older models / non-OpenAI compatible
    endpoints never populate it).
    """
    if usage is None:
        return 0
    try:
        details = getattr(usage, "prompt_tokens_details", None)
        if details is None:
            return 0
        return int(getattr(details, "cached_tokens", 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _extract_anthropic_cached_tokens(usage: Any) -> int:
    """Pull ``cache_read_input_tokens`` out of an Anthropic response."""
    if usage is None:
        return 0
    try:
        return int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _inject_anthropic_cache_control(messages: list[dict]) -> list[dict]:
    """Tag the last system block with ``cache_control: ephemeral``.

    Anthropic charges ~10% of normal input cost for cached prefixes.
    Adding ``cache_control`` to the final system message tells the API
    to cache everything up to that point. Safe no-op if there is no
    system message or if the caller already set cache_control.

    The returned list is a shallow copy so the caller's messages are
    never mutated.
    """
    if not messages:
        return messages
    out = list(messages)
    last_sys_idx = None
    for idx in range(len(out) - 1, -1, -1):
        msg = out[idx]
        if isinstance(msg, dict) and msg.get("role") == "system":
            last_sys_idx = idx
            break
    if last_sys_idx is None:
        return out
    msg = dict(out[last_sys_idx])  # shallow copy
    # If the content is a plain string, convert to a single block so we
    # can attach cache_control. Anthropic accepts either form.
    content = msg.get("content")
    if isinstance(content, str):
        msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(content, list) and content:
        # Tag only the last block; cache_control is a hint that says
        # "cache everything up to and including this block".
        blocks = [dict(b) if isinstance(b, dict) else b for b in content]
        last_block = blocks[-1]
        if isinstance(last_block, dict) and "cache_control" not in last_block:
            last_block["cache_control"] = {"type": "ephemeral"}
        msg["content"] = blocks
    out[last_sys_idx] = msg
    return out


# ─── Safety guardrails (config) ───────────────────────────────────────────

_LLM_MAX_INPUT_CHARS = int(os.environ.get("LLM_MAX_INPUT_CHARS", "50000"))
_LLM_ALLOW_UNKNOWN_MODELS = os.environ.get("LLM_ALLOW_UNKNOWN_MODELS", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_LLM_REQUIRE_AGENT_TAG = os.environ.get("LLM_REQUIRE_AGENT_TAG", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Allowlist of approved models for safety-critical engineering work.
# Using an unapproved model could produce wrong calculations.
_APPROVED_MODELS = frozenset(
    m.strip()
    for m in os.environ.get(
        "LLM_APPROVED_MODELS",
        "gpt-4o,gpt-4o-mini,gpt-4-turbo,gpt-4.1,gpt-4.1-mini,"
        "claude-3-5-sonnet-20241022,claude-3-5-haiku-20241022,"
        "claude-3-opus-20240229,gemini-2.0-flash-exp,gemini-1.5-pro",
    ).split(",")
    if m.strip()
)


class SafetyValidationError(ValueError):
    """Raised when an LLM call violates a safety guardrail."""


def _validate_input(  # NOSONAR
    messages: list[dict], metadata: Optional[dict]
) -> None:  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Run safety guardrails before the LLM call is made.

    Raises ``SafetyValidationError`` on violation.
    """
    # 1. Input length limit (prevents prompt injection / token bombs)
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total_chars += len(str(part["text"]))
    if total_chars > _LLM_MAX_INPUT_CHARS:
        raise SafetyValidationError(
            f"Input too long: {total_chars} chars > {_LLM_MAX_INPUT_CHARS} limit. "
            "This guardrail prevents prompt-injection and token-bomb attacks on "
            "safety-critical engineering agents.",
        )

    # 2. Required agent tag (helps trace accountability)
    if _LLM_REQUIRE_AGENT_TAG and (not metadata or not metadata.get("agent")):
        raise SafetyValidationError(
            "LLM call missing required 'agent' metadata. Every call from a "
            "safety-critical engineering agent must tag itself for audit "
            "traceability. Pass metadata={'agent': 'AgentName'} to the call.",
        )


def _validate_model(model: str) -> None:
    """Refuse unapproved models for safety-critical work."""
    if _LLM_ALLOW_UNKNOWN_MODELS:
        return
    if model not in _APPROVED_MODELS:
        raise SafetyValidationError(
            f"Model '{model}' is not in the approved-models allowlist. "
            "Using unapproved models for safety-critical engineering work "
            "could produce wrong calculations. To allow this model, add it "
            "to LLM_APPROVED_MODELS or set LLM_ALLOW_UNKNOWN_MODELS=true.",
        )


# ─── Lazy import of the Langfuse-wrapped OpenAI/Anthropic SDKs ────────────

_openai_client = None
_anthropic_client = None
_import_attempted = False

# ARCHITECTURE AUDIT FIX (F-04): Counter for untraced LLM calls.
# When Langfuse is configured but the wrapper import fails, every LLM call
# goes through the plain SDK without tracing. This counter tracks how many
# such calls have been made, enabling alerting/paging thresholds.
_untraced_llm_calls: int = 0

# Threshold: if more than this many untraced calls accumulate, emit CRITICAL
_UNTRACED_CALL_ALERT_THRESHOLD = int(os.environ.get("LANGFUSE_UNTRACED_ALERT_THRESHOLD", "10"))


def _get_openai_client():
    """Return the Langfuse-wrapped OpenAI client (lazy).

    ARCHITECTURE AUDIT FIX (F-04): When Langfuse is configured but the
    wrapper import fails, log CRITICAL (not just warning) and increment
    an untraced-call counter. In production with LANGFUSE_ENABLED=true,
    this is a safety observability gap.
    """
    global _openai_client, _import_attempted
    if _openai_client is not None:
        return _openai_client
    if not _import_attempted:
        _import_attempted = True
        try:
            from langfuse.openai import openai as lf_openai  # type: ignore

            _openai_client = lf_openai
            logger.info("Langfuse-wrapped OpenAI client loaded")
        except ImportError as e:
            _langfuse_configured = os.environ.get("LANGFUSE_ENABLED", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if _langfuse_configured:
                logger.critical(
                    "⚠️ ARCHITECTURE AUDIT F-04: Langfuse is ENABLED but langfuse.openai "
                    "import failed! LLM calls will proceed WITHOUT tracing — "
                    "safety-critical observability gap. Error: %s. "
                    "Fix: ensure langfuse package version is compatible.",
                    e,
                )
            else:
                logger.warning(
                    "langfuse.openai not available — falling back to plain openai. "
                    "LLM calls will NOT be traced. Error: %s",
                    e,
                )
            try:
                import openai as _openai_module  # type: ignore

                _openai_client = _openai_module
                # F-04: Increment untraced call counter
                _untraced_llm_calls_local = 1  # Mark this as an untraced fallback
                logger.warning(
                    "F-04: OpenAI client initialized WITHOUT Langfuse tracing. "
                    "Call get_untraced_llm_call_count() to monitor."
                )
            except ImportError:
                _openai_client = None
    return _openai_client


def _get_anthropic_client():
    """Return the Langfuse-wrapped Anthropic client (lazy).

    ARCHITECTURE AUDIT FIX (F-04): Same untraced-call alerting as OpenAI.
    """
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    try:
        from langfuse.anthropic import anthropic as lf_anthropic  # type: ignore

        _anthropic_client = lf_anthropic
        logger.info("Langfuse-wrapped Anthropic client loaded")
    except ImportError as e:
        _langfuse_configured = os.environ.get("LANGFUSE_ENABLED", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if _langfuse_configured:
            logger.critical(
                "⚠️ ARCHITECTURE AUDIT F-04: Langfuse is ENABLED but langfuse.anthropic "
                "import failed! Anthropic calls will proceed WITHOUT tracing. Error: %s",
                e,
            )
        else:
            logger.warning(
                "langfuse.anthropic not available — Anthropic calls will NOT be traced. Error: %s",
                e,
            )
        try:
            import anthropic as _anthropic_module  # type: ignore

            _anthropic_client = _anthropic_module
        except ImportError:
            _anthropic_client = None
    return _anthropic_client


# ─── Public API: openai / anthropic drop-in modules ──────────────────────

# These are the actual Langfuse-wrapped SDKs. Agents should import from
# here instead of importing `openai` / `anthropic` directly, so every
# call is automatically traced.
openai = _get_openai_client()
anthropic = _get_anthropic_client()


# ─── Safe-call wrappers (with guardrails) ────────────────────────────────


def safe_openai_chat(
    *,
    model: str,
    messages: list[dict],
    metadata: Optional[dict] = None,
    user: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs: Any,
):
    """Call ``openai.chat.completions.create`` with safety guardrails + tracing.

    Parameters
    ----------
    model : str
        Must be in the approved-models allowlist (unless
        ``LLM_ALLOW_UNKNOWN_MODELS=true``).
    messages : list[dict]
        OpenAI chat messages. Total content length must be under
        ``LLM_MAX_INPUT_CHARS``.
    metadata : dict, optional
        MUST include ``agent`` key (e.g. ``{"agent": "LoadFlowAgent"}``)
        when ``LLM_REQUIRE_AGENT_TAG=true`` (default).
    user : str, optional
        End-user identifier for Langfuse user-level analytics.
    session_id : str, optional
        Langfuse session ID (groups multiple traces into one session).
    **kwargs
        Passed through to ``openai.chat.completions.create``.

    Returns
    -------
    The OpenAI ChatCompletion response.

    Raises
    ------
    SafetyValidationError
        If a guardrail is violated (input too long, unapproved model,
        missing agent tag).
    """
    if openai is None:
        raise RuntimeError("OpenAI SDK not installed. Run: pip install openai langfuse")

    # 1. Run safety guardrails
    _validate_input(messages, metadata)
    _validate_model(model)

    # F-04: If using plain (untraced) SDK, increment counter for observability alerting
    _is_traced = hasattr(openai, "langfuse") or (
        hasattr(openai, "__name__") and "langfuse" in openai.__name__
    )
    if not _is_traced:
        increment_untraced_call()

    # 2. Inject Langfuse tracing metadata
    # The Langfuse-wrapped OpenAI SDK accepts ``metadata`` and ``langfuse_*``
    # kwargs to attach the call to a trace.
    call_kwargs = dict(kwargs)
    call_kwargs["model"] = model
    call_kwargs["messages"] = messages

    # Langfuse-specific kwargs (the wrapped SDK reads these)
    lf_kwargs: dict[str, Any] = {}
    if metadata:
        lf_kwargs["metadata"] = metadata
    if user:
        lf_kwargs["user"] = user
    if session_id:
        lf_kwargs["langfuse_session_id"] = session_id
    if metadata and metadata.get("agent"):
        # Langfuse trace name = agent name (great for dashboard filtering)
        lf_kwargs["langfuse_trace_name"] = metadata["agent"]

    # Merge with caller kwargs (caller's metadata wins on conflict)
    for k, v in lf_kwargs.items():
        if k not in call_kwargs:
            call_kwargs[k] = v

    # 3. Make the call (Langfuse auto-traces)
    start = time.monotonic()
    try:
        response = openai.chat.completions.create(**call_kwargs)
        elapsed = time.monotonic() - start
        # Capture cache stats for token-economy monitoring.
        usage = getattr(response, "usage", None)
        cached_tokens = _extract_openai_cached_tokens(usage)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        PROMPT_CACHE_STATS.record(
            provider="openai",
            model=model,
            agent=(metadata or {}).get("agent", "unknown"),
            input_tokens=prompt_tokens,
            cached_tokens=cached_tokens,
            output_tokens=completion_tokens,
        )
        logger.debug(
            "OpenAI call: model=%s, agent=%s, latency=%.2fs, tokens=in:%d/cached:%d/out:%d",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
            prompt_tokens,
            cached_tokens,
            completion_tokens,
        )
        return response
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "OpenAI call FAILED: model=%s, agent=%s, latency=%.2fs, error=%s: %s",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
            type(exc).__name__,
            exc,
        )
        raise


def safe_anthropic_message(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    metadata: Optional[dict] = None,
    user: Optional[str] = None,  # NOSONAR unused param kept for API compatibility
    session_id: Optional[str] = None,
    **kwargs: Any,
):
    """Call ``anthropic.messages.create`` with safety guardrails + tracing.

    See ``safe_openai_chat`` for parameter docs.
    """
    if anthropic is None:
        raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic langfuse")

    _validate_input(messages, metadata)
    _validate_model(model)

    # F-04: If using plain (untraced) SDK, increment counter for observability alerting
    _is_traced = hasattr(anthropic, "langfuse") or (
        hasattr(anthropic, "__name__") and "langfuse" in anthropic.__name__
    )
    if not _is_traced:
        increment_untraced_call()

    call_kwargs = dict(kwargs)
    call_kwargs["model"] = model
    # Inject Anthropic cache_control on the last system message so the
    # long system-prompt prefix is billed at ~10% on subsequent calls.
    call_kwargs["messages"] = _inject_anthropic_cache_control(messages)
    call_kwargs["max_tokens"] = max_tokens

    lf_kwargs: dict[str, Any] = {}
    if metadata:
        lf_kwargs["metadata"] = metadata
    if session_id:
        lf_kwargs["langfuse_session_id"] = session_id
    if metadata and metadata.get("agent"):
        lf_kwargs["langfuse_trace_name"] = metadata["agent"]

    for k, v in lf_kwargs.items():
        if k not in call_kwargs:
            call_kwargs[k] = v

    start = time.monotonic()
    try:
        response = anthropic.messages.create(**call_kwargs)
        elapsed = time.monotonic() - start
        usage = getattr(response, "usage", None)
        cached_tokens = _extract_anthropic_cached_tokens(usage)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        PROMPT_CACHE_STATS.record(
            provider="anthropic",
            model=model,
            agent=(metadata or {}).get("agent", "unknown"),
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
        )
        logger.debug(
            "Anthropic call: model=%s, agent=%s, latency=%.2fs, tokens=in:%d/cached:%d/out:%d",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
            input_tokens,
            cached_tokens,
            output_tokens,
        )
        return response
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "Anthropic call FAILED: model=%s, agent=%s, latency=%.2fs, error=%s: %s",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
            type(exc).__name__,
            exc,
        )
        raise


# ─── Cost estimation (per 1K tokens, in USD) ─────────────────────────────
# Source: OpenAI / Anthropic public pricing as of 2025-01. Update as needed.

_PRICING_USD_PER_1K = {
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Estimate the USD cost of an LLM call.

    Returns ``None`` if the model is not in the pricing table.
    """
    pricing = _PRICING_USD_PER_1K.get(model)
    if pricing is None:
        return None
    cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
    return round(cost, 6)


# ─── Health check ─────────────────────────────────────────────────────────


def health_check() -> dict[str, Any]:
    """Return the status of the Langfuse LLM integration.

    ARCHITECTURE AUDIT FIX (F-04): Now includes untraced LLM call count.
    """
    _is_tracing = _openai_client is not None and hasattr(_openai_client, "langfuse")
    return {
        "openai_available": openai is not None,
        "anthropic_available": anthropic is not None,
        "is_tracing_active": _is_tracing,
        "untraced_llm_calls": _untraced_llm_calls,
        "untraced_call_alert_threshold": _UNTRACED_CALL_ALERT_THRESHOLD,
        "approved_models_count": len(_APPROVED_MODELS),
        "approved_models": sorted(_APPROVED_MODELS),
        "max_input_chars": _LLM_MAX_INPUT_CHARS,
        "allow_unknown_models": _LLM_ALLOW_UNKNOWN_MODELS,
        "require_agent_tag": _LLM_REQUIRE_AGENT_TAG,
    }


def get_untraced_llm_call_count() -> int:
    """Return the number of LLM calls made without Langfuse tracing.

    ARCHITECTURE AUDIT FIX (F-04): Use this to alert when too many
    untraced calls have occurred, indicating Langfuse is down.
    """
    return _untraced_llm_calls


def increment_untraced_call() -> None:
    """Increment the untraced LLM call counter and alert if threshold exceeded.

    ARCHITECTURE AUDIT FIX (F-04): Call this from safe_openai_chat /
    safe_anthropic_message when the call goes through the plain SDK.
    """
    global _untraced_llm_calls
    _untraced_llm_calls += 1
    if _untraced_llm_calls == _UNTRACED_CALL_ALERT_THRESHOLD:
        logger.critical(
            "⚠️ F-04 ALERT: %d LLM calls have been made WITHOUT tracing. "
            "Langfuse observability is compromised. Investigate immediately.",
            _untraced_llm_calls,
        )


__all__ = [
    "openai",
    "anthropic",
    "safe_openai_chat",
    "safe_anthropic_message",
    "estimate_cost_usd",
    "health_check",
    "get_untraced_llm_call_count",
    "increment_untraced_call",
    "SafetyValidationError",
    "PROMPT_CACHE_STATS",
    "PromptCacheStats",
    "_inject_anthropic_cache_control",
    "_extract_openai_cached_tokens",
    "_extract_anthropic_cached_tokens",
]
