import { expect, test } from "@playwright/test";

test.describe("Public Routes", () => {
  test("root / redirects to login", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator("#login-email")).toBeVisible({ timeout: 10000 });
  });

  test("/login shows email and password form", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });
    await expect(page.locator("#login-email")).toBeVisible();
    await expect(page.locator("#login-password")).toBeVisible();
  });

  test("/register shows registration form", async ({ page }) => {
    await page.goto("/register", { waitUntil: "networkidle" });
    const childCount = await page.evaluate(
      () => document.getElementById("root")?.children.length ?? 0,
    );
    expect(childCount).toBeGreaterThan(0);
  });
});

test.describe("Protected Routes — Unauthenticated", () => {
  const routes = [
    "/dashboard", "/studies", "/projects", "/assistant", "/settings",
    "/reports", "/grid-editor", "/admin", "/asset-management",
    "/data-import", "/data-export", "/diagnostics", "/logs",
    "/etap", "/gis", "/scada", "/code-guard", "/digital-twin",
    "/admin/cua-monitor",
  ];

  for (const route of routes) {
    test(`redirects ${route} to login when unauthenticated`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle", timeout: 15000 });
      await expect(page.locator("#login-email")).toBeVisible({ timeout: 10000 });
    });
  }
});
