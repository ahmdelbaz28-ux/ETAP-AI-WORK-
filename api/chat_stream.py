"""
api/chat_stream.py — Server-side LLM chat streaming (P4b).

``POST /api/v1/chat/stream`` accepts ``{session_id, messages[],
provider?, model?}`` (NO API keys) and replies with a unified SSE envelope::

    event: token  data: {"delta": "..."}    per generated chunk
    event: done   data: {...}               on successful completion
    event: error  data: {"code", "message"} on failure

Security invariants:
1. Keys never reach the browser — schema uses ``extra="forbid"`` so any
   client-supplied credential field is rejected with 422; keys are read
   exclusively from server env (OPENAI_API_KEY / ANTHROPIC_API_KEY).
2. Provider allowlist — only OpenAI-compatible and Anthropic adapters,
   reusing ui/api/llm-proxy.js wire patterns (SSE framing, ``[DONE]``
   sentinel, Anthropic ``content_block_delta``).
3. No sensitive leakage — upstream failures are truncated + redacted
   (secret-shaped strings AND configured env credential values) before
   being emitted; sanitized details go to server logs only.
4. Auth required — Bearer access token via get_current_user_from_header
   (mirrors the P4a agent-exec path).
5. Per-user rate limiting — bounded sliding window (platform rule).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import AsyncIterator, Dict, List, Optional
from typing_extensions import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import CurrentUser, get_current_user_from_header

logger = logging.getLogger("api.chat_stream")

SSE_DATA_PREFIX = "data:"

router = APIRouter(prefix="/api/v1/chat", tags=["chat-stream"])

# ─── Configuration ─────────────────────────────────────────────────────────
MAX_MESSAGES = 64
MAX_MESSAGE_CHARS = 32_000
MAX_SESSION_ID_CHARS = 128
MAX_ERROR_ECHO_CHARS = 300

RATE_LIMIT_REQUESTS = 30  # chat streams per...
RATE_LIMIT_WINDOW_SECONDS = 60.0  # ...60 s sliding window per user
MAX_RATE_BUCKETS = 4096  # bounded per-user bucket map (self-pruning)

UPSTREAM_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

SUPPORTED_PROVIDERS = ("openai", "anthropic", "gemini")

# Environment variables holding server-side provider configuration.
# NAMES are safe to expose; VALUES never leave the box.
PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
PROVIDER_BASE_URL_ENV = {
    "openai": "OPENAI_BASE_URL",
    "anthropic": "ANTHROPIC_BASE_URL",
    "gemini": "GEMINI_BASE_URL",
}
PROVIDER_DEFAULT_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
PROVIDER_MODEL_ENV = {
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
    "gemini": "GEMINI_MODEL",
}
PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-1.5-flash",
}

ANTHROPIC_VERSION_HEADER = "2023-06-01"
CONTENT_TYPE_JSON = "application/json"

# Secret-shaped strings inside upstream bodies (defence-in-depth on top of
# exact env-value redaction in sanitize_error_text).
_SECRET_SHAPE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{6,}|xox[a-zA-Z]-[A-Za-z0-9-]{6,}|AKIA[0-9A-Z]{16})"
)


# ─── Errors ────────────────────────────────────────────────────────────────
class UpstreamProviderError(Exception):
    """Upstream LLM provider returned a non-OK / in-band error response."""

    def __init__(self, upstream_status: int, body_text: str) -> None:
        super().__init__(body_text)
        self.upstream_status = upstream_status
        self.body_text = body_text


# ─── Request models ────────────────────────────────────────────────────────
class ChatMessageIn(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatStreamRequest(BaseModel):
    """Wire contract for POST /api/v1/chat/stream.

    ``extra="forbid"`` is deliberate SECURITY: a request carrying any
    credential-ish extra field (apiKey / api_key / headers ...) is rejected
    outright instead of silently ignored, making the "no client keys ever"
    invariant observable and testable.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_CHARS)
    messages: List[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    provider: Optional[str] = Field(default=None, pattern="^(openai|anthropic|gemini)$")
    model: Optional[str] = Field(default=None, min_length=1, max_length=128)


class ProviderConfig(BaseModel):
    """Resolved server-side provider configuration (never serialized out)."""

    id: str
    api_key: str
    base_url: str
    model: str


def resolve_provider_config(provider: Optional[str], model: Optional[str]) -> ProviderConfig:
    """Build the provider config from SERVER-SIDE environment only.

    Raises 503 (stable error code in ``detail``) when the requested — or,
    without an explicit request, any — provider lacks a configured key.
    Never guesses; never falls back to client-supplied credentials.
    """
    candidates = (provider,) if provider else SUPPORTED_PROVIDERS
    chosen: Optional[ProviderConfig] = None
    missing: List[str] = []
    for pid in candidates:
        api_key = os.environ.get(PROVIDER_API_KEY_ENV[pid], "").strip()
        if not api_key:
            missing.append(pid)
            continue
        chosen = ProviderConfig(
            id=pid,
            api_key=api_key,
            base_url=(
                os.environ.get(PROVIDER_BASE_URL_ENV[pid], "").strip().rstrip("/")
                or PROVIDER_DEFAULT_BASE_URL[pid]
            ),
            model=(
                (model or "").strip()
                or os.environ.get(PROVIDER_MODEL_ENV[pid], "").strip()
                or PROVIDER_DEFAULT_MODEL[pid]
            ),
        )
        break

    if chosen is None:
        if provider:
            code = "PROVIDER_NOT_CONFIGURED"
            message = "Requested LLM provider is not configured on the server."
        else:
            code = "NO_LLM_PROVIDER_CONFIGURED"
            message = (
                "No LLM provider is configured on the server. Set OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, or GEMINI_API_KEY in the server environment (admin action)."
            )
        logger.warning("chat stream rejected: %s (missing=%s)", code, ",".join(missing) or "-")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": code, "message": message},
        )
    return chosen


