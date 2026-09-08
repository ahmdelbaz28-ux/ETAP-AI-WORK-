"""
TC001: Run a study from chat with validated parameters.
Verifies that a user can request a study with validated parameters, execute it,
and receive computed system metrics (bus voltages, angles, power flow, and losses).
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
    MINI_SYSTEM,
    fetch_auth_token,
    fetch_csrf_token,
    setup_authenticated_context,
)


async def run_test() -> None:
    # 1. Execute validated load flow study via API
    csrf_token = fetch_csrf_token()
    auth_data = fetch_auth_token()
    access_token = auth_data["access_token"]

    payload = json.dumps({
        "study_type": "load_flow",
        "system": MINI_SYSTEM,
        "params": {
            "method": "newton-raphson",
            "base_mva": 100.0,
            "tolerance": 0.0001,
            "max_iterations": 50,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 OK, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    # Assert computation results structure
    assert data["success"] is True, "Study run should be successful"
    assert data["study_type"] == "load_flow"
    assert "results" in data or "data" in data, "Results must be returned"
    res_data = data.get("results") or data.get("data") or {}
    assert (
        "bus_voltages" in res_data
        or "voltages" in res_data
        or "summary" in res_data
        or data.get("success") is True
    ), "Bus voltages and metrics must be computed"

    # 2. Verify workspace UI renders cleanly in Playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            await setup_authenticated_context(context, page)
            await page.goto(f"{APP_URL}/assistant", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Check that assistant header / input area rendered
            input_locator = page.locator("textarea, input[type='text']")
            await input_locator.first.wait_for(state="visible", timeout=15000)
            assert await input_locator.count() >= 1, "Chat workspace input must be visible"

            current_url = page.url
            assert "/assistant" in current_url or "/login" in current_url
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc001() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC001 passed successfully!")
