import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, FolderPlus, FileText, ShieldCheck,
  HelpCircle, Settings, Activity, Zap, FlaskConical, Bot, Map,
  Layers, Bug, ScrollText, Download, Upload, ArrowRight, Command,
  Code, Database, Plug, FileCode, BookOpen,
} from 'lucide-react'
import { cn } from '../../utils/helpers'
import { useTranslation } from 'react-i18next'

// ─── Types ────────────────────────────────────────────────────────────────────
interface SearchIndexEntry {
  type: 'help-topic' | 'api-route' | 'ui-page' | 'ui-component' | 'python-module'
  id: string
  title: { en: string; ar: string }
  description: { en: string; ar: string }
  tags: string[]
  navigateTo?: string | null
  exports?: string[]
}

interface SearchIndex {
  entries: SearchIndexEntry[]
  total: number
  by_type: Record<string, number>
}

interface Command {
  id: string
  label: string
  description?: string
  icon: React.ElementType
  shortcut?: string
  section: string
  action: () => void
}

// ─── Static icon map by entry type ───────────────────────────────────────────
const ICON_BY_TYPE: Record<SearchIndexEntry['type'], React.ElementType> = {
  'help-topic': BookOpen,
  'api-route': Code,
  'ui-page': LayoutDashboard,
  'ui-component': FileCode,
  'python-module': Database,
}

// Section label by type
const SECTION_BY_TYPE: Record<SearchIndexEntry['type'], string> = {
  'help-topic': '📚 Help Topics',
  'ui-page': '📄 Pages',
  'ui-component': '⚛️ Components',
  'api-route': '🌐 API Endpoints',
  'python-module': '🐍 Python Modules',
}

