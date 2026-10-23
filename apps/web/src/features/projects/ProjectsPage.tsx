
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { FolderKanban, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import {
  projectService,
  type Project,
} from './projectService'
import { useProject } from './ProjectContext'

export function ProjectsPage() {
  const { refreshProjects } = useProject()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const result = await projectService.list()
      setProjects(result.items)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load projects.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  function openCreateForm() {
    setEditingProject(null)
    setName('')
    setDescription('')
    setShowForm(true)
    setError(null)
  }

  function openEditForm(project: Project) {
    setEditingProject(project)
    setName(project.name)
    setDescription(project.description ?? '')
    setShowForm(true)
    setError(null)
  }

  function closeForm() {
    setShowForm(false)
    setEditingProject(null)
    setName('')
    setDescription('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const normalizedName = name.trim()

    if (!normalizedName) {
      setError('Project name is required.')
      return
    }

    setSaving(true)
    setError(null)

    try {
      if (editingProject) {
        await projectService.update(editingProject.id, {
          name: normalizedName,
          description: description.trim() || null,
        })
      } else {
        await projectService.create({
          name: normalizedName,
          description: description.trim() || null,
        })
      }

      closeForm()
      await loadProjects()
      await refreshProjects()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to save the project.',
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(project: Project) {
    const confirmed = window.confirm(
      `Delete "${project.name}" from active projects? Its saved records will remain archived.`,
    )

    if (!confirmed) return

    setError(null)

    try {
      await projectService.delete(project.id)
      setProjects((current) =>
        current.filter((item) => item.id !== project.id),
      )
      await refreshProjects()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to delete the project.',
      )
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="WORKSPACE MANAGEMENT"
        title="Projects"
        description="Create and manage your API testing workspaces."
        actions={
          <Button variant="primary" onClick={openCreateForm}>
            <Plus size={16} />
            New project
          </Button>
        }
      />

      {error && (
        <div className="notice notice--demo" role="alert">
          <div>
            <strong>Project operation failed</strong>
            <p>{error}</p>
            <Button size="sm" onClick={() => void loadProjects()}>
              <RefreshCw size={14} />
              Retry loading
            </Button>
          </div>
        </div>
      )}

      {showForm && (
        <Panel
          title={editingProject ? 'Edit project' : 'Create a project'}
          subtitle="Project details are saved to your account."
        >
          <form className="project-form" onSubmit={handleSubmit}>
            <label className="project-form__field">
              Project name
              <input
                autoFocus
                required
                maxLength={120}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Payments API"
              />
            </label>

            <label className="project-form__field">
              Description
              <textarea
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What are you testing in this project?"
              />
            </label>

            <div className="project-form__actions">
              <Button type="button" onClick={closeForm} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={saving}>
                {saving
                  ? 'Saving…'
                  : editingProject
                    ? 'Save changes'
                    : 'Create project'}
              </Button>
            </div>
          </form>
        </Panel>
      )}

      <Panel
        title="Your projects"
        subtitle={`${projects.length} active project${projects.length === 1 ? '' : 's'}`}
        action={
          <Button
            size="sm"
            onClick={() => void loadProjects()}
            disabled={loading}
          >
            <RefreshCw size={14} />
            Refresh
          </Button>
        }
      >
        {loading ? (
          <p className="muted-cell">Loading projects…</p>
        ) : projects.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Create a project to organize your API testing work."
            action={
              <Button variant="primary" onClick={openCreateForm}>
                <Plus size={16} />
                Create your first project
              </Button>
            }
          />
        ) : (
          <div className="project-list">
            {projects.map((project) => (
              <article className="project-row" key={project.id}>
                <span className="project-row__icon">
                  <FolderKanban size={20} />
                </span>

                <div className="project-row__content">
                  <strong>{project.name}</strong>
                  <p>{project.description || 'No description provided.'}</p>
                  <small>
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </small>
                </div>

                <div className="project-row__actions">
                  <Button
                    size="sm"
                    onClick={() => openEditForm(project)}
                    aria-label={`Edit ${project.name}`}
                  >
                    <Pencil size={14} />
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => void handleDelete(project)}
                    aria-label={`Delete ${project.name}`}
                  >
                    <Trash2 size={14} />
                    Delete
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </>
  )
}
