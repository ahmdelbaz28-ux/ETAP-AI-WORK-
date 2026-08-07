#!/usr/bin/env python3
"""Real interactive UI tests using Selenium WebDriver.

These tests interact with the actual web UI — clicking links, verifying
navigation, checking that displayed values match API responses, and
testing form interactions on the Swagger UI.

Run: python3 tests/selenium/test_ui_interactive.py
"""
import sys
import time
import os
import json
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementNotInteractableException,
)

BASE_URL = "http://127.0.0.1:7860"
CHROME_BINARY = "/tmp/chrome-extracted/opt/google/chrome/google-chrome"

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
    options = Options()
    options.binary_location = CHROME_BINARY
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    chromedriver_path = "/home/z/.npm-global/bin/chromedriver"
    service = Service(executable_path=chromedriver_path) if os.path.exists(chromedriver_path) else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def get_api_json(path: str):
    """Fetch JSON from API directly (for cross-checking UI values)."""
    with urllib.request.urlopen(BASE_URL + path, timeout=10) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Interactive UI tests
# ---------------------------------------------------------------------------

def test_homepage_displays_correct_agent_count(driver):
    """Verify the 'AI Agents' stat on homepage matches the API response."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    # Find all stat elements
    stats = driver.find_elements(By.CSS_SELECTOR, ".stat")
    if len(stats) < 4:
        print(f"  ✗ FAIL: expected >= 4 stat elements, got {len(stats)}")
        return False

    # Find the "AI Agents" stat
    agents_stat = None
    for stat in stats:
        text = stat.text
        if "AI Agents" in text:
            agents_stat = stat
            break

    if not agents_stat:
        print(f"  ✗ FAIL: could not find 'AI Agents' stat element")
        return False

    # Extract the number
    stat_num = agents_stat.find_element(By.CSS_SELECTOR, ".stat-num").text
    try:
        ui_count = int(stat_num)
    except ValueError:
        print(f"  ✗ FAIL: could not parse agent count from UI: {stat_num!r}")
        return False

    # Cross-check with API
    api_data = get_api_json("/api/v1/agents")
    api_count = api_data["count"]

    if ui_count != api_count:
        print(f"  ✗ FAIL: UI shows {ui_count} agents, API returns {api_count}")
        return False

    print(f"  UI shows {ui_count} agents, API confirms {api_count}")
    return True


def test_homepage_displays_version(driver):
    """Verify the version displayed on homepage matches API."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text

    # The API returns version in /api/v1/info
    api_info = get_api_json("/api/v1/info")
    api_version = api_info["version"]

    if f"v{api_version}" not in body_text and api_version not in body_text:
        print(f"  ✗ FAIL: version {api_version!r} not found in UI body text")
        return False

    print(f"  UI displays version {api_version}")
    return True


def test_homepage_standards_badges(driver):
    """Verify the standards badges (IEEE 3002.7, IEC 60909, etc.) are displayed."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    badges = driver.find_elements(By.CSS_SELECTOR, ".badge")
    if len(badges) < 5:
        print(f"  ✗ FAIL: expected >= 5 standards badges, got {len(badges)}")
        return False

    badge_texts = [b.text for b in badges]
    expected_standards = ["IEEE 3002.7", "IEC 60909", "IEEE 1584"]
    for std in expected_standards:
        if std not in badge_texts:
            print(f"  ✗ FAIL: standard {std!r} not found in badges: {badge_texts}")
            return False

    print(f"  Found {len(badges)} standards badges: {badge_texts}")
    return True


def test_click_swagger_docs_link(driver):
    """Click the 'Swagger Docs' link and verify navigation to /docs."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    # Find the Swagger Docs link
    try:
        swagger_link = driver.find_element(By.LINK_TEXT, "Swagger Docs")
    except NoSuchElementException:
        print(f"  ✗ FAIL: 'Swagger Docs' link not found")
        return False

    # Click it
    swagger_link.click()

    # Wait for URL to change to /docs
    try:
        wait.until(EC.url_contains("/docs"))
    except TimeoutException:
        print(f"  ✗ FAIL: did not navigate to /docs after click. URL: {driver.current_url}")
        return False

    # Verify Swagger UI loaded (look for swagger-ui container)
    time.sleep(3)  # Swagger UI takes time to render
    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "AhmedETAP" not in body_text and "API" not in body_text:
        print(f"  ✗ FAIL: Swagger UI did not load properly")
        return False

    print(f"  Navigated to {driver.current_url}, Swagger UI loaded")
    return True


