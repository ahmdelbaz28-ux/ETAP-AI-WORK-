import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Search, Bell, X, Globe, Clock, Command, Maximize2, Minimize2,
  Sparkles, HelpCircle, Keyboard, ChevronDown, User as UserIcon,
  Settings, LogOut, ShieldCheck,
} from 'lucide-react'
import { useAppStore } from '../store'
import { cn } from '../utils/helpers'

export function Navbar() {
  const { t, i18n } = useTranslation()
  const { searchQuery, setSearchQuery } = useAppStore()
  const [showSearch, setShowSearch] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)

  const isRtl = i18n.language === 'ar'

  const openHelp = () => {
    window.dispatchEvent(new CustomEvent('toggle-smart-help'))
  }

  const openShortcuts = () => {
    window.dispatchEvent(new CustomEvent('toggle-shortcuts-panel'))
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

  // Close user menu on outside click
  useEffect(() => {
    if (!showUserMenu) return
    const handler = () => setShowUserMenu(false)
    setTimeout(() => document.addEventListener('click', handler), 0)
    return () => document.removeEventListener('click', handler)
  }, [showUserMenu])

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
  const ToolButton = ({
    onClick, icon: Icon, title, badge, active, accent,
  }: {
    onClick: () => void
    icon: React.ElementType
    title: string
    badge?: boolean
    active?: boolean
    accent?: 'brand' | 'default'
  }) => (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className={cn(
        'relative p-2 rounded-lg transition-all duration-150 group',
        active
          ? 'bg-brand-500/15 text-brand-400'
          : accent === 'brand'
            ? 'text-brand-400 hover:bg-brand-500/10 hover:text-brand-300'
            : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
      )}
    >
      <Icon className="w-[18px] h-[18px]" />
      {badge && (
        <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-brand-500 animate-pulse ring-2 ring-[var(--bg-secondary)]" />
      )}
      {/* Tooltip */}
      <span className="absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] text-[var(--text-secondary)] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
        {title}
      </span>
    </button>
  )

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-[var(--bg-secondary)]/80 backdrop-blur-xl border-b border-[var(--border-primary)]/50 shrink-0 z-[var(--z-navbar)] relative">
      {/* ─── Left: Search ──────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-1 max-w-md">
        {/* Search input (expandable) */}
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

        {/* Search toggle button (when collapsed) */}
        {!showSearch && (
          <button
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-primary)]/50 hover:bg-[var(--bg-input)] hover:border-[var(--border-primary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all text-sm group"
            aria-label="Search"
          >
            <Search className="w-4 h-4" />
            <span className="hidden lg:inline text-xs">{t('navbar.searchPlaceholder') || 'Search...'}</span>
            <kbd className="hidden lg:flex items-center gap-0.5 text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]">
              <Command className="w-2.5 h-2.5" />K
            </kbd>
          </button>
        )}
      </div>

      {/* ─── Center: Brand (hidden on mobile) ──────────────────────── */}
      <div className="hidden md:flex items-center gap-2 absolute left-1/2 -translate-x-1/2">
        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-[var(--bg-primary)]/40 border border-[var(--border-primary)]/30">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">
            AhmedETAP v2.1
          </span>
        </div>
      </div>

      {/* ─── Right: Tools ──────────────────────────────────────────── */}
      <div className="flex items-center gap-0.5">
        {/* Language Toggle */}
        <ToolButton
          onClick={toggleLanguage}
          icon={Globe}
          title={isRtl ? 'Switch to English' : 'التبديل للعربية'}
        />

        {/* Fullscreen Toggle */}
        <ToolButton
          onClick={toggleFullscreen}
          icon={isFullscreen ? Minimize2 : Maximize2}
          title={isFullscreen ? 'Exit Fullscreen (F11)' : 'Fullscreen (F11)'}
        />

        {/* Separator */}
        <div className="w-px h-5 bg-[var(--border-primary)] mx-1" />

        {/* Magic Help Inspector */}
        <ToolButton
          onClick={() => window.dispatchEvent(new CustomEvent('start-magic-help-inspect'))}
          icon={Sparkles}
          title="Magic Help Inspector (Ctrl+Shift+H)"
          accent="brand"
          badge
        />

        {/* Help */}
        <ToolButton
          onClick={openHelp}
          icon={HelpCircle}
          title="Smart Help (F1)"
        />

        {/* Keyboard Shortcuts — the new professional icon */}
        <ToolButton
          onClick={openShortcuts}
          icon={Keyboard}
          title="Keyboard Shortcuts (Ctrl+/)"
          active
        />

        {/* Notifications */}
        <ToolButton
          onClick={() => {}}
          icon={Bell}
          title="Notifications"
          badge
        />

        {/* Separator */}
        <div className="w-px h-5 bg-[var(--border-primary)] mx-1" />

        {/* ─── User Avatar + Dropdown ─────────────────────────────── */}
        <div className="relative">
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
            <div
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
                  onClick={() => { setShowUserMenu(false); window.location.hash = '#/settings' }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <Settings className="w-4 h-4 text-[var(--text-muted)]" />
                  <span>Settings</span>
                  <kbd className="ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]">G E</kbd>
                </button>

                <button
                  onClick={() => { setShowUserMenu(false); window.location.hash = '#/diagnostics' }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <ShieldCheck className="w-4 h-4 text-[var(--text-muted)]" />
                  <span>Diagnostics</span>
                  <kbd className="ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]">G I</kbd>
                </button>

                <div className="h-px bg-[var(--border-primary)] my-1.5" />

                <button
                  onClick={() => setShowUserMenu(false)}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>

              {/* Footer */}
              <div className="px-4 py-2 bg-[var(--bg-primary)]/50 border-t border-[var(--border-primary)]">
                <div className="text-[9px] text-[var(--text-muted)] font-mono text-center">
                  AhmedETAP v2.1.0 · Build 2026.06.27
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
