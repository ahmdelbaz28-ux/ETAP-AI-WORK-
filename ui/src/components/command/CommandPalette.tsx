import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, FolderPlus, FileText, ShieldCheck,
  HelpCircle, Settings, Activity, Zap, FlaskConical, Bot, Map,
  Layers, Bug, ScrollText, Download, Upload, ArrowRight, Command,
} from 'lucide-react'
import { cn } from '../../utils/helpers'
import { useTranslation } from 'react-i18next'

interface Command {
  id: string
  label: string
  description?: string
  icon: React.ElementType
  shortcut?: string
  section: string
  action: () => void
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'

  // ─── Static commands (always available) ──────────────────────────────
  const staticCommands: Command[] = useMemo(() => [  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    // Navigation
    { id: 'nav-dashboard', label: lang === 'ar' ? 'لوحة التحكم' : 'Dashboard', description: lang === 'ar' ? 'الذهاب للوحة الرئيسية' : 'Go to main dashboard', icon: LayoutDashboard, shortcut: 'G D', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/dashboard') },
    { id: 'nav-studies', label: lang === 'ar' ? 'الدراسات' : 'Studies', description: lang === 'ar' ? 'نظرة عامة على الدراسات' : 'Engineering studies', icon: FlaskConical, shortcut: 'G S', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/studies') },
    { id: 'nav-assistant', label: lang === 'ar' ? 'المساعد الذكي' : 'AI Assistant', description: lang === 'ar' ? 'الدردشة مع الوكلاء' : 'Chat with AI agents', icon: Bot, shortcut: 'G A', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/assistant') },
    { id: 'nav-projects', label: lang === 'ar' ? 'المشاريع' : 'Projects', description: lang === 'ar' ? 'إدارة المشاريع' : 'Manage projects', icon: FolderPlus, shortcut: 'G P', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/projects') },
    { id: 'nav-asset-management', label: lang === 'ar' ? 'إدارة الأصول' : 'Asset Management', description: lang === 'ar' ? 'أصول النظام' : 'Power system assets', icon: Activity, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/asset-management') },
    { id: 'nav-reports', label: lang === 'ar' ? 'التقارير' : 'Reports', description: lang === 'ar' ? 'عرض التقارير' : 'View reports', icon: FileText, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/reports') },
    { id: 'nav-settings', label: lang === 'ar' ? 'الإعدادات' : 'Settings', description: lang === 'ar' ? 'إعدادات التطبيق' : 'App settings', icon: Settings, shortcut: 'G ,', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/settings') },
    { id: 'nav-diagnostics', label: lang === 'ar' ? 'التشخيص' : 'Diagnostics', description: lang === 'ar' ? 'فحوصات النظام' : 'System checks', icon: Bug, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/diagnostics') },
    { id: 'nav-logs', label: lang === 'ar' ? 'السجلات' : 'Logs', description: lang === 'ar' ? 'سجل التدقيق' : 'Audit log', icon: ScrollText, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/logs') },
    { id: 'nav-admin', label: lang === 'ar' ? 'الإدارة' : 'Administration', description: lang === 'ar' ? 'إدارة النظام' : 'System admin', icon: ShieldCheck, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/admin') },

    // Engineering
    { id: 'nav-etap', label: lang === 'ar' ? 'تكامل ETAP' : 'ETAP Integration', icon: Zap, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/etap') },
    { id: 'nav-gis', label: lang === 'ar' ? 'تكامل GIS' : 'GIS Integration', icon: Map, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/gis') },
    { id: 'nav-digital-twin', label: lang === 'ar' ? 'التوأم الرقمي' : 'Digital Twin', icon: Layers, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/digital-twin') },
    { id: 'nav-code-guard', label: lang === 'ar' ? 'حارس الكود' : 'Code Guard', icon: ShieldCheck, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/code-guard') },

    // Actions
    { id: 'act-import', label: lang === 'ar' ? 'استيراد البيانات' : 'Import Data', icon: Upload, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => navigate('/data-import') },
    { id: 'act-export', label: lang === 'ar' ? 'تصدير البيانات' : 'Export Data', icon: Download, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => navigate('/data-export') },
    { id: 'act-help', label: lang === 'ar' ? 'المساعدة الذكية' : 'Smart Help', icon: HelpCircle, shortcut: 'F1', section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => globalThis.dispatchEvent(new CustomEvent('toggle-smart-help')) },
    { id: 'act-magic-help', label: lang === 'ar' ? '✨ فاحص المساعدة' : '✨ Magic Help Inspector', icon: Zap, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => globalThis.dispatchEvent(new CustomEvent('start-magic-help-inspect')) },
  ], [lang, navigate])

  // ─── Filter by query ────────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!query.trim()) return staticCommands
    const q = query.toLowerCase()
    return staticCommands.filter(c => {
      const haystack = `${c.label} ${c.description || ''} ${c.section} ${c.id}`.toLowerCase()
      return haystack.includes(q)
    })
  }, [query, staticCommands])

  const sections = useMemo(() => {
    const set = new Set<string>()
    filtered.forEach(c => set.add(c.section))
    return Array.from(set)
  }, [filtered])

  const executeCommand = useCallback((cmd: Command) => {
    cmd.action()
    setOpen(false)
    setQuery('')
    setSelectedIndex(0)
  }, [])

  // Toggle with Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => !prev)
      }
    }
    globalThis.addEventListener('keydown', handleKeyDown)
    return () => globalThis.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setSelectedIndex(0)
    }
  }, [open])

  // Reset selection on query change
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Keyboard navigation (only when open)
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, Math.max(filtered.length - 1, 0)))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && filtered[selectedIndex]) {
        e.preventDefault()
        executeCommand(filtered[selectedIndex])
      } else if (e.key === 'Escape') {
        e.preventDefault()
        setOpen(false)
        setQuery('')
      }
    }
    globalThis.addEventListener('keydown', handleKeyDown)
    return () => globalThis.removeEventListener('keydown', handleKeyDown)
  }, [open, filtered, selectedIndex, executeCommand])

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const item = listRef.current.querySelector(`[data-index="${selectedIndex}"]`)
      item?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => { setOpen(false); setQuery('') }} />  // NOSONAR — S6848: non-interactive DOM role; intentional

