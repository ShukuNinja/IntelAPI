import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Play, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { apiRequest } from '../../lib/apiClient'
import { useProjectWorkspace } from '../projects/ProjectWorkspaceContext'

type SavedRequest = { id: string; name: string; method: string; url: string }
type Assertion = { type: string; [key: string]: unknown }
type HealthCheck = { id: string; name: string; saved_request_id: string; enabled: boolean; assertions: Assertion[] }
type Run = { execution_id: string; outcome: string; status_code: number | null; duration_ms: number | null; passed: boolean; created_at: string; assertions: { type: string; passed: boolean; expected: unknown; message: string }[] }

export function HealthChecksPage() {
  const { projects, activeProjectId: projectId, setActiveProjectId } = useProjectWorkspace()
  const [requests, setRequests] = useState<SavedRequest[]>([])
  const [checks, setChecks] = useState<HealthCheck[]>([])
  const [selectedRequestId, setSelectedRequestId] = useState('')
  const [name, setName] = useState('')
  const [assertionsText, setAssertionsText] = useState('[{"type":"status_code","status_code":200}]')
  const [editingId, setEditingId] = useState('')
  const [runs, setRuns] = useState<Record<string, Run[]>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setEditingId(''); setSelectedRequestId(''); setRuns({}); setError('')
  }, [projectId])

  const refresh = useCallback(async () => {
    if (!projectId) { setChecks([]); setRequests([]); return }
    try {
      const [saved, items] = await Promise.all([
        apiRequest<SavedRequest[]>(`/v1/projects/${projectId}/saved-requests`),
        apiRequest<HealthCheck[]>(`/v1/projects/${projectId}/health-checks`),
      ])
      setRequests(saved)
      setChecks(items)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load health checks.') }
  }, [projectId])

  useEffect(() => { void refresh() }, [refresh])

  function edit(check: HealthCheck) {
    setEditingId(check.id); setName(check.name); setSelectedRequestId(check.saved_request_id)
    setAssertionsText(JSON.stringify(check.assertions, null, 2)); setError('')
  }

  async function save() {
    if (!projectId || !selectedRequestId || !name.trim()) { setError('Select a project and saved request, and enter a name.'); return }
    let assertions: Assertion[]
    try {
      assertions = JSON.parse(assertionsText) as Assertion[]
      if (!Array.isArray(assertions) || assertions.length < 1 || assertions.length > 20) throw new Error('Use an array containing 1 to 20 assertions.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Assertions must be a JSON array.'); return }
    setBusy(true); setError('')
    try {
      await apiRequest(`/v1/projects/${projectId}/health-checks${editingId ? `/${editingId}` : ''}`, {
        method: editingId ? 'PATCH' : 'POST', body: JSON.stringify({ name, saved_request_id: selectedRequestId, enabled: true, assertions }),
      })
      setEditingId(''); setName(''); setSelectedRequestId(''); setAssertionsText('[{"type":"status_code","status_code":200}]')
      await refresh()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save health check.') }
    finally { setBusy(false) }
  }

  async function remove(checkId: string) {
    if (!projectId) return
    setBusy(true)
    try { await apiRequest(`/v1/projects/${projectId}/health-checks/${checkId}`, { method: 'DELETE' }); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to delete health check.') }
    finally { setBusy(false) }
  }

  async function run(check: HealthCheck) {
    setBusy(true); setError('')
    try {
      await apiRequest(`/v1/projects/${projectId}/health-checks/${check.id}/run`, { method: 'POST' })
      const history = await apiRequest<Run[]>(`/v1/projects/${projectId}/health-checks/${check.id}/runs`)
      setRuns(current => ({ ...current, [check.id]: history }))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Health check run failed.') }
    finally { setBusy(false) }
  }

  async function loadRuns(check: HealthCheck) {
    try {
      const history = await apiRequest<Run[]>(`/v1/projects/${projectId}/health-checks/${check.id}/runs`)
      setRuns(current => ({ ...current, [check.id]: history }))
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load health-check history.') }
  }

  return <>
    <PageHeader eyebrow="OBSERVABILITY" title="Health Checks" description="Save repeatable assertions for read-only requests and inspect their run history." />
    <Panel title="Check definitions" subtitle="Checks use saved GET, HEAD, or OPTIONS requests and the shared bounded outbound executor.">
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2"><label className="text-xs text-slate-300">Project<select className="ml-2 rounded border border-slate-700 bg-slate-900 px-3 py-2" value={projectId} onChange={event => setActiveProjectId(event.target.value)}><option value="">Select project…</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><Button size="sm" onClick={() => void refresh()}><RefreshCw size={14} /> Refresh</Button></div>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
        <div className="grid gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4 md:grid-cols-2"><label className="text-xs text-slate-300">Check name<input className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2" value={name} onChange={event => setName(event.target.value)} placeholder="Production readiness" /></label><label className="text-xs text-slate-300">Saved request<select className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 px-3 py-2" value={selectedRequestId} onChange={event => setSelectedRequestId(event.target.value)}><option value="">Choose a read-only request…</option>{requests.map(item => <option key={item.id} value={item.id}>{item.method} {item.name} · {item.url}</option>)}</select></label><label className="text-xs text-slate-300 md:col-span-2">Assertions (JSON)<textarea className="mt-1 block min-h-28 w-full rounded border border-slate-700 bg-slate-900 p-3 font-mono text-xs" value={assertionsText} onChange={event => setAssertionsText(event.target.value)} /><span className="mt-1 block text-[11px] text-slate-500">Supported: status_code, latency_ms, json_pointer (exists/equals/type), header_equals (allowlisted headers), response_schema.</span></label><div className="flex gap-2"><Button variant="primary" disabled={busy} onClick={() => void save()}><Plus size={14} /> {editingId ? 'Update check' : 'Save check'}</Button>{editingId && <Button disabled={busy} onClick={() => { setEditingId(''); setName(''); setSelectedRequestId('') }}>Cancel edit</Button>}</div></div>
        {checks.length === 0 ? <div className="rounded border border-slate-800 p-4"><Activity size={20} className="mb-2 text-slate-500" /><p className="m-0 text-sm text-slate-200">No health checks configured.</p><p className="text-xs text-slate-400">Save a read-only request in the workspace first, then create a check here.</p><Link to="/workspace"><Button><Plus size={15} /> Open API Workspace</Button></Link></div> : <div className="space-y-3">{checks.map(check => <article key={check.id} className="rounded-lg border border-slate-800 p-4"><div className="flex flex-wrap items-center gap-2"><strong className="text-sm text-slate-100">{check.name}</strong><Badge>{check.assertions.length} assertions</Badge><span className="ml-auto flex gap-2"><Button size="sm" disabled={busy} onClick={() => void run(check)}><Play size={13} /> Run now</Button><Button size="sm" onClick={() => edit(check)}>Edit</Button><Button size="sm" disabled={busy} onClick={() => void remove(check.id)}><Trash2 size={13} /> Delete</Button></span></div><div className="mt-3 flex flex-wrap gap-2">{check.assertions.map((item, index) => <Badge key={index}>{item.type}</Badge>)}</div><Button size="sm" className="mt-3" onClick={() => void loadRuns(check)}>Show run history</Button>{runs[check.id]?.map(item => <div key={item.execution_id} className="mt-3 rounded border border-slate-800 bg-slate-950/50 p-3"><div className="flex items-center gap-2"><Badge tone={item.passed ? 'success' : 'warning'}>{item.passed ? 'passed' : 'failed'}</Badge><span className="text-xs text-slate-400">{item.outcome} · {item.status_code ?? 'no HTTP response'} · {item.duration_ms ?? '—'} ms</span><span className="ml-auto text-[11px] text-slate-500">{new Date(item.created_at).toLocaleString()}</span></div>{item.assertions.map((result, index) => <p key={index} className="mb-0 text-xs text-slate-400">{result.message} · {result.passed ? 'passed' : 'failed'}</p>)}</div>)}</article>)}</div>}
      </div>
    </Panel>
  </>
}
