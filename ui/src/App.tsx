import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ThemeProvider } from './context/ThemeContext'
import { NotificationProvider } from './context/NotificationContext'
import { AuthProvider } from './hooks/useAuth'
import { Layout } from './components/Layout'
import { SmartHelpDrawer } from './components/help/SmartHelpDrawer'
import { CommandPalette } from './components/command/CommandPalette'
import { ShortcutsPanel } from './components/command/ShortcutsPanel'
import { OnboardingTour } from './components/onboarding/OnboardingTour'
import { ErrorRecovery } from './components/context/ErrorRecovery'
import { DemoModeBanner } from './components/DemoModeBanner'
import { useAppStore } from './store'
import { MagicHelpInspector } from './components/help/MagicHelpInspector'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import './i18n'

// Lazy-loaded page components — loaded on demand
const LoadingFallback = () => (
  <div className="flex items-center justify-center h-64">
    <div className="flex flex-col items-center gap-3">
      <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-[var(--text-muted)]">Loading...</span>
    </div>
  </div>
)

const LazyPage = ({ children }: { children: ReactNode }) => (
  <Suspense fallback={<LoadingFallback />}>{children}</Suspense>
)

const DashboardPage = lazy(() => import('./pages/Dashboard'))
const StudiesPage = lazy(() => import('./pages/Studies'))
const StudyRunPage = lazy(() => import('./pages/StudyRun'))
const AssetManagementPage = lazy(() => import('./pages/AssetManagement'))
const AIAssistantPage = lazy(() => import('./pages/AIAssistant'))
const ProjectsPage = lazy(() => import('./pages/Projects'))
const EtapIntegrationPage = lazy(() => import('./pages/EtapIntegration'))
const GisIntegrationPage = lazy(() => import('./pages/GisIntegration'))
const ReportsPage = lazy(() => import('./pages/Reports'))
const SettingsPage = lazy(() => import('./pages/Settings'))
const AdministrationPage = lazy(() => import('./pages/Administration'))
const DiagnosticsPage = lazy(() => import('./pages/Diagnostics'))
const DigitalTwinPage = lazy(() => import('./pages/DigitalTwin'))
const DataImportPage = lazy(() => import('./pages/DataImport'))
const DataExportPage = lazy(() => import('./pages/DataExport'))
const LogsPage = lazy(() => import('./pages/Logs'))
const CodeGuardPage = lazy(() => import('./pages/CodeGuard'))
const LoginPage = lazy(() => import('./pages/Login'))
const RegisterPage = lazy(() => import('./pages/Register'))

// Inner component that activates keyboard shortcuts inside the Router context
function KeyboardShortcutsHandler() {
  useKeyboardShortcuts()
  return null
}

export default function App() {
  const { i18n } = useTranslation()
  const { lastError, setLastError } = useAppStore()
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpContext, setHelpContext] = useState<string | undefined>()
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  // Electron menu navigation
  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.onNavigate((path: string) => {
        window.location.hash = path
      })
    }
  }, [])

  // F1 / Ctrl+H for Smart Help
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'F1') {
        e.preventDefault()
        setHelpOpen(prev => !prev)
        setHelpContext(undefined)
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault()
        setHelpOpen(prev => !prev)
        setHelpContext(undefined)
      }
    }
    globalThis.addEventListener('keydown', handleKeyDown)
    return () => globalThis.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Listen for toggle-shortcuts-panel events (from the Navbar shortcuts button)
  useEffect(() => {
    const handler = () => setShortcutsOpen(prev => !prev)
    globalThis.addEventListener('toggle-shortcuts-panel', handler)
    return () => globalThis.removeEventListener('toggle-shortcuts-panel', handler)
  }, [])

  // Listen for toggle-theme events
  useEffect(() => {
    const handler = () => {
      const current = document.documentElement.classList.contains('dark') ? 'dark' : 'light'
      const next = current === 'dark' ? 'light' : 'dark'
      document.documentElement.classList.remove(current)
      document.documentElement.classList.add(next)
      localStorage.setItem('etap-theme', next)
    }
    globalThis.addEventListener('toggle-theme', handler)
    return () => globalThis.removeEventListener('toggle-theme', handler)
  }, [])

  // Listen for toggle-language events
  useEffect(() => {
    const handler = () => {
      const newLang = i18n.language === 'ar' ? 'en' : 'ar'
      i18n.changeLanguage(newLang)
      document.documentElement.dir = newLang === 'ar' ? 'rtl' : 'ltr'
      document.documentElement.lang = newLang
    }
    globalThis.addEventListener('toggle-language', handler)
    return () => globalThis.removeEventListener('toggle-language', handler)
  }, [i18n])

  // Listen for help context events from other components
  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent
      if (customEvent.detail?.contextId) {
        setHelpContext(customEvent.detail.contextId)
        setHelpOpen(true)
      }
    }
    globalThis.addEventListener('open-smart-help', handler)
    return () => globalThis.removeEventListener('open-smart-help', handler)
  }, [])

  // Listen for toggle-smart-help events (from the Help button in the navbar)
  useEffect(() => {
    const handler = () => {
      setHelpOpen(prev => !prev)
      setHelpContext(undefined)
    }
    globalThis.addEventListener('toggle-smart-help', handler)
    return () => globalThis.removeEventListener('toggle-smart-help', handler)
  }, [])

  return (
    <ThemeProvider>
      <NotificationProvider>
        <AuthProvider>
        <DemoModeBanner />
        <BrowserRouter>
          <Routes>
            {/* Auth routes - no Layout */}
            <Route path="/login" element={<LazyPage><LoginPage /></LazyPage>} />
            <Route path="/register" element={<LazyPage><RegisterPage /></LazyPage>} />

            {/* App routes - with Layout */}
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<LazyPage><DashboardPage /></LazyPage>} />
              <Route path="/studies" element={<LazyPage><StudiesPage /></LazyPage>} />
              <Route path="/studies/:studyType" element={<LazyPage><StudyRunPage /></LazyPage>} />
              <Route path="/asset-management" element={<LazyPage><AssetManagementPage /></LazyPage>} />
              <Route path="/assistant" element={<LazyPage><AIAssistantPage /></LazyPage>} />
              <Route path="/projects" element={<LazyPage><ProjectsPage /></LazyPage>} />
              <Route path="/etap" element={<LazyPage><EtapIntegrationPage /></LazyPage>} />
              <Route path="/gis" element={<LazyPage><GisIntegrationPage /></LazyPage>} />
              <Route path="/reports" element={<LazyPage><ReportsPage /></LazyPage>} />
              <Route path="/settings" element={<LazyPage><SettingsPage /></LazyPage>} />
              <Route path="/admin" element={<LazyPage><AdministrationPage /></LazyPage>} />
              <Route path="/diagnostics" element={<LazyPage><DiagnosticsPage /></LazyPage>} />
              <Route path="/digital-twin" element={<LazyPage><DigitalTwinPage /></LazyPage>} />
              <Route path="/data-import" element={<LazyPage><DataImportPage /></LazyPage>} />
              <Route path="/data-export" element={<LazyPage><DataExportPage /></LazyPage>} />
              <Route path="/logs" element={<LazyPage><LogsPage /></LazyPage>} />
              <Route path="/code-guard" element={<LazyPage><CodeGuardPage /></LazyPage>} />
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
            onClose={() => { setHelpOpen(false); setHelpContext(undefined) }}
            initialContextId={helpContext}
          />
          <ShortcutsPanel
            open={shortcutsOpen}
            onClose={() => setShortcutsOpen(false)}
          />
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
  )
}
