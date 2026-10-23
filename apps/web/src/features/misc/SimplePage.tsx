import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Clock3, FolderKanban, Settings2, Send } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { apiRequest } from '../../lib/apiClient'

type Kind = 'collections' | 'environments' | 'history' | 'settings'
type Project = { id: string; name: string }
type HistoryEntry = { id: string; method: string; origin: string; status_code: number | null; elapsed_ms: number | null; outcome: string; candidate_id?: string | null; created_at: string }
const config: Record<Kind, { title: string; eyebrow: string; description: string; icon: typeof Boxes; subtitle: string }> = {
  collections: { title: 'Collections', eyebrow: 'REQUEST ORGANIZATION', description: 'Group saved requests into reusable collections.', icon: FolderKanban, subtitle: 'Request collections' },
  environments: { title: 'Environments', eyebrow: 'CONFIGURATION', description: 'Manage base URLs and environment-specific variables safely.', icon: Boxes, subtitle: 'Environment configurations' },
  history: { title: 'Request History', eyebrow: 'ACTIVITY', description: 'Review real executions recorded for your projects.', icon: Clock3, subtitle: 'Recent request executions' },
  settings: { title: 'Settings', eyebrow: 'WORKSPACE CONFIGURATION', description: 'Configure workspace preferences and integrations.', icon: Settings2, subtitle: 'Workspace settings' },
}
export function SimplePage({ kind }: { kind: Kind }) {
  const item = config[kind]
  const Icon = item.icon
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(kind === 'history')
  const [error, setError] = useState('')
  useEffect(() => {
    if (kind !== 'history') return
    let active = true
    void apiRequest<Project[]>('/v1/projects').then(projects => Promise.all(projects.map(project => apiRequest<HistoryEntry[]>(`/v1/projects/${project.id}/executions?limit=50`)))).then(groups => {
      if (active) setEntries(groups.flat().sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 100))
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : 'Unable to load request history.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kind])

  return <>
    <PageHeader eyebrow={item.eyebrow} title={item.title} description={item.description} />
    {error && <p role="alert" className="mb-4 text-xs text-rose-300">{error}</p>}
    <Panel title={item.subtitle} subtitle={kind === 'history' ? 'Status and timing metadata only; request credentials and response bodies are not stored.' : 'This area is not connected to persistent backend resources yet.'}>
      {kind === 'history' ? loading ? <div className="p-5 text-xs text-slate-400">Loading history…</div> : entries.length ? <div className="divide-y divide-slate-800">{entries.map(entry => <div key={entry.id} className="flex flex-wrap items-center gap-3 p-3 text-xs"><Badge tone={entry.status_code != null && entry.status_code < 400 ? 'success' : entry.status_code != null ? 'warning' : 'neutral'}>{entry.status_code ?? entry.outcome}</Badge><strong>{entry.method}</strong><code className="text-slate-400">{entry.origin}</code>{entry.candidate_id && <Badge tone="info">Candidate {entry.candidate_id}</Badge>}<span className="text-slate-500">{entry.elapsed_ms == null ? '—' : `${entry.elapsed_ms} ms`}</span><time className="ml-auto text-slate-500">{new Date(entry.created_at).toLocaleString()}</time></div>)}</div> : <div className="p-5"><p className="mt-0 text-sm text-slate-200">No executions have been recorded yet.</p><Link to="/workspace"><Button variant="primary"><Send size={15} /> Send a request</Button></Link></div> : <div className="p-5"><Icon size={20} className="mb-3 text-slate-500" /><p className="mt-0 text-sm text-slate-200">{item.title} persistence is not implemented yet.</p><p className="text-xs text-slate-400">No sample records are shown. You can still import a specification and send manual requests.</p><div className="flex flex-wrap gap-2"><Link to="/explorer"><Button>Open API Explorer</Button></Link><Link to="/workspace"><Button variant="primary"><Send size={15} /> Open request workspace</Button></Link></div></div>}
    </Panel>
  </>
}
