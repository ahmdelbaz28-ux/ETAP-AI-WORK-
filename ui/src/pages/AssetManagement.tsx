import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Cpu, Zap, Cable, Settings2, Activity, Wrench, Search, Filter } from 'lucide-react'
import { Card, CardSection, Badge, Button, EmptyState } from '../components/ui'
import { cn } from '../utils/helpers'

interface Asset {
  id: string
  name: string
  type: string
  rating: string
  voltage: string
  status: string
}

const defaultAssets: Asset[] = [
  { id: 'T1', name: 'Transformer T1', type: 'Transformer', rating: '50 MVA', voltage: '115/13.8 kV', status: 'active' },
  { id: 'G1', name: 'Generator G1', type: 'Generator', rating: '25 MW', voltage: '13.8 kV', status: 'active' },
  { id: 'CB1', name: 'Circuit Breaker CB-MAIN', type: 'Breaker', rating: '2000A', voltage: '13.8 kV', status: 'active' },
  { id: 'M1', name: 'Motor M-PUMP', type: 'Motor', rating: '250 kW', voltage: '4.16 kV', status: 'maintenance' },
  { id: 'L1', name: 'Line L-MAIN-SWGR', type: 'Line', rating: '500A', voltage: '13.8 kV', status: 'active' },
  { id: 'R1', name: 'Relay REL-01', type: 'Relay', rating: 'Inverse Time', voltage: '13.8 kV', status: 'active' },
]

function loadAssets(): Asset[] {
  try {
    const stored = localStorage.getItem('etap-assets')
    if (stored) return JSON.parse(stored) as Asset[]
  } catch { /* ignore */ }
  return defaultAssets
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
  const [assets] = useState<Asset[]>(loadAssets)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')

  useEffect(() => { localStorage.setItem('etap-assets', JSON.stringify(assets)) }, [assets])

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
            <p className="text-sm text-[var(--text-tertiary)]">{assets.length} assets in inventory</p>
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
                  card.variant === 'warning' ? 'text-amber-400' :
                  card.variant === 'danger' ? 'text-red-400' : 'text-[var(--text-tertiary)]'
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
