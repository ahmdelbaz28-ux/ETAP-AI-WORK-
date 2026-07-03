import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  X, Search, BookOpen, ChevronRight, ArrowRight,
  Zap, FolderPlus, Radio, FileText, Settings, Activity,
  Layers, Bug, HelpCircle, Sparkles, FileQuestion
} from 'lucide-react'
import { cn } from '../../utils/helpers'
import { useSmartHelp } from '../../hooks/useSmartHelp'
import { resolveContext } from '../../help/contextRegistry'

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

interface DocTreeNode {
  label: { en: string; ar: string }
  topicId?: string
  children?: DocTreeNode[]
}

const docTree: DocTreeNode[] = [
  {
    label: { en: '📚 Getting Started', ar: '📚 مقدمة البداية' },
    children: [
      { label: { en: 'Overview Dashboard', ar: 'نظرة عامة على لوحة التحكم' }, topicId: 'dashboard.overview' },
      { label: { en: 'Keyboard Shortcuts', ar: 'اختصارات لوحة المفاتيح' }, topicId: 'keyboard-shortcuts' },
    ],
  },
  {
    label: { en: '📁 Project Management', ar: '📁 إدارة المشاريع' },
    children: [
      { label: { en: 'Creating a New Project', ar: 'إنشاء مشروع جديد' }, topicId: 'projects.create' },
      { label: { en: 'Managing Projects', ar: 'إدارة وتعديل المشاريع' }, topicId: 'projects.manage' },
    ],
  },
  {
    label: { en: '🚨 Fire Alarm System', ar: '🚨 أنظمة إنذار الحريق' },
    children: [
      { label: { en: 'Detector Placement', ar: 'وضع أجهزة الاستشعار' }, topicId: 'fire-alarm.detector-placement' },
      { label: { en: 'Zone Design & Navigation', ar: 'تصميم وتنقل المناطق' }, topicId: 'fire-alarm.zone-navigation' },
      { label: { en: 'Device Symbol Library', ar: 'مكتبة رموز الأجهزة' }, topicId: 'fire-alarm.symbol-library' },
    ],
  },
  {
    label: { en: '📊 Reports & Documentation', ar: '📊 التقارير والتوثيق' },
    children: [
      { label: { en: 'Generating Reports', ar: 'إنشاء وتصدير التقارير' }, topicId: 'reports.generate' },
    ],
  },
  {
    label: { en: '🔗 System Integration & SCADA', ar: '🔗 تكامل الأنظمة والإسكادا' },
    children: [
      { label: { en: 'ETAP Worker Integration', ar: 'تكامل بيئة عمل إيتاب' }, topicId: 'projects.create' },
      { label: { en: 'SCADA System zenon Integration', ar: 'ربط نظام إسكادا (زينون)' }, topicId: 'integration.scada' },
      { label: { en: 'Digital Twin Overview', ar: 'التوأم الرقمي للمشروع' }, topicId: 'digital-twin.overview' },
    ],
  },
  {
    label: { en: '⚙️ Configuration & Settings', ar: '⚙️ التكوين والإعدادات' },
    children: [
      { label: { en: 'FastAPI Backend Config', ar: 'إعدادات خادم الخدمات الهندسية' }, topicId: 'settings.backend' },
    ],
  },
  {
    label: { en: '🛠️ Troubleshooting', ar: '🛠️ استكشاف الأخطاء وحلها' },
    children: [
      { label: { en: 'Backend Service Offline', ar: 'مشاكل توقف الخادم' }, topicId: 'troubleshooting.backend' },
      { label: { en: 'REST API Error Codes', ar: 'أكواد أخطاء استجابة الـ API' }, topicId: 'troubleshooting.api' },
      { label: { en: 'User Auth & JWT Issues', ar: 'مشاكل مصادقة رموز الدخول' }, topicId: 'troubleshooting.auth' },
    ],
  },
]

