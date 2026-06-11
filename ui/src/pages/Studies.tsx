import { useNavigate } from 'react-router-dom'
import { MdPlayArrow } from 'react-icons/md'
import { studyCategories } from '../lib/studyCategories'

function StudyGrid() {
  const navigate = useNavigate()
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {studyCategories.map(s => (
        <button
          key={s.id}
          onClick={() => navigate(`/studies/${s.id}`)}
          className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/50 hover:bg-surface-750 transition-all text-left group"
        >
          <span className="text-2xl">{s.icon}</span>
          <h3 className="text-white font-semibold mt-2 group-hover:text-brand-400 transition-colors">{s.name}</h3>
          <p className="text-sm text-surface-400 mt-1">{s.description}</p>
          <div className="flex items-center gap-2 mt-3 text-xs text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity">
            <MdPlayArrow /> Run Study
          </div>
        </button>
      ))}
    </div>
  )
}

export function Studies() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Engineering Studies</h2>
      <p className="text-surface-400">Select a study type to run real engineering computations powered by the Python engine.</p>
      <StudyGrid />
    </div>
  )
}
