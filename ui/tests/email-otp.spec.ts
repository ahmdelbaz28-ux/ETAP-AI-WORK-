/**
 * Playwright smoke test for the Email OTP page (TASK-8).
 *
 * Covers the wiring to all 3 endpoints in api/email_otp.py
 * (prefix /api/v1/auth/email-otp):
 *   1. Send tab POSTs /send and shows success + test_code (test mode)
 *   2. Send tab handles 429 rate_limited with error banner
 *   3. Verify tab POSTs /verify and shows verified_email
 *   4. Verify tab handles 400 wrong_code with error banner
 *   5. Invalidate tab POSTs /invalidate (query params) and shows success
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-8
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_SEND_OK = {
  success: true,
  expires_in_seconds: 600,
  cooldown_seconds: 60,
  message: "OTP sent to user@example.com. Check your inbox (and spam folder).",
  test_code: "123456",
  test_mode: true,
  trace_id: "trace-send-001",
};

const MOCK_SEND_RATE_LIMITED = {
  success: false,
  error: "rate_limited",
  retry_after_seconds: 45,
  message: "Please wait before requesting another code.",
  trace_id: "trace-rl-001",
};

const MOCK_VERIFY_OK = {
  success: true,
  message: "OTP verified successfully (test mode).",
  verified_email: "user@example.com",
  purpose: "login",
  action_token: null,
  action_token_expires_in: null,
  test_mode: true,
  trace_id: "trace-verify-001",
};

const MOCK_VERIFY_WRONG_CODE = {
  success: false,
  error: "invalid_code",
  message: "OTP verification failed.",
  trace_id: "trace-bad-001",
};

const MOCK_INVALIDATE = {
  success: true,
  message: "OTP invalidated.",
  trace_id: "trace-inv-001",
};

// Track call counts so we can assert side-effects.
let sendCalled = false;
let sendBody: { email?: string; purpose?: string; user_name?: string } | null = null;
let verifyCalled = false;
let verifyBody: { email?: string; purpose?: string; code?: string } | null = null;
let invalidateCalled = false;
let invalidateEmail = "";
let invalidatePurpose = "";

async function mockEmailOtpBackend(page: Page, opts?: { sendStatus?: 429 }) {
  const sendStatus = opts?.sendStatus ?? 200;

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

  // POST /send
  await page.route("**/api/v1/auth/email-otp/send", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    sendCalled = true;
    try {
      sendBody = route.request().postDataJSON() as {
        email?: string;
        purpose?: string;
        user_name?: string;
      } | null;
    } catch {
      sendBody = null;
    }
    if (sendStatus === 429) {
      return route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SEND_RATE_LIMITED),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_SEND_OK),
    });
  });

  // POST /verify
  await page.route("**/api/v1/auth/email-otp/verify", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    verifyCalled = true;
    try {
      verifyBody = route.request().postDataJSON() as {
        email?: string;
        purpose?: string;
        code?: string;
      } | null;
    } catch {
      verifyBody = null;
    }
    // Return wrong-code (400) only when code is "000000"; otherwise OK
    if (verifyBody?.code === "000000") {
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VERIFY_WRONG_CODE),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_VERIFY_OK),
    });
  });

  // POST /invalidate (query params)
  await page.route("**/api/v1/auth/email-otp/invalidate*", (route) => {
    if (route.request().method() !== "POST") return route.continue();
    invalidateCalled = true;
    const url = new URL(route.request().url());
    invalidateEmail = url.searchParams.get("email") ?? "";
    invalidatePurpose = url.searchParams.get("purpose") ?? "";
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

test.describe("Email OTP page (TASK-8)", () => {
  test.beforeEach(() => {
    sendCalled = false;
    sendBody = null;
    verifyCalled = false;
    verifyBody = null;
    invalidateCalled = false;
    invalidateEmail = "";
    invalidatePurpose = "";
  });

  test("Send tab POSTs /send and shows success + test_code (test mode)", async ({ page }) => {
    await mockEmailOtpBackend(page);
    await page.goto("/admin/email-otp");

    // Header
    await expect(page.getByRole("heading", { name: /Email OTP/i })).toBeVisible();

    // Fill the form (Send tab is the default)
    await page.getByTestId("send-email").fill("user@example.com");
    await page.getByTestId("send-purpose").selectOption("signup");
    await page.getByTestId("send-name").fill("Ahmed");

    // Submit
    await page.getByTestId("send-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => sendCalled, { timeout: 15_000 }).toBe(true);
    await expect
      .poll(() => sendBody, { timeout: 15_000 })
      .toEqual({
        email: "user@example.com",
        purpose: "signup",
        user_name: "Ahmed",
      });

    // Result card
    const result = page.getByTestId("send-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByText("Success")).toBeVisible();
    // "test mode" appears both as a badge and inside the success message;
    // use exact match on the badge.
    await expect(result.getByText("test mode", { exact: true })).toBeVisible();
    await expect(result.getByText("123456")).toBeVisible(); // test_code
    await expect(result.getByText("600s")).toBeVisible(); // expires_in_seconds
    await expect(result.getByText("60s")).toBeVisible(); // cooldown_seconds
    await expect(result.getByText("trace-send-001")).toBeVisible(); // trace_id

    // Success toast (the result block also contains the same message text —
    // scope to the toast which is rendered last in a fixed-position container).
    await expect(page.getByText(/OTP sent to user@example\.com/).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Send tab handles 429 rate_limited with error banner", async ({ page }) => {
    await mockEmailOtpBackend(page, { sendStatus: 429 });
    await page.goto("/admin/email-otp");

    // Fill the form
    await page.getByTestId("send-email").fill("user@example.com");
    await page.getByTestId("send-purpose").selectOption("login");

    // Submit
    await page.getByTestId("send-submit").click();

    // POST fired
    await expect.poll(() => sendCalled, { timeout: 15_000 }).toBe(true);

    // Error banner (role=alert) inside the form should mention HTTP 429.
    // The backend returns a JSON body with `error: rate_limited` but the
    // form's error banner string is built from the thrown Error message
    // (`HTTP 429: <message>`), so we match the HTTP status + the message
    // text rather than the JSON `error` field.
    await expect(
      page
        .getByRole("alert")
        .getByText(/429.*Please wait|Please wait.*429/)
        .first(),
    ).toBeVisible({ timeout: 15_000 });

    // Note: when fetch throws on a non-2xx response, the catch block sets
    // `sendError` (rendered as the alert above) but leaves `sendResult`
    // null — so the result card stays in its EmptyState. We assert the
    // error toast (also fired from the catch block) as the second signal.
    await expect(page.getByText(/Send failed: HTTP 429/).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Verify tab POSTs /verify and shows verified_email", async ({ page }) => {
    await mockEmailOtpBackend(page);
    await page.goto("/admin/email-otp");

    // Click the Verify tab
    await page
      .getByRole("button", { name: /Verify/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("verify-email").fill("user@example.com");
    await page.getByTestId("verify-purpose").selectOption("login");
    await page.getByTestId("verify-code").fill("123456");

    // Submit
    await page.getByTestId("verify-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => verifyCalled, { timeout: 15_000 }).toBe(true);
    await expect
      .poll(() => verifyBody, { timeout: 15_000 })
      .toEqual({
        email: "user@example.com",
        purpose: "login",
        code: "123456",
      });

    // Result card
    const result = page.getByTestId("verify-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    // Use exact match on the status span — "Verified" also appears as
    // "Verified email" label and inside the success message text.
    await expect(result.getByText("Verified", { exact: true })).toBeVisible();
    // "test mode" appears both as a badge and inside the success message;
    // use exact match on the badge.
    await expect(result.getByText("test mode", { exact: true })).toBeVisible();
    await expect(result.getByText("user@example.com")).toBeVisible(); // verified_email
    await expect(result.getByText("login")).toBeVisible(); // purpose
    await expect(result.getByText("trace-verify-001")).toBeVisible(); // trace_id

    // Success toast (scope to last to disambiguate from any in-card text).
    await expect(page.getByText(/OTP verified for user@example\.com/).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Verify tab handles 400 wrong_code with error banner", async ({ page }) => {
    await mockEmailOtpBackend(page);
    await page.goto("/admin/email-otp");

    // Click the Verify tab
    await page
      .getByRole("button", { name: /Verify/i })
      .first()
      .click();

    // Fill the form with the "wrong code" sentinel
    await page.getByTestId("verify-email").fill("user@example.com");
    await page.getByTestId("verify-purpose").selectOption("login");
    await page.getByTestId("verify-code").fill("000000");

    // Submit
    await page.getByTestId("verify-submit").click();

    // POST fired
    await expect.poll(() => verifyCalled, { timeout: 15_000 }).toBe(true);

    // Error banner (role=alert) should mention HTTP 400 + the backend
    // message text (the JSON `error: invalid_code` is rendered as the
    // thrown Error message `HTTP 400: OTP verification failed.`).
    await expect(
      page
        .getByRole("alert")
        .getByText(/400.*OTP verification failed|OTP verification failed.*400/)
        .first(),
    ).toBeVisible({ timeout: 15_000 });

    // Note: when fetch throws on a non-2xx response, the catch block sets
    // `verifyError` (rendered as the alert above) but leaves `verifyResult`
    // null — so the result card stays in its EmptyState. We assert the
    // error toast as the second signal.
    await expect(page.getByText(/Verify failed: HTTP 400/).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Invalidate tab POSTs /invalidate (query params) and shows success", async ({ page }) => {
    await mockEmailOtpBackend(page);
    await page.goto("/admin/email-otp");

    // Click the Invalidate tab
    await page
      .getByRole("button", { name: /Invalidate/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("inv-email").fill("user@example.com");
    await page.getByTestId("inv-purpose").selectOption("mfa");

    // Submit
    await page.getByTestId("inv-submit").click();

    // POST should have fired with the right query params
    await expect.poll(() => invalidateCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => invalidateEmail, { timeout: 15_000 }).toBe("user@example.com");
    await expect.poll(() => invalidatePurpose, { timeout: 15_000 }).toBe("mfa");

    // Result card
    const result = page.getByTestId("inv-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByText("Success")).toBeVisible();
    await expect(result.getByText("OTP invalidated.")).toBeVisible();
    await expect(result.getByText("trace-inv-001")).toBeVisible(); // trace_id

    // Success toast (scope to last to disambiguate from any in-card text).
    await expect(
      page.getByText(/OTP invalidated for user@example\.com \(mfa\)/).last(),
    ).toBeVisible({ timeout: 15_000 });
  });
});
