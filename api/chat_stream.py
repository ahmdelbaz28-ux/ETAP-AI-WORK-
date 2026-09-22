"""
api/chat_stream.py — Server-side LLM chat streaming (P4b & S1 BYOK).

``POST /api/v1/chat/stream`` accepts ``{session_id, messages[],
provider?, model?}`` (NO API keys in body payload) and replies with a unified SSE envelope::

    event: token  data: {"delta": "..."}    per generated chunk
    event: done   data: {...}               on successful completion
    event: error  data: {"code", "message"} on failure

Credential & Header Resolution (Channel Boundaries):
- Canonical Stream Channel: ``X-User-LLM-Key`` and ``X-User-LLM-Provider``
  are the ONLY client credential headers accepted for SSE chat streaming
  (consumed solely by ``ui/src/lib/llm-chat.ts:1219`` and allowed in CORS).
- Legacy Channel: ``x-active-*`` headers are legacy REST-only credentials used by
  ``ui/src/lib/api.ts:21-35`` (which may configure custom base URLs ignored by the streaming
  resolver) and are STRICTLY NOT accepted or consumed on the /api/v1/chat/stream path
  to prevent inadvertent credential disclosure.
- Resolution Precedence: Server environment keys (OPENAI_API_KEY / ANTHROPIC_API_KEY /
  GEMINI_API_KEY) take precedence. If server keys are missing, an authorized client BYOK
  header key (X-User-LLM-Key) is used. If neither is present, HTTP 503 is returned.

Security invariants:
1. No keys in body payload — schema uses ``extra="forbid"`` so any client-supplied
   credential field in JSON body is rejected with 422. BYOK credentials must be passed
   via transport headers only.
2. Provider allowlist — only OpenAI-compatible, Anthropic, and Gemini adapters,
   reusing ui/api/llm-proxy.js wire patterns (SSE framing, ``[DONE]``
   sentinel, Anthropic ``content_block_delta``).
3. Zero credential leakage — client and server keys NEVER appear in logs or client-facing
   error bodies. Upstream failures are sanitized via ``sanitize_error_text`` with
   ``extra_secrets`` redaction before emission.
4. Auth required — Bearer access token via get_current_user_from_header
   (mirrors the P4a agent-exec path).
5. Per-user rate limiting — bounded sliding window (platform rule).
6. Output Privacy Gating — LLM response message content capture into Langfuse/external
   observability is strictly gated behind the ``langfuse_output_capture`` feature flag
   (zero content logged when flag is disabled).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated

from api.dependencies import CurrentUser, get_current_user_from_header

logger = logging.getLogger("api.chat_stream")

SSE_DATA_PREFIX = "data:"
_CONTENT_TYPE_JSON = "application/json"
_SAFE_SESSION_ID_PATTERN = r"[^A-Za-z0-9_-]"

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
    credential-ish extra field in the JSON payload (apiKey / api_key / token ...)
    is rejected outright with 422.
    Client-supplied BYOK keys MUST be passed via transport headers (X-User-LLM-Key),
    never in the request body. Server environment keys take precedence; when absent,
    authorized header keys are utilized securely without logging.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=MAX_SESSION_ID_CHARS)
    messages: List[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    provider: Optional[str] = Field(default=None, pattern="^(openai|anthropic|gemini)$")
    model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    project_id: Optional[str] = Field(default=None, max_length=128)


class ProviderConfig(BaseModel):
    """Resolved server-side provider configuration (never serialized out)."""

    id: str
    api_key: str
    base_url: str
    model: str


def resolve_provider_config(
    provider: Optional[str],
    model: Optional[str],
    user_api_key: Optional[str] = None,
    user_provider: Optional[str] = None,
) -> ProviderConfig:
    """Build the provider config from SERVER-SIDE environment or authorized BYOK header.

    If server environment variables lack an API key, an authorized client-provided
    BYOK key (from header X-User-LLM-Key) is utilized securely without logging.
    Raises 503 when no provider can be configured.
    """
    effective_provider = provider or user_provider
    candidates = (effective_provider,) if effective_provider else SUPPORTED_PROVIDERS
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

    # Fallback to BYOK user-supplied API key if server-side key is absent
    if chosen is None and user_api_key and user_api_key.strip():
        target_pid = effective_provider if effective_provider in SUPPORTED_PROVIDERS else "openai"
        chosen = ProviderConfig(
            id=target_pid,
            api_key=user_api_key.strip(),
            base_url=(
                os.environ.get(PROVIDER_BASE_URL_ENV[target_pid], "").strip().rstrip("/")
                or PROVIDER_DEFAULT_BASE_URL[target_pid]
            ),
            model=(
                (model or "").strip()
                or os.environ.get(PROVIDER_MODEL_ENV[target_pid], "").strip()
                or PROVIDER_DEFAULT_MODEL[target_pid]
            ),
        )

    if chosen is None:
        if effective_provider:
            code = "PROVIDER_NOT_CONFIGURED"
            message = "Requested LLM provider is not configured on the server."
        else:
            code = "NO_LLM_PROVIDER_CONFIGURED"
            message = (
                "No LLM provider is configured on the server. Set OPENAI_API_KEY "
                "or ANTHROPIC_API_KEY in the server environment (admin action) or supply BYOK."
            )
        safe_code = re.sub(r"[^A-Za-z0-9_.-]", "", str(code or ""))[:32]
        safe_missing = ",".join(re.sub(r"[^A-Za-z0-9_.-]", "", str(m))[:32] for m in missing) or "-"
        logger.warning("chat stream rejected: %s (missing=%s)", safe_code, safe_missing)
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
def sanitize_error_text(
    text: str, limit: int = MAX_ERROR_ECHO_CHARS, extra_secrets: Optional[List[str]] = None
) -> str:
    """Truncate and strip secret-shaped / configured-credential substrings."""
    out = _SECRET_SHAPE_RE.sub("[REDACTED]", text or "")
    all_secrets: List[str] = list(extra_secrets or [])
    for env_name, env_value in os.environ.items():
        needle = (env_value or "").strip()
        if (
            needle
            and len(needle) >= 12
            and env_name.upper().endswith(("API_KEY", "TOKEN", "SECRET"))
        ):
            all_secrets.append(needle)
    for needle in all_secrets:
        if needle and len(needle) >= 8 and needle in out:
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
    from api.feature_flags import is_strict_feature_enabled

    use_sys = is_strict_feature_enabled("chat_system_prompt")
    url = f"{cfg.base_url}/chat/completions"
    body = {
        "model": cfg.model,
        "messages": payload_body,
        "max_tokens": 8192 if use_sys else 4096,
        "temperature": 0.2 if use_sys else 0.7,
        "stream": True,
    }
    headers = {"Content-Type": _CONTENT_TYPE_JSON, "Authorization": f"Bearer {cfg.api_key}"}
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
    from api.feature_flags import is_strict_feature_enabled

    use_sys = is_strict_feature_enabled("chat_system_prompt")
    system_parts = [m["content"] for m in payload_body if m["role"] == "system"]
    chat_messages = [m for m in payload_body if m["role"] != "system"]
    body: dict = {
        "model": cfg.model.replace("anthropic/", ""),
        "max_tokens": 8192 if use_sys else 4096,
        "messages": chat_messages,
        "stream": True,
    }
    if use_sys:
        body["temperature"] = 0.2
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    url = f"{cfg.base_url}/messages"
    headers = {
        "Content-Type": _CONTENT_TYPE_JSON,
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
    from api.feature_flags import is_strict_feature_enabled

    use_sys = is_strict_feature_enabled("chat_system_prompt")
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
            "temperature": 0.2 if use_sys else 0.7,
            "maxOutputTokens": 8192 if use_sys else 4096,
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
        "Content-Type": _CONTENT_TYPE_JSON,
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
    only, and message CONTENT is never logged unless langfuse_output_capture
    feature flag is explicitly enabled.
    """
    started = time.monotonic()
    deltas = 0
    try:
        from api.feature_flags import is_strict_feature_enabled

        body = [{"role": m.role, "content": m.content} for m in messages]

        # P-A4: System prompt injection (etap_engineer_agent canonical prompt)
        if is_strict_feature_enabled("chat_system_prompt"):
            from agents.prompt_loader import get_system_prompt_async
            try:
                sys_prompt = await get_system_prompt_async("etap_engineer_agent")
            except Exception:
                from agents.prompt_loader import get_system_prompt
                sys_prompt = get_system_prompt("etap_engineer_agent")
            # P-B4: When chat_structured is also enabled, append output schema instructions
            if is_strict_feature_enabled("chat_structured") and sys_prompt:
                sys_prompt += (
                    "\n\nOUTPUT FORMAT INSTRUCTIONS:\n"
                    "Provide your final engineering response strictly formatted as a valid JSON object "
                    "matching the EngineerAnswer schema with keys: 'title', 'summary', 'status' ('complete'|'partial'|'needs_input'|'error'), "
                    "'study_type', 'findings', 'parameters', 'standards_referenced', 'recommendations', 'confidence'."
                )
            if sys_prompt and (not body or body[0].get("role") != "system"):
                body.insert(0, {"role": "system", "content": sys_prompt})

        # P-A5: Token budget history pruning (8000 token cap for etap_engineer_agent)
        if is_strict_feature_enabled("chat_history_prune"):
            from api.token_budget import budget_manager
            body = budget_manager.prune_history(body, max_tokens=8000, keep_system=True)

        async with _build_http_client() as client:
            adapter = _UPSTREAM_ADAPTERS[cfg.id]
            from integrations.langfuse_integration import langfuse_tracker
            obs_cm = langfuse_tracker.get_context_manager(
                name=f"chat_stream.{cfg.id}",
                metadata={"provider": cfg.id, "model": cfg.model, "agent": "etap_engineer_agent"},
                session_id=session_id,
            )
            with obs_cm as obs:
                collected_tokens: list[str] = []
                try:
                    async for delta in adapter(client, cfg, body):
                        deltas += 1
                        collected_tokens.append(delta)
                        if len(delta) > 16_000:  # defensive trim on pathological chunks
                            delta = delta[:16_000]
                        yield _sse("token", {"delta": delta})
                    if hasattr(obs, "update"):
                        full_output_text = "".join(collected_tokens)
                        if is_strict_feature_enabled("langfuse_output_capture"):
                            obs.update(output=full_output_text[:langfuse_tracker.max_capture_chars])
                        else:
                            # P-B5: Obfuscated summary — zero response content logged to tracker
                            obs.update(
                                output=f"[REDACTED: langfuse_output_capture=disabled, chars={len(full_output_text)}, deltas={deltas}, provider={cfg.id}]"
                            )
                except Exception as exc:
                    if hasattr(obs, "record_exception"):
                        with contextlib.suppress(Exception):
                            obs.record_exception(exc)
                    raise

        done_payload: dict[str, Any] = {
            "session_id": session_id,
            "provider": cfg.id,
            "deltas": deltas,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }

        # P-B4: Backend validation against EngineerAnswer when chat_structured is enabled
        if is_strict_feature_enabled("chat_structured"):
            from api.answer_schema import EngineerAnswer

            full_text = "".join(collected_tokens).strip()
            try:
                EngineerAnswer.model_validate_json(full_text)
                done_payload["structured"] = True
            except Exception as schema_err:
                done_payload["structured"] = False
                done_payload["structured_errors"] = [
                    f"{err.get('loc')}: {err.get('msg')}"
                    for err in getattr(schema_err, "errors", lambda: [])()
                ] if hasattr(schema_err, "errors") else ["JSON validation failed"]

        yield _sse("done", done_payload)
    except UpstreamProviderError as exc:
        sanitized = sanitize_error_text(exc.body_text, extra_secrets=[cfg.api_key])
        safe_sid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(session_id or ""))[:32]
        safe_detail = re.sub(r"[\r\n]", " ", str(sanitized or ""))[:128]
        logger.warning(
            "chat stream upstream error session=%s provider=%s status=%s detail=%s",
            safe_sid,
            cfg.id,
            exc.upstream_status,
            safe_detail,
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
        safe_sid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(session_id or ""))[:32]
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
        safe_sid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(session_id or ""))[:32]
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
        safe_sid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(session_id or ""))[:32]
        logger.exception(
            "chat stream unexpected failure session=%s provider=%s: %s",
            safe_sid,
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
    request: Request,
    payload: ChatStreamRequest,
    user: Annotated[CurrentUser, Depends(get_current_user_from_header)],
) -> StreamingResponse:
    """Stream a chat completion through a server-configured LLM provider.

    Provider resolution happens BEFORE the stream starts so misconfiguration
    surfaces as a normal HTTP error (503) rather than a mid-stream event.
    """
    enforce_chat_rate_limit(user.user_id)
    user_api_key = request.headers.get("x-user-llm-key", "").strip() or None
    user_provider = request.headers.get("x-user-llm-provider", "").strip().lower() or None
    cfg = resolve_provider_config(
        payload.provider, payload.model, user_api_key=user_api_key, user_provider=user_provider
    )
    safe_sid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(payload.session_id or ""))[:32]
    safe_uid = re.sub(_SAFE_SESSION_ID_PATTERN, "", str(user.user_id or ""))[:32]
    is_byok = bool(user_api_key and cfg.api_key == user_api_key)
    logger.info(
        "chat stream opened session=%s provider=%s user=%s byok=%s",
        safe_sid,
        cfg.id,
        safe_uid,
        is_byok,
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
