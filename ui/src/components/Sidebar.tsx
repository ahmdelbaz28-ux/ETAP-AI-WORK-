// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import {
  Activity,
  Bot,
  Bug,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Download,
  FileText,
  FlaskConical,
  FolderKanban,
  Grid,
  Layers,
  LayoutDashboard,
  Map,
  Moon,
  Network,
  Plug,
  ScrollText,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sun,
  Upload,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { type HealthResponse, fetchHealth } from "../lib/api";
import { useAppStore } from "../store";
import { cn } from "../utils/helpers";
import { BrandLogo } from "./BrandLogo";

interface NavItem {
  to: string;
  icon: React.ElementType;
  labelKey: string;
  section?: string;
  badge?: string | number;
}

const navItems: NavItem[] = [
  { to: "/dashboard", icon: LayoutDashboard, labelKey: "sidebar.dashboard" },
  { to: "/studies", icon: FlaskConical, labelKey: "sidebar.studies" },
  { to: "/assistant", icon: Bot, labelKey: "sidebar.assistant" },
  { to: "/projects", icon: FolderKanban, labelKey: "sidebar.projects", section: "engineering" },
  { to: "/grid-editor", icon: Grid, labelKey: "sidebar.gridEditor", section: "engineering" },
  {
    to: "/asset-management",
    icon: Network,
    labelKey: "sidebar.assetManagement",
    section: "engineering",
  },
  { to: "/etap", icon: Plug, labelKey: "sidebar.etapIntegration", section: "integration" },
  { to: "/gis", icon: Map, labelKey: "sidebar.gisIntegration", section: "integration" },
  { to: "/scada", icon: Activity, labelKey: "sidebar.scadaIntegration", section: "integration" },
  { to: "/digital-twin", icon: Layers, labelKey: "sidebar.digitalTwin", section: "integration" },
  { to: "/reports", icon: FileText, labelKey: "sidebar.reports" },
  { to: "/data-import", icon: Upload, labelKey: "sidebar.dataImport", section: "system" },
  { to: "/data-export", icon: Download, labelKey: "sidebar.dataExport", section: "system" },
  { to: "/settings", icon: Settings, labelKey: "sidebar.settings", section: "system" },
  { to: "/admin", icon: ShieldCheck, labelKey: "sidebar.administration", section: "system" },
  { to: "/admin/cua-monitor", icon: ShieldAlert, labelKey: "sidebar.cuaMonitor", section: "system" },
  { to: "/diagnostics", icon: Bug, labelKey: "sidebar.diagnostics", section: "system" },
  { to: "/code-guard", icon: Shield, labelKey: "sidebar.codeGuard", section: "system" },
  { to: "/logs", icon: ScrollText, labelKey: "sidebar.logs", section: "system" },
];

const sectionOrder = ["engineering", "integration", "system"] as const;
const sectionLabels: Record<string, string> = {
  engineering: "sidebar.engineering",
  integration: "sidebar.integration",
  system: "sidebar.system",
};

const sectionIcons: Record<string, React.ElementType> = {
  engineering: Cpu,
  integration: Plug,
  system: Wrench,
};

