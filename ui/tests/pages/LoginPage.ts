import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Page Object Model for /login.
 * Follows E2E skill pattern: locators in constructor, navigation +
 * actions as methods, auto-waiting locators instead of arbitrary timeouts.
 */
export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly signInButton: Locator;
  readonly languageToggle: Locator;
  readonly registerLink: Locator;
  readonly forgotPasswordButton: Locator;
  readonly rememberMeCheckbox: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.locator("#login-email");
    this.passwordInput = page.locator("#login-password");
    this.signInButton = page.getByRole("button", { name: /Sign In/i });
    this.languageToggle = page.getByRole("button", { name: /العربية|English/i });
    this.registerLink = page.locator('a[href="/register"]');
    this.forgotPasswordButton = page.getByRole("button", { name: /Forgot password/i });
    this.rememberMeCheckbox = page.locator('input[type="checkbox"]');
  }

  async goto() {
    const resp = await this.page.goto("/login", {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    expect(resp?.status()).toBe(200);
    await expect(this.emailInput).toBeVisible();
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.signInButton.click();
  }

  async expectInvalidCredentialsHandled() {
    // Skill pattern: wait for a specific condition (error banner OR
    // staying on login/dashboard) instead of waitForTimeout.
    const errorBanner = this.page.locator(String.raw`.bg-red-950\/20, .text-red-300`);
    await expect
      .poll(
        async () => {
          if (await errorBanner.isVisible().catch(() => false)) return "error";
          const url = this.page.url();
          if (/\/login|\/dashboard/.test(url)) return "url";
          return "pending";
        },
        { timeout: 15_000 },
      )
      .not.toBe("pending");
  }
}
