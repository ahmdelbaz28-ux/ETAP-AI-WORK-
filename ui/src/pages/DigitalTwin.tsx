import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Layers, RefreshCw, Activity, Box, HardDrive, Cpu, Wifi, WifiOff, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, Badge, Button } from '../components/ui'
import { cn } from '../utils/helpers'
import { useNotify } from '../context/NotificationContext'
import { API_BASE_URL } from '../lib/api-config'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
interface SyncSource {
  name: string
  status: 'online' | 'offline' | 'warning'
  lastSync: string
  records: number
}

interface SystemStat {
  label: string
  value: string | number
  icon: React.ReactNode
  color: string
}

interface DigitalTwinStatus {
  status: string
  buses?: number
  lines?: number
  generators?: number
  loads?: number
  transformers?: number
  sync_sources?: SyncSource[]
  last_updated?: string
}

function DigitalTwinDiagram() {
  return (
    <div className="bg-[var(--bg-primary)] rounded-lg p-4 border border-[var(--border-primary)]">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[var(--text-secondary)]">System One-Line Diagram</h4>
        <Badge variant="info" size="sm">Digital Twin</Badge>
      </div>
      <svg viewBox="0 0 700 400" className="w-full h-auto" style={{ minHeight: 240 }}>
        {/* Grid background */}
        <defs>
          <pattern id="dt-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--border-primary)" strokeWidth="0.5" />
          </pattern>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect width="700" height="400" fill="url(#dt-grid)" />

        {/* Title block */}
        <rect x="10" y="10" width="200" height="30" rx="4" fill="var(--bg-card)" stroke="var(--border-primary)" />
        <text x="20" y="30" fill="var(--text-secondary)" fontSize="11" fontWeight="600">ETAP Digital Twin — 13.8kV System</text>

        {/* Main Bus 1 - 13.8kV */}
        <line x1="80" y1="120" x2="620" y2="120" className="one-line-bus" />
        <rect x="80" y="114" width="540" height="12" rx="2" fill="var(--color-engine-voltage)" opacity="0.08" />
        <text x="340" y="108" textAnchor="middle" fill="var(--color-engine-voltage)" fontSize="10" fontWeight="600">BUS 1 — 13.8 kV</text>

        {/* Generator G1 */}
        <circle cx="150" cy="70" r="22" className="one-line-generator" />
        <text x="150" y="75" textAnchor="middle" fill="var(--text-primary)" fontSize="11" fontWeight="bold">G1</text>
        <line x1="150" y1="92" x2="150" y2="120" stroke="var(--color-engine-power)" strokeWidth="2" />
        <text x="150" y="50" textAnchor="middle" fill="var(--color-engine-power)" fontSize="9">25 MW</text>

        {/* Generator G2 */}
        <circle cx="350" cy="70" r="18" className="one-line-generator" />
        <text x="350" y="75" textAnchor="middle" fill="var(--text-primary)" fontSize="10" fontWeight="bold">G2</text>
        <line x1="350" y1="88" x2="350" y2="120" stroke="var(--color-engine-power)" strokeWidth="2" />
        <text x="350" y="50" textAnchor="middle" fill="var(--color-engine-power)" fontSize="9">15 MW</text>

        {/* Transformer T1 */}
        <line x1="250" y1="120" x2="250" y2="175" stroke="var(--color-engine-impedance)" strokeWidth="1.5" />
        <circle cx="250" cy="185" r="12" className="one-line-transformer" />
        <circle cx="250" cy="205" r="12" className="one-line-transformer" />
        <text x="280" y="198" fill="var(--color-engine-impedance)" fontSize="9">T1</text>
        <text x="280" y="210" fill="var(--text-muted)" fontSize="8">50 MVA</text>

        {/* Secondary Bus - 4.16kV */}
        <line x1="150" y1="220" x2="400" y2="220" className="one-line-bus" stroke="var(--color-engine-current)" strokeWidth="2" />
        <rect x="150" y="214" width="250" height="12" rx="2" fill="var(--color-engine-current)" opacity="0.08" />
        <text x="275" y="240" textAnchor="middle" fill="var(--color-engine-current)" fontSize="10" fontWeight="600">BUS 2 — 4.16 kV</text>
        <line x1="250" y1="217" x2="250" y2="220" stroke="var(--color-engine-impedance)" strokeWidth="1.5" />

        {/* Motor M1 */}
        <circle cx="200" cy="280" r="16" fill="none" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="200" y="284" textAnchor="middle" fill="var(--color-engine-current)" fontSize="9" fontWeight="bold">M1</text>
        <line x1="200" y1="220" x2="200" y2="264" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="200" y="305" textAnchor="middle" fill="var(--text-muted)" fontSize="8">250 kW</text>

        {/* Motor M2 */}
        <circle cx="320" cy="280" r="14" fill="none" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="320" y="284" textAnchor="middle" fill="var(--color-engine-current)" fontSize="9" fontWeight="bold">M2</text>
        <line x1="320" y1="220" x2="320" y2="266" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="320" y="303" textAnchor="middle" fill="var(--text-muted)" fontSize="8">150 kW</text>

        {/* Load on main bus */}
        <polygon points="530,145 555,145 542,170" className="one-line-load" />
        <line x1="542" y1="120" x2="542" y2="145" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="542" y="185" textAnchor="middle" fill="var(--color-engine-current)" fontSize="9">12 MW</text>

        {/* Circuit breaker symbols */}
        <rect x="448" y="110" width="8" height="20" rx="1" fill="var(--color-engine-protection)" />
        <line x1="452" y1="108" x2="452" y2="132" stroke="var(--color-engine-protection)" strokeWidth="1" />
        <text x="452" y="145" textAnchor="middle" fill="var(--color-engine-protection)" fontSize="8">CB1</text>

        {/* Tie breaker */}
        <rect x="448" y="110" width="8" height="20" rx="1" fill="var(--color-engine-protection)" opacity="0.6" />

        {/* Capacitor bank */}
        <line x1="600" y1="120" x2="600" y2="155" stroke="var(--color-engine-voltage)" strokeWidth="1.5" />
        <line x1="590" y1="155" x2="610" y2="155" stroke="var(--color-engine-voltage)" strokeWidth="2" />
        <line x1="590" y1="162" x2="610" y2="162" stroke="var(--color-engine-voltage)" strokeWidth="2" />
        <text x="600" y="180" textAnchor="middle" fill="var(--color-engine-voltage)" fontSize="8">CAP</text>

        {/* Legend */}
        <rect x="10" y="340" width="280" height="50" rx="4" fill="var(--bg-card)" stroke="var(--border-primary)" />
        <circle cx="25" cy="355" r="5" className="one-line-generator" />
        <text x="35" y="359" fill="var(--text-muted)" fontSize="8">Generator</text>
        <line x1="90" y1="355" x2="105" y2="355" className="one-line-bus" strokeWidth="2" />
        <text x="110" y="359" fill="var(--text-muted)" fontSize="8">Bus</text>
        <circle cx="150" cy="355" r="5" className="one-line-transformer" />
        <text x="160" y="359" fill="var(--text-muted)" fontSize="8">Transformer</text>
        <polygon points="230,350 240,350 235,360" className="one-line-load" />
        <text x="248" y="359" fill="var(--text-muted)" fontSize="8">Load</text>
        <text x="25" y="380" fill="var(--text-muted)" fontSize="7">All values in pu / rated unless noted</text>
      </svg>
    </div>
  )
}

