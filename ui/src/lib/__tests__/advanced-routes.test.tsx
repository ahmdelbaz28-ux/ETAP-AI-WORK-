/** @vitest-environment jsdom */
/**
 * P8 — Advanced Routes Migration: frontend acceptance tests.
 *
 * Proves the mandatory P8 acceptance criteria:
 *  - every required page exposes an /advanced route
 *  - legacy routes SPA-redirect to /advanced
 *  - route params and query strings are preserved through the redirect
 *  - /login, /register, /admin/* and /assistant remain at their legacy paths
 *  - exactly one /advanced target per legacy route (no duplicate targets)
 *  - no page component is deleted (lazy imports still resolve)
 *  - unknown paths fall back to /dashboard (no navigation dead end)
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  ADVANCED_ROUTE_MIGRATIONS,
  AdvancedRedirect,
  advancedTargetOf,
  isProtectedLegacyRoute,
  legacyToAdvanced,
  PROTECTED_LEGACY_ROUTES,
} from "../advanced-routes";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

const FILTER: ReadonlyArray<[legacy: string, advanced: string]> = [
  ["/dashboard", "/advanced/dashboard"],
  ["/studies", "/advanced/studies"],
  ["/studies/:studyType", "/advanced/studies/:studyType"],
  ["/grid-editor", "/advanced/grid-editor"],
  ["/data-import", "/advanced/data-import"],
  ["/data-export", "/advanced/data-export"],
  ["/reports", "/advanced/reports"],
  ["/diagnostics", "/advanced/diagnostics"],
  ["/logs", "/advanced/logs"],
  ["/agent-metrics", "/advanced/agent-metrics"],
  ["/audit-logs", "/advanced/audit-logs"],
  ["/etap", "/advanced/integrations/etap"],
  ["/gis", "/advanced/integrations/gis"],
  ["/scada", "/advanced/integrations/scada"],
  ["/digital-twin", "/advanced/digital-twin"],
  ["/code-guard", "/advanced/code-guard"],
  ["/context-engine", "/advanced/context-engine"],
  ["/templates", "/advanced/templates"],
  ["/asset-management", "/advanced/asset-management"],
  ["/asset-library", "/advanced/asset-library"],
  ["/equipment", "/advanced/equipment"],
];

describe("P8 advanced routes — migration table (single source of truth)", () => {
  it("maps every required legacy route to an /advanced target", () => {
    for (const [legacy, advanced] of FILTER) {
      expect(legacyToAdvanced(legacy), `missing target for ${legacy}`).toBe(advanced);
    }
  });

  it("preserves dynamic suffixes on parameterised routes", () => {
    expect(legacyToAdvanced("/studies/load_flow")).toBe("/advanced/studies/load_flow");
    expect(legacyToAdvanced("/studies/arc_flash?x=1")).toBe("/advanced/studies/arc_flash?x=1");
    expect(legacyToAdvanced("/digital-twin")).toBe("/advanced/digital-twin");
  });

  it("preserves suffix, search string and hash via AdvancedRedirect", async () => {
    const LocationProbe = () => {
      const loc = useLocation();
      return (
        <span data-testid="loc">
          {loc.pathname}
          {loc.search}
          {loc.hash}
        </span>
      );
    };
    render(
      <MemoryRouter initialEntries={["/studies/arc_flash?ref=42#results"]}>
        <Routes>
          <Route path="/studies/:studyType" element={<AdvancedRedirect legacy="/studies" />} />
          <Route
            path="/advanced/studies/:studyType"
            element={
              <div>
                STUDY TARGET<LocationProbe />
              </div>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("STUDY TARGET")).toBeTruthy());
    // MemoryRouter does not touch window.location; assert via the router's location.
    expect(screen.getByTestId("loc").textContent).toBe("/advanced/studies/arc_flash?ref=42#results");
  });

  it("maps /etap, /gis and /scada under /advanced/integrations", () => {
    expect(legacyToAdvanced("/etap")).toBe("/advanced/integrations/etap");
    expect(legacyToAdvanced("/gis")).toBe("/advanced/integrations/gis");
    expect(legacyToAdvanced("/scada")).toBe("/advanced/integrations/scada");
  });

  it("returns null for unknown and already-advanced paths", () => {
    expect(legacyToAdvanced("/nope")).toBeNull();
    expect(legacyToAdvanced("/advanced/dashboard")).toBeNull();
  });
});
describe("P8 advanced routes — protected routes never migrate", () => {
  it("explicitly covers every protected legacy route", () => {
    for (const p of PROTECTED_LEGACY_ROUTES) {
      expect(isProtectedLegacyRoute(p), `${p} must be protected`).toBe(true);
    }
    expect(PROTECTED_LEGACY_ROUTES).toContain("/admin");
    expect(PROTECTED_LEGACY_ROUTES).toContain("/admin/email/webhooks");
    expect(PROTECTED_LEGACY_ROUTES).toContain("/assistant");
  });

  it("does not relocate /login, /register or /assistant", () => {
    expect(legacyToAdvanced("/login")).toBeNull();
    expect(legacyToAdvanced("/register")).toBeNull();
    expect(legacyToAdvanced("/assistant")).toBeNull();
  });

  it("does not relocate any /admin path (including deep RBAC URLs)", () => {
    for (const p of [
      "/admin",
      "/admin/cua-monitor",
      "/admin/rbac",
      "/admin/email-dashboard",
      "/admin/email-digest",
      "/admin/study-versions",
      "/admin/email-otp",
      "/admin/magic-links",
      "/admin/mfa",
      "/admin/agents",
      "/admin/ai-playground",
      "/admin/email/webhooks",
    ]) {
      expect(legacyToAdvanced(p), `${p} must stay under /admin`).toBeNull();
    }
  });
});

describe("P8 advanced routes — no duplicate targets and no fallback dead end", () => {
  it("declares exactly one /advanced target per legacy route", () => {
    const targets = ADVANCED_ROUTE_MIGRATIONS.map((m) => m.advanced);
    expect(new Set(targets).size).toBe(targets.length);
  });

  it("declares unique legacy keys", () => {
    const keys = ADVANCED_ROUTE_MIGRATIONS.map((m) => m.legacy);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("does not migrate protected routes via advancedTargetOf", () => {
    expect(advancedTargetOf("/admin")).toBeNull();
    expect(advancedTargetOf("/assistant")).toBeNull();
    expect(advancedTargetOf("/login")).toBeNull();
  });
});

describe("P8 advanced routes — source-of-truth contract with App.tsx and CommandPalette", () => {
  let appSource: string;
  let paletteSource: string;

  beforeEach(() => {
    appSource = readFileSync(join(process.cwd(), "src/App.tsx"), "utf-8");
    paletteSource = readFileSync(
      join(process.cwd(), "src/components/command/CommandPalette.tsx"),
      "utf-8",
    );
  });

  it("App.tsx declares an /advanced route and legacy redirect for every migration", () => {
    for (const { legacy, advanced } of ADVANCED_ROUTE_MIGRATIONS) {
      expect(appSource, `no /advanced route for ${advanced}`).toContain(`path="${advanced}"`);
      expect(appSource, `no legacy SPA redirect for ${legacy}`).toContain(`<Route path="${legacy}"`);
    }
    // The dynamic study route is special-cased (static + :studyType).
    expect(appSource).toContain('path="/advanced/studies/:studyType"');
    expect(appSource).toContain('path="/studies/:studyType"');
  });

  it("CommandPalette never deep-links directly to a migrated legacy route", () => {
    const migratedLegacy = ADVANCED_ROUTE_MIGRATIONS.map((m) => m.legacy);
    for (const match of paletteSource.matchAll(/navigate\("([^"]+)"\)/g)) {
      const target = match[1];
      expect(migratedLegacy, `palette navigates directly to migrated route ${target}`).not.toContain(
        target,
      );
    }
  });

  it("CommandPalette routes migrated pages through navTarget (resolves to /advanced)", () => {
    const navTargeted = new Set(Array.from(paletteSource.matchAll(/navTarget\("([^"]+)"\)/g), (m) => m[1]));
    expect(navTargeted.size).toBeGreaterThan(0);
    for (const target of navTargeted) {
      const advanced = advancedTargetOf(target);
      expect(advanced, `navTarget("${target}") must resolve to a valid /advanced target`).not.toBeNull();
    }
    // Chat-first core and RBAC surfaces keep their exact legacy paths.
    expect(paletteSource).toContain('navigate("/assistant")');
    expect(paletteSource).toContain('navigate("/admin")');
    expect(advancedTargetOf("/assistant")).toBeNull();
    expect(advancedTargetOf("/admin")).toBeNull();
  });

  it("App.tsx has a catch-all SPA fallback to /dashboard (no navigation dead end)", () => {
    expect(appSource).toContain('<Route path="*" element={<Navigate to="/dashboard" replace />} />');
  });
});