export function Sidebar() {
  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  const { t, i18n } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const { sidebarCollapsed, toggleSidebar, mobileSidebarOpen, setMobileSidebarOpen } =
    useAppStore();
  const [healthStatus, setHealthStatus] = useState<"online" | "offline" | "checking">("checking");

  const isRtl = i18n.language === "ar";

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [location.pathname, setMobileSidebarOpen]);

  // Close mobile drawer on Escape
  useEffect(() => {
    if (!mobileSidebarOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileSidebarOpen(false);
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [mobileSidebarOpen, setMobileSidebarOpen]);

  useEffect(() => {
    fetchHealth()
      .then((h: HealthResponse) => setHealthStatus(h.ok ? "online" : "offline"))
      .catch(() => setHealthStatus("offline"));
    const interval = setInterval(() => {
      fetchHealth()
        .then((h: HealthResponse) => setHealthStatus(h.ok ? "online" : "offline"))
        .catch(() => setHealthStatus("offline"));
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const groupedItems: Record<string, NavItem[]> = {};
  const topLevel: NavItem[] = [];
  navItems.forEach((item) => {
    if (item.section) {
      if (!groupedItems[item.section]) groupedItems[item.section] = [];
      groupedItems[item.section].push(item);
    } else {
      topLevel.push(item);
    }
  });

  return (
    <>
      {/* ─── Desktop Sidebar (lg and up) ─────────────────────────────── */}
      <aside
        aria-label="Sidebar Navigation"
        className={cn(
          "hidden lg:flex h-full flex-col bg-[var(--bg-secondary)] border-r border-[var(--border-primary)] shrink-0 transition-all duration-300 overflow-hidden z-[var(--z-sidebar)]",
          sidebarCollapsed ? "w-[68px]" : "w-64",
        )}
      >
        {/* Logo Section */}
        <div className="p-4 border-b border-[var(--border-primary)]">
          <div className={cn("flex items-center gap-2.5", sidebarCollapsed && "justify-center")}>
            <div className="shrink-0 relative">
              <BrandLogo size={36} />
              {healthStatus === "online" && (
                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-[var(--bg-secondary)]" />
              )}
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <h1 className="text-sm font-bold text-[var(--text-primary)] truncate tracking-tight">
                  {t("app.name")}
                </h1>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {(() => {
                    let dotColor;
                    if (healthStatus === "online") dotColor = "bg-green-400 animate-pulse";
                    else if (healthStatus === "checking") dotColor = "bg-amber-400";
                    else dotColor = "bg-red-400";
                    return (
                      <span className={cn("w-1.5 h-1.5 rounded-full", dotColor)} />
                    );
                  })()}
                  <span className="text-[10px] text-[var(--text-muted)] capitalize">
                    {t(`dashboard.${healthStatus}`)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
          {topLevel.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group relative",
                  sidebarCollapsed && "justify-center px-0",
                  !sidebarCollapsed && "nav-indicator",
                  isActive && !sidebarCollapsed && "active",
                  isActive
                    ? "bg-brand-600/80 text-white font-medium shadow-sm shadow-brand-600/30 ring-1 ring-brand-500/30"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                )
              }
            >
              <item.icon className="w-[18px] h-[18px] shrink-0" />
              {!sidebarCollapsed && <span className="truncate">{t(item.labelKey)}</span>}
              {sidebarCollapsed && (
                <div className="absolute left-full ml-2 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-md text-xs text-[var(--text-primary)] shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                  {t(item.labelKey)}
                </div>
              )}
            </NavLink>
          ))}

          {/* Grouped sections */}
          {sectionOrder.map((section) => {
            const items = groupedItems[section];
            if (!items?.length) return null;
            const SectionIcon = sectionIcons[section];
            return (
              <div key={section} className="pt-4">
                {!sidebarCollapsed && (
                  <div className="flex items-center gap-1.5 px-3 mb-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    {SectionIcon && <SectionIcon className="w-3 h-3" />}
                    {t(sectionLabels[section])}
                  </div>
                )}
                {sidebarCollapsed && <hr className="border-[var(--border-primary)] mx-2" />}
                {items.map((item) => {
                  const isActive = location.pathname === item.to;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={() =>
                        cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5 group relative",
                          sidebarCollapsed && "justify-center px-0",
                          isActive
                            ? "bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                        )
                      }
                    >
                      <item.icon className="w-[18px] h-[18px] shrink-0" />
                      {!sidebarCollapsed && <span className="truncate">{t(item.labelKey)}</span>}
                      {sidebarCollapsed && (
                        <div className="absolute left-full ml-2 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-md text-xs text-[var(--text-primary)] shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
                          {t(item.labelKey)}
                        </div>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="p-2 border-t border-[var(--border-primary)] space-y-1">
          <button
            onClick={toggleTheme}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors",
              sidebarCollapsed && "justify-center px-0",
            )}
            aria-label={theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}
          >
            {theme === "dark" ? (
              <Sun className="w-[18px] h-[18px] shrink-0" />
            ) : (
              <Moon className="w-[18px] h-[18px] shrink-0" />
            )}
            {!sidebarCollapsed && (
              <span>{theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}</span>
            )}
          </button>

          <button
            onClick={toggleSidebar}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)] transition-colors",
              sidebarCollapsed && "justify-center px-0",
            )}
            title={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
            aria-label={sidebarCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          >
            {sidebarCollapsed ? (
              <ChevronRight className={`w-[18px] h-[18px] shrink-0 ${isRtl ? "rotate-180" : ""}`} />
            ) : (
              <>
                {isRtl ? (
                  <ChevronRight className="w-[18px] h-[18px] shrink-0" />
                ) : (
                  <ChevronLeft className="w-[18px] h-[18px] shrink-0" />
                )}
                <span>{t("sidebar.collapse")}</span>
              </>
            )}
          </button>

          {!sidebarCollapsed && (
            <div className="text-[10px] text-[var(--text-muted)] text-center pt-1">
              v{t("app.version")} &middot; {new Date().getFullYear()}
            </div>
          )}
        </div>
      </aside>

      {/* ─── Mobile Sidebar (drawer overlay, lg and below) ───────────── */}
      {/* Backdrop */}
      {mobileSidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-[90]"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Drawer */}
      <aside
        aria-label="Mobile Sidebar Navigation"
        aria-hidden={!mobileSidebarOpen}
        className={cn(
          "lg:hidden fixed top-0 left-0 h-full w-72 max-w-[85vw]",
          "bg-[var(--bg-secondary)] border-r border-[var(--border-primary)]",
          "flex flex-col overflow-hidden shadow-2xl",
          "transition-transform duration-300 ease-out z-[100]",
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Header with logo + close button */}
        <div className="p-4 border-b border-[var(--border-primary)] flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="shrink-0 relative">
              <BrandLogo size={36} />
              {healthStatus === "online" && (
                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-[var(--bg-secondary)]" />
              )}
            </div>
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-[var(--text-primary)] truncate tracking-tight">
                {t("app.name")}
              </h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span
                  className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    // SonarCloud typescript:S3358: extract nested ternary.
                    (() => {
                      if (healthStatus === "online") return "bg-green-400 animate-pulse";
                      if (healthStatus === "checking") return "bg-amber-400";
                      return "bg-red-400";
                    })(),
                  )}
                />
                <span className="text-[10px] text-[var(--text-muted)] capitalize">
                  {t(`dashboard.${healthStatus}`)}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={() => setMobileSidebarOpen(false)}
            aria-label="Close menu"
            className="p-2 -mr-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
          {topLevel.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                  isActive
                    ? "bg-brand-600/80 text-white font-medium shadow-sm shadow-brand-600/30 ring-1 ring-brand-500/30"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                )
              }
            >
              <item.icon className="w-[18px] h-[18px] shrink-0" />
              <span className="truncate">{t(item.labelKey)}</span>
            </NavLink>
          ))}

          {sectionOrder.map((section) => {
            const items = groupedItems[section];
            if (!items?.length) return null;
            const SectionIcon = sectionIcons[section];
            return (
              <div key={section} className="pt-4">
                <div className="flex items-center gap-1.5 px-3 mb-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  {SectionIcon && <SectionIcon className="w-3 h-3" />}
                  {t(sectionLabels[section])}
                </div>
                {items.map((item) => {
                  const isActive = location.pathname === item.to;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={() =>
                        cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5",
                          isActive
                            ? "bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                        )
                      }
                    >
                      <item.icon className="w-[18px] h-[18px] shrink-0" />
                      <span className="truncate">{t(item.labelKey)}</span>
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="p-2 border-t border-[var(--border-primary)] space-y-1">
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
            aria-label={theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}
          >
            {theme === "dark" ? (
              <Sun className="w-[18px] h-[18px] shrink-0" />
            ) : (
              <Moon className="w-[18px] h-[18px] shrink-0" />
            )}
            <span>{theme === "dark" ? t("sidebar.lightMode") : t("sidebar.darkMode")}</span>
          </button>

          <div className="text-[10px] text-[var(--text-muted)] text-center pt-1">
            v{t("app.version")} &middot; {new Date().getFullYear()}
          </div>
        </div>
      </aside>
    </>
  );
}
