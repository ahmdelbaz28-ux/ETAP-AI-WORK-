/**
 * Playwright smoke test for the Magic Links page (TASK-9a).
 *
 * Covers the wiring to all 3 endpoints in api/magic_links.py
 * (prefix /api/v1/auth/magic-link):
 *   1. Request tab POSTs /request and shows success + expires_in_seconds
 *   2. Request tab handles 429 rate_limited with error banner
 *   3. Verify tab POSTs /verify and shows access_token + user info
 *   4. Verify tab handles 401 invalid_token with error banner
 *   5. Invalidate tab POSTs /invalidate (body email) and shows invalidated count
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-9a
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_REQUEST_OK = {
  success: true,
  message: "If the email exists, a magic link has been sent.",
  expires_in_seconds: 900,
  trace_id: "trace-req-001",
};

const MOCK_REQUEST_RATE_LIMITED = {
  success: false,
  error: "rate_limited",
  retry_after_seconds: 120,
  message: "Too many magic-link requests. Please wait.",
  trace_id: "trace-rl-001",
};

const MOCK_VERIFY_OK = {
  success: true,
  message: "Magic link verified. You are now logged in.",
  access_token: "access-token-abc-123",
  refresh_token: "refresh-token-xyz-789",
  token_type: "bearer",
  user: {
    id: "user-001",
    email: "user@example.com",
    username: "ahmed",
    role: "admin",
  },
  trace_id: "trace-verify-001",
};

const MOCK_VERIFY_INVALID = {
  success: false,
  error: "token_not_found",
  message: "Magic link is invalid, expired, or already used.",
  trace_id: "trace-bad-001",
};

const MOCK_INVALIDATE = {
  success: true,
  invalidated: 2,
  email: "user@example.com",
  trace_id: "trace-inv-001",
};

// Track call counts so we can assert side-effects.
let requestCalled = false;
let requestBody: { email?: string } | null = null;
let verifyCalled = false;
let verifyBody: { token?: string } | null = null;
let invalidateCalled = false;
let invalidateBody: { email?: string } | null = null;

async function mockMagicLinksBackend(
  page: Page,
  opts?: {
    requestStatus?: 429;
    verifyStatus?: 401;
  },
) {
  const requestStatus = opts?.requestStatus ?? 200;
  const verifyStatus = opts?.verifyStatus ?? 200;

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

  // POST /request
  await page.route("**/api/v1/auth/magic-link/request", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    requestCalled = true;
    try {
      requestBody = route.request().postDataJSON() as {
        email?: string;
      } | null;
    } catch {
      requestBody = null;
    }
    if (requestStatus === 429) {
      return route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify(MOCK_REQUEST_RATE_LIMITED),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_REQUEST_OK),
    });
  });

  // POST /verify
  await page.route("**/api/v1/auth/magic-link/verify", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    verifyCalled = true;
    try {
      verifyBody = route.request().postDataJSON() as {
        token?: string;
      } | null;
    } catch {
      verifyBody = null;
    }
    if (verifyStatus === 401) {
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VERIFY_INVALID),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_VERIFY_OK),
    });
  });

  // POST /invalidate
  await page.route("**/api/v1/auth/magic-link/invalidate*", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    invalidateCalled = true;
    try {
      invalidateBody = route.request().postDataJSON() as {
        email?: string;
      } | null;
    } catch {
      invalidateBody = null;
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_INVALIDATE),
    });
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Magic Links page (TASK-9a)", () => {
  test.beforeEach(() => {
    requestCalled = false;
    requestBody = null;
    verifyCalled = false;
    verifyBody = null;
    invalidateCalled = false;
    invalidateBody = null;
  });

  test("Request tab POSTs /request and shows success + expires_in_seconds", async ({ page }) => {
    await mockMagicLinksBackend(page);
    await page.goto("/admin/magic-links");

    // Header
    await expect(page.getByRole("heading", { name: /Magic Links/i })).toBeVisible();

    // Fill the form (Request tab is the default)
    await page.getByTestId("req-email").fill("user@example.com");

    // Submit
    await page.getByTestId("req-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => requestCalled, { timeout: 5_000 }).toBe(true);
    await expect.poll(() => requestBody, { timeout: 5_000 }).toEqual({ email: "user@example.com" });

    // Result card
    const result = page.getByTestId("req-result");
    await expect(result).toBeVisible({ timeout: 5_000 });
    await expect(result.getByText("Success", { exact: true })).toBeVisible();
    await expect(result.getByText("900s")).toBeVisible();
    // expires_in_seconds + trace_id both rendered as StatRows
    await expect(result.getByText("trace-req-001")).toBeVisible();

    // Success toast (scope to last to disambiguate from any in-card text).
    await expect(page.getByText(/Magic link requested for user@example\.com/).last()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Request tab handles 429 rate_limited with error banner", async ({ page }) => {
    await mockMagicLinksBackend(page, { requestStatus: 429 });
    await page.goto("/admin/magic-links");

    // Fill the form
    await page.getByTestId("req-email").fill("user@example.com");

    // Submit
    await page.getByTestId("req-submit").click();

    // POST fired
    await expect.poll(() => requestCalled, { timeout: 5_000 }).toBe(true);

    // Error banner (role=alert) should mention HTTP 429 + the backend
    // message text (the JSON `error: rate_limited` is rendered as the
    // thrown Error message `HTTP 429: Too many magic-link requests…`).
    await expect(
      page.getByRole("alert").getByText(/429.*Too many magic-link|Too many magic-link.*429/),
    ).toBeVisible({ timeout: 5_000 });

    // Note: when fetch throws on a non-2xx response, the catch block sets
    // `reqError` (rendered as the alert above) but leaves `reqResult`
    // null — so the result card stays in its EmptyState. We assert the
    // error toast as the second signal.
    await expect(page.getByText(/Request failed: HTTP 429/).last()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Verify tab POSTs /verify and shows access_token + user info", async ({ page }) => {
    await mockMagicLinksBackend(page);
    await page.goto("/admin/magic-links");

    // Click the Verify tab
    await page
      .getByRole("button", { name: /Verify/i })
      .first()
      .click();

    // Fill the form with a token
    const token = "a".repeat(43); // token_urlsafe(32) yields 43 chars
    await page.getByTestId("verify-token").fill(token);

    // Submit
    await page.getByTestId("verify-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => verifyCalled, { timeout: 5_000 }).toBe(true);
    await expect.poll(() => verifyBody, { timeout: 5_000 }).toEqual({ token });

    // Result card
    const result = page.getByTestId("verify-result");
    await expect(result).toBeVisible({ timeout: 5_000 });
    await expect(result.getByText("Verified", { exact: true })).toBeVisible();
    await expect(result.getByText("bearer")).toBeVisible(); // token_type badge
    await expect(result.getByText("user-001")).toBeVisible();
    await expect(result.getByText("user@example.com")).toBeVisible();
    await expect(result.getByText("ahmed")).toBeVisible();
    await expect(result.getByText("admin")).toBeVisible();
    await expect(result.getByText("trace-verify-001")).toBeVisible();

    // Success toast (scope to last to disambiguate from any in-card text).
    await expect(page.getByText(/Magic link verified for user@example\.com/).last()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Verify tab handles 401 invalid_token with error banner", async ({ page }) => {
    await mockMagicLinksBackend(page, { verifyStatus: 401 });
    await page.goto("/admin/magic-links");

    // Click the Verify tab
    await page
      .getByRole("button", { name: /Verify/i })
      .first()
      .click();

    // Fill the form with a token
    await page.getByTestId("verify-token").fill("a".repeat(43));

    // Submit
    await page.getByTestId("verify-submit").click();

    // POST fired
    await expect.poll(() => verifyCalled, { timeout: 5_000 }).toBe(true);

    // Error banner (role=alert) should mention HTTP 401 + the backend
    // message text (the JSON `error: token_not_found` is rendered as
    // the thrown Error message `HTTP 401: Magic link is invalid…`).
    await expect(
      page.getByRole("alert").getByText(/401.*Magic link is invalid|Magic link is invalid.*401/),
    ).toBeVisible({ timeout: 5_000 });

    // Error toast
    await expect(page.getByText(/Verify failed: HTTP 401/).last()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("Invalidate tab POSTs /invalidate (body email) and shows invalidated count", async ({
    page,
  }) => {
    await mockMagicLinksBackend(page);
    await page.goto("/admin/magic-links");

    // Click the Invalidate tab
    await page
      .getByRole("button", { name: /Invalidate/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("inv-email").fill("user@example.com");

    // Submit
    await page.getByTestId("inv-submit").click();

    // POST should have fired with the right body
    await expect.poll(() => invalidateCalled, { timeout: 5_000 }).toBe(true);
    await expect
      .poll(() => invalidateBody, { timeout: 5_000 })
      .toEqual({ email: "user@example.com" });

    // Result card
    const result = page.getByTestId("inv-result");
    await expect(result).toBeVisible({ timeout: 5_000 });
    await expect(result.getByText("Success", { exact: true })).toBeVisible();
    await expect(result.getByText("2")).toBeVisible(); // invalidated count
    await expect(result.getByText("trace-inv-001")).toBeVisible();

    // Success toast (scope to last to disambiguate from any in-card text).
    await expect(page.getByText(/Invalidated 2 pending magic link\(s\)/).last()).toBeVisible({
      timeout: 5_000,
    });
  });
});
