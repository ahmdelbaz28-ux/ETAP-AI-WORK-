import { MdFileUpload, MdCloudUpload } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

export function DataImport() {
  const { notify } = useNotify()
  const supported = ['CIM/XML', 'PSS/E RAW', 'MATPOWER', 'ETAP Project', 'JSON', 'CSV']

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Data Import</h2>

      <div className="bg-surface-800 rounded-xl p-8 border-2 border-dashed border-surface-600 text-center hover:border-brand-500/50 transition-colors cursor-pointer"
        onClick={() => notify('info', 'Import functionality coming soon')}>
        <MdCloudUpload className="text-5xl text-surface-500 mx-auto mb-3" />
        <p className="text-lg text-white font-medium">Drop files here or click to browse</p>
        <p className="text-sm text-surface-400 mt-1">Supported formats: {supported.join(', ')}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {supported.map(f => (
          <div key={f} className="bg-surface-800 rounded-lg p-4 text-center border border-surface-700 hover:border-brand-500/30 transition-colors">
            <MdFileUpload className="text-2xl text-brand-400 mx-auto mb-2" />
            <p className="text-xs text-surface-300 font-mono">{f}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
