import { Suspense, lazy, useEffect, useRef, useState } from "react";
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
import { GSAPRouteTransition } from "./components/GSAPPageTransition";
import { NotificationProvider } from "./context/NotificationContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./hooks/useAuth";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useAppStore } from "./store";
import "./i18n";
import { gsap } from "gsap";

// Lazy-loaded page components with GSAP loading animation
const LoadingFallback = () => {
  const loadingRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!loadingRef.current) return;
    
    const ctx = gsap.context(() => {
      // Spinner animation
      gsap.to(".loading-spinner", {
        rotation: 360,
        duration: 1.5,
        repeat: -1,
        ease: "power2.inOut"
      });
      
      // Loading text animation
      gsap.to(".loading-text", {
        opacity: 0.7,
        duration: 1,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut"
      });
      
      // Power surge effect
      gsap.to(".loading-container", {
        boxShadow: "0 0 15px rgba(0, 212, 255, 0.3)",
        duration: 1.5,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut"
      });
    });
    
    return () => ctx.revert();
  }, []);
  
  return (
    <div ref={loadingRef} className="loading-container flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="loading-spinner w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full" />
        <span className="loading-text text-sm text-[var(--text-muted)]">Loading...</span>
      </div>
    </div>
  );
};

const DashboardPage = lazy(() => import("./pages/Dashboard"));
const StudiesPage = lazy(() => import("./pages/Studies"));
const GridEditorPage = lazy(() => import("./pages/GridEditor"));
const StudyRunPage = lazy(() => import("./pages/StudyRun"));
const AssetManagementPage = lazy(() => import("./pages/AssetManagement"));
const AIAssistantPage = lazy(() => import("./pages/AIAssistant"));
const ProjectsPage = lazy(() => import("./pages/Projects"));
const EtapIntegrationPage = lazy(() => import("./pages/EtapIntegration"));
const GisIntegrationPage = lazy(() => import("./pages/GisIntegration"));
const ScadaIntegrationPage = lazy(() => import("./pages/ScadaIntegration"));
const ReportsPage = lazy(() => import("./pages/Reports"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const AdministrationPage = lazy(() => import("./pages/Administration"));
const DiagnosticsPage = lazy(() => import("./pages/Diagnostics"));
const DigitalTwinPage = lazy(() => import("./pages/DigitalTwin"));
const DataImportPage = lazy(() => import("./pages/DataImport"));
const DataExportPage = lazy(() => import("./pages/DataExport"));
const LogsPage = lazy(() => import("./pages/Logs"));
const CodeGuardPage = lazy(() => import("./pages/CodeGuard"));
const LoginPage = lazy(() => import("./pages/Login"));
const RegisterPage = lazy(() => import("./pages/Register"));

// Inner component that activates keyboard shortcuts inside the Router context
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

  // Electron menu navigation
  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onNavigate((path: string) => {
        window.location.hash = path;
      });
    }
  }, []);

  // F1 / Ctrl+H for Smart Help
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

  // Listen for toggle-shortcuts-panel events (from the Navbar shortcuts button)
  useEffect(() => {
    const handler = () => setShortcutsOpen((prev) => !prev);
    globalThis.addEventListener("toggle-shortcuts-panel", handler);
    return () => globalThis.removeEventListener("toggle-shortcuts-panel", handler);
  }, []);

  // Listen for toggle-theme events
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

  // Listen for toggle-language events
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

  // Listen for help context events from other components
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

  // Listen for toggle-smart-help events (from the Help button in the navbar)
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
               {/* Auth routes - no Layout */}
              <Route
                path="/login"
                element={
                  <Suspense fallback={<LoadingFallback />}>
                    <GSAPRouteTransition>
                      <LoginPage />
                    </GSAPRouteTransition>
                  </Suspense>
                }
              />
              <Route
                path="/register"
                element={
                  <Suspense fallback={<LoadingFallback />}>
                    <GSAPRouteTransition>
                      <RegisterPage />
                    </GSAPRouteTransition>
                  </Suspense>
                }
              />

              {/* App routes - protected (require login) - with Layout */}
              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route
                  path="/dashboard"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <DashboardPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/studies"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <StudiesPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/grid-editor"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <GridEditorPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/studies/:studyType"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <StudyRunPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/asset-management"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <AssetManagementPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/assistant"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <AIAssistantPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/projects"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <ProjectsPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/etap"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <EtapIntegrationPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/gis"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <GisIntegrationPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/scada"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <ScadaIntegrationPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/reports"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <ReportsPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/settings"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <SettingsPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <AdministrationPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/diagnostics"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <DiagnosticsPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/digital-twin"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <DigitalTwinPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/data-import"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <DataImportPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/data-export"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <DataExportPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/logs"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <LogsPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                <Route
                  path="/code-guard"
                  element={
                    <Suspense fallback={<LoadingFallback />}>
                      <GSAPRouteTransition>
                        <CodeGuardPage />
                      </GSAPRouteTransition>
                    </Suspense>
                  }
                />
                {/* Fallback */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Routes>

            {/* Global Overlays inside Router context */}
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
