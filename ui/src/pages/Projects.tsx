import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { FolderOpen, Plus, FlaskConical, Calendar, Loader2, AlertCircle, Archive, Trash2 } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardSection, Badge, Button, EmptyState } from '../components/ui'
import ModalBackdrop from '../components/ModalBackdrop'
import ModalHeader from '../components/ModalHeader'
import { ContextHelpButton } from '../components/help/ContextHelpButton'
import {
  listProjects,
  createProject,
  updateProject,
  deleteProject,
  type Project,
} from '../lib/api'

interface ProjectFormState {
  name: string
  description: string
}

const EMPTY_FORM: ProjectFormState = { name: '', description: '' }

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [form, setForm] = useState<ProjectFormState>(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const { notify } = useNotify()

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listProjects()
      setProjects(data.projects ?? [])
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setError(msg)
      setProjects([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const handleCreate = useCallback(async () => {
    if (!form.name.trim()) {
      notify('error', 'Project name is required')
      return
    }
    setSubmitting(true)
    try {
      const created = await createProject({
        name: form.name.trim(),
        description: form.description.trim(),
      })
      notify('success', `Project "${created.name}" created`)
      setShowCreateModal(false)
      setForm(EMPTY_FORM)
      await fetchProjects()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      notify('error', `Failed to create project: ${msg}`)
    } finally {
      setSubmitting(false)
    }
  }, [form, notify, fetchProjects])

  const handleArchive = useCallback(async (project: Project) => {
    setActionInProgress(project.id)
    try {
      await updateProject(project.id, { status: 'archived' })
      notify('success', `Project "${project.name}" archived`)
      await fetchProjects()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      notify('error', `Failed to archive: ${msg}`)
    } finally {
      setActionInProgress(null)
    }
  }, [notify, fetchProjects])

  const handleDelete = useCallback(async (project: Project) => {
    if (!confirm(`Permanently delete project "${project.name}"? This cannot be undone.`)) return
    setActionInProgress(project.id)
    try {
      await deleteProject(project.id)
      notify('success', `Project "${project.name}" deleted`)
      await fetchProjects()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      notify('error', `Failed to delete: ${msg}`)
    } finally {
      setActionInProgress(null)
    }
  }, [notify, fetchProjects])

  const activeCount = projects.filter(p => p.status === 'active').length
  const archivedCount = projects.filter(p => p.status === 'archived').length

  const formatDate = (iso: string): string => {
    try {
      return new Date(iso).toISOString().split('T')[0]
    } catch {
      return iso
    }
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <FolderOpen className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Projects</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">
                {activeCount} active · {archivedCount} archived
              </p>
              <ContextHelpButton contextId="projects.manage" />
            </div>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowCreateModal(true)}>
          New Project
        </Button>
      </motion.div>

      {loading && (
        <Card padding="lg">
          <div className="flex items-center justify-center py-12 text-[var(--text-muted)]">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading projects...
          </div>
        </Card>
      )}

      {error && !loading && (
        <Card padding="lg">
          <div className="flex items-start gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium">Failed to load projects</p>
              <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">{error}</p>
              <Button variant="ghost" size="sm" className="mt-3" onClick={fetchProjects}>
                Retry
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!loading && !error && projects.length > 0 && (
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
                      <p className="text-xs text-[var(--text-muted)]">{project.description || 'No description'}</p>
                    </div>
                  </div>
                  <Badge variant={project.status === 'active' ? 'success' : 'default'} dot size="sm">
                    {project.status}
                  </Badge>
                </div>
                <CardSection>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                      <span className="flex items-center gap-1.5">
                        <FlaskConical className="w-3.5 h-3.5" />
                        Studies
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5" />
                        Modified: {formatDate(project.updated_at || project.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      {project.status === 'active' && (
                        <button
                          onClick={() => handleArchive(project)}
                          disabled={actionInProgress === project.id}
                          title="Archive project"
                          className="p-1.5 rounded text-[var(--text-muted)] hover:text-amber-400 hover:bg-amber-400/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          <Archive className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(project)}
                        disabled={actionInProgress === project.id}
                        title="Delete project"
                        className="p-1.5 rounded text-[var(--text-muted)] hover:text-red-400 hover:bg-red-400/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </CardSection>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {!loading && !error && projects.length === 0 && (
        <Card padding="lg">
          <EmptyState
            icon={<FolderOpen className="w-12 h-12" />}
            title="No projects yet"
            description="Create your first power system project to get started. Projects are stored in the platform database and shared across your team."
            action={
              <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowCreateModal(true)}>
                New Project
              </Button>
            }
          />
        </Card>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <ModalBackdrop onClose={() => setShowCreateModal(false)} disabled={submitting}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="Create New Project"
              onClose={() => setShowCreateModal(false)}
              disabled={submitting}
              icon={Plus}
            />

            <div className="space-y-4">
              <div>
                <label htmlFor="project-name" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
                  Project Name <span className="text-red-400">*</span>
                </label>
                <input
                  id="project-name"
                  type="text"
                  aria-label="Project Name"
                  value={form.name}
                  onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g., Industrial Plant - 13.8kV"
                  autoFocus
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !submitting) handleCreate()
                  }}
                />
              </div>
              <div>
                <label htmlFor="project-description" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
                  Description
                </label>
                <textarea
                  id="project-description"
                  aria-label="Description"
                  value={form.description}
                  onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="e.g., Main industrial facility power system with 5 motors and 2 transformers"
                  rows={3}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreateModal(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={submitting ? Loader2 : Plus}
                onClick={handleCreate}
                disabled={submitting || !form.name.trim()}
                className={submitting ? 'animate-pulse' : ''}
              >
                {submitting ? 'Creating...' : 'Create Project'}
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}
    </div>
  )
}
