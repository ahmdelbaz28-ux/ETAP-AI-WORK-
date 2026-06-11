import { MdBugReport, MdCheckCircle, MdError, MdRefresh, MdMemory } from 'react-icons/md'
import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from '../lib/api'
import { useNotify } from '../context/NotificationContext'

interface DiagnosticCheck {
  name: string
  status: 'pass' | 'fail' | 'warn'
  message: string
  latencyMs?: number
}

export function Diagnostics() {
  const [checks, setChecks] = useState<DiagnosticCheck[]>([])
  const [running, setRunning] = useState(false)
  const { notify } = useNotify()

  const runDiagnostics = async () => {
    setRunning(true)
    const results: DiagnosticCheck[] = []
    const start = performance.now()

    try {
      const health: HealthResponse = await fetchHealth()
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

      results.push({
        name: 'AI Providers',
        status: health.providers.length > 0 ? 'pass' : 'warn',
        message: `${health.providers.length} providers configured`,
      })
    } catch {
      results.push({ name: 'API Gateway', status: 'fail', message: 'Unreachable' })
    }

    results.push({ name: 'Total Diagnostic Time', status: 'pass', message: `${Math.round(performance.now() - start)}ms` })
    setChecks(results)
    setRunning(false)
    notify(results.every(c => c.status === 'pass') ? 'success' : 'warning', 'Diagnostics complete')
  }

  useEffect(() => { runDiagnostics() }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Diagnostics</h2>
        <button onClick={runDiagnostics} disabled={running}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
          <MdRefresh className={running ? 'animate-spin' : ''} /> {running ? 'Running...' : 'Run Diagnostics'}
        </button>
      </div>

      <div className="space-y-3">
        {checks.map(c => (
          <div key={c.name} className={`bg-surface-800 rounded-xl p-4 border ${
            c.status === 'pass' ? 'border-green-500/20' : c.status === 'fail' ? 'border-red-500/20' : 'border-amber-500/20'
          }`}>
            <div className="flex items-center gap-3">
              {c.status === 'pass' ? <MdCheckCircle className="text-green-400 text-xl" /> :
               c.status === 'fail' ? <MdError className="text-red-400 text-xl" /> :
               <MdBugReport className="text-amber-400 text-xl" />}
              <div className="flex-1">
                <h4 className="text-white font-medium">{c.name}</h4>
                <p className={`text-sm ${c.status === 'pass' ? 'text-green-400' : c.status === 'fail' ? 'text-red-400' : 'text-amber-400'}`}>
                  {c.message}
                  {c.latencyMs !== undefined && <span className="text-surface-400 ml-2">({c.latencyMs}ms)</span>}
                </p>
              </div>
              <span className={`px-2 py-1 text-xs rounded-full font-medium uppercase ${
                c.status === 'pass' ? 'bg-green-500/10 text-green-400' : c.status === 'fail' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'
              }`}>{c.status}</span>
            </div>
          </div>
        ))}

        {checks.length === 0 && (
          <div className="text-center py-12 text-surface-500">
            <MdMemory className="text-5xl mx-auto mb-3 opacity-30" />
            <p>No diagnostic results yet. Click "Run Diagnostics" to begin.</p>
          </div>
        )}
      </div>
    </div>
  )
}
