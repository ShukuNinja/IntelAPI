import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, apiRequest } from '../../lib/apiClient'

export interface AuthUser {
  id: string
  email: string | null
  display_name: string | null
  avatar_url: string | null
  created_at: string
}

interface AuthContextValue {
  user: AuthUser | null
  status: 'loading' | 'authenticated' | 'unauthenticated' | 'error'
  error: string | null
  refreshUser: () => Promise<void>
  signInWithGoogle: (idToken: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readCsrfToken(): string {
  const cookie = document.cookie
    .split('; ')
    .find((item) => item.startsWith('csrf_token='))

  return cookie ? decodeURIComponent(cookie.substring('csrf_token='.length)) : ''
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] =
    useState<AuthContextValue['status']>('loading')
  const [error, setError] = useState<string | null>(null)

  const refreshUser = useCallback(async () => {
    setStatus('loading')
    setError(null)

    try {
      const currentUser = await apiRequest<AuthUser>('/v1/auth/me')
      setUser(currentUser)
      setStatus('authenticated')
    } catch (err) {
      setUser(null)

      if (err instanceof ApiError && err.status === 401) {
        setStatus('unauthenticated')
        return
      }

      setStatus('error')
      setError(err instanceof Error ? err.message : 'Unable to verify session.')
    }
  }, [])

  useEffect(() => {
    void refreshUser()
  }, [refreshUser])

  const signInWithGoogle = useCallback(async (idToken: string) => {
    setError(null)

    const authenticatedUser = await apiRequest<AuthUser>(
      '/v1/auth/google/session',
      {
        method: 'POST',
        body: JSON.stringify({ id_token: idToken }),
      },
    )

    setUser(authenticatedUser)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    setError(null)

    try {
      const csrfToken = readCsrfToken()

      if (!csrfToken) {
        throw new Error('CSRF token is missing. Refresh the page and try again.')
      }

      await apiRequest<void>('/v1/auth/logout', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Logout failed.')
      throw err
    }

    setUser(null)
    setStatus('unauthenticated')
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, status, error, refreshUser, signInWithGoogle, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider.')
  }

  return context
}