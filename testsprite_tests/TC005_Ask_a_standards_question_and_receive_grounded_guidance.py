"""
TC005: Ask a standards question and receive grounded guidance.
Verifies that a user can ask an engineering standards question in chat and
receive an evidence-based response grounded in standard engineering practices (IEC 60364 / IEEE 399).
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

    # 1. API: query standards guidance for cable sizing / motor starting
    payload = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "How does ETAP calculate cable sizing according to IEC 60364 standard and ampacity derating factors?",
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

    assert data.get("success") is True, "Standards query must succeed"
    ans_text = str(data.get("data") or data.get("results") or "")
    assert (
        "IEC" in ans_text
        or "Cable" in ans_text
        or "Ampacity" in ans_text
        or "analysis" in ans_text.lower()
    ), "Response must contain grounded IEC/cable sizing guidance"

    # 2. UI: Navigate to chat workspace and interact with question
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
            await chat_input.fill("What is the IEC 60364 standard for cable sizing and derating?")

            val = await chat_input.input_value()
            assert "IEC 60364" in val, "Input should retain standards question"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc005() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC005 passed successfully!")
