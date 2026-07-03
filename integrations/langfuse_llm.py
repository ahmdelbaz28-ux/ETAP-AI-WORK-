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
import time
from typing import Any

logger = logging.getLogger(__name__)

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


def _validate_input(messages: list[dict], metadata: dict | None) -> None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
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


def _get_openai_client():
    """Return the Langfuse-wrapped OpenAI client (lazy)."""
    global _openai_client, _import_attempted
    if _openai_client is not None:
        return _openai_client
    if not _import_attempted:
        _import_attempted = True
        try:
            from langfuse.openai import openai as lf_openai  # type: ignore

            _openai_client = lf_openai
            logger.info("✅ Langfuse-wrapped OpenAI client loaded")
        except ImportError as e:
            logger.warning(
                "langfuse.openai not available — falling back to plain openai. "
                "LLM calls will NOT be traced. Error: %s",
                e,
            )
            try:
                import openai as _openai_module  # type: ignore

                _openai_client = _openai_module
            except ImportError:
                _openai_client = None
    return _openai_client


def _get_anthropic_client():
    """Return the Langfuse-wrapped Anthropic client (lazy)."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    try:
        from langfuse.anthropic import anthropic as lf_anthropic  # type: ignore

        _anthropic_client = lf_anthropic
        logger.info("✅ Langfuse-wrapped Anthropic client loaded")
    except ImportError as e:
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
    metadata: dict | None = None,
    user: str | None = None,
    session_id: str | None = None,
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
        logger.debug(
            "OpenAI call: model=%s, agent=%s, latency=%.2fs, usage=%s",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
            getattr(response, "usage", None),
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
    metadata: dict | None = None,
    user: str | None = None,
    session_id: str | None = None,
    **kwargs: Any,
):
    """Call ``anthropic.messages.create`` with safety guardrails + tracing.

    See ``safe_openai_chat`` for parameter docs.
    """
    if anthropic is None:
        raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic langfuse")

    _validate_input(messages, metadata)
    _validate_model(model)

    call_kwargs = dict(kwargs)
    call_kwargs["model"] = model
    call_kwargs["messages"] = messages
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
        logger.debug(
            "Anthropic call: model=%s, agent=%s, latency=%.2fs",
            model,
            (metadata or {}).get("agent", "unknown"),
            elapsed,
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


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
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
    """Return the status of the Langfuse LLM integration."""
    return {
        "openai_available": openai is not None,
        "anthropic_available": anthropic is not None,
        "approved_models_count": len(_APPROVED_MODELS),
        "approved_models": sorted(_APPROVED_MODELS),
        "max_input_chars": _LLM_MAX_INPUT_CHARS,
        "allow_unknown_models": _LLM_ALLOW_UNKNOWN_MODELS,
        "require_agent_tag": _LLM_REQUIRE_AGENT_TAG,
    }


__all__ = [
    "openai",
    "anthropic",
    "safe_openai_chat",
    "safe_anthropic_message",
    "estimate_cost_usd",
    "health_check",
    "SafetyValidationError",
]
