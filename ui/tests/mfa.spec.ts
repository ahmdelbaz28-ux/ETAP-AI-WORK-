/**
 * Playwright smoke test for the MFA page (TASK-9c).
 *
 * Covers the wiring to all 3 endpoints in api/mfa.py
 * (prefix /api/v1/auth/mfa — all require JWT):
 *   1. Setup tab POSTs /totp/setup and shows qr_code_uri + "MFA enabled"
 *   2. Verify TOTP tab POSTs /totp/verify with code and shows valid badge
 *   3. Verify TOTP tab handles 401 invalid_code with error banner
 *   4. Verify Backup tab POSTs /backup/verify with code and shows valid badge
 *   5. Verify Backup tab handles 401 invalid_backup_code with error banner
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-9c
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_SETUP_OK = {
  success: true,
  data: {
    qr_code_uri: "otpauth://totp/ETAP:admin@etap.com?secret=JBSWY3DPEHPK3PXP&issuer=ETAP",
  },
  trace_id: "trace-setup-001",
};

const MOCK_VERIFY_TOTP_OK = {
  success: true,
  data: { valid: true },
  trace_id: "trace-totp-001",
};

const MOCK_VERIFY_TOTP_INVALID = {
  success: false,
  error: "invalid_code",
  message: "Invalid TOTP code.",
  data: { valid: false },
  trace_id: "trace-totp-bad-001",
};

const MOCK_VERIFY_BACKUP_OK = {
  success: true,
  data: { valid: true },
  trace_id: "trace-backup-001",
};

const MOCK_VERIFY_BACKUP_INVALID = {
  success: false,
  error: "invalid_backup_code",
  message: "Invalid or already used backup code.",
  trace_id: "trace-backup-bad-001",
};

// Track call counts so we can assert side-effects.
let setupCalled = false;
let setupBody: Record<string, unknown> | null = null;
let totpCalled = false;
let totpBody: { code?: string } | null = null;
let backupCalled = false;
let backupBody: { code?: string } | null = null;

async function mockMfaBackend(
  page: Page,
  opts?: {
    totpStatus?: 401;
    backupStatus?: 401;
  },
) {
  const totpStatus = opts?.totpStatus ?? 200;
  const backupStatus = opts?.backupStatus ?? 200;

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

  // POST /totp/setup
  await page.route("**/api/v1/auth/mfa/totp/setup", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    setupCalled = true;
    try {
      setupBody = route.request().postDataJSON() as Record<string, unknown>;
    } catch {
      setupBody = null;
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_SETUP_OK),
    });
  });

  // POST /totp/verify
  await page.route("**/api/v1/auth/mfa/totp/verify", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    totpCalled = true;
    try {
      totpBody = route.request().postDataJSON() as {
        code?: string;
      } | null;
    } catch {
      totpBody = null;
    }
    if (totpStatus === 401) {
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VERIFY_TOTP_INVALID),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_VERIFY_TOTP_OK),
    });
  });

  // POST /backup/verify
  await page.route("**/api/v1/auth/mfa/backup/verify", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    backupCalled = true;
    try {
      backupBody = route.request().postDataJSON() as {
        code?: string;
      } | null;
    } catch {
      backupBody = null;
    }
    if (backupStatus === 401) {
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify(MOCK_VERIFY_BACKUP_INVALID),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_VERIFY_BACKUP_OK),
    });
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("MFA page (TASK-9c)", () => {
  test.beforeEach(() => {
    setupCalled = false;
    setupBody = null;
    totpCalled = false;
    totpBody = null;
    backupCalled = false;
    backupBody = null;
  });

  test("Setup tab POSTs /totp/setup and shows qr_code_uri + MFA enabled", async ({ page }) => {
    // Regression guard for fix/mfa-qr-leak: the QR must NOT be rendered
    // via a third-party network call (previously api.qrserver.com).
    // Fail this test if ANY request goes to that host during the test.
    const thirdPartyRequests: string[] = [];
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("api.qrserver.com") || url.includes("qrserver.com")) {
        thirdPartyRequests.push(url);
      }
    });

    await mockMfaBackend(page);
    await page.goto("/admin/mfa");

    // Header
    await expect(page.getByRole("heading", { name: /^MFA$/i })).toBeVisible();

    // Setup tab is the default — click the submit button
    await page.getByTestId("setup-submit").click();

    // POST should have fired
    await expect.poll(() => setupCalled, { timeout: 15_000 }).toBe(true);
    // Body should be empty JSON object (we omit user_id for F-04 safety)
    await expect.poll(() => setupBody, { timeout: 15_000 }).toEqual({});

    // Result card
    const result = page.getByTestId("setup-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByText("Success", { exact: true })).toBeVisible();
    await expect(result.getByText("MFA enabled", { exact: true })).toBeVisible();
    // qr_code_uri should be rendered (the otpauth:// URI)
    await expect(result.getByText(/otpauth:\/\/totp\//)).toBeVisible();
    await expect(result.getByText("trace-setup-001")).toBeVisible();

    // The QR must be rendered client-side as an inline SVG (qrcode.react),
    // not as a third-party <img>. Assert the SVG is present with role=img
    // and a descriptive aria-label.
    const qrSvg = result.getByRole("img", { name: /TOTP QR code/i });
    await expect(qrSvg).toBeVisible({ timeout: 15_000 });
    // SVG element specifically (not <img>)
    await expect(qrSvg.locator("xpath=self::*[name()='svg']")).toHaveCount(1);

    // No third-party QR requests should have been made.
    expect(thirdPartyRequests, "third-party QR service was called — TOTP secret leak").toEqual([]);

    // Success toast
    await expect(page.getByText(/MFA setup complete/i).last()).toBeVisible({ timeout: 15_000 });
  });

  test("Verify TOTP tab POSTs /totp/verify with code and shows valid badge", async ({ page }) => {
    await mockMfaBackend(page);
    await page.goto("/admin/mfa");

    // Click the Verify TOTP tab
    await page
      .getByRole("button", { name: /Verify TOTP/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("totp-code").fill("123456");

    // Submit
    await page.getByTestId("totp-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => totpCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => totpBody, { timeout: 15_000 }).toEqual({ code: "123456" });

    // Result card
    const result = page.getByTestId("totp-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByText("Verified", { exact: true })).toBeVisible();
    await expect(result.getByText("valid", { exact: true })).toBeVisible();
    await expect(result.getByText("trace-totp-001")).toBeVisible();

    // Success toast
    await expect(page.getByText(/TOTP code verified successfully/i).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Verify TOTP tab handles 401 invalid_code with error banner", async ({ page }) => {
    await mockMfaBackend(page, { totpStatus: 401 });
    await page.goto("/admin/mfa");

    // Click the Verify TOTP tab
    await page
      .getByRole("button", { name: /Verify TOTP/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("totp-code").fill("000000");

    // Submit
    await page.getByTestId("totp-submit").click();

    // POST fired
    await expect.poll(() => totpCalled, { timeout: 15_000 }).toBe(true);

    // Error banner (role=alert) should mention HTTP 401 + the backend
    // message text (the JSON `error: invalid_code` is rendered as the
    // thrown Error message `HTTP 401: Invalid TOTP code.`).
    await expect(
      page
        .getByRole("alert")
        .getByText(/401.*Invalid TOTP code|Invalid TOTP code.*401/)
        .first(),
    ).toBeVisible({ timeout: 15_000 });

    // Error toast
    await expect(page.getByText(/Verify failed: HTTP 401/).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Verify Backup tab POSTs /backup/verify with code and shows valid badge", async ({
    page,
  }) => {
    await mockMfaBackend(page);
    await page.goto("/admin/mfa");

    // Click the Verify Backup tab
    await page
      .getByRole("button", { name: /Verify Backup/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("backup-code").fill("ABCD1234EFGH");

    // Submit
    await page.getByTestId("backup-submit").click();

    // POST should have fired with the expected body
    await expect.poll(() => backupCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => backupBody, { timeout: 15_000 }).toEqual({ code: "ABCD1234EFGH" });

    // Result card
    const result = page.getByTestId("backup-result");
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByText("Verified", { exact: true })).toBeVisible();
    await expect(result.getByText("valid", { exact: true })).toBeVisible();
    await expect(result.getByText("trace-backup-001")).toBeVisible();

    // Success toast
    await expect(page.getByText(/Backup code verified successfully/i).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Verify Backup tab handles 401 invalid_backup_code with error banner", async ({ page }) => {
    await mockMfaBackend(page, { backupStatus: 401 });
    await page.goto("/admin/mfa");

    // Click the Verify Backup tab
    await page
      .getByRole("button", { name: /Verify Backup/i })
      .first()
      .click();

    // Fill the form
    await page.getByTestId("backup-code").fill("INVALID-CODE-X");

    // Submit
    await page.getByTestId("backup-submit").click();

    // POST fired
    await expect.poll(() => backupCalled, { timeout: 15_000 }).toBe(true);

    // Error banner (role=alert) should mention HTTP 401 + the backend
    // message text.
    await expect(
      page
        .getByRole("alert")
        .getByText(
          /401.*Invalid or already used backup code|Invalid or already used backup code.*401/,
        )
        .first(),
    ).toBeVisible({ timeout: 15_000 });

    // Error toast
    await expect(page.getByText(/Verify failed: HTTP 401/).last()).toBeVisible({
      timeout: 15_000,
    });
  });
});
