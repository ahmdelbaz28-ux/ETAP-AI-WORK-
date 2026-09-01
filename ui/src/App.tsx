import { type ComponentType, Suspense, lazy, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { CommandPalette } from "./components/command/CommandPalette";
import { ShortcutsPanel } from "./components/command/ShortcutsPanel";
import { ErrorRecovery } from "./components/context/ErrorRecovery";
import { MagicHelpInspector } from "./components/help/MagicHelpInspector";
import { SmartHelpDrawer } from "./components/help/SmartHelpDrawer";
import { OnboardingTour } from "./components/onboarding/OnboardingTour";
import { NotificationProvider } from "./context/NotificationContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./hooks/useAuth";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { AdvancedRedirect } from "./lib/advanced-routes";
import { useChatFirstUi } from "./lib/chat-first-ui";
import { useAppStore } from "./store";
import "./i18n";

const ChatWorkspace = lazyLoad(() => import("./app/ChatWorkspace"));

const LoadingFallback = () => (
  <div className="flex items-center justify-center h-64">
    <div className="flex flex-col items-center gap-3">
      <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-[var(--text-muted)]">Loading...</span>
    </div>
  </div>
);

function lazyLoad(importFn: () => Promise<{ default: ComponentType<Record<string, unknown>> }>) {
  const Component = lazy(importFn);
  return function LazyLoaded(props: Record<string, unknown>) {
    return (
      <Suspense fallback={<LoadingFallback />}>
        <Component {...props} />
      </Suspense>
    );
  };
}

const DashboardPage = lazyLoad(() => import("./pages/Dashboard"));
const StudiesPage = lazyLoad(() => import("./pages/Studies"));
const GridEditorPage = lazyLoad(() => import("./pages/GridEditor"));
const StudyRunPage = lazyLoad(() => import("./pages/StudyRun"));
const AssetManagementPage = lazyLoad(() => import("./pages/AssetManagement"));
const AIAssistantPage = lazyLoad(() => import("./pages/AIAssistant"));
const ProjectsPage = lazyLoad(() => import("./pages/Projects"));
const VisionKeysPage = lazyLoad(() => import("./pages/VisionKeys"));
const GuardReviewPage = lazyLoad(() => import("./pages/GuardReview"));
const AgentMetricsPage = lazyLoad(() => import("./pages/AgentMetrics"));
const AuditLogsPage = lazyLoad(() => import("./pages/AuditLogs"));
const EtapIntegrationPage = lazyLoad(() => import("./pages/EtapIntegration"));
const GisIntegrationPage = lazyLoad(() => import("./pages/GisIntegration"));
const ScadaIntegrationPage = lazyLoad(() => import("./pages/ScadaIntegration"));
const ReportsPage = lazyLoad(() => import("./pages/Reports"));
const SettingsPage = lazyLoad(() => import("./pages/Settings"));
const AdministrationPage = lazyLoad(() => import("./pages/Administration"));
const DiagnosticsPage = lazyLoad(() => import("./pages/Diagnostics"));
const DigitalTwinPage = lazyLoad(() => import("./pages/DigitalTwin"));
const DataImportPage = lazyLoad(() => import("./pages/DataImport"));
const DataExportPage = lazyLoad(() => import("./pages/DataExport"));
const LogsPage = lazyLoad(() => import("./pages/Logs"));
const CuaMonitorPage = lazyLoad(() => import("./pages/CuaMonitor"));
const CodeGuardPage = lazyLoad(() => import("./pages/CodeGuard"));
const ContextEnginePage = lazyLoad(() => import("./pages/ContextEngine"));
const TemplatesPage = lazyLoad(() => import("./pages/Templates"));
const AssetLibraryPage = lazyLoad(() => import("./pages/AssetLibrary"));
const RbacAdminPage = lazyLoad(() => import("./pages/RbacAdmin"));
const EquipmentManagementPage = lazyLoad(() => import("./pages/EquipmentManagement"));
const EmailDashboardPage = lazyLoad(() => import("./pages/EmailDashboard"));
const EmailWebhooksPage = lazyLoad(() => import("./pages/EmailWebhooks"));
const EmailDigestPage = lazyLoad(() => import("./pages/EmailDigest"));
const StudyVersionsPage = lazyLoad(() => import("./pages/StudyVersions"));
const EmailOtpPage = lazyLoad(() => import("./pages/EmailOtp"));
const AIPlaygroundPage = lazyLoad(() => import("./pages/AIPlayground"));
const MagicLinksPage = lazyLoad(() => import("./pages/MagicLinks"));
const MfaPage = lazyLoad(() => import("./pages/Mfa"));
const AgentsControlPanelPage = lazyLoad(() => import("./pages/AgentsControlPanel"));
const LoginPage = lazyLoad(() => import("./pages/Login"));
const RegisterPage = lazyLoad(() => import("./pages/Register"));

function KeyboardShortcutsHandler() {
  useKeyboardShortcuts();
  return null;
}

export default function App() {
  const { i18n } = useTranslation();
  const { lastError, setLastError } = useAppStore();
  const chatFirstUi = useChatFirstUi();
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpContext, setHelpContext] = useState<string | undefined>();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  // P6 feature flag gate: when `chat_first_ui` is enabled, render ChatWorkspace
  // as the primary UI. Legacy tree (and all existing routes) is preserved
  // below so that toggling the flag off restores the previous experience.
  if (chatFirstUi.enabled) {
    return (
      <ThemeProvider>
        <NotificationProvider>
          <AuthProvider>
            <ChatWorkspace onExitToLegacy={chatFirstUi.exitToLegacy} />
          </AuthProvider>
        </NotificationProvider>
      </ThemeProvider>
    );
  }

  useEffect(() => {
    document.documentElement.dir = i18n.language === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onNavigate((path: string) => {
        window.location.hash = path;
      });
    }
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "F1") {
        e.preventDefault();
        setHelpOpen((prev) => !prev);
        setHelpContext(undefined);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "h") {
        e.preventDefault();
        setHelpOpen((prev) => !prev);
        setHelpContext(undefined);
      }
    };
    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const handler = () => setShortcutsOpen((prev) => !prev);
    globalThis.addEventListener("toggle-shortcuts-panel", handler);
    return () => globalThis.removeEventListener("toggle-shortcuts-panel", handler);
  }, []);

  useEffect(() => {
    const handler = () => {
      const current = document.documentElement.classList.contains("dark") ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.classList.remove(current);
      document.documentElement.classList.add(next);
      localStorage.setItem("etap-theme", next);
    };
    globalThis.addEventListener("toggle-theme", handler);
    return () => globalThis.removeEventListener("toggle-theme", handler);
  }, []);

  useEffect(() => {
    const handler = () => {
      const newLang = i18n.language === "ar" ? "en" : "ar";
      i18n.changeLanguage(newLang);
      document.documentElement.dir = newLang === "ar" ? "rtl" : "ltr";
      document.documentElement.lang = newLang;
    };
    globalThis.addEventListener("toggle-language", handler);
    return () => globalThis.removeEventListener("toggle-language", handler);
  }, [i18n]);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail?.contextId) {
        setHelpContext(customEvent.detail.contextId);
        setHelpOpen(true);
      }
    };
    globalThis.addEventListener("open-smart-help", handler);
    return () => globalThis.removeEventListener("open-smart-help", handler);
  }, []);

  useEffect(() => {
    const handler = () => {
      setHelpOpen((prev) => !prev);
      setHelpContext(undefined);
    };
    globalThis.addEventListener("toggle-smart-help", handler);
    return () => globalThis.removeEventListener("toggle-smart-help", handler);
  }, []);

  return (
    <ThemeProvider>
      <NotificationProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                {/* P8 core: chat-first assistant stays put */}
                <Route path="/assistant" element={<AIAssistantPage />} />
                {/* P8 admin: RBAC surface stays put */}
                <Route path="/admin" element={<AdministrationPage />} />
                <Route path="/admin/cua-monitor" element={<CuaMonitorPage />} />
                <Route path="/admin/rbac" element={<RbacAdminPage />} />
                <Route path="/admin/email-dashboard" element={<EmailDashboardPage />} />
                <Route path="/admin/email-digest" element={<EmailDigestPage />} />
                <Route path="/admin/study-versions" element={<StudyVersionsPage />} />
                <Route path="/admin/email-otp" element={<EmailOtpPage />} />
                <Route path="/admin/magic-links" element={<MagicLinksPage />} />
                <Route path="/admin/mfa" element={<MfaPage />} />
                <Route path="/admin/agents" element={<AgentsControlPanelPage />} />
                <Route path="/admin/ai-playground" element={<AIPlaygroundPage />} />
                <Route path="/admin/email/webhooks" element={<EmailWebhooksPage />} />
                {/* P8 advanced: non-core pages under /advanced */}
                <Route path="/advanced/dashboard" element={<DashboardPage />} />
                <Route path="/advanced/studies" element={<StudiesPage />} />
                <Route path="/advanced/studies/:studyType" element={<StudyRunPage />} />
                <Route path="/advanced/grid-editor" element={<GridEditorPage />} />
                <Route path="/advanced/projects" element={<ProjectsPage />} />
                <Route path="/advanced/vision-keys" element={<VisionKeysPage />} />
                <Route path="/advanced/guard-review" element={<GuardReviewPage />} />
                <Route path="/advanced/agent-metrics" element={<AgentMetricsPage />} />
                <Route path="/advanced/audit-logs" element={<AuditLogsPage />} />
                <Route path="/advanced/asset-management" element={<AssetManagementPage />} />
                <Route path="/advanced/equipment" element={<EquipmentManagementPage />} />
                <Route path="/advanced/integrations/etap" element={<EtapIntegrationPage />} />
                <Route path="/advanced/integrations/gis" element={<GisIntegrationPage />} />
                <Route path="/advanced/integrations/scada" element={<ScadaIntegrationPage />} />
                <Route path="/advanced/digital-twin" element={<DigitalTwinPage />} />
                <Route path="/advanced/reports" element={<ReportsPage />} />
                <Route path="/advanced/settings" element={<SettingsPage />} />
                <Route path="/advanced/diagnostics" element={<DiagnosticsPage />} />
                <Route path="/advanced/data-import" element={<DataImportPage />} />
                <Route path="/advanced/data-export" element={<DataExportPage />} />
                <Route path="/advanced/logs" element={<LogsPage />} />
                <Route path="/advanced/code-guard" element={<CodeGuardPage />} />
                <Route path="/advanced/context-engine" element={<ContextEnginePage />} />
                <Route path="/advanced/templates" element={<TemplatesPage />} />
                <Route path="/advanced/asset-library" element={<AssetLibraryPage />} />
                {/* P8 legacy: SPA redirects → /advanced (params/search/hash preserved) */}
                <Route path="/dashboard" element={<AdvancedRedirect legacy="/dashboard" />} />
                <Route path="/studies" element={<AdvancedRedirect legacy="/studies" />} />
                <Route path="/studies/:studyType" element={<AdvancedRedirect legacy="/studies" />} />
                <Route path="/grid-editor" element={<AdvancedRedirect legacy="/grid-editor" />} />
                <Route path="/projects" element={<AdvancedRedirect legacy="/projects" />} />
                <Route path="/vision-keys" element={<AdvancedRedirect legacy="/vision-keys" />} />
                <Route path="/guard-review" element={<AdvancedRedirect legacy="/guard-review" />} />
                <Route path="/agent-metrics" element={<AdvancedRedirect legacy="/agent-metrics" />} />
                <Route path="/audit-logs" element={<AdvancedRedirect legacy="/audit-logs" />} />
                <Route path="/asset-management" element={<AdvancedRedirect legacy="/asset-management" />} />
                <Route path="/equipment" element={<AdvancedRedirect legacy="/equipment" />} />
                <Route path="/etap" element={<AdvancedRedirect legacy="/etap" />} />
                <Route path="/gis" element={<AdvancedRedirect legacy="/gis" />} />
                <Route path="/scada" element={<AdvancedRedirect legacy="/scada" />} />
                <Route path="/digital-twin" element={<AdvancedRedirect legacy="/digital-twin" />} />
                <Route path="/reports" element={<AdvancedRedirect legacy="/reports" />} />
                <Route path="/settings" element={<AdvancedRedirect legacy="/settings" />} />
                <Route path="/diagnostics" element={<AdvancedRedirect legacy="/diagnostics" />} />
                <Route path="/data-import" element={<AdvancedRedirect legacy="/data-import" />} />
                <Route path="/data-export" element={<AdvancedRedirect legacy="/data-export" />} />
                <Route path="/logs" element={<AdvancedRedirect legacy="/logs" />} />
                <Route path="/code-guard" element={<AdvancedRedirect legacy="/code-guard" />} />
                <Route path="/context-engine" element={<AdvancedRedirect legacy="/context-engine" />} />
                <Route path="/templates" element={<AdvancedRedirect legacy="/templates" />} />
                <Route path="/asset-library" element={<AdvancedRedirect legacy="/asset-library" />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Routes>

            <KeyboardShortcutsHandler />
            <CommandPalette />
            <OnboardingTour />
            <SmartHelpDrawer
              open={helpOpen}
              onClose={() => {
                setHelpOpen(false);
                setHelpContext(undefined);
              }}
              initialContextId={helpContext}
            />
            <ShortcutsPanel open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
            <MagicHelpInspector />
          </BrowserRouter>

          <ErrorRecovery
            error={lastError}
            onDismiss={() => setLastError(null)}
            onRetry={() => globalThis.location.reload()}
          />
        </AuthProvider>
      </NotificationProvider>
    </ThemeProvider>
  );
}
