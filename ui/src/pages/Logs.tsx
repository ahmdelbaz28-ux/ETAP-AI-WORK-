import { useState, useEffect } from 'react'
import { MdArticle, MdFilterList, MdRefresh } from 'react-icons/md'
import { fetchMetrics, fetchAuditLogs, type MetricsResponse, type AuditEntry } from '../lib/api'
import { useNotify } from '../context/NotificationContext'

interface LogEntry {
  timestamp: string
  level: 'info' | 'warn' | 'error'
  source: string
  message: string
}

function auditToLogs(metrics: MetricsResponse | null, audit: AuditEntry[]): LogEntry[] {
  const logs: LogEntry[] = []
  if (metrics) {
    logs.push({ timestamp: new Date().toLocaleTimeString(), level: 'info', source: 'metrics', message: `API requests: ${Object.values(metrics.api).reduce((a, b) => a + b, 0)} total` })
    for (const [name, p] of Object.entries(metrics.providers)) {
      logs.push({ timestamp: new Date().toLocaleTimeString(), level: 'info', source: 'provider', message: `${name}: ${p.count} calls, avg ${p.avgMs}ms, ${(p.failureRate * 100).toFixed(1)}% failures` })
    }
    for (const [name, c] of Object.entries(metrics.circuits)) {
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
  return logs.length ? logs : [{ timestamp: '--', level: 'info', source: 'system', message: 'No log data available. Run a study or chat to generate activity.' }]
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

  const levelColors: Record<string, string> = {
    info: 'text-blue-400',
    warn: 'text-amber-400',
    error: 'text-red-400',
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Logs</h2>
        <div className="flex items-center gap-2">
          <button onClick={loadLogs} disabled={loading}
            className="p-1.5 text-surface-400 hover:text-white transition-colors">
            <MdRefresh className={loading ? 'animate-spin' : ''} />
          </button>
          <MdFilterList className="text-surface-400" />
          {['all', 'info', 'warn', 'error'].map(l => (
            <button key={l} onClick={() => setFilter(l)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === l ? 'bg-brand-600 text-white' : 'bg-surface-700 text-surface-300 hover:text-white'
              }`}>{l.toUpperCase()}</button>
          ))}
        </div>
      </div>

      <div className="bg-surface-800 rounded-xl border border-surface-700 overflow-hidden font-mono text-xs">
        <div className="max-h-[600px] overflow-y-auto">
          {filtered.map((log, i) => (
            <div key={i} className="flex items-start gap-3 px-4 py-2 border-b border-surface-700/50 hover:bg-surface-700/30 transition-colors">
              <span className="text-surface-500 shrink-0 w-16">{log.timestamp}</span>
              <span className={`shrink-0 w-12 uppercase font-bold ${levelColors[log.level]}`}>{log.level}</span>
              <span className="text-surface-500 shrink-0 w-16">{log.source}</span>
              <span className="text-surface-200 flex-1">{log.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
