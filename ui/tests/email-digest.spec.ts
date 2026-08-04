/**
 * Playwright smoke test for the Email Digest page (TASK-6).
 *
 * Covers the wiring to all 4 endpoints in api/email_digest.py
 * (prefix /api/v1/email-digest):
 *   1. Overview tab loads config from GET /config
 *   2. Generate tab POSTs /generate and shows by_flow breakdown (success)
 *   3. Generate tab handles 503 digests_disabled with error toast
 *   4. Schedule run button POSTs /schedule/run and shows sent/failed counts
 *   5. Preview tab loads HTML from GET /preview/{email} in a modal
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-6
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_CONFIG = {
  success: true,
  config: {
    enabled: true,
    daily_schedule: "08:00",
    weekly_schedule: "MONDAY_08:00",
    timezone: "UTC",
  },
};

const MOCK_GENERATE_OK = {
  success: true,
  message_id: "msg-digest-001",
  error: null,
  total_count: 12,
  by_flow: {
    otp: 6,
    password_reset: 3,
    welcome: 2,
    notification: 1,
  },
  trace_id: "trace-gen-001",
};

const MOCK_SCHEDULE_RUN = {
  success: true,
  period: "daily",
  recipients_count: 8,
  sent: 7,
  failed: 1,
  trace_id: "trace-run-001",
};

const MOCK_PREVIEW_HTML = `
<!DOCTYPE html>
<html>
  <head><title>Daily Digest</title></head>
  <body>
    <h2>AhmedETAP — Daily Digest</h2>
    <p>Hello user@example.com,</p>
    <p>You have <strong>5</strong> updates in the last 24 hours.</p>
    <ul>
      <li>Your OTP code</li>
      <li>Password reset request</li>
      <li>Welcome to AhmedETAP</li>
    </ul>
    <p>Visit <a href="https://etap-ai-work.vercel.app">the dashboard</a> for details.</p>
  </body>
</html>
`;

// Track call counts so we can assert side-effects.
let generateCalled = false;
let generateBody: { email?: string; period?: string; user_name?: string } | null = null;
let scheduleRunCalled = false;
let previewCalled = false;
let previewEmail = "";
let previewPeriod = "";

async function mockEmailDigestBackend(page: Page, opts?: { generateStatus?: 503 }) {
  const generateStatus = opts?.generateStatus ?? 200;

  // Auth + onboarding-dismissal
  await page.addInitScript(() => {
    sessionStorage.setItem("authToken", "test-token");
    sessionStorage.setItem(
      "authUser",
      JSON.stringify({
        user_id: "u1",
        email: "admin@etap.com",
        role: "admin",
        tenant_id: "t1",
      }),
    );
    localStorage.setItem("etap-ai-onboarding-completed", "true");
  });

  // Auth: validateTokenAndSetUser calls /api/v1/auth/me on mount.
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user_id: "u1",
        email: "admin@etap.com",
        username: "admin",
        role: "admin",
        is_active: true,
        tenant_id: "t1",
      }),
    }),
  );

  // GET /config
  await page.route("**/api/v1/email-digest/config", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONFIG),
    });
  });

  // POST /generate
  await page.route("**/api/v1/email-digest/generate", async (route) => {
    if (route.request().method() !== "POST") return route.continue();

    generateCalled = true;
    try {
      generateBody = route.request().postDataJSON() as {
        email?: string;
        period?: string;
        user_name?: string;
      } | null;
    } catch {
      generateBody = null;
    }

    if (generateStatus === 503) {
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          success: false,
          error: "digests_disabled",
          trace_id: "trace-503",
        }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_GENERATE_OK),
    });
  });

  // POST /schedule/run
  await page.route("**/api/v1/email-digest/schedule/run", (route) => {
    if (route.request().method() !== "POST") return route.continue();
    scheduleRunCalled = true;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_SCHEDULE_RUN),
    });
  });

  // GET /preview/{email} (HTML)
  await page.route("**/api/v1/email-digest/preview/*", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    previewCalled = true;
    const url = route.request().url();
    // Extract email from path and period from query
    const match = url.match(/\/preview\/([^?]+)/);
    previewEmail = match?.[1] ? decodeURIComponent(match[1]) : "";
    const urlObj = new URL(url);
    previewPeriod = urlObj.searchParams.get("period") ?? "daily";
    return route.fulfill({
      status: 200,
      contentType: "text/html",
      body: MOCK_PREVIEW_HTML,
    });
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Email Digest page (TASK-6)", () => {
  test.beforeEach(() => {
    generateCalled = false;
    generateBody = null;
    scheduleRunCalled = false;
    previewCalled = false;
    previewEmail = "";
    previewPeriod = "";
  });

  test("Overview tab loads config from GET /config", async ({ page }) => {
    await mockEmailDigestBackend(page);
    await page.goto("/admin/email-digest");

    // Header
    await expect(page.getByRole("heading", { name: /Email Digest/i })).toBeVisible();

    // Config card — values from MOCK_CONFIG
    const configCard = page.getByTestId("config-card");
    await expect(configCard).toBeVisible({ timeout: 10_000 });

    // Enabled badge
    await expect(configCard.getByTestId("config-enabled-badge")).toBeVisible();
    await expect(configCard.getByTestId("config-enabled-text")).toHaveText("ENABLED");
    // Daily schedule value (use exact match — "08:00" is a substring of "MONDAY_08:00")
    await expect(configCard.getByText("08:00", { exact: true })).toBeVisible();
    // Weekly schedule value
    await expect(configCard.getByText("MONDAY_08:00", { exact: true })).toBeVisible();
    // Timezone
    await expect(configCard.getByText("UTC", { exact: true })).toBeVisible();
  });

  test("Generate tab POSTs /generate and shows by_flow breakdown", async ({ page }) => {
    await mockEmailDigestBackend(page);
    await page.goto("/admin/email-digest");

    // Click the Generate tab
    await page
      .getByRole("button", { name: /Generate/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("generate-email").fill("user@example.com");
    await page.getByTestId("generate-period").selectOption("weekly");
    await page.getByTestId("generate-name").fill("Ahmed");

    // Submit
    await page.getByTestId("generate-submit").click();

    // The POST should have fired with the expected body
    await expect.poll(() => generateCalled, { timeout: 5_000 }).toBe(true);
    await expect
      .poll(() => generateBody, { timeout: 5_000 })
      .toEqual({
        email: "user@example.com",
        period: "weekly",
        user_name: "Ahmed",
      });

    // Result card should show the by_flow badges
    const resultCard = page.getByTestId("generate-result");
    await expect(resultCard).toBeVisible({ timeout: 5_000 });
    await expect(resultCard.getByText("Success")).toBeVisible();
    await expect(resultCard.getByText("12")).toBeVisible(); // total_count
    await expect(resultCard.getByText("otp: 6")).toBeVisible();
    await expect(resultCard.getByText("password_reset: 3")).toBeVisible();
    await expect(resultCard.getByText("welcome: 2")).toBeVisible();
    await expect(resultCard.getByText("notification: 1")).toBeVisible();
    await expect(resultCard.getByText("msg-digest-001")).toBeVisible(); // message_id
    await expect(resultCard.getByText("trace-gen-001")).toBeVisible(); // trace_id

    // Success toast
    await expect(page.getByText(/Digest sent to user@example\.com/)).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Generate tab handles 503 digests_disabled with error toast", async ({ page }) => {
    await mockEmailDigestBackend(page, { generateStatus: 503 });
    await page.goto("/admin/email-digest");

    // Click the Generate tab
    await page
      .getByRole("button", { name: /Generate/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("generate-email").fill("user@example.com");
    await page.getByTestId("generate-period").selectOption("daily");

    // Submit
    await page.getByTestId("generate-submit").click();

    // POST fired
    await expect.poll(() => generateCalled, { timeout: 5_000 }).toBe(true);

    // Error banner inside the form should mention the failure (HTTP 503 /
    // digests_disabled). Use .first() to disambiguate from the toast
    // notification which also surfaces the same error message.
    await expect(
      page.getByRole("alert").getByText(/503.*digests_disabled|digests_disabled.*503/),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("Schedule run button POSTs /schedule/run and shows sent/failed counts", async ({ page }) => {
    await mockEmailDigestBackend(page);
    await page.goto("/admin/email-digest");

    // Wait for config to load (proves we're on Overview tab)
    await expect(page.getByTestId("config-card")).toBeVisible({ timeout: 10_000 });

    // Click the "Run Now" button
    await page.getByTestId("run-schedule-btn").click();

    // POST should have fired
    await expect.poll(() => scheduleRunCalled, { timeout: 5_000 }).toBe(true);

    // Result block should show counts from MOCK_SCHEDULE_RUN
    const runResult = page.getByTestId("run-result");
    await expect(runResult).toBeVisible({ timeout: 5_000 });
    await expect(runResult.getByText("Success")).toBeVisible();
    await expect(runResult.getByText("daily")).toBeVisible(); // period
    await expect(runResult.getByText("8").first()).toBeVisible(); // recipients_count
    await expect(runResult.getByText("7").first()).toBeVisible(); // sent
    await expect(runResult.getByText("1").first()).toBeVisible(); // failed
    await expect(runResult.getByText("trace-run-001")).toBeVisible(); // trace_id

    // Success toast
    await expect(page.getByText(/Processed 8 recipient\(s\): 7 sent, 1 failed/)).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Preview tab loads HTML from GET /preview/{email} in a modal", async ({ page }) => {
    await mockEmailDigestBackend(page);
    await page.goto("/admin/email-digest");

    // Click the Preview tab
    await page
      .getByRole("button", { name: /Preview/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("preview-email").fill("user@example.com");
    await page.getByTestId("preview-period").selectOption("daily");

    // Submit
    await page.getByTestId("preview-submit").click();

    // GET should have fired with the right email/period
    await expect.poll(() => previewCalled, { timeout: 5_000 }).toBe(true);
    await expect.poll(() => previewEmail, { timeout: 5_000 }).toBe("user@example.com");
    await expect.poll(() => previewPeriod, { timeout: 5_000 }).toBe("daily");

    // Modal should open and contain an iframe with the HTML preview
    const modal = page.getByTestId("preview-modal");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // The iframe should be present
    const iframe = modal.locator("iframe");
    await expect(iframe).toBeVisible();

    // Success toast
    await expect(page.getByText(/Digest preview loaded/)).toBeVisible({
      timeout: 5_000,
    });
  });
});
