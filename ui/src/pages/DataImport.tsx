import { motion } from 'framer-motion'
import { Upload, CloudUpload, FileJson, FileSpreadsheet, FileText, Database, Cable } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import {Card, CardHeader} from '../components/ui/Card'

const supportedFormats = [
  { name: 'CIM/XML', icon: <FileText className="w-5 h-5" />, desc: 'IEC Common Information Model' },
  { name: 'PSS/E RAW', icon: <Database className="w-5 h-5" />, desc: 'Siemens PSS/E format' },
  { name: 'MATPOWER', icon: <FileJson className="w-5 h-5" />, desc: 'MATLAB power system' },
  { name: 'ETAP Project', icon: <Cable className="w-5 h-5" />, desc: 'ETAP native format' },
  { name: 'JSON', icon: <FileJson className="w-5 h-5" />, desc: 'Structured data import' },
  { name: 'CSV', icon: <FileSpreadsheet className="w-5 h-5" />, desc: 'Comma-separated values' },
]

export function DataImport() {
  const { notify } = useNotify()

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Upload className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Data Import</h2>
            <p className="text-sm text-[var(--text-tertiary)]">Import power system models and data</p>
          </div>
        </div>
      </motion.div>

      {/* Upload Drop Zone */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card
          padding="lg"
          className="border-dashed border-2 border-[var(--border-secondary)] hover:border-[var(--color-brand-500)]/50 cursor-pointer transition-colors"
          onClick={() => notify('info', 'Import functionality coming soon')}
        >
          <div className="text-center py-6">
            <div className="w-16 h-16 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center mx-auto mb-4">
              <CloudUpload className="w-8 h-8 text-[var(--text-muted)]" />
            </div>
            <h3 className="text-base font-medium text-[var(--text-primary)]">Drop files here or click to browse</h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Supported: {supportedFormats.map(f => f.name).join(', ')}
            </p>
          </div>
        </Card>
      </motion.div>

      {/* Supported Formats */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card padding="md">
          <CardHeader
            title="Supported Formats"
            subtitle="Power system data formats"
            icon={<Database className="w-4 h-4" />}
          />
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {supportedFormats.map((format, i) => (
              <motion.div
                key={format.name}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.03 * i }}
                className="p-4 text-center bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)] hover:border-[var(--color-brand-500)]/30 hover:bg-[var(--bg-elevated)]/50 transition-all cursor-pointer"
                onClick={() => notify('info', `Import ${format.name} coming soon`)}
              >
                <div className="text-brand-400 flex items-center justify-center mb-2">
                  {format.icon}
                </div>
                <p className="text-xs font-medium text-[var(--text-primary)] font-mono">{format.name}</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{format.desc}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
