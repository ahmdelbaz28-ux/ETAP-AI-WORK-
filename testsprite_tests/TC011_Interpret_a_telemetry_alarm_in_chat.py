"""
TC011: Interpret a telemetry alarm in chat.
A user can ask chat to interpret a current telemetry state and receive
operational guidance for investigating the event.
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
    fetch_auth_token,
    fetch_csrf_token,
    setup_authenticated_context,
)


async def run_test() -> None:
    csrf_token = fetch_csrf_token()
    auth_data = fetch_auth_token()
    access_token = auth_data["access_token"]

    # 1. API: Query interpretation of telemetry alarm (e.g. undervoltage alarm)
    payload = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Telemetry alarm: Bus 2 voltage dropped to 0.88 pu under heavy load, what are the recommended operational actions in ETAP and IEEE 3002.7?",
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
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))

    assert data.get("success") is True, "Telemetry alarm analysis must succeed"
    ans_text = str(data.get("data") or data.get("results") or "")
    assert (
        "voltage" in ans_text.lower()
        or "load flow" in ans_text.lower()
        or "analysis" in ans_text.lower()
    ), "Response must provide operational voltage guidance"

    # 2. UI flow: Digital Twin observation -> Chat interpretation
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            # Login
            await page.goto(f"{APP_URL}/login", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            await page.locator("#login-email").fill(E2E_EMAIL)
            await page.locator("#login-password").fill(E2E_PASSWORD)
            await page.locator("button[type='submit']").first.click()

            # View Digital Twin
            await setup_authenticated_context(context, page)
            await page.goto(f"{APP_URL}/advanced/digital-twin", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            heading = page.locator("h1, h2, [role='heading']").first
            await heading.wait_for(state="visible", timeout=15000)

            # Switch to chat workspace to interpret alarm
            await page.goto(f"{APP_URL}/assistant", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            chat_input = page.locator("textarea, input[type='text']").first
            await chat_input.wait_for(state="visible", timeout=15000)
            await chat_input.fill("Interpret alarm: Bus 2 voltage dropped to 0.88 pu")
            val = await chat_input.input_value()
            assert "0.88 pu" in val, "Input should retain alarm interpretation query"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc011() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC011 passed successfully!")
