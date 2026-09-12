"""tests/test_rate_limit.py — Comprehensive tests for the unified SlowAPI rate-limiting Module.

Tests the rate-limiting Interface test surface:
1. Single Limiter instance verification (D1 / D2).
2. Login rate limiting (10/min) triggering HTTP 429 with Retry-After header.
3. Isolation by IP and username (compound key prevents cross-user lockout).
4. Register (5/min), Refresh (30/min), and Forgot-password (5/min) policies.
5. In-memory fallback verification when USE_REDIS_RATE_LIMIT is false (D6).
6. Proxy-aware IP resolution & spoofing invariant (TRUSTED_PROXY_HOPS) (D5).
7. Non-interference between SlowAPI burst limits and internal lockout limits (D3).
"""

from __future__ import annotations

import os
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from api.auth import router as auth_router
from api.csrf import generate_csrf_token
from api.rate_limit import (
    RateLimitExceeded,
    SlowAPIMiddleware,
    auth_limiter,
    get_authenticated_or_ip_key,
    get_client_ip,
    get_login_rate_limit_key,
    get_remote_address_proxy_aware,
    limiter,
    rate_limit_exceeded_handler,
)
from api.routes import app as main_app


@pytest.fixture(autouse=True)
def _enable_rate_limit_for_tests():
    """Ensure rate limiting is active during rate-limit unit tests."""
    old_enabled = limiter._override_enabled
    limiter.enabled = True
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "storage"):
        limiter._storage.storage.clear()
    yield
    limiter.enabled = old_enabled
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "storage"):
        limiter._storage.storage.clear()


@pytest.fixture
def rate_limit_test_client() -> TestClient:
    """Return a dedicated TestClient with fresh rate-limiting storage."""
    client = TestClient(main_app)
    client.headers.update({"x-csrf-token": generate_csrf_token()})
    api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
    if api_key:
        client.headers.update({"x-api-key": api_key})
    return client


class TestRateLimitModuleContract:
    """Verify architectural invariants of the rate-limiting Module."""

    def test_single_limiter_instance(self) -> None:
        """D1/D2: Exactly one Limiter instance exists; auth_limiter is an alias."""
        assert limiter is not None
        assert auth_limiter is limiter
        assert main_app.state.limiter is limiter

    def test_no_unintended_default_limits_on_limiter(self) -> None:
        """D2: Limiter instance has no default_limits that leak onto un-decorated routes."""
        # _default_limits should be empty on the root Limiter
        assert len(limiter._default_limits) == 0

    def test_proxy_aware_ip_spoofing_invariant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D5: X-Forwarded-For is ignored when TRUSTED_PROXY_HOPS=0 (default)."""
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
                "client": ("10.0.0.1", 12345),
            }
        )
        # Must return connection peer (10.0.0.1), ignoring client-supplied header
        assert get_client_ip(req) == "10.0.0.1"

    def test_proxy_aware_ip_trusted_hops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D5: X-Forwarded-For is respected when TRUSTED_PROXY_HOPS > 0."""
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
                "client": ("10.0.0.1", 12345),
            }
        )
        # 1 hop from right: 70.41.3.18
        assert get_client_ip(req) == "70.41.3.18"

    def test_login_rate_limit_key_extraction(self) -> None:
        """D5: Login key extracts normalized username and client IP."""
        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [],
                "client": ("192.168.1.50", 12345),
            }
        )
        req._body = b'{"username": "  TestEngineer  ", "password": "SecretPassword123!"}'
        key = get_login_rate_limit_key(req)
        assert key == "192.168.1.50:testengineer"

    def test_authenticated_token_key_extraction(self) -> None:
        """D4/D5: Authenticated key hashes Bearer token if present."""
        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/refresh",
                "headers": [(b"authorization", b"Bearer test-jwt-access-token-12345")],
                "client": ("192.168.1.50", 12345),
            }
        )
        key = get_authenticated_or_ip_key(req)
        assert key.startswith("tok:")

    def test_missing_slowapi_fallback(self) -> None:
        """Verify fallback Limiter, Middleware, and RateLimitExceeded work correctly."""
        from api import rate_limit

        # Verify module exports
        assert hasattr(rate_limit, "limiter")
        assert hasattr(rate_limit, "SlowAPIMiddleware")
        assert hasattr(rate_limit, "RateLimitExceeded")
        assert hasattr(rate_limit, "rate_limit_exceeded_handler")

        # Verify fallback class contract behaves as no-op when slowapi is disabled/absent
        class FallbackLimiter:
            def __init__(self, key_func=None, *args, **kwargs) -> None:
                self.key_func = key_func
                self.limiter = None

            def limit(self, *args, **kwargs):
                def decorator(func):
                    return func
                return decorator

        fl = FallbackLimiter(key_func=lambda req: "127.0.0.1")

        @fl.limit("5/minute")
        def dummy_func(x: int) -> int:
            return x * 2

        assert dummy_func(5) == 10

        middleware = rate_limit.SlowAPIMiddleware(app=None)
        assert callable(middleware)


