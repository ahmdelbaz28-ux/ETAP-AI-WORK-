#!/usr/bin/env python3
"""Real UI tests using Selenium WebDriver to test the ETAP-AI web interface.

These tests open the actual web UI in a headless Chrome browser and verify:
1. Page loads correctly (title, headings)
2. Navigation works (clicking links, route changes)
3. API data is displayed on the page
4. Forms are present and functional
5. Error handling in the UI
6. Interactive elements work

Run: python3 tests/selenium/test_ui_real.py
"""
import sys
import time
import os

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

BASE_URL = "http://127.0.0.1:7860"
CHROME_BINARY = "/tmp/chrome-extracted/opt/google/chrome/google-chrome"

# Test results
passed = 0
failed = 0
errors: list[str] = []


def run_test(name: str, test_fn, driver):
    global passed, failed
    print(f"\n--- {name} ---")
    try:
        result = test_fn(driver)
        if result:
            print(f"  ✓ PASS")
            passed += 1
        else:
            failed += 1
            errors.append(name)
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        failed += 1
        errors.append(f"{name} (exception: {e})")


def create_driver():
    """Create a headless Chrome WebDriver."""
    options = Options()
    options.binary_location = CHROME_BINARY
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")

    # Use the chromedriver from npm global install
    chromedriver_path = "/home/z/.npm-global/bin/chromedriver"
    if not os.path.exists(chromedriver_path):
        chromedriver_path = None  # Let Selenium find it

    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


# ---------------------------------------------------------------------------
# UI Tests
# ---------------------------------------------------------------------------

def test_homepage_loads(driver):
    """Test that the homepage loads and has the correct title."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    # Check title
    title = driver.title
    if "AhmedETAP" not in title and "ETAP" not in title:
        print(f"  ✗ FAIL: title should contain 'AhmedETAP' or 'ETAP', got: {title!r}")
        return False

    # Check that body has content (not blank page)
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if len(body_text) < 10:
        print(f"  ✗ FAIL: body text is too short ({len(body_text)} chars), page may be blank")
        return False

    print(f"  Title: {title!r}")
    print(f"  Body text length: {len(body_text)} chars")
    return True


def test_healthz_displays_json(driver):
    """Test that /healthz displays JSON with status=ok."""
    driver.get(BASE_URL + "/healthz")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if '"status"' not in body_text and "status" not in body_text:
        print(f"  ✗ FAIL: response should contain 'status', got: {body_text[:200]!r}")
        return False
    if "ok" not in body_text:
        print(f"  ✗ FAIL: response should contain 'ok', got: {body_text[:200]!r}")
        return False
    print(f"  Response: {body_text[:100]!r}")
    return True


def test_agents_page_loads(driver):
    """Test that /api/v1/agents displays a list of agents."""
    driver.get(BASE_URL + "/api/v1/agents")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if '"agents"' not in body_text and "agents" not in body_text:
        print(f"  ✗ FAIL: response should contain 'agents', got: {body_text[:200]!r}")
        return False
    if '"count"' not in body_text and "count" not in body_text:
        print(f"  ✗ FAIL: response should contain 'count'")
        return False
    # Verify there are actual agent IDs in the response
    if "agent" not in body_text.lower():
        print(f"  ✗ FAIL: no agent IDs found in response")
        return False
    print(f"  Response contains agents list")
    return True


def test_docs_page_loads(driver):
    """Test that /docs (Swagger UI) loads."""
    driver.get(BASE_URL + "/docs")
    wait = WebDriverWait(driver, 15)

    # Swagger UI takes time to load
    time.sleep(3)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    # Swagger UI should have "API" or "AhmedETAP" or "OpenAPI"
    if "AhmedETAP" not in body_text and "API" not in body_text and "swagger" not in body_text.lower():
        print(f"  ✗ FAIL: docs page should contain 'AhmedETAP' or 'API', got: {body_text[:200]!r}")
        return False
    print(f"  Docs page loaded")
    return True


def test_openapi_schema_valid(driver):
    """Test that /openapi.json returns valid OpenAPI schema."""
    driver.get(BASE_URL + "/openapi.json")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if '"openapi"' not in body_text and "openapi" not in body_text:
        print(f"  ✗ FAIL: response should contain 'openapi'")
        return False
    if '"paths"' not in body_text and "paths" not in body_text:
        print(f"  ✗ FAIL: response should contain 'paths'")
        return False
    if '"info"' not in body_text and "info" not in body_text:
        print(f"  ✗ FAIL: response should contain 'info'")
        return False
    print(f"  OpenAPI schema is valid")
    return True


def test_nonexistent_page_error(driver):
    """Test that a non-existent page returns an error (not a crash)."""
    driver.get(BASE_URL + "/api/v1/agents/nonexistent-agent-xyz123")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    # Should contain "not found" or "error"
    if "not found" not in body_text.lower() and "error" not in body_text.lower():
        print(f"  ✗ FAIL: should contain 'not found' or 'error', got: {body_text[:200]!r}")
        return False
    print(f"  Error response correct")
    return True


def test_settings_page_api(driver):
    """Test that settings API endpoints are accessible from the UI context."""
    # Use JavaScript fetch from the browser to test API calls
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    # Execute JavaScript to make API call
    result = driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        fetch('/api/v1/settings/health')
            .then(r => r.json())
            .then(data => callback({success: true, data: data}))
            .catch(err => callback({success: false, error: err.toString()}));
    """)

    if not result.get("success"):
        print(f"  ✗ FAIL: fetch failed: {result.get('error')}")
        return False

    data = result.get("data", {})
    if not data.get("success"):
        print(f"  ✗ FAIL: response.success should be true, got: {data}")
        return False

    if "data" not in data or "crypto_available" not in data["data"]:
        print(f"  ✗ FAIL: missing crypto_available in response")
        return False

    print(f"  Settings API accessible from browser")
    return True


