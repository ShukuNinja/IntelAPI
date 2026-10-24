import { useCallback, useEffect, useState } from 'react'
import { Activity, Ban, FileSearch2, Play, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../../lib/apiClient'
import { useProjectWorkspace } from '../projects/ProjectWorkspaceContext'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'

type Environment = { id: string; name: string }
type GenerationReport = { id: string; specification_id: string; candidate_count: number; operation_count: number; created_at: string }
type GenerationReportDetail = { endpoints: Array<{ operation: { id: string; method: string; path: string; summary?: string }; candidate_count: number }> }
type Campaign = {
  id: string; name: string; project_id: string; state: string; created_at: string
  budget: { max_executions: number; max_iterations: number; max_duration_seconds: number }
  progress: { test_count: number; completed_count: number; execution_count: number; outcomes: Record<string, number> }
}
type CampaignReport = { campaign: Campaign; summary: Campaign['progress']; tests: Array<{ id: string; candidate_key: string; title: string; state: string; execution_id: string | null; result: { outcome?: string; status_code?: number | null; duration_ms?: number | null; error?: string | null } | null }> }
type CampaignEvent = { id: string; sequence_number: number; event_type: string; payload: Record<string, unknown>; created_at: string }

export function CampaignsPage() {
  const { projects, activeProjectId: projectId, setActiveProjectId } = useProjectWorkspace()
  const [reports, setReports] = useState<GenerationReport[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [reportDetail, setReportDetail] = useState<GenerationReportDetail | null>(null)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [report, setReport] = useState<CampaignReport | null>(null)
  const [events, setEvents] = useState<CampaignEvent[]>([])
  const [name, setName] = useState('Contract regression run')
  const [generationReportId, setGenerationReportId] = useState('')
  const [environmentId, setEnvironmentId] = useState('')
  const [baseUrl, setBaseUrl] = useState('http://localhost:8000')
  const [baseline, setBaseline] = useState('{}')
  const [maxExecutions, setMaxExecutions] = useState(10)
  const [confirmUnsafe, setConfirmUnsafe] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSelectedId(''); setReport(null); setEvents([]); setReportDetail(null)
    setGenerationReportId(''); setEnvironmentId(''); setError('')
    setBaseline('{}'); setBaseUrl('')
  }, [projectId])

  const refreshCampaigns = useCallback(async (id: string) => {
    if (!id) { setCampaigns([]); return }
    const items = await apiRequest<Campaign[]>(`/v1/projects/${id}/campaigns`)
    setCampaigns(items)
  }, [])

  const loadSelection = useCallback(async (id: string) => {
    setSelectedId(id)
    if (!id || !projectId) { setReport(null); setEvents([]); return }
    const [nextReport, nextEvents] = await Promise.all([
      apiRequest<CampaignReport>(`/v1/projects/${projectId}/campaigns/${id}/report`),
      apiRequest<CampaignEvent[]>(`/v1/projects/${projectId}/campaigns/${id}/events`),
    ])
    setReport(nextReport)
    setEvents(nextEvents)
  }, [projectId])

  useEffect(() => {
    if (!projectId) { setReports([]); setCampaigns([]); return }
    void Promise.all([
      apiRequest<GenerationReport[]>(`/v1/projects/${projectId}/generation-reports`),
      apiRequest<Environment[]>(`/v1/projects/${projectId}/environments`),
      refreshCampaigns(projectId),
    ]).then(([items, envs]) => {
      setReports(items)
      setEnvironments(envs)
      if (items[0]) setGenerationReportId(current => current || items[0].id)
    }).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load campaign inputs.'))
  }, [projectId, refreshCampaigns])

  useEffect(() => {
    if (!projectId || !generationReportId) { setReportDetail(null); return }
    void apiRequest<GenerationReportDetail>(`/v1/projects/${projectId}/generation-reports/${generationReportId}`)
      .then(setReportDetail)
      .catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to load report operations.'))
  }, [projectId, generationReportId])

  useEffect(() => {
    if (!projectId) return
    const timer = window.setInterval(() => {
      void refreshCampaigns(projectId).catch(() => undefined)
      if (selectedId) void loadSelection(selectedId).catch(() => undefined)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [projectId, selectedId, refreshCampaigns, loadSelection])

  async function createCampaign() {
    if (!projectId || !generationReportId) { setError('Select a project and a generated candidate report.'); return }
    let baselineByOperation: Record<string, unknown>
    try {
      baselineByOperation = JSON.parse(baseline) as Record<string, unknown>
      if (!baselineByOperation || Array.isArray(baselineByOperation) || typeof baselineByOperation !== 'object') throw new Error('Baseline must be a JSON object keyed by operation ID.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Baseline JSON is invalid.'); return }
    setBusy(true)
    try {
      const campaign = await apiRequest<Campaign>(`/v1/projects/${projectId}/campaigns`, {
        method: 'POST',
        body: JSON.stringify({
          name, generation_report_id: generationReportId, base_url: baseUrl,
          environment_id: environmentId || null,
          baseline_by_operation: baselineByOperation, max_executions: maxExecutions,
          max_iterations: maxExecutions, max_duration_seconds: 120, confirm_unsafe: confirmUnsafe,
        }),
      })
      await refreshCampaigns(projectId)
      await loadSelection(campaign.id)
      setError('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to queue campaign.') }
    finally { setBusy(false) }
  }

  async function cancelCampaign() {
    if (!projectId || !selectedId) return
    try {
      await apiRequest<Campaign>(`/v1/projects/${projectId}/campaigns/${selectedId}/cancel`, { method: 'POST' })
      await refreshCampaigns(projectId)
      await loadSelection(selectedId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to cancel campaign.') }
  }

  return <>
    <PageHeader eyebrow="TEST CAMPAIGNS" title="Campaigns" description="Queue bounded contract tests, follow durable progress, and review request outcomes." actions={<Button onClick={() => { if (projectId) void refreshCampaigns(projectId) }}><RefreshCw size={15} /> Refresh</Button>} />
    <Panel title="Create a campaign" subtitle="Campaigns run from saved candidate reports through the same outbound request security controls.">
      <div className="grid gap-3 p-4 md:grid-cols-2">
        <label className="text-xs text-slate-300">Project<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={projectId} onChange={event => { setActiveProjectId(event.target.value); setSelectedId(''); setReport(null); setEvents([]); setReportDetail(null); setGenerationReportId(''); setEnvironmentId('') }}><option value="">Select a project…</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="text-xs text-slate-300">Generation report<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={generationReportId} onChange={event => setGenerationReportId(event.target.value)}><option value="">Select a report…</option>{reports.map(item => <option key={item.id} value={item.id}>{item.candidate_count} candidates · {item.operation_count} operations · {new Date(item.created_at).toLocaleString()}</option>)}</select></label>
        <label className="text-xs text-slate-300">Campaign name<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={name} onChange={event => setName(event.target.value)} /></label>
        <label className="text-xs text-slate-300">Target base URL<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm" value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="https://api.example.com" /></label>
        <label className="text-xs text-slate-300">Environment<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={environmentId} onChange={event => setEnvironmentId(event.target.value)}><option value="">No environment</option>{environments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><span className="mt-1 block text-[11px] text-slate-500">Secret values are resolved by the worker and are not written into campaign requests or events.</span></label>
        <label className="text-xs text-slate-300">Execution budget<input type="number" min={1} max={50} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" value={maxExecutions} onChange={event => setMaxExecutions(Number(event.target.value))} /></label>
        <label className="flex items-center gap-2 self-end pb-2 text-xs text-amber-200"><input type="checkbox" checked={confirmUnsafe} onChange={event => setConfirmUnsafe(event.target.checked)} />Allow state-changing methods in this campaign</label>
        <label className="text-xs text-slate-300 md:col-span-2">Baseline values by operation ID <textarea className="mt-1 min-h-24 w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-xs" value={baseline} onChange={event => setBaseline(event.target.value)} spellCheck={false} />{reportDetail && <span className="mt-2 block text-[11px] text-slate-500">Operation IDs in this report: {reportDetail.endpoints.map(endpoint => `${endpoint.operation.id} (${endpoint.operation.method} ${endpoint.operation.path})`).join(' · ') || 'none'}. Use environment variables such as {'{{token}}'} in headers or bodies instead of pasting secrets here.</span>}</label>
        <div className="flex flex-wrap items-center justify-between gap-3 md:col-span-2"><span className="text-xs text-slate-500">Use an object keyed by operation ID. Values can include path_parameters, query_parameters, headers, and body.</span><Button variant="primary" disabled={busy || !generationReportId} onClick={() => void createCampaign()}><Play size={15} />{busy ? 'Queueing…' : 'Queue campaign'}</Button></div>
        {error && <p role="alert" className="m-0 text-xs text-rose-300 md:col-span-2">{error}</p>}
      </div>
    </Panel>
    <div className="grid gap-4 xl:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.8fr)]">
      <Panel title="Campaign history" subtitle={`${campaigns.length} saved campaign${campaigns.length === 1 ? '' : 's'}`}>
        {campaigns.length ? <div className="divide-y divide-slate-800">{campaigns.map(item => <button key={item.id} type="button" onClick={() => void loadSelection(item.id)} className={`block w-full p-3 text-left hover:bg-slate-900 ${item.id === selectedId ? 'bg-slate-900' : ''}`}><div className="flex items-center justify-between gap-2"><strong className="text-sm text-slate-100">{item.name}</strong><Badge tone={item.state === 'completed' ? 'success' : item.state === 'failed' ? 'warning' : 'neutral'}>{item.state}</Badge></div><p className="mb-0 mt-2 text-xs text-slate-500">{item.progress.completed_count}/{item.progress.test_count} cases · {item.progress.execution_count} requests</p></button>)}</div> : <div className="grid gap-2 p-4 text-xs text-slate-500"><span>No campaign history for this project yet.</span><Link className="inline-flex items-center gap-1 text-cyan-300" to="/explorer"><FileSearch2 size={14} />Generate a candidate report</Link></div>}
      </Panel>
      <div className="grid content-start gap-4">
        <Panel title="Campaign report" subtitle={report ? `${report.summary.execution_count} executions · ${report.summary.test_count} generated tests` : 'Select a campaign to inspect progress and results.'} action={report && !['completed', 'failed', 'cancelled'].includes(report.campaign.state) ? <Button size="sm" onClick={() => void cancelCampaign()}><Ban size={14} /> Cancel</Button> : undefined}>
          {report ? <div className="grid gap-3 p-4"><div className="flex flex-wrap gap-2"><Badge>{report.campaign.state}</Badge><Badge tone="info">{report.summary.completed_count}/{report.summary.test_count} processed</Badge><Badge>{report.summary.execution_count} outbound requests</Badge></div><div className="overflow-auto"><table className="w-full min-w-[520px] text-left text-xs"><thead className="text-slate-500"><tr><th className="p-2">Test case</th><th className="p-2">State</th><th className="p-2">Outcome</th><th className="p-2">Status</th><th className="p-2">Time</th></tr></thead><tbody className="divide-y divide-slate-800">{report.tests.map(test => <tr key={test.id}><td className="max-w-xs p-2 text-slate-200">{test.title}</td><td className="p-2"><Badge>{test.state}</Badge></td><td className="p-2 text-slate-400">{test.result?.outcome ?? '—'}</td><td className="p-2 text-slate-400">{test.result?.status_code ?? '—'}</td><td className="p-2 text-slate-400">{test.result?.duration_ms == null ? '—' : `${test.result.duration_ms} ms`}</td></tr>)}</tbody></table></div>{report.tests.some(test => test.state === 'skipped') && <p className="m-0 text-xs text-slate-500">Some cases need baseline path or body values. Add them by operation ID, then create another campaign.</p>}</div> : <div className="p-5 text-xs text-slate-500">Campaigns are durable in the database. Start the Compose worker to process queued jobs.</div>}
        </Panel>
        <Panel title="Event timeline" subtitle="Append-only campaign lifecycle and execution events.">
          {events.length ? <ol className="grid gap-0 p-3">{events.map(event => <li key={event.id} className="flex gap-3 border-l border-slate-700 pb-3 pl-3 text-xs"><Activity size={14} className="shrink-0 text-cyan-300" /><div><strong className="text-slate-200">{event.event_type.replaceAll('_', ' ')}</strong><time className="ml-2 text-slate-500">{new Date(event.created_at).toLocaleTimeString()}</time><p className="mb-0 mt-1 text-slate-500">{Object.entries(event.payload).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</p></div></li>)}</ol> : <div className="p-4 text-xs text-slate-500">Events appear when a campaign is selected.</div>}
        </Panel>
      </div>
    </div>
  </>
}
