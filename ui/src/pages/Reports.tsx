import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { FileText, Table, Download, Calendar, AlertCircle } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, Badge, Button } from '../components/ui'
import { API_BASE_URL } from '../lib/api-config'
import { ContextHelpButton } from '../components/help/ContextHelpButton'

interface Report {
  name: string
  type: string
  format: string
  date: string
  status: string
}

const formatIcons: Record<string, React.ReactNode> = {
  PDF: <FileText className="w-4 h-4 text-red-400" />,
  XLSX: <Table className="w-4 h-4 text-green-400" />,
  CSV: <Table className="w-4 h-4 text-amber-400" />,
}

export default function Reports() {
  const { notify } = useNotify()
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('authToken')
    fetch(`${API_BASE_URL}/api/v1/reports`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => {
        if (!r.ok) {
          throw new Error(`API ${r.status}: ${r.statusText}`)
        }
        return r.json()
      })
      .then((data: Report[]) => {
        setReports(data)
        setError(null) // Clear any previous error on successful fetch
      })
      .catch(err => {
        console.error('Failed to load reports:', err)
        setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [])

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
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">{generatedCount} generated · {pendingCount} pending</p>
              <ContextHelpButton contextId="reports.generate" />
            </div>
          </div>
        </div>
      </motion.div>

      {/* Reports Table */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
{loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
           <div className="flex items-center justify-center h-32">
             <div className="w-6 h-6 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
           </div>
         )}
         {error && !loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
           <Card>
             <div className="flex items-center gap-3 p-4 text-sm text-[var(--text-tertiary)]">
               <AlertCircle className="w-5 h-5 text-red-400" />
               <span>Failed to load reports: {error}</span>
             </div>
           </Card>
         )}
         {!loading && !error && reports.length === 0 && (
           <Card>
             <div className="flex flex-col items-center gap-2 py-8 text-sm text-[var(--text-tertiary)]">
               <FileText className="w-8 h-8 text-[var(--text-muted)]" />
               <p>No reports generated yet.</p>
               <p className="text-xs text-[var(--text-muted)]">Run a study to generate a report.</p>
             </div>
           </Card>
         )}
         {!loading && !error && reports.length > 0 && (
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
              key={i}  // NOSONAR — S6479: array index as key; items lack stable IDs (tech debt)
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
        )}
      </motion.div>
    </div>
  )
}