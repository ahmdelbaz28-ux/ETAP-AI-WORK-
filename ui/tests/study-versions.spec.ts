/**
 * Playwright smoke test for the Study Versions page (TASK-7).
 *
 * Covers the wiring to all 4 endpoints in api/study_versions.py
 * (prefix /api/v1/projects/{project_id}/studies/{study_id}/versions):
 *   1. Versions tab loads list from GET /
 *   2. Rollback button POSTs /{version_id}/rollback and shows result
 *   3. Create Snapshot tab POSTs / and shows the new version
 *   4. Compare tab GETs /{v1}/compare/{v2} and shows config/results diff
 *   5. Versions tab handles 404 study-not-found with error banner
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-7
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const PROJECT_ID = "proj-001";
const STUDY_ID = "study-001";

const MOCK_VERSIONS = {
        versions: [
                {
                        id: "ver-003",
                        study_id: STUDY_ID,
                        project_id: PROJECT_ID,
                        version_number: 3,
                        label: "Pre-deploy baseline",
                        description: "Snapshot before production deploy",
                        diff_summary: null,
                        created_by: "u1",
                        created_at: "2026-08-04T10:00:00Z",
                },
                {
                        id: "ver-002",
                        study_id: STUDY_ID,
                        project_id: PROJECT_ID,
                        version_number: 2,
                        label: "Added load flow",
                        description: "Configured new load flow case",
                        diff_summary: "Added: load_flow.case_2",
                        created_by: "u1",
                        created_at: "2026-08-03T15:00:00Z",
                },
                {
                        id: "ver-001",
                        study_id: STUDY_ID,
                        project_id: PROJECT_ID,
                        version_number: 1,
                        label: "Initial snapshot",
                        description: null,
                        diff_summary: null,
                        created_by: "u2",
                        created_at: "2026-08-01T09:00:00Z",
                },
        ],
        total: 3,
};

const MOCK_ROLLBACK = {
        message: "Study rolled back to version 2",
        version: 2,
};

const MOCK_CREATE = {
        id: "ver-004",
        study_id: STUDY_ID,
        project_id: PROJECT_ID,
        version_number: 4,
        label: "Manual snapshot",
        description: "Created from UI",
        created_by: "u1",
        created_at: "2026-08-04T11:30:00Z",
};

const MOCK_COMPARE = {
        version_a: MOCK_VERSIONS.versions[1], // v2
        version_b: MOCK_VERSIONS.versions[0], // v3
        config_diff: {
                load_flow: { from: { case: 1 }, to: { case: 2 } },
                voltage_limit: { from: 0.95, to: 0.93 },
        },
        results_diff: {
                total_loss: { from: 12.5, to: 14.8 },
        },
};

// Track call counts so we can assert side-effects.
let listCalled = false;
let listProjectId = "";
let listStudyId = "";
let rollbackCalled = false;
let rollbackVersionId = "";
let createCalled = false;
let createBody: { label?: string; description?: string } | null = null;
let compareCalled = false;
let compareV1 = "";
let compareV2 = "";

async function mockStudyVersionsBackend(
        page: Page,
        opts?: { listStatus?: 404 },
) {
        const listStatus = opts?.listStatus ?? 200;

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

        // Single combined handler for all /api/v1/projects/{p}/studies/{s}/versions** URLs.
        // Using a regex pattern so we can reliably differentiate list/create/rollback/compare
        // based on URL shape AND method, rather than relying on glob `*` for path segments.
        await page.route(
                /\/api\/v1\/projects\/[^/]+\/studies\/[^/]+\/versions/,
                async (route) => {
                        const url = route.request().url();
                        const method = route.request().method();

                        // POST /versions/{version_id}/rollback
                        if (/\/versions\/[^/]+\/rollback$/.test(url) && method === "POST") {
                                rollbackCalled = true;
                                const match = url.match(/\/versions\/([^/]+)\/rollback/);
                                rollbackVersionId = match?.[1] ? decodeURIComponent(match[1]) : "";
                                return route.fulfill({
                                        status: 200,
                                        contentType: "application/json",
                                        body: JSON.stringify(MOCK_ROLLBACK),
                                });
                        }

                        // GET /versions/{v1}/compare/{v2}
                        if (/\/versions\/[^/]+\/compare\/[^/]+$/.test(url) && method === "GET") {
                                compareCalled = true;
                                const match = url.match(/\/versions\/([^/]+)\/compare\/([^/?]+)/);
                                compareV1 = match?.[1] ? decodeURIComponent(match[1]) : "";
                                compareV2 = match?.[2] ? decodeURIComponent(match[2]) : "";
                                return route.fulfill({
                                        status: 200,
                                        contentType: "application/json",
                                        body: JSON.stringify(MOCK_COMPARE),
                                });
                        }

                        // POST /versions (create)
                        if (url.endsWith("/versions") && method === "POST") {
                                createCalled = true;
                                try {
                                        createBody = route.request().postDataJSON() as {
                                                label?: string;
                                                description?: string;
                                        } | null;
                                } catch {
                                        createBody = null;
                                }
                                return route.fulfill({
                                        status: 201,
                                        contentType: "application/json",
                                        body: JSON.stringify(MOCK_CREATE),
                                });
                        }

                        // GET /versions (list)
                        if (url.endsWith("/versions") && method === "GET") {
                                listCalled = true;
                                const match = url.match(
                                        /\/projects\/([^/]+)\/studies\/([^/]+)\/versions/,
                                );
                                listProjectId = match?.[1] ? decodeURIComponent(match[1]) : "";
                                listStudyId = match?.[2] ? decodeURIComponent(match[2]) : "";

                                if (listStatus === 404) {
                                        return route.fulfill({
                                                status: 404,
                                                contentType: "application/json",
                                                body: JSON.stringify({ detail: "Study not found" }),
                                        });
                                }
                                return route.fulfill({
                                        status: 200,
                                        contentType: "application/json",
                                        body: JSON.stringify(MOCK_VERSIONS),
                                });
                        }

                        // Anything else — fall through to the real network (shouldn't happen in tests).
                        return route.continue();
                },
        );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Study Versions page (TASK-7)", () => {
        test.beforeEach(() => {
                listCalled = false;
                listProjectId = "";
                listStudyId = "";
                rollbackCalled = false;
                rollbackVersionId = "";
                createCalled = false;
                createBody = null;
                compareCalled = false;
                compareV1 = "";
                compareV2 = "";
        });

        test("Versions tab loads list from GET /versions", async ({ page }) => {
                await mockStudyVersionsBackend(page);
                await page.goto("/admin/study-versions");

                // Header
                await expect(
                        page.getByRole("heading", { name: /Study Versions/i }),
                ).toBeVisible();

                // Fill the target study form
                await page.getByTestId("sv-project-id").fill(PROJECT_ID);
                await page.getByTestId("sv-study-id").fill(STUDY_ID);
                await page.getByTestId("sv-load-btn").click();

                // GET should have fired with the right path params
                await expect.poll(() => listCalled, { timeout: 5_000 }).toBe(true);
                await expect.poll(() => listProjectId, { timeout: 5_000 }).toBe(PROJECT_ID);
                await expect.poll(() => listStudyId, { timeout: 5_000 }).toBe(STUDY_ID);

                // Target summary should show the locked IDs
                await expect(page.getByTestId("sv-target-summary")).toContainText(
                        PROJECT_ID,
                );
                await expect(page.getByTestId("sv-target-summary")).toContainText(STUDY_ID);

                // Versions table should show all 3 rows in order (newest first)
                const table = page.getByTestId("sv-versions-table");
                await expect(table).toBeVisible({ timeout: 5_000 });
                await expect(table.getByTestId("sv-version-number-ver-003")).toHaveText(
                        "v3",
                );
                await expect(table.getByTestId("sv-version-number-ver-002")).toHaveText(
                        "v2",
                );
                await expect(table.getByTestId("sv-version-number-ver-001")).toHaveText(
                        "v1",
                );
                await expect(table.getByText("Pre-deploy baseline")).toBeVisible();
                await expect(table.getByText("Initial snapshot")).toBeVisible();
        });

        test("Rollback button POSTs /{version_id}/rollback and shows result", async ({
                page,
        }) => {
                await mockStudyVersionsBackend(page);
                await page.goto("/admin/study-versions");

                // Load versions first
                await page.getByTestId("sv-project-id").fill(PROJECT_ID);
                await page.getByTestId("sv-study-id").fill(STUDY_ID);
                await page.getByTestId("sv-load-btn").click();

                // Wait for the table to render
                await expect(page.getByTestId("sv-versions-table")).toBeVisible({
                        timeout: 5_000,
                });

                // Click the Rollback button on v2 (ver-002)
                await page.getByTestId("sv-rollback-btn-ver-002").click();

                // POST should have fired with the right version_id
                await expect.poll(() => rollbackCalled, { timeout: 5_000 }).toBe(true);
                await expect
                        .poll(() => rollbackVersionId, { timeout: 5_000 })
                        .toBe("ver-002");

                // Result block should show the message + version
                const result = page.getByTestId("sv-rollback-result");
                await expect(result).toBeVisible({ timeout: 5_000 });
                await expect(result.getByText("Rollback successful")).toBeVisible();
                await expect(result.getByText(/rolled back to version 2/)).toBeVisible();
                await expect(result.getByText("v2", { exact: true })).toBeVisible();

                // Success toast (the result block also contains the same message text —
                // scope to the toast which is rendered last in a fixed-position container).
                await expect(page.getByText(/rolled back to version 2/i).last()).toBeVisible({
                        timeout: 5_000,
                });
        });

        test("Create Snapshot tab POSTs /versions and shows the new version", async ({
                page,
        }) => {
                await mockStudyVersionsBackend(page);
                await page.goto("/admin/study-versions");

                // Load versions first so the create tab has a target study locked in
                await page.getByTestId("sv-project-id").fill(PROJECT_ID);
                await page.getByTestId("sv-study-id").fill(STUDY_ID);
                await page.getByTestId("sv-load-btn").click();
                await expect(page.getByTestId("sv-versions-table")).toBeVisible({
                        timeout: 5_000,
                });

                // Switch to the Create Snapshot tab
                await page
                        .getByRole("button", { name: /Create Snapshot/i })
                        .first()
                        .click();

                // Fill the form
                await page.getByTestId("sv-create-label").fill("Manual snapshot");
                await page.getByTestId("sv-create-description").fill("Created from UI");

                // Submit
                await page.getByTestId("sv-create-submit").click();

                // POST should have fired with the expected body
                await expect.poll(() => createCalled, { timeout: 5_000 }).toBe(true);
                await expect
                        .poll(() => createBody, { timeout: 5_000 })
                        .toEqual({ label: "Manual snapshot", description: "Created from UI" });

                // Result card should show the new version
                const result = page.getByTestId("sv-create-result");
                await expect(result).toBeVisible({ timeout: 5_000 });
                await expect(result.getByText("Snapshot created")).toBeVisible();
                await expect(result.getByTestId("sv-create-version-number")).toHaveText(
                        "v4",
                );
                await expect(result.getByText("ver-004")).toBeVisible();
                await expect(result.getByText("Manual snapshot")).toBeVisible();

                // Success toast
                await expect(page.getByText(/Snapshot created: v4/)).toBeVisible({
                        timeout: 5_000,
                });
        });

        test("Compare tab GETs /{v1}/compare/{v2} and shows config+results diff", async ({
                page,
        }) => {
                await mockStudyVersionsBackend(page);
                await page.goto("/admin/study-versions");

                // Load versions first so the compare dropdowns are populated
                await page.getByTestId("sv-project-id").fill(PROJECT_ID);
                await page.getByTestId("sv-study-id").fill(STUDY_ID);
                await page.getByTestId("sv-load-btn").click();
                await expect(page.getByTestId("sv-versions-table")).toBeVisible({
                        timeout: 5_000,
                });

                // Switch to the Compare tab
                await page
                        .getByRole("button", { name: /Compare/i })
                        .first()
                        .click();

                // Pick v2 (ver-002) for A and v3 (ver-003) for B
                await page.getByTestId("sv-compare-v1").selectOption("ver-002");
                await page.getByTestId("sv-compare-v2").selectOption("ver-003");

                // Submit
                await page.getByTestId("sv-compare-submit").click();

                // GET should have fired with the right v1/v2 IDs
                await expect.poll(() => compareCalled, { timeout: 5_000 }).toBe(true);
                await expect.poll(() => compareV1, { timeout: 5_000 }).toBe("ver-002");
                await expect.poll(() => compareV2, { timeout: 5_000 }).toBe("ver-003");

                // Compare result block should render with both metadata cards + diff tables
                const result = page.getByTestId("sv-compare-result");
                await expect(result).toBeVisible({ timeout: 5_000 });

                // Version A metadata
                await expect(result.getByText("v2").first()).toBeVisible();
                await expect(result.getByText("Added load flow").first()).toBeVisible();
                // Version B metadata
                await expect(result.getByText("v3").first()).toBeVisible();
                await expect(result.getByText("Pre-deploy baseline").first()).toBeVisible();

                // Config diff — 2 rows: load_flow + voltage_limit
                const configDiff = result.getByTestId("sv-config-diff");
                await expect(configDiff).toBeVisible();
                await expect(
                        configDiff.getByTestId("sv-config-diff-row-load_flow"),
                ).toBeVisible();
                await expect(
                        configDiff.getByTestId("sv-config-diff-row-voltage_limit"),
                ).toBeVisible();
                // 2 changed key(s) subtitle
                await expect(page.getByText(/2 changed key\(s\)/).first()).toBeVisible();

                // Results diff — 1 row: total_loss
                const resultsDiff = result.getByTestId("sv-results-diff");
                await expect(resultsDiff).toBeVisible();
                await expect(
                        resultsDiff.getByTestId("sv-results-diff-row-total_loss"),
                ).toBeVisible();
                // from 12.5 / to 14.8
                await expect(resultsDiff.getByText("12.5")).toBeVisible();
                await expect(resultsDiff.getByText("14.8")).toBeVisible();

                // Success toast
                await expect(page.getByText(/Comparison loaded/)).toBeVisible({
                        timeout: 5_000,
                });
        });

        test("Versions tab handles 404 study-not-found with error banner", async ({
                page,
        }) => {
                await mockStudyVersionsBackend(page, { listStatus: 404 });
                await page.goto("/admin/study-versions");

                // Fill the form with a non-existent study
                await page.getByTestId("sv-project-id").fill("proj-missing");
                await page.getByTestId("sv-study-id").fill("study-missing");
                await page.getByTestId("sv-load-btn").click();

                // GET should have fired
                await expect.poll(() => listCalled, { timeout: 5_000 }).toBe(true);

                // Error banner (role=alert) should mention HTTP 404 + "Study not found"
                await expect(
                        page
                                .getByRole("alert")
                                .getByText(/404.*Study not found|Study not found.*404/),
                ).toBeVisible({ timeout: 5_000 });

                // The versions table should NOT be rendered
                await expect(page.getByTestId("sv-versions-table")).toHaveCount(0);
        });
});
