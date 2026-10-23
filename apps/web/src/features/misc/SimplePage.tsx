import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Clock3, FolderKanban, Settings2, Send } from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { apiDownload, apiRequest } from '../../lib/apiClient'

type Kind = 'collections' | 'environments' | 'history' | 'settings'
type Project = { id: string; name: string }
type HistoryEntry = { id: string; method: string; origin: string; status_code: number | null; elapsed_ms: number | null; outcome: string; candidate_id?: string | null; created_at: string }
type ExecutionReportSummary = { id: string; project_id: string; specification_id: string; candidate_id: string; status_code: number | null; created_at: string }
type ExecutionReport = { id: string; execution_id: string; candidate_id: string; candidate: { kind: string; reason: string; mutation: Record<string, unknown> }; operation: { method: string; path: string }; execution: { outcome: string; status_code: number | null; elapsed_ms: number | null; response_bytes: number | null; response_body_persisted: false }; assertions: { kind: string; expected: number; actual: number | null; passed: boolean }[]; contract_findings: { kind: string; confirmed_defect: false }[]; next_action: string }
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
  const [executionReports, setExecutionReports] = useState<ExecutionReportSummary[]>([])
  const [openReport, setOpenReport] = useState<ExecutionReport | null>(null)
  const [loading, setLoading] = useState(kind === 'history')
  const [error, setError] = useState('')
  useEffect(() => {
    if (kind !== 'history') return
    let active = true
    void apiRequest<Project[]>('/v1/projects').then(projects => Promise.all(projects.map(async project => {
      const [history, reports] = await Promise.all([
        apiRequest<HistoryEntry[]>(`/v1/projects/${project.id}/executions?limit=50`),
        apiRequest<ExecutionReportSummary[]>(`/v1/projects/${project.id}/execution-reports?limit=50`),
      ])
      return { history, reports }
    }))).then(groups => {
      if (active) {
        setEntries(groups.flatMap(group => group.history).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 100))
        setExecutionReports(groups.flatMap(group => group.reports).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 100))
      }
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : 'Unable to load request history.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kind])

  async function loadExecutionReport(summary: ExecutionReportSummary) {
    try {
      setOpenReport(await apiRequest<ExecutionReport>(`/v1/projects/${summary.project_id}/execution-reports/${summary.id}`))
      setError('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load the execution report.') }
  }

  async function downloadExecutionReport(format: 'json' | 'markdown' | 'csv') {
    if (!openReport) return
    const summary = executionReports.find(report => report.id === openReport.id)
    if (!summary) return
    const extension = format === 'markdown' ? 'md' : format
    try {
      await apiDownload(`/v1/projects/${summary.project_id}/execution-reports/${summary.id}/export?format=${format}`, `execution-report-${summary.id}.${extension}`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to download the execution report.') }
  }

  return <>
    <PageHeader eyebrow={item.eyebrow} title={item.title} description={item.description} />
    {error && <p role="alert" className="mb-4 text-xs text-rose-300">{error}</p>}
    <Panel title={item.subtitle} subtitle={kind === 'history' ? 'Status and timing metadata only; request credentials and response bodies are not stored.' : 'This area is not connected to persistent backend resources yet.'}>
      {kind === 'history' ? loading ? <div className="p-5 text-xs text-slate-400">Loading history…</div> : entries.length ? <div className="divide-y divide-slate-800">{entries.map(entry => <div key={entry.id} className="flex flex-wrap items-center gap-3 p-3 text-xs"><Badge tone={entry.status_code != null && entry.status_code < 400 ? 'success' : entry.status_code != null ? 'warning' : 'neutral'}>{entry.status_code ?? entry.outcome}</Badge><strong>{entry.method}</strong><code className="text-slate-400">{entry.origin}</code>{entry.candidate_id && <Badge tone="info">Candidate {entry.candidate_id}</Badge>}<span className="text-slate-500">{entry.elapsed_ms == null ? '—' : `${entry.elapsed_ms} ms`}</span><time className="ml-auto text-slate-500">{new Date(entry.created_at).toLocaleString()}</time></div>)}</div> : <div className="p-5"><p className="mt-0 text-sm text-slate-200">No executions have been recorded yet.</p><Link to="/workspace"><Button variant="primary"><Send size={15} /> Send a request</Button></Link></div> : <div className="p-5"><Icon size={20} className="mb-3 text-slate-500" /><p className="mt-0 text-sm text-slate-200">{item.title} persistence is not implemented yet.</p><p className="text-xs text-slate-400">No sample records are shown. You can still import a specification and send manual requests.</p><div className="flex flex-wrap gap-2"><Link to="/explorer"><Button>Open API Explorer</Button></Link><Link to="/workspace"><Button variant="primary"><Send size={15} /> Open request workspace</Button></Link></div></div>}
    </Panel>
    {kind === 'history' && executionReports.length > 0 && <Panel title="Candidate execution reports" subtitle="Persisted run details, assertions, and contract observations. Response bodies are not stored." action={openReport && <div className="flex gap-1">{(['json', 'markdown', 'csv'] as const).map(format => <Button key={format} size="sm" onClick={() => void downloadExecutionReport(format)}>{format.toUpperCase()}</Button>)}</div>}>
      <div className="divide-y divide-slate-800">{executionReports.map(report => <button key={report.id} type="button" onClick={() => void loadExecutionReport(report)} className="flex w-full flex-wrap items-center gap-3 p-3 text-left text-xs hover:bg-slate-900"><Badge tone={report.status_code != null && report.status_code < 400 ? 'success' : 'warning'}>{report.status_code ?? 'blocked'}</Badge><span>Candidate {report.candidate_id}</span><span className="text-slate-500">{new Date(report.created_at).toLocaleString()}</span></button>)}</div>
      {openReport && <div className="border-t border-slate-800 p-4"><div className="mb-2 flex items-center gap-2"><strong className="text-xs text-slate-200">{openReport.operation.method} {openReport.operation.path}</strong><Badge>{openReport.candidate.kind}</Badge></div><p className="text-xs text-slate-300">{openReport.candidate.reason}</p>{openReport.assertions.map((assertion, index) => <p key={index} className="text-xs text-slate-400">{assertion.kind}: expected {assertion.expected}, observed {assertion.actual} · {assertion.passed ? 'passed' : 'failed'}</p>)}{openReport.contract_findings.map(finding => <p key={finding.kind} className="text-xs text-amber-300">{finding.kind}; observation only, not a confirmed defect.</p>)}<p className="text-xs text-slate-400">{openReport.next_action}</p></div>}
    </Panel>}
  </>
}
