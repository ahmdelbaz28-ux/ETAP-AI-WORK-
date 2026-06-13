import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useTheme } from '../context/ThemeContext'
import { useAppStore } from '../store'
import { fetchHealth, type HealthResponse } from '../lib/api'
import { useEffect, useState } from 'react'
import {
  LayoutDashboard, FlaskConical, Bot, FolderKanban, Settings,
  ShieldCheck, Bug, Map, FileText, Upload, Download, ScrollText,
  ChevronLeft, ChevronRight, Sun, Moon, Zap, Plug, Layers, Network
} from 'lucide-react'
import { cn } from '../utils/helpers'

interface NavItem {
  to: string
  icon: React.ElementType
  labelKey: string
  section?: string
  divider?: boolean
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
  { to: '/studies', icon: FlaskConical, labelKey: 'sidebar.studies' },
  { to: '/assistant', icon: Bot, labelKey: 'sidebar.assistant' },
  { to: '/projects', icon: FolderKanban, labelKey: 'sidebar.projects', section: 'engineering' },
  { to: '/etap', icon: Plug, labelKey: 'sidebar.etapIntegration', section: 'integration' },
  { to: '/gis', icon: Map, labelKey: 'sidebar.gisIntegration', section: 'integration' },
  { to: '/digital-twin', icon: Layers, labelKey: 'sidebar.digitalTwin', section: 'integration' },
  { to: '/asset-management', icon: Network, labelKey: 'sidebar.assetManagement', section: 'engineering' },
  { to: '/reports', icon: FileText, labelKey: 'sidebar.reports' },
  { to: '/data-import', icon: Upload, labelKey: 'sidebar.dataImport', section: 'system' },
  { to: '/data-export', icon: Download, labelKey: 'sidebar.dataExport', section: 'system' },
  { to: '/settings', icon: Settings, labelKey: 'sidebar.settings', section: 'system' },
  { to: '/admin', icon: ShieldCheck, labelKey: 'sidebar.administration', section: 'system' },
  { to: '/diagnostics', icon: Bug, labelKey: 'sidebar.diagnostics', section: 'system' },
  { to: '/logs', icon: ScrollText, labelKey: 'sidebar.logs', section: 'system' },
]

const sectionOrder = ['engineering', 'integration', 'system'] as const
const sectionLabels: Record<string, string> = {
  engineering: 'sidebar.engineering',
  integration: 'sidebar.integration',
  system: 'sidebar.system',
}

export function Sidebar() {
  const { t, i18n } = useTranslation()
  const { theme, toggleTheme } = useTheme()
  const _location = useLocation() // available for future active route highlighting
  const { sidebarCollapsed, toggleSidebar } = useAppStore()
  const [healthStatus, setHealthStatus] = useState<'online' | 'offline' | 'checking'>('checking')

  const isRtl = i18n.language === 'ar'

  useEffect(() => {
    fetchHealth()
      .then((h: HealthResponse) => setHealthStatus(h.ok ? 'online' : 'offline'))
      .catch(() => setHealthStatus('offline'))
    const interval = setInterval(() => {
      fetchHealth()
        .then((h: HealthResponse) => setHealthStatus(h.ok ? 'online' : 'offline'))
        .catch(() => setHealthStatus('offline'))
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  const groupedItems: Record<string, NavItem[]> = {}
  const topLevel: NavItem[] = []
  navItems.forEach(item => {
    if (!item.section) {
      topLevel.push(item)
    } else {
      if (!groupedItems[item.section]) groupedItems[item.section] = []
      groupedItems[item.section].push(item)
    }
  })

  return (
    <aside
      className={cn(
        'h-screen flex flex-col bg-surface-900 border-r border-surface-700 shrink-0 transition-all duration-300 overflow-hidden',
        sidebarCollapsed ? 'w-[68px]' : 'w-64'
      )}
    >
      {/* Logo Section */}
      <div className="p-4 border-b border-surface-700">
        <div className={cn('flex items-center gap-2', sidebarCollapsed && 'justify-center')}>
          <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-brand-700 rounded-lg flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-white truncate">{t('app.name')}</h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={cn(
                  'w-1.5 h-1.5 rounded-full animate-pulse',
                  healthStatus === 'online' ? 'bg-green-400' :
                  healthStatus === 'checking' ? 'bg-amber-400' : 'bg-red-400'
                )} />
                <span className="text-[10px] text-surface-400 capitalize">{t(`dashboard.${healthStatus}`)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {topLevel.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150',
                sidebarCollapsed && 'justify-center px-0',
                isActive
                  ? 'bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30'
                  : 'text-surface-300 hover:bg-surface-800 hover:text-white'
              )
            }
          >
            <item.icon className="w-[18px] h-[18px] shrink-0" />
            {!sidebarCollapsed && <span className="truncate">{t(item.labelKey)}</span>}
          </NavLink>
        ))}

        {/* Grouped sections */}
        {sectionOrder.map(section => {
          const items = groupedItems[section]
          if (!items?.length) return null
          return (
            <div key={section} className="pt-3">
              {!sidebarCollapsed && (
                <div className="px-3 mb-1 text-[10px] font-semibold text-surface-500 uppercase tracking-wider">
                  {t(sectionLabels[section])}
                </div>
              )}
              {sidebarCollapsed && <hr className="border-surface-700 mx-2" />}
              {items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5',
                      sidebarCollapsed && 'justify-center px-0',
                      isActive
                        ? 'bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30'
                        : 'text-surface-300 hover:bg-surface-800 hover:text-white'
                    )
                  }
                >
                  <item.icon className="w-[18px] h-[18px] shrink-0" />
                  {!sidebarCollapsed && <span className="truncate">{t(item.labelKey)}</span>}
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-2 border-t border-surface-700 space-y-1">
        <button
          onClick={toggleTheme}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-300 hover:bg-surface-800 hover:text-white transition-colors',
            sidebarCollapsed && 'justify-center px-0'
          )}
        >
          {theme === 'dark' ? <Sun className="w-[18px] h-[18px] shrink-0" /> : <Moon className="w-[18px] h-[18px] shrink-0" />}
          {!sidebarCollapsed && <span>{theme === 'dark' ? t('sidebar.lightMode') : t('sidebar.darkMode')}</span>}
        </button>

        <button
          onClick={toggleSidebar}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-400 hover:bg-surface-800 hover:text-surface-200 transition-colors',
            sidebarCollapsed && 'justify-center px-0'
          )}
          title={sidebarCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
        >
          {sidebarCollapsed
            ? <ChevronRight className={`w-[18px] h-[18px] shrink-0 ${isRtl ? 'rotate-180' : ''}`} />
            : <>{isRtl ? <ChevronRight className="w-[18px] h-[18px] shrink-0" /> : <ChevronLeft className="w-[18px] h-[18px] shrink-0" />}<span>{t('sidebar.collapse')}</span></>
          }
        </button>

        {!sidebarCollapsed && (
          <div className="text-[10px] text-surface-600 text-center pt-1">
            v{t('app.version')} &middot; {new Date().getFullYear()}
          </div>
        )}
      </div>
    </aside>
  )
}
