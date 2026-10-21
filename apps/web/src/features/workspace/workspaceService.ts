import { apiRequest } from '../../lib/apiClient'
import type { HttpMethod } from './executionService'

export interface SavedRequest {
  id: string
  project_id: string
  collection_id: string | null
  environment_id: string | null
  name: string
  method: HttpMethod
  url_template: string
  headers: Record<string, string>
  query_params: Record<string, string>
  body: unknown | null
  body_type: 'none' | 'json' | 'text' | 'form_urlencoded' | 'multipart'
  created_at: string
  updated_at: string
}

export interface ExecutionRecord {
  id: string
  project_id: string
  saved_request_id: string | null
  environment_id: string | null
  status: string
  method: string
  url: string
  response_status_code: number | null
  response_headers: Record<string, string>
  response_body: string | null
  duration_ms: number | null
  error_code: string | null
  error_message: string | null
  created_at: string
  evidence: Array<{ id: string; kind: string; severity: string; title: string; message: string; details: Record<string, unknown>; created_at: string }>
}

export const workspaceService = {
  listRequests(projectId: string) {
    return apiRequest<{ items: SavedRequest[]; pagination: { limit: number; offset: number; total: number } }>(`/v1/projects/${projectId}/requests`)
  },
  saveRequest(projectId: string, request: Omit<SavedRequest, 'id' | 'project_id' | 'created_at' | 'updated_at'>) {
    return apiRequest<SavedRequest>(`/v1/projects/${projectId}/requests`, { method: 'POST', body: JSON.stringify(request) })
  },
  updateRequest(id: string, request: Omit<SavedRequest, 'id' | 'project_id' | 'created_at' | 'updated_at'>) {
    return apiRequest<SavedRequest>(`/v1/requests/${id}`, { method: 'PATCH', body: JSON.stringify(request) })
  },
  deleteRequest(id: string) {
    return apiRequest<void>(`/v1/requests/${id}`, { method: 'DELETE' })
  },
  executeRequest(id: string, environmentId: string | null) {
    return apiRequest<ExecutionRecord>(`/v1/requests/${id}/execute`, { method: 'POST', body: JSON.stringify({ environment_id: environmentId }) })
  },
  listExecutions(projectId: string) {
    return apiRequest<{ items: ExecutionRecord[]; total: number; limit: number; offset: number }>(`/v1/projects/${projectId}/executions`)
  },
}
