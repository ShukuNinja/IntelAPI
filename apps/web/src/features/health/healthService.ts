import { apiRequest } from '../../lib/apiClient'

export interface HealthCheck {
  id: string
  project_id: string
  saved_request_id: string | null
  name: string
  definition: { assertions: Array<{ type: string; expected: unknown; target?: string | null }> }
  enabled: boolean
  created_at: string
  updated_at: string
}
export interface AssertionResult {
  id: string
  execution_id: string
  assertion_type: string
  passed: boolean
  execution_status?: 'completed' | 'failed' | null
  expected: unknown
  actual: unknown
  message: string
  created_at: string
}
export interface HealthRun {
  health_check: HealthCheck
  execution_id: string
  status: 'healthy' | 'degraded' | 'unavailable'
  assertions: AssertionResult[]
}

export type HealthAssertionType = 'status_code' | 'response_time_lte' | 'json_path_equals' | 'header_equals' | 'response_schema'
export interface HealthAssertionInput {
  type: HealthAssertionType
  expected: unknown
  target?: string
}

export const healthService = {
  list(projectId: string) {
    return apiRequest<{ items: HealthCheck[]; total: number; limit: number; offset: number }>(`/v1/projects/${projectId}/health-checks`)
  },
  create(projectId: string, name: string, saved_request_id: string, assertion: HealthAssertionInput) {
    return apiRequest<HealthCheck>(`/v1/projects/${projectId}/health-checks`, {
      method: 'POST', body: JSON.stringify({ name, saved_request_id, assertions: [assertion] }),
    })
  },
  run(id: string) {
    return apiRequest<HealthRun>(`/v1/health-checks/${id}/run`, { method: 'POST', body: JSON.stringify({}) })
  },
  results(id: string) {
    return apiRequest<AssertionResult[]>(`/v1/health-checks/${id}/results`)
  },
}
