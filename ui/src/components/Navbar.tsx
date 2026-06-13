import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Bell, X, Globe, User, Clock } from 'lucide-react'
import { useAppStore } from '../store'
import { cn } from '../utils/helpers'

export function Navbar() {
  const { t, i18n } = useTranslation()
  const { searchQuery, setSearchQuery } = useAppStore()
  const [showSearch, setShowSearch] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())

  const isRtl = i18n.language === 'ar'

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const toggleLanguage = () => {
    const newLang = i18n.language === 'ar' ? 'en' : 'ar'
    i18n.changeLanguage(newLang)
    document.documentElement.dir = newLang === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = newLang
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
    <header className="flex items-center justify-between px-5 py-3 bg-surface-900/80 backdrop-blur-md border-b border-surface-700/50 shrink-0 z-10">
      <div className="flex items-center gap-3 flex-1">
        {/* Search */}
        <div className={cn(
          'relative transition-all duration-300',
          showSearch ? 'w-64 md:w-80' : 'w-0 overflow-hidden'
        )}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('navbar.searchPlaceholder')}
            className="w-full pl-9 pr-8 py-2 bg-surface-800 border border-surface-600 rounded-lg text-sm text-white placeholder-surface-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition-colors"
            autoFocus={showSearch}
          />
          {showSearch && (
            <button
              onClick={() => { setShowSearch(false); setSearchQuery('') }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-surface-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        {!showSearch && (
          <button
            onClick={() => setShowSearch(true)}
            className="p-2 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-white transition-colors"
            aria-label={t('navbar.searchPlaceholder')}
          >
            <Search className="w-5 h-5" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Language Toggle */}
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-surface-300 hover:bg-surface-800 hover:text-white transition-colors"
          title={isRtl ? 'Switch to English' : 'التبديل للعربية'}
        >
          <Globe className="w-4 h-4" />
          <span className="font-medium">{isRtl ? 'EN' : 'عربي'}</span>
        </button>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-white transition-colors" aria-label={t('navbar.notifications')}>
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-brand-500 rounded-full ring-2 ring-surface-900" />
        </button>

        {/* Separator */}
        <div className="w-px h-6 bg-surface-700 mx-1" />

        {/* User & Time */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex flex-col items-end">
            <div className="text-xs text-surface-300">{t('navbar.welcome')}</div>
            <div className="flex items-center gap-1.5 text-[10px] text-surface-500">
              <Clock className="w-3 h-3" />
              <span>{formatDate()} &middot; {formatTime()}</span>
            </div>
          </div>
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-700 rounded-full flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      </div>
    </header>
  )
}
