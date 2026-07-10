/**
 * ModalBackdrop — shared modal overlay component.
 *
 * Provides the click-to-close + Escape-to-close backdrop used by all modal
 * dialogs in the app. Extracted to eliminate code duplication (SonarCloud
 * S4144 / new_duplicated_lines_density) and ensure consistent accessibility
 * (role="dialog" + aria-modal + keyboard handler).
 */
import { type ReactNode } from 'react'

interface ModalBackdropProps {
  readonly onClose: () => void
  readonly disabled?: boolean
  readonly children: ReactNode
  readonly className?: string
}

export default function ModalBackdrop({ onClose, disabled = false, children, className = '' }: ModalBackdropProps) {
  return (
    <div
      className={`fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 ${className}`}
      role="dialog"
      aria-modal="true"
      onClick={() => !disabled && onClose()}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && !disabled) {
          onClose()
        }
      }}
    >
      {children}
    </div>
  )
}
