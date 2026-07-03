import type { ReactNode } from 'react'
import { cn } from '../../utils/helpers'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 text-center', className)}>
      {icon && <div className="mb-4 text-[var(--text-muted)] opacity-50">{icon}</div>}
      <h3 className="text-base font-medium text-[var(--text-secondary)]">{title}</h3>
      {description && <p className="text-sm text-[var(--text-tertiary)] mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
