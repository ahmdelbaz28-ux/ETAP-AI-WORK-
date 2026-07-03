import { useEffect, useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { resolveContext } from '../../help/contextRegistry'

/**
 * MagicHelpInspector
 *
 * When activated (via the ✨ Sparkles button in the navbar, or via the
 * "Magic Inspect" button inside the Smart Help drawer), the inspector:
 *
 * 1. Changes the cursor to a help cursor
 * 2. Highlights any interactive element under the mouse with a dashed cyan border
 * 3. Listens for a click — but in CAPTURE mode and with preventDefault so the
 *    underlying button/link does NOT fire its normal action
 * 4. Resolves the clicked element's `data-help-context` attribute (or falls
 *    back to text/path heuristics) to a topic ID
 * 5. Dispatches an `open-smart-help` CustomEvent with that contextId
 * 6. Deactivates itself
 *
 * The user can press Esc at any time to exit inspector mode without clicking.
 */
export function MagicHelpInspector() {
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'
  const [isActive, setIsActive] = useState(false)
  const [hoveredRect, setHoveredRect] = useState<DOMRect | null>(null)
  const [hoveredLabel, setHoveredLabel] = useState<string>('')

  useEffect(() => {
    const startInspect = () => {
      setIsActive(true)
      document.body.style.cursor = 'help'
    }

    globalThis.addEventListener('start-magic-help-inspect', startInspect)
    return () => {
      globalThis.removeEventListener('start-magic-help-inspect', startInspect)
    }
  }, [])

  useEffect(() => {
    if (!isActive) return

    const handleMouseMove = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target) return

      // Find the closest interactive or semantic element. Prefer elements
      // with `data-help-context` attribute (these are guaranteed to have docs).
      const interactiveEl = target.closest(
        '[data-help-context], button, a, select, input, textarea, .card, [role="button"], h1, h2, h3, h4, li, label'
      ) as HTMLElement | null

      if (
        interactiveEl &&
        !interactiveEl.closest(String.raw`.fixed.z-\[100\]`) &&
        !interactiveEl.closest('.magic-inspector-overlay') &&
        !interactiveEl.closest('.magic-inspector-banner')
      ) {
        setHoveredRect(interactiveEl.getBoundingClientRect())
        // Build a label for the floating tooltip
        const ctx = interactiveEl.dataset.helpContext ?? null
        const text = (interactiveEl.textContent || '').trim().slice(0, 40)
        const tag = interactiveEl.tagName.toLowerCase()
        setHoveredLabel(ctx ? `📋 ${ctx}` : `🔍 <${tag}> "${text}"`)
      } else {
        setHoveredRect(null)
        setHoveredLabel('')
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        deactivate()
      }
    }

    const handleClick = (e: MouseEvent) => {  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
      // ALWAYS prevent the default action and stop propagation — we want
      // the click to be interpreted as "show me docs for this element",
      // not as a normal button press.
      e.preventDefault()
      e.stopPropagation()

      const target = e.target as HTMLElement
      if (!target) {
        deactivate()
        return
      }

      const interactiveEl = target.closest(
        '[data-help-context], button, a, select, input, textarea, .card, [role="button"], h1, h2, h3, h4, li, label'
      ) as HTMLElement | null

      // 1. Try the explicit `data-help-context` attribute (preferred path)
      let contextId: string | null = null

      if (interactiveEl) {
        contextId = interactiveEl.dataset.helpContext ?? null

        // 2. Walk up the DOM tree looking for a data-help-context on an ancestor
        if (!contextId) {
          let parent: HTMLElement | null = interactiveEl.parentElement
          let depth = 0
          while (parent && depth < 5) {
            const attr = parent.dataset.helpContext
            if (attr) {
              contextId = attr
              break
            }
            parent = parent.parentElement
            depth++
          }
        }

        // 3. Text-content heuristics (fallback when no data-help-context)
        if (!contextId) {
          const text = (interactiveEl.textContent || '').toLowerCase()
          if (text.includes('dashboard') || text.includes('لوحة التحكم') || text.includes('التحكم')) {
            contextId = 'dashboard.overview'
          } else if (text.includes('load flow') || text.includes('تدفق الحمل')) {
            contextId = 'studies.load-flow'
          } else if (text.includes('short circuit') || text.includes('دائرة قصيرة') || text.includes('قصر')) {
            contextId = 'studies.short-circuit'
          } else if (text.includes('arc flash') || text.includes('شرارة') || text.includes('قوس')) {
            contextId = 'studies.arc-flash'
          } else if (text.includes('studies') || text.includes('دراسات')) {
            contextId = 'studies.overview'
          } else if (text.includes('project') || text.includes('مشروع')) {
            contextId = 'projects.create'
          } else if (text.includes('report') || text.includes('تقرير')) {
            contextId = 'reports.generate'
          } else if (text.includes('twin') || text.includes('توأم')) {
            contextId = 'digital-twin.overview'
          } else if (text.includes('settings') || text.includes('إعدادات')) {
            contextId = 'settings.backend'
          } else if (text.includes('assistant') || text.includes('مساعد') || text.includes('ذكاء')) {
            contextId = 'ai-assistant.overview'
          } else if (text.includes('asset') || text.includes('أصول') || text.includes('أصل')) {
            contextId = 'asset-management.overview'
          } else if (text.includes('etap') || text.includes('إيتاب')) {
            contextId = 'etap-integration.overview'
          } else if (text.includes('gis') || text.includes('جغرافي')) {
            contextId = 'gis-integration.overview'
          } else if (text.includes('code') || text.includes('كود') || text.includes('حارس')) {
            contextId = 'code-guard.overview'
          } else if (text.includes('admin') || text.includes('إدارة') || text.includes('مسؤول')) {
            contextId = 'administration.overview'
          } else if (text.includes('diagnostic') || text.includes('تشخيص')) {
            contextId = 'diagnostics.overview'
          } else if (text.includes('logs') || text.includes('سجلات')) {
            contextId = 'logs.overview'
          } else if (text.includes('import') || text.includes('استيراد')) {
            contextId = 'data-import.overview'
          } else if (text.includes('export') || text.includes('تصدير')) {
            contextId = 'data-export.overview'
          } else if (text.includes('test') || text.includes('اختبار') || text.includes('اتصال')) {
            contextId = 'settings.external-services'
          }
        }
      }

      // 4. URL-path fallback (ultimate fallback)
      if (!contextId) {
        const path = globalThis.location.hash || globalThis.location.pathname
        if (path.includes('dashboard')) contextId = 'dashboard.overview'
        else if (path.includes('projects')) contextId = 'projects.create'
        else if (path.includes('studies')) contextId = 'studies.overview'
        else if (path.includes('assistant')) contextId = 'ai-assistant.overview'
        else if (path.includes('asset')) contextId = 'asset-management.overview'
        else if (path.includes('etap')) contextId = 'etap-integration.overview'
        else if (path.includes('gis')) contextId = 'gis-integration.overview'
        else if (path.includes('reports')) contextId = 'reports.generate'
        else if (path.includes('digital-twin')) contextId = 'digital-twin.overview'
        else if (path.includes('settings')) contextId = 'settings.backend'
        else if (path.includes('code-guard')) contextId = 'code-guard.overview'
        else if (path.includes('data-import')) contextId = 'data-import.overview'
        else if (path.includes('data-export')) contextId = 'data-export.overview'
        else if (path.includes('admin')) contextId = 'administration.overview'
        else if (path.includes('diagnostics')) contextId = 'diagnostics.overview'
        else if (path.includes('logs')) contextId = 'logs.overview'
        else contextId = 'dashboard.overview' // ultimate fallback
      }

      // 5. Validate the contextId resolves to an actual topic
      // (if not, the SmartHelpDrawer will show the dashboard default)
      const resolvedTopicId = resolveContext(contextId)
      if (!resolvedTopicId) {
        // contextId is not in registry — log a warning so devs can fix it
        console.warn(
          `[MagicHelpInspector] contextId "${contextId}" is not in the contextRegistry. ` +
          `Falling back to dashboard.overview. Add an entry to contextRegistry.ts to fix.`
        )
      }

      // 6. Open the help drawer with this context
      globalThis.dispatchEvent(
        new CustomEvent('open-smart-help', {
          detail: { contextId },
        })
      )

      deactivate()
    }

    const deactivate = () => {
      setIsActive(false)
      setHoveredRect(null)
      setHoveredLabel('')
      document.body.style.cursor = 'default'
    }

    globalThis.addEventListener('mousemove', handleMouseMove)
    // capture: true so we catch the event before any button's onClick fires
    globalThis.addEventListener('click', handleClick, true)
    globalThis.addEventListener('keydown', handleKeyDown)

    return () => {
      globalThis.removeEventListener('mousemove', handleMouseMove)
      globalThis.removeEventListener('click', handleClick, true)
      globalThis.removeEventListener('keydown', handleKeyDown)
      document.body.style.cursor = 'default'
    }
  }, [isActive])

  if (!isActive) return null

  return (
    <>
      {/* Glow Highlight Box Overlay */}
      {hoveredRect && (
        <div
          className="magic-inspector-overlay fixed border-2 border-dashed border-[var(--accent-primary)] bg-[var(--accent-glow)] rounded-lg pointer-events-none transition-all duration-75 ease-out shadow-[0_0_15px_rgba(0,212,255,0.4)]"
          style={{
            top: hoveredRect.top - 2,
            left: hoveredRect.left - 2,
            width: hoveredRect.width + 4,
            height: hoveredRect.height + 4,
            zIndex: 99999,
          }}
        />
      )}

      {/* Floating tooltip next to the cursor showing what will be selected */}
      {hoveredRect && hoveredLabel && (
        <div
          className="magic-inspector-banner fixed px-2.5 py-1 rounded-md bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] text-[10px] text-[var(--text-primary)] font-mono pointer-events-none"
          style={{
            top: hoveredRect.bottom + 6,
            left: hoveredRect.left,
            zIndex: 99999,
            maxWidth: '300px',
          }}
        >
          {hoveredLabel}
        </div>
      )}

      {/* Floating Instructions Banner at Top */}
      <div
        className="magic-inspector-banner fixed top-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-full bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] shadow-2xl backdrop-blur-md flex items-center gap-3"
        style={{ zIndex: 100000 }}
      >
        <div className="w-6 h-6 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center animate-pulse">
          <Sparkles className="w-3.5 h-3.5 text-brand-400" />
        </div>
        <div className="text-xs font-medium text-[var(--text-primary)]">
          {lang === 'ar' ? (
            <span>
              ✨ <strong>وضع فحص المساعدة نشط</strong> — اضغط على أي عنصر أو بطاقة في الصفحة لشرح كيفية عملها. اضغط <strong>ESC</strong> للخروج.
            </span>
          ) : (
            <span>
              ✨ <strong>Help Inspector Active</strong> — Click any element or card on the screen to see how it works. Press <strong>ESC</strong> to exit.
            </span>
          )}
        </div>
        <button
          onClick={() => setIsActive(false)}
          className="ml-2 p-1 rounded hover:bg-white/10 transition-colors"
          title={lang === 'ar' ? 'إغلاق' : 'Close'}
        >
          <X className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        </button>
      </div>
    </>
  )
}
