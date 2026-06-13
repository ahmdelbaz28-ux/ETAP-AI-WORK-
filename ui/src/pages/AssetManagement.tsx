import { useState, useEffect } from 'react'
import { MdDevices, MdCable, MdMemory, MdBuild } from 'react-icons/md'

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

const typeIcons: Record<string, React.ElementType> = {
  Transformer: MdDevices, Generator: MdMemory, Breaker: MdBuild, Motor: MdCable, Line: MdCable, Relay: MdDevices,
}

export function AssetManagement() {
  const [assets] = useState<Asset[]>(loadAssets)
  useEffect(() => { localStorage.setItem('etap-assets', JSON.stringify(assets)) }, [assets])

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Asset Management</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {(['Active', 'Maintenance', 'Faulted', 'Offline'] as const).map(cat => {
          const count = cat === 'Active' ? assets.filter(a => a.status === 'active').length
            : cat === 'Maintenance' ? assets.filter(a => a.status === 'maintenance').length
            : 0
          return (
            <div key={cat} className="bg-surface-800 rounded-xl p-4 border border-surface-700 text-center">
              <p className="text-sm text-surface-400">{cat}</p>
              <p className="text-2xl font-bold text-white mt-1">{count}</p>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {assets.map(a => {
          const Icon = typeIcons[a.type] || MdDevices
          return (
            <div key={a.id} className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <Icon className="text-2xl text-brand-400" />
                  <div>
                    <h3 className="text-white font-semibold text-sm">{a.name}</h3>
                    <p className="text-xs text-surface-400">{a.type}</p>
                  </div>
                </div>
                <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                  a.status === 'active' ? 'bg-green-500/10 text-green-400' :
                  a.status === 'maintenance' ? 'bg-amber-500/10 text-amber-400' : 'bg-surface-600 text-surface-400'
                }`}>{a.status}</span>
              </div>
              <div className="mt-3 pt-3 border-t border-surface-700 grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-surface-500">Rating:</span><p className="text-white mt-0.5">{a.rating}</p></div>
                <div><span className="text-surface-500">Voltage:</span><p className="text-white mt-0.5">{a.voltage}</p></div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
