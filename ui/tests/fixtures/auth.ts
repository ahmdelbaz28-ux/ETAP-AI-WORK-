import type { Page } from "@playwright/test";

export interface MockUser {
  user_id: string;
  email: string;
  role: string;
  tenant_id: string;
}

export const TEST_ADMIN: MockUser = {
  user_id: "u1",
  email: "admin@etap.com",
  role: "admin",
  tenant_id: "t1",
};

/**
 * Baseline background route mocks to prevent Vite proxy stalls
 * (ECONNREFUSED 127.0.0.1:8000) when running E2E without live FastAPI backend.
 */
export async function mockBaselineRoutes(page: Page): Promise<void> {
  // Feature flags (default off / empty, fail-closed)
  await page.route("**/api/v1/feature-flags*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: [] }),
    }),
  );

  // Notifications bell & list in Navbar
  await page.route("**/api/v1/notifications/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: [], unread_count: 0 }),
    }),
  );

  // Health and readiness checks
  await page.route(
    /.*\/((health|ready)z?|metrics|openapi\.json)$/,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      }),
  );
}

/**
 * Shared authenticated-session mock.
 * Consolidates the sessionStorage + /api/v1/auth/me route setup
 * duplicated across ~8 specs. Uses addInitScript so auth survives
 * navigation, and fulfills /me with a shape accepted by both
 * validateTokenAndSetUser variants (id + user_id).
 */
export async function mockAuthenticatedSession(
  page: Page,
  user: MockUser = TEST_ADMIN,
): Promise<void> {
  await page.addInitScript(
    ({ token, mockUser }: { token: string; mockUser: MockUser }) => {
      sessionStorage.setItem("authToken", token);
      sessionStorage.setItem("authUser", JSON.stringify(mockUser));
      localStorage.setItem("etap-ai-onboarding-completed", "true");
    },
    { token: "test-token", mockUser: user },
  );

  // Install baseline mocks first so specific route mocks registered in specs can override them (LIFO)
  await mockBaselineRoutes(page);

  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: user.user_id,
        user_id: user.user_id,
        email: user.email,
        username: user.email.split("@")[0],
        role: user.role,
        is_active: true,
        tenant_id: user.tenant_id,
      }),
    }),
  );
}

/**
 * The app shows an onboarding tour overlay on first visit.
 * Dismiss before interacting with page elements.
 */
export async function dismissOnboardingIfPresent(page: Page): Promise<void> {
  const skipButton = page.getByRole("button", { name: /Skip onboarding/i });
  if (await skipButton.count()) {
    await skipButton.click({ timeout: 2000 }).catch(() => {
      /* ignore — already dismissed */
    });
  }
}
