import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, RefreshCw, Activity, Cpu, Gauge } from 'lucide-react'
import { fetchHealth, type HealthResponse } from '../lib/api'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, CardSection, Badge, Button, EmptyState } from '../components/ui'
import { cn } from '../utils/helpers'

interface DiagnosticCheck {
  name: string
  status: 'pass' | 'fail' | 'warn'
  message: string
  latencyMs?: number
}

const statusConfig = {
  pass: {
    icon: <CheckCircle className="w-5 h-5 text-green-400" />,
    variant: 'success' as const,
    color: 'text-green-400',
    borderColor: 'border-green-500/20',
    bgColor: 'bg-green-500/5',
  },
  fail: {
    icon: <XCircle className="w-5 h-5 text-red-400" />,
    variant: 'danger' as const,
    color: 'text-red-400',
    borderColor: 'border-red-500/20',
    bgColor: 'bg-red-500/5',
  },
  warn: {
    icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
    variant: 'warning' as const,
    color: 'text-amber-400',
    borderColor: 'border-amber-500/20',
    bgColor: 'bg-amber-500/5',
  },
}

export function Diagnostics() {
  const [checks, setChecks] = useState<DiagnosticCheck[]>([])
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const { notify } = useNotify()

  const runDiagnostics = async () => {
    setRunning(true)
    setProgress(0)
    setChecks([])
    const results: DiagnosticCheck[] = []
    const start = performance.now()

    // Simulate progress steps
    setProgress(10)

    try {
      setProgress(25)
      const health: HealthResponse = await fetchHealth()
      setProgress(50)

      results.push({ name: 'API Gateway', status: health.ok ? 'pass' : 'fail', message: health.ok ? 'Healthy' : 'Unhealthy' })

      if (health.engineeringService?.configured) {
        results.push({
          name: 'Engineering Service',
          status: health.engineeringService.healthy ? 'pass' : 'fail',
          message: health.engineeringService.healthy ? 'Online' : 'Unhealthy',
          latencyMs: health.engineeringService.latencyMs,
        })
      } else {
        results.push({ name: 'Engineering Service', status: 'warn', message: 'Not configured' })
      }

      setProgress(70)
      const providerCount = health.providers ? Object.keys(health.providers).length : 0
      results.push({
        name: 'AI Providers',
        status: providerCount > 0 ? 'pass' : 'warn',
        message: `${providerCount} provider${providerCount !== 1 ? 's' : ''} configured`,
      })
    } catch {
      results.push({ name: 'API Gateway', status: 'fail', message: 'Unreachable' })
    }

    setProgress(85)
    results.push({ name: 'Total Diagnostic Time', status: 'pass', message: `${Math.round(performance.now() - start)}ms` })
    setProgress(100)

    // Small delay so user sees 100%
    await new Promise(r => setTimeout(r, 300))

    setChecks(results)
    setRunning(false)
    setProgress(0)
    notify(results.every(c => c.status === 'pass') ? 'success' : 'warning', 'Diagnostics complete')
  }

  useEffect(() => { runDiagnostics() }, [])

  const passCount = checks.filter(c => c.status === 'pass').length
  const failCount = checks.filter(c => c.status === 'fail').length
  const warnCount = checks.filter(c => c.status === 'warn').length

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Activity className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Diagnostics</h2>
            <p className="text-sm text-[var(--text-tertiary)]">System health checks & status</p>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={RefreshCw} loading={running} onClick={runDiagnostics}>
          {running ? 'Running...' : 'Run Diagnostics'}
        </Button>
      </motion.div>

      {/* Progress Bar */}
      {running && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card padding="md">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-[var(--text-secondary)]">Running diagnostics...</span>
              <span className="text-xs text-[var(--text-muted)] mono-engineering">{progress}%</span>
            </div>
            <div className="h-2 bg-[var(--bg-primary)] rounded-full overflow-hidden border border-[var(--border-primary)]">
              <motion.div
                className="h-full bg-[var(--color-brand-500)] rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </Card>
        </motion.div>
      )}

      {/* Summary Cards */}
      {checks.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card padding="md" className="border-green-500/20 bg-green-500/5">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-sm font-medium text-green-400">Passed</span>
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{passCount}</p>
            </Card>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card padding="md" className="border-amber-500/20 bg-amber-500/5">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-medium text-amber-400">Warnings</span>
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{warnCount}</p>
            </Card>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card padding="md" className="border-red-500/20 bg-red-500/5">
              <div className="flex items-center gap-2 mb-1">
                <XCircle className="w-4 h-4 text-red-400" />
                <span className="text-sm font-medium text-red-400">Failed</span>
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{failCount}</p>
            </Card>
          </motion.div>
        </div>
      )}

      {/* Check Results */}
      {checks.length > 0 ? (
        <div className="space-y-3">
          {checks.map((check, i) => {
            const config = statusConfig[check.status]
            return (
              <motion.div key={check.name} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.05 * i }}>
                <Card padding="md" className={cn(config.borderColor, config.bgColor)}>
                  <div className="flex items-center gap-3">
                    {config.icon}
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-[var(--text-primary)]">{check.name}</h4>
                      <p className={cn('text-sm', config.color)}>
                        {check.message}
                        {check.latencyMs !== undefined && (
                          <span className="text-[var(--text-muted)] ml-2 mono-engineering">({check.latencyMs}ms)</span>
                        )}
                      </p>
                    </div>
                    <Badge variant={config.variant} size="sm" className="uppercase">
                      {check.status}
                    </Badge>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      ) : !running && (
        <Card padding="lg">
          <EmptyState
            icon={<Cpu className="w-12 h-12" />}
            title="No diagnostic results yet"
            description="Click 'Run Diagnostics' to check system health"
            action={
              <Button variant="primary" size="sm" icon={RefreshCw} onClick={runDiagnostics}>
                Run Diagnostics
              </Button>
            }
          />
        </Card>
      )}
    </div>
  )
}
