import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Cpu, Zap, Cable, Settings2, Activity, Wrench, Search, Filter } from 'lucide-react'
import { Card, CardSection, Badge, Button, EmptyState } from '../components/ui'
import { cn } from '../utils/helpers'
import { API_BASE_URL } from '../lib/api-config'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
interface Asset {
  id: string
  name: string
  type: string
  rating: string
  voltage: string
  status: string
}

const typeIcons: Record<string, React.ReactNode> = {
  Transformer: <Zap className="w-5 h-5" />,
  Generator: <Cpu className="w-5 h-5" />,
  Breaker: <Settings2 className="w-5 h-5" />,
  Motor: <Activity className="w-5 h-5" />,
  Line: <Cable className="w-5 h-5" />,
  Relay: <Settings2 className="w-5 h-5" />,
}

const statusConfig: Record<string, { variant: 'success' | 'warning' | 'danger' | 'default'; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  maintenance: { variant: 'warning', label: 'Maintenance' },
  faulted: { variant: 'danger', label: 'Faulted' },
  offline: { variant: 'default', label: 'Offline' },
}

export default function AssetManagement() {
  const [, setLoading] = useState(true)  # NOSONAR — S6754: value intentionally unused
  const [, setError] = useState<string | null>(null)  # NOSONAR — S6754: value intentionally unused
  const [assets, setAssets] = useState<Asset[]>([])
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const fetchAssets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('authToken')
      // Try to fetch assets from the backend. The endpoint may not exist
      // yet (asset management is a future feature) — in that case we show
      // an empty state rather than fake sample data.
      const r = await fetch(`${API_BASE_URL}/api/v1/assets`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      })
      if (r.status === 404) {
        // Endpoint not implemented yet — show empty state, not fake data.
        setAssets([])
        return
      }
      if (!r.ok) {
        const text = await r.text().catch(() => 'Unknown error')
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`)
      }
      const data = await r.json()
      setAssets(Array.isArray(data) ? data : (data.assets ?? []))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setError(msg)
      setAssets([])
    } finally {
      setLoading(false)
    }
  }, [API_BASE_URL])

  useEffect(() => {
    fetchAssets()
  }, [fetchAssets])

  const summaryCards = [
    { label: 'Active', count: assets.filter(a => a.status === 'active').length, variant: 'success' as const, icon: <Activity className="w-4 h-4" /> },
    { label: 'Maintenance', count: assets.filter(a => a.status === 'maintenance').length, variant: 'warning' as const, icon: <Wrench className="w-4 h-4" /> },
    { label: 'Faulted', count: assets.filter(a => a.status === 'faulted').length, variant: 'danger' as const, icon: <Zap className="w-4 h-4" /> },
    { label: 'Offline', count: assets.filter(a => a.status === 'offline').length, variant: 'default' as const, icon: <Cpu className="w-4 h-4" /> },
  ]

  const filteredAssets = assets.filter(a => {
    const matchesSearch = search === '' || a.name.toLowerCase().includes(search.toLowerCase()) || a.type.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filterStatus === 'all' || a.status === filterStatus
    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Cpu className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Asset Management</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">{assets.length} assets in inventory</p>
              <ContextHelpButton contextId="asset-management.overview" />
            </div>
          </div>
        </div>
      </motion.div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card, i) => (
          <motion.div key={card.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
            <Card padding="md" className="text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <span className={cn(
                  card.variant === 'success' ? 'text-green-400' :
                  card.variant === 'warning' ? 'text-amber-400' :  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
                  card.variant === 'danger' ? 'text-red-400' : 'text-[var(--text-tertiary)]'  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
                )}>
                  {card.icon}
                </span>
                <span className="text-xs text-[var(--text-muted)]">{card.label}</span>
              </div>
              <p className="text-3xl font-bold text-[var(--text-primary)] mono-engineering">{card.count}</p>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Search/Filter Bar */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card padding="sm">
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Search assets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-[var(--color-brand-500)] outline-none transition-colors"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <Filter className="w-4 h-4 text-[var(--text-muted)]" />
              {['all', 'active', 'maintenance', 'faulted', 'offline'].map(status => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize',
                    filterStatus === status
                      ? 'bg-[var(--color-brand-500)] text-white'
                      : 'text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]'
                  )}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Asset Cards Grid */}
      {filteredAssets.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAssets.map((asset, i) => {
            const config = statusConfig[asset.status] || statusConfig.offline
            return (
              <motion.div key={asset.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
                <Card variant="bordered" padding="md">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
                        {typeIcons[asset.type] || <Cpu className="w-5 h-5" />}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{asset.name}</h3>
                        <p className="text-xs text-[var(--text-muted)]">{asset.type}</p>
                      </div>
                    </div>
                    <Badge variant={config.variant} dot size="sm">
                      {config.label}
                    </Badge>
                  </div>
                  <CardSection>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <p className="text-[var(--text-muted)]">Rating</p>
                        <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">{asset.rating}</p>
                      </div>
                      <div>
                        <p className="text-[var(--text-muted)]">Voltage</p>
                        <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">{asset.voltage}</p>
                      </div>
                    </div>
                  </CardSection>
                </Card>
              </motion.div>
            )
          })}
        </div>
      ) : (
        <Card padding="lg">
          <EmptyState
            icon={<Cpu className="w-12 h-12" />}
            title="No assets found"
            description={search ? `No results for "${search}"` : 'No assets match the current filter'}
            action={
              <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setFilterStatus('all') }}>
                Clear filters
              </Button>
            }
          />
        </Card>
      )}
    </div>
  )
}
