"""
TC016: Recover from a malformed chat submission.
Verifies that a malformed chat payload is rejected with a validation error (HTTP 422),
and a valid message can then receive a grounded engineering response.
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
    fetch_auth_token,
    fetch_csrf_token,
    setup_authenticated_context,
)


async def run_test() -> None:
    csrf_token = fetch_csrf_token()
    auth_data = fetch_auth_token()
    access_token = auth_data["access_token"]

    # 1. Send malformed chat payload (e.g. invalid types or missing required fields)
    malformed_payload = json.dumps({
        "messages": "not-a-valid-list-of-messages",
        "invalid_extra_field": 12345,
    }).encode("utf-8")

    req_malformed = urllib.request.Request(
        f"{API_URL}/api/v1/chat/stream",
        data=malformed_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    validation_rejected = False
    try:
        with urllib.request.urlopen(req_malformed, timeout=10) as resp:
            if resp.status != 200:
                validation_rejected = True
    except urllib.error.HTTPError as err:
        assert err.code in (400, 422), f"Expected 400 or 422 validation error, got {err.code}"
        validation_rejected = True

    assert validation_rejected, "Malformed chat payload must be rejected with 422/400 validation error"

    # 2. Recover with valid engineering message
    valid_payload = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "What are the IEEE 399 recommendations for motor starting study analysis in ETAP?",
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
        data_valid = json.loads(resp.read().decode("utf-8"))

    assert data_valid.get("success") is True, "Valid engineering request must succeed"
    ans_text = str(data_valid.get("data") or data_valid.get("results") or "")
    assert (
        "IEEE" in ans_text
        or "motor" in ans_text.lower()
        or "analysis" in ans_text.lower()
    ), "Response must contain grounded engineering guidance"

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
            await page.goto(f"{APP_URL}/assistant", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            chat_input = page.locator("textarea, input[type='text']").first
            await chat_input.wait_for(state="visible", timeout=15000)

            # Enter recovered valid question
            await chat_input.fill("IEEE 399 motor starting recommendation in ETAP")
            val = await chat_input.input_value()
            assert "IEEE 399" in val, "Input should retain valid engineering message"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc016() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC016 passed successfully!")
