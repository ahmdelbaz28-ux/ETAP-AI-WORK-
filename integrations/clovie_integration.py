"""
Clovie Router Integration for AhmedETAP
=======================================

OpenAI-compatible gateway exposing the MiMo model family. Supports agent
frameworks: Hermes, OpenClaw, Cline, Claude Code.

Configuration (env vars):
    CLOVIE_API_KEY   — Bearer token for the gateway
    CLOVIE_BASE_URL  — Default: https://clovievalen-clovie-router.hf.space/v1
    CLOVIE_MODEL     — Default: mimo-v2-flash

Available models:
    mimo-v2.5-pro    — Latest flagship (strongest reasoning)
    mimo-v2.5        — Latest balanced
    mimo-v2-omni     — Multimodal (vision + text)
    mimo-v2-pro      — Previous-gen pro
    mimo-v2-flash    — Fastest, cheapest (DEFAULT)

Usage:
    from integrations.clovie_integration import ClovieClient, chat_completion

    client = ClovieClient()
    if client.is_available():
        result = client.chat("Translate 'hello' to Arabic")
        print(result)

Notes:
    - The gateway is 100% OpenAI-compatible: same request/response schema.
      Drop-in replacement for OpenAI client by changing base_url + api_key.
    - Free tier has limited credits. Top up at:
      https://gitlawb.com/opengateway/credits
    - On HTTP 402 (insufficient_credits), the client raises
      ClovieInsufficientCreditsError — callers should fall back to
      another provider.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

CLOVIE_DEFAULT_BASE_URL = "https://clovievalen-clovie-router.hf.space/v1"
CLOVIE_DEFAULT_MODEL = "mimo-v2-flash"
CLOVIE_SUPPORTED_MODELS = frozenset({
    "mimo-v2.5-pro",
    "mimo-v2.5",
    "mimo-v2-omni",
    "mimo-v2-pro",
    "mimo-v2-flash",
})
CLOVIE_TIMEOUT = 30.0


class ClovieError(Exception):
    """Base error for Clovie Router."""


class ClovieInsufficientCreditsError(ClovieError):
    """HTTP 402 — account is out of credits. Top up at the dashboard."""


class ClovieAuthError(ClovieError):
    """HTTP 401/403 — API key is missing, invalid, or expired."""


class ClovieModelError(ClovieError):
    """HTTP 404 — requested model does not exist on the gateway."""


@dataclass
class ClovieChatResult:
    text: str
    model: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class ClovieClient:
    """OpenAI-compatible client for the Clovie Router gateway."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = CLOVIE_TIMEOUT,
    ) -> None:
        self.api_key = api_key or os.environ.get("CLOVIE_API_KEY", "")
        self.base_url = (base_url or os.environ.get("CLOVIE_BASE_URL", CLOVIE_DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("CLOVIE_MODEL", CLOVIE_DEFAULT_MODEL)
        self.timeout = timeout
        self._client: httpx.Client | None = None

    # ─── Lifecycle ───────────────────────────────────────────────────────
    def is_available(self) -> bool:
        """True if API key is set (does NOT verify credits)."""
        return bool(self.api_key)

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ClovieClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ─── Chat ────────────────────────────────────────────────────────────
    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ClovieChatResult:
        """Send a single-turn chat request. Returns the assistant's reply."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat_messages(messages, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)

    def chat_messages(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ClovieChatResult:
        """Send a multi-turn chat request with full message history."""
        if not self.is_available():
            raise ClovieError("CLOVIE_API_KEY is not set")
        use_model = model or self.model
        if use_model not in CLOVIE_SUPPORTED_MODELS:
            logger.warning(
                "Model '%s' is not in the known MiMo model list %s — sending anyway",
                use_model, sorted(CLOVIE_SUPPORTED_MODELS),
            )

        payload: dict[str, Any] = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        client = self._get_client()
        import time as _t
        start = _t.monotonic()
        try:
            r = client.post("/chat/completions", json=payload)
        except httpx.RequestError as e:
            raise ClovieError(f"Network error: {e}") from e
        latency_ms = int((_t.monotonic() - start) * 1000)

        if r.status_code == 402:
            err = self._safe_error(r)
            raise ClovieInsufficientCreditsError(
                f"Clovie account is out of credits. Top up at "
                f"https://gitlawb.com/opengateway/credits — {err}"
            )
        if r.status_code in (401, 403):
            err = self._safe_error(r)
            raise ClovieAuthError(f"Clovie auth failed ({r.status_code}): {err}")
        if r.status_code == 404:
            err = self._safe_error(r)
            raise ClovieModelError(f"Clovie model/endpoint not found: {err}")
        if r.status_code >= 400:
            err = self._safe_error(r)
            raise ClovieError(f"Clovie HTTP {r.status_code}: {err}")

        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        text = choice.get("message", {}).get("content", "")
        finish = choice.get("finish_reason", "")
        usage = data.get("usage", {}) or {}
        return ClovieChatResult(
            text=text,
            model=data.get("model", use_model),
            finish_reason=finish,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency_ms,
        )

    # ─── Streaming ───────────────────────────────────────────────────────
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterable[str]:
        """Stream chat completion tokens. Yields content deltas as strings."""
        if not self.is_available():
            raise ClovieError("CLOVIE_API_KEY is not set")
        use_model = model or self.model
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        client = self._get_client()
        with client.stream("POST", "/chat/completions", json=payload) as r:
            if r.status_code >= 400:
                raise ClovieError(f"HTTP {r.status_code}: {r.read().decode(errors='replace')[:200]}")
            for line in r.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload_str = line[6:].strip()
                if payload_str == "[DONE]":
                    break
                try:
                    import json as _json
                    chunk = _json.loads(payload_str)
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue

    # ─── Health check ────────────────────────────────────────────────────
    def ping(self) -> tuple[bool, str]:
        """Cheap connectivity check. Returns (ok, message)."""
        if not self.is_available():
            return False, "CLOVIE_API_KEY not set"
        try:
            client = self._get_client()
            # We don't have a /models endpoint, so send a 1-token request
            r = client.post("/chat/completions", json={
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            })
            if r.status_code == 200:
                return True, f"OK — model={self.model}"
            if r.status_code == 402:
                return False, "Insufficient credits (top up at https://gitlawb.com/opengateway/credits)"
            if r.status_code in (401, 403):
                return False, f"Auth failed ({r.status_code})"
            return False, f"HTTP {r.status_code}: {self._safe_error(r)}"
        except httpx.RequestError as e:
            return False, f"Network error: {e}"

    @staticmethod
    def _safe_error(r: httpx.Response) -> str:
        try:
            data = r.json()
            return data.get("error", {}).get("message", r.text[:200])
        except Exception:
            return r.text[:200]


# ─── Module-level singleton ──────────────────────────────────────────────
_client: ClovieClient | None = None


def get_clovie_client() -> ClovieClient:
    """Return a shared ClovieClient singleton (lazy-init)."""
    global _client
    if _client is None:
        _client = ClovieClient()
    return _client


def chat_completion(prompt: str, **kwargs: Any) -> str:
    """Convenience wrapper — returns just the assistant's text."""
    return get_clovie_client().chat(prompt, **kwargs).text


__all__ = [
    "ClovieClient",
    "ClovieChatResult",
    "ClovieError",
    "ClovieAuthError",
    "ClovieModelError",
    "ClovieInsufficientCreditsError",
    "CLOVIE_SUPPORTED_MODELS",
    "CLOVIE_DEFAULT_BASE_URL",
    "CLOVIE_DEFAULT_MODEL",
    "get_clovie_client",
    "chat_completion",
]
