"""
tests/test_chat_stream.py — P4b server-side LLM chat stream tests.

Covers (per phase P4b security requirements):
  - POST /api/v1/chat/stream requires an authenticated user (401).
  - Client-supplied credential fields (``apiKey`` / ``api_key``) are rejected
    with 422 (schema ``extra="forbid"``) — keys NEVER reach the browser.
  - No provider configured -> 503 NO_LLM_PROVIDER_CONFIGURED.
  - Requested provider not configured -> 503 PROVIDER_NOT_CONFIGURED.
  - Per-user sliding-window rate limit -> 429 RATE_LIMITED.
  - Silent success: with OPENAI_API_KEY set and a mocked upstream, the
    response is a text/event-stream emitting ``token`` deltas + ``done``.
  - ``sanitize_error_text`` redacts secret-shaped strings and configured
    credential env values (defence-in-depth against leakage).

These tests exercise the real FastAPI app (``api.routes.app``) through the
Starlette TestClient and build JWTs exactly like ``tests/test_agent_executor.py``.
"""

from __future__ import annotations

import time

import httpx
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

import api.chat_stream as chat_stream
from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY


def _auth(user_id: str = "test-user-id") -> dict:
    """Auth headers carrying a valid access JWT + CSRF token.

    The JWT mirrors /api/v1/auth/login; the CSRF token mirrors the browser
    flow (GET /api/v1/csrf/token then X-CSRF-Token on every mutating request).
    Without the CSRF header, CSRFMiddleware rejects the request with 403
    before body validation whenever auth is enforced (CI api-e2e sets
    ENGINEERING_SERVICE_AUTH_DISABLED=false), masking the 422 under test.
    """
    now = time.time()
    token = pyjwt.encode(
        {"sub": user_id, "type": "access", "iat": int(now), "exp": int(now + 600)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    from api.csrf import generate_csrf_token

    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


def _payload(**overrides) -> dict:
    body = {
        "session_id": "sess-p4b-test",
        "messages": [{"role": "user", "content": "hello"}],
        "provider": "openai",
    }
    body.update(overrides)
    return body


@pytest.fixture(scope="module")
def client():
    """Module-scoped app client (starts FastAPI lifespan ONCE)."""
    from api.routes import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_rate():
    """Reset rate-limit buckets around every test."""
    chat_stream.reset_chat_rate_limiter()
    yield
    chat_stream.reset_chat_rate_limiter()


# ─── 1. Authentication ─────────────────────────────────────────────────────


def test_requires_auth(client):
    """Unauthenticated POST (with valid CSRF) must return 401.

    A CSRF token is included so CSRFMiddleware passes the request through;
    without it the middleware short-circuits with 403 whenever auth is
    enforced (AUTH_DISABLED=false), masking the authentication check.
    """
    from api.csrf import generate_csrf_token

    resp = client.post(
        "/api/v1/chat/stream",
        json=_payload(),
        headers={"X-CSRF-Token": generate_csrf_token()},
    )
    assert resp.status_code == 401


# ─── 2. Credential-free request contract (extra="forbid") ──────────────────


def test_rejects_client_supplied_api_key_422(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-server-only")
    body = dict(_payload())
    body["apiKey"] = "sk-client-tried-to-set-key"
    resp = client.post("/api/v1/chat/stream", json=body, headers=_auth())
    assert resp.status_code == 422


def test_rejects_client_supplied_headers_422(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-server-only")
    body = dict(_payload())
    body["headers"] = {"Authorization": "Bearer sk-client-credential"}
    resp = client.post("/api/v1/chat/stream", json=body, headers=_auth())
    assert resp.status_code == 422


# ─── 3. Provider configuration (503, server env only) ──────────────────────


def test_no_provider_configured_503(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # No explicit provider in the request -> any-missing => generic code.
    resp = client.post(
        "/api/v1/chat/stream",
        json=_payload(provider=None),
        headers=_auth(),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "NO_LLM_PROVIDER_CONFIGURED"


def test_requested_provider_not_configured_503(client, monkeypatch):
    # Anthropic configured, but the request asks for openai -> 503.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.post("/api/v1/chat/stream", json=_payload(), headers=_auth())
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


def test_default_provider_fallback_picks_first_configured(monkeypatch):
    # No explicit provider + openai configured -> openai is resolved (no 503).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ok")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = chat_stream.resolve_provider_config(None, None)
    assert cfg.id == "openai"
    assert cfg.model == chat_stream.PROVIDER_DEFAULT_MODEL["openai"]


# ─── 4. Rate limiting ──────────────────────────────────────────────────────


def test_rate_limited_429(client, monkeypatch):
    # NO provider configured on purpose: rate-limit runs before resolution, so
    # the first two requests 503 (still count toward the window) and the third
    # is rejected with 429 — avoiding any real upstream HTTP call.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(chat_stream, "RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(chat_stream, "RATE_LIMIT_WINDOW_SECONDS", 60.0)
    chat_stream.reset_chat_rate_limiter()
    for _ in range(2):
        r = client.post("/api/v1/chat/stream", json=_payload(), headers=_auth())
        assert r.status_code == 503  # each counts toward the bucket
    resp = client.post("/api/v1/chat/stream", json=_payload(), headers=_auth())
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "RATE_LIMITED"


# ─── 5. Successful streaming with a mocked upstream ────────────────────────


def _mock_openai_response(sse_body: str):
    def _handler(request: httpx.Request):
        return httpx.Response(
            200,
            text=sse_body,
            headers={"Content-Type": "text/event-stream"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(_handler))


def test_successful_openai_stream(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    sse_body = (
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    monkeypatch.setattr(chat_stream, "_build_http_client", lambda: _mock_openai_response(sse_body))

    resp = client.post("/api/v1/chat/stream", json=_payload(), headers=_auth())
    assert resp.status_code == 200
    text = resp.text
    assert "event: token" in text
    assert '"delta": "Hello"' in text
    assert '"delta": " world"' in text
    assert "event: done" in text
    assert '"provider": "openai"' in text


def test_successful_anthropic_stream(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sse_body = (
        'data: {"type":"content_block_delta","delta":{"text":"hola"}}\n\n'
        'data: {"type":"content_block_delta","delta":{"text":" mundo"}}\n\n'
        'data: {"type":"message_stop"}\n\n'
    )
    monkeypatch.setattr(chat_stream, "_build_http_client", lambda: _mock_openai_response(sse_body))

    resp = client.post(
        "/api/v1/chat/stream",
        json=_payload(provider="anthropic"),
        headers=_auth(),
    )
    assert resp.status_code == 200
    text = resp.text
    assert '"delta": "hola"' in text
    assert '"delta": " mundo"' in text
    assert '"provider": "anthropic"' in text


# ─── 6. Error sanitation (defence-in-depth) ────────────────────────────────


def test_sanitize_redacts_secret_shapes():
    out = chat_stream.sanitize_error_text("failed for key sk-abcdef123456 and ok")
    assert "sk-abcdef123456" not in out
    assert "[REDACTED]" in out


def test_sanitize_redacts_configured_credential_env(monkeypatch):
    monkeypatch.setenv("SERVICE_CHAT_TOKEN", "super-secret-token-value-1234")
    out = chat_stream.sanitize_error_text("bad with super-secret-token-value-1234 inside")
    assert "super-secret-token-value-1234" not in out
    assert "[REDACTED]" in out


def test_sanitize_truncates_long():
    long_text = "x" * 1000
    out = chat_stream.sanitize_error_text(long_text)
    assert len(out) <= chat_stream.MAX_ERROR_ECHO_CHARS + 1  # + ellipsis char
    assert out.endswith("…")