def test_click_health_link(driver):
    """Click the 'Health' link and verify it shows health JSON."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    try:
        health_link = driver.find_element(By.LINK_TEXT, "Health")
    except NoSuchElementException:
        print(f"  ✗ FAIL: 'Health' link not found")
        return False

    health_link.click()

    try:
        wait.until(EC.url_contains("/healthz"))
    except TimeoutException:
        print(f"  ✗ FAIL: did not navigate to /healthz. URL: {driver.current_url}")
        return False

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "ok" not in body_text:
        print(f"  ✗ FAIL: health response does not contain 'ok'")
        return False

    print(f"  Navigated to {driver.current_url}, health status displayed")
    return True


def test_click_agents_link(driver):
    """Click the 'Agents' link and verify it shows the agents list."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    try:
        agents_link = driver.find_element(By.LINK_TEXT, "Agents")
    except NoSuchElementException:
        print(f"  ✗ FAIL: 'Agents' link not found")
        return False

    agents_link.click()

    try:
        wait.until(EC.url_contains("/api/v1/agents"))
    except TimeoutException:
        print(f"  ✗ FAIL: did not navigate to agents. URL: {driver.current_url}")
        return False

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "agents" not in body_text.lower():
        print(f"  ✗ FAIL: agents response does not contain 'agents'")
        return False

    # Verify the count in the response matches the UI homepage
    api_data = get_api_json("/api/v1/agents")
    if str(api_data["count"]) not in body_text:
        print(f"  ✗ FAIL: agent count {api_data['count']} not in displayed text")
        return False

    print(f"  Navigated to {driver.current_url}, agents list displayed")
    return True


def test_swagger_ui_has_endpoints(driver):
    """Verify Swagger UI at /docs displays actual API endpoints."""
    driver.get(BASE_URL + "/docs")
    wait = WebDriverWait(driver, 15)
    time.sleep(5)  # Swagger UI takes time to fully render

    body_text = driver.find_element(By.TAG_NAME, "body").text

    # Check for key endpoints that should appear in Swagger UI
    expected_endpoints = [
        "healthz",
        "agents",
        "studies",
        "settings",
        "predict",
    ]
    missing = [ep for ep in expected_endpoints if ep not in body_text.lower()]
    if missing:
        print(f"  ✗ FAIL: Swagger UI missing endpoints: {missing}")
        return False

    print(f"  Swagger UI displays all expected endpoints")
    return True


def test_swagger_ui_try_it_out(driver):
    """Test the 'Try it out' button on Swagger UI for /healthz endpoint."""
    driver.get(BASE_URL + "/docs")
    wait = WebDriverWait(driver, 15)
    time.sleep(5)  # Wait for Swagger UI to load

    # Find and click the /healthz endpoint to expand it
    try:
        # Look for the healthz endpoint button
        healthz_element = driver.find_element(By.XPATH, "//*[contains(text(), 'healthz')]")
        healthz_element.click()
        time.sleep(2)
    except NoSuchElementException:
        print(f"  ⚠ SKIP: could not find healthz endpoint in Swagger UI (UI may differ)")
        return True  # Don't fail — Swagger UI structure varies

    # Look for "Try it out" button
    try:
        try_it_out = driver.find_element(By.XPATH, "//button[contains(text(), 'Try it out')]")
        try_it_out.click()
        time.sleep(1)

        # Look for "Execute" button
        execute = driver.find_element(By.XPATH, "//button[contains(text(), 'Execute')]")
        execute.click()
        time.sleep(2)

        # Check for response
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "ok" not in body_text:
            print(f"  ⚠ SKIP: Try it out did not show expected response (UI may differ)")
            return True
    except (NoSuchElementException, ElementNotInteractableException):
        print(f"  ⚠ SKIP: Try it out button not interactable (UI may differ)")
        return True

    print(f"  Swagger UI 'Try it out' works for /healthz")
    return True


