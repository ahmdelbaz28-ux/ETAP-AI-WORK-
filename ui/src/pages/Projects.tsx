import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { FolderOpen, Plus, FlaskConical, Calendar, MoreVertical } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, CardSection, Badge, Button, EmptyState } from '../components/ui'
import { cn } from '../utils/helpers'

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
    if (stored) return JSON.parse(stored) as Project[]
  } catch { /* ignore */ }
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
  const [projects] = useState<Project[]>(loadProjects)
  const { notify } = useNotify()

  useEffect(() => { saveProjects(projects) }, [projects])

  const activeCount = projects.filter(p => p.status === 'active').length
  const archivedCount = projects.filter(p => p.status === 'archived').length

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <FolderOpen className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Projects</h2>
            <p className="text-sm text-[var(--text-tertiary)]">
              {activeCount} active · {archivedCount} archived
            </p>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={Plus} onClick={() => notify('info', 'Project creation coming soon')}>
          New Project
        </Button>
      </motion.div>

      {projects.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {projects.map((project, i) => (
            <motion.div key={project.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
              <Card variant="bordered" padding="md">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-brand-500/10">
                      <FolderOpen className="w-5 h-5 text-brand-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{project.name}</h3>
                      <p className="text-xs text-[var(--text-muted)]">{project.description}</p>
                    </div>
                  </div>
                  <Badge variant={project.status === 'active' ? 'success' : 'default'} dot size="sm">
                    {project.status}
                  </Badge>
                </div>
                <CardSection>
                  <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                    <span className="flex items-center gap-1.5">
                      <FlaskConical className="w-3.5 h-3.5" />
                      {project.studyCount} studies
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      Modified: {project.lastModified}
                    </span>
                  </div>
                </CardSection>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : (
        <Card padding="lg">
          <EmptyState
            icon={<FolderOpen className="w-12 h-12" />}
            title="No projects yet"
            description="Create your first power system project to get started"
            action={
              <Button variant="primary" size="sm" icon={Plus} onClick={() => notify('info', 'Project creation coming soon')}>
                New Project
              </Button>
            }
          />
        </Card>
      )}
    </div>
  )
}
