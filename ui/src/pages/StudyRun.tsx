import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Play, CheckCircle, XCircle, ArrowLeft,
  Clock, ChevronDown, ChevronUp,
  Zap, AlertTriangle, BarChart3
} from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { runStudy } from '../lib/api'
import { studyCategories } from '../lib/studyCategories'
import { Card, CardHeader, Badge, Button, Toggle, Tabs, TabPanels, useTabState } from '../components/ui'
import { cn } from '../utils/helpers'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
// One-line diagram SVG component for study results visualization
function OneLineDiagram() {
  return (
    <div className="bg-[var(--bg-primary)] rounded-lg p-4 border border-[var(--border-primary)]">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[var(--text-secondary)]">System One-Line Diagram</h4>
        <Badge variant="info" size="sm">Simplified View</Badge>
      </div>
      <svg viewBox="0 0 600 300" className="w-full h-auto" style={{ minHeight: 200 }}>
        {/* Grid */}
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--border-primary)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="600" height="300" fill="url(#grid)" />

        {/* Bus 1 - Slack */}
        <line x1="50" y1="100" x2="250" y2="100" className="one-line-bus" />
        <circle cx="50" cy="100" r="15" className="one-line-generator" />
        <text x="50" y="104" textAnchor="middle" fill="var(--text-primary)" fontSize="10" fontWeight="bold">G1</text>
        <text x="50" y="130" textAnchor="middle" fill="var(--color-engine-voltage)" fontSize="9">1.05 pu</text>
        <text x="150" y="90" textAnchor="middle" fill="var(--text-tertiary)" fontSize="9">Bus 1 (Slack)</text>

        {/* Line 1-2 */}
        <line x1="250" y1="100" x2="400" y2="100" stroke="var(--color-surface-400)" strokeWidth="1.5" />
        <text x="325" y="90" textAnchor="middle" fill="var(--text-muted)" fontSize="8">L1: R=0.01 X=0.05</text>

        {/* Bus 2 - PV */}
        <line x1="400" y1="100" x2="550" y2="100" className="one-line-bus" />
        <circle cx="400" cy="60" r="12" className="one-line-generator" />
        <text x="400" y="64" textAnchor="middle" fill="var(--text-primary)" fontSize="9" fontWeight="bold">G2</text>
        <line x1="400" y1="72" x2="400" y2="100" stroke="var(--color-engine-power)" strokeWidth="1.5" />
        <text x="475" y="90" textAnchor="middle" fill="var(--text-tertiary)" fontSize="9">Bus 2 (PV)</text>

        {/* Transformer symbol */}
        <circle cx="400" cy="160" r="10" className="one-line-transformer" />
        <circle cx="400" cy="180" r="10" className="one-line-transformer" />
        <line x1="400" y1="100" x2="400" y2="150" stroke="var(--color-engine-impedance)" strokeWidth="1.5" />

        {/* Bus 3 - PQ */}
        <line x1="300" y1="200" x2="500" y2="200" className="one-line-bus" />
        <line x1="400" y1="190" x2="400" y2="200" stroke="var(--color-engine-impedance)" strokeWidth="1.5" />

        {/* Load symbol */}
        <polygon points="350,230 380,230 365,260" className="one-line-load" />
        <line x1="365" y1="200" x2="365" y2="230" stroke="var(--color-engine-current)" strokeWidth="1.5" />
        <text x="365" y="275" textAnchor="middle" fill="var(--color-engine-current)" fontSize="9">1.0 + j0.3</text>
        <text x="400" y="215" textAnchor="middle" fill="var(--text-tertiary)" fontSize="9">Bus 3 (PQ)</text>

        {/* Voltage labels */}
        <rect x="245" y="104" width="30" height="14" rx="3" fill="var(--color-engine-voltage)" opacity="0.2" />
        <text x="260" y="114" textAnchor="middle" fill="var(--color-engine-voltage)" fontSize="8" fontWeight="bold">1.05</text>
        <rect x="395" y="104" width="30" height="14" rx="3" fill="var(--color-engine-voltage)" opacity="0.2" />
        <text x="410" y="114" textAnchor="middle" fill="var(--color-engine-voltage)" fontSize="8" fontWeight="bold">1.00</text>

        {/* Legend */}
        <rect x="10" y="260" width="180" height="35" rx="4" fill="var(--bg-card)" stroke="var(--border-primary)" />
        <circle cx="25" cy="272" r="4" className="one-line-generator" />
        <text x="33" y="276" fill="var(--text-muted)" fontSize="7">Generator</text>
        <line x1="80" y1="272" x2="95" y2="272" className="one-line-bus" />
        <text x="100" y="276" fill="var(--text-muted)" fontSize="7">Bus</text>
        <polygon points="140,268 150,268 145,276" className="one-line-load" />
        <text x="155" y="276" fill="var(--text-muted)" fontSize="7">Load</text>
        <text x="25" y="290" fill="var(--text-muted)" fontSize="7">Voltage in pu</text>
      </svg>
    </div>
  )
}

