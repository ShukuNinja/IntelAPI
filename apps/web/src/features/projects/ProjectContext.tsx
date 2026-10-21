import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { projectService, type Project } from './projectService'

interface ProjectContextValue {
  projects: Project[]
  project: Project | null
  loading: boolean
  error: string | null
  selectProject: (projectId: string) => void
  refreshProjects: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedId, setSelectedId] = useState(() => localStorage.getItem('intelapi.projectId') ?? '')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await projectService.list()
      setProjects(result.items)
      setSelectedId((current) => {
        const next = result.items.some((item) => item.id === current) ? current : (result.items[0]?.id ?? '')
        if (next) localStorage.setItem('intelapi.projectId', next)
        else localStorage.removeItem('intelapi.projectId')
        return next
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load projects.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refreshProjects() }, [refreshProjects])

  const selectProject = useCallback((projectId: string) => {
    setSelectedId(projectId)
    if (projectId) localStorage.setItem('intelapi.projectId', projectId)
  }, [])

  const value = useMemo(() => ({
    projects,
    project: projects.find((item) => item.id === selectedId) ?? null,
    loading,
    error,
    selectProject,
    refreshProjects,
  }), [projects, selectedId, loading, error, selectProject, refreshProjects])

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useProject() {
  const value = useContext(ProjectContext)
  if (!value) throw new Error('useProject must be used within ProjectProvider.')
  return value
}
