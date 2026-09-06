"""
TC008: Correct an invalid study submission and run it successfully.
Verifies that invalid study parameters are rejected, then accepted after
correction, with a valid result returned.
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

    # 1. Incomplete / invalid payload (missing required 'system' network elements)
    invalid_payload = json.dumps({
        "study_type": "load_flow",
        "system": {"buses": [], "lines": []},
    }).encode("utf-8")

    req_invalid = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=invalid_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    validation_error_seen = False
    try:
        with urllib.request.urlopen(req_invalid, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success", True) or data.get("errors"):
                validation_error_seen = True
    except urllib.error.HTTPError as err:
        assert err.code in (400, 422), f"Expected 400/422 validation error, got {err.code}"
        validation_error_seen = True

    assert validation_error_seen, "Incomplete study submission must be rejected with validation error"

    # 2. Corrected valid load flow submission
    valid_payload = json.dumps({
        "study_type": "load_flow",
        "system": MINI_SYSTEM,
        "params": {
            "method": "newton-raphson",
            "base_mva": 100.0,
            "tolerance": 0.0001,
            "max_iterations": 50,
        },
    }).encode("utf-8")

    req_valid = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=valid_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_valid, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 OK, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    assert data["success"] is True, "Corrected study submission must succeed"
    assert "resultId" in data or "task_id" in data, "Result ID must be present"

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

            # Check form exists and is ready for inputs
            form = page.locator("form").first
            await form.wait_for(state="visible", timeout=15000)
            assert await form.is_visible()
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc008() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC008 passed successfully!")
