import { useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError, apiRequest } from '../../lib/apiClient'
import { useAuth } from './AuthContext'

interface GoogleConfig {
  client_id: string
}

interface GoogleCredentialResponse {
  credential: string
}

interface GoogleIdentity {
  initialize: (options: {
    client_id: string
    callback: (response: GoogleCredentialResponse) => void
  }) => void
  renderButton: (
    element: HTMLElement,
    options: {
      theme: 'outline'
      size: 'large'
      text: 'signin_with'
      shape: 'rectangular'
      width: number
    },
  ) => void
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: GoogleIdentity
      }
    }
  }
}

const GOOGLE_SCRIPT_ID = 'google-identity-services'

export function LoginPage() {
  const buttonRef = useRef<HTMLDivElement>(null)
  const { status, signInWithGoogle } = useAuth()

  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === 'authenticated') return

    let cancelled = false

    async function initializeGoogleSignIn() {
      try {
        const config = await apiRequest<GoogleConfig>(
          '/v1/auth/google/config',
        )

        if (!config.client_id) {
          throw new Error('Google sign-in is not configured on the API.')
        }

        const renderButton = () => {
          if (cancelled || !buttonRef.current || !window.google) return

          window.google.accounts.id.initialize({
            client_id: config.client_id,
            callback: (response) => {
              if (!response.credential || cancelled) {
                setMessage('Google did not return a valid credential.')
                return
              }

              setBusy(true)
              setMessage(null)

              void signInWithGoogle(response.credential)
                .catch((err: unknown) => {
                  setMessage(
                    err instanceof ApiError
                      ? `Sign-in failed (${err.status}). Check the API response and server logs.`
                      : err instanceof Error
                        ? err.message
                        : 'Google sign-in failed.',
                  )
                })
                .finally(() => setBusy(false))
            },
          })

          buttonRef.current.replaceChildren()

          window.google.accounts.id.renderButton(buttonRef.current, {
            theme: 'outline',
            size: 'large',
            text: 'signin_with',
            shape: 'rectangular',
            width: 280,
          })
        }

        let script = document.getElementById(
          GOOGLE_SCRIPT_ID,
        ) as HTMLScriptElement | null

        if (window.google) {
          renderButton()
          return
        }

        if (!script) {
          script = document.createElement('script')
          script.id = GOOGLE_SCRIPT_ID
          script.src = 'https://accounts.google.com/gsi/client'
          script.async = true
          script.defer = true
          document.head.appendChild(script)
        }

        script.addEventListener('load', renderButton)

        script.addEventListener(
          'error',
          () => {
            if (!cancelled) {
              setMessage('Could not load Google sign-in. Check your network connection.')
            }
          },
          { once: true },
        )
      } catch (err) {
        if (!cancelled) {
          setMessage(
            err instanceof Error
              ? err.message
              : 'Could not initialize Google sign-in.',
          )
        }
      }
    }

    void initializeGoogleSignIn()

    return () => {
      cancelled = true
    }
  }, [signInWithGoogle, status])

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: '#f5f7fb',
        color: '#172033',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <section
        style={{
          width: '100%',
          maxWidth: 420,
          padding: 36,
          border: '1px solid #e2e7ef',
          borderRadius: 16,
          background: '#fff',
          boxShadow: '0 12px 36px rgba(20, 35, 60, 0.07)',
          textAlign: 'center',
        }}
      >
        <h1 style={{ margin: '0 0 8px', fontSize: 28 }}>IntelAPI</h1>
        <p style={{ margin: '0 0 28px', color: '#667085' }}>
          Sign in to your API Intelligence workspace.
        </p>

        {status === 'loading' ? (
          <p>Checking your session…</p>
        ) : (
          <>
            <div
              ref={buttonRef}
              style={{
                minHeight: 44,
                display: 'flex',
                justifyContent: 'center',
              }}
            />

            {busy && <p>Signing you in…</p>}

            {message && (
              <p role="alert" style={{ color: '#b42318', fontSize: 14 }}>
                {message}
              </p>
            )}

            {status === 'error' && (
              <button type="button" onClick={() => window.location.reload()}>
                Retry
              </button>
            )}
          </>
        )}
      </section>
    </main>
  )
}