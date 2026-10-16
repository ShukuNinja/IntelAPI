/**
 * Central API boundary. Keep UI components independent of transport details.
 * The backend is not implemented yet, so pages currently use demoData.ts.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const requestId = response.headers.get('x-request-id') ?? undefined
    const message = `API request failed (${response.status})`
    throw new ApiError(message, response.status, requestId)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const apiClientConfig = { baseUrl: API_BASE_URL || '(same origin)' }