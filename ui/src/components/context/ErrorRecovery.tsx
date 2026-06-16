import { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, X, ExternalLink, RefreshCw, HelpCircle, ChevronRight } from 'lucide-react'
import { cn } from '../../utils/helpers'

interface ErrorInfo {
  id: string
  message: string
  code?: number
  timestamp: number
}

interface HelpMapping {
  topic: string
  title: string
  description: string
  url?: string
  actions?: { label: string; action: string }[]
}

const ERROR_HELP_MAP: Record<string, HelpMapping> = {
  'backend_unavailable': {
    topic: 'troubleshooting.backend',
    title: 'Backend Service Unavailable',
    description: 'The engineering service is not responding. This usually means the Python backend is not running or the connection was refused.',
    url: 'https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-#quick-start',
    actions: [
      { label: 'Check Backend Status', action: 'check_status' },
      { label: 'Restart Service', action: 'restart_service' },
    ],
  },
  'auth_failed': {
    topic: 'troubleshooting.auth',
    title: 'Authentication Failed',
    description: 'Your credentials were rejected. Your session may have expired or the API key is invalid.',
    actions: [
      { label: 'Refresh Token', action: 'refresh_token' },
      { label: 'Check API Key', action: 'check_api_key' },
    ],
  },
  'project_not_found': {
    topic: 'projects.troubleshooting',
    title: 'Project Not Found',
    description: 'The requested project does not exist or has been deleted. It may have been removed by another user.',
    actions: [
      { label: 'Browse Projects', action: 'browse_projects' },
      { label: 'Create New Project', action: 'create_project' },
    ],
  },
  'report_generation_failed': {
    topic: 'reports.troubleshooting',
    title: 'Report Generation Failed',
    description: 'The report could not be generated. This may be due to missing study results or a template error.',
    actions: [
      { label: 'Run Study First', action: 'run_study' },
      { label: 'Check Templates', action: 'check_templates' },
    ],
  },
  'study_failed': {
    topic: 'studies.troubleshooting',
    title: 'Study Execution Failed',
    description: 'The engineering study did not complete successfully. Check your input parameters and try again.',
    actions: [
      { label: 'Validate Input', action: 'validate_input' },
      { label: 'Try Different Parameters', action: 'retry_study' },
    ],
  },
  'network_error': {
    topic: 'troubleshooting.network',
    title: 'Network Error',
    description: 'A network error occurred while communicating with the server. Check your internet connection.',
    actions: [
      { label: 'Retry Request', action: 'retry' },
      { label: 'Check Connectivity', action: 'check_connectivity' },
    ],
  },
  'rate_limited': {
    topic: 'troubleshooting.rate_limit',
    title: 'Rate Limit Exceeded',
    description: 'Too many requests were sent in a short period. Wait a moment before trying again.',
    actions: [
      { label: 'Wait and Retry', action: 'wait_retry' },
    ],
  },
  'validation_error': {
    topic: 'input.validation',
    title: 'Input Validation Error',
    description: 'The data you provided does not meet the required format. Check the fields and try again.',
    actions: [
      { label: 'Review Input', action: 'review_input' },
    ],
  },
}

function mapErrorToHelp(error: Error | string): HelpMapping {
  const message = typeof error === 'string' ? error : error.message
  const lower = message.toLowerCase()

  if (lower.includes('fetch') || lower.includes('network') || lower.includes('econnrefused') || lower.includes('failed to fetch')) {
    return ERROR_HELP_MAP['backend_unavailable']
  }
  if (lower.includes('401') || lower.includes('unauthorized') || lower.includes('token')) {
    return ERROR_HELP_MAP['auth_failed']
  }
  if (lower.includes('404') || lower.includes('not found')) {
    return ERROR_HELP_MAP['project_not_found']
  }
  if (lower.includes('report')) {
    return ERROR_HELP_MAP['report_generation_failed']
  }
  if (lower.includes('study') || lower.includes('engine')) {
    return ERROR_HELP_MAP['study_failed']
  }
  if (lower.includes('429') || lower.includes('rate limit')) {
    return ERROR_HELP_MAP['rate_limited']
  }
  if (lower.includes('valid')) {
    return ERROR_HELP_MAP['validation_error']
  }

  return ERROR_HELP_MAP['network_error']
}

interface ErrorRecoveryProps {
  error: Error | string | null
  onDismiss: () => void
  onRetry?: () => void
}

export function ErrorRecovery({ error, onDismiss, onRetry }: ErrorRecoveryProps) {
  const [help, setHelp] = useState<HelpMapping | null>(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (error) {
      setHelp(mapErrorToHelp(error))
      setExpanded(true)
    } else {
      setHelp(null)
      setExpanded(false)
    }
  }, [error])

  const handleAction = useCallback((action: string) => {
    switch (action) {
      case 'check_status':
      case 'check_api_key':
      case 'check_connectivity':
        window.location.hash = '/diagnostics'
        break
      case 'browse_projects':
        window.location.hash = '/projects'
        break
      case 'create_project':
        window.location.hash = '/projects'
        break
      case 'run_study':
        window.location.hash = '/studies'
        break
      case 'retry':
      case 'retry_study':
      case 'wait_retry':
        onRetry?.()
        break
      default:
        break
    }
    onDismiss()
  }, [onRetry, onDismiss])

  if (!error || !help) return null

  return (
    <div className={cn(
      'fixed bottom-4 right-4 z-[90] w-96 max-w-[calc(100vw-2rem)]',
      'bg-[var(--bg-secondary)] border border-red-500/30 rounded-xl shadow-xl shadow-red-500/10',
      'transition-all duration-300',
      expanded ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0 pointer-events-none'
    )}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]">
        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0">
          <AlertTriangle className="w-4 h-4 text-red-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[var(--text-primary)]">{help.title}</div>
          <div className="text-xs text-[var(--text-muted)]">{help.topic}</div>
        </div>
        <button onClick={onDismiss} className="p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-muted)]">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Body */}
      <div className="px-4 py-3">
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{help.description}</p>
      </div>

      {/* Actions */}
      <div className="px-4 pb-3 flex gap-2">
        {onRetry && (
          <button
            onClick={() => { onRetry(); onDismiss() }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] rounded-lg hover:bg-[var(--accent-primary)]/20 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
        {help.actions?.map((a, i) => (
          <button
            key={i}
            onClick={() => handleAction(a.action)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-[var(--bg-elevated)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--border-primary)] transition-colors"
          >
            {a.label}
          </button>
        ))}
        {help.url && (
          <a
            href={help.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            Help
          </a>
        )}
      </div>
    </div>
  )
}

// Global error handler hook
export function useErrorRecovery() {
  const [error, setError] = useState<Error | string | null>(null)

  const reportError = useCallback((err: Error | string) => {
    setError(err)
  }, [])

  const dismissError = useCallback(() => {
    setError(null)
  }, [])

  return { error, reportError, dismissError }
}
