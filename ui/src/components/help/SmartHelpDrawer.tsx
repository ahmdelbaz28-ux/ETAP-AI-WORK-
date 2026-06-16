import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  X, Search, BookOpen, ChevronRight, ArrowRight, ExternalLink,
  Zap, FolderPlus, Radio, FileText, ShieldCheck, Settings, Activity,
  Layers, Bug, HelpCircle,
} from 'lucide-react'
import { cn } from '../../utils/helpers'
import { useSmartHelp } from '../../hooks/useSmartHelp'
import type { HelpCategory } from '../../help/types'

const categoryIcons: Record<string, React.ElementType> = {
  'getting-started': Zap,
  'projects': FolderPlus,
  'fire-alarm': Radio,
  'engineering': Activity,
  'reports': FileText,
  'digital-twin': Layers,
  'settings': Settings,
  'troubleshooting': Bug,
  'keyboard-shortcuts': BookOpen,
}

interface SmartHelpDrawerProps {
  open: boolean
  onClose: () => void
  initialContextId?: string
}

export function SmartHelpDrawer({ open, onClose, initialContextId }: SmartHelpDrawerProps) {
  const { i18n } = useTranslation()
  const navigate = useNavigate()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'
  const searchRef = useRef<HTMLInputElement>(null)
  const {
    categories,
    activeTopic,
    searchQuery,
    selectedCategory,
    setSearchQuery,
    setSelectedCategory,
    openTopic,
    openContext,
    closeTopic,
    filteredTopics,
  } = useSmartHelp()

  useEffect(() => {
    if (open && initialContextId) {
      openContext(initialContextId)
    }
  }, [open, initialContextId, openContext])

  useEffect(() => {
    if (open) {
      setTimeout(() => searchRef.current?.focus(), 100)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeTopic) closeTopic()
        else onClose()
      }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [open, activeTopic, onClose, closeTopic])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className={cn(
        'relative z-[101] w-full max-w-lg h-full',
        'bg-[var(--bg-secondary)] border-l border-[var(--border-primary)]',
        'shadow-2xl shadow-black/30',
        'flex flex-col',
        'animate-slide-in'
      )}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-primary)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--accent-glow)] flex items-center justify-center">
              <HelpCircle className="w-4 h-4 text-[var(--accent-primary)]" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                {lang === 'ar' ? 'المساعدة الذكية' : 'Smart Help'}
              </h2>
              <p className="text-[10px] text-[var(--text-muted)]">
                {lang === 'ar' ? 'دليل سياقي ذكي' : 'Context-aware intelligent guide'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Area */}
        {activeTopic ? (
          /* Topic Detail View */
          <div className="flex-1 overflow-y-auto">
            {/* Back button */}
            <button
              onClick={closeTopic}
              className="flex items-center gap-1.5 px-5 py-3 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
            >
              ← {lang === 'ar' ? 'العودة' : 'Back to topics'}
            </button>

            {/* Topic header */}
            <div className="px-5 pb-4">
              <div className="flex items-center gap-2 mb-2">
                {(() => {
                  const Icon = categoryIcons[activeTopic.category] || BookOpen
                  return <Icon className="w-5 h-5 text-[var(--accent-primary)]" />
                })()}
                <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                  {activeTopic.title[lang]}
                </h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">
                {activeTopic.description[lang]}
              </p>
            </div>

            {/* Content */}
            <div className="px-5 pb-4">
              <div className="prose prose-sm max-w-none text-[var(--text-secondary)]">
                {activeTopic.content[lang].split('\n').map((line, i) => {
                  if (line.startsWith('**') && line.endsWith('**')) {
                    return <h4 key={i} className="text-sm font-semibold text-[var(--text-primary)] mt-4 mb-2">{line.replace(/\*\*/g, '')}</h4>
                  }
                  if (line.startsWith('- ')) {
                    return <li key={i} className="text-xs ml-4 mb-1">{line.substring(2)}</li>
                  }
                  if (line.startsWith('```')) return null
                  if (line.trim() === '') return <div key={i} className="h-2" />
                  return <p key={i} className="text-xs leading-relaxed mb-2">{line}</p>
                })}
              </div>
            </div>

            {/* Actions */}
            <div className="px-5 pb-4 space-y-2">
              {activeTopic.navigateTo && (
                <button
                  onClick={() => {
                    navigate(activeTopic.navigateTo!)
                    onClose()
                  }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] rounded-lg hover:bg-[var(--accent-primary)]/20 transition-colors"
                >
                  <ArrowRight className="w-4 h-4" />
                  {lang === 'ar' ? 'فتح الصفحة ذات الصلة' : 'Open related page'}
                </button>
              )}
            </div>

            {/* Related Topics */}
            {activeTopic.relatedTopics && activeTopic.relatedTopics.length > 0 && (
              <div className="px-5 pb-5 border-t border-[var(--border-primary)] pt-4">
                <h4 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                  {lang === 'ar' ? 'مواضيع ذات صلة' : 'Related Topics'}
                </h4>
                <div className="space-y-1">
                  {activeTopic.relatedTopics.map(rid => {
                    const related = filteredTopics.find(t => t.id === rid) ?? null
                    if (!related) return null
                    return (
                      <button
                        key={rid}
                        onClick={() => openTopic(rid)}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] rounded-lg transition-colors text-left"
                      >
                        <ChevronRight className="w-3 h-3 text-[var(--text-muted)]" />
                        {related.title[lang]}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Topic List View */
          <>
            {/* Search */}
            <div className="px-5 py-3 border-b border-[var(--border-primary)]">
              <div className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <Search className="w-4 h-4 text-[var(--text-muted)]" />
                <input
                  ref={searchRef}
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={lang === 'ar' ? 'البحث في المواضيع...' : 'Search topics...'}
                  className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
                />
              </div>
            </div>

            {/* Category Tabs */}
            <div className="px-5 py-2 border-b border-[var(--border-primary)] flex gap-1 overflow-x-auto">
              {categories.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={cn(
                    'px-2.5 py-1 text-[11px] font-medium rounded-md whitespace-nowrap transition-colors',
                    selectedCategory === cat.id
                      ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]'
                      : 'text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)]'
                  )}
                >
                  {cat.label[lang]}
                </button>
              ))}
            </div>

            {/* Topic List */}
            <div className="flex-1 overflow-y-auto py-2">
              {filteredTopics.length === 0 ? (
                <div className="px-5 py-12 text-center">
                  <HelpCircle className="w-10 h-10 text-[var(--text-muted)] mx-auto mb-3" />
                  <p className="text-sm text-[var(--text-muted)]">
                    {lang === 'ar' ? 'لم يتم العثور على مواضيع' : 'No topics found'}
                  </p>
                </div>
              ) : (
                <div className="space-y-0.5">
                  {filteredTopics.map(topic => {
                    const Icon = categoryIcons[topic.category] || BookOpen
                    return (
                      <button
                        key={topic.id}
                        onClick={() => openTopic(topic.id)}
                        className="w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-[var(--bg-elevated)] transition-colors group"
                      >
                        <div className="w-7 h-7 rounded-md bg-[var(--bg-elevated)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent-glow)]">
                          <Icon className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-[var(--text-primary)] truncate">
                            {topic.title[lang]}
                          </div>
                          <div className="text-[10px] text-[var(--text-muted)] truncate">
                            {topic.description[lang]}
                          </div>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]">
              {lang === 'ar'
                ? `${filteredTopics.length} مواضيع · F1 للمساعدة`
                : `${filteredTopics.length} topics · F1 for help`}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