// Result summary component
function ResultSummary({ result }: { result: Record<string, unknown> }) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center border border-[var(--border-primary)]">
        <Zap className="w-4 h-4 text-[var(--color-engine-voltage)] mx-auto mb-1" />
        <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering">
          {(result.data as Record<string, unknown>)?.voltage_profile ? 'Computed' : 'N/A'}
        </p>
        <p className="text-[10px] text-[var(--text-muted)]">Voltage Profile</p>
      </div>
      <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center border border-[var(--border-primary)]">
        <BarChart3 className="w-4 h-4 text-[var(--color-engine-power)] mx-auto mb-1" />
        <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering">
          {(result.data as Record<string, unknown>)?.power_flow ? 'Computed' : 'N/A'}
        </p>
        <p className="text-[10px] text-[var(--text-muted)]">Power Flow</p>
      </div>
      <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center border border-[var(--border-primary)]">
        <AlertTriangle className="w-4 h-4 text-[var(--color-engine-fault)] mx-auto mb-1" />
        <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering">
          {(result.data as Record<string, unknown>)?.losses ? 'Computed' : 'N/A'}
        </p>
        <p className="text-[10px] text-[var(--text-muted)]">Losses</p>
      </div>
      <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center border border-[var(--border-primary)]">
        <Clock className="w-4 h-4 text-[var(--color-engine-impedance)] mx-auto mb-1" />
        <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering">
          {result.duration_ms ? `${result.duration_ms}ms` : 'N/A'}
        </p>
        <p className="text-[10px] text-[var(--text-muted)]">Duration</p>
      </div>
    </div>
  )
}

