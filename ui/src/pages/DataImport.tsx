import { useState, useCallback, useRef } from 'react'
import { motion } from 'framer-motion'
import { Upload, CloudUpload, FileJson, FileSpreadsheet, FileText, Database, Cable, Loader2, AlertCircle, CheckCircle2, X } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Badge } from '../components/ui'
import { ContextHelpButton } from '../components/help/ContextHelpButton'
import { API_BASE_URL } from '../lib/api-config'

interface FormatInfo {
  id: string
  name: string
  icon: React.ReactNode
  desc: string
  standard: string
  ext: string
}

const supportedFormats: FormatInfo[] = [
  { id: 'cim-xml',       name: 'CIM/XML',       icon: <FileText className="w-5 h-5" />,      desc: 'IEC Common Information Model',  standard: 'IEC 61970',  ext: '.xml, .cim' },
  { id: 'psse-raw',      name: 'PSS/E RAW',     icon: <Database className="w-5 h-5" />,      desc: 'Siemens PSS/E format',          standard: 'PSS/E v35',  ext: '.raw' },
  { id: 'matpower',      name: 'MATPOWER',      icon: <FileJson className="w-5 h-5" />,      desc: 'MATLAB power system',           standard: 'MATPOWER',   ext: '.m' },
  { id: 'etap-project',  name: 'ETAP Project',  icon: <Cable className="w-5 h-5" />,         desc: 'ETAP native format',            standard: 'ETAP',       ext: '.json, .etap' },
  { id: 'json',          name: 'JSON',          icon: <FileJson className="w-5 h-5" />,      desc: 'Structured data import',        standard: 'Custom',     ext: '.json' },
  { id: 'csv',           name: 'CSV',           icon: <FileSpreadsheet className="w-5 h-5" />, desc: 'Comma-separated values',      standard: 'Custom',     ext: '.csv, .tsv' },
]

interface ImportResult {
  success: boolean
  format: string
  filename: string
  file_size_bytes: number
  parsed_at: string
  buses: Array<{ id: string; name: string | null; voltage_kv: number | null; type: string | null }>
  branches: Array<{ id: string; from_bus: string; to_bus: string; type: string | null }>
  metadata: Record<string, unknown>
  warnings: string[]
  errors: string[]
}

