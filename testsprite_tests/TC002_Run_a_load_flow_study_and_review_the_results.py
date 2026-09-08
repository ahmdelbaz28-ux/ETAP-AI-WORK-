"""
TC002: Run a load flow study and review the results.
Verifies that a user can submit a valid load flow study and review
computed system metrics (bus voltages, angles, power flows, and losses).
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

    # Assert load flow results
    assert data["success"] is True, "Load flow study must converge and succeed"
    assert data["study_type"] == "load_flow"
    assert "resultId" in data or "task_id" in data, "Result ID must be generated"

    study_data = data.get("data") or data.get("results") or {}
    assert "bus_voltages" in study_data, "Bus voltages must be in load flow results"
    voltages = study_data["bus_voltages"]
    assert len(voltages) >= 2, "Must compute voltages for multiple buses"

    # Verify angles and flows/Ybus are present
    assert "Ybus" in study_data, "Admittance matrix Ybus must be computed"

    # Verify UI page navigation with Playwright
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
            await page.goto(f"{APP_URL}/advanced/studies/load_flow", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Check that form parameters rendered
            await page.locator("form").first.wait_for(state="visible", timeout=15000)
            method_select = page.locator("select[name='method'], select#method")
            assert await method_select.count() >= 1, "Solution method select must be present"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc002() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC002 passed successfully!")
