import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Search, Bell, X, Globe, Clock, Command, Maximize2, Minimize2,
  Sparkles, HelpCircle, Keyboard, ChevronDown, User as UserIcon,
  Settings, LogOut, ShieldCheck, CheckCircle2, AlertCircle, Info, AlertTriangle,
  Menu, Zap,
} from 'lucide-react'
import { useAppStore } from '../store'
import { cn } from '../utils/helpers'

interface NotificationItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  time: string
  read: boolean
}

const DEMO_NOTIFICATIONS: NotificationItem[] = [
  { id: '1', type: 'info', title: 'Welcome to AhmedETAP', message: 'Demo mode is active — explore all features without a backend.', time: '2m ago', read: false },
  { id: '2', type: 'success', title: 'Load Flow Completed', message: 'Industrial Plant study finished in 245ms', time: '1h ago', read: false },
  { id: '3', type: 'warning', title: 'ETAP Worker Offline', message: 'Connect to ETAP worker to enable live studies', time: '3h ago', read: true },
  { id: '4', type: 'info', title: 'New Agent Available', message: 'Harmonic Analysis Agent v2.0 deployed', time: '5h ago', read: true },
]

const notifIcon = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const notifColor = {
  success: 'text-green-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-brand-400',
}

interface ToolButtonProps {
  onClick: () => void
  icon: React.ElementType
  title: string
  badge?: boolean
  active?: boolean
  accent?: 'brand' | 'default'
  unreadCount?: number
}

function ToolButton({ onClick, icon: Icon, title, badge, active, accent, unreadCount = 0 }: ToolButtonProps) {
  const toolButtonClass = active
    ? 'bg-brand-500/15 text-brand-400'
    : accent === 'brand'
      ? 'text-brand-400 hover:bg-brand-500/10 hover:text-brand-300'
      : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className={cn(
        'relative p-2 rounded-lg transition-all duration-150 group',
        toolButtonClass
      )}
    >
      <Icon className="w-[18px] h-[18px]" />
      {badge && unreadCount > 0 && (
        <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-[var(--bg-secondary)]">
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      )}
      {/* Tooltip */}
      <span className="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] text-[var(--text-secondary)] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
        {title}
      </span>
    </button>
  )
}

