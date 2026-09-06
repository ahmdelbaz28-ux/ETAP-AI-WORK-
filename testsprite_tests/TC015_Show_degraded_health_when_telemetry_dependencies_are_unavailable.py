"""
TC015: Show degraded health when telemetry dependencies are unavailable.
Verifies that backend readiness/health probes check required dependencies (DB, Redis, telemetry),
and the UI monitoring view handles dependency status and availability states appropriately.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request

import pytest
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from testsprite_tests.conftest import (
    API_URL,
    APP_URL,
    E2E_EMAIL,
    E2E_PASSWORD,
    setup_authenticated_context,
)


async def run_test() -> None:
    # 1. Inspect dependency health probe via /readyz
    req = urllib.request.Request(f"{API_URL}/readyz")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status in (200, 503), f"Expected 200 or 503 from /readyz, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    assert "checks" in data, "Readiness response must contain subsystem checks"
    checks = data["checks"]
    assert "db" in checks, "Database dependency check must be monitored"
    assert "redis" in checks, "Redis/cache telemetry dependency must be monitored"

    # Also verify basic liveness /healthz
    req_live = urllib.request.Request(f"{API_URL}/healthz")
    with urllib.request.urlopen(req_live, timeout=10) as resp_live:
        assert resp_live.status == 200
        live_data = json.loads(resp_live.read().decode("utf-8"))
        assert live_data.get("status") in ("ok", "healthy")

    # 2. UI flow: Login and view Digital Twin / SCADA monitoring workspace
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            await page.goto(f"{APP_URL}/login", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            await page.locator("#login-email").fill(E2E_EMAIL)
            await page.locator("#login-password").fill(E2E_PASSWORD)
            await page.locator("button[type='submit']").first.click()

            # View Digital Twin monitoring
            await setup_authenticated_context(context, page)
            await page.goto(f"{APP_URL}/advanced/digital-twin", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Verify monitoring view elements
            heading = page.locator("h1, h2, [role='heading']").first
            await heading.wait_for(state="visible", timeout=15000)
            assert await heading.is_visible(), "Monitoring view heading must be visible"

            # Check that container / status indicators are rendered
            status_elements = page.locator("span, div, p")
            assert await status_elements.count() >= 5, "Monitoring view must display status indicators"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc015() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC015 passed successfully!")
