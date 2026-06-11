import { MdFileDownload, MdPictureAsPdf, MdTableChart, MdCode } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

export function DataExport() {
  const { notify } = useNotify()
  const formats = [
    { id: 'pdf', name: 'PDF Report', icon: MdPictureAsPdf, desc: 'Professional engineering report' },
    { id: 'xlsx', name: 'Excel Spreadsheet', icon: MdTableChart, desc: 'Tabular data for further analysis' },
    { id: 'json', name: 'JSON Export', icon: MdCode, desc: 'Raw data for integration' },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Data Export</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {formats.map(f => (
          <button key={f.id}
            onClick={() => notify('success', `Exporting as ${f.name}...`) }
            className="bg-surface-800 rounded-xl p-6 border border-surface-700 hover:border-brand-500/30 hover:bg-surface-750 transition-all text-left">
            <f.icon className="text-3xl text-brand-400 mb-3" />
            <h3 className="text-white font-semibold">{f.name}</h3>
            <p className="text-sm text-surface-400 mt-1">{f.desc}</p>
          </button>
        ))}
      </div>

      <div className="bg-surface-800 rounded-xl p-5 border border-surface-700">
        <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2"><MdFileDownload className="text-brand-400" /> Recent Exports</h3>
        <div className="space-y-2">
          {['load_flow_results.pdf', 'short_circuit_analysis.xlsx', 'system_model.json'].map((f, i) => (
            <div key={i} className="flex items-center justify-between px-3 py-2 bg-surface-700 rounded-lg">
              <span className="text-sm text-white font-mono">{f}</span>
              <button onClick={() => notify('info', 'Download started')}
                className="text-brand-400 hover:text-brand-300 text-sm"><MdFileDownload /></button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
