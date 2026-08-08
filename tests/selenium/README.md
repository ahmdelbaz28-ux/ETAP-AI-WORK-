# Selenium API & UI Tests

Real tests that verify response VALUES and UI behavior — not just HTTP status.

## Files

- `test_api_values.py` — 26 API tests that verify response structure, types, and values
  - 11 GET tests (verify specific field values)
  - 5 POST tests (verify response content)
  - 10 negative scenario tests (missing fields, invalid input, 404/400/422)
- `test_ui_real.py` — Selenium WebDriver tests that open Chrome and test the actual UI

## Removed (was misleading)

- `etap-api-tests.side` — DELETED. Only checked HTTP 200, not response values.
- `test_all_apis.py` — DELETED. Duplicated the .side tests with urllib.

## Prerequisites

```bash
# Python dependencies
pip install selenium

# Chrome + ChromeDriver
npm install -g chromedriver

# Chrome binary (or use system Chrome)
# For headless testing in CI: download google-chrome-stable_current_amd64.deb
```

## Running Tests

### API value tests (fast, no browser needed):
```bash
# Start the API server first
python3 -c "
import sys, os
sys.path.insert(0, 'hf-space')
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'
os.environ['ENGINEERING_SERVICE_AUTH_DISABLED'] = 'true'
import uvicorn
from app import app
uvicorn.run(app, host='127.0.0.1', port=7860, log_level='warning')
" &

# Run tests
python3 tests/selenium/test_api_values.py
```

### UI tests (requires Chrome + ChromeDriver):
```bash
python3 tests/selenium/test_ui_real.py
```

## What these tests actually verify

### API tests (`test_api_values.py`)

Unlike the deleted `.side` file that only checked HTTP 200, these tests verify:

1. **Response structure** — required JSON keys are present
2. **Field types** — `crypto_available` is bool, `agents` is list, etc.
3. **Field values** — `status == "ok"`, `name == "AhmedETAP"`, anomaly[3] == True
4. **Cross-field consistency** — `count` matches `len(agents list)`
5. **Negative scenarios** — missing fields return 422, invalid types return 400

### UI tests (`test_ui_real.py`)

Opens a real Chrome browser and verifies:

1. **Page loads** — title contains "AhmedETAP"
2. **API accessible from browser** — fetch() from JS context works
3. **Swagger docs** — /docs page renders
4. **OpenAPI schema** — /openapi.json is valid
5. **Chat API works** — returns non-empty response (1429+ chars)

## Limitations (honest)

These tests do NOT cover:
- Button click workflows (UI interaction testing)
- Form submission and validation
- Navigation between pages
- Rate limiting
- Authentication flows
- SQL injection / XSS
- Performance under load
- Concurrency

For comprehensive coverage, add tests for the above scenarios.
