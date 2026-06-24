import { motion } from 'framer-motion'
import { FileText, Table, Download, Calendar } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, Badge, Button } from '../components/ui'

interface Report {
  name: string
  type: string
  format: string
  date: string
  status: string
}

const reports: Report[] = [
  { name: 'Load Flow Report - Industrial Plant', type: 'Load Flow', format: 'PDF', date: '2026-06-10', status: 'generated' },
  { name: 'Short Circuit Report - Substation B', type: 'Short Circuit', format: 'XLSX', date: '2026-06-09', status: 'generated' },
  { name: 'Arc Flash Study - MCC Panel', type: 'Arc Flash', format: 'PDF', date: '2026-06-08', status: 'generated' },
  { name: 'Harmonic Analysis - Solar Farm', type: 'Harmonic', format: 'PDF', date: '2026-06-07', status: 'pending' },
]

const formatIcons: Record<string, React.ReactNode> = {
  PDF: <FileText className="w-4 h-4 text-red-400" />,
  XLSX: <Table className="w-4 h-4 text-green-400" />,
  CSV: <Table className="w-4 h-4 text-amber-400" />,
}

export default function Reports() {
  const { notify } = useNotify()

  const generatedCount = reports.filter(r => r.status === 'generated').length
  const pendingCount = reports.filter(r => r.status === 'pending').length

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <FileText className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Reports</h2>
            <p className="text-sm text-[var(--text-tertiary)]">{generatedCount} generated · {pendingCount} pending</p>
          </div>
        </div>
      </motion.div>

      {/* Reports Table */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card padding="none">
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)]">
            <div className="col-span-4 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Report</div>
            <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Type</div>
            <div className="col-span-1 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Format</div>
            <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Date</div>
            <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">Status</div>
            <div className="col-span-1 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider"></div>
          </div>

          {/* Table Rows */}
          {reports.map((report, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.05 * i }}
              className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-[var(--border-primary)] last:border-0 hover:bg-[var(--bg-elevated)]/50 transition-colors items-center"
            >
              <div className="col-span-4">
                <p className="text-sm font-medium text-[var(--text-primary)]">{report.name}</p>
              </div>
              <div className="col-span-2">
                <Badge variant="brand" size="sm">{report.type}</Badge>
              </div>
              <div className="col-span-1">
                <div className="flex items-center gap-1.5">
                  {formatIcons[report.format] || <FileText className="w-4 h-4 text-[var(--text-muted)]" />}
                  <span className="text-xs text-[var(--text-muted)]">{report.format}</span>
                </div>
              </div>
              <div className="col-span-2">
                <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                  <Calendar className="w-3 h-3" />
                  {report.date}
                </div>
              </div>
              <div className="col-span-2">
                <Badge variant={report.status === 'generated' ? 'success' : 'warning'} dot size="sm">
                  {report.status}
                </Badge>
              </div>
              <div className="col-span-1 flex justify-end">
                <Button
                  variant="ghost"
                  size="icon"
                  icon={Download}
                  onClick={() => notify('success', `Downloading ${report.name}`)}
                  className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                />
              </div>
            </motion.div>
          ))}
        </Card>
      </motion.div>
    </div>
  )
}