# ─── Rate limiting (bounded sliding window, per user) ──────────────────────
_RATE_BUCKETS: Dict[str, List[float]] = {}


def reset_chat_rate_limiter() -> None:
    """Clear in-memory buckets (used by tests and admin resets)."""
    _RATE_BUCKETS.clear()


def enforce_chat_rate_limit(user_id: str) -> None:
    """Allow at most RATE_LIMIT_REQUESTS per user in the sliding window."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    hits = [t for t in _RATE_BUCKETS.get(user_id, ()) if t > cutoff]
    if len(hits) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMITED",
                "message": "Too many chat requests. Please retry shortly.",
            },
        )
    hits.append(now)
    _RATE_BUCKETS[user_id] = hits
    if len(_RATE_BUCKETS) > MAX_RATE_BUCKETS:
        # Self-prune: drop expired buckets, then (still oversized) oldest ones.
        for uid in [u for u, ts in _RATE_BUCKETS.items() if all(t <= cutoff for t in ts)]:
            del _RATE_BUCKETS[uid]
        while len(_RATE_BUCKETS) > MAX_RATE_BUCKETS:
            _RATE_BUCKETS.pop(next(iter(_RATE_BUCKETS)))


# ─── Secret redaction ──────────────────────────────────────────────────────
def sanitize_error_text(text: str, limit: int = MAX_ERROR_ECHO_CHARS) -> str:
    """Truncate and strip secret-shaped / configured-credential substrings."""
    out = _SECRET_SHAPE_RE.sub("[REDACTED]", text or "")
    for env_name, env_value in os.environ.items():
        needle = (env_value or "").strip()
        if (
            needle
            and len(needle) >= 12
            and env_name.upper().endswith(("API_KEY", "TOKEN", "SECRET"))
            and needle in out
        ):
            out = out.replace(needle, "[REDACTED]")
    out = " ".join(out.split())  # collapse whitespace/newlines from upstream bodies
    if len(out) > limit:
        out = out[:limit] + "…"
    return out


def _build_http_client() -> httpx.AsyncClient:
    """Factory hook so tests can inject ``httpx.MockTransport`` clients."""
    return httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT)


# ─── Upstream adapters (same wire patterns as ui/api/llm-proxy.js) ─────────
async def _openai_upstream_tokens(
    client: httpx.AsyncClient, cfg: ProviderConfig, payload_body: List[dict]
) -> AsyncIterator[str]:
    """Yield content deltas from an OpenAI-compatible /chat/completions SSE."""
    url = f"{cfg.base_url}/chat/completions"
    body = {
        "model": cfg.model,
        "messages": payload_body,
        "max_tokens": 4096,
        "temperature": 0.7,
        "stream": True,
    }
    headers = {"Content-Type": CONTENT_TYPE_JSON, "Authorization": f"Bearer {cfg.api_key}"}
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        if resp.status_code >= 400:
            raise UpstreamProviderError(
                resp.status_code, (await resp.aread()).decode("utf-8", "replace")
            )
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith(SSE_DATA_PREFIX):
                continue
            data = line[len(SSE_DATA_PREFIX) :].strip()
            if data == "[DONE]":
                return
            try:
                parsed = json.loads(data)
            except ValueError:
                continue  # skip keep-alives / partial frames
            if parsed.get("error"):
                raise UpstreamProviderError(resp.status_code, data)
            delta = (parsed.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield str(delta)


async def _anthropic_upstream_tokens(
    client: httpx.AsyncClient, cfg: ProviderConfig, payload_body: List[dict]
) -> AsyncIterator[str]:
    """Yield text deltas from the Anthropic /v1/messages SSE stream."""
    system_parts = [m["content"] for m in payload_body if m["role"] == "system"]
    chat_messages = [m for m in payload_body if m["role"] != "system"]
    body: dict = {
        "model": cfg.model.replace("anthropic/", ""),
        "max_tokens": 4096,
        "messages": chat_messages,
        "stream": True,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    url = f"{cfg.base_url}/messages"
    headers = {
        "Content-Type": CONTENT_TYPE_JSON,
        "x-api-key": cfg.api_key,
        "anthropic-version": ANTHROPIC_VERSION_HEADER,
    }
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        if resp.status_code >= 400:
            raise UpstreamProviderError(
                resp.status_code, (await resp.aread()).decode("utf-8", "replace")
            )
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith(SSE_DATA_PREFIX):
                continue
            try:
                parsed = json.loads(line[len(SSE_DATA_PREFIX) :].strip())
            except ValueError:
                continue
            event_type = parsed.get("type")
            if event_type == "content_block_delta":
                text = parsed.get("delta", {}).get("text")
                if text:
                    yield str(text)
            elif event_type == "message_stop":
                return
            elif event_type == "error":
                msg = parsed.get("error", {}).get("message") or "Anthropic stream error"
                raise UpstreamProviderError(resp.status_code, msg)


def _build_gemini_payload(payload_body: List[dict]) -> dict:
    """Construct Google Gemini contents payload with systemInstruction."""
    system_parts = [m["content"] for m in payload_body if m["role"] == "system"]
    chat_messages = [m for m in payload_body if m["role"] != "system"]
    contents = [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in chat_messages
    ]
    body: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    return body


def _extract_gemini_deltas(data: str, status_code: int) -> List[str]:
    """Parse Gemini SSE JSON chunk and return text deltas, or raise on error."""
    try:
        parsed = json.loads(data)
    except ValueError:
        return []
    if parsed.get("error"):
        msg = parsed.get("error", {}).get("message") or "Gemini stream error"
        raise UpstreamProviderError(status_code, msg)
    deltas: List[str] = []
    candidates = parsed.get("candidates") or []
    if candidates:
        for part in (candidates[0].get("content") or {}).get("parts") or []:
            text = part.get("text")
            if text:
                deltas.append(str(text))
    return deltas


async def _gemini_upstream_tokens(
    client: httpx.AsyncClient, cfg: ProviderConfig, payload_body: List[dict]
) -> AsyncIterator[str]:
    """Yield text deltas from Google Gemini streamGenerateContent SSE stream."""
    body = _build_gemini_payload(payload_body)
    model_name = cfg.model.replace("gemini/", "").replace("google/", "")
    url = f"{cfg.base_url.rstrip('/')}/models/{model_name}:streamGenerateContent?alt=sse"
    headers = {
        "Content-Type": CONTENT_TYPE_JSON,
        "x-goog-api-key": cfg.api_key,
    }
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        if resp.status_code >= 400:
            raise UpstreamProviderError(
                resp.status_code, (await resp.aread()).decode("utf-8", "replace")
            )
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith(SSE_DATA_PREFIX):
                continue
            data = line[len(SSE_DATA_PREFIX) :].strip()
            if not data:
                continue
            for delta in _extract_gemini_deltas(data, resp.status_code):
                yield delta


_UPSTREAM_ADAPTERS = {
    "openai": _openai_upstream_tokens,
    "anthropic": _anthropic_upstream_tokens,
    "gemini": _gemini_upstream_tokens,
}


# ─── SSE envelope helpers ──────────────────────────────────────────────────
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\n{SSE_DATA_PREFIX} {json.dumps(data, ensure_ascii=False)}\n\n"


async def _chat_event_stream(
    session_id: str,
    messages: List[ChatMessageIn],
    cfg: ProviderConfig,
) -> AsyncIterator[str]:
    """Drive the upstream adapter and translate failures into SSE events.

    Errors NEVER echo secrets: every outward message passes through
    :func:`sanitize_error_text`; unsanitized context goes to server logs
    only, and message CONTENT is never logged at all.
    """
    started = time.monotonic()
    deltas = 0
    try:
        body = [{"role": m.role, "content": m.content} for m in messages]
        async with _build_http_client() as client:
            async for delta in _UPSTREAM_ADAPTERS[cfg.id](client, cfg, body):
                deltas += 1
                if len(delta) > 16_000:  # defensive trim on pathological chunks
                    delta = delta[:16_000]
                yield _sse("token", {"delta": delta})
        yield _sse(
            "done",
            {
                "session_id": session_id,
                "provider": cfg.id,
                "deltas": deltas,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            },
        )
    except UpstreamProviderError as exc:
        sanitized = sanitize_error_text(exc.body_text)
        logger.warning(
            "chat stream upstream error session=%.24s provider=%s status=%s detail=%s",
            session_id,
            cfg.id,
            exc.upstream_status,
            sanitized,
        )
        yield _sse(
            "error",
            {
                "code": "UPSTREAM_ERROR",
                "message": f"LLM provider returned an error (HTTP {exc.upstream_status}).",
                "detail": sanitized,
                "session_id": session_id,
            },
        )
    except httpx.TimeoutException:
        safe_sid = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or ""))[:32]
        logger.warning("chat stream timeout session=%s provider=%s", safe_sid, cfg.id)
        yield _sse(
            "error",
            {
                "code": "UPSTREAM_TIMEOUT",
                "message": "LLM provider timed out. Please retry.",
                "session_id": session_id,
            },
        )
    except httpx.HTTPError as exc:
        # Connectivity/DNS/TLS issues: generic message outward, detail logged.
        safe_sid = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or ""))[:32]
        logger.warning(
            "chat stream connectivity error session=%s provider=%s: %s",
            safe_sid,
            cfg.id,
            exc.__class__.__name__,
        )
        yield _sse(
            "error",
            {
                "code": "CONNECTIVITY_ERROR",
                "message": "Could not reach the LLM provider.",
                "session_id": session_id,
            },
        )
    except asyncio.CancelledError:
        raise  # client disconnected — propagate quietly, no error frame needed
    except Exception as exc:  # noqa: BLE001 — final belt-and-braces guard
        logger.exception(
            "chat stream unexpected failure session=%.24s provider=%s: %s",
            session_id,
            cfg.id,
            exc.__class__.__name__,
        )
        yield _sse(
            "error",
            {
                "code": "INTERNAL_ERROR",
                "message": "Unexpected server error while streaming the reply.",
                "session_id": session_id,
            },
        )


# ─── Endpoint ──────────────────────────────────────────────────────────────
@router.post(
    "/stream",
    summary="Server-side LLM chat stream (SSE) — P4b",
    description=(
        "Accepts {session_id, messages, provider?, model?} with NO API keys. "
        "Keys are read from the server environment only. Responds with a "
        "text/event-stream emitting token/done/error events."
    ),
)
async def chat_stream_endpoint(
    payload: ChatStreamRequest,
    user: Annotated[CurrentUser, Depends(get_current_user_from_header)],
) -> StreamingResponse:
    """Stream a chat completion through a server-configured LLM provider.

    Provider resolution happens BEFORE the stream starts so misconfiguration
    surfaces as a normal HTTP error (503) rather than a mid-stream event.
    """
    enforce_chat_rate_limit(user.user_id)
    cfg = resolve_provider_config(payload.provider, payload.model)
    logger.info(
        "chat stream opened session=%.24s provider=%s user=%.24s",
        payload.session_id,
        cfg.id,
        user.user_id,
    )
    return StreamingResponse(
        _chat_event_stream(payload.session_id, payload.messages, cfg),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