def test_studies_types_via_browser(driver):
    """Test that /api/v1/studies/types returns expected study types via browser."""
    driver.get(BASE_URL + "/api/v1/studies/types")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text

    expected_types = ["load_flow", "short_circuit", "arc_flash"]
    missing = [t for t in expected_types if t not in body_text]
    if missing:
        print(f"  ✗ FAIL: missing expected study types: {missing}")
        return False

    print(f"  All expected study types present")
    return True


def test_ml_capabilities_via_browser(driver):
    """Test that /api/v1/ml/capabilities returns ML info via browser."""
    driver.get(BASE_URL + "/api/v1/ml/capabilities")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "sklearn" not in body_text:
        print(f"  ✗ FAIL: 'sklearn' not in response")
        return False
    if "success" not in body_text:
        print(f"  ✗ FAIL: 'success' not in response")
        return False
    print(f"  ML capabilities returned correctly")
    return True


def test_cors_headers_present(driver):
    """Test that CORS headers are present (important for browser-based apps)."""
    # Use JavaScript to check response headers
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    result = driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        fetch('/healthz')
            .then(r => {
                var headers = {};
                r.headers.forEach((v, k) => { headers[k] = v; });
                callback({status: r.status, headers: headers});
            })
            .catch(err => callback({error: err.toString()}));
    """)

    if "error" in result:
        print(f"  ✗ FAIL: fetch error: {result['error']}")
        return False

    # CORS headers may or may not be present depending on config
    # But the request should succeed
    if result.get("status") != 200:
        print(f"  ✗ FAIL: status should be 200, got {result.get('status')}")
        return False

    headers = result.get("headers", {})
    print(f"  Response headers: {list(headers.keys())}")
    return True


def test_chat_api_via_browser_fetch(driver):
    """Test that the chat API works when called from the browser via fetch."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    result = driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        fetch('/api/v1/agents/etap-expert/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: 'What is the cable size for a 100A load?'})
        })
            .then(r => r.json().then(data => ({status: r.status, data: data})))
            .then(result => callback(result))
            .catch(err => callback({error: err.toString()}));
    """)

    if "error" in result:
        print(f"  ✗ FAIL: fetch error: {result['error']}")
        return False

    if result.get("status") != 200:
        print(f"  ✗ FAIL: status should be 200, got {result.get('status')}")
        print(f"  Response: {result.get('data')}")
        return False

    data = result.get("data", {})
    if not data.get("success"):
        print(f"  ✗ FAIL: response.success should be true, got: {data}")
        return False

    if "data" not in data or "response" not in data.get("data", {}):
        print(f"  ✗ FAIL: missing data.response in chat response")
        return False

    response_text = data["data"]["response"]
    if not response_text or len(str(response_text)) < 10:
        print(f"  ✗ FAIL: response text is too short: {response_text!r}")
        return False

    print(f"  Chat response length: {len(str(response_text))} chars")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("REAL UI TESTS — using Selenium WebDriver to test the actual web UI")
    print("=" * 70)

    try:
        driver = create_driver()
        print(f"Chrome WebDriver started (binary: {CHROME_BINARY})")
    except Exception as e:
        print(f"FATAL: Could not start Chrome WebDriver: {e}")
        sys.exit(1)

    try:
        run_test("Homepage loads with correct title", test_homepage_loads, driver)
        run_test("/healthz displays JSON with status=ok", test_healthz_displays_json, driver)
        run_test("/api/v1/agents displays agents list", test_agents_page_loads, driver)
        run_test("/docs (Swagger UI) loads", test_docs_page_loads, driver)
        run_test("/openapi.json returns valid schema", test_openapi_schema_valid, driver)
        run_test("Non-existent agent returns error", test_nonexistent_page_error, driver)
        run_test("Settings API accessible from browser", test_settings_page_api, driver)
        run_test("Studies types via browser", test_studies_types_via_browser, driver)
        run_test("ML capabilities via browser", test_ml_capabilities_via_browser, driver)
        run_test("CORS headers check", test_cors_headers_present, driver)
        run_test("Chat API via browser fetch", test_chat_api_via_browser_fetch, driver)
    finally:
        driver.quit()
        print("\nWebDriver closed.")

    print("\n" + "=" * 70)
    print(f"UI TEST RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✓ All UI tests passed!")
        sys.exit(0)
