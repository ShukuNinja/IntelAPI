
/**
 * Central API boundary.
 * Automatically includes cookies and CSRF protection for state-changing requests.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

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

function readCsrfToken(): string | null {
  const cookie = document.cookie
    .split('; ')
    .find((item) => item.startsWith('csrf_token='))

  if (!cookie) return null

  return decodeURIComponent(cookie.substring('csrf_token='.length))
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const headers = new Headers(init?.headers)

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  // Attach CSRF protection automatically to state-changing requests.
  if (!SAFE_METHODS.has(method) && !headers.has('X-CSRF-Token')) {
    const csrfToken = readCsrfToken()

    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken)
    }
  }

  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...init,
    method,
    credentials: 'include',
    headers,
  })

  if (!response.ok) {
    const requestId = response.headers.get('x-request-id') ?? undefined
    throw new ApiError(
      `API request failed (${response.status})`,
      response.status,
      requestId,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const apiClientConfig = {
  baseUrl: API_BASE_URL || '(same origin)',
}