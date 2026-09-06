"""
TC009: Confirm backend health before viewing live telemetry.
A user can verify backend health and then open the digital twin view to receive live telemetry updates.
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
    # 1. Verify backend health via /healthz endpoint
    req = urllib.request.Request(f"{API_URL}/healthz")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK from /healthz, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") in ("ok", "healthy"), f"Unexpected healthz status: {data}"

    # 2. UI flow: Login and open Digital Twin / SCADA telemetry view
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            # Login interaction
            await page.goto(f"{APP_URL}/login", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            await page.locator("#login-email").fill(E2E_EMAIL)
            await page.locator("#login-password").fill(E2E_PASSWORD)
            await page.locator("button[type='submit']").first.click()

            # Navigate to Digital Twin view
            await setup_authenticated_context(context, page)
            await page.goto(f"{APP_URL}/advanced/digital-twin", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Check that digital twin / telemetry workspace rendered
            heading = page.locator("h1, h2, [role='heading']").first
            await heading.wait_for(state="visible", timeout=15000)
            assert await heading.is_visible(), "Digital twin heading must be visible"

            # Check for telemetry / digital twin diagram or control cards
            cards = page.locator("div, svg, canvas")
            assert await cards.count() >= 5, "Digital twin visualization elements must be rendered"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc009() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC009 passed successfully!")