export default function DigitalTwin() {
  const { notify } = useNotify()
  const [syncing, setSyncing] = useState(false)
  const [status, setStatus] = useState<DigitalTwinStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('authToken')
      const r = await fetch(`${API_BASE_URL}/api/v1/digital-twin/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      })
      if (!r.ok) {
        const text = await r.text().catch(() => 'Unknown error')
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`)
      }
      const data = await r.json()
      setStatus(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [API_BASE_URL])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const handleSync = async () => {
    setSyncing(true)
    try {
      // Re-fetch status as the sync operation. The backend digital-twin
      // endpoint returns the current sync state; calling it again is the
      // real refresh operation (no fake setTimeout).
      await fetchStatus()
      notify('success', 'Digital twin status refreshed')
    } catch {
      notify('error', 'Failed to sync digital twin')
    } finally {
      setSyncing(false)
    }
  }

  // Derive sync sources + system stats from the real API response.
  // If the API returns no data (e.g. no system loaded), show empty/zero
  // values rather than fake hardcoded sample data.
  const syncSources: SyncSource[] = status?.sync_sources ?? []
  const systemStats: SystemStat[] = [
    { label: 'Buses', value: status?.buses ?? 0, icon: <Box className="w-4 h-4" />, color: 'text-[var(--color-engine-voltage)]' },
    { label: 'Lines', value: status?.lines ?? 0, icon: <Activity className="w-4 h-4" />, color: 'text-[var(--color-engine-impedance)]' },
    { label: 'Loads', value: status?.loads ?? 0, icon: <HardDrive className="w-4 h-4" />, color: 'text-[var(--color-engine-current)]' },
    { label: 'Generators', value: status?.generators ?? 0, icon: <Cpu className="w-4 h-4" />, color: 'text-[var(--color-engine-power)]' },
  ]

  const statusConfig = {
    online: { variant: 'success' as const, icon: <Wifi className="w-3 h-3" /> },
    offline: { variant: 'danger' as const, icon: <WifiOff className="w-3 h-3" /> },
    warning: { variant: 'warning' as const, icon: <AlertTriangle className="w-3 h-3" /> },
  }

  // Show loading state while fetching
  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading digital twin status…</span>
        </div>
      </div>
    )
  }

  // Show error state if fetch failed
  if (error && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load digital twin status</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchStatus}>
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Layers className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Digital Twin</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Real-time power system topology & synchronization</p>
              <ContextHelpButton contextId="digital-twin.overview" />
            </div>
          </div>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} loading={syncing} onClick={handleSync}>
          Sync Now
        </Button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* One-Line Diagram */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="lg:col-span-2">
          <Card padding="md">
            <CardHeader
              title="System Topology"
              subtitle="Interactive one-line diagram"
              icon={<Activity className="w-4 h-4" />}
            />
            <DigitalTwinDiagram />
          </Card>
        </motion.div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Sync Status */}
          <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <Card padding="md">
              <CardHeader
                title="Sync Status"
                subtitle="Data source connections"
                icon={<RefreshCw className="w-4 h-4" />}
              />
              <div className="space-y-3">
                {syncSources.map(source => {
                  const config = statusConfig[source.status]
                  return (
                    <div key={source.name} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                      <div className="flex items-center gap-2.5">
                        {config.icon}
                        <div>
                          <p className="text-sm font-medium text-[var(--text-primary)]">{source.name}</p>
                          <p className="text-xs text-[var(--text-muted)]">{source.lastSync}</p>
                        </div>
                      </div>
                      <Badge variant={config.variant} dot size="sm">
                        {source.status === 'online' ? 'Online' : source.status === 'offline' ? 'Offline' : 'Warning'}
                      </Badge>
                    </div>
                  )
                })}
              </div>
            </Card>
          </motion.div>

          {/* Quick Stats */}
          <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
            <Card padding="md">
              <CardHeader
                title="System Statistics"
                subtitle="Model element counts"
                icon={<HardDrive className="w-4 h-4" />}
              />
              <div className="grid grid-cols-2 gap-3">
                {systemStats.map(stat => (
                  <div key={stat.label} className="text-center p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className={cn('flex items-center justify-center mb-1.5', stat.color)}>
                      {stat.icon}
                    </div>
                    <p className="text-xl font-bold text-[var(--text-primary)] mono-engineering">{stat.value}</p>
                    <p className="text-xs text-[var(--text-muted)]">{stat.label}</p>
                  </div>
                ))}
              </div>
            </Card>
          </motion.div>

          {/* Model Info */}
          <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
            <Card padding="md">
              <CardHeader
                title="Model Info"
                subtitle="Twin configuration"
                icon={<Cpu className="w-4 h-4" />}
              />
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Base MVA</span>
                  <span className="text-[var(--text-primary)] mono-engineering">100</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Frequency</span>
                  <span className="text-[var(--text-primary)] mono-engineering">60 Hz</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Voltage Levels</span>
                  <span className="text-[var(--text-primary)] mono-engineering">2</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Last Updated</span>
                  <span className="text-[var(--text-primary)]">—</span>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
