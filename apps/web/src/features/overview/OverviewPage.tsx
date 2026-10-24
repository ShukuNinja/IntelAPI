import { useEffect, useState } from 'react'
import { ArrowRight, Database, FileSearch2, FolderOpen, Send } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'

type Project = { id: string; name: string; description: string | null }
type ProjectOverview = { project: Project; counts: { specifications: number; executions: number; campaigns: number; health_checks: number }; recent_executions: { id: string; status_code: number | null; outcome: string; created_at: string }[] }

export function OverviewPage() {
  const [projects, setProjects] = useState<ProjectOverview[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void apiRequest<Project[]>('/v1/projects').then(async items => {
      const summaries = await Promise.all(items.map(project =>
        apiRequest<ProjectOverview>(`/v1/projects/${project.id}/overview`),
      ))
      if (active) setProjects(summaries)
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : 'Unable to load workspace data.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const specificationCount = projects.reduce((sum, project) => sum + project.counts.specifications, 0)
  const executionCount = projects.reduce((sum, project) => sum + project.counts.executions, 0)
  return <>
    <PageHeader eyebrow="WORKSPACE" title="API testing overview" description="A live summary of your projects, imported specifications, and recent requests."
      actions={<><Link to="/explorer"><Button><FileSearch2 size={15} /> Import specification</Button></Link><Link to="/workspace"><Button variant="primary"><Send size={15} /> New request</Button></Link></>} />
    {error && <p role="alert" className="mb-4 text-xs text-rose-300">{error}</p>}
    <div className="metrics-grid">
      {[['Projects', projects.length], ['Specifications', specificationCount], ['Recent requests', executionCount]].map(([label, value]) => <div className="metric-card" key={label}><div className="metric-card__top"><span>{label}</span><span className="metric-icon metric-icon--0"><Database size={16} /></span></div><div className="metric-card__value">{loading ? '…' : value}</div><div className="metric-card__foot"><span className="metric-period">from stored project data</span></div></div>)}
    </div>
    <Panel title="Projects" subtitle="Stored workspaces and their most recent real executions.">
      {loading ? <div className="p-5 text-xs text-slate-400">Loading projects…</div> : projects.length ? <div className="divide-y divide-slate-800">{projects.map(summary => <article key={summary.project.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><FolderOpen size={17} className="text-indigo-300" /><strong className="text-sm text-slate-100">{summary.project.name}</strong><Badge tone="info">{summary.counts.specifications} specs</Badge><Badge>{summary.counts.executions} executions</Badge><Badge>{summary.counts.campaigns} campaigns</Badge><Link className="ml-auto text-xs text-indigo-300 hover:text-indigo-200" to={`/explorer?project=${summary.project.id}`}>Open project <ArrowRight size={13} className="inline" /></Link></div>{summary.project.description && <p className="mb-0 mt-2 text-xs text-slate-400">{summary.project.description}</p>}{summary.recent_executions[0] && <p className="mb-0 mt-2 text-xs text-slate-500">Latest: {summary.recent_executions[0].status_code ?? summary.recent_executions[0].outcome} · {new Date(summary.recent_executions[0].created_at).toLocaleString()}</p>}</article>)}</div> : <div className="p-5"><h3 className="m-0 text-sm font-medium text-slate-100">No projects yet</h3><p className="my-2 text-xs text-slate-400">Create a project in API Explorer, then import its first API specification.</p><Link to="/explorer"><Button variant="primary"><FileSearch2 size={15} /> Go to API Explorer</Button></Link></div>}
    </Panel>
  </>
}
