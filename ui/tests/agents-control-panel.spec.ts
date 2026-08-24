/**
 * Playwright smoke test for the Agents Control Panel page (TASK-5).
 *
 * Covers the wiring to all 15 JSON endpoints in api/agents.py:
 *   1. Agents tab loads list from GET /api/v1/agents + opens detail modal (GET /{id})
 *   2. Agent Chat: ETAP Expert submit fires POST /etap-expert/chat
 *   3. CUA & Safety: health card loads from GET /etap-gui/health
 *   4. Kill-switch activate opens modal then fires POST /kill-switch/activate?reason=
 *   5. Audit verify fires GET /safety/audit/verify and shows verdict
 *   6. SIEM tab loads events from GET /siem/events
 *   7. Orchestration: fill form + submit fires POST /ahmed-etap/orchestrate
 *
 * The test mocks the backend via page.route() so it can run without a live API.
 *
 * Ref: TASK-5
 */

import { type Page, expect, test } from "@playwright/test";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_AGENTS = [
  {
    id: "load-flow-agent",
    name: "Load Flow Agent",
    description: "Performs Newton-Raphson load flow analysis",
    standard: "IEEE 399",
    status: "active",
    capabilities: ["load_flow", "voltage_profile", "power_losses"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "short-circuit-agent",
    name: "Short Circuit Agent",
    description: "IEC 60909 short-circuit analysis",
    standard: "IEC 60909",
    status: "active",
    capabilities: ["short_circuit", "iec_60909", "equipment_rating"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "etap-gui-agent",
    name: "ETAP GUI Agent",
    description: "Computer Use Agent for ETAP GUI automation",
    standard: "CUA",
    status: "coming_soon",
    capabilities: ["gui_automation", "cua", "screenshot_analysis"],
    model: "gpt-4o",
    provider: "openai",
  },
];

const MOCK_AGENTS_INFO = {
  success: true,
  data: {
    agents: { "load-flow-agent": { loaded: true } },
    available_prompts: ["load_flow.md", "short_circuit.md", "arc_flash.md"],
    prompt_count: 3,
  },
};

const MOCK_EXPERT_RESULT = {
  success: true,
  data: {
    format: "A",
    analysis: "REQUEST ANALYSIS: COMPLETE",
    steps: ["PARSE", "SEARCH", "VALIDATE", "SIMULATE", "FORMAT", "QA"],
  },
};

const MOCK_CUA_HEALTH = {
  success: true,
  data: {
    cua_loop_available: true,
    missing_dependencies: [],
    gemini_vision: { available: true, model: "gemini-1.5-pro" },
    agent_info: { name: "etap-gui-agent", version: "1.0" },
    life_safety: {
      kill_switch_active: false,
      audit_chain_valid: true,
      audit_chain_broken_entries: [],
      lethal_patterns_count: 12,
      dual_confirmation_patterns_count: 5,
      cooldown_seconds: 3,
      degraded_vision_sources: [],
    },
  },
};

const MOCK_KILL_ACTIVATE = {
  success: true,
  data: {
    kill_switch_active: true,
    reason: "test_activation",
    activated_at: "2026-08-04T10:00:00Z",
    message: "CUA Loop will abort on next action. Call /deactivate to resume.",
  },
};

const MOCK_AUDIT_VERIFY = {
  success: true,
  data: {
    is_valid: true,
    broken_entries: [],
    total_broken: 0,
    message: "Audit chain is intact",
  },
};

const MOCK_SIEM_HEALTH = {
  success: true,
  data: {
    enabled: true,
    protocol: "file",
    log_file: "/tmp/siem.log",
    events_forwarded: 42,
  },
};

const MOCK_SIEM_EVENTS = {
  success: true,
  data: {
    events: [
      { event: "kill_switch_activated", level: "critical", timestamp: "2026-08-04T10:00:00Z" },
      { event: "cua_action_executed", level: "info", timestamp: "2026-08-04T09:55:00Z" },
      { event: "lethal_pattern_blocked", level: "warning", timestamp: "2026-08-04T09:50:00Z" },
    ],
    total: 3,
    log_file: "/tmp/siem.log",
  },
};

const MOCK_AHMED_INFO = {
  success: true,
  data: {
    skill_text_chars: 12500,
    peer_review_matrix: { load_flow: "protection_agent" },
    token_budget_defaults: { default: 8000, compress_at: 5600 },
    max_retries: 2,
    math_guard_tolerance_pct: 0.01,
  },
};

const MOCK_ORCHESTRATE = {
  success: true,
  data: {
    verdict: "approved",
    math_guard: { passed: true, claim_value: 1.0, recomputed_value: 1.0001 },
    peer_review: { passed: true, reviewer: "protection_agent", notes: "ok" },
    iterations: 1,
    elapsed_seconds: 2.34,
    response: { bus_voltages: { "1": 1.0 } },
  },
};

// Track POST side-effects so tests can assert them.
let expertChatCalled = false;
let killActivateCalled = false;
let killActivateReason: string | null = null;
let auditVerifyCalled = false;
let orchestrateCalled = false;
let orchestrateStudyType: string | null = null;

async function mockAgentsBackend(page: Page) {
  // Auth + onboarding-dismissal (same pattern as email-dashboard.spec.ts)
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

  // GET "" (list) — the bare prefix /api/v1/agents has NO trailing path, so
  // the catch-all glob **/api/v1/agents/** does NOT match it. Register a
  // dedicated bare route FIRST (route matching is registration-order).
  await page.route("**/api/v1/agents", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, agents: MOCK_AGENTS }),
    }),
  );

  // Single catch-all for /api/v1/agents/**
  await page.route("**/api/v1/agents/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // GET /info
    if (method === "GET" && url.includes("/agents/info")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_AGENTS_INFO),
      });
      return;
    }

    // GET /{agent_id} — match a single path segment after /agents/
    // Excludes known sub-paths (info, etap-expert, etap-gui, ahmed-etap).
    if (method === "GET" && /\/api\/v1\/agents\/[^/]+$/.test(url) && !url.includes("/info")) {
      const match = url.match(/\/api\/v1\/agents\/([^/?]+)$/);
      const id = match?.[1] ?? "unknown";
      const agent = MOCK_AGENTS.find((a) => a.id === id) ?? MOCK_AGENTS[0];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, agent }),
      });
      return;
    }

    // POST /etap-expert/chat
    if (method === "POST" && url.includes("/etap-expert/chat")) {
      expertChatCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_EXPERT_RESULT),
      });
      return;
    }

    // POST /etap-gui/chat
    if (method === "POST" && url.includes("/etap-gui/chat")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, data: { format: "A", mode: "Analyze" } }),
      });
      return;
    }

    // POST /etap-gui/execute
    if (method === "POST" && url.includes("/etap-gui/execute")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: { objective_complete: true, steps_taken: 3 },
        }),
      });
      return;
    }

    // GET /etap-gui/health
    if (method === "GET" && url.includes("/etap-gui/health")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CUA_HEALTH),
      });
      return;
    }

    // POST /etap-gui/kill-switch/activate
    if (method === "POST" && url.includes("/kill-switch/activate")) {
      killActivateCalled = true;
      const u = new URL(url);
      killActivateReason = u.searchParams.get("reason");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_KILL_ACTIVATE),
      });
      return;
    }

    // POST /etap-gui/kill-switch/deactivate
    if (method === "POST" && url.includes("/kill-switch/deactivate")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: { was_active: true, kill_switch_active: false, message: "Deactivated." },
        }),
      });
      return;
    }

    // GET /etap-gui/safety/health
    if (method === "GET" && url.includes("/safety/health")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, data: MOCK_CUA_HEALTH.data.life_safety }),
      });
      return;
    }

    // GET /etap-gui/safety/audit/verify
    if (method === "GET" && url.includes("/safety/audit/verify")) {
      auditVerifyCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_AUDIT_VERIFY),
      });
      return;
    }

    // GET /etap-gui/siem/health
    if (method === "GET" && url.includes("/siem/health")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SIEM_HEALTH),
      });
      return;
    }

    // GET /etap-gui/siem/events
    if (method === "GET" && url.includes("/siem/events")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SIEM_EVENTS),
      });
      return;
    }

    // GET /ahmed-etap/info
    if (method === "GET" && url.includes("/ahmed-etap/info")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_AHMED_INFO),
      });
      return;
    }

    // POST /ahmed-etap/orchestrate
    if (method === "POST" && url.includes("/ahmed-etap/orchestrate")) {
      orchestrateCalled = true;
      try {
        const body = route.request().postDataJSON() as { study_type?: string };
        orchestrateStudyType = body?.study_type ?? null;
      } catch {
        orchestrateStudyType = null;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_ORCHESTRATE),
      });
      return;
    }

    await route.continue();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Agents Control Panel page (TASK-5)", () => {
  test.beforeEach(() => {
    expertChatCalled = false;
    killActivateCalled = false;
    killActivateReason = null;
    auditVerifyCalled = false;
    orchestrateCalled = false;
    orchestrateStudyType = null;
  });

  test("Agents tab loads list and opens detail modal", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Header
    await expect(page.getByRole("heading", { name: /Agents Control Panel/i })).toBeVisible();

    // Agents table — wait for mock agents to load
    const agentsTable = page.locator("table").first();
    await expect(agentsTable.getByText("Load Flow Agent")).toBeVisible({ timeout: 20_000 });
    await expect(agentsTable.getByText("Short Circuit Agent")).toBeVisible();
    await expect(agentsTable.getByText("IEEE 399")).toBeVisible();

    // Click the first "View" button to open the detail modal. The button
    // text is just "View" (the tooltip "View agent detail" is a title attr,
    // not accessible to getByRole name).
    const viewBtn = page.getByRole("button", { name: /^View$/i }).first();
    await viewBtn.click();

    // Modal opens with agent detail — the "Agent Detail" heading only
    // appears inside the modal.
    await expect(page.getByText("Agent Detail").first()).toBeVisible({ timeout: 15_000 });
    // Capabilities only appear in the modal (not the table)
    await expect(page.getByText("load_flow").first()).toBeVisible();
    await expect(page.getByText("voltage_profile")).toBeVisible();
  });

  test("Agent Chat: ETAP Expert submit fires POST /etap-expert/chat", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the Agent Chat tab
    await page.getByRole("button", { name: /^Agent Chat$/i }).click();

    // The first textarea is the ETAP Expert input
    const expertTextarea = page.locator("textarea").first();
    await expertTextarea.fill("What is the load flow solution for a 5-bus system?");

    // Click the "Ask Expert" button
    await page.getByRole("button", { name: /Ask Expert/i }).click();

    // The POST should have fired
    await expect.poll(() => expertChatCalled, { timeout: 15_000 }).toBe(true);

    // The result should display — "REQUEST ANALYSIS: COMPLETE" only appears
    // in the result JSON block.
    await expect(page.getByText(/REQUEST ANALYSIS: COMPLETE/)).toBeVisible({
      timeout: 15_000,
    });
  });

  test("CUA & Safety: health card loads from GET /etap-gui/health", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the CUA & Safety tab
    await page.getByRole("button", { name: /^CUA & Safety$/i }).click();

    // The CUA Loop stat card should show "Available" (green badge from mock)
    await expect(page.getByText("Available").first()).toBeVisible({ timeout: 20_000 });
    // Kill Switch card should show "Inactive"
    await expect(page.getByText("Inactive").first()).toBeVisible();
    // Audit Chain card should show "Valid"
    await expect(page.getByText("Valid").first()).toBeVisible();
    // Lethal Patterns card should show "12"
    await expect(page.getByText("12").first()).toBeVisible();
  });

  test("Kill-switch activate opens modal then fires POST with reason", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the CUA & Safety tab
    await page.getByRole("button", { name: /^CUA & Safety$/i }).click();

    // Wait for health to load so the activate button is enabled
    await expect(page.getByText("Available").first()).toBeVisible({ timeout: 20_000 });

    // Click "Activate Kill Switch" button (danger variant)
    await page.getByRole("button", { name: /Activate Kill Switch/i }).click();

    // Confirmation modal should open
    await expect(
      page.getByRole("heading", { name: /Activate Emergency Kill Switch/i }),
    ).toBeVisible({ timeout: 15_000 });

    // Change the reason
    const reasonInput = page.locator('input[type="text"]').last();
    await reasonInput.fill("test_activation");

    // Click "Activate Now"
    await page.getByRole("button", { name: /Activate Now/i }).click();

    // The POST should have fired with reason=test_activation
    await expect.poll(() => killActivateCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => killActivateReason, { timeout: 15_000 }).toBe("test_activation");
  });

  test("Audit verify fires GET /safety/audit/verify and shows verdict", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the CUA & Safety tab
    await page.getByRole("button", { name: /^CUA & Safety$/i }).click();

    // Wait for health to load
    await expect(page.getByText("Available").first()).toBeVisible({ timeout: 20_000 });

    // Click "Verify Audit Chain"
    await page.getByRole("button", { name: /Verify Audit Chain/i }).click();

    // The GET should have fired
    await expect.poll(() => auditVerifyCalled, { timeout: 15_000 }).toBe(true);

    // The verdict should display — "Chain Intact" only appears after verify
    await expect(page.getByText("Chain Intact").first()).toBeVisible({ timeout: 15_000 });
    // The mock message — use .first() because the success toast ALSO renders
    // this text (the verifyAudit handler calls notify("success", message)).
    await expect(page.getByText("Audit chain is intact").first()).toBeVisible();
  });

  test("SIEM tab loads events from GET /siem/events", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the SIEM tab
    await page.getByRole("button", { name: /^SIEM$/i }).click();

    // The SIEM events table should show mock events
    const siemTable = page.locator("table").first();
    await expect(siemTable.getByText("kill_switch_activated")).toBeVisible({ timeout: 20_000 });
    await expect(siemTable.getByText("cua_action_executed")).toBeVisible();
    await expect(siemTable.getByText("lethal_pattern_blocked")).toBeVisible();
    // The syslog forwarder health JSON should show the log_file
    await expect(page.getByText("/tmp/siem.log").first()).toBeVisible();
  });

  test("Orchestration: fill form + submit fires POST /ahmed-etap/orchestrate", async ({ page }) => {
    await mockAgentsBackend(page);
    await page.goto("/admin/agents");

    // Go to the Orchestration tab
    await page.getByRole("button", { name: /^Orchestration$/i }).click();

    // Skill info card should load
    await expect(page.getByText("12,500 chars")).toBeVisible({ timeout: 20_000 });

    // Change the study type. The study type input is the first text input
    // in the orchestration form — scope to <main> to avoid matching the
    // navbar global-search textbox.
    const mainRegion = page.locator("main");
    const orchInputs = mainRegion.locator('input[type="text"]');
    await orchInputs.first().fill("short_circuit");

    // Click "Run Orchestration"
    await page.getByRole("button", { name: /Run Orchestration/i }).click();

    // The POST should have fired with study_type=short_circuit
    await expect.poll(() => orchestrateCalled, { timeout: 15_000 }).toBe(true);
    await expect.poll(() => orchestrateStudyType, { timeout: 15_000 }).toBe("short_circuit");

    // The verdict badge should display "approved"
    await expect(page.getByText("approved").first()).toBeVisible({ timeout: 15_000 });
  });
});
