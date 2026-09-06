"""
testsprite_tests/conftest.py — Shared fixtures and engineering utilities for TestSprite E2E suite.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, AsyncGenerator, Dict

import pytest
from playwright.async_api import BrowserContext, Page, async_playwright

APP_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"

E2E_USERNAME = "e2e"
E2E_EMAIL = "e2e@test.local"
E2E_PASSWORD = os.environ.get("E2E_USER_PASSWORD", "Test123!")

# Validated IEEE 3-bus test system fixture (IEEE 3002.7 / IEC 60909)
MINI_SYSTEM: Dict[str, Any] = {
    "base_mva": 100.0,
    "buses": [
        {
            "bus_id": 1,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "slack",
            "base_kv": 20.0,
        },
        {
            "bus_id": 2,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "pq",
            "base_kv": 20.0,
        },
        {
            "bus_id": 3,
            "voltage_magnitude": 1.0,
            "voltage_angle": 0.0,
            "bus_type": "pv",
            "base_kv": 20.0,
        },
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02, "x1": 0.08, "bshunt1": 0.0},
        {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.02, "x1": 0.08, "bshunt1": 0.0},
    ],
    "generators": [
        {"generator_id": 1, "bus_id": 1, "internal_voltage_mag": 1.0},
        {"generator_id": 2, "bus_id": 3, "internal_voltage_mag": 1.0},
    ],
    "loads": [
        {"load_id": 1, "bus_id": 2, "p_mw": 0.8, "q_mvar": 0.6},
    ],
    "transformers": [],
}


def fetch_csrf_token() -> str:
    """Fetch fresh CSRF token from engineering service."""
    req = urllib.request.Request(f"{API_URL}/api/v1/csrf/token")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return str(data["token"])


def fetch_auth_token() -> Dict[str, str]:
    """Authenticate e2e test user and return access+refresh tokens."""
    csrf_token = fetch_csrf_token()
    payload = json.dumps({"username": E2E_EMAIL, "password": E2E_PASSWORD}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/v1/auth/login",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return {
            "access_token": str(data["access_token"]),
            "refresh_token": str(data.get("refresh_token", "")),
            "csrf_token": csrf_token,
        }


async def setup_authenticated_context(
    context: BrowserContext,
    page: Page,
) -> Dict[str, str]:
    """Inject JWT access token into sessionStorage before navigating."""
    tokens = fetch_auth_token()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    await context.add_init_script(f"""
        window.sessionStorage.setItem('authToken', '{access_token}');
        window.sessionStorage.setItem('refreshToken', '{refresh_token}');
    """)
    return tokens


@pytest.fixture(scope="session")
def auth_tokens() -> Dict[str, str]:
    return fetch_auth_token()


@pytest.fixture
async def e2e_page() -> AsyncGenerator[Page, None]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()
            await browser.close()
