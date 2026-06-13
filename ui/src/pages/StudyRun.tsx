import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Play, CheckCircle, XCircle, ArrowLeft, FileCheck } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { runStudy } from '../lib/api'
import { studyCategories } from '../lib/studyCategories'
import { cn } from '../utils/helpers'

export function StudyRun() {
  const { studyType } = useParams<{ studyType: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { notify } = useNotify()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [dryRun, setDryRun] = useState(false)

  const category = studyCategories.find(s => s.id === studyType)

  if (!studyType || !category) {
    return (
      <div className="text-center py-12">
        <p className="text-surface-400">{t('common.noData')}</p>
        <button onClick={() => navigate('/studies')} className="mt-3 text-brand-400 hover:underline text-sm">← {t('studyRun.backToStudies')}</button>
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
      notify(res.status === 'dry_run' ? 'success' : res.status === 'completed' ? 'success' : 'error',
        res.status === 'dry_run' ? t('studyRun.dryRunCompleted') : res.status === 'completed' ? t('studyRun.completed') : `${t('studyRun.failed')}: ${res.status}`)
    } catch (err) {
      notify('error', `${t('studyRun.failed')}: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setRunning(false)
    }
  }

  const isSuccess = result && (result.status === 'completed' || result.status === 'dry_run')

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/studies')} className="p-2 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="p-2 rounded-lg bg-brand-500/10">
            <span className="text-2xl">{category.icon}</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">{category.name}</h2>
            <p className="text-surface-400 text-sm">{category.description}</p>
          </div>
          {category.standard && (
            <span className="ml-auto text-xs font-medium text-brand-400 bg-brand-500/10 border border-brand-500/20 px-3 py-1 rounded-full">
              {category.standard}
            </span>
          )}
        </div>
      </motion.div>

      {/* Form */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className="bg-surface-800 rounded-xl p-6 border border-surface-700">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Dry Run Toggle */}
          <label className="flex items-center gap-3 cursor-pointer group">
            <div className={cn(
              'w-10 h-5 rounded-full transition-colors relative',
              dryRun ? 'bg-brand-500' : 'bg-surface-600'
            )}>
              <div className={cn(
                'absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform shadow-sm',
                dryRun ? 'translate-x-5' : 'translate-x-0.5'
              )} />
            </div>
            <div>
              <span className="text-sm text-surface-200 group-hover:text-white transition-colors">{t('studyRun.dryRun')}</span>
              <div className="flex items-center gap-1 text-[10px] text-surface-500 mt-0.5">
                <FileCheck className="w-3 h-3" />
                Validate inputs without computation
              </div>
            </div>
          </label>

          <hr className="border-surface-700" />

          {/* Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {category.params.map(p => (
              <div key={p.name}>
                <label className="block text-sm font-medium text-surface-300 mb-1.5 capitalize">
                  {p.label || p.name.replace(/_/g, ' ')}
                </label>
                {p.type === 'select' ? (
                  <select name={p.name} defaultValue={p.default}
                    className="w-full px-3 py-2.5 bg-surface-900 border border-surface-600 rounded-lg text-white text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-colors">
                    {p.name === 'method' && <><option value="newton-raphson">Newton-Raphson</option><option value="gauss-seidel">Gauss-Seidel</option><option value="fast-decoupled">Fast Decoupled</option></>}
                    {p.name === 'standard' && <><option value="iec60909">IEC 60909</option><option value="ieee1584">IEEE 1584</option></>}
                    {p.name === 'fault_type' && <><option value="three_phase">Three-Phase</option><option value="line_to_ground">Line-to-Ground</option><option value="line_to_line">Line-to-Line</option><option value="double_line_to_ground">Double Line-to-Ground</option></>}
                    {p.name === 'starting_method' && <><option value="across_the_line">Across-the-Line</option><option value="star_delta">Star-Delta</option><option value="vsd">VSD</option></>}
                    {p.name === 'objective' && <><option value="min_cost">Minimize Cost</option><option value="min_loss">Minimize Loss</option><option value="max_load">Maximize Load</option></>}
                    {p.name !== 'method' && p.name !== 'standard' && p.name !== 'fault_type' && p.name !== 'starting_method' && p.name !== 'objective' && <option value={String(p.default)}>{String(p.default)}</option>}
                  </select>
                ) : (
                  <input type={p.type} name={p.name} defaultValue={p.default}
                    className="w-full px-3 py-2.5 bg-surface-900 border border-surface-600 rounded-lg text-white text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 outline-none transition-colors font-mono" />
                )}
              </div>
            ))}
          </div>

          {/* Submit */}
          <button type="submit" disabled={running}
            className={cn(
              'flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all',
              running
                ? 'bg-surface-700 text-surface-400 cursor-not-allowed'
                : 'bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-600/20 hover:shadow-brand-500/30'
            )}>
            {running ? (
              <><span className="animate-spin rounded-full h-4 w-4 border-2 border-surface-400 border-t-transparent" />{t('studyRun.running')}</>
            ) : (
              <><Play className="w-4 h-4" />{dryRun ? t('studyRun.validateStudy') : t('studyRun.runStudy')}</>
            )}
          </button>
        </form>
      </motion.div>

      {/* Results */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className={cn(
            'rounded-xl p-5 border',
            isSuccess ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'
          )}>
          <div className="flex items-center gap-2 mb-3">
            {isSuccess ? <CheckCircle className="text-green-400 w-5 h-5" /> : <XCircle className="text-red-400 w-5 h-5" />}
            <h3 className="text-lg font-semibold text-white">{t('studyRun.studyResult')}</h3>
            <span className={cn(
              'ml-auto text-xs px-2.5 py-0.5 rounded-full font-medium',
              isSuccess ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
            )}>
              {String(result.status)}
            </span>
          </div>
          <pre className="text-xs text-surface-300 overflow-x-auto bg-surface-900 rounded-lg p-4 max-h-96 overflow-y-auto font-mono leading-relaxed">
            {JSON.stringify(result, null, 2)}
          </pre>
        </motion.div>
      )}
    </div>
  )
}
