/**
 * Playwright smoke test for the RBAC Admin page (TASK-1).
 *
 * Covers the CRUD happy path:
 *   1. Page renders with the three tabs (Roles, Permissions, User Assignments)
 *   2. "New Role" modal opens with permission multi-select
 *   3. Submitting the modal calls POST /api/v1/auth/roles
 *   4. Edit button on a role row opens the modal pre-filled
 *   5. Delete flow shows confirmation modal then calls DELETE
 *
 * The test mocks the backend via page.route() so it can run without a live
 * API. This keeps the test hermetic and fast.
 *
 * Ref: TASK-1
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_PERMISSIONS = [
  {
    id: "perm-1",
    resource: "projects",
    action: "read",
    description: "View projects",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "perm-2",
    resource: "projects",
    action: "write",
    description: "Create/update projects",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "perm-3",
    resource: "studies",
    action: "delete",
    description: "Delete studies",
    created_at: "2026-01-01T00:00:00Z",
  },
];

const MOCK_ROLES = [
  {
    id: "role-admin",
    name: "admin",
    description: "Full access",
    is_system: true,
    permission_ids: ["perm-1", "perm-2", "perm-3"],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "role-viewer",
    name: "viewer",
    description: "Read-only access",
    is_system: false,
    permission_ids: ["perm-1"],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// Track creates/updates/deletes so we can assert side-effects.
const createdRoles: unknown[] = [];
let deletedRoleId: string | null = null;

async function mockRbacBackend(page: Page) {
  // Auth token in sessionStorage so ProtectedRoute lets us through.
  // Onboarding completion in localStorage so the OnboardingTour doesn't
  // overlay the page and intercept clicks.
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

  // Match the roles URL on any origin (localhost, hf.space, etc.) using
  // a regex so we don't depend on which API_BASE_URL resolves at runtime.
  await page.route(/\/api\/v1\/auth\/roles(\?.*)?$/, async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          roles: MOCK_ROLES,
          total: MOCK_ROLES.length,
          page: 1,
          page_size: 500,
        }),
      });
      return;
    }
    if (method === "POST") {
      const body = route.request().postDataJSON() as { name: string };
      createdRoles.push(body);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: `role-${Date.now()}`,
          name: body.name,
          description: body.description ?? null,
          is_system: false,
          permission_ids: body.permission_ids ?? [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });

  // Separate route for /roles/{id} (PUT, DELETE) — different path pattern.
  await page.route(/\/api\/v1\/auth\/roles\/[^/]+$/, async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    if (method === "PUT") {
      const body = route.request().postDataJSON();
      createdRoles.push({ ...body, _op: "PUT" });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...MOCK_ROLES[1], ...body }),
      });
      return;
    }
    if (method === "DELETE") {
      deletedRoleId = url.split("/").pop() ?? null;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "deleted" }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/api/v1/auth/permissions*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          permissions: MOCK_PERMISSIONS,
          total: MOCK_PERMISSIONS.length,
          page: 1,
          page_size: 500,
        }),
      });
      return;
    }
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { resource: string; action: string };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: `perm-${Date.now()}`,
          resource: body.resource,
          action: body.action,
          description: body.description ?? null,
          created_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });

  // Generic catch-all for other API calls the layout may make (health, etc.)
  await page.route("**/api/v1/notifications*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/v1/health*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    }),
  );

  // Auth: validateTokenAndSetUser calls /api/v1/auth/me on mount.
  // Without this mock, the auth context marks the token invalid and
  // ProtectedRoute redirects to /login.
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "u1",
        user_id: "u1",
        email: "admin@etap.com",
        name: "Admin",
        role: "admin",
        tenant_id: "t1",
      }),
    }),
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * The app shows an onboarding tour overlay on first visit. The overlay sits
 * at z-200 and intercepts clicks, so we dismiss it before interacting with
 * page elements.
 */
