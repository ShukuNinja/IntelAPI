import { useEffect, useState } from 'react'
import { Activity, LogOut, Settings2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { useAuth } from '../auth/AuthContext'
import { useProject } from '../projects/ProjectContext'
import { apiClientConfig } from '../../lib/apiClient'

export function SettingsPage() {
  const { user, logout } = useAuth()
  const { project } = useProject()
  const navigate = useNavigate()
  const [apiStatus, setApiStatus] = useState<'checking' | 'ready' | 'unavailable'>('checking')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const base = apiClientConfig.baseUrl === '(same origin)' ? '' : apiClientConfig.baseUrl
    void fetch(`${base}/health/ready`, { credentials: 'include' })
      .then(response => { if (active) setApiStatus(response.ok ? 'ready' : 'unavailable') })
      .catch(() => { if (active) setApiStatus('unavailable') })
    return () => { active = false }
  }, [])

  async function signOut() {
    setBusy(true); setError(null)
    try { await logout(); navigate('/login', { replace: true }) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign out.') }
    finally { setBusy(false) }
  }

  return <>
    <PageHeader eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Review your signed-in account, active project, and service connectivity." />
    {error && <div className="notice notice--warning"><strong>Sign out failed</strong><p>{error}</p></div>}
    <Panel title="Account" subtitle="Authenticated with the configured Google sign-in provider."><div className="resource-list"><article className="environment-card"><Settings2 size={18} /><div className="environment-card__body"><strong>{user?.display_name ?? 'Signed-in user'}</strong><small>{user?.email ?? 'No email provided'} · Account created {user ? new Date(user.created_at).toLocaleDateString() : '—'}</small></div><Button variant="danger" disabled={busy} onClick={() => void signOut()}><LogOut size={14} /> Sign out</Button></article></div></Panel>
    <Panel title="Active workspace" subtitle="All saved resources and history are scoped to this project."><div className="environment-card"><div className="environment-card__body"><strong>{project?.name ?? 'No project selected'}</strong><small>{project?.description ?? 'Choose a project from the application header or create one in Projects.'}</small></div></div></Panel>
    <Panel title="Service status" subtitle="Connectivity check from this browser session."><div className="environment-card"><Activity size={18} /><div className="environment-card__body"><strong>API database readiness</strong><small>{apiClientConfig.baseUrl}</small></div><Badge tone={apiStatus === 'ready' ? 'success' : apiStatus === 'unavailable' ? 'danger' : 'info'}>{apiStatus}</Badge></div></Panel>
  </>
}