export default function StudyRun() {
  const { studyType } = useParams<{ studyType: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { notify } = useNotify()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [dryRun, setDryRun] = useState(false)
  const [showFullResult, setShowFullResult] = useState(false)
  const { activeTab, setActiveTab } = useTabState('diagram')

  const category = studyCategories.find(s => s.id === studyType)

  if (!studyType || !category) {
    return (
      <div className="text-center py-12">
        <p className="text-[var(--text-tertiary)]">{t('common.noData')}</p>
        <button onClick={() => navigate('/studies')} className="mt-3 text-brand-400 hover:underline text-sm">
          &larr; {t('studyRun.backToStudies')}
        </button>
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setRunning(true)
    setResult(null)
    const formData = new FormData(e.currentTarget)
    const params: Record<string, unknown> = {}
    formData.forEach((v, k) => { params[k] = v })

    try {
      const res = await runStudy(studyType, params, dryRun)
      setResult(res as unknown as Record<string, unknown> | null)
      notify(res.status === 'dry_run' ? 'success' : res.status === 'completed' ? 'success' : 'error',  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
        res.status === 'dry_run' ? t('studyRun.dryRunCompleted') : res.status === 'completed' ? t('studyRun.completed') : `${t('studyRun.failed')}: ${res.status}`)  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
    } catch (err) {
      notify('error', `${t('studyRun.failed')}: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/studies')} icon={ArrowLeft} />
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <span className="text-2xl">{category.icon}</span>
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">{category.name}</h2>
            <div className="flex items-center gap-2">
              <p className="text-[var(--text-tertiary)] text-sm">{category.description}</p>
              <ContextHelpButton contextId="studies.overview" />
            </div>
          </div>
          {category.standard && (
            <Badge variant="brand">{category.standard}</Badge>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card padding="lg">
          <CardHeader
            title="Parameters"
            subtitle="Configure the study execution"
            icon={<Zap className="w-4 h-4" />}
          />
          <form onSubmit={handleSubmit} className="space-y-5">
            <Toggle
              checked={dryRun}
              onChange={setDryRun}
              label={t('studyRun.dryRun')}
              description="Validate inputs without computation"
            />

            <hr className="border-[var(--border-primary)]" />

            {/* Parameters */}
            <div className="grid grid-cols-1 gap-4">
              {category.params.map(p => (
                <div key={p.name}>
                  <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5 capitalize">
                    {p.label || p.name.replace(/_/g, ' ')}
                  </label>
                  {p.type === 'select' ? (
                    <select name={p.name} defaultValue={p.default}
                      className="w-full px-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-colors">
                      {p.name === 'method' && <><option value="newton-raphson">Newton-Raphson</option><option value="gauss-seidel">Gauss-Seidel</option><option value="fast-decoupled">Fast Decoupled</option></>}
                      {p.name === 'standard' && <><option value="iec60909">IEC 60909</option><option value="ieee1584">IEEE 1584</option></>}
                      {p.name === 'fault_type' && <><option value="three_phase">Three-Phase</option><option value="line_to_ground">Line-to-Ground</option><option value="line_to_line">Line-to-Line</option><option value="double_line_to_ground">Double Line-to-Ground</option></>}
                      {p.name === 'starting_method' && <><option value="across_the_line">Across-the-Line</option><option value="star_delta">Star-Delta</option><option value="vsd">VSD</option></>}
                      {p.name === 'objective' && <><option value="min_cost">Minimize Cost</option><option value="min_loss">Minimize Loss</option><option value="max_load">Maximize Load</option></>}
                      {p.name !== 'method' && p.name !== 'standard' && p.name !== 'fault_type' && p.name !== 'starting_method' && p.name !== 'objective' && <option value={String(p.default)}>{String(p.default)}</option>}
                    </select>
                  ) : (
                    <input type={p.type} name={p.name} defaultValue={p.default}
                      className="w-full px-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-colors mono-engineering" />
                  )}
                </div>
              ))}
            </div>

            {/* Submit */}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={running}
              icon={Play}
              className="w-full"
            >
              {dryRun ? t('studyRun.validateStudy') : t('studyRun.runStudy')}
            </Button>
          </form>
        </Card>

        {/* Visualization / Results */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Result Status */}
              <Card
                padding="md"
                className={cn(
                  result.status === 'completed' || result.status === 'dry_run' ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'
                )}
              >
                <div className="flex items-center gap-2 mb-3">
                  {result.status === 'completed' || result.status === 'dry_run' ? <CheckCircle className="text-green-400 w-5 h-5" /> : <XCircle className="text-red-400 w-5 h-5" />}
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">{t('studyRun.studyResult')}</h3>
                  <Badge variant={result.status === 'completed' || result.status === 'dry_run' ? 'success' : 'danger'} className="ml-auto">
                    {String(result.status)}
                  </Badge>
                </div>
                <ResultSummary result={result} />
              </Card>

              {/* Tabs for different views */}
              <Card padding="md">
                <Tabs
                  tabs={[
                    { id: 'diagram', label: 'One-Line Diagram' },
                    { id: 'data', label: 'Raw Data' },
                  ]}
                  activeTab={activeTab}
                  onChange={setActiveTab}
                />
                <TabPanels>
                  {activeTab === 'diagram' && <OneLineDiagram />}
                  {activeTab === 'data' && (
                    <div className="relative">
                      <button
                        onClick={() => setShowFullResult(!showFullResult)}
                        className="absolute top-2 right-2 p-1.5 rounded-md hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                      >
                        {showFullResult ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      <pre className={cn(
                        'text-xs text-[var(--text-secondary)] overflow-x-auto bg-[var(--bg-primary)] rounded-lg p-4 font-mono leading-relaxed border border-[var(--border-primary)]',
                        !showFullResult && 'max-h-96 overflow-y-auto'
                      )}>
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </div>
                  )}
                </TabPanels>
              </Card>
            </>
          ) : (
            <Card padding="lg">
              <div className="text-center py-12">
                <div className="w-16 h-16 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-8 h-8 text-[var(--text-muted)]" />
                </div>
                <h3 className="text-base font-medium text-[var(--text-secondary)]">Ready to Run</h3>
                <p className="text-sm text-[var(--text-muted)] mt-1 max-w-xs mx-auto">
                  Configure the parameters and click Run Study to see results and visualizations here.
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
