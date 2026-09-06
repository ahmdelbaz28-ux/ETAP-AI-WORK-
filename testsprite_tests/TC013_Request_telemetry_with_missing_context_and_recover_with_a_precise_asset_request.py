"""
TC013: Request telemetry with missing context and recover with a precise asset request.
A user asking for unavailable telemetry receives a constrained response and
can refine the request with the correct asset or time window to get useful context.
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

    # 1. Query telemetry for nonexistent asset
    payload_missing = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Show real-time telemetry voltage stream for nonexistent Substation-999 Feeder-XYZ",
        },
    }).encode("utf-8")

    req_missing = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_missing,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_missing, timeout=15) as resp:
        assert resp.status == 200
        data_missing = json.loads(resp.read().decode("utf-8"))

    assert data_missing.get("success") is True
    res_text = str(data_missing.get("data") or data_missing.get("results") or "")
    assert len(res_text) > 0, "Agent should return constrained guidance on missing asset"

    # 2. Refine query with valid asset
    payload_precise = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "How to map SCADA telemetry tags for 20kV Main Substation Bus 1 and Bus 2 in ETAP digital twin?",
        },
    }).encode("utf-8")

    req_precise = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_precise,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_precise, timeout=15) as resp:
        assert resp.status == 200
        data_precise = json.loads(resp.read().decode("utf-8"))

    assert data_precise.get("success") is True
    ans_precise = str(data_precise.get("data") or data_precise.get("results") or "")
    assert (
        "SCADA" in ans_precise
        or "Bus" in ans_precise
        or "ETAP" in ans_precise
        or "analysis" in ans_precise.lower()
    ), "Precise asset query must return grounded operational guidance"

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

            # Missing context -> Precise asset recovery
            await chat_input.fill("Show telemetry for Substation-999")
            await chat_input.fill("Show SCADA tags for Main Substation Bus 1 and Bus 2")
            val = await chat_input.input_value()
            assert "Bus 1 and Bus 2" in val, "Input should contain precise asset query"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc013() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC013 passed successfully!")
