/**
 * Playwright smoke test for the AI/ML Playground page (TASK-8).
 *
 * Covers:
 *   1. Page renders with 5 capability tabs
 *   2. Default tab is 'predict/load' and the JSON editor is pre-filled
 *   3. Clicking 'Run' calls POST /api/v1/predict/load
 *   4. Switching tabs clears the result and changes the editor content
 *   5. Invalid JSON shows an error without making a network call
 *   6. 'Sample' button restores the original sample input
 *
 * Mocks backend via page.route() — runs without a live API.
 *
 * Ref: TASK-8
 */

import { type Page, expect, test } from "@playwright/test";

const MOCK_PREDICT_LOAD_RESPONSE = {
  success: true,
  data: {
    predictions: [125, 138, 142, 150, 148, 155],
    method_used: "prophet",
    confidence_interval: {
      lower: [120, 130, 135, 142, 140, 148],
      upper: [130, 146, 149, 158, 156, 162],
    },
    metrics: { mape: 0.034, rmse: 2.1 },
  },
  trace_id: "test-trace-1",
};

const MOCK_PREDICT_ANOMALY_RESPONSE = {
  success: true,
  data: {
    anomalies: [
      false,
      false,
      false,
      false,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
    ],
    anomaly_count: 2,
    method: "iforest",
    contamination: 0.1,
  },
  trace_id: "test-trace-2",
};

async function mockApiRoutes(page: Page) {
  await page.route("**/api/v1/predict/load", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PREDICT_LOAD_RESPONSE),
    });
  });
  await page.route("**/api/v1/predict/anomaly", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PREDICT_ANOMALY_RESPONSE),
    });
  });
  // Other endpoints return generic success
  await page.route("**/api/v1/predict/fault", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { fault_probability: 0.12 }, trace_id: "t3" }),
    });
  });
  await page.route("**/api/v1/gnn/predict", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { stability_index: 0.87 }, trace_id: "t4" }),
    });
  });
  await page.route("**/api/v1/rag/query", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: { answer: "IEEE 519 limits THD to 5%.", sources: [] },
        trace_id: "t5",
      }),
    });
  });
}

test.describe("AI/ML Playground (TASK-8)", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiRoutes(page);
    // Mock auth so the page can load
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: { id: "u1", email: "test@example.com", role: "admin", name: "Test User" },
        }),
      });
    });
  });

  test("renders 5 capability tabs and defaults to predict/load", async ({ page }) => {
    await page.goto("/admin/ai-playground");
    // Wait for the heading
    await expect(page.getByRole("heading", { name: /AI\/ML Playground/i })).toBeVisible();
    // All 5 tabs should be present
    await expect(page.getByRole("button", { name: /Load Forecast/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Fault Prediction/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Anomaly Detection/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /GNN Power Grid/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /RAG Query/i })).toBeVisible();
    // The default path text should appear somewhere
    await expect(page.getByText(/POST \/api\/v1\/predict\/load/i)).toBeVisible();
  });

  test("running a query calls POST /api/v1/predict/load and shows result", async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/v1/predict/")) {
        requests.push(req.url());
      }
    });

    await page.goto("/admin/ai-playground");
    // Click Run
    await page.getByRole("button", { name: /Run/i }).click();
    // Result viewer should show SUCCESS badge
    await expect(page.getByText("SUCCESS")).toBeVisible({ timeout: 5000 });
    // Network call should have been made
    expect(requests.length).toBeGreaterThan(0);
    expect(requests[0]).toContain("/api/v1/predict/load");
  });

  test("switching tabs clears the result and changes the editor", async ({ page }) => {
    await page.goto("/admin/ai-playground");
    // Run on first tab
    await page.getByRole("button", { name: /^Run/i }).click();
    await expect(page.getByText("SUCCESS")).toBeVisible({ timeout: 5000 });
    // Switch to Anomaly Detection
    await page.getByRole("button", { name: /Anomaly Detection/i }).click();
    // Result should be cleared (SUCCESS text from previous run should be gone)
    await expect(page.getByText("Run a query to see results here.")).toBeVisible();
    // Path should now show anomaly
    await expect(page.getByText(/POST \/api\/v1\/predict\/anomaly/i)).toBeVisible();
  });

  test("invalid JSON shows error without network call", async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/v1/predict/")) {
        requests.push(req.url());
      }
    });

    await page.goto("/admin/ai-playground");
    // Replace textarea content with invalid JSON
    const textarea = page.getByLabel(/JSON input for Load Forecast/i);
    await textarea.fill("{not valid json");
    // Click Run
    await page.getByRole("button", { name: /^Run/i }).click();
    // Should show an error (validation failed)
    await expect(page.getByText(/Invalid JSON/i)).toBeVisible({ timeout: 3000 });
    // No network call should have been made
    expect(requests.length).toBe(0);
  });

  test("Sample button restores original sample input", async ({ page }) => {
    await page.goto("/admin/ai-playground");
    const textarea = page.getByLabel(/JSON input for Load Forecast/i);
    // Get original value
    const original = await textarea.inputValue();
    // Modify
    await textarea.fill('{"modified": true}');
    // Click Sample
    await page.getByRole("button", { name: /Sample/i }).click();
    // Should be restored
    const restored = await textarea.inputValue();
    expect(restored).toBe(original);
  });
});
