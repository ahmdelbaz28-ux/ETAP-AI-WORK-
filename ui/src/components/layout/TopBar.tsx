import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  Search, HelpCircle, Settings, Zap, ChevronDown, Sparkles,
} from 'lucide-react'
import { useAppStore } from '../../store'

interface TopBarProps {
  onHelpOpen?: () => void
}

export function TopBar({ onHelpOpen }: TopBarProps) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { toggleHelpPanel } = useAppStore()

  const handleHelp = () => {
    if (onHelpOpen) onHelpOpen()
    else toggleHelpPanel()
  }

  return (
    <header className="h-12 flex items-center justify-between px-4 bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] shrink-0">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/dashboard')}>
          <div className="w-7 h-7 bg-gradient-to-br from-orange-500 to-red-600 rounded-lg flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-[var(--text-primary)] tracking-tight hidden sm:block">
            Ahmed etap
          </span>
        </div>

        {/* Project context placeholder */}
        <div className="hidden md:flex items-center gap-1.5 ml-3 px-2.5 py-1 rounded-md bg-[var(--bg-primary)] border border-[var(--border-primary)] text-xs text-[var(--text-muted)]">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
          <span>No project loaded</span>
          <ChevronDown className="w-3 h-3" />
        </div>
      </div>

      {/* Center: Search placeholder */}
      <div className="hidden lg:flex items-center flex-1 max-w-md mx-8">
        <div className="flex items-center gap-2 w-full px-3 py-1.5 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)] text-xs text-[var(--text-muted)]">
          <Search className="w-3.5 h-3.5" />
          <span>Search projects, studies, settings...</span>
          <kbd className="ml-auto px-1.5 py-0.5 text-[9px] font-mono bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded">
            Ctrl+K
          </kbd>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        <button
          className="p-2 rounded-lg text-brand-400 hover:bg-brand-500/10 hover:text-brand-300 transition-colors relative"
          title="Magic Help Inspector / فاحص المساعدة الذكي"
          onClick={() => {
            globalThis.dispatchEvent(new CustomEvent('start-magic-help-inspect'));
          }}
        >
          <Sparkles className="w-4 h-4" />
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-brand-500 animate-ping" />
        </button>
        <button
          className="p-2 rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
          title={t('help.title') || 'Help'}
          onClick={handleHelp}
        >
          <HelpCircle className="w-4 h-4" />
        </button>
        <button
          className="p-2 rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors relative"
          title={t('settings.title') || 'Settings'}
          onClick={() => navigate('/settings')}
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
