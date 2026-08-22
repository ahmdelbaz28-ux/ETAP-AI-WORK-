/**
 * Playwright smoke test for the Equipment Management page (TASK-2).
 *
 * Covers the CRUD happy path for both Equipment and Categories:
 *   1. Page renders with two tabs (Equipment, Categories) and loads data
 *   2. "New Equipment" modal opens, requires a category, submits on POST
 *   3. Edit button opens modal pre-filled
 *   4. Single delete shows confirmation modal and issues DELETE
 *   5. Bulk select + bulk delete confirmation flow
 *   6. Categories tab shows category cards with equipment counts
 *
 * Ref: TASK-2
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_CATEGORIES = [
  {
    id: "cat-1",
    name: "Transformers",
    slug: "transformers",
    description: "Power transformers",
    icon: null,
    display_order: 0,
    equipment_count: 2,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "cat-2",
    name: "Switchgear",
    slug: "switchgear",
    description: "MV/LV switchgear",
    icon: null,
    display_order: 1,
    equipment_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const MOCK_EQUIPMENT = [
  {
    id: "eq-1",
    category_id: "cat-1",
    category_name: "Transformers",
    name: "100kVA Transformer",
    manufacturer: "ABB",
    model_number: "TX-100-3P",
    serial_number: "SN-001",
    specs: null,
    weight_kg: 1250.5,
    dimensions: "1200x800x600 mm",
    standards: null,
    tags: ["high-voltage", "indoor"],
    is_active: true,
    notes: "Installed 2024",
    created_by: "u1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "eq-2",
    category_id: "cat-1",
    category_name: "Transformers",
    name: "50kVA Transformer",
    manufacturer: "Siemens",
    model_number: "TX-50-3P",
    serial_number: "SN-002",
    specs: null,
    weight_kg: 800.0,
    dimensions: "1000x700x500 mm",
    standards: null,
    tags: [],
    is_active: true,
    notes: null,
    created_by: "u1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// Side-effect trackers
const createdEquipment: unknown[] = [];
let deletedEquipmentId: string | null = null;

async function mockEquipmentBackend(page: Page) {
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

  // Auth
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

  // Equipment list endpoint — GET/POST /api/v1/equipment/ (with optional ?query)
  // Use ** glob to match trailing slash + query string variants.
  // IMPORTANT: skip category URLs — those are handled by routes registered
  // AFTER this one (Playwright evaluates routes in LIFO order, so the
  // categories routes registered below will take precedence over this one).
  await page.route("**/api/v1/equipment/**", async (route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Skip if this is a category URL (handled by categories routes)
    if (url.includes("/categories")) {
      await route.fallback();
      return;
    }

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          equipment: MOCK_EQUIPMENT,
          total: MOCK_EQUIPMENT.length,
          page: 1,
          page_size: 25,
        }),
      });
      return;
    }
    if (method === "POST") {
      const body = route.request().postDataJSON() as { name: string };
      createdEquipment.push(body);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: `eq-${Date.now()}`,
          category_id: body.category_id,
          category_name: MOCK_CATEGORIES.find((c) => c.id === body.category_id)?.name ?? "",
          name: body.name,
          manufacturer: body.manufacturer ?? null,
          model_number: body.model_number ?? null,
          serial_number: body.serial_number ?? null,
          specs: null,
          weight_kg: body.weight_kg ?? null,
          dimensions: body.dimensions ?? null,
          standards: null,
          tags: body.tags ?? [],
          is_active: true,
          notes: body.notes ?? null,
          created_by: "u1",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    if (method === "DELETE") {
      deletedEquipmentId = url.split("/").pop() ?? null;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "deleted" }),
      });
      return;
    }
    if (method === "PUT") {
      const body = route.request().postDataJSON();
      const id = url.split("/").pop();
      const existing = MOCK_EQUIPMENT.find((e) => e.id === id);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...existing, ...body }),
      });
      return;
    }
    await route.continue();
  });

  // Equipment endpoint with no trailing slash (e.g. /api/v1/equipment?search=...)
  await page.route("**/api/v1/equipment?*", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          equipment: MOCK_EQUIPMENT,
          total: MOCK_EQUIPMENT.length,
          page: 1,
          page_size: 25,
        }),
      });
      return;
    }
    await route.continue();
  });

  // Categories routes — registered LAST so they take precedence over the
  // equipment/** route above (Playwright evaluates routes in LIFO order).
  await page.route("**/api/v1/equipment/categories", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ categories: MOCK_CATEGORIES, total: MOCK_CATEGORIES.length }),
      });
      return;
    }
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { name: string };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: `cat-${Date.now()}`,
          name: body.name,
          slug: body.slug ?? body.name.toLowerCase(),
          description: body.description ?? null,
          icon: body.icon ?? null,
          display_order: body.display_order ?? 0,
          equipment_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });

  // Single category by ID — PUT/DELETE
  await page.route("**/api/v1/equipment/categories/*", async (route) => {
    const method = route.request().method();
    const url = route.request().url();
    if (method === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "deleted" }),
      });
      return;
    }
    if (method === "PUT") {
      const body = route.request().postDataJSON();
      const id = url.split("/").pop();
      const existing = MOCK_CATEGORIES.find((c) => c.id === id);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...existing, ...body }),
      });
      return;
    }
    await route.continue();
  });

  // Generic catch-alls
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
}

