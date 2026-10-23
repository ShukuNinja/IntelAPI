import { apiRequest } from '../../lib/apiClient'

export type ExperimentApproach =
  | 'llm_baseline'
  | 'semantic_assisted'
  | 'feedback_guided'
  | 'evidence_backed'

export interface ExperimentRun {
  id: string
  campaign_id: string
  approach: ExperimentApproach
  state: string
  configuration: Record<string, unknown>
  generation_metadata: Record<string, unknown>
  candidate_count: number
  execution_count: number
}

export interface Experiment {
  id: string
  project_id: string
  specification_id: string
  name: string
  configuration: Record<string, unknown>
  state: string
  created_at: string
  updated_at: string
  runs: ExperimentRun[]
}

export interface MetricValue {
  value: number | string | null
  unavailable_reason: string | null
}

export type ExperimentMetric = MetricValue | Record<string, number>

export interface LlmProviderOption {
  id: 'nvidia' | 'groq'
  configured: boolean
  model: string
}

export interface LlmProviderOptions {
  default_provider: 'nvidia' | 'groq'
  providers: LlmProviderOption[]
}

export interface ExperimentComparison {
  experiment: Experiment
  metrics_by_approach: Record<string, Record<string, ExperimentMetric>>
}

export const approachDetails: Record<ExperimentApproach, { title: string; description: string }> = {
  llm_baseline: {
    title: 'LLM baseline',
    description: 'Generate from the OpenAPI operation without semantic facts or execution feedback.',
  },
  semantic_assisted: {
    title: 'Semantic assisted',
    description: 'Add extracted, source-linked API facts to the same generation prompt.',
  },
  feedback_guided: {
    title: 'Feedback guided',
    description: 'Use previous execution outcomes to choose the next candidate from the pool.',
  },
  evidence_backed: {
    title: 'Evidence backed',
    description: 'Prioritize operation and category coverage using recorded execution evidence.',
  },
}

export const experimentService = {
  providers() {
    return apiRequest<LlmProviderOptions>('/v1/meta/llm-providers')
  },
  list(projectId: string) {
    return apiRequest<{ items: Experiment[]; total: number; limit: number; offset: number }>(
      `/v1/projects/${projectId}/experiments`,
    )
  },
  create(projectId: string, payload: {
    name: string
    operation_ids: string[]
    environment_id: string
    approaches: ExperimentApproach[]
    categories: string[]
    use_llm: boolean
    llm_provider?: 'nvidia' | 'groq'
    llm_model?: string
  }) {
    return apiRequest<Experiment>(`/v1/projects/${projectId}/experiments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  compare(id: string) {
    return apiRequest<ExperimentComparison>(`/v1/experiments/${id}/comparison`)
  },
}
