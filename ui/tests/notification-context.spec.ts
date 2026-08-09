/**
 * Playwright smoke test for the NotificationContext (TASK-3).
 *
 * Verifies the backend wiring:
 *   1. Initial hydration from GET /api/v1/notifications/?unread_only=true
 *      surfaces unread notifications as toasts.
 *   2. Clicking a backend-sourced toast fires PUT /api/v1/notifications/{id}/read.
 *   3. When the REST endpoint is unreachable, the degraded-mode banner
 *      ("Real-time notifications offline — retrying") is shown.
 *   4. Real-time push via WebSocket: a WS message from the server
 *      surfaces a new toast.
 *
 * The test mocks both HTTP (page.route) and WebSocket (page.routeWebSocket)
 * so it can run without a live backend.
 *
 * Ref: TASK-3
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_UNREAD = {
  notifications: [
    {
      id: "n-001",
      user_id: "u1",
      notification_type: "study_completed",
      title: "Study Complete",
      message: "Load flow study 'LF-2026-001' finished successfully.",
      priority: "normal",
      data: null,
      is_read: false,
      is_archived: false,
      created_at: "2026-08-04T10:00:00Z",
      read_at: null,
    },
    {
      id: "n-002",
      user_id: "u1",
      notification_type: "error_alert",
      title: "Critical Alert",
      message: "SCADA feed lost on substation SUB-7.",
      priority: "critical",
      data: null,
      is_read: false,
      is_archived: false,
      created_at: "2026-08-04T10:05:00Z",
      read_at: null,
    },
  ],
  total: 2,
  unread_count: 2,
  page: 1,
  page_size: 20,
};

const EMPTY_LIST = {
  notifications: [],
  total: 0,
  unread_count: 0,
  page: 1,
  page_size: 20,
};

// Track which notification IDs were marked as read via PUT.
const markedRead: string[] = [];

/**
 * Set up auth + onboarding-dismissal + mock the notification REST endpoints.
 *
 * `mode` controls the GET /api/v1/notifications/ mock:
 *   - "ok"        → 200 with MOCK_UNREAD (default)
 *   - "empty"     → 200 with no notifications
 *   - "error"     → 500 (to trigger degraded-mode banner)
 */
async function setupPage(page: Page, mode: "ok" | "empty" | "error" = "ok") {
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

  // Single catch-all route for /api/v1/notifications/** — handles both
  // the list endpoint (GET /) and the mark-as-read endpoint (PUT /{id}/read).
  // Using a glob is more reliable than two separate regex routes.
  await page.route("**/api/v1/notifications/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // PUT /{id}/read — mark as read
    if (method === "PUT" && /\/api\/v1\/notifications\/[^/]+\/read/.test(url)) {
      const match = url.match(/\/api\/v1\/notifications\/([^/]+)\/read/);
      const id = match?.[1] ?? "unknown";
      markedRead.push(id);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...MOCK_UNREAD.notifications[0], id, is_read: true }),
      });
      return;
    }

    // GET / — list notifications
    if (method === "GET") {
      if (mode === "error") {
        await route.fulfill({ status: 500, body: "Internal Server Error" });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mode === "empty" ? EMPTY_LIST : MOCK_UNREAD),
      });
      return;
    }

    // Default: pass through
    await route.continue();
  });

  // Also handle the no-trailing-slash variant: GET /api/v1/notifications
  await page.route("**/api/v1/notifications", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    if (mode === "error") {
      await route.fulfill({ status: 500, body: "Internal Server Error" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mode === "empty" ? EMPTY_LIST : MOCK_UNREAD),
    });
  });

  // Mock the WebSocket so it accepts the connection and lets us push
  // server-to-client messages during the test.
  await page.routeWebSocket(/\/ws\/notifications/, async (ws) => {
    // Accept the connection. We'll expose a way to push messages by
    // listening for client pings and echoing nothing; the test will
    // use page.evaluate to send via a window hook (see below).
    ws.onMessage((data) => {
      if (data === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
      }
    });
    // Stash the server socket so the test can push to it.
    // Note: page.routeWebSocket doesn't expose a global handle, so we
    // can't push from the test directly. Instead, we send one notification
    // immediately on connect.
    ws.send(
      JSON.stringify({
        type: "notification",
        id: "n-ws-001",
        notification_type: "system_alert",
        title: "WS Push",
        message: "Real-time notification from WebSocket.",
        priority: "high",
        data: null,
        created_at: "2026-08-04T10:10:00Z",
      }),
    );
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("NotificationContext backend wiring (TASK-3)", () => {
  test.beforeEach(() => {
    markedRead.length = 0;
  });

  test("hydrates unread notifications from REST on mount", async ({ page }) => {
    await setupPage(page, "ok");
    await page.goto("/dashboard");

    // Wait for the toast container to render. The container is fixed
    // bottom-right and is always present (even when empty) — but we look
    // for the actual toast content.
    const toastContainer = page.locator('div[style*="position: fixed"]').last();

    // Two unread notifications should surface as toasts.
    await expect(
      toastContainer.getByText(
        "Study Complete: Load flow study 'LF-2026-001' finished successfully.",
      ),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      toastContainer.getByText("Critical Alert: SCADA feed lost on substation SUB-7."),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("clicking a backend toast fires PUT /{id}/read", async ({ page }) => {
    await setupPage(page, "ok");
    await page.goto("/dashboard");

    // Wait for the toasts to appear, then click the first one (n-001).
    const firstToast = page.getByText(
      "Study Complete: Load flow study 'LF-2026-001' finished successfully.",
    );
    await expect(firstToast).toBeVisible({ timeout: 10_000 });
    await firstToast.click();

    // The PUT should have been issued for n-001.
    await expect.poll(() => markedRead.slice(), { timeout: 5_000 }).toContain("n-001");
  });

  test("shows degraded-mode banner when REST is unreachable", async ({ page }) => {
    await setupPage(page, "error");
    await page.goto("/dashboard");

    // The amber degraded-mode banner should appear.
    await expect(page.getByText("Real-time notifications offline — retrying")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("does not show degraded banner when REST returns empty list", async ({ page }) => {
    await setupPage(page, "empty");
    await page.goto("/dashboard");

    // No toasts, no banner — the page should just render normally.
    await expect(page.getByText("Real-time notifications offline — retrying")).not.toBeVisible({
      timeout: 5_000,
    });

    // Also no toast content should be visible.
    await expect(
      page.getByText("Study Complete: Load flow study 'LF-2026-001' finished successfully."),
    ).not.toBeVisible({ timeout: 2_000 });
  });

  test("surfaces real-time notifications pushed via WebSocket", async ({ page }) => {
    await setupPage(page, "empty"); // no REST notifications
    await page.goto("/dashboard");

    // The mocked WS pushes n-ws-001 on connect. Its toast should appear
    // even though REST returned an empty list.
    await expect(page.getByText("WS Push: Real-time notification from WebSocket.")).toBeVisible({
      timeout: 10_000,
    });
  });
});
