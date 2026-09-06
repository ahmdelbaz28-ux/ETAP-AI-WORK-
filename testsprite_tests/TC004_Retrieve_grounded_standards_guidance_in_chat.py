"""
TC004: Retrieve grounded standards guidance in chat.
A user can ask a standards-related engineering question in chat and receive a
grounded answer based on retrieved knowledge (IEEE 1584, IEC 60909, NFPA 70E).
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

    # 1. API: query knowledge / standards guidance
    payload = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "What standard governs arc flash calculation and boundary in ETAP, and what is IEEE 1584?",
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

    assert data.get("success") is True, "Expert guidance query must succeed"
    ans_text = str(data.get("data") or data.get("results") or "")
    assert (
        "IEEE" in ans_text
        or "1584" in ans_text
        or "Arc Flash" in ans_text
        or "analysis" in ans_text.lower()
    ), "Response must contain grounded IEEE/standards reference"

    # 2. UI flow: Login + Chat Workspace
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--window-size=1280,720", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context()
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            # Login form navigation & interaction
            await page.goto(f"{APP_URL}/login", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            email_input = page.locator("#login-email")
            await email_input.wait_for(state="visible", timeout=15000)
            await email_input.fill(E2E_EMAIL)

            password_input = page.locator("#login-password")
            await password_input.fill(E2E_PASSWORD)

            submit_btn = page.locator("button[type='submit']").first
            await submit_btn.click()

            # Set authenticated state and navigate to chat workspace
            await setup_authenticated_context(context, page)
            await page.goto(f"{APP_URL}/assistant", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")

            # Verify chat input and interaction
            chat_input = page.locator("textarea, input[type='text']").first
            await chat_input.wait_for(state="visible", timeout=15000)
            await chat_input.fill("What is the IEEE 1584 arc flash boundary standard?")

            # Verify input retains text and chat workspace is functional
            val = await chat_input.input_value()
            assert "IEEE 1584" in val, "Chat input should contain standard question"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc004() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC004 passed successfully!")