      <div className="relative z-[101] w-full max-w-xl mx-4 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]">
          <Search className="w-5 h-5 text-[var(--text-muted)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={lang === 'ar'
              ? `ابحث في ${filtered.length} عنصر...`
              : `Search ${filtered.length} items...`}
            className="flex-1 bg-transparent text-[var(--text-primary)] text-sm placeholder:text-[var(--text-muted)] outline-none"
          />
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded">
            ESC
          </kbd>
        </div>

        {/* Command List */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
          {filtered.length > 0 ? (
            sections.map(section => {
              const sectionCommands = filtered
                .map((cmd, idx) => ({ cmd, idx }))
                .filter(({ cmd }) => cmd.section === section)
              return (
                <div key={section}>
                  <div className="px-4 py-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    {section}
                  </div>
                  {sectionCommands.map(({ cmd, idx }) => {
                    const isSelected = idx === selectedIndex
                    return (
                      <button
                        key={cmd.id}
                        data-index={idx}
                        onClick={() => executeCommand(cmd)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={cn(
                          'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                          isSelected
                            ? 'bg-[var(--accent-glow)] text-[var(--accent-primary)]'
                            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                        )}
                      >
                        <cmd.icon className={cn('w-4 h-4 shrink-0', isSelected ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]')} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{cmd.label}</div>
                          {cmd.description && (
                            <div className="text-xs text-[var(--text-muted)] truncate">{cmd.description}</div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <div className="flex gap-1">
                            {cmd.shortcut.split(' ').map(k => (
                              <kbd key={k} className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded">
                                {k}
                              </kbd>
                            ))}
                          </div>
                        )}
                        {isSelected && <ArrowRight className="w-3.5 h-3.5 text-[var(--accent-primary)] shrink-0" />}
                      </button>
                    )
                  })}
                </div>
              )
            })
          ) : (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
              {lang === 'ar' ? `لا توجد نتائج لـ "${query}"` : `No results for "${query}"`}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1"><Command className="w-3 h-3" /> K to toggle</span>
          <span>↑↓ navigate</span>
          <span>↵ select</span>
          <span>esc close</span>
          <span className="ml-auto">{filtered.length} commands</span>
        </div>
      </div>
    </div>
  )
}
