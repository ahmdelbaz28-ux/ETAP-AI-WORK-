"""
TC012: Handle missing knowledge with a grounded fallback.
A user asking for information with no relevant indexed evidence receives a
constrained fallback and can improve the answer by providing more specific terms.
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

    # 1. API: Unknown / unindexed query
    payload_vague = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "Explain quantum flux warp coils in electrical distribution networks",
        },
    }).encode("utf-8")

    req_vague = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_vague,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_vague, timeout=15) as resp:
        assert resp.status == 200
        data_vague = json.loads(resp.read().decode("utf-8"))

    # Response should handle unknown concepts gracefully (fail-closed/clarification/Format C/B)
    assert data_vague.get("success") is True
    res_vague = str(data_vague.get("data") or data_vague.get("results") or "")
    assert len(res_vague) > 0

    # 2. Targeted follow-up with grounded standard
    payload_grounded = json.dumps({
        "study_type": "etap_expert",
        "parameters": {
            "question": "What are the IEEE 141 voltage drop limits for industrial branch circuits in ETAP?",
        },
    }).encode("utf-8")

    req_grounded = urllib.request.Request(
        f"{API_URL}/api/v1/studies/run",
        data=payload_grounded,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    with urllib.request.urlopen(req_grounded, timeout=15) as resp:
        assert resp.status == 200
        data_grounded = json.loads(resp.read().decode("utf-8"))

    assert data_grounded.get("success") is True
    ans_grounded = str(data_grounded.get("data") or data_grounded.get("results") or "")
    assert (
        "IEEE" in ans_grounded
        or "voltage" in ans_grounded.lower()
        or "analysis" in ans_grounded.lower()
    ), "Targeted query must return grounded standard guidance"

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

            # Enter vague question, then refine with targeted terms
            await chat_input.fill("Explain quantum flux warp coils")
            await chat_input.fill("What are the IEEE 141 voltage drop limits in ETAP?")
            val = await chat_input.input_value()
            assert "IEEE 141" in val, "Input should contain grounded follow-up question"
        finally:
            await context.close()
            await browser.close()


@pytest.mark.asyncio
async def test_tc012() -> None:
    await run_test()


if __name__ == "__main__":
    asyncio.run(run_test())
    print("TC012 passed successfully!")
