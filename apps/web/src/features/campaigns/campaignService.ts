import { apiRequest } from '../../lib/apiClient'

export interface Campaign {
  id: string
  project_id: string
  name: string
  state: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  configuration: { saved_request_ids?: string[]; operation_ids?: string[]; input_type?: string; environment_id: string | null }
  budget_max_executions: number
  budget_max_iterations: number
  budget_max_duration_seconds: number
  started_at: string | null
  completed_at: string | null
  cancel_requested_at: string | null
  failure_code: string | null
  failure_summary: string | null
  created_at: string
  updated_at: string
  test_count: number
  execution_count: number
}
export interface CampaignEvent {
  sequence_number: number
  event_type: string
  payload: Record<string, unknown>
  created_at: string
}
export interface CampaignTestCase {
  id: string
  campaign_id: string
  candidate_key: string
  category: string
  title: string
  description: string | null
  request_override: Record<string, unknown>
  expected_behavior: Record<string, unknown> | null
  generation_provenance: string
  created_at: string
}
export interface CampaignExecution {
  id: string
  test_case_id: string | null
  campaign_id: string | null
  status: string
  method: string
  url: string
  response_status_code: number | null
  duration_ms: number | null
  response_body: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
}
export interface CampaignReport {
  campaign: Campaign
  tests: Record<string, number>
  executions: Record<string, number>
  findings: Record<string, number>
  events: CampaignEvent[]
}

export const campaignService = {
  list(projectId: string) {
    return apiRequest<{ items: Campaign[]; total: number; limit: number; offset: number }>(`/v1/projects/${projectId}/campaigns`)
  },
  create(projectId: string, input: { name: string; saved_request_ids?: string[]; operation_ids?: string[]; categories?: string[]; environment_id: string | null }) {
    return apiRequest<Campaign>(`/v1/projects/${projectId}/campaigns`, { method: 'POST', body: JSON.stringify(input) })
  },
  cancel(id: string) {
    return apiRequest<Campaign>(`/v1/campaigns/${id}/cancel`, { method: 'POST', body: JSON.stringify({}) })
  },
  report(id: string) {
    return apiRequest<CampaignReport>(`/v1/campaigns/${id}/report`)
  },
  tests(id: string) {
    return apiRequest<CampaignTestCase[]>(`/v1/campaigns/${id}/tests`)
  },
  executions(id: string, limit = 100, offset = 0) {
    return apiRequest<{ items: CampaignExecution[]; total: number; limit: number; offset: number }>(`/v1/campaigns/${id}/executions?limit=${limit}&offset=${offset}`)
  },
}
