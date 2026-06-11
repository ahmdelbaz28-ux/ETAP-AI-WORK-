import { MdDescription, MdPictureAsPdf, MdTableChart, MdDownload } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

export function Reports() {
  const { notify } = useNotify()

  const reports = [
    { name: 'Load Flow Report - Industrial Plant', type: 'Load Flow', format: 'PDF', date: '2026-06-10', status: 'generated' },
    { name: 'Short Circuit Report - Substation B', type: 'Short Circuit', format: 'XLSX', date: '2026-06-09', status: 'generated' },
    { name: 'Arc Flash Study - MCC Panel', type: 'Arc Flash', format: 'PDF', date: '2026-06-08', status: 'generated' },
    { name: 'Harmonic Analysis - Solar Farm', type: 'Harmonic', format: 'PDF', date: '2026-06-07', status: 'pending' },
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Reports</h2>

      <div className="bg-surface-800 rounded-xl border border-surface-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-700">
            <tr>
              {['Report', 'Type', 'Format', 'Date', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-surface-300 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map((r, i) => (
              <tr key={i} className="border-t border-surface-700 hover:bg-surface-700/50 transition-colors">
                <td className="px-4 py-3 text-white">{r.name}</td>
                <td className="px-4 py-3 text-surface-300">{r.type}</td>
                <td className="px-4 py-3">
                  {r.format === 'PDF' ? <MdPictureAsPdf className="text-red-400" /> :
                   r.format === 'XLSX' ? <MdTableChart className="text-green-400" /> :
                   <MdDescription className="text-surface-400" />}
                </td>
                <td className="px-4 py-3 text-surface-400">{r.date}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${r.status === 'generated' ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'}`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => notify('success', `Downloading ${r.name}`)}
                    className="text-brand-400 hover:text-brand-300 transition-colors"><MdDownload /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
