import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, useEffect, useState } from 'react'
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

function LazyPage({ loader }: { loader: () => Promise<{ [key: string]: unknown }> }) {
  const Component = lazy(async () => {
    const mod = await loader()
    const name = Object.keys(mod).find(k => k !== 'default') || 'default'
    return { default: mod[name] as React.ComponentType }
  })
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading...</span>
        </div>
      </div>
    }>
      <Component />
    </Suspense>
  )
}

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
              <Route path="/dashboard" element={<LazyPage loader={() => import('./pages/Dashboard')} />} />
              <Route path="/studies" element={<LazyPage loader={() => import('./pages/Studies')} />} />
              <Route path="/studies/:studyType" element={<LazyPage loader={() => import('./pages/StudyRun')} />} />
              <Route path="/asset-management" element={<LazyPage loader={() => import('./pages/AssetManagement')} />} />
              <Route path="/assistant" element={<LazyPage loader={() => import('./pages/AIAssistant')} />} />
              <Route path="/projects" element={<LazyPage loader={() => import('./pages/Projects')} />} />
              <Route path="/etap" element={<LazyPage loader={() => import('./pages/EtapIntegration')} />} />
              <Route path="/gis" element={<LazyPage loader={() => import('./pages/GisIntegration')} />} />
              <Route path="/reports" element={<LazyPage loader={() => import('./pages/Reports')} />} />
              <Route path="/settings" element={<LazyPage loader={() => import('./pages/Settings')} />} />
              <Route path="/admin" element={<LazyPage loader={() => import('./pages/Administration')} />} />
              <Route path="/diagnostics" element={<LazyPage loader={() => import('./pages/Diagnostics')} />} />
              <Route path="/digital-twin" element={<LazyPage loader={() => import('./pages/DigitalTwin')} />} />
              <Route path="/data-import" element={<LazyPage loader={() => import('./pages/DataImport')} />} />
              <Route path="/data-export" element={<LazyPage loader={() => import('./pages/DataExport')} />} />
              <Route path="/logs" element={<LazyPage loader={() => import('./pages/Logs')} />} />
              <Route path="/code-guard" element={<LazyPage loader={() => import('./pages/CodeGuard')} />} />
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
