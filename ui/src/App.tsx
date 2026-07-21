import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ThemeProvider } from './context/ThemeContext'
import { NotificationProvider } from './context/NotificationContext'
import { Layout } from './components/Layout'
import { useAppStore } from './store'
import './i18n'

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

const CommandPalette = lazy(() => import('./components/command/CommandPalette'))
const OnboardingTour = lazy(() => import('./components/onboarding/OnboardingTour'))
const SmartHelpDrawer = lazy(() => import('./components/help/SmartHelpDrawer'))
const ErrorRecovery = lazy(() => import('./components/context/ErrorRecovery'))

const PageFallback = () => (
  <div className="flex items-center justify-center h-64">
    <div className="flex flex-col items-center gap-3">
      <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-[var(--text-muted)]">Loading...</span>
    </div>
  </div>
)

export default function App() {
  const { i18n } = useTranslation()
  const { lastError, setLastError, toggleHelpPanel } = useAppStore()
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
              <Route path="/dashboard" element={<Suspense fallback={<PageFallback />}><DashboardPage /></Suspense>} />
              <Route path="/studies" element={<Suspense fallback={<PageFallback />}><StudiesPage /></Suspense>} />
              <Route path="/studies/:studyType" element={<Suspense fallback={<PageFallback />}><StudyRunPage /></Suspense>} />
              <Route path="/asset-management" element={<Suspense fallback={<PageFallback />}><AssetManagementPage /></Suspense>} />
              <Route path="/assistant" element={<Suspense fallback={<PageFallback />}><AIAssistantPage /></Suspense>} />
              <Route path="/projects" element={<Suspense fallback={<PageFallback />}><ProjectsPage /></Suspense>} />
              <Route path="/etap" element={<Suspense fallback={<PageFallback />}><EtapIntegrationPage /></Suspense>} />
              <Route path="/gis" element={<Suspense fallback={<PageFallback />}><GisIntegrationPage /></Suspense>} />
              <Route path="/reports" element={<Suspense fallback={<PageFallback />}><ReportsPage /></Suspense>} />
              <Route path="/settings" element={<Suspense fallback={<PageFallback />}><SettingsPage /></Suspense>} />
              <Route path="/admin" element={<Suspense fallback={<PageFallback />}><AdministrationPage /></Suspense>} />
              <Route path="/diagnostics" element={<Suspense fallback={<PageFallback />}><DiagnosticsPage /></Suspense>} />
              <Route path="/digital-twin" element={<Suspense fallback={<PageFallback />}><DigitalTwinPage /></Suspense>} />
              <Route path="/data-import" element={<Suspense fallback={<PageFallback />}><DataImportPage /></Suspense>} />
              <Route path="/data-export" element={<Suspense fallback={<PageFallback />}><DataExportPage /></Suspense>} />
              <Route path="/logs" element={<Suspense fallback={<PageFallback />}><LogsPage /></Suspense>} />
              <Route path="/code-guard" element={<Suspense fallback={<PageFallback />}><CodeGuardPage /></Suspense>} />
            </Route>
          </Routes>
        </BrowserRouter>

        <Suspense fallback={null}>
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
        </Suspense>
      </NotificationProvider>
    </ThemeProvider>
  )
}
