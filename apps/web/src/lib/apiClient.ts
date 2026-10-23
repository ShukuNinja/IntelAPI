/**
 * Central API boundary. Keep UI components independent of transport details.
 * Pages use this transport boundary for real backend workflows.
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
    let message = `API request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown; message?: unknown }
      if (typeof body.detail === 'string') message = body.detail
      else if (typeof body.message === 'string') message = body.message
    } catch { /* Keep the HTTP status message when the server returns no JSON body. */ }
    throw new ApiError(message, response.status, requestId)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    credentials: 'include',
    headers: { Accept: '*/*' },
  })
  if (!response.ok) {
    let message = `API request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch { /* Keep the HTTP status message for non-JSON errors. */ }
    throw new ApiError(message, response.status, response.headers.get('x-request-id') ?? undefined)
  }
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}

export const apiClientConfig = { baseUrl: API_BASE_URL || '(same origin)' }
