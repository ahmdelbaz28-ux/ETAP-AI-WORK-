import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useTheme } from '../context/ThemeContext'
import { useAppStore } from '../store'
import { fetchHealth, type HealthResponse } from '../lib/api'
import { useEffect, useState } from 'react'
import {
  LayoutDashboard, FlaskConical, Bot, FolderKanban, Settings,
  ShieldCheck, Bug, Map, FileText, Upload, Download, ScrollText,
  ChevronLeft, ChevronRight, Sun, Moon, Zap, Plug, Layers, Network,
  Cpu, Wrench, Shield
} from 'lucide-react'
import { cn } from '../utils/helpers'

interface NavItem {
  to: string
  icon: React.ElementType
  labelKey: string
  section?: string
  badge?: string | number
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, labelKey: 'sidebar.dashboard' },
  { to: '/studies', icon: FlaskConical, labelKey: 'sidebar.studies' },
  { to: '/assistant', icon: Bot, labelKey: 'sidebar.assistant' },
  { to: '/projects', icon: FolderKanban, labelKey: 'sidebar.projects', section: 'engineering' },
  { to: '/asset-management', icon: Network, labelKey: 'sidebar.assetManagement', section: 'engineering' },
  { to: '/etap', icon: Plug, labelKey: 'sidebar.etapIntegration', section: 'integration' },
  { to: '/gis', icon: Map, labelKey: 'sidebar.gisIntegration', section: 'integration' },
  { to: '/digital-twin', icon: Layers, labelKey: 'sidebar.digitalTwin', section: 'integration' },
  { to: '/reports', icon: FileText, labelKey: 'sidebar.reports' },
  { to: '/data-import', icon: Upload, labelKey: 'sidebar.dataImport', section: 'system' },
  { to: '/data-export', icon: Download, labelKey: 'sidebar.dataExport', section: 'system' },
  { to: '/settings', icon: Settings, labelKey: 'sidebar.settings', section: 'system' },
  { to: '/admin', icon: ShieldCheck, labelKey: 'sidebar.administration', section: 'system' },
  { to: '/diagnostics', icon: Bug, labelKey: 'sidebar.diagnostics', section: 'system' },
  { to: '/code-guard', icon: Shield, labelKey: 'sidebar.codeGuard', section: 'system' },
  { to: '/logs', icon: ScrollText, labelKey: 'sidebar.logs', section: 'system' },
]

const sectionOrder = ['engineering', 'integration', 'system'] as const
const sectionLabels: Record<string, string> = {
  engineering: 'sidebar.engineering',
  integration: 'sidebar.integration',
  system: 'sidebar.system',
}

const sectionIcons: Record<string, React.ElementType> = {
  engineering: Cpu,
  integration: Plug,
  system: Wrench,
}

export function Sidebar() {  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  const { t, i18n } = useTranslation()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
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
      role="complementary"
      aria-label="Sidebar Navigation"
      className={cn(
        'h-screen flex flex-col bg-[var(--bg-secondary)] border-r border-[var(--border-primary)] shrink-0 transition-all duration-300 overflow-hidden z-[var(--z-sidebar)]',
        sidebarCollapsed ? 'w-[68px]' : 'w-64'
      )}
    >
      {/* Logo Section */}
      <div className="p-4 border-b border-[var(--border-primary)]">
        <div className={cn('flex items-center gap-2.5', sidebarCollapsed && 'justify-center')}>
          <div className="w-9 h-9 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/25 relative">
            <Zap className="w-5 h-5 text-white" />
            {healthStatus === 'online' && (
              <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-[var(--bg-secondary)]" />
            )}
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-[var(--text-primary)] truncate tracking-tight">{t('app.name')}</h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  healthStatus === 'online' ? 'bg-green-400 animate-pulse' :
                  healthStatus === 'checking' ? 'bg-amber-400' : 'bg-red-400'  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
                )} />
                <span className="text-[10px] text-[var(--text-muted)] capitalize">{t(`dashboard.${healthStatus}`)}</span>
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
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group relative',
                sidebarCollapsed && 'justify-center px-0',
                !sidebarCollapsed && 'nav-indicator',
                isActive && !sidebarCollapsed && 'active',
                isActive
                  ? 'bg-brand-600/80 text-white font-medium shadow-sm shadow-brand-600/30 ring-1 ring-brand-500/30'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
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
        {sectionOrder.map(section => {
          const items = groupedItems[section]
          if (!items?.length) return null
          const SectionIcon = sectionIcons[section]
          return (
            <div key={section} className="pt-4">
              {!sidebarCollapsed && (
                <div className="flex items-center gap-1.5 px-3 mb-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                  {SectionIcon && <SectionIcon className="w-3 h-3" />}
                  {t(sectionLabels[section])}
                </div>
              )}
              {sidebarCollapsed && <hr className="border-[var(--border-primary)] mx-2" />}
              {items.map(item => {
                const isActive = location.pathname === item.to
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={() =>
                      cn(
                        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5 group relative',
                        sidebarCollapsed && 'justify-center px-0',
                        isActive
                          ? 'bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30'
                          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
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
                )
              })}
            </div>
          )
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-2 border-t border-[var(--border-primary)] space-y-1">
        <button
          onClick={toggleTheme}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors',
            sidebarCollapsed && 'justify-center px-0'
          )}
          aria-label={theme === 'dark' ? t('sidebar.lightMode') : t('sidebar.darkMode')}
        >
          {theme === 'dark' ? <Sun className="w-[18px] h-[18px] shrink-0" /> : <Moon className="w-[18px] h-[18px] shrink-0" />}
          {!sidebarCollapsed && <span>{theme === 'dark' ? t('sidebar.lightMode') : t('sidebar.darkMode')}</span>}
        </button>

        <button
          onClick={toggleSidebar}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)] transition-colors',
            sidebarCollapsed && 'justify-center px-0'
          )}
          title={sidebarCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
          aria-label={sidebarCollapsed ? t('sidebar.expand') : t('sidebar.collapse')}
        >
          {sidebarCollapsed
            ? <ChevronRight className={`w-[18px] h-[18px] shrink-0 ${isRtl ? 'rotate-180' : ''}`} />
            : <>{isRtl ? <ChevronRight className="w-[18px] h-[18px] shrink-0" /> : <ChevronLeft className="w-[18px] h-[18px] shrink-0" />}<span>{t('sidebar.collapse')}</span></>
          }
        </button>

        {!sidebarCollapsed && (
          <div className="text-[10px] text-[var(--text-muted)] text-center pt-1">
            v{t('app.version')} &middot; {new Date().getFullYear()}
          </div>
        )}
      </div>
    </aside>
  )
}
