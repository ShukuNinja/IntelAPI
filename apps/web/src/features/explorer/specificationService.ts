import { apiRequest } from '../../lib/apiClient'

export interface Specification {
  id: string
  project_id: string
  name: string
  source_kind: string
  source_url: string | null
  content_sha256: string
  openapi_version: string | null
  created_at: string
  operation_count: number
}

export interface ApiOperation {
  id: string
  specification_id: string
  operation_key: string
  method: string
  path_template: string
  summary: string | null
  operation_document: Record<string, unknown>
  created_at: string
}

export interface KnowledgeFact {
  id: string
  fact_type: string
  subject: string
  fact_value: Record<string, unknown>
  provenance: string
  confidence: number | null
  source_ref: Record<string, unknown>
  created_at: string
}

export interface CandidatePreview {
  items: Array<{ candidate_id: string; category: string; title: string; rationale: string; method: string; path: string }>
  persisted: false
  llm_status: string
  llm_error: string | null
}

export const specificationService = {
  list(projectId: string) {
    return apiRequest<{ items: Specification[]; pagination: { limit: number; offset: number; total: number } }>(`/v1/projects/${projectId}/specifications`)
  },
  import(projectId: string, payload: { content: string } | { url: string }) {
    return apiRequest<Specification>(`/v1/projects/${projectId}/specifications/import`, { method: 'POST', body: JSON.stringify(payload) })
  },
  operations(specId: string) {
    return apiRequest<{ items: ApiOperation[]; pagination: { limit: number; offset: number; total: number } }>(`/v1/specifications/${specId}/operations`)
  },
  facts(operationId: string) {
    return apiRequest<KnowledgeFact[]>(`/v1/operations/${operationId}/knowledge-facts`)
  },
  preview(operationId: string) {
    return apiRequest<CandidatePreview>(`/v1/operations/${operationId}/candidates/preview`, { method: 'POST', body: JSON.stringify({}) })
  },
}
