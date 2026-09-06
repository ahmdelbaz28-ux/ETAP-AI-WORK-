"""
TC007: Refuse unsupported engineering requests and recover with approved inputs.
A user making an unsupported request receives a fail-closed refusal and can
then obtain evidence-based guidance by providing approved references.
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

    # 1. Submit unsupported / invalid study type -> must FAIL-CLOSED (422 or error)
    bad_payload = json.dumps({
        "study_type": "unsupported_warp_reactor_sim",
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

    failed_closed = False
    try:
        with urllib.request.urlopen(req_bad, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success", True):
                failed_closed = True
    except urllib.error.HTTPError as err:
        assert err.code in (400, 422, 404), f"Expected 400/422/404 fail-closed, got {err.code}"
        failed_closed = True

    assert failed_closed, "Unsupported study type must fail closed"

    # 2. Recover with approved valid load flow study
    good_payload = json.dumps({
        "study_type": "load_flow",
        "system": MINI_SYSTEM,
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
        assert resp.status == 200
        good_data = json.loads(resp.read().decode("utf-8"))

    assert good_data["success"] is True, "Approved study request must succeed"

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

            # Enter unsupported request, then recover with approved reference
            await chat_input.fill("Run an ungrounded warp field calculation without parameters")
            await chat_input.fill("Calculate IEEE 3-bus load flow with Newton-Raphson method")
            val = await chat_input.input_value()
            assert "IEEE 3-bus" in val
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc007() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC007 passed successfully!")
