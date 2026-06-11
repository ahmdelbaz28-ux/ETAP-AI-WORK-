import { useState, useEffect } from 'react'
import { MdFolder, MdAdd, MdScience } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'archived'
  studyCount: number
  lastModified: string
}

function loadProjects(): Project[] {
  try {
    const stored = localStorage.getItem('etap-projects')
    if (stored) return JSON.parse(stored)
  } catch {}
  return [
    { id: '1', name: 'Industrial Plant - 13.8kV', description: 'Main industrial facility power system', status: 'active', studyCount: 4, lastModified: '2026-06-09' },
    { id: '2', name: 'Substation B - 115kV/13.8kV', description: 'Substation with two transformers', status: 'active', studyCount: 2, lastModified: '2026-06-07' },
    { id: '3', name: 'Solar Farm - 34.5kV', description: '50MW solar PV interconnection', status: 'archived', studyCount: 1, lastModified: '2026-05-20' },
  ]
}

function saveProjects(projects: Project[]) {
  localStorage.setItem('etap-projects', JSON.stringify(projects))
}

export function Projects() {
  const [projects, setProjects] = useState<Project[]>(loadProjects)
  const { notify } = useNotify()

  useEffect(() => { saveProjects(projects) }, [projects])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Projects</h2>
        <button onClick={() => notify('info', 'Project creation coming soon')}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium transition-colors">
          <MdAdd /> New Project
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {projects.map(p => (
          <div key={p.id} className="bg-surface-800 rounded-xl p-5 border border-surface-700 hover:border-brand-500/30 transition-all">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <MdFolder className="text-2xl text-brand-400" />
                <div>
                  <h3 className="text-white font-semibold">{p.name}</h3>
                  <p className="text-sm text-surface-400">{p.description}</p>
                </div>
              </div>
              <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                p.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-surface-600 text-surface-400'
              }`}>{p.status}</span>
            </div>
            <div className="flex items-center gap-4 mt-4 text-xs text-surface-400">
              <span className="flex items-center gap-1"><MdScience className="text-sm" /> {p.studyCount} studies</span>
              <span>Modified: {p.lastModified}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
