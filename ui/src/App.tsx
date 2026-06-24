import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ThemeProvider } from './context/ThemeContext'
import { NotificationProvider } from './context/NotificationContext'
import { Layout } from './components/Layout'
import { SmartHelpDrawer } from './components/help/SmartHelpDrawer'
import { CommandPalette } from './components/command/CommandPalette'
import { OnboardingTour } from './components/onboarding/OnboardingTour'
import { ErrorRecovery } from './components/context/ErrorRecovery'
import { useAppStore } from './store'
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

export default function App() {
  const { i18n } = useTranslation()
  const { lastError, setLastError } = useAppStore()
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpContext, setHelpContext] = useState<string | undefined>()

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
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Listen for help context events from other components
  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent
      if (customEvent.detail?.contextId) {
        setHelpContext(customEvent.detail.contextId)
        setHelpOpen(true)
      }
    }
    window.addEventListener('open-smart-help', handler)
    return () => window.removeEventListener('open-smart-help', handler)
  }, [])

  return (
    <ThemeProvider>
      <NotificationProvider>
        <BrowserRouter>
          <Routes>
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
            </Route>
          </Routes>
        </BrowserRouter>

        {/* Global Overlays */}
        <CommandPalette />
        <OnboardingTour />
        <SmartHelpDrawer
          open={helpOpen}
          onClose={() => { setHelpOpen(false); setHelpContext(undefined) }}
          initialContextId={helpContext}
        />
        <ErrorRecovery
          error={lastError}
          onDismiss={() => setLastError(null)}
          onRetry={() => window.location.reload()}
        />
      </NotificationProvider>
    </ThemeProvider>
  )
}
