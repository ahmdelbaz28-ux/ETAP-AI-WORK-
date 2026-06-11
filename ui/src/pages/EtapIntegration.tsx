import { MdCable, MdSettingsEthernet } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

export function EtapIntegration() {
  const { notify } = useNotify()

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <MdCable className="text-3xl text-brand-400" />
        <h2 className="text-2xl font-bold text-white">ETAP Integration</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 space-y-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2"><MdSettingsEthernet className="text-brand-400" /> Connection Status</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-surface-400">Worker URL:</span><p className="text-white mt-0.5">Not configured</p></div>
            <div><span className="text-surface-400">License:</span><p className="text-white mt-0.5">Not connected</p></div>
            <div><span className="text-surface-400">Worker Status:</span><p className="text-amber-400 mt-0.5">Offline</p></div>
            <div><span className="text-surface-400">Projects:</span><p className="text-white mt-0.5">0</p></div>
          </div>
          <button onClick={() => notify('info', 'ETAP connection requires Windows with ETAP installed')}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium transition-colors">
            Connect to ETAP
          </button>
        </div>

        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 space-y-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2"><MdCable className="text-brand-400" /> Recent Studies</h3>
          <div className="space-y-2">
            {['Load Flow - Industrial Plant', 'Short Circuit - Substation B', 'Arc Flash - MCC Panel'].map((s, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-2 bg-surface-700 rounded-lg">
                <span className="text-sm text-white">{s}</span>
                <span className="text-xs text-green-400">Completed</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
