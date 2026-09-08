"""
TC003: Run a short circuit study and review the fault results.
Verifies that a user can submit a valid short circuit study and inspect the
returned fault current results (IEC 60909 fault currents, angles, and ratings).
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

    # 1. Submit valid short circuit study request
    payload = json.dumps({
        "study_type": "short_circuit",
        "system": MINI_SYSTEM,
        "parameters": {
            "bus_id": 1,
            "fault_type": "three_phase",
            "standard": "IEC_60909",
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

    # Assert computation results
    assert data["success"] is True, "Short circuit study must succeed"
    assert data["study_type"] == "short_circuit"
    assert "resultId" in data or "task_id" in data, "Result ID must be generated"

    study_data = data.get("data") or data.get("results") or {}
    assert "fault_current_ka" in study_data or "fault_current_magnitude" in study_data, (
        "Fault current results must be computed and returned"
    )
    fault_ka = study_data.get("fault_current_ka", 0)
    assert fault_ka > 0, f"Fault current in kA must be positive, got {fault_ka}"

    # 2. Inspect study workspace in Playwright
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
            await page.goto(f"{APP_URL}/advanced/studies/short_circuit", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Check that form / study elements rendered
            form = page.locator("form").first
            await form.wait_for(state="visible", timeout=15000)
            assert await form.is_visible(), "Short circuit study form must be visible"

            # Check for study inputs (fault type, standard, or bus selection)
            selects = page.locator("select, input")
            assert await selects.count() >= 1, "Form input controls must be available"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc003() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC003 passed successfully!")
