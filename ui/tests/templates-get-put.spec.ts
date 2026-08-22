/**
 * Playwright smoke test for the Templates page (TASK-9b) — covers the
 * newly-wired GET /{id} + PUT /{id} endpoints, plus regression coverage
 * for the previously-wired GET / (list) and POST / (create) endpoints.
 *
 * api/templates.py endpoints (prefix /api/v1/templates):
 *   GET  /                    — list (already wired in TASK-3 era)
 *   POST /                    — create (already wired)
 *   GET  /{template_id}       — NEW: get details (TASK-9b)
 *   PUT  /{template_id}       — NEW: update (TASK-9b)
 *   DELETE /{template_id}     — delete (already wired)
 *   POST /{template_id}/apply — apply (already wired)
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-9b
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_LIST = {
  templates: [
    {
      id: "tpl-001",
      name: "Baseline Load Flow",
      description: "Standard load flow template",
      study_type: "load_flow",
      parameters: { method: "newton-raphson" },
      system_config: null,
      tags: ["baseline", "production"],
      is_public: true,
      usage_count: 12,
      created_by: "u1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    },
    {
      id: "tpl-002",
      name: "Quick Short Circuit",
      description: "Fast short circuit check",
      study_type: "short_circuit",
      parameters: { standard: "IEC 60909" },
      system_config: null,
      tags: ["quick"],
      is_public: false,
      usage_count: 3,
      created_by: "u1",
      created_at: "2026-01-15T00:00:00Z",
      updated_at: "2026-01-20T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 50,
};

const MOCK_DETAIL = {
  id: "tpl-001",
  name: "Baseline Load Flow",
  description: "Standard load flow template",
  study_type: "load_flow",
  parameters: { method: "newton-raphson", max_iterations: 50 },
  system_config: null,
  tags: ["baseline", "production"],
  is_public: true,
  usage_count: 12,
  created_by: "u1",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

const MOCK_UPDATED = {
  ...MOCK_DETAIL,
  name: "Baseline Load Flow v2",
  description: "Updated description",
  parameters: { method: "newton-raphson", max_iterations: 100 },
  tags: ["baseline", "production", "v2"],
  is_public: false,
  updated_at: "2026-03-01T00:00:00Z",
};

const MOCK_CREATED = {
  id: "tpl-new-001",
  name: "New Template",
  description: "Fresh template",
  study_type: "arc_flash",
  parameters: { standard: "IEEE 1584" },
  system_config: null,
  tags: ["new"],
  is_public: false,
  usage_count: 0,
  created_by: "u1",
  created_at: "2026-03-15T00:00:00Z",
  updated_at: "2026-03-15T00:00:00Z",
};

// Track call counts so we can assert side-effects.
let listCalled = false;
let detailCalled = false;
let detailId = "";
let updateCalled = false;
let updateId = "";
let updateBody: Record<string, unknown> | null = null;
let createCalled = false;
let createBody: Record<string, unknown> | null = null;

async function mockTemplatesBackend(page: Page) {
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

  // GET / (list) — must be registered BEFORE the /{id} route so that
  // the more specific /{id} pattern doesn't shadow it. Playwright
  // matches routes in registration order, so order matters here.
  await page.route("**/api/v1/templates/", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      listCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_LIST),
      });
    }
    if (method === "POST") {
      createCalled = true;
      try {
        createBody = route.request().postDataJSON() as Record<string, unknown>;
      } catch {
        createBody = null;
      }
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CREATED),
      });
    }
    return route.continue();
  });

  // GET /{id} (detail) + PUT /{id} (update) — single regex handler
  // that branches on URL shape + method. This avoids the glob-shadow
  // problem where **/api/v1/templates/* would also catch list /.
  await page.route(/\/api\/v1\/templates\/[^/]+$/, async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    // Extract the id from the URL (last path segment)
    const id = url.split("/").pop() ?? "";

    if (method === "GET") {
      detailCalled = true;
      detailId = id;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_DETAIL),
      });
    }
    if (method === "PUT") {
      updateCalled = true;
      updateId = id;
      try {
        updateBody = route.request().postDataJSON() as Record<string, unknown>;
      } catch {
        updateBody = null;
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_UPDATED),
      });
    }
    return route.continue();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Templates page — GET/PUT /{id} (TASK-9b)", () => {
  test.beforeEach(() => {
    listCalled = false;
    detailCalled = false;
    detailId = "";
    updateCalled = false;
    updateId = "";
    updateBody = null;
    createCalled = false;
    createBody = null;
  });

  test("loads templates list via GET / on mount", async ({ page }) => {
    await mockTemplatesBackend(page);
    await page.goto("/templates");

    // Header
    await expect(page.getByRole("heading", { name: /Templates/i })).toBeVisible();

    // GET / should have fired
    await expect.poll(() => listCalled, { timeout: 15_000 }).toBe(true);

    // Both template cards should be rendered
    await expect(page.getByText("Baseline Load Flow", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Quick Short Circuit", { exact: true })).toBeVisible();

    // "public" badge on tpl-001 (is_public: true)
    await expect(page.getByText("public", { exact: true }).first()).toBeVisible();
  });

  test("Edit button fetches GET /{id} and opens modal pre-filled with detail", async ({ page }) => {
    await mockTemplatesBackend(page);
    await page.goto("/templates");

    // Wait for list to load
    await expect.poll(() => listCalled, { timeout: 15_000 }).toBe(true);

    // Click the Edit button (Pencil icon) on the first template card.
    // The Edit button is the one with title "Edit template (GET + PUT /{id})".
    await page.getByTitle("Edit template (GET + PUT /{id})").first().click();

    // GET /{id} should have fired with the right id
    await expect.poll(() => detailCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => detailId, { timeout: 15_000 }).toBe("tpl-001");

    // Modal should be visible with "Edit Template" title
    await expect(page.getByRole("heading", { name: /Edit Template/i })).toBeVisible({
      timeout: 15_000,
    });

    // Form fields should be pre-filled with the DETAIL response
    // (not the truncated list response — note max_iterations=50 is only
    // in MOCK_DETAIL, not in MOCK_LIST's parameters field).
    await expect(page.locator("#tpl-name")).toHaveValue("Baseline Load Flow");
    await expect(page.locator("#tpl-description")).toHaveValue("Standard load flow template");
    await expect(page.locator("#tpl-study-type")).toHaveValue("load_flow");
    // Parameters JSON should contain max_iterations (only in detail)
    await expect(page.locator("#tpl-parameters")).toContainText("max_iterations");
    await expect(page.locator("#tpl-parameters")).toContainText("50");
    // Tags should be comma-separated
    await expect(page.locator("#tpl-tags")).toHaveValue("baseline, production");
    // is_public checkbox should be checked (detail.is_public === true)
    await expect(page.locator("#tpl-is-public")).toBeChecked();
  });

  test("Save in edit mode fires PUT /{id} with updated body", async ({ page }) => {
    await mockTemplatesBackend(page);
    await page.goto("/templates");

    // Wait for list + open edit modal
    await expect.poll(() => listCalled, { timeout: 15_000 }).toBe(true);
    await page.getByTitle("Edit template (GET + PUT /{id})").first().click();
    await expect.poll(() => detailCalled, { timeout: 15_000 }).toBe(true);

    // Modify the name
    await page.locator("#tpl-name").fill("Baseline Load Flow v2");
    // Modify parameters
    await page.locator("#tpl-parameters").fill('{"method":"newton-raphson","max_iterations":100}');
    // Modify tags
    await page.locator("#tpl-tags").fill("baseline, production, v2");
    // Uncheck is_public
    await page.locator("#tpl-is-public").uncheck();

    // Click Update
    await page.getByRole("button", { name: /^Update$/i }).click();

    // PUT should have fired with the right id + body
    await expect.poll(() => updateCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => updateId, { timeout: 15_000 }).toBe("tpl-001");
    await expect
      .poll(() => updateBody, { timeout: 15_000 })
      .toEqual({
        name: "Baseline Load Flow v2",
        description: "Standard load flow template",
        study_type: "load_flow",
        parameters: {
          method: "newton-raphson",
          max_iterations: 100,
        },
        tags: ["baseline", "production", "v2"],
        is_public: false,
      });

    // Success toast
    await expect(page.getByText(/Template "Baseline Load Flow v2" updated/i).last()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Create mode fires POST / with full body (parameters + tags + is_public)", async ({
    page,
  }) => {
    await mockTemplatesBackend(page);
    await page.goto("/templates");

    // Wait for list to load
    await expect.poll(() => listCalled, { timeout: 15_000 }).toBe(true);

    // Click New Template
    await page.getByRole("button", { name: /New Template/i }).click();

    // Modal should open in create mode
    await expect(page.getByRole("heading", { name: /Create Template/i })).toBeVisible({
      timeout: 15_000,
    });

    // Fill the form
    await page.locator("#tpl-name").fill("New Template");
    await page.locator("#tpl-description").fill("Fresh template");
    await page.locator("#tpl-study-type").selectOption("arc_flash");
    await page.locator("#tpl-parameters").fill('{"standard":"IEEE 1584"}');
    await page.locator("#tpl-tags").fill("new");
    // is_public defaults to false (unchecked)

    // Click Create
    await page.getByRole("button", { name: /^Create$/i }).click();

    // POST should have fired with the right body
    await expect.poll(() => createCalled, { timeout: 15_000 }).toBe(true);
    await expect
      .poll(() => createBody, { timeout: 15_000 })
      .toEqual({
        name: "New Template",
        description: "Fresh template",
        study_type: "arc_flash",
        parameters: { standard: "IEEE 1584" },
        tags: ["new"],
        is_public: false,
      });

    // Success toast
    await expect(page.getByText(/Template created successfully/i).last()).toBeVisible({
      timeout: 15_000,
    });
  });
});
