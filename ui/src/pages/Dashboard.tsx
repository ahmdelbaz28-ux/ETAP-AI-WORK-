import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Zap, Bot, FlaskConical, CheckCircle, XCircle,
  TrendingUp, Activity, Server, Clock
} from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { useNotify } from '../context/NotificationContext'
import { fetchHealth, fetchAgents, type HealthResponse, type AgentMeta } from '../lib/api'
import { studyCategories } from '../lib/studyCategories'
import { cn } from '../utils/helpers'

// Simulated time-series data for charts
const generateTimeSeriesData = () => {
  const data = []
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    data.push({
      time: new Date(now - i * 3600000).toLocaleTimeString('en-US', { hour: '2-digit', hour12: false }),
      requests: Math.floor(Math.random() * 50) + 10,
      latency: Math.floor(Math.random() * 100) + 20,
    })
  }
  return data
}

const studyDistributionData = [
  { name: 'Load Flow', count: 45 },
  { name: 'Short Circuit', count: 32 },
  { name: 'Arc Flash', count: 28 },
  { name: 'Harmonic', count: 18 },
  { name: 'Protection', count: 15 },
  { name: 'Motor Start', count: 12 },
]

const fadeIn = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4 }
}

interface StatCardProps {
  icon: React.ElementType
  label: string
  value: string | number
  sublabel?: string
  color: 'green' | 'blue' | 'amber' | 'purple' | 'red'
  trend?: string
}

function StatCard({ icon: Icon, label, value, sublabel, color, trend }: StatCardProps) {
  const colorMap = {
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    blue: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
  }

  return (
    <motion.div
      {...fadeIn}
      className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-surface-600 transition-all group"
    >
      <div className="flex items-start justify-between">
        <div className={cn('p-2.5 rounded-lg border', colorMap[color])}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full',
            trend.startsWith('+') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
          )}>
            {trend}
          </span>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-sm text-surface-400 mt-0.5">{label}</p>
        {sublabel && <p className="text-xs text-surface-500 mt-0.5">{sublabel}</p>}
      </div>
    </motion.div>
  )
}

