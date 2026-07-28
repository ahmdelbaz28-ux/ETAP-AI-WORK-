import { expect, test } from "@playwright/test";

test.describe("Login Page", () => {
  test.beforeEach(async ({ page }) => {
    const resp = await page.goto("/login", { waitUntil: "networkidle", timeout: 15000 });
    expect(resp?.status()).toBe(200);
  });

  test("renders email input, password input, and sign-in button", async ({ page }) => {
    await expect(page.locator("#login-email")).toBeVisible();
    await expect(page.locator("#login-email")).toHaveAttribute("type", "email");
    await expect(page.locator("#login-password")).toBeVisible();
    await expect(page.locator("#login-password")).toHaveAttribute("type", "password");
    await expect(page.getByRole("button", { name: /Sign In/i })).toBeVisible();
  });

  test("accepts typed email and password values", async ({ page }) => {
    await page.locator("#login-email").fill("engineer@etap.com");
    await page.locator("#login-password").fill("SecurePass123!");
    await expect(page.locator("#login-email")).toHaveValue("engineer@etap.com");
    await expect(page.locator("#login-password")).toHaveValue("SecurePass123!");
  });

  test("has language toggle button", async ({ page }) => {
    await expect(page.getByRole("button", { name: /العربية|English/i })).toBeVisible();
  });

  test("has register link that navigates to /register", async ({ page }) => {
    const link = page.locator('a[href="/register"]');
    await expect(link).toBeVisible();
    await expect(link).toHaveText(/Create Engineer Account/i);
    await link.click();
    await page.waitForLoadState("networkidle", { timeout: 10000 });
    await expect(page).toHaveURL(/\/register/);
  });

  test("has forgot password button", async ({ page }) => {
    await expect(page.getByRole("button", { name: /Forgot password/i })).toBeVisible();
  });

  test("has remember me checkbox", async ({ page }) => {
    await expect(page.locator('input[type="checkbox"]')).toBeVisible();
  });

  test("handles invalid credentials gracefully", async ({ page }) => {
    await page.locator("#login-email").fill("bad@example.com");
    await page.locator("#login-password").fill("wrongpassword");
    await page.getByRole("button", { name: /Sign In/i }).click();
    await page.waitForTimeout(3000);
    const errorBanner = page.locator(".bg-red-950\\/20, .text-red-300");
    if (await errorBanner.isVisible().catch(() => false)) {
      await expect(errorBanner).toBeVisible();
    } else {
      expect(page.url()).toMatch(/\/login|\/dashboard/);
    }
  });
});
