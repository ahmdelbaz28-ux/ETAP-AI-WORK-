import { Suspense, lazy, useEffect, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
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
import { useAppStore } from "./store";
import "./i18n";

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
const LoginPage = lazyLoad(() => import("./pages/Login"));
const RegisterPage = lazyLoad(() => import("./pages/Register"));
const AuditLogsPage = lazyLoad(() => import("./pages/AuditLogs"));
const IntegrationsPage = lazyLoad(() => import("./pages/Integrations"));
const FeatureFlagsPage = lazyLoad(() => import("./pages/FeatureFlags"));

function KeyboardShortcutsHandler() {
  useKeyboardShortcuts();
  return null;
}

export default function App() {
  const { i18n } = useTranslation();
  const { lastError, setLastError } = useAppStore();
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpContext, setHelpContext] = useState<string | undefined>();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

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
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/studies" element={<StudiesPage />} />
                <Route path="/grid-editor" element={<GridEditorPage />} />
                <Route path="/studies/:studyType" element={<StudyRunPage />} />
                <Route path="/asset-management" element={<AssetManagementPage />} />
                <Route path="/assistant" element={<AIAssistantPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/etap" element={<EtapIntegrationPage />} />
                <Route path="/gis" element={<GisIntegrationPage />} />
                <Route path="/scada" element={<ScadaIntegrationPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/admin" element={<AdministrationPage />} />
                <Route path="/diagnostics" element={<DiagnosticsPage />} />
                <Route path="/digital-twin" element={<DigitalTwinPage />} />
                <Route path="/data-import" element={<DataImportPage />} />
                <Route path="/data-export" element={<DataExportPage />} />
                <Route path="/logs" element={<LogsPage />} />
                <Route path="/code-guard" element={<CodeGuardPage />} />
                <Route path="/context-engine" element={<ContextEnginePage />} />
                <Route path="/templates" element={<TemplatesPage />} />
                <Route path="/asset-library" element={<AssetLibraryPage />} />
                <Route path="/admin/cua-monitor" element={<CuaMonitorPage />} />
                <Route path="/admin/audit-logs" element={<AuditLogsPage />} />
                <Route path="/admin/feature-flags" element={<FeatureFlagsPage />} />
                <Route path="/integrations" element={<IntegrationsPage />} />
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
