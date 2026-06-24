import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, FolderPlus, FileText, ShieldCheck,
  HelpCircle, Settings, Activity, Zap, FlaskConical, Bot, Map,
  Layers, Bug, ScrollText, Download, Upload, ArrowRight, Command,
} from 'lucide-react'
import { cn } from '../../utils/helpers'

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

  const commands: Command[] = [
    // Navigation
    { id: 'dashboard', label: 'Open Dashboard', description: 'Go to the main dashboard', icon: LayoutDashboard, shortcut: 'G D', section: 'Navigation', action: () => navigate('/dashboard') },
    { id: 'studies', label: 'Open Studies', description: 'Engineering studies overview', icon: FlaskConical, shortcut: 'G S', section: 'Navigation', action: () => navigate('/studies') },
    { id: 'assistant', label: 'Open AI Assistant', description: 'Chat with AI agents', icon: Bot, shortcut: 'G A', section: 'Navigation', action: () => navigate('/assistant') },
    { id: 'projects', label: 'Open Projects', description: 'Manage projects', icon: FolderPlus, shortcut: 'G P', section: 'Navigation', action: () => navigate('/projects') },
    { id: 'reports', label: 'Open Reports', description: 'View generated reports', icon: FileText, section: 'Navigation', action: () => navigate('/reports') },
    { id: 'settings', label: 'Open Settings', description: 'Application settings', icon: Settings, shortcut: 'G ,', section: 'Navigation', action: () => navigate('/settings') },
    { id: 'diagnostics', label: 'Open Diagnostics', description: 'System health checks', icon: Bug, section: 'Navigation', action: () => navigate('/diagnostics') },
    { id: 'logs', label: 'Open Logs', description: 'Audit log viewer', icon: ScrollText, section: 'Navigation', action: () => navigate('/logs') },

    // Engineering
    { id: 'etap', label: 'ETAP Integration', description: 'Connect to ETAP software', icon: Zap, section: 'Engineering', action: () => navigate('/etap') },
    { id: 'gis', label: 'GIS Integration', description: 'Geographic information system', icon: Map, section: 'Engineering', action: () => navigate('/gis') },
    { id: 'digital-twin', label: 'Digital Twin', description: 'Network digital twin', icon: Layers, section: 'Engineering', action: () => navigate('/digital-twin') },
    { id: 'assets', label: 'Asset Management', description: 'Power system assets', icon: Activity, section: 'Engineering', action: () => navigate('/asset-management') },
    { id: 'code-guard', label: 'Code Guard', description: 'Security code review', icon: ShieldCheck, section: 'Engineering', action: () => navigate('/code-guard') },

    // Actions
    { id: 'import', label: 'Import Data', description: 'Import project data files', icon: Upload, section: 'Actions', action: () => navigate('/data-import') },
    { id: 'export', label: 'Export Data', description: 'Export results and reports', icon: Download, section: 'Actions', action: () => navigate('/data-export') },
    { id: 'help', label: 'Smart Help', description: 'Open the help panel', icon: HelpCircle, shortcut: 'F1', section: 'Actions', action: () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'F1' })) },
    { id: 'status', label: 'Check Backend Status', description: 'Verify API connectivity', icon: Activity, section: 'Actions', action: () => navigate('/diagnostics') },
  ]

  const filtered = query
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase()) ||
        c.section.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  const sections = [...new Set(filtered.map(c => c.section))]

  const executeCommand = useCallback((cmd: Command) => {
    cmd.action()
    setOpen(false)
    setQuery('')
    setSelectedIndex(0)
  }, [])

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

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedIndex(0)
    }
  }, [open])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedIndex(0)
  }, [query])

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
            placeholder="Type a command or search..."
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
              No commands found for "{query}"
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1"><Command className="w-3 h-3" /> K to toggle</span>
          <span>↑↓ navigate</span>
          <span>↵ select</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  )
}
