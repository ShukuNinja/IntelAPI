import { useEffect, useState } from 'react'
import { ArrowRight, Clock3, FlaskConical, Plus, RefreshCw, Send } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { useAuth } from '../auth/AuthContext'
import { useProject } from '../projects/ProjectContext'
import { workspaceService, type ExecutionRecord } from '../workspace/workspaceService'

export function OverviewPage() {
  const { user } = useAuth()
  const { project } = useProject()
  const [requestCount, setRequestCount] = useState(0)
  const [executions, setExecutions] = useState<ExecutionRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const displayName = user?.display_name?.trim() || user?.email || 'User'
  const firstName = displayName.split(/\s+/)[0]

  useEffect(() => {
    if (!project) { setRequestCount(0); setExecutions([]); return }
    setLoading(true); setError(null)
    Promise.all([workspaceService.listRequests(project.id), workspaceService.listExecutions(project.id)])
      .then(([requests, history]) => { setRequestCount(requests.pagination.total); setExecutions(history.items) })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unable to load project activity.'))
      .finally(() => setLoading(false))
  }, [project])

  return <>
    <PageHeader
      eyebrow={new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).toUpperCase()}
      title={`Good morning, ${firstName}`}
      description={project ? `Recent activity for ${project.name}.` : 'Select a project to view its API workspace activity.'}
      actions={<><Link to="/workspace"><Button><Plus size={16} /> New request</Button></Link><Link to="/explorer"><Button variant="primary"><FlaskConical size={16} /> Explore API</Button></Link></>}
    />
    {error && <div className="notice notice--warning" role="alert">{error}</div>}
    {!project ? <EmptyState title="No project selected" description="Create a project or use the project selector to open a workspace." action={<Link to="/projects"><Button variant="primary">Manage projects</Button></Link>} /> : <>
      <div className="metrics-grid metrics-grid--three">
        <div className="metric-card"><div className="metric-card__top"><span>Saved requests</span><Send size={16} /></div><div className="metric-card__value">{loading ? '—' : requestCount}</div><div className="metric-card__foot"><span className="metric-period">In this project</span></div></div>
        <div className="metric-card"><div className="metric-card__top"><span>Executions</span><Clock3 size={16} /></div><div className="metric-card__value">{loading ? '—' : executions.length}</div><div className="metric-card__foot"><span className="metric-period">Recent persisted history</span></div></div>
        <div className="metric-card"><div className="metric-card__top"><span>Latest result</span><span className="status-dot status-dot--green" /></div><div className="metric-card__value metric-card__value--small">{loading ? 'Loading' : executions[0]?.response_status_code ?? executions[0]?.status ?? '—'}</div><div className="metric-card__foot"><span className="metric-period">From the latest execution</span></div></div>
      </div>
      <Panel title="Recent executions" subtitle="Persisted request results" action={<Link className="text-link" to="/history">View history <ArrowRight size={14} /></Link>}>
        {loading ? <p className="muted-cell">Loading project activity…</p> : executions.length === 0 ? <EmptyState title="No executions yet" description="Save and run a request in the API Workspace. Its response and evidence will appear here." action={<Link to="/workspace"><Button variant="primary"><Plus size={15} /> Open API Workspace</Button></Link>} /> : <div className="table-wrap"><table><thead><tr><th>REQUEST</th><th>RESULT</th><th>DURATION</th><th>EXECUTED</th></tr></thead><tbody>{executions.slice(0, 5).map((item) => <tr key={item.id}><td><strong>{item.method}</strong><small className="block muted-cell">{item.url}</small></td><td><Badge tone={item.status === 'completed' ? 'success' : 'danger'}>{item.response_status_code ?? item.error_code ?? item.status}</Badge></td><td className="tabular">{item.duration_ms ?? '—'} ms</td><td className="muted-cell">{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
      </Panel>
      <Panel title="Continue setup" subtitle="Build a useful project workspace">
        <div className="quick-start-links"><Link to="/collections"><span><strong>Organize requests</strong><small>Create project collections</small></span><ArrowRight size={15} /></Link><Link to="/environments"><span><strong>Configure environments</strong><small>Set a base URL and variables</small></span><ArrowRight size={15} /></Link><Link to="/explorer"><span><strong>Import API specification</strong><small>Browse documented operations</small></span><ArrowRight size={15} /></Link></div>
      </Panel>
      <div className="overview-refresh"><Button size="sm" onClick={() => { setError(null); if (project) { setLoading(true); Promise.all([workspaceService.listRequests(project.id), workspaceService.listExecutions(project.id)]).then(([requests, history]) => { setRequestCount(requests.pagination.total); setExecutions(history.items) }).catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unable to refresh project activity.')).finally(() => setLoading(false)) } }} disabled={loading}><RefreshCw size={14} /> Refresh activity</Button></div>
    </>}
  </>
}
