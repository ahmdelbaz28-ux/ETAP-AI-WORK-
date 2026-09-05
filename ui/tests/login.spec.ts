import { expect, test } from "@playwright/test";
import { LoginPage } from "./pages/LoginPage";
import { TEST_USERS } from "./fixtures/data";

test.describe("Login Page", () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test("renders email input, password input, and sign-in button", async () => {
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.emailInput).toHaveAttribute("type", "email");
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.passwordInput).toHaveAttribute("type", "password");
    await expect(loginPage.signInButton).toBeVisible();
  });

  test("accepts typed email and password values", async () => {
    await loginPage.emailInput.fill(TEST_USERS.engineer.email);
    await loginPage.passwordInput.fill(TEST_USERS.engineer.password);
    await expect(loginPage.emailInput).toHaveValue(TEST_USERS.engineer.email);
    await expect(loginPage.passwordInput).toHaveValue(TEST_USERS.engineer.password);
  });

  test("has language toggle button", async () => {
    await expect(loginPage.languageToggle).toBeVisible();
  });

  test("has register link that navigates to /register", async ({ page }) => {
    await expect(loginPage.registerLink).toBeVisible();
    await expect(loginPage.registerLink).toHaveText(/Create Engineer Account/i);
    await loginPage.registerLink.click();
    await page.waitForLoadState("networkidle", { timeout: 20000 });
    await expect(page).toHaveURL(/\/register/);
  });

  test("has forgot password button", async () => {
    await expect(loginPage.forgotPasswordButton).toBeVisible();
  });

  test("has remember me checkbox", async () => {
    await expect(loginPage.rememberMeCheckbox).toBeVisible();
  });

  test("handles invalid credentials gracefully", async ({ page }) => {
    await loginPage.login(TEST_USERS.invalid.email, TEST_USERS.invalid.password);
    // Skill pattern: wait for a specific condition instead of waitForTimeout.
    // Either an error banner appears or the app stays on login/dashboard.
    const errorBanner = page.locator(String.raw`.bg-red-950\/20, .text-red-300`);
    await expect
      .poll(
        async () => {
          if (await errorBanner.isVisible().catch(() => false)) return "error";
          const url = page.url();
          if (/\/login|\/dashboard/.test(url)) return "settled";
          return "pending";
        },
        { timeout: 15_000 },
      )
      .not.toBe("pending");
  });
});