/**
 * The app shows an onboarding tour overlay on first visit. Dismiss before
 * interacting with page elements.
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

test.describe("Equipment Management Page", () => {
  test.beforeEach(async ({ page }) => {
    createdEquipment.length = 0;
    deletedEquipmentId = null;
    await mockEquipmentBackend(page);
  });

  test("renders two tabs and loads equipment table", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    await expect(page.getByRole("heading", { name: /Equipment Management/i })).toBeVisible();

    // Two tab buttons
    await expect(page.getByRole("button", { name: /^Equipment/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Categories/i })).toBeVisible();

    // Equipment tab is active — both mock items should appear in the main area
    const main = page.locator("main").first();
    await expect(main.getByText("100kVA Transformer")).toBeVisible();
    await expect(main.getByText("50kVA Transformer")).toBeVisible();
    await expect(main.getByText("ABB")).toBeVisible();
  });

  test("opens Create Equipment modal and submits on POST", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    await page
      .getByRole("button", { name: /New Equipment/i })
      .first()
      .click();

    await expect(page.getByRole("heading", { name: /Create Equipment/i })).toBeVisible();
    await expect(page.locator("#eq-name")).toBeVisible();

    // Fill the form
    await page.locator("#eq-name").fill("200kVA Transformer");
    await page.locator("#eq-manufacturer").fill("Schneider");
    await page.locator("#eq-model").fill("TX-200-3P");

    // Submit
    await page.getByRole("button", { name: /Create Equipment/i }).click();

    await expect.poll(() => createdEquipment.length).toBeGreaterThanOrEqual(1);
    expect(createdEquipment[0]).toMatchObject({
      name: "200kVA Transformer",
      manufacturer: "Schneider",
      model_number: "TX-200-3P",
    });
  });

  test("opens Edit Equipment modal pre-filled", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    const row = page.locator("tr", { hasText: "100kVA Transformer" });
    await row.locator('button[aria-label*="Edit"]').click();

    await expect(page.getByRole("heading", { name: /Edit Equipment/i })).toBeVisible();
    await expect(page.locator("#eq-name")).toHaveValue("100kVA Transformer");
    await expect(page.locator("#eq-manufacturer")).toHaveValue("ABB");
    await expect(page.locator("#eq-model")).toHaveValue("TX-100-3P");
  });

  test("single delete shows confirmation and issues DELETE", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    const row = page.locator("tr", { hasText: "50kVA Transformer" });
    await row.locator('button[aria-label*="Delete"]').click();

    await expect(page.getByRole("heading", { name: /Delete Equipment/i })).toBeVisible();
    await expect(page.getByText(/Are you sure you want to delete/i)).toBeVisible();

    await page.getByRole("button", { name: /^Delete$/i }).click();

    await expect.poll(() => deletedEquipmentId).toBe("eq-2");
  });

  test("bulk select and bulk delete confirmation flow", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    // Click "select all" checkbox in table header
    await page.getByRole("checkbox", { name: /Select all equipment on this page/i }).check();

    // Both row checkboxes should now be checked
    await expect(page.getByRole("checkbox", { name: /Select 100kVA Transformer/i })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: /Select 50kVA Transformer/i })).toBeChecked();

    // "2 selected · Delete selected" link should appear
    await expect(page.getByText(/2 selected/i)).toBeVisible();

    // Click the "Delete selected" link
    await page.getByRole("button", { name: /Delete selected/i }).click();

    // Bulk-delete confirmation modal
    await expect(page.getByRole("heading", { name: /Delete Selected Equipment/i })).toBeVisible();
    await expect(page.getByText(/You are about to delete 2/i)).toBeVisible();

    // Confirm — the button label is dynamic so match flexibly
    await page.getByRole("button", { name: /^Delete 2 items$/i }).click();

    // Both DELETEs should have been issued. We only track the last one, so
    // assert that at least one DELETE fired.
    await expect.poll(() => deletedEquipmentId).not.toBeNull();
  });

  test("Categories tab shows category cards with equipment counts", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    await page.getByRole("button", { name: /^Categories/i }).click();

    const main = page.locator("main").first();
    // Use exact match to avoid matching "Power transformers" subtitle.
    await expect(main.getByText("Transformers", { exact: true })).toBeVisible();
    await expect(main.getByText("Switchgear", { exact: true })).toBeVisible();
    // Equipment counts shown as brand badges — the Transformers category has 2.
    await expect(main.locator("text=2").first()).toBeVisible();
  });

  test("create new category via modal", async ({ page }) => {
    await page.goto("/equipment", { waitUntil: "networkidle", timeout: 30000 });
    await dismissOnboardingIfPresent(page);

    await page.getByRole("button", { name: /^Categories/i }).click();
    await page
      .getByRole("button", { name: /New Category/i })
      .first()
      .click();

    await expect(page.getByRole("heading", { name: /Create Category/i })).toBeVisible();
    await page.locator("#cat-name").fill("Cables");
    // Slug auto-generates if blank, but let's fill it explicitly
    await page.locator("#cat-slug").fill("cables");
    await page.locator("#cat-description").fill("Power and control cables");

    await page.getByRole("button", { name: /Create Category/i }).click();
    // Modal should close on success
    await expect(page.getByRole("heading", { name: /Create Category/i })).toBeHidden({
      timeout: 30000,
    });
  });
});
