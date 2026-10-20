
import { apiRequest } from '../../lib/apiClient'

export interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
  archived_at: string | null
}

export interface ProjectList {
  items: Project[]
  pagination: {
    limit: number
    offset: number
    total: number
  }
}

export interface ProjectCreateInput {
  name: string
  description: string | null
}

export type ProjectUpdateInput = Partial<ProjectCreateInput>

export const projectService = {
  list(): Promise<ProjectList> {
    return apiRequest<ProjectList>('/v1/projects')
  },

  create(input: ProjectCreateInput): Promise<Project> {
    return apiRequest<Project>('/v1/projects', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  update(
    projectId: string,
    input: ProjectUpdateInput,
  ): Promise<Project> {
    return apiRequest<Project>(`/v1/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    })
  },

  archive(projectId: string): Promise<Project> {
    return apiRequest<Project>(`/v1/projects/${projectId}/archive`, {
      method: 'POST',
    })
  },
}