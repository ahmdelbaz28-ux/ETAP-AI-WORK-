import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ThemeProvider } from './context/ThemeContext'
import { NotificationProvider } from './context/NotificationContext'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Studies } from './pages/Studies'
import { StudyRun } from './pages/StudyRun'
import { AIAssistant } from './pages/AIAssistant'
import { Projects } from './pages/Projects'
import { EtapIntegration } from './pages/EtapIntegration'
import { GisIntegration } from './pages/GisIntegration'
import { Reports } from './pages/Reports'
import { Settings } from './pages/Settings'
import { Administration } from './pages/Administration'
import { Diagnostics } from './pages/Diagnostics'
import { AssetManagement } from './pages/AssetManagement'
import { DigitalTwin } from './pages/DigitalTwin'
import { DataImport } from './pages/DataImport'
import { DataExport } from './pages/DataExport'
import { Logs } from './pages/Logs'
import './i18n'

export default function App() {
  const { i18n } = useTranslation()

  // Set initial direction based on language
  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  return (
    <ThemeProvider>
      <NotificationProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/studies" element={<Studies />} />
              <Route path="/studies/:studyType" element={<StudyRun />} />
              <Route path="/asset-management" element={<AssetManagement />} />
              <Route path="/assistant" element={<AIAssistant />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/etap" element={<EtapIntegration />} />
              <Route path="/gis" element={<GisIntegration />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/admin" element={<Administration />} />
              <Route path="/diagnostics" element={<Diagnostics />} />
              <Route path="/digital-twin" element={<DigitalTwin />} />
              <Route path="/data-import" element={<DataImport />} />
              <Route path="/data-export" element={<DataExport />} />
              <Route path="/logs" element={<Logs />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </NotificationProvider>
    </ThemeProvider>
  )
}