export function Navbar() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { searchQuery, setSearchQuery, toggleMobileSidebar } = useAppStore()
  const [showSearch, setShowSearch] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const [notifications, setNotifications] = useState<NotificationItem[]>(DEMO_NOTIFICATIONS)

  const userMenuRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)

  const isRtl = i18n.language === 'ar'

  const openHelp = () => {
    globalThis.dispatchEvent(new CustomEvent('toggle-smart-help'))
  }

  const openShortcuts = () => {
    globalThis.dispatchEvent(new CustomEvent('toggle-shortcuts-panel'))
  }

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const handleFsChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handleFsChange)
    return () => document.removeEventListener('fullscreenchange', handleFsChange)
  }, [])

  // Close menus on outside click
  useEffect(() => {
    if (!showUserMenu && !showNotifications) return
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false)
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false)
      }
    }
    setTimeout(() => document.addEventListener('click', handler), 0)
    return () => document.removeEventListener('click', handler)
  }, [showUserMenu, showNotifications])

  const toggleLanguage = () => {
    const newLang = i18n.language === 'ar' ? 'en' : 'ar'
    i18n.changeLanguage(newLang)
    document.documentElement.dir = newLang === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = newLang
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      document.documentElement.requestFullscreen()
    }
  }

  const handleSignOut = () => {
    setShowUserMenu(false)
    localStorage.removeItem('authToken')
    localStorage.removeItem('etap-user')
    navigate('/login')
  }

  const markAllRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const dismissNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }

  const unreadCount = notifications.filter(n => !n.read).length

  const formatTime = () => {
    return currentTime.toLocaleTimeString(isRtl ? 'ar-EG' : 'en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !isRtl,
    })
  }

  const formatDate = () => {
    return currentTime.toLocaleDateString(isRtl ? 'ar-EG' : 'en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    })
  }

  // ─── Toolbar button component ──────────────────────────────────────────
  // (ToolButton moved to module scope to avoid re-creating on each render)

  return (
    <header className="flex items-center justify-between px-3 sm:px-4 py-2 bg-[var(--bg-secondary)]/80 backdrop-blur-xl border-b border-[var(--border-primary)]/50 shrink-0 z-[var(--z-navbar)] relative">
      {/* ─── Left: Hamburger (mobile only) + Brand + Search ────────── */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {/* Hamburger menu — mobile only */}
        <button
          onClick={toggleMobileSidebar}
          aria-label="Open menu"
          className="lg:hidden p-2 -ml-1 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors shrink-0"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Brand logo — mobile only (desktop uses sidebar logo) */}
        <div className="lg:hidden flex items-center gap-1.5 shrink-0">
          <div className="w-7 h-7 bg-gradient-to-br from-brand-500 to-brand-700 rounded-lg flex items-center justify-center shadow-sm">
            <Zap className="w-4 h-4 text-white" />
          </div>
        </div>

        {/* Search input (expandable) — hidden on mobile when collapsed */}
        <div className={cn(
          'relative transition-all duration-300 ease-out',
          showSearch ? 'w-full opacity-100' : 'w-9 opacity-0 pointer-events-none'
        )}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('navbar.searchPlaceholder') || 'Search...'}
            className="w-full pl-9 pr-10 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
            autoFocus={showSearch}
          />
          {showSearch && (
            <button
              onClick={() => { setShowSearch(false); setSearchQuery('') }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Search toggle button (when collapsed) — hidden on mobile */}
        {!showSearch && (
          <button
            onClick={() => setShowSearch(true)}
            className="hidden sm:flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-primary)]/50 hover:bg-[var(--bg-input)] hover:border-[var(--border-primary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all text-sm group"
            aria-label="Search"
          >
            <Search className="w-4 h-4" />
            <span className="hidden lg:inline text-xs">{t('navbar.searchPlaceholder') || 'Search...'}</span>
            <kbd className="hidden lg:flex items-center gap-0.5 text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]">
              <Command className="w-2.5 h-2.5" />K
            </kbd>
          </button>
        )}

        {/* Mobile search icon button (when not expanded) */}
        {!showSearch && (
          <button
            onClick={() => setShowSearch(true)}
            aria-label="Search"
            className="sm:hidden p-2 rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors shrink-0"
          >
            <Search className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* ─── Center: Brand (hidden on mobile) ──────────────────────── */}
      <div className="hidden lg:flex items-center gap-2 absolute left-1/2 -translate-x-1/2">
        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-[var(--bg-primary)]/40 border border-[var(--border-primary)]/30">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">
            AhmedETAP v2.1
          </span>
        </div>
      </div>

      {/* ─── Right: Tools ──────────────────────────────────────────── */}
      <div className="flex items-center gap-0.5 shrink-0">
        {/* Language Toggle — hidden on mobile (in sidebar drawer instead) */}
        <div className="hidden sm:block">
          <ToolButton
            onClick={toggleLanguage}
            icon={Globe}
            title={isRtl ? 'Switch to English' : 'التبديل للعربية'}
          />
        </div>

        {/* Fullscreen Toggle — hidden on mobile */}
        <div className="hidden sm:block">
          <ToolButton
            onClick={toggleFullscreen}
            icon={isFullscreen ? Minimize2 : Maximize2}
            title={isFullscreen ? 'Exit Fullscreen (F11)' : 'Fullscreen (F11)'}
          />
        </div>

        {/* Separator — hidden on mobile */}
        <div className="hidden sm:block w-px h-5 bg-[var(--border-primary)] mx-1" />

        {/* Magic Help Inspector — hidden on mobile */}
        <div className="hidden md:block">
          <ToolButton
            onClick={() => globalThis.dispatchEvent(new CustomEvent('start-magic-help-inspect'))}
            icon={Sparkles}
            title="Magic Help Inspector (Ctrl+Shift+H)"
            accent="brand"
            badge
            unreadCount={unreadCount}
          />
        </div>

        {/* Help — hidden on mobile */}
        <div className="hidden md:block">
          <ToolButton
            onClick={openHelp}
            icon={HelpCircle}
            title="Smart Help (F1)"
          />
        </div>

        {/* Keyboard Shortcuts — hidden on mobile */}
        <div className="hidden md:block">
          <ToolButton
            onClick={openShortcuts}
            icon={Keyboard}
            title="Keyboard Shortcuts (Ctrl+/)"
            active
          />
        </div>

        {/* Notifications — with dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setShowNotifications(prev => !prev) }}
            title="Notifications"
            aria-label="Notifications"
            className={cn(
              'relative p-2 rounded-lg transition-all duration-150 group',
              showNotifications
                ? 'bg-brand-500/15 text-brand-400'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
            )}
          >
            <Bell className="w-[18px] h-[18px]" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-[var(--bg-secondary)] animate-pulse">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
            <span className="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] text-[var(--text-secondary)] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
              Notifications
            </span>
          </button>

          {showNotifications && (
            <div  // NOSONAR — S6848: non-interactive DOM role; intentional
              className="absolute right-0 top-full mt-2 w-96 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-primary)]/50">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-brand-400" />
                  <span className="text-sm font-semibold text-[var(--text-primary)]">Notifications</span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400 font-bold">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    className="text-[10px] text-brand-400 hover:text-brand-300 font-medium transition-colors"
                  >
                    Mark all read
                  </button>
                )}
              </div>

              {/* Notifications list */}
              <div className="max-h-96 overflow-y-auto">
                {notifications.length > 0 ? (
                  notifications.map(n => {
                    const Icon = notifIcon[n.type]
                    return (
                      <div
                        key={n.id}
                        className={cn(
                          'flex items-start gap-3 px-4 py-3 border-b border-[var(--border-primary)]/50 hover:bg-[var(--bg-elevated)]/50 transition-colors group',
                          !n.read && 'bg-brand-500/5'
                        )}
                      >
                        <Icon className={cn('w-4 h-4 mt-0.5 shrink-0', notifColor[n.type])} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{n.title}</p>
                            {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />}
                          </div>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-2">{n.message}</p>
                          <p className="text-[9px] text-[var(--text-muted)] mt-1 font-mono">{n.time}</p>
                        </div>
                        <button
                          onClick={() => dismissNotification(n.id)}
                          className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors opacity-0 group-hover:opacity-100"
                          aria-label="Dismiss"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    )
                  })
                ) : (
                  <div className="py-12 text-center">
                    <Bell className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
                    <p className="text-sm text-[var(--text-tertiary)]">No notifications</p>
                    <p className="text-xs text-[var(--text-muted)] mt-1">You're all caught up!</p>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-4 py-2 bg-[var(--bg-primary)]/50 border-t border-[var(--border-primary)] text-center">
                <span className="text-[10px] text-[var(--text-muted)]">
                  Notification center · {notifications.length} total
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="w-px h-5 bg-[var(--border-primary)] mx-1" />

        {/* ─── User Avatar + Dropdown ─────────────────────────────── */}
        <div className="relative" ref={userMenuRef}>
          <button
            onClick={(e) => { e.stopPropagation(); setShowUserMenu(prev => !prev) }}
            className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors group"
          >
            {/* Professional user avatar with gradient ring */}
            <div className="relative">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 via-brand-500 to-brand-700 p-[2px]">
                <div className="w-full h-full rounded-full bg-[var(--bg-secondary)] flex items-center justify-center">
                  <UserIcon className="w-4 h-4 text-brand-400" />
                </div>
              </div>
              {/* Online status indicator */}
              <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-400 ring-2 ring-[var(--bg-secondary)]" />
            </div>

            {/* User info (hidden on small screens) */}
            <div className="hidden md:flex flex-col items-start leading-tight">
              <span className="text-xs font-medium text-[var(--text-primary)]">
                {t('navbar.welcome') || 'Engineer'}
              </span>
              <div className="flex items-center gap-1 text-[9px] text-[var(--text-muted)] font-mono">
                <Clock className="w-2.5 h-2.5" />
                <span>{formatDate()} · {formatTime()}</span>
              </div>
            </div>

            <ChevronDown className={cn(
              'w-3.5 h-3.5 text-[var(--text-muted)] transition-transform hidden md:block',
              showUserMenu && 'rotate-180'
            )} />
          </button>

          {/* User dropdown menu */}
          {showUserMenu && (
            <div  // NOSONAR — S6848: non-interactive DOM role; intentional
              className="absolute right-0 top-full mt-2 w-64 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50"
              onClick={(e) => e.stopPropagation()}
            >
              {/* User header */}
              <div className="px-4 py-3 bg-gradient-to-br from-brand-500/8 to-transparent border-b border-[var(--border-primary)]">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-brand-700 p-[2px]">
                    <div className="w-full h-full rounded-full bg-[var(--bg-secondary)] flex items-center justify-center">
                      <UserIcon className="w-5 h-5 text-brand-400" />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--text-primary)] truncate">
                      Eng. Ahmed Elbaz
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-green-400">
                      <ShieldCheck className="w-3 h-3" />
                      <span>Administrator · Online</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Menu items */}
              <div className="py-1.5">
                <button
                  onClick={() => { setShowUserMenu(false); navigate('/settings') }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <Settings className="w-4 h-4 text-[var(--text-muted)]" />
                  <span>Settings</span>
                  <kbd className="ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]">G E</kbd>
                </button>

                <button
                  onClick={() => { setShowUserMenu(false); navigate('/diagnostics') }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <ShieldCheck className="w-4 h-4 text-[var(--text-muted)]" />
                  <span>Diagnostics</span>
                  <kbd className="ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]">G I</kbd>
                </button>

                <div className="h-px bg-[var(--border-primary)] my-1.5" />

                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>

              {/* Footer */}
              <div className="px-4 py-2 bg-[var(--bg-primary)]/50 border-t border-[var(--border-primary)]">
                <div className="text-[9px] text-[var(--text-muted)] font-mono text-center">
                  AhmedETAP v2.1.0 · Build 2026.07.03
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