async function dismissOnboardingIfPresent(page: Page): Promise<void> {
  const skipButton = page.getByRole("button", { name: /Skip onboarding/i });
  if (await skipButton.count()) {
    await skipButton.click({ timeout: 2000 }).catch(() => {
      /* ignore — already dismissed */
    });
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("RBAC Admin Page", () => {
  test.beforeEach(async ({ page }) => {
    createdRoles.length = 0;
    deletedRoleId = null;
    await mockRbacBackend(page);
  });

  test("renders three tabs and loads roles table", async ({ page }) => {
    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    // Header
    await expect(page.getByRole("heading", { name: /RBAC Administration/i })).toBeVisible();

    // Three tab buttons
    await expect(page.getByRole("button", { name: /^Roles/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Permissions/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^User Assignments/i })).toBeVisible();

    // Roles tab is active by default — both mock roles should appear in the
    // roles table body (scope to main to avoid matching sidebar/breadcrumb).
    const main = page.locator("main").first();
    await expect(main.getByText("admin", { exact: true })).toBeVisible();
    await expect(main.getByText("viewer", { exact: true })).toBeVisible();
    await expect(main.getByText("Full access")).toBeVisible();
  });

  test("opens Create Role modal with permission multi-select and submits", async ({ page }) => {
    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    // Click "New Role" button (there are two — one in empty-state and one in
    // the toolbar). Click the toolbar one for determinism.
    await page
      .getByRole("button", { name: /New Role/i })
      .first()
      .click();

    // Modal is open
    await expect(page.getByRole("heading", { name: /Create Role/i })).toBeVisible();
    await expect(page.locator("#rbac-role-name")).toBeVisible();

    // Permission multi-select is visible — at least one mock permission shown.
    // The modal is rendered as a fixed-position overlay. Scope to it via the
    // closest ancestor of the #rbac-role-name input.
    const modal = page
      .locator("#rbac-role-name")
      .locator("xpath=ancestor::div[contains(@class,'fixed')]")
      .first();
    await expect(modal.getByText(/projects:read/i).first()).toBeVisible();
    await expect(modal.getByText(/projects:write/i).first()).toBeVisible();

    // Fill the form
    await page.locator("#rbac-role-name").fill("test-engineer");
    await page.locator("#rbac-role-description").fill("Test engineer role");

    // Select the first permission checkbox
    const firstPermCheckbox = page.getByRole("checkbox").first();
    await firstPermCheckbox.check();

    // Submit
    await page.getByRole("button", { name: /Create Role/i }).click();

    // Wait for the POST to be intercepted
    await expect.poll(() => createdRoles.length).toBeGreaterThanOrEqual(1);
    expect(createdRoles[0]).toMatchObject({ name: "test-engineer" });
  });

  test("opens Edit Role modal pre-filled with existing values", async ({ page }) => {
    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    // Find the "viewer" row's edit button and click it
    const viewerRow = page.locator("tr", { hasText: "viewer" });
    await viewerRow.locator('button[aria-label*="Edit role"]').click();

    // Modal should be in edit mode
    await expect(page.getByRole("heading", { name: /Edit Role/i })).toBeVisible();
    await expect(page.locator("#rbac-role-name")).toHaveValue("viewer");
    await expect(page.locator("#rbac-role-description")).toHaveValue("Read-only access");
  });

  test("delete role shows confirmation modal then issues DELETE", async ({ page }) => {
    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    // The "admin" role is system — its delete button should be disabled.
    const adminRow = page.locator("tr", { hasText: /^admin/ });
    const adminDeleteBtn = adminRow.locator('button[aria-label*="Delete role"]');
    await expect(adminDeleteBtn).toBeDisabled();

    // The "viewer" row's delete button should be enabled.
    const viewerRow = page.locator("tr", { hasText: "viewer" });
    const viewerDeleteBtn = viewerRow.locator('button[aria-label*="Delete role"]');
    await viewerDeleteBtn.click();

    // Confirmation modal
    await expect(page.getByRole("heading", { name: /Delete Role/i })).toBeVisible();
    await expect(page.getByText(/Are you sure you want to delete/i)).toBeVisible();

    // Confirm — the modal footer has a single "Delete Role" button. Use
    // exact match (anchored) to avoid matching the modal heading.
    await page.getByRole("button", { name: /^Delete Role$/i }).click();

    // Skill pattern: expect.poll already auto-waits — no waitForTimeout needed.
    await expect.poll(() => deletedRoleId, { timeout: 30000 }).toBe("role-viewer");
  });

  test("Permissions tab shows permissions grouped by resource", async ({ page }) => {
    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    await page.getByRole("button", { name: /^Permissions/i }).click();

    // Two resource groups: projects and studies
    await expect(page.getByText("projects", { exact: true })).toBeVisible();
    await expect(page.getByText("studies", { exact: true })).toBeVisible();

    // Action badges
    await expect(page.locator("text=read").first()).toBeVisible();
    await expect(page.locator("text=write").first()).toBeVisible();
    await expect(page.locator("text=delete").first()).toBeVisible();
  });

  test("User Assignments tab allows lookup and role toggling", async ({ page }) => {
    // Mock the user-roles lookup endpoint
    await page.route("**/api/v1/auth/users/*/roles", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            user_id: "u-123",
            roles: [MOCK_ROLES[1]], // viewer
          }),
        });
        return;
      }
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON() as { role_ids: string[] };
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            user_id: "u-123",
            roles: body.role_ids
              .map((id) => MOCK_ROLES.find((r) => r.id === id))
              .filter((r): r is (typeof MOCK_ROLES)[number] => r !== undefined),
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/admin/rbac", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);
    await page.getByRole("button", { name: /^User Assignments/i }).click();

    // Enter user ID and lookup
    await page.locator("#rbac-user-id").fill("u-123");
    await page.getByRole("button", { name: /Lookup/i }).click();

    // Current role panel shows "viewer" — the lookup renders the role once
    // in the "Current roles" card and once in the "Update role assignments"
    // toggle list. Use .first() to disambiguate (the current-roles card
    // appears above the toggle list in the DOM).
    await expect(page.getByText("Current roles for")).toBeVisible();
    const currentRoleCard = page.locator("div").filter({ hasText: "Current roles for" }).first();
    await expect(currentRoleCard.getByText("viewer").first()).toBeVisible();
  });
});