export function Dashboard() {
  const { t } = useTranslation()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [loading, setLoading] = useState(true)
  const { notify } = useNotify()
  const navigate = useNavigate()
  const [timeSeriesData] = useState(generateTimeSeriesData)

  useEffect(() => {
    Promise.all([fetchHealth().catch(() => null), fetchAgents().catch(() => [])])
      .then(([h, a]) => { setHealth(h); setAgents(a); setLoading(false) })
      .catch(() => { notify('error', 'Failed to load dashboard data'); setLoading(false) })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-500 border-t-transparent" />
          <p className="text-surface-400 text-sm">{t('common.loading')}</p>
        </div>
      </div>
    )
  }

  const studyCount = agents.reduce((sum, a) => sum + a.capabilities.length, 0)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div {...fadeIn}>
        <h2 className="text-2xl font-bold text-white">{t('dashboard.title')}</h2>
        <p className="text-surface-400 mt-1">{t('dashboard.subtitle')}</p>
      </motion.div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={health?.ok ? CheckCircle : XCircle}
          label={t('dashboard.systemHealth')}
          value={health?.ok ? t('dashboard.online') : t('dashboard.offline')}
          sublabel={health?.version ? `v${health.version}` : undefined}
          color={health?.ok ? 'green' : 'red'}
        />
        <StatCard
          icon={Bot}
          label={t('dashboard.agents')}
          value={agents.length}
          sublabel={`${studyCount} ${t('dashboard.studyCapabilities')}`}
          color="blue"
          trend="+2"
        />
        <StatCard
          icon={FlaskConical}
          label={t('dashboard.totalStudies')}
          value={studyCount}
          sublabel={t('dashboard.activeStudies')}
          color="amber"
        />
        <StatCard
          icon={Server}
          label={t('dashboard.engineeringService')}
          value={health?.engineeringService?.configured
            ? (health.engineeringService.healthy ? t('dashboard.healthy') : 'Unhealthy')
            : 'Not Configured'
          }
          sublabel={health?.engineeringService?.latencyMs ? `${health.engineeringService.latencyMs}ms` : undefined}
          color={health?.engineeringService?.healthy ? 'green' : 'purple'}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Request Activity Chart */}
        <motion.div {...fadeIn} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-brand-400" />
              API Activity
            </h3>
            <span className="text-xs text-surface-400">Last 24 hours</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeSeriesData}>
              <defs>
                <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Area type="monotone" dataKey="requests" stroke="#3b82f6" fill="url(#colorRequests)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Study Distribution Chart */}
        <motion.div {...fadeIn} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-amber-400" />
              Study Distribution
            </h3>
            <span className="text-xs text-surface-400">By category</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={studyDistributionData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Quick Actions & Agents Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Studies */}
        <motion.div {...fadeIn} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              {t('dashboard.quickActions')}
            </h3>
            <button onClick={() => navigate('/studies')} className="text-xs text-brand-400 hover:text-brand-300 transition-colors">
              {t('dashboard.viewAll')} →
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {studyCategories.slice(0, 6).map(s => (
              <button
                key={s.id}
                onClick={() => navigate(`/studies/${s.id}`)}
                className="flex items-center gap-2 px-3 py-2.5 text-sm text-left rounded-lg bg-surface-700/50 hover:bg-brand-600/20 text-surface-200 hover:text-white transition-all group border border-transparent hover:border-brand-500/30"
              >
                <span className="text-lg">{s.icon}</span>
                <span className="truncate text-xs font-medium">{s.name}</span>
              </button>
            ))}
          </div>
        </motion.div>

        {/* AI Agents */}
        <motion.div {...fadeIn} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Bot className="w-5 h-5 text-brand-400" />
              {t('dashboard.agents')}
            </h3>
            <button onClick={() => navigate('/assistant')} className="text-xs text-brand-400 hover:text-brand-300 transition-colors">
              {t('dashboard.viewAll')} →
            </button>
          </div>
          <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
            {agents.length > 0 ? agents.map(agent => (
              <button
                key={agent.id}
                onClick={() => navigate('/assistant')}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface-700/50 transition-colors text-left group"
              >
                <div className="p-1.5 rounded-md bg-brand-500/10 shrink-0">
                  <Bot className="w-4 h-4 text-brand-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white font-medium truncate group-hover:text-brand-400 transition-colors">{agent.name}</p>
                  <p className="text-xs text-surface-400 truncate">{agent.capabilities.slice(0, 3).join(' • ')}</p>
                </div>
                <span className="text-[10px] text-surface-500 bg-surface-700 px-2 py-0.5 rounded-full shrink-0">
                  {agent.provider || 'active'}
                </span>
              </button>
            )) : (
              <div className="text-center py-6">
                <Bot className="w-8 h-8 text-surface-600 mx-auto mb-2" />
                <p className="text-sm text-surface-400">No agents available</p>
                <p className="text-xs text-surface-500 mt-1">Check API key configuration in Settings</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>

      {/* Engineering Service Status */}
      {health?.engineeringService && (
        <motion.div {...fadeIn} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Server className="w-5 h-5 text-brand-400" />
            {t('dashboard.engineeringService')}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-surface-900/50 rounded-lg p-3 text-center">
              <p className="text-xs text-surface-400 mb-1">{t('dashboard.configured')}</p>
              <span className={cn('text-sm font-bold', health.engineeringService.configured ? 'text-green-400' : 'text-red-400')}>
                {health.engineeringService.configured ? '✓ Yes' : '✗ No'}
              </span>
            </div>
            <div className="bg-surface-900/50 rounded-lg p-3 text-center">
              <p className="text-xs text-surface-400 mb-1">{t('dashboard.healthy')}</p>
              <span className={cn('text-sm font-bold', health.engineeringService.healthy ? 'text-green-400' : 'text-red-400')}>
                {health.engineeringService.healthy ? '✓ Yes' : '✗ No'}
              </span>
            </div>
            <div className="bg-surface-900/50 rounded-lg p-3 text-center">
              <p className="text-xs text-surface-400 mb-1">{t('dashboard.latency')}</p>
              <span className="text-sm font-bold text-white">{health.engineeringService.latencyMs ?? 'N/A'}ms</span>
            </div>
            <div className="bg-surface-900/50 rounded-lg p-3 text-center">
              <p className="text-xs text-surface-400 mb-1">{t('dashboard.uptime')}</p>
              <span className="text-sm font-bold text-white flex items-center justify-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {health.uptime ? `${Math.round(health.uptime / 3600)}h` : 'N/A'}
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
