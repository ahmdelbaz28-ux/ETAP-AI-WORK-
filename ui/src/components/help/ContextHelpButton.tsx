import { HelpCircle } from 'lucide-react'
import { cn } from '../../utils/helpers'

interface ContextHelpButtonProps {
  contextId: string
  onClick: (contextId: string) => void
  size?: 'sm' | 'md'
  className?: string
  label?: string
}

export function ContextHelpButton({ contextId, onClick, size = 'sm', className, label }: ContextHelpButtonProps) {
  const sizeClasses = {
    sm: 'w-5 h-5',
    md: 'w-6 h-6',
  }

  return (
    <button
      onClick={() => onClick(contextId)}
      data-help-context={contextId}
      className={cn(
        'inline-flex items-center justify-center rounded-md transition-colors',
        'text-[var(--text-muted)] hover:text-[var(--accent-primary)] hover:bg-[var(--accent-glow)]',
        size === 'sm' ? 'p-1' : 'p-1.5',
        className
      )}
      title={`Help: ${contextId}`}
    >
      <HelpCircle className={sizeClasses[size]} />
      {label && <span className="ml-1 text-xs">{label}</span>}
    </button>
  )
}
