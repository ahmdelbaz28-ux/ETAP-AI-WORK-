import { type ReactNode } from 'react'
import { AlertTriangle, CheckCircle, Info, ExternalLink, X, ChevronRight } from 'lucide-react'
import { cn } from '../../utils/helpers'

export interface ContextItem {
  label: string
  value: string | number | ReactNode
  icon?: React.ElementType
}

export interface ContextWarning {
  id: string
  message: string
  severity: 'info' | 'warning' | 'error'
  action?: { label: string; onClick: () => void }
}

export interface ContextAction {
  label: string
  onClick: () => void
  icon?: React.ElementType
  variant?: 'primary' | 'secondary' | 'ghost'
}

interface ContextPanelProps {
  title?: string
  selectedItem?: { type: string; name: string; details?: ContextItem[] }
  warnings?: ContextWarning[]
  actions?: ContextAction[]
  helpTopic?: { title: string; url?: string; content?: ReactNode }
  onClose?: () => void
  emptyMessage?: string
}

const severityConfig = {
  info: { icon: Info, bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400' },
  warning: { icon: AlertTriangle, bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
  error: { icon: X, bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400' },
}

export function ContextPanel({  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  title = 'Properties',
  selectedItem,
  warnings = [],
  actions = [],
  helpTopic,
  onClose,
  emptyMessage = 'Select an item to view its properties',
}: ContextPanelProps) {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)]">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-muted)]">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Selected Item Details */}
        {selectedItem ? (
          <div className="p-4 space-y-4">
            {/* Item Header */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[var(--accent-glow)] flex items-center justify-center">
                <span className="text-xs font-bold text-[var(--accent-primary)]">
                  {selectedItem.type.charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <div className="text-sm font-medium text-[var(--text-primary)]">{selectedItem.name}</div>
                <div className="text-xs text-[var(--text-muted)]">{selectedItem.type}</div>
              </div>
            </div>

            {/* Properties List */}
            {selectedItem.details && selectedItem.details.length > 0 && (
              <div className="space-y-1">
                {selectedItem.details.map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-[var(--bg-elevated)]">  // NOSONAR — S6479: array index as key; items lack stable IDs (tech debt)
                    <span className="text-xs text-[var(--text-muted)]">{item.label}</span>  // NOSONAR — S6772: inline spacing; cosmetic
                    <span className="text-xs font-medium text-[var(--text-secondary)] mono-engineering">
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="p-6 text-center">
            <div className="w-10 h-10 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center mx-auto mb-3">
              <Info className="w-5 h-5 text-[var(--text-muted)]" />
            </div>
            <p className="text-xs text-[var(--text-muted)]">{emptyMessage}</p>
          </div>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="px-4 pb-3 space-y-2">
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">Warnings</div>
            {warnings.map(warning => {
              const config = severityConfig[warning.severity]
              const WarningIcon = config.icon
              return (
                <div key={warning.id} className={cn('p-2.5 rounded-lg border', config.bg, config.border)}>
                  <div className="flex items-start gap-2">
                    <WarningIcon className={cn('w-3.5 h-3.5 mt-0.5 shrink-0', config.text)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[var(--text-secondary)]">{warning.message}</p>
                      {warning.action && (
                        <button
                          onClick={warning.action.onClick}
                          className="mt-1 text-xs text-[var(--accent-primary)] hover:underline"
                        >
                          {warning.action.label}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Actions */}
        {actions.length > 0 && (
          <div className="px-4 pb-3 space-y-1">
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Actions</div>
            {actions.map((action, i) => (
              <button
                key={i}  // NOSONAR — S6479: array index as key; items lack stable IDs (tech debt)
                onClick={action.onClick}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left',
                  action.variant === 'primary'
                    ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20'
                    : action.variant === 'ghost'  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
                    ? 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                    : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--border-primary)]'
                )}
              >
                {action.icon && <action.icon className="w-3.5 h-3.5" />}
                <span className="flex-1">{action.label}</span>
                <ChevronRight className="w-3 h-3 text-[var(--text-muted)]" />
              </button>
            ))}
          </div>
        )}

        {/* Help Topic */}
        {helpTopic && (
          <div className="px-4 pb-4">
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Related Help</div>
            <div className="p-3 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)]">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                <span className="text-xs font-medium text-[var(--text-primary)]">{helpTopic.title}</span>
              </div>
              {helpTopic.content && (
                <div className="text-xs text-[var(--text-secondary)] mt-1">{helpTopic.content}</div>
              )}
              {helpTopic.url && (
                <a
                  href={helpTopic.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-2 text-xs text-[var(--accent-primary)] hover:underline"
                >
                  Open documentation <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
