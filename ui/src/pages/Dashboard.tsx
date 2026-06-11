import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MdScience, MdSmartToy, MdCheckCircle, MdError, MdTrendingUp } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'
import { fetchHealth, fetchAgents, type HealthResponse, type AgentMeta } from '../lib/api'

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [loading, setLoading] = useState(true)
  const { notify } = useNotify()
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([fetchHealth().catch(() => null), fetchAgents().catch(() => [])])
      .then(([h, a]) => { setHealth(h); setAgents(a); setLoading(false) })
      .catch(() => { notify('error', 'Failed to load dashboard data'); setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-400" />
      </div>
    )
  }

  const statusColor = health?.ok ? 'text-green-400' : 'text-red-400'
  const studyCount = agents.reduce((sum, a) => sum + a.capabilities.length, 0)

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Dashboard</h2>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-colors">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${health?.ok ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
              <MdCheckCircle className={`text-xl ${statusColor}`} />
            </div>
            <div>
              <p className="text-sm text-surface-400">System Status</p>
              <p className={`text-lg font-bold ${statusColor}`}>{health?.ok ? 'Online' : 'Offline'}</p>
            </div>
          </div>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-colors">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-500/10">
              <MdSmartToy className="text-xl text-brand-400" />
            </div>
            <div>
              <p className="text-sm text-surface-400">Active Agents</p>
              <p className="text-lg font-bold text-white">{agents.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-colors">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/10">
              <MdScience className="text-xl text-amber-400" />
            </div>
            <div>
              <p className="text-sm text-surface-400">Study Capabilities</p>
              <p className="text-lg font-bold text-white">{studyCount}</p>
            </div>
          </div>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-colors">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <MdTrendingUp className="text-xl text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-surface-400">Engineering Service</p>
              <p className={`text-lg font-bold ${health?.engineeringService?.healthy ? 'text-green-400' : 'text-red-400'}`}>
                {health?.engineeringService?.configured ? (health.engineeringService.healthy ? 'Online' : 'Unhealthy') : 'Not Configured'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <h3 className="text-lg font-semibold text-white mb-4">Quick Studies</h3>
          <div className="grid grid-cols-2 gap-2">
            {['load_flow', 'short_circuit', 'arc_flash', 'protection_coordination', 'harmonic_analysis', 'motor_starting'].map(s => (
              <button
                key={s}
                onClick={() => navigate(`/studies/${s}`)}
                className="px-3 py-2 text-sm text-left rounded-lg bg-surface-700 hover:bg-brand-600 text-surface-200 hover:text-white transition-colors capitalize"
              >
                {s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <h3 className="text-lg font-semibold text-white mb-4">AI Agents</h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {agents.map(agent => (
              <button
                key={agent.id}
                onClick={() => navigate('/assistant')}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-700 transition-colors text-left"
              >
                <MdSmartToy className="text-brand-400 shrink-0" />
                <div>
                  <p className="text-sm text-white font-medium">{agent.name}</p>
                  <p className="text-xs text-surface-400">{agent.capabilities.slice(0, 3).join(', ')}</p>
                </div>
              </button>
            ))}
            {agents.length === 0 && (
              <p className="text-sm text-surface-500">No agents available. Check API key configuration.</p>
            )}
          </div>
        </div>
      </div>

      {/* Engineering Service Status */}
      {health?.engineeringService && (
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <h3 className="text-lg font-semibold text-white mb-2">Engineering Service</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-surface-400">Configured:</span>
              <span className={`ml-2 ${health.engineeringService.configured ? 'text-green-400' : 'text-red-400'}`}>
                {health.engineeringService.configured ? 'Yes' : 'No'}
              </span>
            </div>
            <div>
              <span className="text-surface-400">Healthy:</span>
              <span className={`ml-2 ${health.engineeringService.healthy ? 'text-green-400' : 'text-red-400'}`}>
                {health.engineeringService.healthy ? 'Yes' : 'No'}
              </span>
            </div>
            <div>
              <span className="text-surface-400">Latency:</span>
              <span className="ml-2 text-white">{health.engineeringService.latencyMs ?? 'N/A'}ms</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