function DocTreeViewNode({
  node,
  lang,
  onSelectTopic,
  expandedNodes,
  onToggleNode,
  level = 0
}: {
  node: DocTreeNode
  lang: 'en' | 'ar'
  onSelectTopic: (id: string) => void
  expandedNodes: Set<string>
  onToggleNode: (label: string) => void
  level?: number
}) {
  const isFolder = !!node.children
  const nodeKey = node.label.en
  const isExpanded = expandedNodes.has(nodeKey)

  return (
    <div className="select-none text-left" style={{ marginLeft: `${level * 10}px` }}>
      <div
        onClick={() => {
          if (isFolder) {
            onToggleNode(nodeKey)
          } else if (node.topicId) {
            onSelectTopic(node.topicId)
          }
        }}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-all mt-0.5",
          "hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
          !isFolder && "pl-6 border-l border-transparent hover:border-[var(--accent-primary)]/40"
        )}
      >
        {isFolder ? (
          <span className="text-[9px] text-[var(--text-muted)] font-mono shrink-0 w-3 text-center">
            {isExpanded ? '▼' : '▶'}
          </span>
        ) : (
          <FileQuestion className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
        )}
        <span className="truncate">{node.label[lang]}</span>
      </div>

      {isFolder && isExpanded && node.children && (
        <div className="mt-0.5 border-l border-[var(--border-primary)] ml-3.5 pl-1.5 space-y-0.5">
          {node.children.map((child, idx) => (
            <DocTreeViewNode
              key={idx}
              node={child}
              lang={lang}
              onSelectTopic={onSelectTopic}
              expandedNodes={expandedNodes}
              onToggleNode={onToggleNode}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
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

  const [helpViewMode, setHelpViewMode] = useState<'list' | 'tree'>('tree')
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['📚 Getting Started']))

  const toggleNode = (label: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  useEffect(() => {
    if (open && initialContextId) {
      openContext(initialContextId)
      // Auto expand parent folder in book tree
      const resolvedTopicId = resolveContext(initialContextId)
      if (resolvedTopicId) {
        const parentFolder = docTree.find(folder =>
          folder.children?.some(child => child.topicId === resolvedTopicId)
        )
        if (parentFolder) {
          setExpandedNodes(prev => {
            const next = new Set(prev)
            next.add(parentFolder.label.en)
            return next
          })
        }
      }
    }
  }, [open, initialContextId, openContext])

  useEffect(() => {
    if (open && helpViewMode === 'list') {
      setTimeout(() => searchRef.current?.focus(), 100)
    }
  }, [open, helpViewMode])

  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeTopic) closeTopic()
        else onClose()
      }
    }
    globalThis.addEventListener('keydown', handleEsc)
    return () => globalThis.removeEventListener('keydown', handleEsc)
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
                {lang === 'ar' ? 'المساعدة الذكية (TOC)' : 'Smart Help (TOC)'}
              </h2>
              <p className="text-[10px] text-[var(--text-muted)]">
                {lang === 'ar' ? 'دليل شجرة الفهرس والمستندات' : 'TOC book index & context guide'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                onClose();
                globalThis.dispatchEvent(new CustomEvent('start-magic-help-inspect'));
              }}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-brand-500/10 border border-brand-500/20 text-brand-400 hover:bg-brand-500 hover:text-white transition-all text-[11px] font-medium"
              title={lang === 'ar' ? 'فحص عناصر الصفحة' : 'Inspect page elements'}
            >
              <Sparkles className="w-3 h-3 text-brand-400" />
              <span>{lang === 'ar' ? 'الفحص الذكي' : 'Magic Inspect'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
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
              ← {lang === 'ar' ? 'العودة للفهرس' : 'Back to book index'}
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
          /* Book Index / Search View */
          <>
            {/* View Mode Switcher */}
            <div className="px-5 py-2 border-b border-[var(--border-primary)] flex gap-2">
              <button
                onClick={() => setHelpViewMode('tree')}
                className={cn(
                  'flex-1 py-1.5 text-xs font-semibold rounded-lg border text-center transition-all',
                  helpViewMode === 'tree'
                    ? 'bg-brand-500/10 text-brand-400 border-brand-500/25'
                    : 'bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text-primary)]'
                )}
              >
                🗂️ {lang === 'ar' ? 'كتاب الفهرس (Tree)' : 'Book Manual (Tree)'}
              </button>
              <button
                onClick={() => setHelpViewMode('list')}
                className={cn(
                  'flex-1 py-1.5 text-xs font-semibold rounded-lg border text-center transition-all',
                  helpViewMode === 'list'
                    ? 'bg-brand-500/10 text-brand-400 border-brand-500/25'
                    : 'bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text-primary)]'
                )}
              >
                🔎 {lang === 'ar' ? 'بحث سريع' : 'Quick Search'}
              </button>
            </div>

            {helpViewMode === 'tree' ? (
              /* ETAP-style Documentation Tree view */
              <div className="flex-1 overflow-y-auto p-4 space-y-1.5">
                {docTree.map((node, idx) => (
                  <DocTreeViewNode
                    key={idx}
                    node={node}
                    lang={lang}
                    onSelectTopic={(id) => openTopic(id)}
                    expandedNodes={expandedNodes}
                    onToggleNode={toggleNode}
                  />
                ))}
              </div>
            ) : (
              /* Standard Search & List View */
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
              </>
            )}

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
