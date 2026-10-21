import { apiRequest } from '../../lib/apiClient'

export interface Finding {
  id: string
  project_id: string
  campaign_id: string | null
  test_case_id: string | null
  execution_id: string | null
  finding_key: string
  title: string
  summary: string
  classification: string
  machine_severity: string
  confidence: number | null
  user_status: string
  user_severity: string | null
  triage_note: string | null
  created_at: string
  updated_at: string
  evidence_count: number
}
export interface EvidenceReference {
  id: string
  project_id: string
  finding_id: string | null
  execution_id: string | null
  assertion_result_id: string | null
  specification_id: string | null
  operation_id: string | null
  knowledge_fact_id: string | null
  provenance: string
  evidence_type: string
  excerpt: string | null
  evidence_metadata: Record<string, unknown>
  created_at: string
}

export const findingsService = {
  list(projectId: string) {
    return apiRequest<{ items: Finding[]; total: number; limit: number; offset: number }>(`/v1/projects/${projectId}/findings`)
  },
  evidence(id: string) {
    return apiRequest<EvidenceReference[]>(`/v1/findings/${id}/evidence`)
  },
  update(id: string, patch: Pick<Finding, 'user_status' | 'user_severity' | 'triage_note'>) {
    return apiRequest<Finding>(`/v1/findings/${id}`, { method: 'PATCH', body: JSON.stringify(patch) })
  },
}