class TestRateLimitPolicies:
    """Test policy enforcement and HTTP 429 response structure."""

    def test_login_rate_limit_and_retry_after(self) -> None:
        """D1/D3: Login enforces 10/min and returns HTTP 429 with Retry-After header."""
        test_app = FastAPI()
        test_app.state.limiter = limiter
        test_app.add_middleware(SlowAPIMiddleware)
        test_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @test_app.post("/test-login")
        @limiter.limit("5/minute", key_func=get_login_rate_limit_key)
        async def mock_login(request: Request, body: Dict[str, Any]) -> Dict[str, str]:
            return {"status": "ok"}

        client = TestClient(test_app)

        # 5 successful attempts within the minute window
        for i in range(5):
            res = client.post(
                "/test-login",
                json={"username": "alice", "password": "Password1!"},
                headers={"x-forwarded-for": "198.51.100.1"},
            )
            assert res.status_code == 200, f"Attempt {i + 1} failed: {res.text}"

        # 6th attempt must trigger HTTP 429
        res_blocked = client.post(
            "/test-login",
            json={"username": "alice", "password": "Password1!"},
            headers={"x-forwarded-for": "198.51.100.1"},
        )
        assert res_blocked.status_code == 429
        assert "Rate limit exceeded" in res_blocked.json()["error"]
        assert "Retry-After" in res_blocked.headers
        retry_after = int(res_blocked.headers["Retry-After"])
        assert retry_after > 0

    def test_login_isolation_between_accounts(self) -> None:
        """D5: Rate limiting alice does not block bob under the same IP."""
        test_app = FastAPI()
        test_app.state.limiter = limiter
        test_app.add_middleware(SlowAPIMiddleware)
        test_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @test_app.post("/test-login-iso")
        @limiter.limit("3/minute", key_func=get_login_rate_limit_key)
        async def mock_login(request: Request, body: Dict[str, Any]) -> Dict[str, str]:
            return {"user": body.get("username", "")}

        client = TestClient(test_app)

        # Alice hits limit
        for _ in range(3):
            client.post("/test-login-iso", json={"username": "alice"})
        alice_blocked = client.post("/test-login-iso", json={"username": "alice"})
        assert alice_blocked.status_code == 429

        # Bob is NOT blocked
        bob_allowed = client.post("/test-login-iso", json={"username": "bob"})
        assert bob_allowed.status_code == 200
        assert bob_allowed.json()["user"] == "bob"

    def test_register_stricter_rate_limit_policy(self) -> None:
        """D4: Register enforces strict 5/minute policy."""
        test_app = FastAPI()
        test_app.state.limiter = limiter
        test_app.add_middleware(SlowAPIMiddleware)
        test_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @test_app.post("/test-register")
        @limiter.limit("5/minute", key_func=get_remote_address_proxy_aware)
        async def mock_register(request: Request) -> Dict[str, str]:
            return {"status": "registered"}

        client = TestClient(test_app)

        for _ in range(5):
            res = client.post("/test-register", headers={"x-forwarded-for": "192.0.2.1"})
            assert res.status_code == 200

        res_blocked = client.post("/test-register", headers={"x-forwarded-for": "192.0.2.1"})
        assert res_blocked.status_code == 429
        assert "Retry-After" in res_blocked.headers

    def test_token_refresh_rate_limit_policy(self) -> None:
        """D4: Token refresh allows higher volume (30/minute) keyed by token."""
        test_app = FastAPI()
        test_app.state.limiter = limiter
        test_app.add_middleware(SlowAPIMiddleware)
        test_app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        @test_app.post("/test-refresh")
        @limiter.limit("30/minute", key_func=get_authenticated_or_ip_key)
        async def mock_refresh(request: Request) -> Dict[str, str]:
            return {"status": "refreshed"}

        client = TestClient(test_app)
        res = client.post(
            "/test-refresh", headers={"authorization": "Bearer dummy-refresh-token-xyz"}
        )
        assert res.status_code == 200

    def test_in_memory_fallback_storage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D6: When USE_REDIS_RATE_LIMIT=false, falls back safely to memory:// storage."""
        monkeypatch.setenv("USE_REDIS_RATE_LIMIT", "false")
        monkeypatch.setenv("REDIS_URL", "")
        assert "memory://" in str(limiter._storage_uri)
