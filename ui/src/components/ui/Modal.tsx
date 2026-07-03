import { useEffect, type ReactNode, useRef } from 'react'
import { cn } from '../../utils/helpers'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  children: ReactNode
  footer?: ReactNode
  closeOnOverlay?: boolean
}

const sizeStyles = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[90vw]',
}

export function Modal({ open, onClose, title, subtitle, size = 'md', children, footer, closeOnOverlay = true }: ModalProps) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const previouslyOpen = useRef(open)

  useEffect(() => {
    previouslyOpen.current = open
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose()
    }
    globalThis.addEventListener('keydown', handleEsc)
    return () => globalThis.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className={cn(
        'fixed inset-0 z-[var(--z-modal-backdrop)] flex items-center justify-center p-4',
        'transition-all duration-200',
        open ? 'opacity-100' : 'opacity-0 pointer-events-none'
      )}
    >
      {/* Backdrop */}
      <div  // NOSONAR — S6848: non-interactive DOM role; intentional
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={closeOnOverlay ? onClose : undefined}
      />

      {/* Content */}
      <div
        className={cn(
          'relative z-[var(--z-modal)] w-full rounded-xl',
          'bg-[var(--bg-secondary)] border border-[var(--border-primary)]',
          'shadow-[var(--shadow-modal)]',
          'transition-all duration-200',
          sizeStyles[size],
          open ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'
        )}
      >
        {/* Header */}
        {(title || subtitle) && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)]">
            <div>
              {title && <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>}
              {subtitle && <p className="text-sm text-[var(--text-tertiary)] mt-0.5">{subtitle}</p>}
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Body */}
        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-primary)]">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
