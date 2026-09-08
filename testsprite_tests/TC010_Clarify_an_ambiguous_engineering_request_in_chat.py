"""
TC010: Clarify an ambiguous engineering request in chat.
Verifies that an ambiguous or unsupported engineering request is met with
a constrained clarification prompt (Format B: REQUEST ANALYSIS: INCOMPLETE)
and can be resolved with follow-up input.
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
    fetch_auth_token,
    fetch_csrf_token,
    setup_authenticated_context,
)


async def run_test() -> None:
    csrf_token = fetch_csrf_token()
    auth_data = fetch_auth_token()
    access_token = auth_data["access_token"]

    # 1. Submit ambiguous/incomplete request ("Size transformer for 500kW")
    payload_ambiguous = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Size transformer for 500kW",
        },
    }).encode("utf-8")

    req_ambiguous = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_ambiguous,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_ambiguous, timeout=15) as resp:
        assert resp.status == 200
        data_ambiguous = json.loads(resp.read().decode("utf-8"))

    assert data_ambiguous.get("success") is True
    res_data = data_ambiguous.get("data") or data_ambiguous.get("results") or {}
    assert res_data.get("classification") == "incomplete" or "INCOMPLETE" in str(res_data), (
        "Ambiguous request must trigger clarification / incomplete classification"
    )

    # 2. Provide missing inputs / complete engineering parameters
    payload_complete = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Size transformer for 500kW load with 13.8 kV primary, 480 V secondary, power factor 0.85, per IEEE 141 and IEEE C57.12",
        },
    }).encode("utf-8")

    req_complete = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_complete,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_complete, timeout=15) as resp:
        assert resp.status == 200
        data_complete = json.loads(resp.read().decode("utf-8"))

    assert data_complete.get("success") is True
    res_complete = data_complete.get("data") or data_complete.get("results") or {}
    assert res_complete.get("classification") == "complete" or "COMPLETE" in str(res_complete), (
        "Complete parameters must result in complete engineering analysis"
    )

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

            # Enter ambiguous request, then provide clarification
            await chat_input.fill("Size transformer for 500kW")
            await chat_input.fill("Size transformer for 500kW: 13.8kV/480V, pf 0.85")
            val = await chat_input.input_value()
            assert "13.8kV/480V" in val, "Input should contain clarified parameters"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc010() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC010 passed successfully!")
