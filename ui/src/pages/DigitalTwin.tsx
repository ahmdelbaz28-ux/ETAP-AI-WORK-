import { MdMemory, MdSync, MdTrackChanges } from 'react-icons/md'

export function DigitalTwin() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Digital Twin</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-surface-800 rounded-xl p-5 border border-surface-700 col-span-2">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2"><MdTrackChanges className="text-brand-400" /> System Topology</h3>
          <div className="bg-surface-900 rounded-lg p-6 text-center text-surface-500 min-h-[200px] flex items-center justify-center">
            <div>
              <MdMemory className="text-5xl mx-auto mb-3 opacity-30" />
              <p>Live topology viewer requires connected SCADA/GIS data</p>
              <p className="text-xs mt-1">Connect a data source in Settings or GIS Integration</p>
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2"><MdSync className="text-green-400" /> Sync Status</h3>
            <div className="space-y-2 text-sm">
              {['SCADA Feed: Offline', 'GIS Feed: Not configured', 'ETAP Model: Not synced'].map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-surface-400">
                  <span className={`w-1.5 h-1.5 rounded-full ${s.includes('Offline') || s.includes('Not') ? 'bg-red-400' : 'bg-green-400'}`} />
                  {s}
                </div>
              ))}
            </div>
          </div>
          <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
            <h3 className="text-lg font-semibold text-white mb-3">Quick Stats</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {[['Buses', '0'], ['Lines', '0'], ['Loads', '0'], ['Generators', '0']].map(([k, v]) => (
                <div key={k} className="text-center p-2 bg-surface-700 rounded-lg">
                  <p className="text-xl font-bold text-white">{v}</p>
                  <p className="text-xs text-surface-400">{k}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
