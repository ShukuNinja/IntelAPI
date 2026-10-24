import { createContext, useContext } from 'react'

export type Project = { id: string; name: string; description?: string | null }

export type ProjectWorkspaceValue = {
  projects: Project[]
  activeProjectId: string
  setActiveProjectId: (projectId: string) => void
  createProject: (name: string) => Promise<Project>
  loadingProjects: boolean
  projectError: string
}

export const ProjectWorkspaceContext = createContext<ProjectWorkspaceValue | null>(null)

export function useProjectWorkspace() {
  const value = useContext(ProjectWorkspaceContext)
  if (!value) throw new Error('Project workspace controls are unavailable.')
  return value
}
