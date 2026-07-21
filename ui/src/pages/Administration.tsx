import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Shield, Users, Key, Activity, Clock, RefreshCw, Zap, TrendingUp } from 'lucide-react'
import { fetchMetrics, fetchAgents, type MetricsResponse, type AgentMeta } from '../lib/api'
import { useNotify } from '../context/NotificationContext'
import {Card, CardHeader} from '../components/ui/Card'
import {Badge} from '../components/ui/Badge'
import {Button} from '../components/ui/Button'
import { cn } from '../utils/helpers'

export function Administration() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [loading, setLoading] = useState(true)
  const { notify } = useNotify()

  const load = useCallback(async () => {
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
  }, [notify])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  const totalCalls = metrics ? Object.values(metrics.api as Record<string, number>).reduce((a: number, b: number) => a + b, 0) : 0
  const activeKeys = metrics ? Object.keys(metrics.perKey).length : 0
  const errors = (metrics?.api as Record<string, number>)?.errors ?? 0

  const statCards = [
    {
      title: 'API Calls',
      value: totalCalls,
      subtitle: `${errors} errors`,
      icon: <Users className="w-4 h-4" />,
      color: 'text-brand-400',
      bgColor: 'bg-brand-500/10',
    },
    {
      title: 'API Keys',
      value: activeKeys || 1,
      subtitle: activeKeys > 0 ? `${activeKeys} active` : 'Legacy secret',
      icon: <Key className="w-4 h-4" />,
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/10',
    },
    {
      title: 'Agents',
      value: agents.length,
      subtitle: `${agents.reduce((s, a) => s + a.capabilities.length, 0)} capabilities`,
      icon: <Shield className="w-4 h-4" />,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
    {
      title: 'Uptime',
      value: '99.9%',
      subtitle: 'Last 30 days',
      icon: <Clock className="w-4 h-4" />,
      color: 'text-[var(--color-engine-voltage)]',
      bgColor: 'bg-[var(--color-brand-500)]/10',
    },
  ]

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Shield className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Administration</h2>
            <p className="text-sm text-[var(--text-tertiary)]">Platform monitoring & management</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} loading={loading} onClick={load}>
          Refresh
        </Button>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <motion.div key={card.title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
            <Card padding="md">
              <div className="flex items-center justify-between mb-3">
                <div className={cn('p-2 rounded-lg', card.bgColor, card.color)}>
                  {card.icon}
                </div>
                <TrendingUp className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{card.value}</p>
              <p className="text-xs text-[var(--text-muted)] mt-1">{card.subtitle}</p>
              <p className="text-xs text-[var(--text-tertiary)] mt-2 font-medium">{card.title}</p>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* API Metrics & Provider Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Metrics */}
        {metrics && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card padding="md">
              <CardHeader
                title="API Metrics"
                subtitle="Request distribution"
                icon={<Activity className="w-4 h-4" />}
              />
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(metrics.api as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <p className="text-xs text-[var(--text-muted)] capitalize">{k.replace(/([A-Z])/g, ' $1').trim()}</p>
                    <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">{v}</p>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>
        )}

        {/* Provider Latency */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card padding="md">
            <CardHeader
              title="Provider Latency"
              subtitle="Response time & failure rates"
              icon={<Zap className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {metrics ? Object.entries(metrics.providers as Record<string, { count: number; avgMs: number; failureRate: number }>).map(([name, p]) => {
                const latencyColor = p.avgMs < 500 ? 'bg-green-500' : p.avgMs < 1000 ? 'bg-amber-500' : 'bg-red-500'
                const latencyPercent = Math.min(100, (p.avgMs / 2000) * 100)
                return (
                  <div key={name} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-[var(--text-primary)] capitalize">{name}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant={p.failureRate > 0.05 ? 'warning' : 'success'} size="sm">
                          {(p.failureRate * 100).toFixed(1)}% fail
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                        <div className={cn('h-full rounded-full transition-all', latencyColor)} style={{ width: `${latencyPercent}%` }} />
                      </div>
                      <span className="text-xs text-[var(--text-muted)] mono-engineering w-16 text-right">{p.avgMs}ms</span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-1.5">{p.count} calls</p>
                  </div>
                )
              }) : agents.slice(0, 4).map(a => (
                <div key={a.id} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{a.name}</span>
                    <span className="text-xs text-[var(--text-muted)]">{a.capabilities.slice(0, 3).join(', ')}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Agent Registry */}
      {agents.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <Card padding="md">
            <CardHeader
              title="Agent Registry"
              subtitle={`${agents.length} registered agents`}
              icon={<Users className="w-4 h-4" />}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {agents.map(agent => (
                <div key={agent.id} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className="p-1.5 rounded-md bg-brand-500/10">
                      <Zap className="w-3.5 h-3.5 text-brand-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">{agent.name}</p>
                      {agent.model && <p className="text-xs text-[var(--text-muted)]">{agent.model}</p>}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {agent.capabilities.slice(0, 3).map(cap => (
                      <Badge key={cap} variant="neutral" size="sm">{cap}</Badge>
                    ))}
                    {agent.capabilities.length > 3 && (
                      <Badge variant="neutral" size="sm">+{agent.capabilities.length - 3}</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  )
}
