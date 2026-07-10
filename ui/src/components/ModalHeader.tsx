/**
 * ModalHeader — shared header for modal dialogs (icon + title + close button).
 *
 * Extracted from ui/src/pages/AssetManagement.tsx and Projects.tsx to
 * eliminate code duplication (SonarCloud new_duplicated_lines_density).
 *
 * Both pages had identical 19-line blocks rendering:
 *   <div className="flex items-start justify-between mb-4">
 *     <div className="flex items-center gap-3">
 *       <div className="p-2 rounded-lg bg-brand-500/10">
 *         <Plus className="w-5 h-5 text-brand-400" />
 *       </div>
 *       <h3 className="text-lg font-semibold text-[var(--text-primary)]">Title</h3>
 *     </div>
 *     <button onClick={close} disabled={submitting} aria-label="Close">
 *       <X className="w-4 h-4" />
 *     </button>
 *   </div>
 */
import { type LucideIcon, Plus, X } from 'lucide-react'

interface ModalHeaderProps {
  readonly title: string
  readonly onClose: () => void
  readonly disabled?: boolean
  readonly icon?: LucideIcon
}

export default function ModalHeader({ title, onClose, disabled = false, icon: Icon = Plus }: ModalHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-brand-500/10">
          <Icon className="w-5 h-5 text-brand-400" />
        </div>
        <h3 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h3>
      </div>
      <button
        type="button"
        onClick={() => !disabled && onClose()}
        disabled={disabled}
        className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-primary)] disabled:opacity-50 transition-colors"
        aria-label="Close"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
