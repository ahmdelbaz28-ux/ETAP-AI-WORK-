import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function MagicHelpInspector() {
  const { i18n } = useTranslation()
  const lang = (i18n.language === 'ar' ? 'ar' : 'en') as 'en' | 'ar'
  const [isActive, setIsActive] = useState(false)
  const [hoveredRect, setHoveredRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    const startInspect = () => {
      setIsActive(true)
      document.body.style.cursor = 'help'
    }

    window.addEventListener('start-magic-help-inspect', startInspect)
    return () => {
      window.removeEventListener('start-magic-help-inspect', startInspect)
    }
  }, [])

  useEffect(() => {
    if (!isActive) return

    const handleMouseMove = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target) return

      // Find the closest interactive or semantic element
      const interactiveEl = target.closest(
        'button, a, select, input, [data-help-context], .card, [role="button"], h1, h2, h3, h4, li'
      ) as HTMLElement | null

      if (interactiveEl && !interactiveEl.closest('.fixed.z-\\[100\\]') && !interactiveEl.closest('.magic-inspector-overlay')) {
        setHoveredRect(interactiveEl.getBoundingClientRect())
      } else {
        setHoveredRect(null)
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        deactivate()
      }
    }

    const handleClick = (e: MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()

      const target = e.target as HTMLElement
      if (!target) {
        deactivate()
        return
      }

      const interactiveEl = target.closest(
        'button, a, select, input, [data-help-context], .card, [role="button"], h1, h2, h3, h4, li'
      ) as HTMLElement | null

      // 1. Resolve help context ID
      let contextId: string | null = null

      if (interactiveEl) {
        contextId = interactiveEl.getAttribute('data-help-context')
        
        if (!contextId) {
          // Check text content matching
          const text = (interactiveEl.textContent || '').toLowerCase()
          if (text.includes('dashboard') || text.includes('التحكم')) {
            contextId = 'dashboard.overview'
          } else if (text.includes('studies') || text.includes('دراسات') || text.includes('load flow') || text.includes('short circuit') || text.includes('arc flash')) {
            contextId = 'fire-alarm.detector-placement' // falls back to studies
          } else if (text.includes('project') || text.includes('مشروع')) {
            contextId = 'projects.create'
          } else if (text.includes('report') || text.includes('تقرير')) {
            contextId = 'reports.generate'
          } else if (text.includes('twin') || text.includes('توأم')) {
            contextId = 'digital-twin.overview'
          } else if (text.includes('settings') || text.includes('إعدادات')) {
            contextId = 'settings.backend'
          }
        }
      }

      // 2. Fallback based on URL path
      if (!contextId) {
        const path = window.location.hash || window.location.pathname
        if (path.includes('dashboard')) contextId = 'dashboard.overview'
        else if (path.includes('projects')) contextId = 'projects.create'
        else if (path.includes('studies')) contextId = 'fire-alarm.detector-placement'
        else if (path.includes('reports')) contextId = 'reports.generate'
        else if (path.includes('digital-twin')) contextId = 'digital-twin.overview'
        else if (path.includes('settings')) contextId = 'settings.backend'
        else contextId = 'dashboard.overview' // ultimate fallback
      }

      // 3. Open help drawer
      window.dispatchEvent(
        new CustomEvent('open-smart-help', {
          detail: { contextId },
        })
      )

      deactivate()
    }

    const deactivate = () => {
      setIsActive(false)
      setHoveredRect(null)
      document.body.style.cursor = 'default'
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('click', handleClick, true) // capture mode
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('click', handleClick, true)
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.cursor = 'default'
    }
  }, [isActive])

  if (!isActive) return null

  return (
    <>
      {/* Glow Highlight Box Overlay */}
      {hoveredRect && (
        <div
          className="magic-inspector-overlay fixed border-2 border-dashed border-[var(--accent-primary)] bg-[var(--accent-glow)] rounded-lg pointer-events-none transition-all duration-75 ease-out shadow-[0_0_15px_rgba(0,212,255,0.3)]"
          style={{
            top: hoveredRect.top,
            left: hoveredRect.left,
            width: hoveredRect.width,
            height: hoveredRect.height,
            zIndex: 99999,
          }}
        />
      )}

      {/* Floating Instructions Banner at Top */}
      <div
        className="fixed top-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-full bg-[rgba(15,21,37,0.85)] border border-[var(--accent-primary)] shadow-2xl backdrop-blur-md flex items-center gap-3 animate-pulse"
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
      </div>
    </>
  )
}
