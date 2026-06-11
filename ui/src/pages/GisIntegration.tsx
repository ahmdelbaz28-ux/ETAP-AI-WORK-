import { MdMap, MdLayers, MdCheckCircle, MdError } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

export function GisIntegration() {
  const { notify } = useNotify()

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <MdMap className="text-3xl text-green-400" />
        <h2 className="text-2xl font-bold text-white">GIS Integration</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2"><MdLayers className="text-green-400" /> GIS Providers</h3>
          <div className="space-y-2">
            {[
              { name: 'ArcGIS Provider', status: 'configured', message: 'Ready' },
              { name: 'QGIS Provider', status: 'not_configured', message: 'Not configured' },
            ].map(p => (
              <div key={p.name} className="flex items-center justify-between px-3 py-2 bg-surface-700 rounded-lg">
                <span className="text-sm text-white">{p.name}</span>
                <span className={`flex items-center gap-1 text-xs ${p.status === 'configured' ? 'text-green-400' : 'text-surface-400'}`}>
                  {p.status === 'configured' ? <MdCheckCircle /> : <MdError />}
                  {p.message}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 space-y-4">
          <h3 className="text-lg font-semibold text-white">GIS Validation</h3>
          <div className="space-y-2 text-sm">
            {[
              { label: 'CRS Validator', status: 'pass' },
              { label: 'Topology Validator', status: 'pass' },
              { label: 'Grid Consistency Engine', status: 'warn' },
              { label: 'Impedance Validator', status: 'pass' },
            ].map(v => (
              <div key={v.label} className="flex items-center justify-between">
                <span className="text-surface-300">{v.label}</span>
                <span className={v.status === 'pass' ? 'text-green-400' : 'text-amber-400'}>
                  {v.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
          <button onClick={() => notify('info', 'GIS validation requires connected data sources')}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors">
            Run Validation
          </button>
        </div>
      </div>
    </div>
  )
}
