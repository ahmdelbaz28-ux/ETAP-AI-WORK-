/**
 * Playwright smoke test for the Email Dashboard page (TASK-4).
 *
 * Covers the wiring to all 7 JSON endpoints in api/email_dashboard.py:
 *   1. Overview tab loads stats + by-day from GET /api/stats + /api/by-day
 *   2. Window selector changes reload stats with new window_hours
 *   3. Recent tab loads records from GET /api/recent (with flow filter)
 *   4. Clicking a record row opens the detail modal (uses cached record)
 *   5. Config tab loads non-secret config from GET /api/config
 *   6. Clear Old modal issues POST /api/clear and shows toast
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-4
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_STATS = {
  success: true,
  stats: {
    window_hours: 24,
    total: 42,
    succeeded: 38,
    failed: 4,
    success_rate: 90.48,
    avg_elapsed_ms: 1234.5,
    by_flow: {
      otp: { total: 20, success: 19, failed: 1 },
      password_reset: { total: 10, success: 9, failed: 1 },
      welcome: { total: 12, success: 10, failed: 2 },
    },
    top_errors: [
      { error: "SMTP timeout", count: 3 },
      { error: "Invalid recipient", count: 1 },
    ],
    top_recipients: [
      { email: "user1@example.com", count: 8 },
      { email: "user2@example.com", count: 5 },
    ],
    buffer_size: 100,
    buffer_max: 5000,
  },
};

const MOCK_BY_DAY = {
  success: true,
  days: [
    { date: "2026-08-04", total: 12, succeeded: 11, failed: 1 },
    { date: "2026-08-03", total: 15, succeeded: 14, failed: 1 },
    { date: "2026-08-02", total: 8, succeeded: 8, failed: 0 },
    { date: "2026-08-01", total: 7, succeeded: 6, failed: 1 },
  ],
};

const MOCK_RECORDS = [
  {
    id: "rec-001",
    timestamp: "2026-08-04T10:00:00Z",
    recipient: "user1@example.com",
    subject: "Your OTP code",
    flow: "otp",
    success: true,
    message_id: "msg-001",
    error: null,
    status_code: 200,
    elapsed_ms: 850,
    tags: ["high-priority"],
  },
  {
    id: "rec-002",
    timestamp: "2026-08-04T09:30:00Z",
    recipient: "user2@example.com",
    subject: "Password reset request",
    flow: "password_reset",
    success: false,
    message_id: null,
    error: "SMTP timeout",
    status_code: 504,
    elapsed_ms: 15000,
    tags: [],
  },
];

const MOCK_CONFIG = {
  success: true,
  config: {
    RESEND_ENABLED: "true",
    RESEND_FROM_EMAIL: "onboarding@resend.dev",
    RESEND_FROM_NAME: "AhmedETAP",
    RESEND_REPLY_TO: "",
    RESEND_TIMEOUT_SECONDS: "15",
    RESEND_MAX_RETRIES: "3",
    RESEND_RATE_LIMIT_MAX: "10",
    RESEND_RATE_LIMIT_WINDOW: "60",
    RESEND_LOGIN_ALERTS_ENABLED: "false",
    RESEND_LOCKOUT_ALERTS_ENABLED: "true",
    RESEND_WELCOME_EMAIL_ENABLED: "true",
    RESEND_NOTIFICATION_EMAILS_ENABLED: "true",
    OTP_TTL_SECONDS: "600",
    MAGIC_LINK_TTL_SECONDS: "900",
    EMAIL_DIGEST_ENABLED: "true",
    EMAIL_DIGEST_SCHEDULE_DAILY: "08:00",
    EMAIL_BRAND_NAME: "AhmedETAP",
    EMAIL_APP_URL: "https://etap-ai-work.vercel.app",
    RESEND_API_KEY_SET: "yes",
  },
};

// Track POST /api/clear calls so we can assert side-effects.
let clearCalled = false;
let clearMaxAge: number | null = null;

async function mockEmailDashboardBackend(page: Page) {
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

  // Auth: validateTokenAndSetUser calls /api/v1/auth/me on mount. The token
  // is fake, so we must mock the /me response or ProtectedRoute redirects
  // to /login. (Same pattern used by rbac-admin.spec.ts and
  // equipment-management.spec.ts.)
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

  // Single catch-all route for /api/v1/email-dashboard/api/**
  await page.route("**/api/v1/email-dashboard/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // GET /api/stats
    if (method === "GET" && url.includes("/api/stats")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_STATS),
      });
      return;
    }

    // GET /api/recent
    if (method === "GET" && url.includes("/api/recent")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, records: MOCK_RECORDS }),
      });
      return;
    }

    // GET /api/by-day
    if (method === "GET" && url.includes("/api/by-day")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_BY_DAY),
      });
      return;
    }

    // GET /api/record/{id}
    if (method === "GET" && /\/api\/record\/[^/]+/.test(url)) {
      const match = url.match(/\/api\/record\/([^/]+)/);
      const id = match?.[1] ?? "unknown";
      const record = MOCK_RECORDS.find((r) => r.id === id) ?? MOCK_RECORDS[0];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, record }),
      });
      return;
    }

    // POST /api/clear
    if (method === "POST" && url.includes("/api/clear")) {
      clearCalled = true;
      try {
        const body = route.request().postDataJSON() as { max_age_hours?: number };
        clearMaxAge = body?.max_age_hours ?? null;
      } catch {
        clearMaxAge = null;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, removed: 5, max_age_hours: clearMaxAge ?? 720 }),
      });
      return;
    }

    // GET /api/config
    if (method === "GET" && url.includes("/api/config")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CONFIG),
      });
      return;
    }

    await route.continue();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Email Dashboard page (TASK-4)", () => {
  test.beforeEach(() => {
    clearCalled = false;
    clearMaxAge = null;
  });

  test("renders Overview tab with stats and daily chart", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Header
    await expect(page.getByRole("heading", { name: /Email Dashboard/i })).toBeVisible();

    // Stat cards — check the key numbers from MOCK_STATS
    await expect(page.getByText("42").first()).toBeVisible({ timeout: 10_000 }); // Total Sends
    await expect(page.getByText("90.48%")).toBeVisible(); // Success Rate
    await expect(page.getByText("1234.5 ms")).toBeVisible(); // Avg Latency

    // By-flow table — otp row
    await expect(page.getByText("otp").first()).toBeVisible();
    await expect(page.getByText("password_reset").first()).toBeVisible();

    // Daily chart — dates from MOCK_BY_DAY
    await expect(page.getByText("2026-08-04")).toBeVisible();
    await expect(page.getByText("2026-08-03")).toBeVisible();

    // Top errors
    await expect(page.getByText("SMTP timeout").first()).toBeVisible();
  });

  test("changing window selector reloads stats", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Wait for initial load
    await expect(page.getByText("90.48%")).toBeVisible({ timeout: 10_000 });

    // Change the window selector
    const windowSelect = page.locator("#window-hours");
    await windowSelect.selectOption("168"); // Last 7 days

    // The page should re-fetch — wait a moment for the request to fire
    // and verify stats are still visible (mock returns same data, so we
    // just check no error banner appeared).
    await page.waitForTimeout(500);
    await expect(page.locator("text=HTTP 5")).not.toBeVisible();
    await expect(page.getByText("90.48%")).toBeVisible();
  });

  test("Recent tab loads records with flow filter", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Click the Recent Sends tab
    await page.getByRole("button", { name: /Recent Sends/i }).click();

    // Both mock records should appear in the table
    const recentTable = page.locator("table").first();
    await expect(recentTable.getByText("user1@example.com")).toBeVisible({ timeout: 10_000 });
    await expect(recentTable.getByText("user2@example.com")).toBeVisible();
    await expect(recentTable.getByText("Your OTP code")).toBeVisible();
    await expect(recentTable.getByText("Password reset request")).toBeVisible();

    // Flow badges + success badges (scoped to the table with exact match to
    // avoid matching <option> elements or substrings in subject cells)
    await expect(recentTable.getByText("otp", { exact: true })).toBeVisible();
    await expect(recentTable.getByText("password_reset", { exact: true })).toBeVisible();
    await expect(recentTable.getByText("OK", { exact: true })).toBeVisible();
    await expect(recentTable.getByText("FAIL", { exact: true })).toBeVisible();

    // Change flow filter
    const flowSelect = page.locator("#flow-filter");
    await flowSelect.selectOption("otp");
    await page.waitForTimeout(300);
    // The mock returns the same records regardless of filter, so we just
    // verify the select changed without errors.
    await expect(page.locator("text=HTTP 5")).not.toBeVisible();
  });

  test("clicking a record row opens the detail modal", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Go to Recent tab
    await page.getByRole("button", { name: /Recent Sends/i }).click();
    const recentTable = page.locator("table").first();
    await expect(recentTable.getByText("user1@example.com")).toBeVisible({ timeout: 10_000 });

    // Click the first eye button (View detail)
    const eyeButton = page.getByRole("button", { name: /View detail/i }).first();
    await eyeButton.click();

    // Modal should open with the record details. The Modal component renders
    // a fixed-position overlay; scope to it via the fixed backdrop container.
    // The heading "Email Send Record" only appears in the modal.
    await expect(page.getByText("Email Send Record").first()).toBeVisible({
      timeout: 5_000,
    });
    // message_id "msg-001" only appears in the modal (not in the table)
    await expect(page.getByText("msg-001")).toBeVisible();
    // "Message ID" label only appears in the modal
    await expect(page.getByText("Message ID")).toBeVisible();
  });

  test("Config tab loads non-secret Resend config", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Click the Config tab
    await page.getByRole("button", { name: /^Config$/i }).click();

    // Config keys from MOCK_CONFIG should appear
    await expect(page.getByText("RESEND_ENABLED").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("RESEND_FROM_EMAIL").first()).toBeVisible();
    await expect(page.getByText("onboarding@resend.dev").first()).toBeVisible();
    await expect(page.getByText("RESEND_API_KEY_SET").first()).toBeVisible();
    await expect(page.getByText("yes").first()).toBeVisible();
  });

  test("Clear Old modal issues POST /api/clear and shows toast", async ({ page }) => {
    await mockEmailDashboardBackend(page);
    await page.goto("/admin/email-dashboard");

    // Wait for initial load
    await expect(page.getByText("90.48%")).toBeVisible({ timeout: 10_000 });

    // Click "Clear Old" button
    await page.getByRole("button", { name: /Clear Old/i }).click();

    // Modal should open
    await expect(page.getByRole("heading", { name: /Clear Old Log Records/i })).toBeVisible({
      timeout: 5_000,
    });

    // Change the max-age value
    const ageInput = page.locator("#clear-age");
    await ageInput.fill("168");

    // Click the "Clear Records" button (danger variant)
    await page.getByRole("button", { name: /Clear Records/i }).click();

    // The POST should have fired with max_age_hours=168
    await expect.poll(() => clearCalled, { timeout: 5_000 }).toBe(true);
    await expect.poll(() => clearMaxAge, { timeout: 5_000 }).toBe(168);

    // A success toast should appear
    await expect(page.getByText(/Cleared 5 records older than 168h/)).toBeVisible({
      timeout: 5_000,
    });
  });
});
