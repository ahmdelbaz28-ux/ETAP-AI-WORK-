/**
 * P8 — Advanced Routes Migration (frontend).
 *
 * All non-core legacy pages were relocated under /advanced/*. This module is
 * the single source of truth for that migration:
 *
 *  - `ADVANCED_ROUTE_MIGRATIONS` maps every migrated legacy route base to its
 *    /advanced target (e.g. `/etap` -> `/advanced/integrations/etap`);
 *  - `legacyToAdvanced()` resolves an incoming legacy pathname to the advanced
 *    equivalent while preserving any dynamic suffix (so `/studies/:studyType`
 *    keeps `:studyType`) — search string and hash are appended by the caller;
 *  - `AdvancedRedirect` is the SPA redirect element used by App.tsx so old
 *    bookmarks / links / internal navigation keep working without backend
 *    redirects and without touching page components.
 *
 * Routes that are intentionally NOT migrated are never listed here:
 *   `/login`, `/register`, `/assistant` (chat-first core) and `/admin/*`
 *   (RBAC surface) — see `PROTECTED_LEGACY_ROUTES`.
 */
import { Navigate, useLocation } from "react-router";

export interface AdvancedRouteMigration {
  /** Legacy route base segment (e.g. `/studies`). */
  readonly legacy: string;
  /** Advanced target base segment (e.g. `/advanced/studies`). */
  readonly advanced: string;
}

export const ADVANCED_ROUTE_MIGRATIONS: ReadonlyArray<AdvancedRouteMigration> = [
  { legacy: "/dashboard", advanced: "/advanced/dashboard" },
  { legacy: "/studies", advanced: "/advanced/studies" },
  { legacy: "/grid-editor", advanced: "/advanced/grid-editor" },
  { legacy: "/projects", advanced: "/advanced/projects" },
  { legacy: "/asset-management", advanced: "/advanced/asset-management" },
  { legacy: "/vision-keys", advanced: "/advanced/vision-keys" },
  { legacy: "/guard-review", advanced: "/advanced/guard-review" },
  { legacy: "/agent-metrics", advanced: "/advanced/agent-metrics" },
  { legacy: "/audit-logs", advanced: "/advanced/audit-logs" },
  { legacy: "/equipment", advanced: "/advanced/equipment" },
  { legacy: "/etap", advanced: "/advanced/integrations/etap" },
  { legacy: "/gis", advanced: "/advanced/integrations/gis" },
  { legacy: "/scada", advanced: "/advanced/integrations/scada" },
  { legacy: "/digital-twin", advanced: "/advanced/digital-twin" },
  { legacy: "/reports", advanced: "/advanced/reports" },
  { legacy: "/settings", advanced: "/advanced/settings" },
  { legacy: "/diagnostics", advanced: "/advanced/diagnostics" },
  { legacy: "/data-import", advanced: "/advanced/data-import" },
  { legacy: "/data-export", advanced: "/advanced/data-export" },
  { legacy: "/logs", advanced: "/advanced/logs" },
  { legacy: "/code-guard", advanced: "/advanced/code-guard" },
  { legacy: "/context-engine", advanced: "/advanced/context-engine" },
  { legacy: "/templates", advanced: "/advanced/templates" },
  { legacy: "/asset-library", advanced: "/advanced/asset-library" },
] as const;

/**
 * Routes that must remain at their current paths (auth surfaces, the
 * chat-first core assistant page and the whole /admin RBAC area).
 */
export const PROTECTED_LEGACY_ROUTES: ReadonlyArray<string> = [
  "/login",
  "/register",
  "/assistant",
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
] as const;

/** True for authenticated surfaces that P8 must never relocate. */
export function isProtectedLegacyRoute(path: string): boolean {
  return path === "/login" || path === "/register" || path === "/assistant" || path.startsWith("/admin");
}

/** Exact lookup: advanced base for a legacy route base, or null if not migrated. */
export function advancedTargetOf(legacy: string): string | null {
  return ADVANCED_ROUTE_MIGRATIONS.find((m) => m.legacy === legacy)?.advanced ?? null;
}

/**
 * Resolve an incoming legacy pathname to its /advanced counterpart.
 *
 * The dynamic suffix is preserved so parameterised routes such as
 * `/studies/:studyType` keep working after migration. Returns null when the
 * path is not a migrated legacy route (e.g. `/advanced/...`, `/admin/...`).
 */
export function legacyToAdvanced(pathname: string): string | null {
  for (const { legacy, advanced } of ADVANCED_ROUTE_MIGRATIONS) {
    if (pathname === legacy) return advanced;
    if (pathname.startsWith(`${legacy}/`)) return `${advanced}${pathname.slice(legacy.length)}`;
  }
  return null;
}

/**
 * SPA redirect from a legacy route (including dynamic paths under it) to its
 * /advanced counterpart, preserving path suffix, search string and hash.
 * Used as the `element` of every legacy <Route> in App.tsx. Never applies to
 * protected routes — those keep their own elements.
 */
export function AdvancedRedirect({ legacy }: Readonly<{ legacy: string }>) {
  const location = useLocation();
  const resolved = legacyToAdvanced(location.pathname) ?? advancedTargetOf(legacy);
  if (!resolved) return null;
  return <Navigate to={`${resolved}${location.search}${location.hash}`} replace />;
}