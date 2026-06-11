import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { MdPlayArrow, MdCheckCircle, MdError } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'
import { runStudy } from '../lib/api'
import { studyCategories } from '../lib/studyCategories'

export function StudyRun() {
  const { studyType } = useParams<{ studyType: string }>()
  const navigate = useNavigate()
  const { notify } = useNotify()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [dryRun, setDryRun] = useState(false)

  const category = studyCategories.find(s => s.id === studyType)

  if (!studyType || !category) {
    return (
      <div className="text-center py-12">
        <p className="text-surface-400">Study type not found.</p>
        <button onClick={() => navigate('/studies')} className="mt-3 text-brand-400 hover:underline text-sm">← Back to Studies</button>
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
      setResult(res)
      notify(res.status === 'dry_run' ? 'success' : res.status === 'completed' ? 'success' : 'error',
        res.status === 'dry_run' ? 'Dry-run completed' : res.status === 'completed' ? 'Study completed' : `Study failed: ${res.status}`)
    } catch (err) {
      notify('error', `Execution failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/studies')} className="text-surface-400 hover:text-white transition-colors">← Back</button>
        <h2 className="text-2xl font-bold text-white">{category.name}</h2>
      </div>

      <div className="bg-surface-800 rounded-xl p-6 border border-surface-700">
        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} className="rounded" />
            <span className="text-sm text-surface-300">Dry Run (validate only, no computation)</span>
          </label>

          {category.params.map(p => (
            <div key={p.name}>
              <label className="block text-sm font-medium text-surface-300 mb-1 capitalize">{p.name.replace(/_/g, ' ')}</label>
              {p.type === 'select' ? (
                <select name={p.name} defaultValue={p.default}
                  className="w-full px-3 py-2 bg-surface-900 border border-surface-600 rounded-lg text-white text-sm focus:border-brand-500 outline-none">
                  {p.name === 'method' && <><option value="newton-raphson">Newton-Raphson</option><option value="gauss-seidel">Gauss-Seidel</option></>}
                  {p.name === 'standard' && <><option value="iec60909">IEC 60909</option><option value="ieee1584">IEEE 1584</option></>}
                  {p.name === 'fault_type' && <><option value="three_phase">Three-Phase</option><option value="line_to_ground">Line-to-Ground</option></>}
                  {p.name === 'starting_method' && <><option value="across_the_line">Across-the-Line</option><option value="vsd">VSD</option></>}
                </select>
              ) : (
                <input type={p.type} name={p.name} defaultValue={p.default}
                  className="w-full px-3 py-2 bg-surface-900 border border-surface-600 rounded-lg text-white text-sm focus:border-brand-500 outline-none" />
              )}
            </div>
          ))}

          <button type="submit" disabled={running}
            className="flex items-center gap-2 px-6 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors">
            {running ? <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> : <MdPlayArrow />}
            {running ? 'Running...' : dryRun ? 'Validate Study' : 'Run Study'}
          </button>
        </form>
      </div>

      {result && (
        <div className={`rounded-xl p-5 border ${result.status === 'completed' || result.status === 'dry_run' ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'}`}>
          <div className="flex items-center gap-2 mb-3">
            {(result.status === 'completed' || result.status === 'dry_run') ? <MdCheckCircle className="text-green-400" /> : <MdError className="text-red-400" />}
            <h3 className="text-lg font-semibold text-white">Study Result</h3>
          </div>
          <pre className="text-xs text-surface-300 overflow-x-auto bg-surface-900 rounded-lg p-4 max-h-96 overflow-y-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
