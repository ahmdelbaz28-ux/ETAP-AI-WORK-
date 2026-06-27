import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Bell, X, Globe, User, Clock, Command, Maximize2, Minimize2, Sparkles } from 'lucide-react'
import { useAppStore } from '../store'
import { cn } from '../utils/helpers'

export function Navbar() {
  const { t, i18n } = useTranslation()
  const { searchQuery, setSearchQuery } = useAppStore()
  const [showSearch, setShowSearch] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())
  const [isFullscreen, setIsFullscreen] = useState(false)

  const isRtl = i18n.language === 'ar'

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const handleFsChange = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handleFsChange)
    return () => document.removeEventListener('fullscreenchange', handleFsChange)
  }, [])

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

  return (
    <header className="flex items-center justify-between px-5 py-2.5 bg-[var(--bg-secondary)]/80 backdrop-blur-md border-b border-[var(--border-primary)]/50 shrink-0 z-[var(--z-navbar)]">
      <div className="flex items-center gap-3 flex-1">
        {/* Search */}
        <div className={cn(
          'relative transition-all duration-300',
          showSearch ? 'w-64 md:w-80' : 'w-0 overflow-hidden'
        )}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('navbar.searchPlaceholder')}
            className="w-full pl-9 pr-16 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition-colors"
            autoFocus={showSearch}
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-[var(--text-muted)] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono">
            <Command className="w-2.5 h-2.5 inline" /> K
          </kbd>
          {showSearch && (
            <button
              onClick={() => { setShowSearch(false); setSearchQuery('') }}
              className="absolute right-12 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        {!showSearch && (
          <button
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors text-sm"
            aria-label={t('navbar.searchPlaceholder')}
          >
            <Search className="w-4 h-4" />
            <span className="hide-mobile text-xs">{t('navbar.searchPlaceholder')}</span>
            <kbd className="hide-mobile text-[10px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono">⌘K</kbd>
          </button>
        )}
      </div>

      <div className="flex items-center gap-1">
        {/* Language Toggle */}
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
          title={isRtl ? 'Switch to English' : 'التبديل للعربية'}
          aria-label={isRtl ? 'Switch to English' : 'التبديل للعربية'}
        >
          <Globe className="w-4 h-4" />
          <span className="font-medium text-xs">{isRtl ? 'EN' : 'عربي'}</span>
        </button>

        {/* Fullscreen Toggle */}
        <button
          onClick={toggleFullscreen}
          className="p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          aria-label={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>

        {/* Magic Help Inspector */}
        <button
          onClick={() => {
            window.dispatchEvent(new CustomEvent('start-magic-help-inspect'));
          }}
          className="p-2 rounded-lg text-brand-400 hover:bg-brand-500/10 hover:text-brand-300 transition-colors relative"
          title="Magic Help Inspector / فاحص المساعدة الذكي"
        >
          <Sparkles className="w-4 h-4" />
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-brand-500 animate-ping" />
        </button>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors" aria-label={t('navbar.notifications')}>
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-brand-500 rounded-full ring-2 ring-[var(--bg-secondary)]" />
        </button>

        {/* Separator */}
        <div className="w-px h-6 bg-[var(--border-primary)] mx-1" />

        {/* User & Time */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex flex-col items-end">
            <div className="text-xs text-[var(--text-secondary)] font-medium">{t('navbar.welcome')}</div>
            <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
              <Clock className="w-3 h-3" />
              <span>{formatDate()} &middot; {formatTime()}</span>
            </div>
          </div>
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-700 rounded-full flex items-center justify-center shrink-0 shadow-sm shadow-brand-500/20">
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      </div>
    </header>
  )
}
