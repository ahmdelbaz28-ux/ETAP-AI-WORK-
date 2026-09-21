"""tests/test_security_headers.py — Comprehensive tests for SecurityHeadersMiddleware and HostValidationMiddleware.

Verifies:
1. Injection of HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
2. Host validation rejecting malformed host headers.
3. HTTPS 301 redirection behavior when ENFORCE_HTTPS=true and incoming traffic is HTTP.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from api.security_headers import HostValidationMiddleware, SecurityHeadersMiddleware


async def _dummy_endpoint(request):
    return JSONResponse({"status": "ok"})


def _build_test_app() -> Starlette:
    app = Starlette(routes=[Route("/test", _dummy_endpoint)])
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HostValidationMiddleware)
    return app


def test_security_headers_injected():
    client = TestClient(_build_test_app())

    # Plain HTTP request: security headers present, but HSTS omitted per RFC 6797 Section 7.2 & FIX-RC5
    res = client.get("/test")
    assert res.status_code == 200
    assert "Strict-Transport-Security" not in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" in res.headers
    assert "Content-Security-Policy" in res.headers
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in res.headers

    # HTTPS request (via X-Forwarded-Proto): HSTS is injected with max-age
    res_https = client.get("/test", headers={"X-Forwarded-Proto": "https"})
    assert res_https.status_code == 200
    assert "Strict-Transport-Security" in res_https.headers
    assert "max-age=" in res_https.headers["Strict-Transport-Security"]


def test_host_validation_valid():
    client = TestClient(_build_test_app())
    res = client.get("/test", headers={"Host": "api.etap.local"})
    assert res.status_code == 200


def test_host_validation_invalid():
    client = TestClient(_build_test_app())
    res = client.get("/test", headers={"Host": "invalid host!#@$"})
    assert res.status_code == 400
    assert "Invalid Host header" in res.json().get("detail", "")


def test_https_redirect_enforced(monkeypatch):
    monkeypatch.setenv("ENFORCE_HTTPS", "true")
    client = TestClient(_build_test_app(), base_url="http://testserver")
    res = client.get(
        "/test",
        headers={"X-Forwarded-Proto": "http", "Host": "etap.example.com"},
        follow_redirects=False,
    )
    assert res.status_code == 301
    assert res.headers["Location"].startswith("https://etap.example.com/test")


def test_https_redirect_not_enforced_when_proto_is_https(monkeypatch):
    monkeypatch.setenv("ENFORCE_HTTPS", "true")
    client = TestClient(_build_test_app(), base_url="http://testserver")
    res = client.get(
        "/test",
        headers={"X-Forwarded-Proto": "https", "Host": "etap.example.com"},
    )
    assert res.status_code == 200
