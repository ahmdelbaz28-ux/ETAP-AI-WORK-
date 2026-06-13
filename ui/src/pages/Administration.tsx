import { useState, useEffect } from 'react'
import { MdAdminPanelSettings, MdKey, MdPeople, MdShield, MdRefresh } from 'react-icons/md'
import { fetchMetrics, fetchAgents, type MetricsResponse, type AgentMeta } from '../lib/api'
import { useNotify } from '../context/NotificationContext'

export function Administration() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [loading, setLoading] = useState(true)
  const { notify } = useNotify()

  const load = async () => {
    setLoading(true)
    try {
      const [m, a] = await Promise.all([
        fetchMetrics().catch(() => null),
        fetchAgents().catch(() => []),
      ])
      setMetrics(m)
      setAgents(a)
    } catch {
      notify('error', 'Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const totalCalls = metrics ? Object.values(metrics.api as Record<string, number>).reduce((a: number, b: number) => a + b, 0) : 0
  const activeKeys = metrics ? Object.keys(metrics.perKey).length : 0
  const errors = (metrics?.api as Record<string, number>)?.errors ?? 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MdAdminPanelSettings className="text-3xl text-purple-400" />
          <h2 className="text-2xl font-bold text-white">Administration</h2>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-surface-300 hover:text-white transition-colors">
          <MdRefresh className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center gap-2 text-lg font-semibold text-white mb-3"><MdPeople className="text-brand-400" /> API Calls</div>
          <p className="text-3xl font-bold text-white">{totalCalls}</p>
          <p className="text-sm text-surface-400 mt-1">{errors} errors</p>
        </div>
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center gap-2 text-lg font-semibold text-white mb-3"><MdKey className="text-amber-400" /> API Keys</div>
          <p className="text-3xl font-bold text-white">{activeKeys || 1}</p>
          <p className="text-sm text-surface-400 mt-1">{activeKeys > 0 ? `${activeKeys} active` : 'Legacy secret'}</p>
        </div>
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center gap-2 text-lg font-semibold text-white mb-3"><MdShield className="text-green-400" /> Agents</div>
          <p className="text-3xl font-bold text-white">{agents.length}</p>
          <p className="text-sm text-surface-400 mt-1">{agents.reduce((s, a) => s + a.capabilities.length, 0)} capabilities</p>
        </div>
      </div>

      {metrics && (
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <h3 className="text-lg font-semibold text-white mb-3">API Metrics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {Object.entries(metrics.api as Record<string, number>).map(([k, v]) => (
              <div key={k} className="bg-surface-700 rounded-lg p-3">
                <p className="text-surface-400 capitalize">{k.replace(/([A-Z])/g, ' $1').trim()}</p>
                <p className="text-lg font-bold text-white">{v}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
        <h3 className="text-lg font-semibold text-white mb-3">Provider Latency</h3>
        <div className="space-y-2">
          {metrics ? Object.entries(metrics.providers as Record<string, { count: number; avgMs: number; failureRate: number }>).map(([name, p]) => (
            <div key={name} className="flex items-center justify-between px-3 py-2 bg-surface-700 rounded-lg">
              <span className="text-sm text-white capitalize">{name}</span>
              <span className="text-sm text-surface-300">{p.count} calls, {p.avgMs}ms avg, {(p.failureRate * 100).toFixed(1)}% fail</span>
            </div>
          )) : agents.map(a => (
            <div key={a.id} className="flex items-center justify-between px-3 py-2 bg-surface-700 rounded-lg">
              <span className="text-sm text-white">{a.name}</span>
              <span className="text-sm text-surface-300">{a.capabilities.slice(0, 3).join(', ')}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