export default function DataImport() {
  const { notify } = useNotify()
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadFile = useCallback(async (file: File) => {
    setUploading(true)
    setResult(null)
    try {
      const token = localStorage.getItem('authToken')
      const formData = new FormData()
      formData.append('file', file)

      const r = await fetch(`${API_BASE_URL}/api/v1/import/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        signal: AbortSignal.timeout(60000),
      })

      const data = await r.json()
      if (!r.ok) {
        const detail = data.detail || data.message || `HTTP ${r.status}`
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }

      setResult(data as ImportResult)
      if (data.success) {
        notify('success', `Imported ${file.name}: ${data.buses.length} buses, ${data.branches.length} branches`)
      } else {
        notify('error', `Import failed: ${data.errors.join('; ') || 'unknown error'}`)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      notify('error', `Upload failed: ${msg}`)
      setResult({
        success: false,
        format: 'unknown',
        filename: file.name,
        file_size_bytes: file.size,
        parsed_at: new Date().toISOString(),
        buses: [],
        branches: [],
        metadata: {},
        warnings: [],
        errors: [msg],
      })
    } finally {
      setUploading(false)
    }
  }, [notify])

  const handleFile = useCallback((file: File | undefined) => {
    if (!file) return
    if (file.size > 20 * 1024 * 1024) {
      notify('error', `File too large: ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum: 20 MB.`)
      return
    }
    uploadFile(file)
  }, [notify, uploadFile])

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    handleFile(file)
  }, [handleFile])

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
  }, [])

  const handleFormatClick = useCallback((format: FormatInfo) => {
    // Trigger file picker with format-specific accept filter
    if (fileInputRef.current) {
      const extMap: Record<string, string> = {
        'cim-xml': '.xml,.cim,.rdf',
        'psse-raw': '.raw,.psse',
        'matpower': '.m,.matpower',
        'etap-project': '.json,.etap',
        'json': '.json',
        'csv': '.csv,.tsv',
      }
      fileInputRef.current.accept = extMap[format.id] || '*'
      fileInputRef.current.click()
    }
  }, [])

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Upload className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Data Import</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Import power system models from industry-standard formats</p>
              <ContextHelpButton contextId="data-import.overview" />
            </div>
          </div>
        </div>
      </motion.div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {/* Upload Drop Zone */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card
          padding="lg"
          className={`border-dashed border-2 cursor-pointer transition-colors ${
            dragActive
              ? 'border-[var(--color-brand-500)] bg-brand-500/5'
              : 'border-[var(--border-secondary)] hover:border-[var(--color-brand-500)]/50'
          }`}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          <div
            className="text-center py-6"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <div className="w-16 h-16 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center mx-auto mb-4">
              {uploading ? (
                <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
              ) : (
                <CloudUpload className="w-8 h-8 text-[var(--text-muted)]" />
              )}
            </div>
            <h3 className="text-base font-medium text-[var(--text-primary)]">
              {uploading ? 'Uploading and parsing...' : 'Drop files here or click to browse'}
            </h3>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Supported: {supportedFormats.map(f => f.name).join(', ')}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-2">
              Maximum file size: 20 MB · Files are parsed on the server
            </p>
          </div>
        </Card>
      </motion.div>

      {/* Import Result */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Card padding="md">
            <CardHeader
              title="Import Result"
              subtitle={`${result.filename} · ${(result.file_size_bytes / 1024).toFixed(1)} KB`}
              icon={result.success ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <AlertCircle className="w-4 h-4 text-red-400" />}
              action={
                <button
                  onClick={() => setResult(null)}
                  className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
                  aria-label="Dismiss"
                >
                  <X className="w-4 h-4" />
                </button>
              }
            />
            <div className="space-y-3 mt-3">
              <div className="flex items-center gap-2">
                <Badge variant={result.success ? 'success' : 'danger'} dot>
                  {result.success ? 'SUCCESS' : 'FAILED'}
                </Badge>
                <Badge variant="default">{result.format}</Badge>
              </div>

              {result.success && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[var(--bg-primary)] rounded-lg p-3 border border-[var(--border-primary)]">
                    <p className="text-xs text-[var(--text-muted)]">Buses</p>
                    <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{result.buses.length}</p>
                  </div>
                  <div className="bg-[var(--bg-primary)] rounded-lg p-3 border border-[var(--border-primary)]">
                    <p className="text-xs text-[var(--text-muted)]">Branches</p>
                    <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{result.branches.length}</p>
                  </div>
                </div>
              )}

              {result.warnings.length > 0 && (
                <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
                  <p className="text-xs font-medium text-amber-400 mb-1">Warnings ({result.warnings.length})</p>
                  <ul className="text-xs text-[var(--text-secondary)] space-y-0.5 max-h-32 overflow-y-auto">
{result.warnings.slice(0, 10).map((w, i) => {
                       const warningKey = `warning-${w.substring(0, 50).replace(/\s/g, '_')}`
                       return (
                         <li key={warningKey} className="font-mono">{w}</li>
                       )
                     })}
                    {result.warnings.length > 10 && (
                      <li className="text-[var(--text-muted)] italic">... and {result.warnings.length - 10} more</li>
                    )}
                  </ul>
                </div>
              )}

              {result.errors.length > 0 && (
                <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                  <p className="text-xs font-medium text-red-400 mb-1">Errors</p>
                  <ul className="text-xs text-[var(--text-secondary)] space-y-0.5">
{result.errors.map((e, i) => {
                       const errorKey = `error-${e.substring(0, 50).replace(/\s/g, '_')}`
                       return (
                         <li key={errorKey} className="font-mono">{e}</li>
                       )
                     })}
                  </ul>
                </div>
              )}

              {result.success && result.buses.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                    Show parsed buses ({result.buses.length})
                  </summary>
                  <div className="mt-2 max-h-48 overflow-y-auto bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <table className="w-full">
                      <thead className="sticky top-0 bg-[var(--bg-elevated)]">
                        <tr className="text-left text-[var(--text-muted)]">
                          <th className="p-2 font-medium">ID</th>
                          <th className="p-2 font-medium">Name</th>
                          <th className="p-2 font-medium">Voltage (kV)</th>
                          <th className="p-2 font-medium">Type</th>
                        </tr>
                      </thead>
                      <tbody>
{result.buses.slice(0, 100).map((b, i) => {
                           const busKey = `bus-${b.id}`
                           return (
                             <tr key={busKey} className="border-t border-[var(--border-primary)]">
                               <td className="p-2 font-mono text-[var(--text-primary)]">{b.id}</td>
                               <td className="p-2 text-[var(--text-secondary)]">{b.name || '—'}</td>
                               <td className="p-2 mono-engineering text-[var(--text-primary)]">{b.voltage_kv ?? '—'}</td>
                               <td className="p-2 text-[var(--text-secondary)]">{b.type || '—'}</td>
                             </tr>
                           )
                         })}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Supported Formats */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card padding="md">
          <CardHeader
            title="Supported Formats"
            subtitle="Click a format to select a file for upload"
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
                onClick={() => !uploading && handleFormatClick(format)}
              >
                <div className="text-brand-400 flex items-center justify-center mb-2">
                  {format.icon}
                </div>
                <p className="text-xs font-medium text-[var(--text-primary)] font-mono">{format.name}</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">{format.desc}</p>
                <p className="text-[10px] text-[var(--text-tertiary)] mt-1">{format.ext}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
