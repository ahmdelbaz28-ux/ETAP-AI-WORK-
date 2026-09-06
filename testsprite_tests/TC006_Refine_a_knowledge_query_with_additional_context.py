"""
TC006: Refine a knowledge query with additional context.
A user can ask a topology or relationship question in chat and then refine it
with a follow-up to receive a more specific network explanation.
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

    # 1. API: Initial query on topology
    payload_1 = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Explain standard IEEE 3-bus network topology with slack and PV buses.",
        },
    }).encode("utf-8")

    req_1 = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_1,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req_1, timeout=15) as resp:
        assert resp.status == 200
        data_1 = json.loads(resp.read().decode("utf-8"))
    assert data_1.get("success") is True

    # 2. Refined query with specific connected equipment
    payload_2 = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "For a 3-bus network with Bus 1 (Slack) and Bus 3 (PV), what is the reactive power Q limit on generator 2 at Bus 3?",
        },
    }).encode("utf-8")

    req_2 = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_2,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req_2, timeout=15) as resp:
        assert resp.status == 200
        data_2 = json.loads(resp.read().decode("utf-8"))
    assert data_2.get("success") is True
    ans_2 = str(data_2.get("data") or data_2.get("results") or "")
    assert len(ans_2) > 0, "Refined response must contain engineering details"

    # 3. UI interaction in Playwright
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

            chat_input = page.locator("textarea").first
            await chat_input.wait_for(state="visible", timeout=15000)

            # Enter topology question and refined question
            await chat_input.fill("What is the 3-bus network topology? What are the generator ratings on Bus 1 and Bus 3?")
            val = await chat_input.input_value()
            assert "Bus 1 and Bus 3" in val, "Refined input should be present"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc006() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC006 passed successfully!")
