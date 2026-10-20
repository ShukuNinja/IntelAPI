
import { apiRequest } from '../../lib/apiClient'

export type HttpMethod =
  | 'GET'
  | 'POST'
  | 'PUT'
  | 'PATCH'
  | 'DELETE'
  | 'HEAD'
  | 'OPTIONS'

export interface ExecutionRequest {
  method: HttpMethod
  url: string
  headers: Record<string, string>
  query_params: Record<string, string>
  body: string | null
}

export interface ExecutionResponse {
  status_code: number
  headers: Record<string, string>
  body: string
  duration_ms: number
  size_bytes: number
  final_url: string
}

export const executionService = {
  execute(request: ExecutionRequest): Promise<ExecutionResponse> {
    return apiRequest<ExecutionResponse>('/v1/executions/', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
}