import { NavLink } from 'react-router-dom'
import { useTheme } from '../context/ThemeContext'
import {
  MdDashboard, MdScience, MdSmartToy, MdFolder, MdSettings,
  MdAdminPanelSettings, MdBugReport, MdMap, MdDescription,
  MdFileUpload, MdFileDownload, MdMemory, MdArticle, MdDevices
} from 'react-icons/md'
import { useEffect, useState } from 'react'
import { fetchHealth } from '../lib/api'

const navItems = [
  { to: '/dashboard', icon: MdDashboard, label: 'Dashboard' },
  { to: '/studies', icon: MdScience, label: 'Studies' },
  { to: '/assistant', icon: MdSmartToy, label: 'AI Assistant' },
  { to: '/projects', icon: MdFolder, label: 'Projects' },
  { divider: true },
  { to: '/etap', icon: MdDashboard, label: 'ETAP Integration' },
  { to: '/gis', icon: MdMap, label: 'GIS Integration' },
  { to: '/digital-twin', icon: MdMemory, label: 'Digital Twin' },
  { divider: true },
  { to: '/asset-management', icon: MdDevices, label: 'Asset Management' },
  { to: '/reports', icon: MdDescription, label: 'Reports' },
  { to: '/data-import', icon: MdFileUpload, label: 'Data Import' },
  { to: '/data-export', icon: MdFileDownload, label: 'Data Export' },
  { divider: true },
  { to: '/settings', icon: MdSettings, label: 'Settings' },
  { to: '/admin', icon: MdAdminPanelSettings, label: 'Administration' },
  { to: '/diagnostics', icon: MdBugReport, label: 'Diagnostics' },
  { to: '/logs', icon: MdArticle, label: 'Logs' },
]

export function Sidebar() {
  const { theme, toggleTheme } = useTheme()
  const [healthStatus, setHealthStatus] = useState<'online' | 'offline' | 'checking'>('checking')

  useEffect(() => {
    fetchHealth()
      .then(h => setHealthStatus(h.ok ? 'online' : 'offline'))
      .catch(() => setHealthStatus('offline'))
    const interval = setInterval(() => {
      fetchHealth()
        .then(h => setHealthStatus(h.ok ? 'online' : 'offline'))
        .catch(() => setHealthStatus('offline'))
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <aside className="w-60 h-screen flex flex-col bg-surface-900 dark:bg-surface-900 border-r border-surface-700 shrink-0 overflow-y-auto">
      <div className="p-4 border-b border-surface-700">
        <div className="flex items-center gap-2">
          <MdScience className="text-brand-400 text-2xl" />
          <div>
            <h1 className="text-sm font-bold text-white">ETAP AI Platform</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${
                healthStatus === 'online' ? 'bg-green-400' :
                healthStatus === 'checking' ? 'bg-amber-400' : 'bg-red-400'
              }`} />
              <span className="text-[10px] text-surface-400 capitalize">{healthStatus}</span>
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map((item, i) =>
          'divider' in item ? (
            <hr key={i} className="my-2 border-surface-700" />
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-600 text-white font-medium shadow-sm'
                    : 'text-surface-300 hover:bg-surface-800 hover:text-white'
                }`
              }
            >
              <item.icon className="text-lg shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          )
        )}
      </nav>

      <div className="p-3 border-t border-surface-700">
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-surface-300 hover:bg-surface-800 hover:text-white transition-colors"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
          <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
        <div className="mt-2 text-[10px] text-surface-500 text-center">v1.0.0</div>
      </div>
    </aside>
  )
}