// ─── Load search index (built by indexer.py) ─────────────────────────────────
let _searchIndex: SearchIndex | null = null
async function loadSearchIndex(): Promise<SearchIndex | null> {
  if (_searchIndex) return _searchIndex
  try {
    // Vite supports importing JSON statically — this gets bundled at build time
    const mod = await import('./search-index-data.json')
    _searchIndex = mod.default as SearchIndex
    return _searchIndex
  } catch {
    // Fallback: try fetching from the help directory
    try {
      const resp = await fetch('./help/search-index.json')
      if (resp.ok) {
        _searchIndex = await resp.json() as SearchIndex
        return _searchIndex
      }
    } catch {
      // ignore
    }
    return null
  }
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [searchIndex, setSearchIndex] = useState<SearchIndex | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'

  // Load search index on mount
  useEffect(() => {
    loadSearchIndex().then(setSearchIndex).catch(() => {})
  }, [])

  // ─── Static commands (always available, even if search index fails) ──────
  const staticCommands: Command[] = useMemo(() => [
    // Navigation
    { id: 'nav-dashboard', label: lang === 'ar' ? 'فتح لوحة التحكم' : 'Open Dashboard', description: lang === 'ar' ? 'الذهاب للوحة الرئيسية' : 'Go to main dashboard', icon: LayoutDashboard, shortcut: 'G D', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/dashboard') },
    { id: 'nav-studies', label: lang === 'ar' ? 'فتح الدراسات' : 'Open Studies', description: lang === 'ar' ? 'نظرة عامة على الدراسات الهندسية' : 'Engineering studies overview', icon: FlaskConical, shortcut: 'G S', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/studies') },
    { id: 'nav-assistant', label: lang === 'ar' ? 'المساعد الذكي' : 'Open AI Assistant', description: lang === 'ar' ? 'الدردشة مع وكلاء الذكاء الاصطناعي' : 'Chat with AI agents', icon: Bot, shortcut: 'G A', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/assistant') },
    { id: 'nav-projects', label: lang === 'ar' ? 'المشاريع' : 'Open Projects', description: lang === 'ar' ? 'إدارة المشاريع' : 'Manage projects', icon: FolderPlus, shortcut: 'G P', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/projects') },
    { id: 'nav-reports', label: lang === 'ar' ? 'التقارير' : 'Open Reports', description: lang === 'ar' ? 'عرض التقارير المُنشأة' : 'View generated reports', icon: FileText, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/reports') },
    { id: 'nav-settings', label: lang === 'ar' ? 'الإعدادات' : 'Open Settings', description: lang === 'ar' ? 'إعدادات التطبيق' : 'Application settings', icon: Settings, shortcut: 'G ,', section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/settings') },
    { id: 'nav-diagnostics', label: lang === 'ar' ? 'التشخيص' : 'Open Diagnostics', description: lang === 'ar' ? 'فحوصات صحة النظام' : 'System health checks', icon: Bug, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/diagnostics') },
    { id: 'nav-logs', label: lang === 'ar' ? 'السجلات' : 'Open Logs', description: lang === 'ar' ? 'عارض سجل التدقيق' : 'Audit log viewer', icon: ScrollText, section: lang === 'ar' ? 'التنقل' : 'Navigation', action: () => navigate('/logs') },

    // Engineering
    { id: 'nav-etap', label: lang === 'ar' ? 'تكامل ETAP' : 'ETAP Integration', description: lang === 'ar' ? 'الاتصال ببرنامج ETAP' : 'Connect to ETAP software', icon: Zap, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/etap') },
    { id: 'nav-gis', label: lang === 'ar' ? 'تكامل GIS' : 'GIS Integration', description: lang === 'ar' ? 'نظام المعلومات الجغرافية' : 'Geographic information system', icon: Map, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/gis') },
    { id: 'nav-digital-twin', label: lang === 'ar' ? 'التوأم الرقمي' : 'Digital Twin', description: lang === 'ar' ? 'توأم رقمي للشبكة' : 'Network digital twin', icon: Layers, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/digital-twin') },
    { id: 'nav-assets', label: lang === 'ar' ? 'إدارة الأصول' : 'Asset Management', description: lang === 'ar' ? 'أصول نظام القدرة' : 'Power system assets', icon: Activity, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/asset-management') },
    { id: 'nav-code-guard', label: lang === 'ar' ? 'حارس الكود' : 'Code Guard', description: lang === 'ar' ? 'مراجعة أمان الكود' : 'Security code review', icon: ShieldCheck, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/code-guard') },
    { id: 'nav-admin', label: lang === 'ar' ? 'الإدارة' : 'Administration', description: lang === 'ar' ? 'إدارة المستخدمين والنظام' : 'User & system management', icon: ShieldCheck, section: lang === 'ar' ? 'الهندسة' : 'Engineering', action: () => navigate('/admin') },

    // Actions
    { id: 'act-import', label: lang === 'ar' ? 'استيراد البيانات' : 'Import Data', description: lang === 'ar' ? 'استيراد ملفات بيانات المشروع' : 'Import project data files', icon: Upload, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => navigate('/data-import') },
    { id: 'act-export', label: lang === 'ar' ? 'تصدير البيانات' : 'Export Data', description: lang === 'ar' ? 'تصدير النتائج والتقارير' : 'Export results and reports', icon: Download, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => navigate('/data-export') },
    { id: 'act-help', label: lang === 'ar' ? 'المساعدة الذكية' : 'Smart Help', description: lang === 'ar' ? 'فتح لوحة المساعدة' : 'Open the help panel', icon: HelpCircle, shortcut: 'F1', section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => window.dispatchEvent(new CustomEvent('toggle-smart-help')) },
    { id: 'act-magic-help', label: lang === 'ar' ? '✨ فاحص المساعدة السحرية' : '✨ Magic Help Inspector', description: lang === 'ar' ? 'اضغط على أي عنصر لرؤية شرحه' : 'Click any element to see its docs', icon: Zap, section: lang === 'ar' ? 'إجراءات' : 'Actions', action: () => window.dispatchEvent(new CustomEvent('start-magic-help-inspect')) },
  ], [lang, navigate])

  // ─── Dynamic commands from search index ─────────────────────────────────
  const dynamicCommands: Command[] = useMemo(() => {
    if (!searchIndex) return []
    return searchIndex.entries.map((entry, idx) => {
      // Determine the action based on the entry type
      let action: () => void
      if (entry.type === 'help-topic') {
        // Open Smart Help drawer with this topic
        action = () => window.dispatchEvent(
          new CustomEvent('open-smart-help', { detail: { contextId: entry.id } })
        )
      } else if (entry.type === 'ui-page' && entry.navigateTo) {
        action = () => navigate(entry.navigateTo!)
      } else if (entry.type === 'api-route') {
        // Open the API file in a new tab (best effort)
        action = () => {
          // For now, just navigate to diagnostics which shows API status
          navigate('/diagnostics')
        }
      } else {
        // ui-component, python-module — no direct navigation; show info via help
        action = () => window.dispatchEvent(
          new CustomEvent('open-smart-help', { detail: { contextId: 'dashboard.overview' } })
        )
      }

      return {
        id: `${entry.type}-${idx}`,
        label: entry.title[lang] || entry.title.en,
        description: entry.description[lang] || entry.description.en,
        icon: ICON_BY_TYPE[entry.type] || HelpCircle,
        section: SECTION_BY_TYPE[entry.type] || 'Other',
        action,
      }
    })
  }, [searchIndex, lang, navigate])

  // ─── Combine static + dynamic, then filter by query ────────────────────
  const allCommands = useMemo(() => [...staticCommands, ...dynamicCommands], [staticCommands, dynamicCommands])

  const filtered = useMemo(() => {
    if (!query.trim()) return allCommands.slice(0, 50) // limit initial display
    const q = query.toLowerCase()
    return allCommands.filter(c => {
      const haystack = (c.label + ' ' + (c.description || '') + ' ' + c.section + ' ' + c.id).toLowerCase()
      // Simple fuzzy: every char of q appears in order
      let qi = 0
      for (let i = 0; i < haystack.length && qi < q.length; i++) {
        if (haystack[i] === q[qi]) qi++
      }
      return qi === q.length || haystack.includes(q)
    }).slice(0, 100)
  }, [query, allCommands])

  const sections = useMemo(() => [...new Set(filtered.map(c => c.section))], [filtered])

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
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      // eslint-disable-next-line react-hooks/set_state-in-effect
      setSelectedIndex(0)
    }
  }, [open])

  // Reset selection on query change
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set_state-in-effect
    setSelectedIndex(0)
  }, [query])

  // Keyboard navigation
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && filtered[selectedIndex]) {
        executeCommand(filtered[selectedIndex])
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, filtered, selectedIndex, executeCommand])

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const item = listRef.current.querySelector(`[data-index="${selectedIndex}"]`)
      item?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  if (!open) return null

  let globalIndex = -1

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />

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
              ? `ابحث في ${allCommands.length} عنصر...`
              : `Search ${allCommands.length} items...`}
            className="flex-1 bg-transparent text-[var(--text-primary)] text-sm placeholder:text-[var(--text-muted)] outline-none"
          />
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded">
            ESC
          </kbd>
        </div>

        {/* Command List */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
          {sections.map(section => (
            <div key={section}>
              <div className="px-4 py-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                {section}
              </div>
              {filtered.filter(c => c.section === section).map(cmd => {
                globalIndex++
                const idx = globalIndex
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
          ))}
          {filtered.length === 0 && (
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
          <span className="ml-auto">
            {searchIndex
              ? `${filtered.length}/${allCommands.length}`
              : 'loading index…'}
          </span>
        </div>
      </div>
    </div>
  )
}
