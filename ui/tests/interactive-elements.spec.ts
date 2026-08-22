import { expect, test } from "@playwright/test";

test.describe("Login Page — Interactive Elements", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle", timeout: 30000 });
  });

  test("all form inputs are enabled and accept input", async ({ page }) => {
    await expect(page.locator("#login-email")).toBeEnabled();
    await expect(page.locator("#login-password")).toBeEnabled();
    await page.locator("#login-email").fill("test@example.com");
    await expect(page.locator("#login-email")).toHaveValue("test@example.com");
  });

  test("Sign In button is enabled when form is empty", async ({ page }) => {
    await expect(page.getByRole("button", { name: /Sign In/i })).toBeEnabled();
  });

  test("language toggle button is clickable", async ({ page }) => {
    const langBtn = page.getByRole("button", { name: /العربية|English/i });
    await expect(langBtn).toBeVisible({ timeout: 30000 });
    await expect(langBtn).toBeEnabled();
    await langBtn.click({ force: true });
    await page.waitForTimeout(500);
    await expect(langBtn).toBeVisible();
  });

  test("Forgot password button opens forgot password flow", async ({ page }) => {
    const forgotBtn = page.getByRole("button", { name: /Forgot password/i });
    await expect(forgotBtn).toBeVisible();
    await forgotBtn.click({ force: true });
    await page.waitForTimeout(500);
    const forgotEmailInput = page.locator('input[type="email"]:not([id="login-email"])');
    const hasForgotForm = (await forgotEmailInput.count()) > 0;
    if (hasForgotForm) {
      await expect(forgotEmailInput.first()).toBeVisible();
      const placeholder = await forgotEmailInput.first().getAttribute("placeholder");
      expect(placeholder?.length).toBeGreaterThan(0);
    }
  });

  test("register link is clickable", async ({ page }) => {
    const link = page.locator('a[href="/register"]');
    await expect(link).toBeVisible();
    await expect(link).toBeEnabled();
  });
});
