# Selenium IDE API Tests

This directory contains Selenium IDE tests for the ETAP-AI-WORK API endpoints.

## Files

- `etap-api-tests.side` — Selenium IDE project file with 20 API endpoint tests
- `test_all_apis.py` — Python script for basic HTTP API testing (Postman collection)

## Running Selenium IDE Tests

### Prerequisites

1. **Node.js** (v8 or v10+)
2. **npm** (Node Package Manager)
3. **selenium-side-runner** — Install globally:
   ```bash
   npm install -g selenium-side-runner
   ```
4. **ChromeDriver** — Install globally:
   ```bash
   npm install -g chromedriver
   ```
5. **Google Chrome** or **Chromium** browser installed

### Running Tests

#### Basic run (uses default browser):
```bash
selenium-side-runner tests/selenium/etap-api-tests.side \
  --base-url http://127.0.0.1:7860
```

#### Headless Chrome run:
```bash
selenium-side-runner tests/selenium/etap-api-tests.side \
  -c "browserName=chrome" \
  -c "goog:chromeOptions.args=[headless,no-sandbox,disable-dev-shm-usage,disable-gpu]" \
  --base-url http://127.0.0.1:7860 \
  -o results \
  -w 1
```

#### With custom Chrome binary:
```bash
selenium-side-runner tests/selenium/etap-api-tests.side \
  -c "browserName=chrome" \
  -c "goog:chromeOptions.binary=/path/to/chrome" \
  -c "goog:chromeOptions.args=[headless,no-sandbox,disable-dev-shm-usage,disable-gpu]" \
  --base-url http://127.0.0.1:7860 \
  -o results
```

### Test Structure

The `.side` file contains 20 tests organized in one suite:

| # | Test | Endpoint | Expected Content |
|---|------|----------|------------------|
| 1 | GET /healthz | `/healthz` | `ok` |
| 2 | GET /health | `/health` | `healthy` |
| 3 | GET /ready | `/ready` | `ready` |
| 4 | GET /readyz | `/readyz` | `ready` |
| 5 | GET /metrics | `/metrics` | `uptime_seconds` |
| 6 | GET / | `/` | `AhmedETAP` |
| 7 | GET /api/v1/info | `/api/v1/info` | `AhmedETAP` |
| 8 | GET /api/v1/agents | `/api/v1/agents` | `agents` |
| 9 | GET /api/v1/agents/etap_expert | `/api/v1/agents/etap_expert` | `ETAP` |
| 10 | GET /api/v1/agents/etap-gui/health | `/api/v1/agents/etap-gui/health` | `success` |
| 11 | GET /api/v1/agents/etap-gui/safety/health | `/api/v1/agents/etap-gui/safety/health` | `kill_switch` |
| 12 | GET /api/v1/agents/etap-gui/safety/audit/verify | `/api/v1/agents/etap-gui/safety/audit/verify` | `is_valid` |
| 13 | GET /api/v1/agents/etap-gui/siem/health | `/api/v1/agents/etap-gui/siem/health` | `enabled` |
| 14 | GET /api/v1/agents/etap-gui/siem/events | `/api/v1/agents/etap-gui/siem/events` | `events` |
| 15 | GET /api/v1/studies/types | `/api/v1/studies/types` | `study_types` |
| 16 | GET /api/v1/knowledge | `/api/v1/knowledge` | `etap` |
| 17 | GET /api/v1/ml/capabilities | `/api/v1/ml/capabilities` | `sklearn` |
| 18 | GET /api/v1/settings/health | `/api/v1/settings/health` | `crypto_available` |
| 19 | GET /api/v1/settings/keys | `/api/v1/settings/keys` | `providers` |
| 20 | GET /api/v1/settings/keys/openai | `/api/v1/settings/keys/openai` | `openai` |

### Test Method

Each test uses `executeScript` with JavaScript to verify the response:
1. `open` — Opens the API endpoint URL
2. `executeScript` — Runs `document.body.innerText.includes('expected_text')` and stores result
3. `assert` — Asserts the result is `true`

This approach works reliably with JSON API responses rendered in Chrome's `<pre>` tags.

### Results

Test results are written to the `--output-directory` as JSON files with timestamps.

**Last run: 20/20 passed (100%)**