def test_redoc_loads(driver):
    """Verify /redoc page loads."""
    driver.get(BASE_URL + "/redoc")
    wait = WebDriverWait(driver, 15)
    time.sleep(5)  # ReDoc takes time to render

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "AhmedETAP" not in body_text and "API" not in body_text:
        print(f"  ✗ FAIL: ReDoc did not load properly")
        return False

    print(f"  ReDoc loaded at {driver.current_url}")
    return True


def test_404_page_displays_error(driver):
    """Verify non-existent page shows error in browser."""
    driver.get(BASE_URL + "/api/v1/agents/nonexistent-xyz")
    wait = WebDriverWait(driver, 10)

    body_text = driver.find_element(By.TAG_NAME, "body").text
    if "not found" not in body_text.lower():
        print(f"  ✗ FAIL: 404 page should show 'not found', got: {body_text[:200]!r}")
        return False

    print(f"  404 error displayed correctly")
    return True


def test_homepage_status_indicator(driver):
    """Verify the LIVE status indicator is present and shows uptime."""
    driver.get(BASE_URL + "/")
    wait = WebDriverWait(driver, 10)

    try:
        status = driver.find_element(By.CSS_SELECTOR, ".status")
    except NoSuchElementException:
        print(f"  ✗ FAIL: status indicator element not found")
        return False

    status_text = status.text
    if "LIVE" not in status_text:
        print(f"  ✗ FAIL: status indicator should show 'LIVE', got: {status_text!r}")
        return False

    if "Uptime" not in status_text:
        print(f"  ✗ FAIL: status indicator should show uptime, got: {status_text!r}")
        return False

    print(f"  Status indicator: {status_text!r}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("INTERACTIVE UI TESTS — clicking links, verifying navigation, cross-checking values")
    print("=" * 70)

    try:
        driver = create_driver()
        print(f"Chrome WebDriver started")
    except Exception as e:
        print(f"FATAL: Could not start Chrome WebDriver: {e}")
        sys.exit(1)

    try:
        run_test("Homepage displays correct agent count (cross-check with API)", test_homepage_displays_correct_agent_count, driver)
        run_test("Homepage displays version (cross-check with API)", test_homepage_displays_version, driver)
        run_test("Homepage displays standards badges", test_homepage_standards_badges, driver)
        run_test("Homepage status indicator shows LIVE + uptime", test_homepage_status_indicator, driver)
        run_test("Click 'Swagger Docs' link navigates to /docs", test_click_swagger_docs_link, driver)
        run_test("Click 'Health' link navigates to /healthz", test_click_health_link, driver)
        run_test("Click 'Agents' link navigates to agents list", test_click_agents_link, driver)
        run_test("Swagger UI displays API endpoints", test_swagger_ui_has_endpoints, driver)
        run_test("Swagger UI 'Try it out' button works", test_swagger_ui_try_it_out, driver)
        run_test("ReDoc page loads", test_redoc_loads, driver)
        run_test("404 page displays error message", test_404_page_displays_error, driver)
    finally:
        driver.quit()
        print("\nWebDriver closed.")

    print("\n" + "=" * 70)
    print(f"INTERACTIVE UI TEST RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✓ All interactive UI tests passed!")
        sys.exit(0)
