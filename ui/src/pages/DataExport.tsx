import { motion } from 'framer-motion'
import { Download, FileText, FileSpreadsheet, FileJson, Clock, HardDrive } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Button } from '../components/ui'
import { cn } from '../utils/helpers'

const exportFormats = [
  {
    id: 'pdf',
    name: 'PDF Report',
    icon: <FileText className="w-6 h-6" />,
    desc: 'Professional engineering report with charts and tables',
    color: 'text-red-400',
    bgColor: 'bg-red-500/10',
  },
  {
    id: 'xlsx',
    name: 'Excel Spreadsheet',
    icon: <FileSpreadsheet className="w-6 h-6" />,
    desc: 'Tabular data for further analysis and processing',
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
  },
  {
    id: 'json',
    name: 'JSON Export',
    icon: <FileJson className="w-6 h-6" />,
    desc: 'Raw structured data for API integration',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
  },
]

const recentExports = [
  { name: 'load_flow_results.pdf', size: '2.4 MB', date: '2026-06-10' },
  { name: 'short_circuit_analysis.xlsx', size: '1.1 MB', date: '2026-06-09' },
  { name: 'system_model.json', size: '456 KB', date: '2026-06-08' },
]

export function DataExport() {
  const { notify } = useNotify()

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Download className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Data Export</h2>
            <p className="text-sm text-[var(--text-tertiary)]">Export study results and system data</p>
          </div>
        </div>
      </motion.div>

      {/* Export Format Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {exportFormats.map((format, i) => (
          <motion.div key={format.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
            <Card
              variant="bordered"
              padding="lg"
              className="cursor-pointer"
              onClick={() => notify('success', `Exporting as ${format.name}...`)}
            >
              <div className={cn('p-3 rounded-lg w-fit mb-4', format.bgColor, format.color)}>
                {format.icon}
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">{format.name}</h3>
              <p className="text-sm text-[var(--text-muted)] mt-1.5">{format.desc}</p>
              <div className="mt-4 pt-3 border-t border-[var(--border-primary)]">
                <Button variant="outline" size="sm" icon={Download} className="w-full">
                  Export
                </Button>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Recent Exports */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card padding="md">
          <CardHeader
            title="Recent Exports"
            subtitle="Previously exported files"
            icon={<Clock className="w-4 h-4" />}
          />
          <div className="space-y-3">
            {recentExports.map((file, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-md bg-brand-500/10">
                    <HardDrive className="w-3.5 h-3.5 text-brand-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)] font-mono">{file.name}</p>
                    <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] mt-0.5">
                      <span>{file.size}</span>
                      <span>·</span>
                      <span>{file.date}</span>
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  icon={Download}
                  onClick={() => notify('info', 'Download started')}
                  className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                />
              </div>
            ))}
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
