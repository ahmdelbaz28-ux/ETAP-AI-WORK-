"""
TC014: Open a known result after an invalid result lookup.
Verifies that an unknown or expired result reference is handled gracefully (404/422/error),
and a valid study result can still be executed and opened afterward.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
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

    # 1. Invalid study / result lookup reference -> verify handled with error (404 / 422)
    bad_payload = json.dumps({
        "study_type": "nonexistent_study_result_lookup",
        "system": MINI_SYSTEM,
    }).encode("utf-8")

    req_bad = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=bad_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    invalid_handled = False
    try:
        with urllib.request.urlopen(req_bad, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success", True):
                invalid_handled = True
    except urllib.error.HTTPError as err:
        assert err.code in (400, 404, 422), f"Expected error code for invalid lookup, got {err.code}"
        invalid_handled = True

    assert invalid_handled, "Invalid result lookup must be rejected or handled with not found state"

    # 2. Open / run known valid study result
    good_payload = json.dumps({
        "study_type": "load_flow",
        "system": MINI_SYSTEM,
        "params": {
            "method": "newton-raphson",
            "base_mva": 100.0,
            "tolerance": 0.0001,
        },
    }).encode("utf-8")

    req_good = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=good_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_good, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 OK, got {resp.status}"
        data_good = json.loads(resp.read().decode("utf-8"))

    assert data_good["success"] is True, "Valid study must succeed"
    assert "resultId" in data_good or "task_id" in data_good
    results = data_good.get("data") or data_good.get("results") or {}
    assert "bus_voltages" in results or "summary" in results, "Computation results must be returned"

    # 3. UI interaction
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

            # Check study workspace and form controls are accessible
            form = page.locator("form").first
            await form.wait_for(state="visible", timeout=15000)
            assert await form.is_visible(), "Study form must be visible"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc014() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC014 passed successfully!")
