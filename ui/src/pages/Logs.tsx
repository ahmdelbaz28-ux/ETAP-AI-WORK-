import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, Filter, Terminal, AlertTriangle, Info, XCircle, Clock } from 'lucide-react'
import { fetchMetrics, fetchAuditLogs, type MetricsResponse, type AuditEntry } from '../lib/api'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Badge, Button, EmptyState } from '../components/ui'
import { cn } from '../utils/helpers'

interface LogEntry {
  timestamp: string
  level: 'info' | 'warn' | 'error'
  source: string
  message: string
}

function auditToLogs(metrics: MetricsResponse | null, audit: AuditEntry[]): LogEntry[] {
  const logs: LogEntry[] = []
  if (metrics) {
    const apiEntries = metrics.api as Record<string, number>
    logs.push({ timestamp: new Date().toLocaleTimeString(), level: 'info', source: 'metrics', message: `API requests: ${Object.values(apiEntries).reduce((a: number, b: number) => a + b, 0)} total` })
    const providerEntries = metrics.providers as Record<string, { count: number; avgMs: number; failureRate: number }>
    for (const [name, p] of Object.entries(providerEntries)) {
      logs.push({ timestamp: new Date().toLocaleTimeString(), level: 'info', source: 'provider', message: `${name}: ${p.count} calls, avg ${p.avgMs}ms, ${(p.failureRate * 100).toFixed(1)}% failures` })
    }
    const circuitEntries = metrics.circuits as Record<string, { state: string; consecutiveFailures: number }>
    for (const [name, c] of Object.entries(circuitEntries)) {
      if (c.state !== 'closed') logs.push({ timestamp: new Date().toLocaleTimeString(), level: 'warn', source: 'circuit', message: `Breaker ${name}: ${c.state} (${c.consecutiveFailures} failures)` })
    }
  }
  for (const entry of audit.slice(0, 50)) {
    const t = new Date(entry.timestamp)
    logs.push({
      timestamp: t.toLocaleTimeString(),
      level: entry.statusCode >= 400 ? 'error' : entry.statusCode >= 300 ? 'warn' : 'info',
      source: 'audit',
      message: `${entry.method} ${entry.path} ${entry.statusCode} — ${entry.action}${entry.latencyMs ? ` (${entry.latencyMs}ms)` : ''}`,
    })
  }
  return logs.length ? logs : [{ timestamp: '--', level: 'info' as const, source: 'system', message: 'No log data available. Run a study or chat to generate activity.' }]
}

const levelConfig = {
  info: {
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/5',
    borderColor: 'border-blue-500/20',
    icon: <Info className="w-3 h-3" />,
  },
  warn: {
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/5',
    borderColor: 'border-amber-500/20',
    icon: <AlertTriangle className="w-3 h-3" />,
  },
  error: {
    color: 'text-red-400',
    bgColor: 'bg-red-500/5',
    borderColor: 'border-red-500/20',
    icon: <XCircle className="w-3 h-3" />,
  },
}

export function Logs() {
  const [filter, setFilter] = useState<string>('all')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const { notify } = useNotify()

  const loadLogs = async () => {
    setLoading(true)
    try {
      const [metrics, audit] = await Promise.all([fetchMetrics().catch(() => null), fetchAuditLogs().catch(() => [])])
      setLogs(auditToLogs(metrics, audit))
    } catch {
      notify('error', 'Failed to load logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadLogs() }, [])

  const filtered = filter === 'all' ? logs : logs.filter(l => l.level === filter)

  const infoCount = logs.filter(l => l.level === 'info').length
  const warnCount = logs.filter(l => l.level === 'warn').length
  const errorCount = logs.filter(l => l.level === 'error').length

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Terminal className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Logs</h2>
            <p className="text-sm text-[var(--text-tertiary)]">{logs.length} entries · Real-time activity</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" icon={RefreshCw} loading={loading} onClick={loadLogs} />
          <div className="flex items-center gap-1.5">
            <Filter className="w-4 h-4 text-[var(--text-muted)]" />
            {[
              { key: 'all', label: 'ALL', count: logs.length },
              { key: 'info', label: 'INFO', count: infoCount },
              { key: 'warn', label: 'WARN', count: warnCount },
              { key: 'error', label: 'ERROR', count: errorCount },
            ].map(level => (
              <button
                key={level.key}
                onClick={() => setFilter(level.key)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  filter === level.key
                    ? 'bg-[var(--color-brand-500)] text-white'
                    : 'text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]'
                )}
              >
                {level.label}
                {level.count > 0 && level.key !== 'all' && (
                  <span className="ml-1 opacity-60">({level.count})</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Log Output */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card padding="none">
          {/* Log Header */}
          <div className="flex items-center gap-6 px-5 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)]">
            <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider w-16">Time</span>
            <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider w-14">Level</span>
            <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider w-16">Source</span>
            <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider flex-1">Message</span>
          </div>

          {/* Log Entries */}
          <div className="max-h-[600px] overflow-y-auto font-mono text-xs">
            {filtered.length > 0 ? filtered.map((log, i) => {
              const config = levelConfig[log.level]
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.01 * i }}
                  className="flex items-start gap-6 px-5 py-2.5 border-b border-[var(--border-primary)]/50 hover:bg-[var(--bg-elevated)]/30 transition-colors"
                >
                  <span className="text-[var(--text-muted)] shrink-0 w-16">{log.timestamp}</span>
                  <div className="flex items-center gap-1.5 shrink-0 w-14">
                    {config.icon}
                    <span className={cn('uppercase font-bold', config.color)}>{log.level}</span>
                  </div>
                  <span className="text-[var(--text-muted)] shrink-0 w-16">{log.source}</span>
                  <span className="text-[var(--text-secondary)] flex-1 break-all">{log.message}</span>
                </motion.div>
              )
            }) : (
              <div className="py-12 text-center">
                <EmptyState
                  icon={<Terminal className="w-10 h-10" />}
                  title="No logs found"
                  description={filter !== 'all' ? `No ${filter} level log entries` : 'No log data available'}
                  action={
                    filter !== 'all' ? (
                      <Button variant="ghost" size="sm" onClick={() => setFilter('all')}>Clear filter</Button>
                    ) : undefined
                  }
                />
              </div>
            )}
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
